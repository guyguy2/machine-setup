# Ideas: more uses for this Pi

A backlog of things this Pi could do next, written 2026-10-23 after reviewing `~/dev` and what's running. Nothing
here is set up yet. When one gets done, move it into the runbook (`README.md`, `restore.sh`) and delete it here.

## Where things stood

| Area | State on 2026-10-23 |
|---|---|
| Hardware | Pi 5, 8 GB RAM, 119 GB SD card only (no SSD, nothing on USB), ethernet |
| Running | Pi-hole (Docker, LAN only), pi-status, Tailscale Serve on 443/8443/8444/8445, desktop via VNC |
| Agents | OpenClaw, Hermes: started by hand, one at a time (peak RSS 1–1.8 GB each) |
| Gaps | no cron jobs or timers, no alerts, no exit node or subnet routes, no backup disk |

## Quick wins with what's already here

| # | Idea | How | Why |
|---|---|---|---|
| 1 | Pi-hole for the phone and Mac everywhere | Tailscale admin console → DNS → Nameservers: the Pi's Tailscale IP (`tailscale ip -4`), turn on **Override local DNS** | Ad and tracker blocking away from home; nothing to change on the Pi |
| 2 | Exit node | `tailscale set --advertise-exit-node` (plus `--advertise-routes=<LAN subnet>` for home devices), approve in the admin console | Safe browsing on public Wi-Fi through home, filtered by Pi-hole |
| 3 | Unbound behind Pi-hole | Second container in `services/pihole/docker-compose.yml`, Pi-hole upstream → Unbound | Recursive DNS, so no upstream provider sees every lookup; about 30 MB RAM |
| 4 | Push alerts to the phone | ntfy (container or ntfy.sh) + a systemd timer that reuses pi-status's "Needs attention" checks | pi-status never polls, so throttling, a failed unit, an expired sign-in or a full disk go unnoticed. `upd` and the agents could post too |

## Agent lab follow-ons

| # | Idea | How | Why |
|---|---|---|---|
| 5 | Put the winner on a schedule | Weekly systemd timer that runs whichever of OpenClaw or Hermes scores best in the lab on one prompt (digest, deliveries, commitments, subscription audit) and sends the result to ntfy or a Gmail draft | Turns the lab into something used every week |
| 6 | Small local model | llama.cpp or Ollama with a 1–3B model (Qwen, Llama 3.2) | Email classification, a first prompt-injection screen (UC-009), summaries without API calls. Slow but fine for batch jobs; fits next to one agent |
| 7 | Change detection | changedetection.io, or a job through the shared `web` browser (`agent-lab/browser.md`) | Watch prices, restocks, bill portals with the logins already in the lab profile |

## New services

Each would go in its own folder under `services/`, published with `tailscale serve` on a new port like Pi-hole, and
added to `restore.sh`, pi-status and `upd`. For containers, see `docker/README.md`; before a fifth port, consider Caddy 2 as one
front door (same file, "Later").

| # | Idea | Why | Cost |
|---|---|---|---|
| 8 | Paperless-ngx | OCR'd, searchable archive of bills, receipts and statements; agents could look there instead of Gmail (UC-002, UC-005, UC-008) | About 1 GB RAM: run only when no agent is running |
| 9 | Uptime Kuma | Up/down history for outside services and the agent dashboards, which pi-status doesn't keep | About 150 MB RAM |
| 10 | Self-hosted GitHub Actions runner (arm64) | Run pi-status tests on every push and check `restore.sh --dry-run` on real hardware | Idle until a job runs |
| 11 | Syncthing | Sync `~/dev/agent-lab` and other files with the Mac without going through GitHub | Small |

## Hardware

| # | Idea | Why |
|---|---|---|
| 12 | NVMe HAT + SSD (boot from it) | The best upgrade. Docker, three agents and their Chromium profiles all run from an SD card, which is slow and wears out. `restore.sh` makes the move easy. A USB SSD is cheaper and could also be a Time Machine target for the Mac (Samba) |
| 13 | AI HAT+ (Hailo) | Only for camera or vision work, e.g. Frigate on a doorbell or package camera. It doesn't speed up language models |

## Suggested order

1 and 2 (about 5 minutes, and a big gain on the phone), then 4 and 5 together (alerts plus a scheduled digest), then
12 when buying hardware.
