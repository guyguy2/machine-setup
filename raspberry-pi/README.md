# raspberry-pi

Rebuild this Raspberry Pi 5 from a blank SD card: packages, shell, settings, the pi-status website, Pi-hole, and
the AI agents (Hermes, OpenClaw). Everything comes from public GitHub, so no login is needed to start.

**No secrets in git: this repo is public.** Everything else (agent state in `~/.hermes`, sign-ins and secrets, the
`me` store, app data) goes in a nightly encrypted restic backup on Google Drive, two repos per Pi (user and root-only
system), and comes back with `pi-restore-state` (dry run first, `--yes` to write). Tailscale state,
`/etc/machine-id` and caches are never backed up. How it works and how to set it up: [Nightly backup](#nightly-backup-restic)
below. Without a backup (a first-ever setup), logins, the Pi-hole password and agent onboarding
are done by hand at the end (section 4).

What comes back automatically:

| From | What |
|---|---|
| this folder | scripts, the pi-status website, the Pi-hole compose file, the OpenClaw npm project, agent launchers |
| `snapshot/` (written by `save.sh`) | apt packages and repos, Brewfile, uv and npm tools, dotfiles (`.zshrc` with `upd`, `.gitconfig`, Claude Code settings and skills, desktop configs), systemd user units, hostname and timezone, the list of `~/dev` repos |
| `snapshot/repos.txt` | the `~/dev` git repos: `agent-lab` (private: needs the GitHub login), upstream source clones `hermes-agent`, `openclaw` |

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
| `system` | hostname, timezone, adds you to the `docker` group, enables docker, persistent journal, `PermitRootLogin no` (`sshd_config.d/10-hardening.conf`), masks rpcbind (NFS unused) | `snapshot/system.txt` |
| `tailscale` | installs and enables tailscaled (sign-in is section 4) | |
| `brew` | Homebrew + all formulae and casks (gh, uv, claude-code, gcloud-cli, googleworkspace-cli, ...) | `snapshot/Brewfile` |
| `uv`, `npm` | uv tools, global npm packages (pyright) | `snapshot/uv-tools.txt`, `npm-global.txt` |
| `omzsh` | Oh My Zsh | |
| `dotfiles` | copies `snapshot/dotfiles/` into `$HOME` | `snapshot/dotfiles/` |
| `github` | `gh auth login` (device code) + `gh auth setup-git` | |
| `repos` | clones each repo in `snapshot/repos.txt` that's missing from `~/dev` | `snapshot/repos.txt` |
| `links` | `~/dev/{scripts,pi-status,pihole,openclaw_node,hermes-proxy}` → folders in this repo; `pi-checkup`, `pi-backup`, `pi-restore-state` → `~/.local/bin`; the pi-checkup skill → `~/.claude/skills`; turns on this repo's pre-commit hook (`core.hooksPath .githooks`) | pi-checkup `drift.links` warns about any that are missing |
| `pihole` | asks for the admin password, then `docker-compose up -d`; on the main Pi adds the local DNS record `<LAN IP> <this Pi's tailnet name>` (read on the Pi at run time; only when Pi-hole has none) so home-network devices reach DreamBase without Tailscale | `services/pihole/` |
| `agents` | installs OpenClaw (npm) with `upd`'s own functions, and Hermes with its official installer (`install.sh --skip-browser --skip-computer-use`; the Homebrew formula lacked the `anthropic` library). `~/.hermes` data comes back with `pi-restore-state` (section 4), not this step | `~/.zshrc` |
| `pi-status` | `uv sync`, enables the website service, `tailscale serve` for the four HTTPS ports (once Tailscale is signed in) | `pi-status/` |
| `rei` | the REI dashboard: clones the private repo to `~/dev/rei` (needs the `github` step), `uv sync`, its `deploy/pi/install.sh` (links and enables `rei.service` and `rei-proxy.service`; `rei-vault-sync.timer` only once the rclone remote `gdrive:` exists), then `tailscale serve --https=8446` (tailnet only). Prints its manual follow-ups (section 4) | `~/dev/rei` |
| `mail` | the email sorter behind Home Base's Emails tab: clones the private repo to `~/dev/mail` (needs the `github` step), `uv sync`, links and enables `mail-sync.timer` (every hour). Needs the gws Gmail sign-in and Claude Code signed in; its data (`~/.local/share/mail`) comes back with `pi-restore-state`; without a backup, `uv run mail bootstrap` relearns the last two weeks | `~/dev/mail` |
| `lab` | agent-lab's units: links `vault-index.{service,timer}` from `~/dev/agent-lab/tools/systemd` and enables the timer (hourly Obsidian vault index; needs the rclone remote from `pi-restore-state`); lab Chromium via agent-lab's `bin/browser install-service` | `~/dev/agent-lab` |
| `shell` | login shell → zsh | |
| `systemd` | DreamBase (`~/dev/websites/install.sh`), then enables the user units that were enabled before and have a unit file here (pi-status, `hermes-gateway.service` on the main Pi only, ...; the agent dashboards stay off), lists enabled units that have no unit file, turns on linger | `snapshot/systemd-user-enabled.txt` |

## 4. Finish by hand (user; also printed at the end of restore.sh)

1. **Log out and back in** (or `sudo reboot`): picks up zsh, the docker group and the hostname.
2. **Tailscale**: `sudo tailscale up`, open the link it prints. In the
   [admin console](https://login.tailscale.com/admin/machines) remove the old machine, then name the new one
   `raspberrypi` so the `https://raspberrypi.<tailnet>.ts.net` URLs stay the same. Then
   `~/dev/machine-setup/raspberry-pi/restore.sh --only pi-status` to publish the HTTPS addresses.
   **Restore state**: `pi-restore-state` (dry run), then `pi-restore-state --yes`. It brings back `~/.hermes`,
   sign-ins and data, so the sign-ins and onboarding in steps 3 to 6 are only for a first-ever setup or what it
   reports as missing; still start the agent you use (step 5) and re-run `restore.sh --only rei` (step 6). Needs the
   restic passphrases and the OAuth client file (password manager) and the `gdrive-backup:` rclone remote; see [New Pi from backup](#new-pi-from-backup).
3. **Claude Code**: run `claude` and log in. The agents use this login too.
   **Antigravity CLI** (`agy`, Brewfile cask `antigravity-cli`): run `agy` and sign in, only if not restoring state. Its settings and
   status line come back with the dotfiles step; the token, conversations and memory with `pi-restore-state`.
4. **Google**: `gcloud auth login --no-launch-browser`. For gws, download the OAuth client from Google Cloud console
   → APIs & Services → Credentials to `~/.config/gws/client_secret.json`, then `gws auth login`.
5. **Agents**: onboard each one the way `~/dev/agent-lab/agents.md` records (each uses the `claude` CLI login, no
   API keys). They're installed but not enabled, on purpose: 8 GB of RAM means one at a time. Start one from the
   pi-status Agents tab, with `~/dev/agent-lab/bin/lab use <agent>`, or with `systemctl --user start hermes-dashboard`
   (or `openclaw-gateway`).
6. **REI dashboard** (if you use it): `~/dev/rei/inputs/` comes back with `pi-restore-state`; otherwise copy it from the Mac.
   For the vault sync, run `rclone authorize "drive"` on a machine with a browser (the Mac), then on the Pi
   `rclone config create gdrive drive scope=drive.readonly token='<the JSON it printed>'` and
   `~/dev/machine-setup/raspberry-pi/restore.sh --only rei` again to enable the sync timer. Start it with
   `systemctl --user start rei.service`; the pi-status REI tab shows whether it's up.
7. **Router**: give the Pi a fixed IP (a DHCP reservation for the **new** MAC address). Devices that use Pi-hole for
   DNS depend on it. Then point the router's DNS at Pi-hole with Google as the secondary: [The house's DNS](#the-houses-dns-google-nest-wifi).
8. **SSH keys**: `~/.ssh/` (keys, `authorized_keys`, `config`) comes back with `pi-restore-state`; without it, SSH
   access comes only from the key given to Imager in step 1. To allow another machine, append its public key to
   `~/.ssh/authorized_keys`. `gh` handles git over HTTPS.

## 5. Check it worked

| Check | Expected |
|---|---|
| `systemctl --user is-active pi-status` | `active`; `curl -s localhost:8080 \| head -1` prints HTML |
| `docker ps` | `pihole` Up (healthy); `getent hosts example.com` resolves |
| `tailscale serve status` | `/` → 8080, `:8443/hermes` → 9120 (Caddy) → 9119, `:8444/openclaw` → 18789, `:8445/pihole` → 8081, `:8446` → 8421 (REI's Caddy) |
| `ls ~/dev` | agent-lab, hermes-agent, machine-setup, openclaw, rei, websites; symlinks openclaw_node, pihole, pi-status, scripts |
| `curl -s 127.0.0.1:8080/api/rei` | `"unit_state": "active"` and `"health": {"reachable": true, ...}` once `inputs/` is in place and it's started |
| `whence -a hermes claude gh uv` | each found once |
| pi-status page → Agents → Sign-ins | gcloud, gws, gh, claude, Tailscale signed in |
| `pi-backup status` | last good backup under 36 h old (after `pi-backup init`, the next night) |
| `upd` | runs to "All done." |

---

## Keeping the snapshot current

`upd` runs `save.sh --push` every 5th run (on the main Pi; a worker saves locally only). To save now: `~/dev/machine-setup/raspberry-pi/save.sh --push`.

- It rewrites `snapshot/`, then commits and pushes **only `snapshot/`**. It refuses if a file is over 100 KB or
  looks like a credential.
- It then lists any `~/dev` repo with uncommitted or unpushed work. Code (pi-status, scripts, agent-lab) is never
  committed automatically; commit it yourself, or a restore won't have it.

## Host firewall and hardening (host/)

Installed by restore.sh's `system` step from `host/` (since 2026-11-08):

- **Firewall:** nftables table `inet host` (`host/host.nft`), loaded at boot by `host-firewall.service`. It drops
  unsolicited input except from the LAN (192.168.86.0/24, link-local, ULA and eth0's current global IPv6 /64, which
  `host-firewall refresh` reads from the router's RA via a NetworkManager dispatcher hook and a 10-minute timer),
  `tailscale0`, Docker bridges and Tailscale's UDP port. LAN gets SSH, DNS, mDNS and DreamBase (8090/8091).
  Outbound is untouched. Docker's and Tailscale's own iptables-nft tables are left alone: never use Debian's
  `/etc/nftables.conf` (it starts with `flush ruleset`).
- **Test:** `bin/fw-test` (from the Mac on the LAN over `ssh mac`; every line PASS). From the internet: a phone
  on cellular with Wi-Fi and Tailscale off must time out on `http://[<global IPv6>]:8090/`.
- **What it blocked:** `sudo journalctl -k -g host-fw` (rate-limited log of drops). To open a port to the LAN, add
  it to the `lan` chain in `host/host.nft`, run `./restore.sh --only system`, then `bin/fw-test`.
  Emergency off until the next boot: `sudo systemctl stop host-firewall`.
- **sshd:** keys only, no root, no X11, `AllowUsers guy`. **sysctl:** kptr/dmesg restricted, no ICMP redirects
  (ip_forward stays on for Docker and Tailscale). **unattended-upgrades:** Debian security updates only, no
  automatic reboot; everything else waits for `upd`.

## DNS: Pi-hole and its fallbacks

Pi-hole (`services/pihole/`) answers DNS for the house and for this Pi, forwards to Google (8.8.8.8, 8.8.4.4) and
validates DNSSEC (`FTLCONF_dns_dnssec`: answers it checked carry the AD flag, a broken signature gets SERVFAIL).
When Pi-hole is down, both the house and the Pi fall back to Google directly (since 2026-11-08, agent-lab/reviews R-034):

- **This Pi** resolves through Tailscale's MagicDNS (`/etc/resolv.conf` is `100.100.100.100`), which answers tailnet
  names itself and forwards everything else to NetworkManager's nameservers for the LAN connection. The `pihole`
  step sets those to `127.0.0.1 8.8.8.8 8.8.4.4` (ignoring the router's). MagicDNS asks them all at once and takes the
  first real answer; a timeout or SERVFAIL waits for the others. Pi-hole is a millisecond away and answers blocked
  names from its list instantly, so it normally wins; when it's down, Google answers. Check: `pi-checkup docker`
  (`docker.pi-dns`, and the DNSSEC line). Without Tailscale, glibc reads the same nameservers in order.
- **The house** asks the router, which forwards to its DNS servers. Set them in the Google Home app (next section).

### The house's DNS (Google Nest Wifi)

In the **Google Home** app on the phone:

1. Tap **Wi-Fi** (on the Favorites or Devices tab), then **Settings** (the gear, top right).
2. **Advanced networking** → **DNS**.
3. Choose **Custom**. **Primary server**: this Pi's LAN IP (on the Pi: `ip -4 route get 1.1.1.1`, the address after
   `src`; it needs the DHCP reservation from section 4). **Secondary server**: `8.8.8.8`.
4. **Save**. The network may restart (a minute without Wi-Fi).
5. Check from the Mac on the Wi-Fi: `dig example.com` answers, and `dig doubleclick.net` usually gives `0.0.0.0`.

Caveat: Nest Wifi doesn't keep the secondary only for when the primary fails. It spreads queries over both, so even
with Pi-hole up some lookups go straight to Google: those aren't blocked or counted in Pi-hole's stats (more ads
get through). For full blocking, leave the secondary empty and accept that the house loses DNS when Pi-hole does.
On a second Pi (MULTI-PI.md), use the two Pis' LAN IPs instead and drop `8.8.8.8`.

## Nightly backup (restic)

Everything git can't hold (secrets and sign-ins, `~/.hermes`, the `me` store, app data) goes, encrypted, to Google
Drive every night with [restic](https://restic.net). The code is `backup/`; the design, file paths, `last.json`
schema and exit codes are in `MULTI-PI.md` ("Interfaces").

| Repo | What | Runs as | When |
|---|---|---|---|
| `gdrive-backup:pi-backups/<host>/user` | `backup/includes.txt` + staged copies: Hermes (`hermes backup`), SQLite databases, Pi-hole Teleporter export, the lab Chromium profile (the shared lab browser is stopped for the copy and restarted), gitignored `.env` files in `~/dev` | `guy`: `pi-backup`, user timer | ~03:00 |
| `gdrive-backup:pi-backups/<host>/system` | `backup/system-includes.txt`: labvault, `credential.secret`, `/etc/agent-lab`, SSH host keys, agent-lab sudoers | root: `/usr/local/lib/pi-backup/pi-backup-system`, system timer | ~03:30 |

Keeps 7 daily, 4 weekly, 6 monthly; `restic check` runs weekly. Never backed up: Tailscale state, `/etc/machine-id`,
caches, DreamBase `photos/` (re-fetched from the album), the Pi-hole query log.

**Security**: root never runs anything `guy` can write. `sudo backup/setup` installs root-owned copies of the root
side (and of Homebrew's static `rclone`) into `/usr/local/lib/pi-backup/`, after showing what changed and asking
for `yes`; `pi-backup-system` refuses to run if those files aren't root-owned. Re-run `setup` after changing
`pi-backup-system`, `system-includes.txt` or its units, or after Homebrew upgrades rclone (`setup --check`,
`pi-checkup backup` and `upd` say when). `guy`'s Drive token can still delete either repo: Drive's trash (30 days)
is the undo.

**Passphrases**: one per repo, master copies in the password manager. Each Pi keeps them in
`~/.config/pi-backup/restic-password` and `/root/.config/pi-backup/restic-password` (0600). Without them nobody can
open the backup.

**Keep outside the Pi** (password manager): both passphrases **and the Google OAuth client file**
(`~/.config/gws/client_secret.json`, the gws Desktop client). `gdrive-backup:` uses that client, and
`drive.file` only shows a client the files it created, so a new client can't see the backup. The Pi's only copy is
inside the backup, and Google Cloud console may not show the secret again.

**Fresh-Pi guard**: `pi-backup` and `pi-backup-system` (`init` and `run`) refuse, exit 2, when Drive already has
backups of this hostname but this Pi has neither backed up (`last.json`) nor been restored. Otherwise a new Pi would
make its near-empty home the newest snapshot, which `pi-restore-state` restores by default. `pi-restore-state --yes`
marks the Pi (`<state dir>/restored`); `--fresh` backs up this Pi's state anyway (starting over on purpose).

### Set it up (once per Pi; the user runs these, one at a time)

Replacing a Pi from its backup? Use [New Pi from backup](#new-pi-from-backup) instead: restore first, `init` last.

1. Google OAuth client for rclone (Desktop app) in Google Cloud console, if there isn't one yet. Use the same client
   on every Pi: the `drive.file` scope only sees files made by that client.
2. `rclone authorize "drive" <client_id> <client_secret>` on the Mac, then on the Pi
   `rclone config create gdrive-backup drive scope=drive.file client_id=… client_secret=… token='<JSON>'`.
3. `sudo apt install restic`.
4. Write both password files (the commands `setup` prints read the passphrase without echoing it).
5. `sudo ~/dev/machine-setup/raspberry-pi/backup/setup`, then `sudo /usr/local/lib/pi-backup/pi-backup-system init`.
6. `pi-backup init` (creates the repo, enables the timer), then a first `pi-backup run --dry-run` and `pi-backup run`.

### Every day

- `pi-backup status` (exit 0 = last good backup under 36 h old and the last check didn't fail);
  `/usr/local/lib/pi-backup/pi-backup-system status` for root's. The pi-status Overview has a Backup strip and
  lists problems under "Needs attention"; `pi-checkup backup` warns too; `upd` runs both checks.
- Logs: `journalctl --user -u pi-backup`, `journalctl -u pi-backup-system` (no file lists are logged).
- By hand: `pi-backup run [--dry-run]`, `pi-backup check`, `pi-backup list` (what's included).

### Restore

`pi-restore-state` is a dry run; it lists what each group would restore and what it would replace. Add `--yes` to
write. `--only hermes,signins,data,system`, `--snapshot ID`, `--host <other Pi>` (whose repo). Replaced files go to
`~/.pi-restore-backup-<timestamp>/`. Hermes comes back through `hermes import`. Telegram is kept only when this is the main
Pi restoring its own backup; otherwise `TELEGRAM_*` is removed and the gateway stays off, so two Pis never poll
one bot. `~/.ssh/authorized_keys` is merged, not replaced. The Pi-hole export is never imported automatically (it
prints the command). Drill without touching anything live: `pi-restore-state --target-home <empty dir> --yes`.

### New Pi from backup

The order matters: restore before the nightly backup is switched on (the fresh-Pi guard refuses the other way round).
Shut the old Pi down first if it still runs: the restored main Pi keeps the Telegram bot, and two gateways can't
share one.

1. Flash with the same hostname (`raspberrypi`) and user `guy`; then `bootstrap.sh` (sections 1 and 2). It installs
   restic, zip, rclone and Hermes.
2. Put the OAuth client file back at `~/.config/gws/client_secret.json` (password manager), then
   `~/dev/agent-lab/bin/rclone-login --remote gdrive-backup` (two steps, from the Mac's browser).
3. Write both passphrase files (password manager), then `sudo ~/dev/machine-setup/raspberry-pi/backup/setup`.
4. `pi-restore-state` (dry run: check what it would restore), then `pi-restore-state --yes`.
5. Only now: `pi-backup init` and `sudo /usr/local/lib/pi-backup/pi-backup-system init` (they enable the timers).
6. The rest of section 4 (Tailscale, `restore.sh --only rei`, ...).

## Pi lost or compromised: revoke everything

If the Pi (or its SD card) is stolen, lost, or something on it can't be trusted any more, revoke what it holds
**from another device**, in this order (most reach first). Almost all of it can be done off the Pi. Then rebuild
from [New Pi from backup](#new-pi-from-backup) and sign everything in again; that new sign-in replaces what was
revoked here.

1. **Mac**: delete the Pi's public key from the Mac's `~/.ssh/authorized_keys` (the Pi can SSH into the Mac). This
   needs the Mac itself. A `from=` / `command=` restriction on that key line limits what it can do in the meantime.
2. **GitHub** → Settings → Developer settings → Fine-grained tokens: revoke the Pi's token (it can push to the
   public repo future Pis bootstrap from). Also check Settings → Applications for OAuth apps it signed in.
3. **Google** → Google Account → Security → Third-party connections (myaccount.google.com/permissions): remove
   access for the Pi's own OAuth client (gws and the rclone Drive remotes use it), rclone, and Google Cloud SDK.
   This also cuts off the backup on Drive; afterwards change both restic passphrases from another machine
   (`restic key add`, then `restic key remove` the old key), since the Pi held them.
4. **Anthropic**: in the Console, revoke the API key the agents use; on claude.ai, sign out the Pi's Claude Code
   session (Settings → sessions / devices).
5. **Telegram**: in BotFather, `/revoke` the bot's token (the Hermes gateway uses it).
6. **WhatsApp** (phone) → Linked devices: log out the Pi's session.
7. **Tailscale** admin console → Machines: remove the Pi (its node key gets tailnet access to the other devices).
8. **Todoist** → Settings → Integrations: revoke the CLI's token.
9. **Shopping and utility accounts the agents sign into** (Amazon, Walmart, the utilities): change the password,
   sign out all devices, and for Amazon **re-enroll the authenticator (TOTP)**: the Pi had the same seed as the
   phone, so the old codes stay valid until it is replaced.
10. **LastPass** → Account settings → Trusted devices: remove the Pi.
11. **Firecrawl**: confirm the API key is revoked (no copy is kept on the Pi, so this can't be checked from it).

## Layout

```
raspberry-pi/
  bootstrap.sh            curl | bash entry point for a fresh image
  restore.sh              rebuild (steps in section 3); --role main|worker (remembered in ~/.config/pi-role)
  MULTI-PI.md             plan for the backup and more Pis: decisions, security model, interfaces, build order
  backup/                 nightly restic backup and pi-restore-state (section "Nightly backup")
  save.sh                 refresh snapshot/ (upd runs it)
  IDEAS.md                backlog of things this Pi could do next (not set up)
  checkup/                pi-checkup command + /pi-checkup skill (own README)
  docker/                 notes: Docker setup, adding a container, Caddy 2 later
  bin/                    agent launchers                    ~/dev/scripts -> here
  pi-status/              the status website (own README)    ~/dev/pi-status -> here
  services/pihole/        docker-compose.yml, .env.example    ~/dev/pihole -> here
  services/openclaw_node/ npm project OpenClaw runs from     ~/dev/openclaw_node -> here
  services/hermes-proxy/  Caddyfile adding /hermes for Hermes ~/dev/hermes-proxy -> here
  snapshot/               generated by save.sh; don't edit by hand
```

`.env`, `etc-pihole/` and `node_modules/` stay local (gitignored). Pi-hole's whole config is in its compose file:
upstream DNS 8.8.8.8/8.8.4.4, Pi-hole's default blocklist, and one local DNS record (this Pi's tailnet name → its LAN
IP, written by the `pihole` step because both values are per-Pi and the repo is public). `etc-pihole/` is rebuilt on
first start (the nightly backup keeps a Teleporter export of it). To change Pi-hole settings, use the `pihole` Claude
skill or the admin UI; put anything that should survive a rebuild into the compose file as an `FTLCONF_` variable
(pi-checkup's `docker.pihole-ui` warns about settings that are only in `etc-pihole/`).

### Services and ports

| What | Runs as | Local | Tailnet HTTPS (`tailscale serve`) |
|---|---|---|---|
| pi-status website | user unit `pi-status.service` (enabled) | 127.0.0.1:8080 | `https://raspberrypi.<tailnet>.ts.net` |
| Hermes dashboard | user unit `hermes-dashboard.service` | 127.0.0.1:9119 | `:8443/hermes/` (through `hermes-proxy.service`, Caddy on 127.0.0.1:9120) |
| OpenClaw gateway + UI | user unit `openclaw-gateway.service` | 127.0.0.1:18789 | `:8444/openclaw/` |
| Hermes Telegram bot | user unit `hermes-gateway.service` (enabled; main Pi only, one gateway per bot token), unit file in `snapshot/dotfiles` | none | none |
| Obsidian vault index | user timer `vault-index.timer` (hourly), linked from `~/dev/agent-lab/tools/systemd` by the `lab` step | none | none |
| Lab Chromium (shared browser for the agents) | user unit `lab-chromium.service`, linked by agent-lab's `bin/browser install-service` (the `lab` step) | CDP 127.0.0.1:9222 | none |
| Pi-hole | docker container `pihole` | DNS :53 (all interfaces), UI 127.0.0.1:8081 | `:8445/pihole/admin/` |
| REI dashboard | user units `rei.service` (uvicorn) and `rei-proxy.service` (Caddy; rewrites Host, the app only accepts loopback Hosts), `rei-vault-sync.timer` (rclone, read-only Drive), from the private repo `~/dev/rei` (its `deploy/pi/install.sh`, run by the `rei` step) | 127.0.0.1:8420, Caddy 127.0.0.1:8421 | `:8446/` → 8421, tailnet only (not on the Wi-Fi/LAN, no redirect port) |
| DreamBase (family site) | user units `dreambase*` from the private repo `~/dev/websites` (its `install.sh`, run by the systemd step; manual steps in its README) | 127.0.0.1:8092 | not `tailscale serve`: its own Caddy on :8091 (HTTPS, Wi-Fi and tailnet), :8090 redirects |

`tailscale serve` settings belong to the machine and aren't backed up; the `pi-status` step recreates them.

## Rules for changing things (humans and AI agents)

- Edit in this repo; the `~/dev` symlinks point here. Never keep a second copy.
- Never commit secrets or identifying details here: the repo is public. Write `<tailnet>` instead of the real
  Tailscale name (`save.sh` refuses a snapshot containing it). Passwords and tokens stay on the Pi (gitignored `.env` files, tool
  config dirs) and in the encrypted backup.
- Secrets stay out of git. To keep a new secret or data file, add it to `backup/includes.txt` (gitignored `.env`
  files in `~/dev` repos are found automatically).
- New setting file to keep → add it to `dotfiles` in `save.sh`. New tool → install it the usual way (see
  `~/.claude/CLAUDE.md`); the next save picks it up in the Brewfile or apt list. New repo in `~/dev` → picked up by
  `repos.txt` automatically.
- New service → files under `services/<name>/`, a symlink in the `links` step, a start step in `restore.sh`, a row
  in the tables above.
- After changing a script: `shellcheck -S warning *.sh` and `./restore.sh --dry-run`.
- Commits run `.githooks/pre-commit` (gitleaks, the tailnet name, shellcheck, pi-checkup tests; the `links` step turns
  it on) and every push runs CI (`.github/workflows/ci.yml`). `--no-verify` skips the hook only in an emergency.

## pi-status/ (status web page)

Single-page status site for this Pi: overview, agents and sign-ins, Agent Lab, network with ready-to-paste SSH
commands, services, processes, ports, Docker. It's a uv project with no runtime dependencies; see its
[README](pi-status/README.md). `upd` restarts it after pulling, and the page shows a **Restart now** button when its
code on disk is newer than the running server. It doesn't poll. Tests: `cd ~/dev/pi-status && uv run pytest`.

## Mac side

`mac/` holds scripts that run on the Mac and talk to the Pi over `ssh pi`. Keep them out of `bin/`, which is on the Pi.

`mac/pi-paste` sends the clipboard image to `~/screenshots` on the Pi and prints its remote path. Ctrl+Opt+V in Ghostty runs it through `~/.hammerspoon/init.lua` and types that path into the terminal.
