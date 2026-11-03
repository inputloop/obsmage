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
curl -s -o /dev/null -w 'https://obsmage.com/ %{http_code}\n' --resolve obsmage.com:443:127.0.0.1 https://obsmage.com/
curl -s -o /dev/null -w 'http redirects: %{http_code}\n' -H 'Host: obsmage.com' http://127.0.0.1/
