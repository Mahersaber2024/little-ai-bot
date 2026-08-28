#!/usr/bin/env bash
#
# setup_spotify_ssl.sh (v3)
# ---------------------------------------------------------------
# Adds spotify.heysolo.online as an isolated nginx site and gets it
# a Let's Encrypt certificate, WITHOUT the chicken-and-egg bug from
# v2 (which wrote an SSL server block pointing at a certificate that
# didn't exist yet, so nginx -t failed before certbot could even run).
#
# How this version avoids it:
#   1. Write ONLY a plain HTTP vhost first (+ a webroot path for the
#      ACME challenge). No SSL block yet, so nginx -t can never fail
#      on a missing certificate.
#   2. Get the certificate with `certbot certonly --webroot`, which
#      only needs that HTTP vhost to be live - it never touches or
#      depends on nginx's SSL config.
#   3. Only THEN append the HTTPS server block, now pointing at a
#      certificate that actually exists.
#
# It also drops the `include options-ssl-nginx.conf` / `ssl_dhparam`
# lines (those files only get created by certbot's own --nginx
# installer flow, which we're deliberately not using) and inlines
# safe modern TLS settings instead. And it drops the
# `limit_req zone=one` line, since that zone is only defined if your
# existing nginx.conf happens to define one - safer not to assume.
#
# It still does NOT touch:
#   - /etc/nginx/nginx.conf
#   - any other site in sites-available/sites-enabled
#   - any other domain's certificate
#
# Run ON YOUR SERVER as root:
#   sudo bash setup_spotify_ssl.sh you@example.com
# ---------------------------------------------------------------
set -euo pipefail

DOMAIN="spotify.heysolo.online"
BACKEND_PORT="8888"
EMAIL="${1:-}"
SITE_FILE="/etc/nginx/sites-available/${DOMAIN}.conf"
WEBROOT="/var/www/certbot"
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"

echo "== 1/6: Ensuring nginx and certbot are installed =="
if ! command -v nginx >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y nginx
else
  echo "nginx already installed."
fi
if ! command -v certbot >/dev/null 2>&1; then
  apt-get install -y certbot
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

echo "== 3/6: Writing an HTTP-only vhost (no SSL block yet) =="
mkdir -p "$WEBROOT"
cat > "$SITE_FILE" <<EOF
# Separate vhost - only handles $DOMAIN. Does not affect other sites.
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root $WEBROOT;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}
EOF
ln -sf "$SITE_FILE" "/etc/nginx/sites-enabled/${DOMAIN}.conf"

nginx -t
if systemctl is-active --quiet nginx; then
  systemctl reload nginx
else
  echo "nginx is not currently running - starting it."
  if ! systemctl start nginx; then
    echo "!! nginx failed to start. This usually means something else on this"
    echo "   machine is already bound to port 80 or 443. Check with:"
    echo "     sudo ss -ltnp | grep -E ':80 |:443 '"
    echo "   Fix that conflict, then re-run this script."
    exit 1
  fi
fi

echo "== 4/6: Getting a certificate for $DOMAIN via webroot (independent of nginx's SSL config) =="
if [ -d "$CERT_DIR" ]; then
  echo "A certificate already exists at $CERT_DIR - skipping issuance."
else
  if [ -n "$EMAIL" ]; then
    certbot certonly --webroot -w "$WEBROOT" -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL"
  else
    certbot certonly --webroot -w "$WEBROOT" -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email
  fi
fi

echo "== 5/6: Adding the HTTPS server block now that the certificate exists =="
cat > "$SITE_FILE" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root $WEBROOT;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name $DOMAIN;

    ssl_certificate $CERT_DIR/fullchain.pem;
    ssl_certificate_key $CERT_DIR/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers off;

    server_tokens off;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

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

nginx -t
if systemctl reload nginx; then
  echo "nginx reloaded OK."
else
  echo "!! nginx failed to reload with the HTTPS block added. This usually means"
  echo "   another process already holds port 443 on this machine. Check with:"
  echo "     sudo ss -ltnp | grep ':443 '"
  echo "   Free that port (or move that other service behind nginx too), then"
  echo "   run: sudo systemctl reload nginx"
  exit 1
fi

echo "== 6/6: Making sure renewal keeps nginx in sync =="
mkdir -p /etc/letsencrypt/renewal-hooks/deploy
cat > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh <<'EOF'
#!/bin/sh
systemctl reload nginx
EOF
chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
systemctl enable --now certbot.timer
systemctl status certbot.timer --no-pager || true

echo
echo "Done. https://$DOMAIN/callback should now work over HTTPS."
echo "Next: set https://$DOMAIN/callback as the Redirect URI in the Spotify"
echo "dashboard and in the bot's /admin -> Spotify Settings."
