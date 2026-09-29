#!/usr/bin/env python3
"""Fetch live Proxmox data and emit a Command Center snapshot JSON.

The snapshot feeds a dashboard page (see article.md) that renders node health,
all guests, service launchers, and storage from this single JSON blob.

Auth: set PROXMOX_URL and PROXMOX_TOKEN in the environment, e.g.
    export PROXMOX_URL="https://your-proxmox:8006/api2/json"
    export PROXMOX_TOKEN="PVEAPIToken=root@pam!your-token-id=your-secret"

The token needs broad read rights. In Proxmox: Datacenter -> Permissions ->
API Tokens, and UNCHECK "Privilege Separation" (with it on and no explicit
permissions, every request 403s). Treat the token as root-equivalent and keep
it server-side.

Service container states come from the last `pct exec` output pasted by hand
(LXCs have no guest-agent exec endpoint); each entry carries state_checked_at
so the dashboard is honest about staleness.
"""
import json
import os
import datetime
import urllib.request
import urllib.parse

BASE = os.environ.get("PROXMOX_URL", "https://your-proxmox:8006/api2/json")
TOKEN = os.environ["PROXMOX_TOKEN"]  # KeyError with a clear message if unset
NODE = os.environ.get("PROXMOX_NODE", "pve")


def api(path, params=None):
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Authorization": TOKEN,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())["data"]


def gb(b):
    return round(b / (1024 ** 3), 1)


def main():
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

    node = api(f"/nodes/{NODE}/status")
    qemus = api(f"/nodes/{NODE}/qemu")
    lxcs = api(f"/nodes/{NODE}/lxc")
    storages = api(f"/nodes/{NODE}/storage")

    # Human-readable role per guest; edit to match what's actually inside yours.
    roles = {
        # 100: "Debian 12, Docker host, zero containers",
        # 201: "Main services host",
    }

    guests = []
    for g in sorted(qemus + lxcs, key=lambda x: x["vmid"]):
        vmid = g["vmid"]
        guests.append(
            {
                "id": vmid,
                "kind": "qemu" if g.get("type") == "qemu" else "lxc",
                "name": g.get("name", f"vm-{vmid}"),
                "status": g.get("status", "unknown"),
                "cpu": g.get("cpus", g.get("maxcpu", 0)),
                "ram": f"{gb(g.get('maxmem', 0))} GB",
                # Guest IPs via the QEMU guest agent need an extra call per VM;
                # "dhcp" here just means "not resolved in this snapshot".
                "ip": "dhcp",
                "role": roles.get(vmid, ""),
            }
        )

    storage = [
        {
            "name": s.get("storage"),
            "used_pct": round(100 * s.get("used", 0) / s.get("total", 1)),
            "used": f"{gb(s.get('used', 0))} GB",
            "total": f"{gb(s.get('total', 0))} GB",
        }
        for s in storages
        if s.get("total")
    ]

    # Static service launchers: (name, url, host label, container, state, checked_at).
    # Update state_checked_at whenever you verify container states by hand.
    checked = now  # replace with the real timestamp of your last `pct exec`
    raw_services = [
        # ("Homepage", "http://192.168.0.20:3000", "services (201)", "homepage", "running", checked),
    ]
    services = [
        {
            "name": n,
            "url": u,
            "host": h,
            "container": c,
            "state": s,
            "state_checked_at": t,
        }
        for n, u, h, c, s, t in raw_services
    ]

    snapshot = {
        "taken_at": now,
        "node": {
            "name": NODE,
            "status": node.get("status", "unknown"),
            "version": (node.get("pveversion") or "").split("/")[0],
            "uptime": node.get("uptime", 0),
            "cpu_pct": round(100 * node.get("cpu", 0)),
            "mem_used_gb": gb(node.get("memory", {}).get("used", 0)),
            "mem_total_gb": gb(node.get("memory", {}).get("total", 0)),
        },
        "guests": guests,
        "services": services,
        "storage": storage,
    }
    print(json.dumps(snapshot, indent=2))


if __name__ == "__main__":
    main()
