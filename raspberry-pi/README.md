# raspberry-pi

Back up and restore this Raspberry Pi's setup (shell, packages, tools, settings).
Text and scripts only: no SSH keys, tokens, history or caches.

## Back up

    ./save.sh          # refresh ./snapshot
    ./save.sh --push   # also commit snapshot/ and push

`upd` runs `save.sh --push` as its last step, so the repo stays current.
`save.sh` aborts if any snapshot file is over 100 KB or looks like it contains a credential.

## Restore on a new Pi / fresh image

1. Install git and clone this repo to `~/dev/machine-setup` (HTTPS clone needs no login while the repo is public).
2. `cd ~/dev/machine-setup/raspberry-pi && ./restore.sh --dry-run` to preview, then `./restore.sh`.
   Use `--only apt,brew,dotfiles` to run selected steps.
   Steps in order: apt-sources apt tailscale brew uv npm omzsh dotfiles links pi-status shell systemd.
3. Manual follow-ups (also printed at the end): `gh auth login`, `sudo tailscale up` then
   `./restore.sh --only pi-status` (publishes the status page over HTTPS), log in to `claude`, run
   `~/dev/scripts/openhuman` and `~/dev/scripts/openclaw` once to self-install, recreate `~/.ssh` keys.

Existing files are never overwritten: they are moved to `~/.pi-restore-backup-<timestamp>/`.

## What is in snapshot/

| File | Contents |
|---|---|
| `dotfiles/` | `.zshrc` (aliases, `upd`), `.gitconfig`, `~/.config/{zellij,lxterminal,kanshi,wf-panel-pi}`, `mimeapps.list`, user systemd units (`openhuman`, `pi-status`), Claude Code `CLAUDE.md`/`settings.json`/status line |
| `apt-manual.txt` | `apt-mark showmanual` |
| `apt-sources/` | third-party apt sources and their public keys (NodeSource, Tailscale) |
| `Brewfile` | Homebrew formulae, taps and casks (includes Claude Code) |
| `uv-tools.txt`, `npm-global.txt` | `uv tool` / `npm -g` installs |
| `systemd-*-enabled.txt` | enabled units. User units with a restored file are enabled; system-unit differences are only reported |
| `versions.txt` | OS and agent versions at save time (reference) |

`bin/` holds the launch wrappers for Hermes, OpenClaw and OpenHuman; each updates its tool on launch.
`~/dev/scripts` is a symlink to this `bin/` (created by the `links` step of `restore.sh`), so run the agents from there: `~/dev/scripts/hermes`, `~/dev/scripts/openclaw`, `~/dev/scripts/openhuman`.

To back up another file, add it to the `dotfiles` list at the top of `save.sh`.

## Tailscale

The `tailscale` step installs the `tailscale` apt package (its repo and key come from `snapshot/apt-sources/`), enables
`tailscaled`, and reports whether the machine is signed in. Signing in is interactive, so it stays manual: `sudo tailscale up`
and open the link it prints. Tailnet-wide settings (MagicDNS, HTTPS certificates, Serve) live in the Tailscale admin
console and survive a rebuild; the per-machine Serve config does not, which is why the `pi-status` step re-runs
`sudo tailscale serve --bg 8080`.

## pi-status/ (status web page)

`pi-status/` is a single-page status site for this Pi (overview, network with ready-to-paste SSH commands, agents and
sign-in status, Docker, services, processes, ports). It is a uv project with no runtime dependencies; see its
[README](pi-status/README.md). It lives in this repo and `~/dev/pi-status` is a symlink to it (made by the `links`
step), so edit it here and never keep a second copy.

- `~/.config/systemd/user/pi-status.service` (in `snapshot/dotfiles`) runs it on `127.0.0.1:8080`.
- The `pi-status` step runs `uv sync`, enables the service, and, once Tailscale is signed in, runs
  `sudo tailscale serve --bg 8080` to publish it at `https://<pi>.<tailnet>.ts.net` (tailnet only).
- `upd` restarts the service after pulling repos, so the running page loads the new code. The bottom of the page's
  sidebar shows `v<date time> · <commit>`; an amber "newer code on disk" notice with a **Restart now** button means
  the code on disk is newer than the running server.
- The page never polls: it loads when you open a tab and again when you press **Refresh**, so it costs nothing while
  idle.
- `save.sh --push` commits only `snapshot/`. Commit changes under `pi-status/` yourself, or a restore from GitHub
  will not include them.
- Tests: `cd ~/dev/pi-status && uv run pytest`. The README in `pi-status/` has the tab list, endpoints and how to add
  an agent or a sign-in check.
