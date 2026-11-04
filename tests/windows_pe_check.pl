#!/usr/bin/perl
# windows_pe_check.pl -- the second witness on obsmage-core.dll, in Perl (core modules only): it reads the PE file
# itself, sharing no code or tools with tests/e2e-windows.sh (which asks binutils' objdump) or with omg-win (sh),
# the NSIS script or the C it checks.
#   perl tests/windows_pe_check.pl DLL DEF...      one line per check; exit 0 all ok, 1 a check is RED, 2 usage
# What it holds the DLL to:
#   P1 an x86-64 (PE32+) DLL;
#   P2 no link timestamp (0), so the same commit gives the same bytes;
#   P3 it exports what libobs requires of a module (obs_module_load, obs_module_set_pointer, obs_module_ver);
#   P4 it imports from no DLL but OBS's two and Windows' own (KERNEL32, msvcrt), and nothing by ordinal;
#   P5 each function it imports from an OBS DLL is listed in the .def named for that DLL (LIBRARY line).
use strict;
use warnings;

@ARGV >= 2 or do { print STDERR "usage: windows_pe_check.pl DLL DEF...\n"; exit 2 };
my ($dll, @defs) = @ARGV;
open(my $fh, '<:raw', $dll) or do { print STDERR "windows_pe_check: cannot read $dll\n"; exit 2 };
my $b = do { local $/; <$fh> };
close $fh;

my ($pass, $fail) = (0, 0);
sub ok  { $pass++; print "ok    $_[0]\n" }
sub red { $fail++; print "RED   $_[0]\n" }
sub u16 { unpack('v', substr($b, $_[0], 2)) }
sub u32 { unpack('V', substr($b, $_[0], 4)) }
sub cstr { my $o = shift; my $e = index($b, "\0", $o); $e < 0 ? '' : substr($b, $o, $e - $o) }

substr($b, 0, 2) eq 'MZ' or do { red("P1 not a PE file (no MZ)"); exit 1 };
my $pe = u32(0x3c);
substr($b, $pe, 4) eq "PE\0\0" or do { red("P1 not a PE file (no PE signature)"); exit 1 };
my ($machine, $nsec, $stamp, $optsz, $chars) = (u16($pe + 4), u16($pe + 6), u32($pe + 8), u16($pe + 20), u16($pe + 22));
my $opt = $pe + 24;
my $magic = u16($opt);
($machine == 0x8664 && $magic == 0x20b && ($chars & 0x2000))
  ? ok("P1 an x86-64 PE32+ DLL")
  : red(sprintf("P1 an x86-64 PE32+ DLL (machine %#x, magic %#x, characteristics %#x)", $machine, $magic, $chars));
$stamp == 0 ? ok("P2 no link timestamp") : red("P2 no link timestamp (it is $stamp)");

my @sec;
my $st = $opt + $optsz;
for my $i (0 .. $nsec - 1) {
  my $s = $st + 40 * $i;
  my ($vsz, $va, $rawsz, $raw) = (u32($s + 8), u32($s + 12), u32($s + 16), u32($s + 20));
  push @sec, [$va, ($vsz > $rawsz ? $vsz : $rawsz), $raw];
}
sub off {
  my $rva = shift;
  for my $s (@sec) { return $rva - $s->[0] + $s->[2] if $rva >= $s->[0] && $rva < $s->[0] + $s->[1] }
  return undef;
}
my $ndir = u32($opt + 108);
my ($exp_rva, $imp_rva) = ($ndir > 0 ? u32($opt + 112) : 0, $ndir > 1 ? u32($opt + 120) : 0);

my %exports;
if ($exp_rva and defined(my $e = off($exp_rva))) {
  my ($n, $names) = (u32($e + 24), u32($e + 32));
  for my $i (0 .. $n - 1) { $exports{ cstr(off(u32(off($names) + 4 * $i))) } = 1 }
}
my @need = grep { !$exports{$_} } qw(obs_module_load obs_module_set_pointer obs_module_ver);
@need ? red("P3 exports what libobs requires (missing: @need)") : ok("P3 exports what libobs requires");

my %allowed = map { $_ => 1 } qw(obs.dll obs-frontend-api.dll kernel32.dll msvcrt.dll);
my (%imports, @stray, @ordinal);
if ($imp_rva and defined(my $d = off($imp_rva))) {
  for (my $i = 0; ; $i++) {
    my $desc = $d + 20 * $i;
    my ($oft, $nm, $ft) = (u32($desc), u32($desc + 12), u32($desc + 16));
    last unless $oft || $nm || $ft;
    my $lib = lc cstr(off($nm));
    push @stray, $lib unless $allowed{$lib};
    my $t = off($oft || $ft);
    for (my $j = 0; ; $j++) {
      my ($lo, $hi) = (u32($t + 8 * $j), u32($t + 8 * $j + 4));
      last unless $lo || $hi;
      if ($hi & 0x80000000) { push @ordinal, "$lib#" . ($lo & 0xffff); next }
      push @{ $imports{$lib} }, cstr(off($lo) + 2);
    }
  }
}
(@stray || @ordinal)
  ? red("P4 imports only from OBS and Windows (" . join(', ', (map {"stray $_"} @stray), (map {"ordinal $_"} @ordinal)) . ")")
  : ok("P4 imports only from OBS and Windows (" . join(', ', sort keys %imports) . ")");

my %def;
for my $f (@defs) {
  open(my $d, '<', $f) or do { red("P5 cannot read $f"); next };
  my ($lib, $in) = ('', 0);
  while (my $l = <$d>) {
    $l =~ s/;.*//; $l =~ s/^\s+|\s+$//g;
    next if $l eq '';
    if ($l =~ /^LIBRARY\s+"?([^"\s]+)"?/i) { $lib = lc $1; next }
    if ($l =~ /^EXPORTS$/i) { $in = 1; next }
    $def{$lib}{(split /\s+/, $l)[0]} = 1 if $in && $lib ne '';
  }
  close $d;
}
my @undeclared;
for my $lib ('obs.dll', 'obs-frontend-api.dll') {
  push @undeclared, map { "$lib:$_" } grep { !$def{$lib}{$_} } @{ $imports{$lib} || [] };
}
my $n = 0; $n += scalar @{ $imports{$_} || [] } for ('obs.dll', 'obs-frontend-api.dll');
(@undeclared || $n == 0)
  ? red("P5 every OBS function imported is in its .def (" . ($n ? "not listed: @undeclared" : "no OBS imports at all") . ")")
  : ok("P5 every OBS function imported is in its .def ($n functions)");

print "windows_pe_check: $pass ok, $fail RED\n";
exit($fail ? 1 : 0);

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin, claude-opus-5-5)
