# I Built a Command Center for My Entire Homelab

**Subtitle:** Eleven guests, one dashboard, zero SSH sessions to check on everything. Here's how I wired my Proxmox stack into a single live page.

---

Eleven guests. Two Docker hosts, a services LXC stuffed with containers, a couple of Rocky builds, templates, an Ansible box I haven't touched in weeks. My Proxmox node had become one of those setups where I *knew* everything was in there somewhere — I just couldn't tell you what was running without opening three tabs and an SSH session.

So tonight I built a Command Center: one private page that shows every guest, every service, node health, and storage at a glance — and refreshes itself every hour from the Proxmox API. Here's the full build, step by step, so you can do the same.

## Step 1: Get an API token that actually works

Everything starts with the Proxmox API. In the Proxmox UI: **Datacenter → Permissions → API Tokens**, create a token for `root@pam`.

Here's the part that cost me twenty minutes: **uncheck "Privilege Separation."** With it on and no explicit permissions granted, every request dies with a 403 — and a 403 looks exactly like a wrong key, so you'll chase your tail. Unchecked, the token inherits your rights. (Keep it server-side, obviously. This token is root-equivalent.)

The header format Proxmox wants:

```
Authorization: PVEAPIToken=root@pam!muse-agent=<secret>
```

One gotcha: the *full* format with the token ID is required. The bare secret alone fails validation. Test it with a throwaway call:

```
GET https://your-proxmox:8006/api2/json/version
```

200 with your VE version? You're in.

![The muse-agent token with Privilege Separation off — the 20-minute lesson](proxmox-api-tokens.png)

## Step 2: Take a live inventory and rename by what's inside

My guest names were archaeology: `docker`, `docker-fleetcopy`, `Copy-of-VM-rocky9-template`. Names from past experiments, not from reality. Before building any dashboard, I pulled the real inventory and renamed everything according to what was actually in each guest:

| Before | After | Why |
|---|---|---|
| `docker-fleet-vm` | `docker-empty` | Debian 12, Docker installed, zero containers |
| `docker-fleetcopy` | `firefox-box` | Runs one container: a browser |
| `Copy-of-VM-rocky9-template` | `rocky9-clone` | Full clone of the Rocky 9 template |
| `docker` (200) | `portainer-agent` | Portainer agent only |
| `docker` (201) | `services` | The whole stack lives here |

The rename that surprised me most was VM 100. I'd been calling it a "docker fleet" box. The guest agent reported Docker installed and *zero containers*. It was an empty garage I'd been afraid to open. Naming things by what's actually inside them is the cheapest infrastructure cleanup you'll ever do. (You can see the new names in the Proxmox server tree in the screenshot above — and in the dashboard's guest cards below.)

## Step 3: Learn the guest agent's one weird rule

To see inside the QEMU guests without SSH, Proxmox has a guest-agent `exec` endpoint. It has exactly one rule that matters, and breaking it gives you a cryptic HTTP 596:

**The command must be a JSON array, not a string.**

```json
POST /nodes/sly/qemu/102/agent/exec
{"command": ["docker", "ps"]}
```

Send `"docker ps"` as a single string and the agent treats the whole thing as a literal binary path. Send the array and it works. Poll `exec-status?pid=<pid>` until it exits, then read the output.

That's how I confirmed `firefox-box` runs exactly one container — `youtube-firefox` from the linuxserver image, up for four weeks — and grabbed its LAN IP from the guest agent's network interfaces: `192.168.0.27`. No SSH, no guessing.

Two honest limits I hit here, because they shaped the whole design:

1. **LXCs have no `exec` endpoint.** QEMU guests get the guest agent; containers don't. For the services LXC, I ran `pct exec` on the host and worked from the output. Old school, but it worked.
2. **My automation environment can't SSH to the host** — the egress proxy kills it. So container states inside the LXCs can't self-refresh. The dashboard marks every service state with *when it was last verified*. A dashboard that lies about freshness is worse than no dashboard.

## Step 4: Build the dashboard around a snapshot

The design decision: the dashboard never talks to Proxmox directly. Instead, a script collects everything into one JSON snapshot — node health, all guests, services, storage — and pushes it into the page through a single `ingest` action. The page just renders whatever snapshot it holds.

The script is ~150 lines of Python: hit `/nodes/sly/status`, `/qemu`, `/lxc`, `/storage`, assemble, print JSON. The services list is a static table with URLs, since those barely change:

```python
raw_services = [
    ("Homepage",          "http://192.168.0.20:3000", ...),
    ("Portainer CE",      "http://192.168.0.20:9000", ...),
    ("Nginx Proxy Manager","http://192.168.0.20:81",  ...),
    ("Vaultwarden",       "http://192.168.0.20:8081", ...),
    ("Firefly III",       "http://192.168.0.20:8082", ...),
    ("WordPress",         "http://192.168.0.20:8080", ...),
    ("Firefox (Kasm)",    "http://192.168.0.27:3000", ...),
]
```

Each entry carries a `state_checked_at` timestamp. The ones from the `pct exec` paste say when the paste happened. The Firefox one says when *I* checked it via the guest agent. Different sources, different timestamps, all visible. That's the whole honesty system.

The page itself: near-black background, gold accents, status LEDs, one card per guest, one launcher per service, storage bars, quick links to Proxmox and n8n. Nothing fancy — it's a tool, not a portfolio piece.

![Node health, all eleven guests with their new names](command-center-overview.png)

![Every service as a one-tap launcher, each stamped with when its state was last verified](command-center-services.png)

## Step 5: Make it refresh itself hourly

A dashboard you have to refresh by hand is a dashboard you'll stop trusting. A cron job runs the snapshot script every hour and pushes the result. Node CPU, memory, guest up/down states, storage percentages — all live within the hour.

But here's the deliberate boundary: the hourly job only refreshes what the API can see. The container states inside the LXCs stay frozen at their last verified timestamp until I paste fresh `pct exec` output. I'd rather show "checked 3 days ago" than pretend I know something I don't. If your monitoring can't distinguish *stale* from *live*, it's decoration.

## Step 6: Curate it like a homepage

The last step was editorial, not technical. The Portainer agent card? Removed — I don't launch a browser at an agent port, ever. The Firefox container? Added, because I actually open it. A command center should contain the things you reach for, not an exhaustive inventory. Exhaustive is what the guest list is for.

---

**What I'd do differently next time:** get the agent onto the tailnet (or any reachable SSH path) so LXC container states can refresh for real instead of riding on pasted output. That's the one gap in the system, and it's a network problem, not a code problem.

The total build was one evening: token, inventory, renames, script, page, cron. The part I'm happiest about isn't the page — it's the rule that every state carries its own timestamp. Trustworthy beats pretty.

---

*If your infrastructure is currently held together by SSH sessions and memory, that's exactly the kind of thing I untangle for clients — I do managed IT and Linux infrastructure work through Sylvect. Sometimes the fix is a dashboard; sometimes it's deleting the three VMs you were afraid to look inside.*

*The full snapshot script and dashboard pattern are described above — steal them freely. If you build your own, I'd genuinely love to see it.*
