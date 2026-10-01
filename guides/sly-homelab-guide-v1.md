# Build Your First Production-Style Homelab

**By Sylvester (SLY) — Linux · Infrastructure · Homelab · Automation · Practical AI**

*Guide V1 · October 2026 · Read time ~12 min · Weekend build*

**Build. Automate. Own Your Infrastructure.**

This is the guide I wish I had on day one. It mirrors my live lab — Proxmox VE 9.2.5 on a single node called "sly" with 11 guests — distilled into a build order you can finish in a weekend and run like production.

**Production-style means:** documented IPs, HTTPS everywhere internally, a separate backup target, monitoring that actually alerts, and a restore you have actually tested. If it isn't backed up and monitored, it isn't "done."

## Who this is for

- **IT pros and helpdesk → sysadmins** who want a lab that teaches production habits, not just "it boots."

- **Homelab beginners** with one mini PC or old desktop and a managed-switch budget.

- **Small-business owners** evaluating self-hosted tools before paying per-seat SaaS for everything.

---

## 1. Reference architecture — one node, done right

Start with **one Proxmox node**. One node done cleanly beats three nodes done messy, every time. You can add a second node later for clustering / HA — the layout below does not paint you into a corner.

- **Edge:** Your ISP router (or OPNsense later) → a NETGEAR GS108Ev3-class managed switch. VLAN-capable from day one, even if you start flat.

- **Compute:** Proxmox VE host ("sly" in my lab). Mini PC with an SSD for VMs/LXCs. Runs templates, the Docker host, DNS, proxy, and monitoring.

- **Storage + power:** A QNAP TS-216G-class 2-bay NAS as backup target and shared storage, plus an APC BR1500MS2-class UPS so blips are non-events and shutdowns are clean.

**Traffic flow:** Devices → switch → Proxmox services (AdGuard for DNS, Nginx Proxy Manager for HTTPS) → Tailscale for remote access. No port-forwards to the internet for admin panels. Ever.

**My live proof:** This is the same layout behind my Homelab Command Center build log — 11 guests on one node: a services LXC running Docker, a Portainer agent, networking/DNS, Vaultwarden, Firefly III, WordPress + MariaDB, templates, and more.

---

## 2. Hardware baseline — spend where it matters

You don't need enterprise gear. You need **quiet, low-power, reliable** — because this will run 24/7 in your home or office.

| Piece | Minimum viable | What I run |
| --- | --- | --- |
| Compute | Mini PC / SFF, 4-core, 16 GB RAM | Dell OptiPlex 7070 Micro, i5-9500T |
| Switch | 8-port managed, VLAN-capable | NETGEAR GS108Ev3 |
| Backup target | External drive or NAS | QNAP TS-216G 2-bay NAS |
| Power | UPS with USB signalling | APC BR1500MS2 |
| Rack (optional) | Small shelf to start | RackPath 9U |

Notes: 32 GB RAM is recommended on the compute node. The NAS sits separate from the host SSD in the 3-2-1 layout (Section 6). The UPS is non-negotiable — it rides out blips and gives guests a clean shutdown on an extended outage.

**Budget order if you are buying piecemeal:** UPS first (it protects everything), then compute + RAM, then the managed switch, then the NAS. A pretty rack with no UPS is a liability with good cable management.

---

## 3. Proxmox layout — templates, guests, storage

### Install and first 30 minutes

- Install Proxmox VE from ISO, set a static IP on your management network, and write it down. Tape on the box counts as documentation if you also put it in a note.
- Switch apt to the no-subscription repo if this is a lab, run full updates, reboot.
- Storage: local SSD = local-lvm (LVM-thin) or ZFS for VM disks. **Backups never live only on the same disk as the VMs.**
- Add your NAS as NFS/SMB storage for backups.
- Set up email / webhook notifications under Datacenter → Notifications so host alerts leave the box.

### The golden template — do this before any "real" VM

- Install **Rocky Linux 9** minimal, apply all updates, install `qemu-guest-agent` + cloud-init, set timezone / locale / admin user.
- Clean machine-id and SSH host keys, then convert to template. Name it like `rocky9-golden-2026-10` — future-you will thank present-you.
- Every Linux VM from now on is a **clone** of this. Consistent, fast, repeatable — the same habit you'd want in a client environment.

### Guest plan (single-node starter)

| Guest | Type | Job |
| --- | --- | --- |
| docker-host | LXC or VM | Docker services via Portainer |
| net-services | LXC / VM | AdGuard Home + Nginx Proxy Manager |
| monitoring | LXC (co-locate early) | Uptime Kuma + Homepage dashboard |
| templates | Template | Rocky 9 golden image |

One Docker host to start — don't shard prematurely. Give the Docker host the most RAM; keep everything else lean (1–2 vCPU, 1–2 GB to start). Proxmox makes resizing easy — undocumented over-provisioning makes troubleshooting miserable.

---

## 4. Networking — DNS, VLAN thinking, remote access

- **DNS filtering:** Run **AdGuard Home** as your network DNS and point your router's DHCP DNS at it. You get ad/tracker blocking plus a query log that teaches you more about your network in a week than a month of guessing.
- **VLAN thinking (even if day one is flat):** Plan three zones — **Trusted** (PCs / servers), **IoT** (TVs, bulbs, cameras), **Guest**. Implement on the managed switch + router when ready. The plan is free; retrofitting without a plan is not.
- **Remote access:** **Tailscale** on the Proxmox host + key services. It punches through CGNAT, needs no port-forwards, and gives you named, ACL'd access.
- **HTTPS everywhere:** Nginx Proxy Manager in front of every web UI, with real certs (Let's Encrypt via Cloudflare DNS challenge if you own a domain). `vault.yourdomain.com` beats `192.168.1.47:8080` in every way that matters.
- **Document as you go:** Keep one page (Wiki.js, Notion, or a Markdown file) with: IP plan, guest list, credentials location (Vaultwarden — not a sticky note), backup schedule, restore-test dates. In production, documentation **is** the system.

---

## 5. The starter stack — what to run first

Install in this order. Each piece makes the next one easier.

| # | Service | Why first |
| --- | --- | --- |
| 1 | Portainer | Manage Docker without living in the CLI |
| 2 | Nginx Proxy Manager | One place for hostnames + SSL |
| 3 | AdGuard Home | Network DNS + filtering, instant win |
| 4 | Vaultwarden | Self-hosted vault for lab credentials |
| 5 | Uptime Kuma + Homepage | Monitoring + dashboard |
| 6 | One "real" service | Firefly III, Wiki.js, or WordPress |

Portainer is a safety net — you will still learn the CLI. Every later service gets a clean URL on day one thanks to the proxy. Your lab credentials need a real home immediately (Vaultwarden). Pick the one "real" service you will actually use weekly — usage is what turns a lab into a skill.

### Container rules (production habits, homelab scale)

- One Compose file per service, named volumes, `.env` for secrets — **never secrets in git**.
- Pin image versions (`image: service:1.2.3`) and update deliberately. "Latest broke at 2am" is a rite of passage you only need once.
- Every Compose file lives in version control (without secrets). If the host dies, redeploy = clone repo + `docker compose up -d`.

---

## 6. Backups that restore — 3-2-1 or it didn't happen

**3 copies, 2 different media, 1 offsite/offline.** In this layout: live VMs (copy 1) → NAS via Proxmox backup (copy 2) → offsite / offline copy (copy 3 — a cloud bucket or a rotated external drive).

- **Schedule:** Nightly, incremental-friendly backups; retain 7 daily + 4 weekly. Databases (MariaDB etc.) get logical dumps too — VM snapshots alone are not a database backup strategy.
- **Monthly restore test (the whole point):** Pick one VM, restore it to a test ID, boot it, log in, verify the service. Log the date and the result. **An untested backup is a hope, not a backup.**
- **Config backups:** Compose files, Proxmox config notes, router/switch exports. Rebuilding hardware is annoying; rebuilding undocumented config is a lost weekend.

**This is also a Sylvect service for a reason:** most small businesses I meet "have backups." Almost none have a dated, successful restore test. If reading this made you nervous about your business systems, see "Work with me" at the end — the Backup & Recovery Check exists for exactly that.

---

## 7. Security baseline — 30 minutes, huge payoff

- Unique admin passwords in Vaultwarden + 2FA on Proxmox and your registrar / Cloudflare.
- SSH keys only, no password SSH on guests; updates on a cadence (weekly for the lab, planned windows for anything client-facing).
- No admin UIs exposed to the internet — Tailscale or VPN only. The reverse proxy gets HTTPS + strong auth for anything sensitive.
- UPS monitored (NUT or the vendor tool) so guests shut down cleanly before the battery dies.

---

## 8. The weekend build order

### Day 1 — Foundation: Proxmox + template + Docker

1. Install Proxmox, static IP, updates, storage + NAS backup target.
2. Build the Rocky 9 golden template (updates, guest agent, cloud-init).
3. Clone the Docker host, install Docker + Portainer.
4. Deploy Nginx Proxy Manager — first hostname + cert working.

### Day 2 — Services + safety: DNS, monitoring, backups

1. AdGuard Home live, router DNS pointed at it.
2. Tailscale on host + phone, remote login proven.
3. Vaultwarden + Uptime Kuma + Homepage up.
4. First backup job runs **and one restore test passes** — then you're done.

**What to skip for now:** Kubernetes, HA clustering, Ceph, a second node "for later," and any service you can't name a weekly use for. Depth on one node teaches you more than breadth across five half-finished systems.

### Common first-month mistakes (so you can skip them)

- Backups on the same disk as the VMs — that's one copy with extra steps.
- Port-forwarding Proxmox / Portainer to the internet "temporarily" — it never is.
- Twelve services, zero monitoring; first alert = a family member saying "the internet is down."
- No IP / credential documentation until "later" — later is doing it from memory at midnight.

---

## 9. Starter checklist

Work top to bottom. This is the same checklist as the interactive version on the guide page.

- [ ] **Hardware ready** — mini PC (16–32 GB RAM), managed switch, UPS on the desk.
- [ ] **Proxmox installed** — static IP, updates done, NAS added as backup storage.
- [ ] **Golden template built** — Rocky 9, guest agent + cloud-init, cloned once successfully.
- [ ] **Docker host live** — Portainer up, Nginx Proxy Manager issuing real HTTPS certs.
- [ ] **DNS + remote access** — AdGuard serving the network, Tailscale login proven from your phone.
- [ ] **Core stack up** — Vaultwarden, Uptime Kuma, Homepage, and one real service you use weekly.
- [ ] **Backups + restore test** — nightly job running, one VM restored and verified, date logged.
- [ ] **Documented** — IP plan, guest list, credential locations, and restore dates on one page.

---

## The gear this actually runs on

These are the exact units in my lab. Prices and availability change — check the listing for current details.

- **Dell OptiPlex 7070 Micro · i5-9500T** — the Proxmox workhorse. Small, quiet, sips power. https://amzn.to/4hT4Vks
- **NETGEAR GS108Ev3 managed switch** — VLANs and clean segmentation without enterprise pricing. https://amzn.to/3TXJ42b
- **APC BR1500MS2 UPS** — rides out blips, clean shutdown on extended outages. https://amzn.to/4rDFg2n
- **QNAP TS-216G NAS** — backup target + shared storage in the 3-2-1 layout. https://amzn.to/46LVBIX
- **RackPath 9U rack** — keeps switch, node, UPS, and cables tidy once you grow. https://amzn.to/4da6ms2

**Disclosure:** Gear links are Amazon Associates links (tag: slateenterpri-20). I only list hardware that actually runs in my lab. If you buy through a link, it supports the builds at no extra cost to you.

**Software I live in:** Proxmox VE · Rocky Linux · Docker / Portainer · n8n · Tailscale · Cloudflare · Wiki.js · Vaultwarden.

---

## Where to go next

The lab on my page is this guide, lived in — Command Center dashboard, n8n automations, Wiki.js knowledge base, AI agents. Build the foundation this weekend, then pick **one** project track and go deep.

When you're ready for the templates version of everything above (Compose files, backup checklists, layout worksheets), join the newsletter — **template drops go to subscribers first.** The AI-Assisted IT Engineer Playbook lands there first too.

- **Newsletter / build logs:** https://slybuilds.substack.com — see it in practice: "I Built a Command Center for My Entire Homelab" — https://slybuilds.substack.com/p/i-built-a-command-center-for-my-entire
- **Threads (personal):** https://www.threads.com/@sergeant_sly
- **Threads (business):** https://www.threads.com/@sylvect_it_solutions
- **Sylvect IT Services:** https://sylvect.biz/

## Want this built for your business?

Everything above, productized — fixed-scope project packages for NJ / NYC small businesses (Sylvect IT Services):

- **Backup & Recovery Check — from $500.** Audit your backups, run a real restore test, fix the gaps.
- **Linux Server Cleanup — from $600.** Updates, services, logs, security basics, clean bill of health.
- **App Deployment & Handoff — from $750.** Server, proxy, SSL, backups, and a handoff doc your team can follow.
- **Workflow Automation Build — from $1,500.** One painful manual workflow, automated end-to-end and documented.

Details: https://sylvect.biz/

---

*Guide V1 · October 2026 · Based on the live "sly" Proxmox lab. Found an error or want a topic expanded? Reply on Threads @sergeant_sly — reader fixes ship in V1.1.*
