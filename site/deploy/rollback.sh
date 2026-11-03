#!/bin/sh
# rollback.sh -- put obsmage.com back as it was before an install.
#   sh deploy/rollback.sh             the backup named in $BACKUP/LAST
#   sh deploy/rollback.sh STAMP       a named one (ls /var/backups/obsmage.com)
# Restores the served files, the site file and the obsmage-* snippets from that backup (a file
# that did not exist then is removed), runs `nginx -t`, reloads. Never touches another site.
# If nginx -t fails, nothing is reloaded and it says so. Same overrides as install.sh.
# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
set -eu
NGINX_DIR=${NGINX_DIR:-/etc/nginx}
WWW_ROOT=${WWW_ROOT:-/var/www/obsmage.com}
BACKUP=${BACKUP:-/var/backups/obsmage.com}
SUDO=${SUDO-sudo}
NGINX=${NGINX:-nginx}
RELOAD=${RELOAD:-systemctl reload nginx}
SITE=$NGINX_DIR/sites-available/obsmage.com
SNIP=$NGINX_DIR/snippets
stamp=${1:-$($SUDO cat "$BACKUP/LAST" 2>/dev/null || true)}
case $stamp in ''|*/*|.*) echo "rollback: no backup named" >&2; exit 1 ;; esac
b=$BACKUP/$stamp
$SUDO test -d "$b" || { echo "rollback: $b does not exist" >&2; exit 1; }
if $SUDO test -f "$b/site"; then $SUDO cp -p "$b/site" "$SITE"; else $SUDO rm -f "$SITE"; fi
if $SUDO test -f "$b/was-enabled" && $SUDO test -f "$SITE"; then $SUDO ln -sf "$SITE" "$NGINX_DIR/sites-enabled/obsmage.com"; else $SUDO rm -f "$NGINX_DIR/sites-enabled/obsmage.com"; fi
for s in common topology-csp releases; do
  if $SUDO test -f "$b/snippets/obsmage-$s.conf"; then $SUDO cp -p "$b/snippets/obsmage-$s.conf" "$SNIP/"; else $SUDO rm -f "$SNIP/obsmage-$s.conf"; fi
done
if $SUDO test -d "$b/public"; then $SUDO rsync -a --delete "$b/public/" "$WWW_ROOT/public/"; fi
if $SUDO $NGINX -t 2>&1; then $SUDO $RELOAD; sleep "${RELOAD_WAIT:-2}"; echo "rolled back to $stamp; nginx reloaded"
else echo "rollback: nginx -t fails with the restored files; nothing reloaded" >&2; exit 1; fi
