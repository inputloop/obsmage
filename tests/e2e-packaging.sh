#!/bin/sh
# e2e-packaging.sh -- checks that the Debian packaging and the user-mode healer units are whole.
# Judges with grep, test and sed only (no shared code with the Python tests).
# usage: sh tests/e2e-packaging.sh [--prove-red]   (--prove-red plants faults; the checks must go RED)
set -u
here=$(cd "$(dirname "$0")" && pwd); top=$(dirname "$here")
t=$(mktemp -d); trap 'rm -rf "$t"' EXIT
cp -R "$top/debian" "$t/debian"; mkdir -p "$t/user"; cp "$top"/packaging/healer/user/* "$t/user/"
if [ "${1:-}" = --prove-red ]; then
  sed -i '/^ExecStart=/d' "$t/user/obsmage-heal.service"
  echo 'User=obsmage-heal' >> "$t/user/obsmage-heal.service"
  rm "$t/debian/source/format"
  sed -i 's/^Package: obsmage/Package: other/' "$t/debian/control"
fi
pass=0; fail=0
ok()  { pass=$((pass + 1)); echo "ok    $1"; }
red() { fail=$((fail + 1)); echo "RED   $1"; }
chk() { desc=$1; shift; if "$@" >/dev/null 2>&1; then ok "$desc"; else red "$desc"; fi; }
no()  { ! "$@"; }

S="$t/user/obsmage-heal.service"; T="$t/user/obsmage-heal.timer"
chk "user service runs omg-heal heal" grep -q '^ExecStart=.*omg-heal .*heal$' "$S"
chk "user service has no User=" no grep -q '^User=' "$S"
chk "user service has no StateDirectory=" no grep -q '^StateDirectory=' "$S"
chk "user timer is daily and installs into timers.target" sh -c "grep -q '^OnCalendar=daily' '$T' && grep -q '^WantedBy=timers.target' '$T'"
chk "debian/control names the package" grep -q '^Package: obsmage$' "$t/debian/control"
chk "debian/control builds against libobs-dev" grep -q 'Build-Depends:.*libobs-dev' "$t/debian/control"
chk "debian/source/format is native" grep -q 'native' "$t/debian/source/format"
chk "debian/changelog has a version" grep -Eq '^obsmage \([0-9][^)]*\) ' "$t/debian/changelog"
chk "debian/rules is executable" test -x "$top/debian/rules"
# every file the rules install must exist in the tree
miss=0
for f in $(sed -e ':a' -e '/\\$/{N;s/\\\n//;ba' -e '}' "$top/debian/rules" | sed -n 's/^[[:space:]]*install -m 0[0-9]* \(.*\) debian\/obsmage.*/\1/p' | tr ' \t' '\n\n' | grep '/'); do
  [ -e "$top/$f" ] || { echo "      missing: $f"; miss=1; }
done
chk "every file debian/rules installs exists" test $miss = 0
echo "e2e-packaging: $pass ok, $fail RED"
if [ "${1:-}" = --prove-red ]; then [ $fail -gt 0 ] && echo "PROVE-RED ok: the checks went red" && exit 0; echo "PROVE-RED FAILED: stayed green"; exit 1; fi
[ $fail = 0 ]
