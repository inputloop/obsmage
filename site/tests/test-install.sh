#!/bin/sh
# test-install.sh -- site/deploy/install.sh and rollback.sh against a fake nginx tree: a fake
# `nginx -t`, a fake reload that "serves" the installed id, a fake probe. No real host is touched.
#   sh site/tests/test-install.sh [--prove-red]     (--prove-red plants faults in a copy; each must go RED)
# DEPLOY_DIR=dir checks the scripts in dir (the plants use this).
set -u
here=$(cd "$(dirname "$0")" && pwd); site=$(dirname "$here")
if [ "${1:-}" = --prove-red ]; then
  t=$(mktemp -d); bad=0
  plant() {  # name file sed-expr
    rm -rf "$t/d"; cp -R "$site/deploy" "$t/d"; sed "$3" "$t/d/$2" > "$t/x" && cp "$t/x" "$t/d/$2"
    if cmp -s "$site/deploy/$2" "$t/d/$2"; then echo "PLANT FAILED  $1"; bad=1; return; fi
    if DEPLOY_DIR=$t/d sh "$0" > "$t/log" 2>&1; then echo "STAYED GREEN  $1"; bad=1; else echo "went red      $1  ($(grep -m1 '^RED' "$t/log"))"; fi
  }
  plant "no backup of the served files"   install.sh  's/^\[ -d "\$WWW_ROOT\/public" \] && \$SUDO rsync -a "\$WWW_ROOT\/public\/" "\$b\/public\/" || :$/:/'
  plant "nginx -t failure not undone"     install.sh  's/^  undo; echo "install: nginx -t failed/  echo "install: nginx -t failed/'
  plant "reload not waited for"           install.sh  's/^  n=\$((n + 1)); \[ \$n -lt "\$WAIT" \] || {.*$/  break/'
  plant "TLS block chosen without a cert" install.sh  's/then conf=nginx-obsmage.com.conf; else conf=obsmage.com.interim.conf; fi/then conf=obsmage.com.interim.conf; else conf=nginx-obsmage.com.conf; fi/'
  plant "rollback leaves the new files"   rollback.sh 's/^if \$SUDO test -d "\$b\/public"; then .*$/:/'
  rm -rf "$t"
  [ $bad = 0 ] && echo "PROVE-RED OK" || { echo "PROVE-RED FAILED"; exit 1; }
  exit 0
fi
D=${DEPLOY_DIR:-$site/deploy}
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT INT TERM
pass=0; fail=0
ok()  { pass=$((pass + 1)); echo "ok    $1"; }
red() { fail=$((fail + 1)); echo "RED   $1"; }
B=$T/build; mkdir -p "$B/public" "$B/generated"; cp -R "$D" "$B/deploy"
echo "one" > "$B/public/index.html"; echo "# t" > "$B/generated/topology-csp.conf"; echo "# closed" > "$B/generated/releases.conf"
mkdir -p "$T/bin" "$T/nginx/sites-available" "$T/nginx/sites-enabled" "$T/nginx/snippets" "$T/le"
cat > "$T/bin/nginx" <<E
#!/bin/sh
[ -f "$T/nginx-fail" ] && { echo "nginx: [emerg] planted"; exit 1; }
echo "nginx: configuration file test is successful"
E
cat > "$T/bin/reload" <<E
#!/bin/sh
echo reload >> "$T/reloads"
[ -f "$T/reload-lost" ] || sed -n 's/^add_header X-Obsmage-Conf "\\(.*\\)" always;\$/\\1/p' "$T/nginx/snippets/obsmage-common.conf" > "$T/served" 2>/dev/null
exit 0
E
cat > "$T/bin/probe" <<E
#!/bin/sh
printf 'HTTP/1.1 200 OK\r\nX-Obsmage-Conf: %s\r\n\r\n' "\$(cat "$T/served" 2>/dev/null)"
E
# rsync -a [--delete] SRC/ DST/, the only way the scripts call it (the real one where it is installed)
if command -v rsync >/dev/null 2>&1; then ln -s "$(command -v rsync)" "$T/bin/rsync"; else cat > "$T/bin/rsync" <<'R'
#!/bin/sh
del=0; while [ $# -gt 2 ]; do [ "$1" = --delete ] && del=1; shift; done
mkdir -p "$2"; [ $del = 1 ] && find "$2" -mindepth 1 -delete
cp -a "$1". "$2"
R
fi
for f in "$T/bin/"*; do [ -L "$f" ] || chmod +x "$f"; done   # never chmod through the link to the real rsync
export PATH="$T/bin:$PATH"
# another site on the same host, which must not change
echo "server { server_name corwin.cloud; }" > "$T/nginx/sites-available/corwin.cloud"
ln -s "$T/nginx/sites-available/corwin.cloud" "$T/nginx/sites-enabled/corwin.cloud"
echo "add_header X-Other 1;" > "$T/nginx/snippets/corwin-cloud-topology-csp.conf"
others() { find "$T/nginx" -name 'obsmage*' -prune -o -type f -print | sort | xargs cksum; }
before=$(others)
inst() { NGINX_DIR=$T/nginx LE_LIVE=$T/le WWW_ROOT=$T/www BACKUP=$T/bak SUDO= NGINX=$T/bin/nginx RELOAD=$T/bin/reload PROBE=$T/bin/probe RELOAD_WAIT=3 sh "$B/deploy/install.sh" > "$T/out" 2>&1; }
roll() { NGINX_DIR=$T/nginx WWW_ROOT=$T/www BACKUP=$T/bak SUDO= NGINX=$T/bin/nginx RELOAD=$T/bin/reload RELOAD_WAIT=0 sh "$B/deploy/rollback.sh" "$@" > "$T/out" 2>&1; }

# I1 a first install: the interim block (no certificate yet), every file in place, the id filled in, the reload waited for
inst; rc=$?
[ $rc = 0 ] && cmp -s "$B/deploy/obsmage.com.interim.conf" "$T/nginx/sites-available/obsmage.com" && [ -L "$T/nginx/sites-enabled/obsmage.com" ] \
  && [ -f "$T/nginx/snippets/obsmage-topology-csp.conf" ] && [ -f "$T/nginx/snippets/obsmage-releases.conf" ] \
  && ! grep -q '@CONF_ID@' "$T/nginx/snippets/obsmage-common.conf" && grep -q '^one$' "$T/www/public/index.html" && grep -q 'nginx answers with it' "$T/out" \
  && ok "I1 first install: interim block, files, id, reload waited for" || red "I1 first install (rc=$rc): $(tail -n 1 "$T/out")"
first=$(cat "$T/bak/LAST" 2>/dev/null)
[ -n "$first" ] && [ -d "$T/bak/$first" ] && ok "I2 a backup is made and named in LAST" || red "I2 a backup is made and named in LAST"

# I3 with the certificate, the TLS block; the previous served files are in the backup
sleep 1; echo cert > "$T/le/fullchain.pem"; echo "two" > "$B/public/index.html"
inst; rc=$?; second=$(cat "$T/bak/LAST")
[ $rc = 0 ] && cmp -s "$B/deploy/nginx-obsmage.com.conf" "$T/nginx/sites-available/obsmage.com" && grep -q '^one$' "$T/bak/$second/public/index.html" \
  && cmp -s "$B/deploy/obsmage.com.interim.conf" "$T/bak/$second/site" && ok "I3 TLS block with a certificate; the old files backed up" || red "I3 TLS block with a certificate (rc=$rc)"

# I4 nginx -t fails: the previous files come back, no reload
sleep 1; echo "three" > "$B/public/index.html"; touch "$T/nginx-fail"; n0=$(wc -l < "$T/reloads")
inst; rc=$?; rm -f "$T/nginx-fail"
[ $rc = 1 ] && grep -q '^two$' "$T/www/public/index.html" && cmp -s "$B/deploy/nginx-obsmage.com.conf" "$T/nginx/sites-available/obsmage.com" \
  && [ "$(wc -l < "$T/reloads")" = "$n0" ] && ok "I4 nginx -t failure: previous files back, not reloaded" || red "I4 nginx -t failure (rc=$rc)"

# I5 a reload that never lands is reported, not assumed
sleep 1; touch "$T/reload-lost"; inst; rc=$?; rm -f "$T/reload-lost"
[ $rc = 2 ] && grep -q 'did not answer' "$T/out" && ok "I5 a reload that never lands is reported (exit 2)" || red "I5 a reload that never lands (rc=$rc)"

# I6 rollback to the first install's backup (the state before it: nothing) and to the second's (the first install)
roll "$second"; rc=$?
[ $rc = 0 ] && grep -q '^one$' "$T/www/public/index.html" && cmp -s "$B/deploy/obsmage.com.interim.conf" "$T/nginx/sites-available/obsmage.com" \
  && ok "I6 rollback puts the earlier files and block back" || red "I6 rollback (rc=$rc): $(tail -n 1 "$T/out")"
roll "$first"; rc=$?
[ $rc = 0 ] && [ ! -e "$T/nginx/sites-available/obsmage.com" ] && [ ! -e "$T/nginx/sites-enabled/obsmage.com" ] && [ ! -e "$T/nginx/snippets/obsmage-common.conf" ] \
  && ok "I7 rollback past the first install removes the site again" || red "I7 rollback past the first install (rc=$rc)"

# I8 no other site's files changed, at any step; a broken build changes nothing
[ "$before" = "$(others)" ] && ok "I8 no other site's files changed" || red "I8 another site's files changed"
rm "$B/generated/releases.conf"; inst; rc=$?
[ $rc = 1 ] && grep -q 'missing' "$T/out" && [ ! -e "$T/nginx/sites-available/obsmage.com" ] && ok "I9 a build with a part missing changes nothing" || red "I9 a part missing (rc=$rc)"

echo "test-install: $pass ok, $fail RED"
[ $fail = 0 ]

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin, claude-opus-5-5)
