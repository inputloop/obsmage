#!/bin/sh
# install.sh -- put obsmage.com on this host's nginx (gw33, as the gw33 account, which has sudo).
#   sh deploy/install.sh            from an unpacked build: public/, deploy/, generated/ side by side
# Backs up before it changes anything: the served files, the site file and the snippets go to
# $BACKUP/<stamp>/ (and $BACKUP/LAST names it), so deploy/rollback.sh can put them back.
# Uses the TLS block once obsmage.com's certificate exists, the port-80 interim block before; so a
# reinstall never takes https down. On any `nginx -t` failure the previous files are put back.
# After the reload it waits until nginx answers with this install's id (X-Obsmage-Conf), so a
# check made afterwards reads the new configuration, not the old.
# Touches only obsmage.com's own files: its site file and link, three snippets named obsmage-*,
# /var/www/obsmage.com. No other site is read or changed.
# Paths and commands can be overridden for tests: NGINX_DIR, LE_LIVE, WWW_ROOT, BACKUP, SUDO, NGINX, RELOAD, PROBE.
# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
set -eu
here=$(cd "$(dirname "$0")" && pwd); top=$(dirname "$here")
NGINX_DIR=${NGINX_DIR:-/etc/nginx}
LE_LIVE=${LE_LIVE:-/etc/letsencrypt/live/obsmage.com}
WWW_ROOT=${WWW_ROOT:-/var/www/obsmage.com}
BACKUP=${BACKUP:-/var/backups/obsmage.com}
SUDO=${SUDO-sudo}
NGINX=${NGINX:-nginx}
RELOAD=${RELOAD:-systemctl reload nginx}
WAIT=${RELOAD_WAIT:-30}
SITE=$NGINX_DIR/sites-available/obsmage.com
SNIP=$NGINX_DIR/snippets

for f in public/index.html generated/topology-csp.conf generated/releases.conf deploy/common-headers.conf; do
  [ -f "$top/$f" ] || { echo "install: $f is missing beside this script: nothing changed" >&2; exit 1; }
done
if $SUDO test -s "$LE_LIVE/fullchain.pem"; then conf=nginx-obsmage.com.conf; else conf=obsmage.com.interim.conf; fi
stamp=$(date -u +%Y%m%d-%H%M%S)
id="$stamp-$(cat "$top/public/index.html" "$here/$conf" "$top/generated/"*.conf | cksum | cut -d' ' -f1)"

# 1. back up what is there now
b=$BACKUP/$stamp
$SUDO mkdir -p "$b/snippets"
[ -f "$SITE" ] && $SUDO cp -p "$SITE" "$b/site" || :
for s in common topology-csp releases; do [ -f "$SNIP/obsmage-$s.conf" ] && $SUDO cp -p "$SNIP/obsmage-$s.conf" "$b/snippets/" || :; done
[ -L "$NGINX_DIR/sites-enabled/obsmage.com" ] && $SUDO touch "$b/was-enabled" || :
[ -d "$WWW_ROOT/public" ] && $SUDO rsync -a "$WWW_ROOT/public/" "$b/public/" || :
echo "$stamp" | $SUDO tee "$BACKUP/LAST" >/dev/null
echo "backed up to $b"

# 2. put the new files in place
undo() {
  if [ -f "$b/site" ]; then $SUDO cp -p "$b/site" "$SITE"; else $SUDO rm -f "$SITE" "$NGINX_DIR/sites-enabled/obsmage.com"; fi
  for s in common topology-csp releases; do
    if [ -f "$b/snippets/obsmage-$s.conf" ]; then $SUDO cp -p "$b/snippets/obsmage-$s.conf" "$SNIP/"; else $SUDO rm -f "$SNIP/obsmage-$s.conf"; fi
  done
  if [ -d "$b/public" ]; then $SUDO rsync -a --delete "$b/public/" "$WWW_ROOT/public/"; fi
}
$SUDO mkdir -p "$WWW_ROOT/public" "$WWW_ROOT/acme" "$SNIP" "$NGINX_DIR/sites-available" "$NGINX_DIR/sites-enabled"
$SUDO rsync -a --delete "$top/public/" "$WWW_ROOT/public/"
sed "s/@CONF_ID@/$id/" "$here/common-headers.conf" | $SUDO tee "$SNIP/obsmage-common.conf" >/dev/null
$SUDO install -m 644 "$top/generated/topology-csp.conf" "$SNIP/obsmage-topology-csp.conf"
$SUDO install -m 644 "$top/generated/releases.conf" "$SNIP/obsmage-releases.conf"
$SUDO install -m 644 "$here/$conf" "$SITE"
$SUDO ln -sf "$SITE" "$NGINX_DIR/sites-enabled/obsmage.com"

# 3. test, reload, and wait for the reload to land
if ! $SUDO $NGINX -t 2>&1; then
  undo; echo "install: nginx -t failed with $conf: the previous files are back, nginx not reloaded" >&2; exit 1
fi
$SUDO $RELOAD
if [ "$conf" = nginx-obsmage.com.conf ]; then probe=${PROBE:-"curl -s -D - -o /dev/null --resolve obsmage.com:443:127.0.0.1 https://obsmage.com/"}
else probe=${PROBE:-"curl -s -D - -o /dev/null -H Host:obsmage.com http://127.0.0.1/"}; fi
n=0
while :; do
  if $probe 2>/dev/null | tr -d '\r' | grep -qi "^x-obsmage-conf: $id\$"; then break; fi
  n=$((n + 1)); [ $n -lt "$WAIT" ] || { echo "install: nginx did not answer with this install's id after ${WAIT}s; the files are in place, check by hand" >&2; exit 2; }
  sleep 1
done
echo "installed $id with $conf; nginx answers with it after ${n}s"
