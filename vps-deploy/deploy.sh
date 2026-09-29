#!/usr/bin/env bash
# Deploy the self-hosted Command Center on n8n-vps.
# Run from this directory on the VPS:  ./deploy.sh
set -euo pipefail
cd "$(dirname "$0")"

command -v docker >/dev/null || { echo "ERROR: docker not found on this host."; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "ERROR: 'docker compose' plugin not found."; exit 1; }

if [ ! -f .env ]; then
  read -rp "Dashboard username [sly]: " DASH_USER
  DASH_USER="${DASH_USER:-sly}"
  DASH_PASS="$(python3 -c 'import secrets,string; a=string.ascii_letters+string.digits; print("".join(secrets.choice(a) for _ in range(20)))')"
  INGEST_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  {
    echo "DASH_USER=${DASH_USER}"
    echo "DASH_PASS=${DASH_PASS}"
    echo "INGEST_TOKEN=${INGEST_TOKEN}"
    echo "PORT=8741"
  } > .env
  chmod 600 .env
  echo "Created .env (mode 600). Dashboard password generated:"
  echo "  user: ${DASH_USER}"
  echo "  pass: ${DASH_PASS}"
  echo "Save that password somewhere safe — it is only printed here."
else
  echo ".env already exists — keeping existing credentials."
fi

mkdir -p data
docker compose up -d --build
sleep 4

if curl -sf http://127.0.0.1:8741/healthz >/dev/null; then
  echo "OK: container healthy at http://127.0.0.1:8741/healthz"
else
  echo "WARNING: health check failed — run 'docker compose logs' to inspect."
fi

INGEST_TOKEN="$(grep -E '^INGEST_TOKEN=' .env | cut -d= -f2-)"
echo
echo "================ NEXT STEPS ================"
echo "1. Cloudflare DNS: add A record  dash.sylvect.biz  ->  <this VPS public IP>, proxied (orange cloud)."
echo "2. Append Caddyfile.snippet to the VPS Caddyfile, then reload Caddy:"
echo "     docker compose exec caddy caddy reload"
echo "   (run from the directory holding the n8n/Caddy compose file; adjust the service name if needed)"
echo "3. Paste this INGEST_TOKEN to Spaa (via the secure card) so the hourly snapshot push starts:"
echo "     ${INGEST_TOKEN}"
echo "4. Open https://dash.sylvect.biz and log in with the dashboard user/pass above."
echo "==========================================="
