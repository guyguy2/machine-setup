# pi-status

A single-page status site for the Raspberry Pi it runs on. Standard library only, no runtime dependencies, reachable
only over Tailscale. It is part of this repo because it is part of setting up a new Pi: `restore.sh` in the parent
folder installs and starts it.

    uv run pi-status                    # binds the Tailscale IP, port 8080
    uv run pi-status --host 127.0.0.1   # what the service uses; Tailscale Serve adds HTTPS in front

## Tabs

| Tab | Shows |
|---|---|
| Overview | The home page. **Needs attention** lists what needs you, each problem once, and is hidden when all is well: power/thermal throttling, a failed agent, a sign-in that is signed out, expired or failing, a failed systemd service, and newer pi-status code on disk (with **Restart now**). Then CPU, temperature, memory and disk, one line per agent with its status and **Start/Stop**, and uptime, model and revision, OS, kernel, Wi-Fi/ethernet, local IP and Tailscale IP |
| Agents | One card per agent (Claude Code, OpenHuman, Hermes, OpenClaw), running ones first. Status is running, starting, stopping, stopped or failed, taken from the agent's systemd unit ("starting" while the unit is up but its dashboard port isn't listening yet), or for Claude Code from its processes. The card links to the Hermes dashboard or OpenClaw Control UI on the tailnet (opens in a new tab, with Copy); if it isn't published yet, it shows the `tailscale serve` command instead. **Start/Stop** control the services of Hermes, OpenClaw and OpenHuman to free up resources: a stop is systemd's graceful one (SIGTERM, then the unit's stop timeout to clean up), and a stopped service starts again at boot. The card shows uptime, CPU and memory; Claude Code lists one row per session (directory, uptime, memory, command one click away); **More** has the `ssh -L` tunnel and localhost URL, the unit and the process table. **Sign-ins** (`gcloud`, `gws`, `gh`, `claude`, Tailscale: signed in, expired, signed out or not installed, with account and project) fold to one line, "5 of 5 signed in", and open themselves when one isn't signed in |
| Agent Lab | Read-only view of `~/dev/agent-lab` (the OpenClaw / Hermes / OpenHuman comparison): scoreboard per use case, average scores per agent as a bar chart, time and memory per run, my notes per agent, every run note (`#lab/<file>` links to one), and each use case's prompt with a Copy button. The markdown files stay the source of truth; nothing is written back |
| Network | Ready-to-paste SSH commands (Tailscale name and IP, `.local`, LAN IP, plus an `ssh pi` config snippet), Wi-Fi details, gateway, DNS, interfaces, Tailscale peers, logged-in sessions |
| System | Sub-tabs, each with its own address: **Docker** (`#system/docker`, the default: containers, with an HTTPS link to the Pi-hole admin UI (`https://<pi>.<tailnet>.ts.net:8445/pihole/admin/`) while its container runs, or the `tailscale serve` command to publish it, or that Docker isn't installed or isn't running), **Services** (`#system/services`: running and failed systemd system and user services), **Processes** (`#system/processes`: top processes by CPU or memory) and **Ports** (`#system/ports`: listening TCP ports and who can reach them: local only, tailnet, all interfaces). The old `#services`, `#processes`, `#ports` and `#docker` links redirect there |

To track another agent, add an entry to `AGENTS` in `src/pi_status/collect.py` (and to `DASHBOARDS` if it has a
web UI, with its local port and the HTTPS port `tailscale serve` publishes it on); for another sign-in check, add a
function and an entry to `AUTH_CHECKS` there. Sign-in checks only call each CLI's local status command. Tokens, client
IDs and org IDs never reach the page, and command lines have key-like values masked.

## Refreshing and resource use

Nothing runs in the background. The server only reads `/proc` or runs a command when a request arrives, and the page
fetches once when you open a tab (and again when you press **Refresh** in the sidebar); it never polls. With no page
open the service uses no CPU. The sign-in checks (slow CLIs such as `gcloud`) are cached for 60 seconds.

## Version stamp and restart button

The bottom of the sidebar shows `v<date time> · <commit>`. The commit is the last one that touched this folder, so the
constant snapshot commits elsewhere in the repo don't change it. A trailing `+` means uncommitted changes and
`uncommitted` means no commit yet.

If the code on disk is newer than what the running server loaded (after editing or `git pull`), the stamp shows an
amber "newer code on disk" notice with a **Restart now** button. The button POSTs to `/api/restart` (the request must
carry an `X-Requested-With` header, so other websites can't trigger it), the service restarts itself through systemd,
and the page reloads when the new server is up. A server started by hand can't restart itself, so there the notice just
asks you to restart it: `systemctl --user restart pi-status`.

## How it runs on the Pi

- `~/.config/systemd/user/pi-status.service` starts it on `127.0.0.1:8080` and restarts it if it dies.
- `sudo tailscale serve --bg 8080` publishes it as `https://<pi>.<tailnet>.ts.net` with a real certificate
  (enable HTTPS certificates and Serve once in the Tailscale admin console).
- The dashboards it links to run as their own user units (`hermes-dashboard.service` on 9119,
  `openclaw-gateway.service` on 18789), published on the tailnet at `:8443/hermes/` and `:8444/openclaw/` (its `gateway.controlUi.basePath` is `/openclaw`). The Pi-hole UI (Docker, host port 8081) is published at `:8445/pihole/admin/`. Hermes has no prefix setting of its own but honours `X-Forwarded-Prefix`, so `hermes-proxy.service` (Caddy on 127.0.0.1:9120, config in `services/hermes-proxy/`, started and stopped with `hermes-dashboard.service`) adds that header and Tailscale publishes the proxy.
- `restore.sh` in the parent folder sets all of this up on a fresh image (steps `tailscale` and `pi-status`).
- `~/dev/pi-status` is a symlink to this folder, so there is only one copy.
- `upd` runs `uv sync` and restarts the service after pulling repos.

## Develop

    uv run pytest                       # unit, server and browser tests (Playwright drives the system Chromium)
    uv run python screenshots.py        # PNGs of every tab (desktop + phone) in ./screenshots
    pyright                             # type-check the Python (kept at 0 errors; install with sudo npm install -g pyright)

JSON endpoints (all GET except restart): `/api/status`, `/api/network`, `/api/agents`, `/api/dashboards`, `/api/auth`, `/api/docker`,
`/api/services`, `/api/processes`, `/api/ports`, `/api/lab`, `/api/version`; `POST /api/restart`, `POST /api/agents/<unit>/start` and `/stop` (only the
units in `AGENTS`; both POSTs need the `X-Requested-With: pi-status` header).
