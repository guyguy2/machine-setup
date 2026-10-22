# raspberry-pi

Rebuild this Raspberry Pi 5 from a blank SD card: packages, shell, settings, the pi-status website, Pi-hole, and
the AI agents (Hermes, OpenClaw, OpenHuman). Everything comes from public GitHub, so no login is needed to start.

**No secrets and no agent state are backed up, on purpose.** Logins, the Pi-hole password and agent onboarding are
done by hand at the end (section 4). It takes about 15 minutes and gives clean agents.

What comes back automatically:

| From | What |
|---|---|
| this folder | scripts, the pi-status website, the Pi-hole compose file, the OpenClaw npm project, agent launchers |
| `snapshot/` (written by `save.sh`) | apt packages and repos, Brewfile, uv and npm tools, dotfiles (`.zshrc` with `upd`, `.gitconfig`, `authorized_keys`, Claude Code settings and skills, desktop configs), systemd user units, hostname and timezone, the list of `~/dev` repos |
| `snapshot/repos.txt` | the `~/dev` git repos: `agent-lab` (private: needs the GitHub login), upstream source clones `hermes-agent`, `openclaw`, `openhuman` |

---

## For an AI agent doing the restore

Follow sections 1 to 5 in order. Rules:

- **Run everything as the normal user `guy`, never root.** The scripts call sudo themselves.
- **Preview with `--dry-run` first**, then run for real. Every step is safe to re-run; files it replaces are moved
  to `~/.pi-restore-backup-<timestamp>/`.
- **Interactive prompts need the user.** These are the sudo password (if not passwordless), the GitHub device code
  (`github` step), the Pi-hole password (`pihole` step) and everything in section 4. Ask the user to run that
  command themselves; in Claude Code they type it with a `!` prefix, e.g. `! ~/dev/machine-setup/raspberry-pi/restore.sh --only github`.
  The user works over SSH from a Mac, so browser sign-ins open on the Mac. `~/.claude/CLAUDE.md` (restored by the
  `dotfiles` step) explains the redirect workaround.
- If a step fails, fix the cause and re-run only that step: `./restore.sh --only <step>`.
- Finish with the checks in section 5 and report which passed and which didn't.

---

## 1. Flash the card (user, on the Mac)

Raspberry Pi Imager → Raspberry Pi OS (64-bit, Debian trixie or newer) → **Edit settings**: hostname
`raspberrypi`, user `guy`, Wi-Fi, timezone `America/Chicago`, **Services → enable SSH with public-key auth** and
paste the Mac's public key. Boot the Pi and wait a minute.

## 2. Bootstrap (one command)

```sh
ssh guy@raspberrypi.local
curl -fsSL https://raw.githubusercontent.com/guyguy2/machine-setup/main/raspberry-pi/bootstrap.sh | bash
```

`bootstrap.sh` installs git, clones this repo to `~/dev/machine-setup` and runs `restore.sh` (preview with
`… | bash -s -- --dry-run`). Expect 20 to 40 minutes, mostly apt and Homebrew. Two prompts along the way:

| Step | Prompt | Answer |
|---|---|---|
| `github` | one-time code | open https://github.com/login/device on the Mac, enter it, approve |
| `pihole` | `choose a Pi-hole admin password` | any password; it's stored in `~/dev/pihole/.env` (gitignored) |

If you're already on the Pi with this repo cloned: `cd ~/dev/machine-setup/raspberry-pi && ./restore.sh`.

## 3. What restore.sh does

| Step | Does | Source |
|---|---|---|
| `apt-sources` | NodeSource and Tailscale apt repos and keys | `snapshot/apt-sources/` |
| `apt` | installs the manually-installed packages (zsh, docker.io, docker-compose, nodejs, git, build tools, ...) | `snapshot/apt-manual.txt` |
| `system` | hostname, timezone, adds you to the `docker` group, enables docker | `snapshot/system.txt` |
| `tailscale` | installs and enables tailscaled (sign-in is section 4) | |
| `brew` | Homebrew + all formulae and casks (gh, uv, hermes-agent, claude-code, gcloud-cli, googleworkspace-cli, ...) | `snapshot/Brewfile` |
| `uv`, `npm` | uv tools, global npm packages (pyright) | `snapshot/uv-tools.txt`, `npm-global.txt` |
| `omzsh` | Oh My Zsh | |
| `dotfiles` | copies `snapshot/dotfiles/` into `$HOME` | `snapshot/dotfiles/` |
| `github` | `gh auth login` (device code) + `gh auth setup-git` | |
| `repos` | clones each repo in `snapshot/repos.txt` that's missing from `~/dev` | `snapshot/repos.txt` |
| `links` | `~/dev/{scripts,pi-status,pihole,openclaw_node}` → folders in this repo | |
| `pihole` | asks for the admin password, then `docker-compose up -d` | `services/pihole/` |
| `agents` | installs OpenClaw (npm) and OpenHuman (.deb + `/opt/openhuman-core`) with `upd`'s own functions; Hermes came from the Brewfile | `~/.zshrc` |
| `pi-status` | `uv sync`, enables the website service, `tailscale serve` for the four HTTPS ports (once Tailscale is signed in) | `pi-status/` |
| `shell` | login shell → zsh | |
| `systemd` | enables the restored user units that were enabled before (only pi-status; the agents stay off) | `snapshot/systemd-user-enabled.txt` |

## 4. Finish by hand (user; also printed at the end of restore.sh)

1. **Log out and back in** (or `sudo reboot`): picks up zsh, the docker group and the hostname.
2. **Tailscale**: `sudo tailscale up`, open the link it prints. In the
   [admin console](https://login.tailscale.com/admin/machines) remove the old machine, then name the new one
   `raspberrypi` so the `https://raspberrypi.<tailnet>.ts.net` URLs stay the same. Then
   `~/dev/machine-setup/raspberry-pi/restore.sh --only pi-status` to publish the HTTPS addresses.
3. **Claude Code**: run `claude` and log in. The agents use this login too.
4. **Google**: `gcloud auth login --no-launch-browser`. For gws, download the OAuth client from Google Cloud console
   → APIs & Services → Credentials to `~/.config/gws/client_secret.json`, then `gws auth login`.
5. **Agents**: onboard each one the way `~/dev/agent-lab/agents.md` records (each uses the `claude` CLI login, no
   API keys). They're installed but not enabled, on purpose: 8 GB of RAM means one at a time. Start one from the
   pi-status Agents tab, with `~/dev/agent-lab/bin/lab use <agent>`, or with `systemctl --user start hermes-dashboard`
   (or `openclaw-gateway`, `openhuman`).
6. **Router**: give the Pi a fixed IP (a DHCP reservation for the **new** MAC address). Devices that use Pi-hole for
   DNS depend on it. The old Pi was 192.168.86.60 on Wi-Fi.
7. **SSH keys** (only if needed): the Pi has no private keys; `gh` handles git over HTTPS.

## 5. Check it worked

| Check | Expected |
|---|---|
| `systemctl --user is-active pi-status` | `active`; `curl -s localhost:8080 \| head -1` prints HTML |
| `docker ps` | `pihole` Up (healthy); `getent hosts example.com` resolves |
| `tailscale serve status` | `/` → 8080, `:8443` → 9119, `:8444` → 18789, `:8445` → 8081 |
| `ls ~/dev` | agent-lab, hermes-agent, machine-setup, openclaw, openhuman; symlinks openclaw_node, pihole, pi-status, scripts |
| `whence -a hermes claude gh uv` | each found once |
| pi-status page → Agents → Sign-ins | gcloud, gws, gh, claude, Tailscale signed in |
| `upd` | runs to "All done." |

---

## Keeping the backup current

`upd` runs `save.sh --push` every 5th run. To save now: `~/dev/machine-setup/raspberry-pi/save.sh --push`.

- It rewrites `snapshot/`, then commits and pushes **only `snapshot/`**. It refuses if a file is over 100 KB or
  looks like a credential.
- It then lists any `~/dev` repo with uncommitted or unpushed work. Code (pi-status, scripts, agent-lab) is never
  committed automatically; commit it yourself, or a restore won't have it.

## Layout

```
raspberry-pi/
  bootstrap.sh            curl | bash entry point for a fresh image
  restore.sh              rebuild (steps in section 3)
  save.sh                 refresh snapshot/ (upd runs it)
  bin/                    agent launchers                    ~/dev/scripts -> here
  pi-status/              the status website (own README)    ~/dev/pi-status -> here
  services/pihole/        docker-compose.yml, .env.example    ~/dev/pihole -> here
  services/openclaw_node/ npm project OpenClaw runs from     ~/dev/openclaw_node -> here
  snapshot/               generated by save.sh; don't edit by hand
```

`.env`, `etc-pihole/` and `node_modules/` stay local (gitignored). Pi-hole's whole config is in its compose file:
upstream DNS 8.8.8.8/8.8.4.4, Pi-hole's default blocklist, no local DNS records. `etc-pihole/` is rebuilt on first
start. To change Pi-hole settings, use the `pihole` Claude skill or the admin UI; put anything that should survive
a rebuild into the compose file as an `FTLCONF_` variable.

### Services and ports

| What | Runs as | Local | Tailnet HTTPS (`tailscale serve`) |
|---|---|---|---|
| pi-status website | user unit `pi-status.service` (enabled) | 127.0.0.1:8080 | `https://raspberrypi.<tailnet>.ts.net` |
| Hermes dashboard | user unit `hermes-dashboard.service` | 127.0.0.1:9119 | `:8443` |
| OpenClaw gateway + UI | user unit `openclaw-gateway.service` | 127.0.0.1:18789 | `:8444` |
| OpenHuman daemon | user unit `openhuman.service` | | |
| Pi-hole | docker container `pihole` | DNS :53 (all interfaces), UI 127.0.0.1:8081 | `:8445/admin/` |

`tailscale serve` settings belong to the machine and aren't backed up; the `pi-status` step recreates them.

## Rules for changing things (humans and AI agents)

- Edit in this repo; the `~/dev` symlinks point here. Never keep a second copy.
- Never commit secrets here: the repo is public. Passwords and tokens stay on the Pi (gitignored `.env` files, tool
  config dirs) and get re-entered after a rebuild.
- New setting file to keep → add it to `dotfiles` in `save.sh`. New tool → install it the usual way (see
  `~/.claude/CLAUDE.md`); the next save picks it up in the Brewfile or apt list. New repo in `~/dev` → picked up by
  `repos.txt` automatically.
- New service → files under `services/<name>/`, a symlink in the `links` step, a start step in `restore.sh`, a row
  in the tables above.
- After changing a script: `shellcheck -S warning *.sh` and `./restore.sh --dry-run`.

## pi-status/ (status web page)

Single-page status site for this Pi: overview, agents and sign-ins, Agent Lab, network with ready-to-paste SSH
commands, services, processes, ports, Docker. It's a uv project with no runtime dependencies; see its
[README](pi-status/README.md). `upd` restarts it after pulling, and the page shows a **Restart now** button when its
code on disk is newer than the running server. It doesn't poll. Tests: `cd ~/dev/pi-status && uv run pytest`.
