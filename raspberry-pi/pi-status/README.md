# pi-status

A single-page status site for the Raspberry Pi it runs on: overview, network (with ready-to-paste SSH commands),
agents and sign-in status, Docker, services, processes and listening ports. Standard library only, no runtime
dependencies. Reachable only over Tailscale.

    uv run pi-status                    # binds the Tailscale IP, port 8080
    uv run pi-status --host 127.0.0.1   # what the service uses; Tailscale Serve adds HTTPS in front

## Resource use

Nothing runs in the background. The server only reads `/proc` or runs a command when a request arrives, and the page
fetches once when you open a tab (and once more when you press **Refresh**); it never polls. With no page open the
service uses no CPU. The sign-in checks (slow CLIs such as `gcloud`) are cached for 60 seconds.

## How it runs on the Pi

- `~/.config/systemd/user/pi-status.service` starts it on `127.0.0.1:8080` and restarts it if it dies.
- `sudo tailscale serve --bg 8080` publishes it as `https://<pi>.<tailnet>.ts.net` with a real certificate
  (enable HTTPS certificates and Serve once in the Tailscale admin console).
- `restore.sh` in the parent folder sets all of this up on a fresh image (steps `tailscale` and `pi-status`).
- The bottom of the sidebar shows `v<date time> · <commit>`. A trailing `+` means uncommitted changes, and an
  amber "restart to update" means newer code is on disk than the running server loaded:
  `systemctl --user restart pi-status`.

## Develop

    uv run pytest                       # unit, server and browser tests (Playwright drives the system Chromium)
    uv run python screenshots.py        # PNGs of every tab (desktop + phone) in ./screenshots

Sign-in checks only call each CLI's local status command. Tokens, client IDs and org IDs never reach the page, and
command lines have key-like values masked.
