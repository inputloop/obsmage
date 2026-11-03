#!/bin/sh
# e2e.sh -- end-to-end check of tools/omg_atoms.py against tests/SPEC.txt (AT1-AT9), in POSIX sh.
# It drives the CLI only and judges results with cmp, grep and stat -- no shared code with
# tests/test_atoms.py.   usage: sh tests/e2e.sh [--prove-red]
# --prove-red plants a secret into the atom store after split; AT2 must then go RED.
set -u
here=$(cd "$(dirname "$0")" && pwd); top=$(dirname "$here")
omg="python3 $top/tools/omg_atoms.py"; fix="$here/fixtures/config-small"
t=$(mktemp -d); trap 'rm -rf "$t"' EXIT
pass=0; fail=0
ok()  { pass=$((pass + 1)); echo "ok    $1"; }
red() { fail=$((fail + 1)); echo "RED   $1"; }

$omg split "$fix" "$t/atoms" --vault "$t/vault.kv" >/dev/null || red "split ran"
[ "${1:-}" = --prove-red ] && echo "Token=FAKEFAKEFAKEtoken0000" >> "$t/atoms/basic/profiles/Demo/basic.ini/set-Twitch.kv"

# AT1
$omg join "$t/atoms" "$t/out" --vault "$t/vault.kv" >/dev/null
at1=ok
for f in basic/profiles/Demo/basic.ini global.ini; do cmp -s "$fix/$f" "$t/out/$f" || at1=no; done
for f in basic/profiles/Demo/service.json basic/scenes/Demo.json; do
  python3 -c 'import json,sys; sys.exit(json.load(open(sys.argv[1]))!=json.load(open(sys.argv[2])))' "$fix/$f" "$t/out/$f" || at1=no
done
[ $at1 = ok ] && ok "AT1 lossless round trip" || red "AT1 lossless round trip"

# AT2
$omg rollup "$t/atoms" "$t/STAGES.md" >/dev/null
leak=0
for s in FAKEFAKEFAKEtoken0000 FAKErefresh00000000000000 FAKEsecretFAKEsecret== live_FAKE_stream_key_123456; do
  grep -rqF -- "$s" "$t/atoms" "$t/STAGES.md" && leak=1
done
grep -q '^Token=@secret(len=21)$' "$t/atoms/basic/profiles/Demo/basic.ini/set-Twitch.kv" || leak=1
[ $leak = 0 ] && ok "AT2 no secret published" || red "AT2 no secret published"

# AT3
mode=$(stat -c %a "$t/vault.kv" 2>/dev/null || stat -f %Lp "$t/vault.kv")
[ "$mode" = 600 ] && ok "AT3 vault mode 600" || red "AT3 vault mode is $mode"

# AT4
out=$($omg join "$t/atoms" "$t/out2" --vault "$t/none.kv"); rc=$?
[ $rc = 1 ] && echo "$out" | grep -q 'Twitch|Token' && [ ! -f "$t/out2/basic/profiles/Demo/basic.ini" ] \
  && ok "AT4 join refuses without vault" || red "AT4 join refuses without vault (rc=$rc)"

# AT5
pins=$(grep -c '^<!-- omg:pin [0-9a-f]\{64\} -->$' "$t/STAGES.md")
sets=$(find "$t/atoms" -name '*.kv' | wc -l | tr -d ' ')
blocks=$(grep -c '^```kv set=' "$t/STAGES.md")
[ "$pins" = 1 ] && [ "$sets" = "$blocks" ] && ok "AT5 one pin, $blocks blocks" || red "AT5 pins=$pins sets=$sets blocks=$blocks"

# AT6
sed 's/^BaseCY=1080$/BaseCY=1440/' "$t/STAGES.md" > "$t/S2" && mv "$t/S2" "$t/STAGES.md"
$omg unroll "$t/STAGES.md" "$t/atoms" >/dev/null && grep -q '^BaseCY=1440$' "$t/atoms/basic/profiles/Demo/basic.ini/set-Video.kv" \
  && ok "AT6 roll-up edit unrolls" || red "AT6 roll-up edit unrolls"

# AT7
$omg rollup "$t/atoms" "$t/STAGES.md" >/dev/null
echo "Extra=1" >> "$t/atoms/basic/profiles/Demo/basic.ini/set-Video.kv"
sed 's/^Name=Demo$/Name=Other/' "$t/STAGES.md" > "$t/S2" && mv "$t/S2" "$t/STAGES.md"
out=$($omg unroll "$t/STAGES.md" "$t/atoms"); rc=$?
[ $rc = 1 ] && echo "$out" | grep -q 'set-General.kv' && grep -q '^Name=Demo$' "$t/atoms/basic/profiles/Demo/basic.ini/set-General.kv" \
  && ok "AT7 two-sided change stops" || red "AT7 two-sided change stops (rc=$rc)"

# AT8
before=$(find "$t/atoms" -type f | sort | xargs cat | cksum)
mkdir -p "$t/led"; printf 'e1\ta|k\ne1\tb|k\n' > "$t/led/events.tsv"
$omg suggest "$t/led" --min 1 >/dev/null
[ "$before" = "$(find "$t/atoms" -type f | sort | xargs cat | cksum)" ] && ok "AT8 suggest moves nothing" || red "AT8 suggest moves nothing"

# AT9
out=$($omg find); rc=$?
[ $rc = 0 ] && echo "$out" | grep -Eq '^(FOUND|absent) ' && ok "AT9 find" || red "AT9 find"

# AT10 (found 2026-11-01: rollup to a bare file name crashed)
( cd "$t" && $omg rollup atoms STAGES-bare.md >/dev/null ) && [ -s "$t/STAGES-bare.md" ] \
  && ok "AT10 rollup to a bare file name" || red "AT10 rollup to a bare file name"

# AT11 (found 2026-11-02: obs-websocket's ServerPassword was published as plain)
mkdir -p "$t/ws"; printf '[OBSWebSocket]\nServerEnabled=true\nServerPassword=FAKEwsPassword42\n' > "$t/ws/global.ini"
[ "${1:-}" = --prove-red ] && printf '[X]\nleak=FAKEwsPassword42\n' >> "$t/ws/global.ini"
$omg split "$t/ws" "$t/ws-atoms" --vault "$t/ws-vault.kv" >/dev/null
! grep -rqF FAKEwsPassword42 "$t/ws-atoms" && grep -q '^ServerPassword=@secret(len=16)$' "$t/ws-atoms/global.ini/set-OBSWebSocket.kv" \
  && ok "AT11 websocket password withheld" || red "AT11 websocket password withheld"

echo "e2e: $pass ok, $fail RED"
[ $fail = 0 ]

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin; claude-opus-5-5)
