#!/usr/bin/env bash
#
# setup_spotify_ssl.sh  (v2 - coexists with an already-configured nginx)
# ---------------------------------------------------------------
# Adds spotify.heysolo.online as a SEPARATE, isolated nginx site,
# alongside your existing heysolo.online config. It does NOT touch:
#   - /etc/nginx/nginx.conf
#   - /etc/nginx/sites-available/heysolo.online (or whatever it's named)
#   - the existing heysolo.online SSL certificate
#
# nginx can serve unlimited domains on the same 80/443 ports - it
# picks the right server{} block using the Host header (HTTP) or SNI
# (HTTPS). So "these ports are already busy" is not actually a
# conflict, as long as each domain has its own server_name and its
# own certificate.
#
# Run ON YOUR SERVER as root:
#   sudo bash setup_spotify_ssl.sh you@example.com
# ---------------------------------------------------------------
set -euo pipefail

DOMAIN="spotify.heysolo.online"
BACKEND_PORT="8888"
EMAIL="${1:-}"
SITE_FILE="/etc/nginx/sites-available/${DOMAIN}.conf"

echo "== 0/6: Checking what's currently listening on 80 / 443 / $BACKEND_PORT =="
ss -ltnp 2>/dev/null | grep -E ":80 |:443 |:$BACKEND_PORT " || echo "(nothing matched - fine)"
echo
echo "If a PID other than nginx shows up for :80/:443, note it - most likely"
echo "it IS your existing nginx (expected, not a conflict)."
echo "If something OTHER than the bot shows up for :$BACKEND_PORT, that port is taken:"
echo "change BACKEND_PORT in this script AND host/port in webserver.py to match."
read -p "Press Enter to continue once you've reviewed this ..." _

echo "== 1/6: Ensuring nginx and certbot are installed (skips if already present) =="
if ! command -v nginx >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y nginx
else
  echo "nginx already installed - leaving your existing setup untouched."
fi
if ! command -v certbot >/dev/null 2>&1; then
  apt-get install -y certbot python3-certbot-nginx
else
  echo "certbot already installed."
fi

echo "== 2/6: Checking DNS for $DOMAIN =="
RESOLVED_IP=$(dig +short "$DOMAIN" | tail -n1 || true)
if [ -z "$RESOLVED_IP" ]; then
  echo "WARNING: $DOMAIN does not resolve yet. Add the DNS A record first," \
       "then re-run this script. Aborting."
  exit 1
fi
echo "$DOMAIN resolves to: $RESOLVED_IP"

echo "== 3/6: Writing an ISOLATED site file: $SITE_FILE =="
if [ -f "$SITE_FILE" ]; then
  echo "A file already exists at $SITE_FILE - not overwriting it."
  echo "Review it manually, then re-run without this check if needed."
else
cat > "$SITE_FILE" <<EOF
# Separate vhost - only handles $DOMAIN. Does not affect heysolo.online.
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name $DOMAIN;

    # certbot will fill these two lines in automatically in the next step
    # (creates a fresh, separate certificate just for this subdomain)
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    server_tokens off;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # reuses the "one" rate-limit zone already defined globally in nginx.conf
    limit_req zone=one burst=20 nodelay;

    location = /callback {
        proxy_pass http://127.0.0.1:$BACKEND_PORT/callback;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        return 404;
    }
}
EOF
fi

ln -sf "$SITE_FILE" "/etc/nginx/sites-enabled/${DOMAIN}.conf"

echo "== 4/6: Getting a certificate JUST for $DOMAIN (does not touch heysolo.online's cert) =="
# --nginx here only edits the server{} blocks matching -d $DOMAIN, i.e. only
# the file we just created. It cannot see or modify unrelated domains.
if [ -n "$EMAIL" ]; then
  certbot certonly --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL"
else
  certbot certonly --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email
fi

echo "== 5/6: Validating full nginx config (all sites, including your existing one) =="
nginx -t
systemctl reload nginx

echo "== 6/6: Confirming auto-renewal is active for ALL certs (existing + new) =="
systemctl enable --now certbot.timer
systemctl status certbot.timer --no-pager || true

echo
echo "Done. https://$DOMAIN/callback now works independently of heysolo.online."
echo "Next: set the same URL as the Redirect URI in the Spotify dashboard and"
echo "in the bot's /admin -> Spotify Settings (see README-fa.md)."
