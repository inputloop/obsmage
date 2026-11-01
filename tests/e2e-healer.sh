#!/bin/sh
# e2e-healer.sh -- end-to-end test of packaging/healer/omg-heal against a throwaway git repo.
# Run: dash tests/e2e-healer.sh        HEAL_PROVE_RED=1 dash tests/e2e-healer.sh  (must go red)
# Exit: 0 all passed (or, with HEAL_PROVE_RED=1, the harness went red as it should); 1 otherwise.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
REAL=$HERE/../packaging/healer/omg-heal
T=$(mktemp -d) || exit 1
trap 'rm -rf "$T"' EXIT
export HOME=$T GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@example.invalid GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@example.invalid

PASS=0; FAIL=0
ok()   { PASS=$((PASS + 1)); printf 'ok   %s\n' "$1"; }
bad()  { FAIL=$((FAIL + 1)); printf 'FAIL %s\n' "$1"; }
has()  { case $2 in *"$3"*) ok "$1" ;; *) bad "$1 (wanted '$3' in: $2)" ;; esac; }
lacks(){ case $2 in *"$3"*) bad "$1 (unexpected '$3' in: $2)" ;; *) ok "$1" ;; esac; }
eq()   { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected '$2' got '$3')"; fi; }

HEAL=$REAL
if [ "${HEAL_PROVE_RED:-0}" = 1 ]; then
    # planted fault: signature check always passes, so the unsigned tag is wrongly accepted
    HEAL=$T/omg-heal-faulty
    sed 's/^# FAULT-POINT$/check_signed() { return 0; }/' "$REAL" > "$HEAL"
    printf 'PROVE-RED: running against a copy of omg-heal whose signature check always passes\n'
fi
H() { dash "$HEAL" "$@"; }

# ---- the throwaway upstream
R=$T/upstream
git init -q "$R" && git -C "$R" symbolic-ref HEAD refs/heads/main
git -C "$R" config commit.gpgsign false; git -C "$R" config tag.gpgsign false
printf 'hello\nworld\n' > "$R/README"; printf '0.1.0\n' > "$R/VERSION"
git -C "$R" add -A && git -C "$R" commit -q -m first
git -C "$R" tag -a v0.1.0 -m 'release 0.1.0 (unsigned)'
TAGSHA=$(git -C "$R" rev-parse 'v0.1.0^{commit}')
printf 'news\n' > "$R/NEWS"; git -C "$R" add -A && git -C "$R" commit -q -m 'main moves on'
TIP=$(git -C "$R" rev-parse HEAD)
[ "$TAGSHA" != "$TIP" ] && ok "fixture: tag and tip differ"

# ---- patches for upstream 0.1.0
P=$T/patches/0.1.0; mkdir -p "$P"
cat > "$P/upstream.patch" <<'X'
--- a/README
+++ b/README
@@ -1 +1,2 @@
 hello
+world
X
cat > "$P/good.patch" <<'X'
--- a/README
+++ b/README
@@ -1,2 +1,3 @@
 hello
 world
+patched
X
printf '# our queue\nupstream.patch\ngood.patch\nmissing.patch\n' > "$P/series"
B=$T/badpatches/0.1.0; mkdir -p "$B"
cat > "$B/bad.patch" <<'X'
--- a/README
+++ b/README
@@ -1,2 +1,2 @@
 nothere
-nor
+this
X
printf 'bad.patch\n' > "$B/series"
mkdir -p "$T/deb"; printf 'Source: obsmage\n' > "$T/deb/control"

conf() { # file follow build [extra lines...]
    f=$1; fo=$2; bu=$3; shift 3
    { printf 'SRC=%s\nWORK=%s\nPULL=no\nBUILD=%s\nPATCHES=%s\nDEBIAN=%s\n' "$R" "$T/work" "$bu" "$T/patches" "$T/deb"
      [ -n "$fo" ] && printf 'FOLLOW=%s\n' "$fo"
      for l in "$@"; do printf '%s\n' "$l"; done; } > "$f"
}

# ---- plan: each follow mode
conf "$T/default.conf" "" deb
out=$(H --conf "$T/default.conf" plan 2>&1); rc=$?
eq "plan default (no FOLLOW) exits 0" 0 $rc
has "plan default follows main tip" "$out" "Would build:      branch main at $TIP"
has "plan default says it is the default" "$out" "(the default)"
has "plan sees the patch series" "$out" "Patches:          3 entries"

conf "$T/main.conf" main deb
out=$(H --conf "$T/main.conf" plan 2>&1)
has "plan main picks the tip" "$out" "branch main at $TIP"

conf "$T/tagged.conf" tagged deb
out=$(H --conf "$T/tagged.conf" plan 2>&1); rc=$?
eq "plan tagged exits 0" 0 $rc
has "plan tagged picks v0.1.0" "$out" "Would build:      tag v0.1.0 at $TAGSHA"

conf "$T/meta.conf" meta deb
out=$(H --conf "$T/meta.conf" plan 2>&1); rc=$?
eq "plan meta exits 0" 0 $rc
has "plan meta picks the tag for VERSION 0.1.0" "$out" "tag v0.1.0 at $TAGSHA"
has "plan meta explains where the version came from" "$out" "the VERSION file"

conf "$T/signed.conf" tagged+signed deb
out=$(H --conf "$T/signed.conf" plan 2>&1); rc=$?
eq "tagged+signed refuses the unsigned tag (exit 4)" 4 $rc
has "tagged+signed says REFUSED plainly" "$out" "REFUSED: tag v0.1.0 is not signed"
lacks "tagged+signed prints no build line" "$out" "Would build"

# ---- plan has no side effects
[ -e "$T/work" ] && bad "plan created WORK" || ok "plan left WORK alone"

# ---- dry-run build
conf "$T/deb.conf" main deb
out=$(H --conf "$T/deb.conf" --dry-run build 2>&1); rc=$?
eq "dry-run deb build exits 0" 0 $rc
has "dry-run prints dpkg-buildpackage" "$out" "dpkg-buildpackage -us -uc -b"
has "dry-run says it would apply patches" "$out" "would apply"
[ -e "$T/work" ] && bad "dry-run created WORK" || ok "dry-run created nothing"

# ---- real source build with patches (needs xz)
conf "$T/src.conf" main source
if command -v xz >/dev/null 2>&1; then
    out=$(H --conf "$T/src.conf" build 2>&1); rc=$?
    eq "source build exits 0" 0 $rc
    has "reports patch skipped as already upstream" "$out" "SKIPPED upstream.patch: already in upstream"
    has "reports missing patch skipped" "$out" "SKIPPED missing.patch"
    has "reports good patch applied" "$out" "APPLIED good.patch"
    S=$(printf '%.8s' "$TIP")
    eq "patched tree has the patched line" patched "$(tail -n 1 "$T/work/build-$S/README" 2>/dev/null)"
    [ -f "$T/work/obsmage-0.1.0+git$S.tar.xz" ] && ok "source tarball written" || bad "source tarball missing"

    # ---- heal: build, up to date, then newer ref
    rm -rf "$T/work"
    out=$(H --conf "$T/src.conf" heal 2>&1); rc=$?; eq "heal #1 builds (exit 0)" 0 $rc
    has "heal #1 says why" "$out" "no earlier build record"
    out=$(H --conf "$T/src.conf" heal 2>&1); has "heal #2 finds nothing to do" "$out" "Up to date"
    printf 'more\n' >> "$R/NEWS"; git -C "$R" commit -q -am 'newer'
    out=$(H --conf "$T/src.conf" heal 2>&1); has "heal #3 sees the moved ref" "$out" "the followed ref moved"
    res=$(cut -f5 "$T/work/state/heal.tsv" | tr '\n' ' ')
    eq "heal.tsv records ok, uptodate, ok" "ok uptodate ok " "$res"
    eq "heal.tsv has five tab-separated columns" 5 "$(head -n 1 "$T/work/state/heal.tsv" | awk -F'\t' '{print NF}')"
    out=$(H --conf "$T/src.conf" status 2>&1); has "status speaks plainly" "$out" "result ok"

    # ---- a patch that fits neither way stops the build
    conf "$T/bad.conf" tagged source "PATCHES=$T/badpatches"
    out=$(H --conf "$T/bad.conf" build 2>&1); rc=$?
    eq "unapplicable patch exits 7" 7 $rc
    has "unapplicable patch is named" "$out" "FAILED bad.patch"
    out=$(H --conf "$T/bad.conf" status 2>&1); has "failed build is recorded" "$out" "result failed"
else
    printf 'SKIP source/heal checks: xz is not installed (apt install xz-utils)\n'
fi

# ---- meta with an unreleased VERSION
printf '0.2.0\n' > "$R/VERSION"; git -C "$R" commit -q -am 'bump to 0.2.0, not tagged'
out=$(H --conf "$T/meta.conf" plan 2>&1); rc=$?
eq "meta with no matching tag exits 5" 5 $rc
has "meta says why it will not build" "$out" "not released yet; not building"
NEWTIP=$(git -C "$R" rev-parse HEAD)
out=$(H --conf "$T/main.conf" plan 2>&1); has "main still follows the new tip" "$out" "branch main at $NEWTIP"
out=$(H --conf "$T/tagged.conf" plan 2>&1); has "tagged still builds v0.1.0" "$out" "tag v0.1.0"

# ---- the healer's own self-checks, green and planted-red
out=$(dash "$REAL" selftest 2>&1); eq "omg-heal selftest green" 0 $?
out=$(dash "$REAL" --prove-red 2>&1); rc=$?; eq "omg-heal --prove-red sees red" 0 $rc

printf '\n%s passed, %s failed\n' "$PASS" "$FAIL"
if [ "${HEAL_PROVE_RED:-0}" = 1 ]; then
    if [ "$FAIL" -gt 0 ]; then printf 'PROVE-RED: ok - the harness went red with the planted fault\n'; exit 0; fi
    printf 'PROVE-RED: FAILED - the harness stayed green with a planted fault\n'; exit 1
fi
[ "$FAIL" -eq 0 ]

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later
# Mentat (for Corwin; claude-sonnet via subagent)
