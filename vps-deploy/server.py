#!/usr/bin/env python3
"""Command Center — self-hosted homelab dashboard (runs on n8n-vps).

Stdlib only. No dependencies.

Routes:
  GET  /healthz  -> 200 "ok" (no auth; for Caddy / Uptime Kuma)
  POST /ingest   -> Bearer INGEST_TOKEN; validates + stores snapshot JSON
  GET  /         -> HTTP Basic Auth (DASH_USER / DASH_PASS); renders dashboard

Environment:
  DASH_USER, DASH_PASS   dashboard login (required for /)
  INGEST_TOKEN           bearer token for /ingest (required)
  PORT                   listen port (default 8741)
  HOST                   bind address (default 127.0.0.1)
  DATA_DIR               where snapshot.json lives (default /data)
"""
import base64
import hashlib
import hmac
import html
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DATA_DIR = os.environ.get("DATA_DIR", "/data")
SNAP_FILE = os.path.join(DATA_DIR, "snapshot.json")
INGEST_TOKEN = os.environ.get("INGEST_TOKEN", "")
DASH_USER = os.environ.get("DASH_USER", "")
DASH_PASS = os.environ.get("DASH_PASS", "")
PORT = int(os.environ.get("PORT", "8741"))
HOST = os.environ.get("HOST", "127.0.0.1")
MAX_BODY = 5 * 1024 * 1024  # 5 MB

GOLD = "#C9A84C"
DARK_GOLD = "#7A5F25"
BG = "#0B0B0B"
CARD = "#141414"
TEXT = "#EDEDED"
MUTED = "#9A9A9A"

REQUIRED_KEYS = ("node", "guests", "services", "storage")


def esc(v):
    return html.escape(str(v if v is not None else ""), quote=True)


def human_uptime(seconds):
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return "—"
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, _ = divmod(s, 60)
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def status_dot(status):
    s = (status or "").lower()
    if s in ("running", "online"):
        return "#3ECF6F"
    if s in ("stopped", "offline"):
        return "#E5484D"
    return "#E8B93E"


def bar(pct, color=GOLD):
    pct = max(0, min(100, pct or 0))
    return (
        f'<div class="meter"><div class="fill" style="width:{pct:.0f}%;'
        f'background:{color}"></div></div>'
    )


def render_dashboard(snap):
    node = snap.get("node", {}) or {}
    guests = snap.get("guests", []) or []
    services = snap.get("services", []) or []
    storage = snap.get("storage", []) or []
    taken = esc(snap.get("taken_at", "unknown"))

    mem_used = node.get("mem_used_gb") or 0
    mem_total = node.get("mem_total_gb") or 1
    mem_pct = round(mem_used / mem_total * 100) if mem_total else 0

    guest_rows = []
    for g in guests:
        guest_rows.append(
            "<tr>"
            f'<td><span class="dot" style="background:{status_dot(g.get("status"))}"></span>'
            f"{esc(g.get('name'))}</td>"
            f"<td class='num'>{esc(g.get('id'))}</td>"
            f"<td>{esc(g.get('kind'))}</td>"
            f"<td>{esc(g.get('status'))}</td>"
            f"<td class='num'>{esc(g.get('cpu'))}</td>"
            f"<td>{esc(g.get('ram'))}</td>"
            f"<td class='mono'>{esc(g.get('ip'))}</td>"
            f"<td class='muted'>{esc(g.get('role'))}</td>"
            "</tr>"
        )

    svc_cards = []
    for s in services:
        state = (s.get("state") or "unknown").lower()
        color = status_dot("running" if state == "running" else state)
        checked = esc(s.get("state_checked_at", "—"))
        svc_cards.append(
            "<div class='card svc'>"
            f'<div class="svc-head"><span class="dot" style="background:{color}"></span>'
            f"<strong>{esc(s.get('name'))}</strong></div>"
            f"<div class='muted small'>{esc(s.get('host'))} · {esc(s.get('container'))}</div>"
            f"<div class='small'>state: {esc(state)} <span class='muted'>(checked {checked})</span></div>"
            f"<a class='btn' href='{esc(s.get('url'))}' target='_blank' rel='noopener'>Open →</a>"
            "</div>"
        )

    stor_cards = []
    for st in storage:
        pct = st.get("used_pct") or 0
        stor_cards.append(
            "<div class='card'>"
            f"<div class='row'><strong>{esc(st.get('name'))}</strong>"
            f"<span class='muted small'>{esc(st.get('used'))} / {esc(st.get('total'))}</span></div>"
            f"{bar(pct)}"
            f"<div class='small muted'>{pct:.0f}% used</div>"
            "</div>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="300">
<title>Command Center — {esc(node.get('name', 'homelab'))}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ background: {BG}; color: {TEXT}; font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
         margin: 0; padding: 24px; }}
  h1 {{ color: {GOLD}; font-size: 1.6rem; margin: 0; }}
  h2 {{ color: {GOLD}; font-size: 1.05rem; text-transform: uppercase; letter-spacing: .08em;
        border-bottom: 1px solid {DARK_GOLD}; padding-bottom: 6px; }}
  .wrap {{ max-width: 1200px; margin: 0 auto; }}
  .top {{ display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px; }}
  .muted {{ color: {MUTED}; }} .small {{ font-size: .82rem; }} .mono {{ font-family: ui-monospace, monospace; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }}
  .card {{ background: {CARD}; border: 1px solid #2a2a2a; border-radius: 10px; padding: 14px; }}
  .row {{ display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }}
  .meter {{ height: 8px; background: #262626; border-radius: 4px; margin: 8px 0 4px; overflow: hidden; }}
  .meter .fill {{ height: 100%; border-radius: 4px; }}
  .dot {{ display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .88rem; }}
  th {{ text-align: left; color: {MUTED}; font-weight: 600; font-size: .75rem; text-transform: uppercase;
       letter-spacing: .05em; padding: 8px 10px; border-bottom: 1px solid {DARK_GOLD}; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid #222; vertical-align: top; }}
  tr:hover td {{ background: #161616; }}
  .svc-head {{ margin-bottom: 4px; }}
  .btn {{ display: inline-block; margin-top: 8px; padding: 6px 14px; border: 1px solid {GOLD};
          color: {GOLD}; border-radius: 6px; text-decoration: none; font-size: .85rem; }}
  .btn:hover {{ background: {GOLD}; color: {BG}; }}
  section {{ margin: 28px 0; }}
  footer {{ margin-top: 36px; padding-top: 12px; border-top: 1px solid #2a2a2a; }}
  footer a {{ color: {GOLD}; margin-right: 16px; text-decoration: none; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <h1>⬢ Command Center</h1>
    <div class="muted small">node <strong>{esc(node.get('name'))}</strong> ·
      snapshot <span class="mono">{taken}</span></div>
  </div>

  <section>
    <h2>Node health</h2>
    <div class="grid">
      <div class="card">
        <div class="row"><strong>Status</strong>
          <span><span class="dot" style="background:{status_dot(node.get('status'))}"></span>
          {esc(node.get('status'))}</span></div>
        <div class="small muted">Proxmox VE {esc(node.get('version', ''))} ·
          uptime {esc(human_uptime(node.get('uptime')))}</div>
      </div>
      <div class="card">
        <div class="row"><strong>CPU</strong><span>{esc(node.get('cpu_pct'))}%</span></div>
        {bar(node.get('cpu_pct'))}
      </div>
      <div class="card">
        <div class="row"><strong>Memory</strong>
          <span>{esc(mem_used)} / {esc(mem_total)} GB</span></div>
        {bar(mem_pct)}
        <div class="small muted">{mem_pct}% used</div>
      </div>
    </div>
  </section>

  <section>
    <h2>Storage</h2>
    <div class="grid">{''.join(stor_cards)}</div>
  </section>

  <section>
    <h2>Guests ({len(guests)})</h2>
    <div class="card" style="padding:0;overflow-x:auto">
      <table>
        <tr><th>Name</th><th style="text-align:right">ID</th><th>Type</th><th>Status</th>
            <th style="text-align:right">CPU</th><th>RAM</th><th>IP</th><th>Role</th></tr>
        {''.join(guest_rows)}
      </table>
    </div>
  </section>

  <section>
    <h2>Services</h2>
    <div class="grid">{''.join(svc_cards)}</div>
  </section>

  <footer class="small muted">
    <a href="https://proxmox.sylvect.biz" target="_blank" rel="noopener">Proxmox</a>
    <a href="https://n8n.sylvect.biz" target="_blank" rel="noopener">n8n</a>
    <span style="float:right">served from n8n-vps · refreshes hourly</span>
  </footer>
</div>
</body>
</html>"""


def render_waiting():
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta http-equiv="refresh" content="60">
<title>Command Center</title>
<style>body{{background:{BG};color:{TEXT};font-family:system-ui,sans-serif;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0}}
h1{{color:{GOLD}}}</style></head>
<body><div><h1>⬢ Command Center</h1>
<p style="color:{MUTED}">Waiting for the first snapshot… the hourly push will fill this in.</p></div></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "CommandCenter/1.0"

    def log_message(self, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), " ".join(str(a) for a in args)))

    def _send(self, code, body, ctype="text/html; charset=utf-8", extra=None):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _auth_ok(self):
        """HTTP Basic Auth against DASH_USER / DASH_PASS (constant-time)."""
        if not DASH_USER or not DASH_PASS:
            return False
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(auth[6:]).decode("utf-8", "replace")
        except Exception:
            return False
        expected = f"{DASH_USER}:{DASH_PASS}"
        return hmac.compare_digest(
            hashlib.sha256(decoded.encode()).digest(),
            hashlib.sha256(expected.encode()).digest(),
        )

    def _require_auth(self):
        self._send(401, "Authentication required.",
                   extra={"WWW-Authenticate": 'Basic realm="Command Center"'})

    def do_GET(self):
        if self.path == "/healthz":
            self._send(200, "ok", ctype="text/plain")
            return
        if self.path not in ("/", "/index.html"):
            self._send(404, "Not found.", ctype="text/plain")
            return
        if not self._auth_ok():
            self._require_auth()
            return
        try:
            with open(SNAP_FILE, "r", encoding="utf-8") as fh:
                snap = json.load(fh)
            page = render_dashboard(snap)
        except FileNotFoundError:
            page = render_waiting()
        except Exception as e:
            self._send(500, f"Snapshot unreadable: {esc(e)}", ctype="text/plain")
            return
        self._send(200, page)

    def do_POST(self):
        if self.path != "/ingest":
            self._send(404, "Not found.", ctype="text/plain")
            return
        if not INGEST_TOKEN:
            self._send(503, "Ingest not configured.", ctype="text/plain")
            return
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or not hmac.compare_digest(
            hashlib.sha256(auth[7:].encode()).digest(),
            hashlib.sha256(INGEST_TOKEN.encode()).digest(),
        ):
            self._send(401, "Bad ingest token.", ctype="text/plain")
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            self._send(400, "Bad body size.", ctype="text/plain")
            return
        try:
            snap = json.loads(self.rfile.read(length))
        except Exception:
            self._send(400, "Invalid JSON.", ctype="text/plain")
            return
        if not isinstance(snap, dict) or not all(k in snap for k in REQUIRED_KEYS):
            self._send(400, "Snapshot missing required keys.", ctype="text/plain")
            return
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = SNAP_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(snap, fh)
        os.replace(tmp, SNAP_FILE)
        self._send(200, json.dumps({"ok": True}), ctype="application/json")


def main():
    if not INGEST_TOKEN:
        sys.stderr.write("warning: INGEST_TOKEN not set; /ingest disabled\n")
    if not DASH_USER or not DASH_PASS:
        sys.stderr.write("warning: DASH_USER/DASH_PASS not set; / is locked\n")
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    sys.stderr.write(f"command-center listening on {HOST}:{PORT}\n")
    srv.serve_forever()


if __name__ == "__main__":
    main()
