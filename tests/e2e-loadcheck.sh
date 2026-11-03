#!/bin/sh
# e2e-loadcheck.sh -- checks packaging/healer/omg-load-check (the test instance) against a fake OBS:
# a fake obs that writes OBS's log lines (or does not) and leaves a child behind, and a fake
# xvfb-run. Real dpkg-deb packs a small package. Nothing real is started.
#   sh tests/e2e-loadcheck.sh [--prove-red]     (--prove-red plants faults in a copy; each must go RED)
# LOADCHECK=path checks another copy.
set -u
here=$(cd "$(dirname "$0")" && pwd); top=$(dirname "$here")
if [ "${1:-}" = --prove-red ]; then
  t=$(mktemp -d); bad=0
  plant() {
    cp "$top/packaging/healer/omg-load-check" "$t/lc"; sed "$2" "$t/lc" > "$t/lc2"
    if cmp -s "$t/lc" "$t/lc2"; then echo "PLANT FAILED  $1"; bad=1; return; fi
    if LOADCHECK=$t/lc2 sh "$0" > "$t/log" 2>&1; then echo "STAYED GREEN  $1"; bad=1; else echo "went red      $1  ($(grep -m1 '^RED' "$t/log"))"; fi
  }
  plant "the group is not stopped"        's/kill -TERM "-\$pg" 2>\/dev\/null; sleep 2; kill -KILL "-\$pg" 2>\/dev\/null/:/'
  plant "the throwaway HOME is kept"       's/|| rm -rf "\$T"/|| :/'
  plant "any log line counts as loaded"    's/\\\[obsmage-core\\\] loaded/info/'
  plant "no record written"                's/^printf .when=%s\\ndeb=.*$/:/'
  rm -rf "$t"
  [ $bad = 0 ] && echo "PROVE-RED OK" || { echo "PROVE-RED FAILED"; exit 1; }
  exit 0
fi
LC=${LOADCHECK:-$top/packaging/healer/omg-load-check}
T=$(mktemp -d); trap 'pkill -f "omg-stray-$$" 2>/dev/null; rm -rf "$T"' EXIT INT TERM
pass=0; fail=0
ok()  { pass=$((pass + 1)); echo "ok    $1"; }
red() { fail=$((fail + 1)); echo "RED   $1"; }
mkdir -p "$T/bin" "$T/work" "$T/tmp" "$T/pkg/DEBIAN" "$T/pkg/usr/lib/x86_64-linux-gnu/obs-plugins" "$T/pkg/usr/share/obs/obs-plugins/obsmage-core/locale"
printf 'Package: obsmage\nVersion: 0.0.1\nArchitecture: all\nMaintainer: E <e@example.invalid>\nDescription: t\n' > "$T/pkg/DEBIAN/control"
echo so > "$T/pkg/usr/lib/x86_64-linux-gnu/obs-plugins/obsmage-core.so"; echo "x=1" > "$T/pkg/usr/share/obs/obs-plugins/obsmage-core/locale/en-US.ini"
dpkg-deb --root-owner-group --build "$T/pkg" "$T/work/obsmage_0.0.1_amd64.deb" >/dev/null
printf 'WORK=%s\n' "$T/work" > "$T/heal.conf"
cat > "$T/bin/xvfb-run" <<'X'
#!/bin/sh
while [ $# -gt 0 ]; do case $1 in -a) shift ;; -s) shift 2 ;; *) break ;; esac; done
exec "$@"
X
cat > "$T/bin/obs" <<X
#!/bin/sh
[ "\${1:-}" = --version ] && { echo "OBS Studio - 32.1.0-fake"; exit 0; }
L=\$HOME/.config/obs-studio/logs; mkdir -p "\$L"
[ -f "\$HOME/.config/obs-studio/plugins/obsmage-core/bin/64bit/obsmage-core.so" ] || { echo "no plugin" > "\$L/a.txt"; sleep 300; }
sh -c 'sleep 300' omg-stray-$$ &
echo "info: Loading module: obsmage-core.so" >> "\$L/a.txt"
[ -f "$T/silent" ] || echo "info: [obsmage-core] loaded; display-binding audit runs here (read-only)" >> "\$L/a.txt"
sleep 300
X
chmod +x "$T/bin/"*
export PATH="$T/bin:$PATH" TMPDIR="$T/tmp"

# L1 the plugin loads: exit 0, a record, its log lines shown
out=$(LOAD_SECS=10 sh "$LC" --conf "$T/heal.conf" 2>&1); rc=$?
[ $rc = 0 ] && echo "$out" | grep -q 'loaded in OBS Studio - 32.1.0-fake' && echo "$out" | grep -q '\[obsmage-core\] loaded' \
  && ok "L1 loaded: exit 0, said, log lines shown" || red "L1 loaded (rc=$rc): $(echo "$out" | tail -n 1)"
grep -q '^result=loaded$' "$T/work/state/load-check" 2>/dev/null && [ "$(wc -l < "$T/work/state/load.tsv")" = 1 ] && ok "L2 the run is recorded" || red "L2 the run is recorded"

# L3 nothing OBS started is left running; L4 no throwaway HOME left behind
sleep 1
pgrep -f "omg-stray-$$" >/dev/null && red "L3 OBS and its children stopped" || ok "L3 OBS and its children stopped"
[ -z "$(ls "$T/tmp")" ] && ok "L4 the throwaway HOME is gone" || red "L4 the throwaway HOME is gone ($(ls "$T/tmp"))"

# L5 the plugin never says it loaded: exit 1, recorded as not-loaded, still nothing left running
touch "$T/silent"
out=$(LOAD_SECS=3 sh "$LC" --conf "$T/heal.conf" 2>&1); rc=$?
sleep 1
[ $rc = 1 ] && grep -q '^result=not-loaded$' "$T/work/state/load-check" && ! pgrep -f "omg-stray-$$" >/dev/null \
  && ok "L5 not loaded: exit 1, recorded, nothing left" || red "L5 not loaded (rc=$rc)"

# L6 no OBS on this host: exit 3, says so, nothing recorded as a failure of the plugin
mkdir -p "$T/bin2"; for x in xvfb-run; do cp "$T/bin/$x" "$T/bin2/"; done
out=$(PATH="$T/bin2:/usr/bin:/bin" sh "$LC" --conf "$T/heal.conf" 2>&1); rc=$?
if command -v obs >/dev/null 2>&1 && [ "$(command -v obs)" != "$T/bin/obs" ]; then ok "L6 skipped (a real obs is installed here)"
else [ $rc = 3 ] && echo "$out" | grep -q 'obs is not installed' && ok "L6 no OBS: exit 3 and said" || red "L6 no OBS (rc=$rc)"; fi

echo "e2e-loadcheck: $pass ok, $fail RED"
[ $fail = 0 ]

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin, claude-opus-5-5)
