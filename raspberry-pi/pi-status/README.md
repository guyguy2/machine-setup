# pi-status

A single-page status site for the Raspberry Pi it runs on. Standard library only, no runtime dependencies, reachable
only over Tailscale. It is part of this repo because it is part of setting up a new Pi: `restore.sh` in the parent
folder installs and starts it.

    uv run pi-status                    # binds the Tailscale IP, port 8080
    uv run pi-status --host 127.0.0.1   # what the service uses; Tailscale Serve adds HTTPS in front

## Tabs

| Tab | Shows |
|---|---|
| Overview | CPU, temperature, memory, disk, uptime, model and revision, OS, kernel, Wi-Fi/ethernet, local IP, Tailscale IP, power/thermal throttling warnings |
| Network | Ready-to-paste SSH commands (Tailscale name and IP, `.local`, LAN IP, plus an `ssh pi` config snippet), Wi-Fi details, gateway, DNS, interfaces, Tailscale peers, logged-in sessions |
| Agents | **Sign-ins** (`gcloud`, `gws`, `gh`, `claude`, Tailscale: signed in, expired, signed out or not installed, with account and project) and which agents are running (Claude Code, OpenHuman, Hermes, OpenClaw) with PID, CPU, memory, directory, listening ports |
| Docker | Containers, or a note that Docker isn't installed |
| Services | Running (and failed) systemd system and user services |
| Processes | Top processes by CPU or memory |
| Ports | Listening TCP ports and who can reach them (local only, tailnet, all interfaces) |

To track another agent, add an entry to `AGENTS` in `src/pi_status/collect.py`; for another sign-in check, add a
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
- `restore.sh` in the parent folder sets all of this up on a fresh image (steps `tailscale` and `pi-status`).
- `~/dev/pi-status` is a symlink to this folder, so there is only one copy.
- `upd` runs `uv sync` and restarts the service after pulling repos.

## Develop

    uv run pytest                       # unit, server and browser tests (Playwright drives the system Chromium)
    uv run python screenshots.py        # PNGs of every tab (desktop + phone) in ./screenshots

JSON endpoints (all GET except restart): `/api/status`, `/api/network`, `/api/agents`, `/api/auth`, `/api/docker`,
`/api/services`, `/api/processes`, `/api/ports`, `/api/version`; `POST /api/restart`.
