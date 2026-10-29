# Docker on this Pi

Notes on how Docker is set up here, how to add a container service, and options for later. Written 2026-10-27.
Nothing in this folder is run by `restore.sh`; each service's own files live under `../services/<name>/`.

## What's installed

| Part | Version (2026-10-27) | Source |
|---|---|---|
| Engine (`docker.io`, containerd, runc) | 26.1.5 | apt (Debian trixie), listed in `snapshot/apt-manual.txt` |
| Compose (`docker-compose`, also `docker compose`) | 2.26.1 | apt |
| buildx | 0.13.1 | apt |

- Data in `/var/lib/docker` on the SD card, overlay2, cgroup v2. No `/etc/docker/daemon.json` (all defaults).
- `restore.sh`'s `system` step adds you to the `docker` group and enables `docker.service`; log out and back in
  before `docker` works without sudo.
- `upd` updates the engine through apt and the Pi-hole image with `docker-compose pull && up -d && image prune -f`.
- pi-status shows containers on its Docker tab (`/api/docker`).

## What runs in it

| Container | Compose file | Ports |
|---|---|---|
| `pihole` | `services/pihole/docker-compose.yml` (`~/dev/pihole`) | DNS :53 on all interfaces, UI 127.0.0.1:8081 |

Everything else (pi-status, the Hermes and OpenClaw dashboards, the Caddy in `services/hermes-proxy/`) runs as
systemd user units, not containers.

## Adding a container service

1. `services/<name>/docker-compose.yml` with `restart: unless-stopped`, settings as environment variables in the file,
   secrets in a gitignored `.env` (plus `.env.example`), data in a gitignored folder next to it.
2. Publish ports on loopback only (`"127.0.0.1:<port>:<container port>"`). Docker writes its own iptables rules, so a
   port published as `"<port>:<port>"` is open to the LAN whatever the host firewall says. Then put it on the tailnet
   with `tailscale serve --bg --https=<new port> ...` like the others.
3. Follow "Rules for changing things" in `../README.md`: symlink in the `links` step, a start step in `restore.sh`, a
   row in the services table, an update line in `upd`.
4. Watch RAM: 8 GB is shared with the agents (1-1.8 GB each).

## Known gaps

- **No log rotation.** The default `json-file` driver keeps container logs forever, on the SD card. Fix when it
  matters: `/etc/docker/daemon.json` with `{"log-driver": "local"}` or
  `{"log-opts": {"max-size": "10m", "max-file": "3"}}`, restart docker, recreate containers.
- **Leftover images.** `debian:trixie` and `hello-world` aren't used (`docker system df`: about 140 MB reclaimable).
  `docker image prune -a` would remove them.
- **SD card.** Container writes wear the card; moving to an SSD (IDEAS.md #12) helps Docker most.

## Later: Caddy 2 as the front door

Caddy 2 is already installed (Homebrew, v2.11.7) but only does one job: `services/hermes-proxy/` strips `/hermes` for
the Hermes dashboard. Today each web UI gets its own `tailscale serve` HTTPS port (443, 8443, 8444, 8445), and every
new service adds another.

The option: one Caddyfile routing every service, with `tailscale serve` (or Caddy itself) on a single port.

| | Now (`tailscale serve`, one port each) | Caddy 2 in front |
|---|---|---|
| URLs | `:8443/hermes`, `:8444/openclaw`, `:8445/pihole`, ... | `/hermes`, `/openclaw`, `/pihole` on one port |
| Config | machine state, recreated by `restore.sh` commands | one Caddyfile in git |
| Prefix handling | per app (`FTLCONF_webserver_paths_prefix`, the Hermes proxy) | `handle_path` and headers in one place |
| Extras | none | basic auth, headers, gzip, a landing page, static files |
| HTTPS | Tailscale does it | keep `tailscale serve` → Caddy on loopback, or let Caddy get the `*.ts.net` cert from tailscaled itself (Caddy 2.5+ does this automatically) |

Ways to run it:

- **Grow the existing Brew Caddy**: rename `hermes-proxy` to something like `services/caddy/`, add a block per
  service. Least work, no Docker needed, can reach host services on 127.0.0.1.
- **Caddy in Docker** (`caddy:2` image, arm64): fits if most services become containers, since it can reach them by
  name on a shared Docker network without publishing ports at all. Host services then need
  `host.docker.internal` or `network_mode: host`.
- **caddy-docker-proxy**: Caddy reads routes from container labels, so a new compose service routes itself. Only
  worth it with many containers.

Worth doing when the next web service lands (Uptime Kuma, Paperless, ntfy from IDEAS.md), before a fifth port.
Check first: apps behind a path prefix need to support it (Pi-hole and Hermes do; OpenClaw already serves under
`/openclaw`).
