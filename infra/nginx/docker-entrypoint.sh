#!/bin/sh
# ==========================================================================
# Custom nginx entrypoint: self-signed TLS fallback for local prod runs.
#
#   * Real server: certbot has already issued certs at $CERT_DIR, the
#     `if` below is skipped and real certs are served as usual.
#   * Local machine: no certbot -> generate a self-signed cert once on
#     first boot (persisted via the ./certbot/conf volume), so nginx can
#     start instead of crash-looping on the missing fullchain.pem.
#
# Browsers will show a warning for the self-signed cert — expected locally.
# ==========================================================================
set -e

CERT_DIR="/etc/letsencrypt/live/scalpy.space"
CERT_FILE="$CERT_DIR/fullchain.pem"
KEY_FILE="$CERT_DIR/privkey.pem"

if [ ! -f "$CERT_FILE" ]; then
    echo "⚠️  No TLS certificate found at $CERT_FILE. Generating self-signed cert for local development..."
    # nginx:alpine does not ship openssl — install it only on this path.
    if ! command -v openssl >/dev/null 2>&1; then
        apk add --no-cache openssl >/dev/null
    fi
    mkdir -p "$CERT_DIR"
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$KEY_FILE" \
        -out "$CERT_FILE" \
        -subj "/CN=localhost/O=TradingSimulator-Dev"
    echo "✅ Self-signed certificate generated."
fi

# Chain into the stock nginx entrypoint (envsubst templates, tuning, etc.)
exec /docker-entrypoint.sh nginx -g 'daemon off;'
