#!/bin/sh
# e2e-dist.sh -- end-to-end checks of packaging/dist/omg-dist in POSIX sh, against a fake origin it
# builds itself; judged with cmp, sha256sum -c, grep and awk. No code or fixtures shared with
# tests/test_dist.py (the second language), which --prove-red also runs.
#   sh tests/e2e-dist.sh               run the checks
#   sh tests/e2e-dist.sh --prove-red   plant a fault in a copy of omg-dist; each must turn a check red
# DIST_SCRIPT=path checks another copy (the plants use this).
set -u
here=$(cd "$(dirname "$0")" && pwd); top=$(dirname "$here")
SD=$top/packaging/dist

if [ "${1:-}" = --prove-red ]; then
  t=$(mktemp -d); bad=0
  plant() {  # name sed-expr which(sh|py)
    rm -rf "$t/d"; mkdir "$t/d"; cp "$SD"/omg-dist "$SD"/secret-scan.py "$SD"/chan_check.py "$t/d/"
    sed "$2" "$t/d/omg-dist" > "$t/x" && cp "$t/x" "$t/d/omg-dist"
    if cmp -s "$SD/omg-dist" "$t/d/omg-dist"; then echo "PLANT FAILED  $1"; bad=1; return; fi
    if [ "$3" = sh ]; then DIST_SCRIPT=$t/d/omg-dist OMG_TOOLS=$top/tools sh "$0" >"$t/log" 2>&1
    else DIST_SCRIPT=$t/d/omg-dist OMG_TOOLS=$top/tools python3 -m unittest "$here/test_dist.py" >"$t/log" 2>&1; fi
    if [ $? = 0 ]; then echo "STAYED GREEN  $1"; bad=1; else echo "went red      $1  ($(grep -m1 -E '^(RED|FAIL)' "$t/log" | cut -c1-70))"; fi
  }
  plant "secret scan skipped (sh)"            's#^"\$PY" "\$here/secret-scan.py" "\$TMP/x"#: "$here/secret-scan.py" "$TMP/x"#' sh
  plant "secret scan skipped (py)"            's#^"\$PY" "\$here/secret-scan.py" "\$TMP/x"#: "$here/secret-scan.py" "$TMP/x"#' py
  plant "the name takes the clock (sh)"       's/^name=\$CHANNEL-\$version-\$stamp-\$rev12$/name=$CHANNEL-$version-$(date +%s%N)-$rev12/' sh
  plant "gzip keeps a timestamp (py)"         's/gzip -n -9 < "\$TMP\/src.tar"/{ sleep 1; touch "$TMP\/src.tar"; gzip -9 -c "$TMP\/src.tar"; } < \/dev\/null/' py
  plant "feed names the wrong sha256 (sh)"    's#^sha=\$(sumc "\$PUB/\$name.tar.gz"#sha=$(sumc "$LOG"#' sh
  plant "feed written before its bundle (py)" 's/^for f in "\$name.tar.gz" \${debname:+"\$debname"}; do$/for f in ${debname:+"$debname"}; do/' py
  plant "retention keeps nothing (py)"        's/\[ \$n -gt "\$KEEP" \] || continue/[ $n -gt 0 ] || continue/' py
  plant "same commit staged again (sh)"       's/ && \[ \$FORCE = 0 \]; then say "nothing new/ \&\& false; then say "nothing new/' sh
  plant "folders lose their search bit (sh)"  's#^find "\$PUB" -type f -exec chmod 644 {} + 2>/dev/null; find "\$PUB" -type d -exec chmod 755 {} +#chmod 644 "$PUB"/*; : #' sh
  plant "lock ignored (py)"                   's/^if ! mkdir "\$LOCK" 2>\/dev\/null; then/mkdir -p "$LOCK"; if false; then/' py
  rm -rf "$t"
  [ $bad = 0 ] && echo "PROVE-RED OK" || { echo "PROVE-RED FAILED"; exit 1; }
  exit 0
fi

DIST=${DIST_SCRIPT:-$SD/omg-dist}
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT INT TERM
pass=0; fail=0
ok()  { pass=$((pass + 1)); echo "ok    $1"; }
red() { fail=$((fail + 1)); echo "RED   $1"; }
g() { GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_AUTHOR_NAME=E GIT_AUTHOR_EMAIL=e@example.invalid GIT_COMMITTER_NAME=E GIT_COMMITTER_EMAIL=e@example.invalid git -C "$O" "$@"; }
commit() { GIT_AUTHOR_DATE=$2 GIT_COMMITTER_DATE=$2 g add -A && GIT_AUTHOR_DATE=$2 GIT_COMMITTER_DATE=$2 g commit -q -m "$1"; }
run() { DIST_SRC=$O DIST_OUT=$1 DIST_DEB=no DIST_BASE_URL=${3:-} DIST_KEEP=${2:-20} sh "$DIST" >"$T/run.out" 2>&1; }

O=$T/origin; mkdir -p "$O/debian" "$O/atoms/s/global.ini"
g init -q -b main
printf 'obsmage (1.2.3) unstable; urgency=low\n\n  * e2e\n\n -- E <e@example.invalid>  Mon, 02 Nov 2026 09:00:00 +0000\n' > "$O/debian/changelog"
printf 'ServerPort=4455\nServerPassword=@secret(len=12)\n' > "$O/atoms/s/global.ini/set-OBSWebSocket.kv"
echo "first" > "$O/NOTES"
commit one 2026-11-02T09:00:00Z

# E1 a run stages a tarball named from the commit, and a feed
run "$T/a"; rc=$?
tb=$(ls "$T/a/public" | grep '\.tar\.gz$')
[ $rc = 0 ] && echo "$tb" | grep -Eq '^obsmage-1\.2\.3-20261102-090000-[0-9a-f]{12}\.tar\.gz$' && ok "E1 tarball named from the commit ($tb)" || red "E1 tarball named from the commit (rc=$rc, $tb)"

# E2 the feed is the line form, and its sha256 and size are the tarball's
f=$T/a/public/channel.json
lf=$(awk 'NR==1&&$0!="{"{b=1} NR>1{l[NR]=$0} END{if(l[NR]!="}")b=1; for(i=2;i<NR;i++){if(l[i]!~/^  "[a-z][a-z0-9_]*": "[^"\\]*",?$/)b=1; c=substr(l[i],length(l[i]),1)==","; if(c!=(i<NR-1))b=1} print b?"bad":"good"}' "$f")
want=$(sha256sum "$T/a/public/$tb" | cut -d' ' -f1); size=$(wc -c < "$T/a/public/$tb" | tr -d ' ')
[ "$lf" = good ] && grep -q "^  \"sha256\": \"$want\",$" "$f" && grep -q "^  \"size\": \"$size\",$" "$f" && grep -q '^  "format": "channel/1",$' "$f" \
  && ok "E2 feed in line form, sha256 and size match" || red "E2 feed in line form, sha256 and size match ($lf)"

# E3 SHA256SUMS checks out
( cd "$T/a/public" && sha256sum -c --quiet SHA256SUMS ) >/dev/null 2>&1 && grep -q "$tb" "$T/a/public/SHA256SUMS" && ok "E3 SHA256SUMS checks out" || red "E3 SHA256SUMS checks out"

# E4 a second clean run elsewhere gives the same bytes
run "$T/b"
cmp -s "$T/a/public/$tb" "$T/b/public/$tb" && cmp -s "$T/a/public/channel.json" "$T/b/public/channel.json" && ok "E4 reproducible: same tarball, same feed" || red "E4 reproducible: same tarball, same feed"

# E5 the same commit again changes nothing
ls -l --time-style=+%s "$T/a/public" > "$T/before"; sleep 1; run "$T/a"; rc=$?
ls -l --time-style=+%s "$T/a/public" > "$T/after"
[ $rc = 0 ] && cmp -s "$T/before" "$T/after" && [ "$(grep -c building "$T/a/work/dist.log")" = 1 ] \
  && ok "E5 nothing new for the same commit (exit 0, nothing built)" || red "E5 nothing new for the same commit (rc=$rc)"

# E6 a plain credential in an atom is refused, nothing staged, the value never printed
printf 'ServerPort=4455\nServerPassword=hunter2hunter2\n' > "$O/atoms/s/global.ini/set-OBSWebSocket.kv"; commit leak 2026-11-02T10:00:00Z
run "$T/c"; rc=$?
[ $rc = 1 ] && [ -z "$(ls "$T/c/public")" ] && grep -q 'secret-scan refused' "$T/run.out" && ! grep -q hunter2 "$T/run.out" \
  && ok "E6 a credential refuses the release" || red "E6 a credential refuses the release (rc=$rc)"
g revert -q --no-edit HEAD >/dev/null 2>&1 || GIT_COMMITTER_DATE=2026-11-02T10:30:00Z g revert --no-edit HEAD >/dev/null

# E7 a new commit adds a release and keeps the old; the feed names the new one
echo "second" > "$O/NOTES"; commit two 2026-11-02T11:00:00Z
run "$T/a" 20 https://obsmage.example.invalid/dist; n=$(ls "$T/a/public" | grep -c '\.tar\.gz$')
[ "$n" = 2 ] && grep -q '"stamp": "20261102-110000"' "$T/a/public/channel.json" && grep -q '"artifact": "https://obsmage.example.invalid/dist/obsmage-1.2.3-20261102-110000-' "$T/a/public/channel.json" \
  && ok "E7 new release staged beside the old, feed names it" || red "E7 new release staged beside the old (n=$n)"

# E8 retention: with KEEP below 3, three are kept
for i in 3 4 5; do echo "v$i" > "$O/NOTES"; commit "v$i" "2026-11-02T1$i:00:00Z"; run "$T/a" 1; done
n=$(ls "$T/a/public" | grep -c '\.tar\.gz$'); j=$(ls "$T/a/public" | grep -c '^obsmage-.*\.json$')
[ "$n" = 3 ] && [ "$j" = 3 ] && ok "E8 retention keeps three" || red "E8 retention keeps three (tarballs $n, records $j)"

# E9 a live lock is respected
mkdir -p "$T/l/work/lock"; sleep 30 & sp=$!; echo $sp > "$T/l/work/lock/pid"
run "$T/l"; rc=$?
kill $sp 2>/dev/null; wait $sp 2>/dev/null
[ $rc = 0 ] && [ ! -f "$T/l/public/channel.json" ] && grep -q 'skipped' "$T/l/work/dist.log" && ok "E9 a run in progress is not overlapped" || red "E9 a run in progress is not overlapped"

# E10 a staged sub-folder (windows/) keeps its search bit when a run re-permissions the tree
mkdir -p "$T/a/public/windows"; echo x > "$T/a/public/windows/README.txt"; chmod 755 "$T/a/public/windows"
echo "v10" > "$O/NOTES"; commit v10 2026-11-02T20:00:00Z; run "$T/a"
m=$(stat -c %a "$T/a/public/windows" 2>/dev/null); f=$(stat -c %a "$T/a/public/windows/README.txt" 2>/dev/null)
[ "$m" = 755 ] && [ "$f" = 644 ] && ok "E10 a staged folder stays 755, its files 644" || red "E10 a staged folder stays 755, its files 644 (folder $m, file $f)"

echo "e2e-dist: $pass ok, $fail RED"
[ $fail = 0 ]

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin, claude-opus-5-5)
