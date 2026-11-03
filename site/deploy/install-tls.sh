#!/bin/sh
# install-tls.sh -- on gw33, after install.sh and once obsmage.com and www.obsmage.com point here:
# get the certificate for both names (certbot, webroot, so nginx keeps serving; certbot's own
# timer renews it), then run install.sh again, which picks the TLS block now the certificate exists.
# Safe to run again: certbot keeps a valid certificate.
# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
sudo mkdir -p /var/www/obsmage.com/acme
sudo certbot certonly --webroot -w /var/www/obsmage.com/acme -d obsmage.com -d www.obsmage.com \
  --non-interactive --agree-tos --keep-until-expiring --cert-name obsmage.com
sudo test -s /etc/letsencrypt/live/obsmage.com/fullchain.pem || { echo "no certificate; nothing changed" >&2; exit 1; }
sh "$here/install.sh"
# Said, not judged: a request in the second after a reload can find the old workers closing
# (seen 2026-11-03: one 000, then 200s), so each is tried up to five times and never ends the script.
for i in 1 2 3 4 5; do c=$(curl -s -o /dev/null -w '%{http_code}' --resolve obsmage.com:443:127.0.0.1 https://obsmage.com/ || :); [ "$c" = 200 ] && break; sleep 1; done
echo "https://obsmage.com/ $c"
for i in 1 2 3 4 5; do c=$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: obsmage.com' http://127.0.0.1/ || :); [ "$c" = 301 ] && break; sleep 1; done
echo "http redirects: $c"
