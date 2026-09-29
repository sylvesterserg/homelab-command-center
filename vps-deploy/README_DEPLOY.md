# Command Center — VPS deploy

Self-hosted copy of the Proxmox Command Center dashboard, running in Docker on
`n8n-vps` behind the existing Caddy reverse proxy at `https://dash.sylvect.biz`.

## How it works

- `server.py` (stdlib-only Python, no dependencies) serves the dashboard and
  accepts snapshots:
  - `GET /healthz` — no auth, for Caddy / Uptime Kuma
  - `POST /ingest` — bearer-token auth, stores the latest snapshot JSON
  - `GET /` — HTTP Basic Auth, renders the dashboard from the latest snapshot
- The hourly snapshot job (runs off-VPS) POSTs fresh Proxmox data to `/ingest`.
  Until the first snapshot lands, `/` shows a "waiting" page.
- The page auto-refreshes every 5 minutes. Nothing here is public: dashboard
  login is required, the container only listens on `127.0.0.1:8741`, and TLS
  comes from Caddy + Cloudflare.

## Deploy (on the VPS)

```bash
git clone https://github.com/sylvesterserg/homelab-command-center.git
cd homelab-command-center/vps-deploy
./deploy.sh
```

`deploy.sh` creates `.env` (dashboard user/pass + ingest token, mode 600),
builds, and starts the container. It then prints the remaining steps:

1. **Cloudflare DNS** — A record `dash.sylvect.biz` → VPS public IP, proxied.
2. **Caddy** — append `Caddyfile.snippet` to the VPS Caddyfile, then
   `docker compose exec caddy caddy reload` (from the n8n/Caddy compose dir).
3. **Ingest token** — paste the printed `INGEST_TOKEN` to Spaa via the secure
   card so the hourly push starts.
4. Open `https://dash.sylvect.biz` and log in.

## Files

| File | Purpose |
|---|---|
| `server.py` | dashboard + ingest server (stdlib only) |
| `Dockerfile` | `python:3.12-slim`, non-root |
| `docker-compose.yml` | one service, port bound to 127.0.0.1 only |
| `Caddyfile.snippet` | reverse-proxy block for the existing Caddy |
| `deploy.sh` | one-command deploy |
| `.env.example` | (create locally) variables the deploy writes |

`.env` is never committed.
