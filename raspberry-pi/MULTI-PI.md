# Multi-Pi plan: full backup, then more Pis

Written 2026-11-06, reviewed the same day against the code (restore.sh, save.sh, Hermes v0.23.0 source and docs,
agent-lab). **Being built: "Build order" has the status.** When a step is done, move what it built into `README.md` (the
runbook) and tick it off in "Build order".

## Goal

1. **Back up everything that makes this Pi "this Pi"**, so a dead SD card costs one restore, not a re-teach: agent
   state (Hermes memories, skills, sessions), sign-ins and secrets, personal data, app data.
2. **Add worker Pis** (`pi2` now, `pi3` maybe later) on the same LAN (ethernet, through a switch) and the tailnet. They
   do work: run agents, run Docker. Never more than a few Pis; a home lab, not a cluster.

## What exists today

`save.sh` / `restore.sh` rebuild this Pi from GitHub in about 40 minutes (see `README.md`): packages, Homebrew,
dotfiles, `~/dev` repos, Pi-hole, pi-status, REI, mail, DreamBase (`restore.sh` runs `~/dev/websites/install.sh` in
its `systemd` step) and the Hermes install. They deliberately skip everything below, which this plan adds:

| Layer | Contents | Today |
|---|---|---|
| 1. System | apt, Homebrew, dotfiles, systemd units, Docker, Tailscale install | `restore.sh` ✅ |
| 2. Apps (code) | pi-status, Pi-hole, REI, mail, websites/DreamBase | `restore.sh` ✅ |
| 3. Agent state | `~/.hermes` (memories, own skills, sessions, cron, kanban, profiles) | ❌ |
| 4. Secrets, sign-ins | Hermes `.env`/`auth.json`, gws, rclone, gh, gcloud, todoist-cli, Claude Code, SSH key, labvault | ❌ redone by hand |
| 5. Personal and app data | `me` store, REI `inputs/`, mail data, DreamBase data, Pi-hole lists, services' `.env` | ❌ |

## Decisions (made 2026-11-06)

| # | Topic | Decision | Why |
|---|---|---|---|
| 1 | Backup tool | **restic, from apt** (trixie: 0.18) | Encrypted, versioned, deduplicated, one restore command. apt, not Homebrew: a system service (the root timer) depends on it, and `/home/linuxbrew` is writable by `guy` (see Security) | ✅ set up 2026-11-06: both repos on Drive, timers 03:00 (user) / 03:30 (system), first backups and checks ok (~107 MB on Drive); restore drill into an empty home ok (hermes, signins, data) |
| 2 | Passphrase | Master copies in the user's password manager; each Pi keeps owner-only password files for the nightly runs | Without it the backup can't be opened by anyone | |
| 3 | Drive access | New rclone remote **`gdrive-backup:`**, scope **`drive.file`**, on **the user's own Google OAuth client from day one** | `gdrive:` stays `drive.readonly`. `drive.file` only sees files created by the same OAuth client, so switching clients later would hide the repo || ✅ code 2026-11-06: pi-status Overview Backup strip + attention items (`/api/backup`), `pi-checkup backup` domain, `upd` step, README "Nightly backup"; shows real data after the first run |
| 4 | Scope | **Everything**: Hermes incl. secrets, sign-ins, `me` store, app data | Restore without re-teaching or re-signing in | ✅ 2026-11-06 (worker skips `rei`, `mail`, DreamBase; `save.sh --push` refuses on a worker) |
| 5 | Schedule | **Nightly ~03:00** (systemd timers); keep 7 daily / 4 weekly / 6 monthly; `restic check` weekly; failures in pi-status and pi-checkup | restic stores only changes, so nightly is cheap | |
| 6 | Setting up a Pi | **`restore.sh --role main\|worker`**; Ansible only if the Pis drift | Builds on the tested script | |
| 7 | Talking to agents | **One front door**: the main Pi's Hermes on Telegram. It hands work to workers with **`hermes peer run`/`peer status`** (wrapped in an agent-lab command it runs from the terminal). **Each Pi keeps its own kanban board** | One bot, one chat. Hermes kanban is single-host by design (`kanban.md`, "Out of scope"); two gateways can't share one bot token | |
| 8 | Model keys | **A separate Anthropic API key per Pi**, same account | Per-Pi usage; revoke one Pi alone | |
| 9 | Docker | **Compose per Pi from git**, managed from main with `docker --context <pi>` over SSH | Built in; no cluster |
| 10 | DNS | **Second Pi-hole on `pi2`**; router hands out both | DNS survives either Pi being down |
| 11 | Storage | **SD card** on `pi2` | The nightly backup makes a dead card recoverable |
| 12 | Names | Keep **`raspberrypi`**; new ones **`pi2`**, `pi3` | No existing URL changes |
| 13 | Code location | **this repo** (`machine-setup`, public), `raspberry-pi/backup/` | One runbook. Scripts hold no secrets or personal values |

## Security model (read before building)

- The real boundary is thin: `guy` has passwordless sudo and is in the `docker` group, so anything running as `guy`
  can become root. What keeps agents out of root-only things today is Hermes's deny rules. The plan must not make
  that worse.
- **Two restic repositories per Pi.** Agents run as `guy`; labvault (`/var/lib/labvault`, user `labvault`) exists to
  keep website logins away from them. Root-only files go in a separate repo with a root-only passphrase.
- **Nothing root runs may be writable by `guy`.** No root timer may run restic/rclone from Homebrew or a script from
  `~/dev`. A `sudo raspberry-pi/backup/setup` (like agent-lab's `labvault-setup`) installs root-owned copies of
  `pi-backup-system`, its lists and the units into `/usr/local/lib/pi-backup/` and `/etc/systemd/system/`, with
  absolute paths. Root gets its own `/root/.config/rclone/rclone.conf`. Re-run `setup` after changing those files.
- `guy`'s Drive token can delete the system repo too (`drive.file` sees everything the client created). Drive's trash
  is the undo; note it in the runbook.
- `guy` is in `adm` and can read the system journal: the system job must not log file lists.
- Staging dirs and the Hermes zip: mode 0700/0600, not under `~/.cache`, deleted after each run. The status JSON holds
  times, sizes, snapshot ids and ok/fail only.
- Nothing secret is ever written inside the repo; `save.sh`'s credential check must keep passing.

## Interfaces (contracts every piece builds against)

Fixed 2026-11-06 before building. Change them here first, then in the code.

### Files and paths

| What | User side (`guy`) | System side (root) |
|---|---|---|
| Code (repo) | `raspberry-pi/backup/pi-backup`, `pi-restore-state` (linked to `~/.local/bin/` by `restore.sh`'s `links` step) | `raspberry-pi/backup/pi-backup-system`, `setup` (reviewed in git, never run by a timer from there) |
| Installed copy | runs from the repo | `/usr/local/lib/pi-backup/` (root:root, dir 0755, scripts 0755, lists 0644): `pi-backup-system`, `system-includes.txt`, `rclone` (copy of Homebrew's), `rclone.version` (`rclone version` first line) |
| Lists | `backup/includes.txt`, `backup/excludes.txt` | `backup/system-includes.txt` (installed copy is what runs) |
| Units | `backup/systemd/pi-backup.{service,timer}`, linked into `~/.config/systemd/user/` by `pi-backup init` | `backup/systemd/pi-backup-system.{service,timer}`, copied to `/etc/systemd/system/` (0644) by `setup` |
| restic | `/usr/bin/restic` (apt) | `/usr/bin/restic` (apt) |
| rclone | `/home/linuxbrew/.linuxbrew/bin/rclone`, config `~/.config/rclone/rclone.conf` | `/usr/local/lib/pi-backup/rclone`, config `/root/.config/rclone/rclone.conf` (`setup` copies only the `[gdrive-backup]` section from guy's, if root has none) |
| Repo | `rclone:gdrive-backup:pi-backups/<host>/user` | `rclone:gdrive-backup:pi-backups/<host>/system` |
| Password file | `~/.config/pi-backup/restic-password` (dir 0700, file 0600) | `/root/.config/pi-backup/restic-password` (dir 0700, file 0600) |
| State dir | `~/.local/state/pi-backup/` (0700) | `/var/lib/pi-backup/` (root, 0755) |
| Status | `~/.local/state/pi-backup/last.json` | `/var/lib/pi-backup/last.json` (0644, readable by guy) |
| Restored marker | `~/.local/state/pi-backup/restored`: one line (`restored <time> from <host>` or `fresh <time>`), written by `pi-restore-state --yes` (not a drill) or `--fresh` | `/var/lib/pi-backup/restored` (0644), same |
| Staging | `~/.local/state/pi-backup/staging/` (0700; files 0600; removed at the end of every run, success or not) | `/var/lib/pi-backup/staging/` (0700, same rule; only if something needs staging) |
| Run log (user side only) | `~/.local/state/pi-backup/pi-backup.log`: timestamped copy of the run's output (also in the journal); rotated at 1 MB, 3 kept. `pi-backup log [N]` shows it. Real runs only | none yet: the system job's journal is its log |
| History (user side only) | `~/.local/state/pi-backup/history.jsonl`: one JSON line per real run (`host, started, finished, exit, phase, duration_s`; `phase` = where it was when it ended) | none yet |
| Lock | `flock -n` on `<state dir>/lock`; a second run exits 1 with "already running" | same |
| Role | `~/.config/pi-role`: one line, `main` or `worker` | |

`<host>` is `hostname -s`. restic always gets `--host <host>`, `--tag pi-backup`, `--password-file`, `-o rclone.program=<rclone>`.
JSON is read and written with `/usr/bin/python3 -I` (no jq, no Homebrew tools on the root side). SQLite copies use
Python's `sqlite3` backup API, not the `sqlite3` CLI (that one is Homebrew's).

### Environment overrides (for drills and tests; units set none of these)

| Variable | Default (user / system) |
|---|---|
| `PI_BACKUP_REPO` | the repo above |
| `PI_BACKUP_PASSWORD_FILE` | the password file above |
| `PI_BACKUP_RESTIC` | `/usr/bin/restic` |
| `PI_BACKUP_RCLONE` | Homebrew's rclone / `/usr/local/lib/pi-backup/rclone` |
| `PI_BACKUP_STATE_DIR` | `~/.local/state/pi-backup` / `/var/lib/pi-backup` |
| `PI_BACKUP_HOST` | `hostname -s` (whose repo; `pi-restore-state --host` sets it) |

A test points `PI_BACKUP_RESTIC` at a stub script and `PI_BACKUP_REPO` at a scratch path; nothing in the scripts
may hard-code around these. The system unit's environment comes only from its root-owned unit file, so `guy` can't
set these for the timer. `pi-backup-system`'s ownership self-check (below) runs on whatever paths are in effect:
fatal (exit 2) for a real run, a warning with `--dry-run`.

Units: user `pi-backup.service` is `Type=oneshot`, `ExecStart=%h/dev/machine-setup/raspberry-pi/backup/pi-backup run`,
`Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin` (for `hermes`), `Nice=10`, `IOSchedulingClass=idle`.
System `pi-backup-system.service`: `ExecStart=/usr/local/lib/pi-backup/pi-backup-system run`,
`Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`, `InaccessiblePaths=/home` (root never
touches guy's files), `ProtectSystem=strict`, `ReadWritePaths=/var/lib/pi-backup /root/.cache/restic /root/.config/rclone`,
`PrivateTmp=yes`, `NoNewPrivileges=yes`, `Nice=10`, `IOSchedulingClass=idle`. Timers: `OnCalendar=*-*-* 03:00`
(system 03:30), `RandomizedDelaySec=10m`, `Persistent=true`.

### List formats

`includes.txt`: one item per line, `<group> <path>`; `#` comments and blank lines ignored. Groups: `signins`,
`data` (`hermes` and `system` are not in this file). Paths start with `~/` (expanded to `$HOME`) and may contain
restic globs; symlinks are resolved to real paths. Items that don't exist are skipped with a note. `excludes.txt`:
restic `--exclude-file` patterns, `~/` expanded. `system-includes.txt`: absolute paths/globs, one per line.

### Staging layout (inside the user snapshot)

| Path under the staging dir | Holds | Group | Restored to |
|---|---|---|---|
| `hermes/` | `hermes backup -o …/hermes.zip -k 0`, unzipped (zip deleted) | `hermes` | `hermes import` (re-zipped) |
| `home/<path relative to $HOME>` | SQLite copies (every `*.db` under the include paths; live `*.db`, `-wal`, `-shm` excluded) and the Chromium profile copy (caches excluded) | `data` | `$HOME/<path>` |
| `pihole/teleporter.zip` | `docker exec pihole pihole-FTL --teleporter`, copied out | `data` | imported by hand (printed), never automatically |
| `manifest.json` | `{"schema":1,"host","home","created","items":{"hermes":"ok\|failed","pihole":"ok\|failed\|skipped","chromium":"ok\|skipped\|skipped-running\|failed","sqlite":"ok\|failed"}}` (`skipped`: not on this Pi, e.g. no Chromium profile on a worker; never an error) | | read by `pi-restore-state` |

Gitignored `.env` files are found at run time: `git ls-files --others --ignored --exclude-standard` in every
`~/dev/*` repo (symlinks resolved, `node_modules/` skipped), file name `.env` or `.env.*` except `.env.example`;
group `data`, backed up live.

### `last.json` (both sides, schema 1, written atomically; times are ISO 8601 with offset)

```json
{
  "schema": 1,
  "side": "user",
  "host": "raspberrypi",
  "updated": "2026-11-07T03:04:12-06:00",
  "last_run":  {"started": "…", "finished": "…", "ok": true, "exit": 0, "snapshot": "1a2b3c4d",
                "bytes_added": 12345, "bytes_total": 1234567890, "files_new": 3, "files_changed": 10,
                "duration_s": 245},
  "last_ok":   {"finished": "…", "snapshot": "1a2b3c4d", "bytes_total": 1234567890},
  "last_check":{"finished": "…", "ok": true, "exit": 0, "repo_bytes": 987654321},
  "items":     {"hermes": "ok", "pihole": "ok", "chromium": "skipped-running", "sqlite": "ok"},
  "chromium_last_ok": "2026-11-05T03:02:00-06:00"
}
```

`last_ok` and `chromium_last_ok` carry over from the previous file when this run didn't succeed. A missing key is
`null`. Only times, sizes, counts, short snapshot ids and status words: never paths, file names or error text
(errors go to the journal; the system side never logs file lists either, so no `--verbose` and restic output is parsed,
not echoed). The system side has `"side": "system"`, no `items`/`chromium_last_ok`.

### CLIs and exit codes

Shared exit codes: **0** ok, **1** failed, **2** usage, missing dependency or setup (no restic, no password file, no
rclone remote, not root/root when it must not be), **3** repo unreachable (rclone/Drive error), **4** finished but
incomplete (restic exit 3, or a staging item failed).

`pi-backup <command>` (and `pi-backup-system`, same commands, must run as root):
- `init`: create the repo if it doesn't exist (`restic cat config` first), then link and enable the timer
  (`pi-backup-system`: enable the system timer). Idempotent. `--dry-run` prints what it would do.
- `run [--dry-run]`: lock, `restic unlock` (stale locks only), stage, `restic backup --json --ignore-inode
  --ignore-ctime --files-from … --exclude-file …`, `restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6`
  (no prune), write `last.json`, remove staging. If a snapshot was made (exit 0 or 4) and the check is due
  (`last_check` missing, `ok` false, or older than 6.5 days), then `forget --prune` and `check` (fills `last_check`;
  an unreachable repo, exit 3, leaves the previous `last_check` alone). `--dry-run`: stage, `restic backup
  --dry-run --json` (falls back to a `du` estimate if the repo can't be reached), print what and how much, remove
  staging, write nothing else (no `last.json`).
- Fresh-Pi guard (`init` and `run`, both sides): go ahead if the restored marker exists, or `last.json` has a
  `last_ok` for this host, or `restic snapshots --host <host> --tag pi-backup --latest 1` is empty. Otherwise exit
  **2** naming the newest snapshot (`run` records it in `last.json`; `init` leaves the timer alone). `--fresh`
  writes the marker first. `--dry-run` says whether a real run would refuse. Why: a new Pi with the old hostname
  would make its near-empty state the newest snapshot, the one `pi-restore-state` restores by default.
- `status [--json]`: print `last.json` readably; exit 0 if `last_ok` is under 36 h old and `last_check.ok` isn't
  false, else 1. No network.
- `check`: `forget --prune` then `check`; updates `last_check`.
- `list` (user side only): print `<group>\t<path>` for every resolved include (no staging, no network).
- `--help` everywhere.

`sudo raspberry-pi/backup/setup [--dry-run] [--check]`:
- shows what root will run (diff of each repo file against the installed copy, unpushed/uncommitted changes in
  `backup/`, the copied rclone's sha256 and version) and asks for `yes` (`--yes` skips the prompt but refuses
  uncommitted or unpushed changes). Reads every source as the calling user, never following guy's symlinks as root.
- installs the root-owned copies and units above, copies Homebrew's rclone, copies the `[gdrive-backup]` rclone
  section to root if missing, `systemctl daemon-reload`. Does **not** create passwords or enable the timer
  (`pi-backup-system init` does). Prints the next command when something is missing.
- refuses (exit 2) if `/usr/bin/restic` is missing or not root (except `--check`).
- `--check` (runs as guy, no sudo): exit 0 if every installed file matches the repo and the rclone copy's version
  matches Homebrew's; exit 1 listing what differs; exit 2 if not installed.
- `pi-backup-system` refuses to run (exit 2) if it, its list, its rclone or restic, or any parent directory of those,
  isn't owned by root or is group/other-writable.

`pi-restore-state [--yes] [--snapshot ID] [--host HOST] [--only hermes,signins,data,system] [--target-home DIR]`:
- dry run by default: lists what each group would restore and replace. `--yes` writes.
- `--snapshot` defaults to `latest`; `--host` defaults to `hostname -s` (sets `PI_BACKUP_HOST`, i.e. whose repo).
- `--target-home DIR` (drills): restores into DIR as `HOME` and `DIR/.hermes` as `HERMES_HOME`; Telegram always
  stripped, gateway never started, `system` not allowed.
- Telegram is kept only when `~/.config/pi-role` is `main` **and** `--host` is this Pi's own name (a replacement
  of the same Pi). Otherwise `TELEGRAM_*` lines are removed from the staged `.env` before re-zipping, and
  `hermes-gateway.service` is stopped and disabled before `hermes import`.
- `system` needs sudo (it calls `sudo` itself, only that part) and creates `labvault` with the UID recorded in
  the snapshot (`restic ls --json <snap> /var/lib/labvault` gives uid/gid; 999 today) before restoring
  `/var/lib/labvault`. If those IDs are taken (apt may create system users first), it creates labvault with free
  IDs and re-owns the restored tree.
- SQLite: replacing `X.db` also moves aside its `-wal`/`-shm`/`-journal`; the user units that write restored data
  (mail-sync, rei, dreambase) are stopped for the copy and restarted if they were running.
- `~/.ssh/authorized_keys` is merged (missing lines appended), never replaced.
- exit codes as above; ends by printing what's left by hand.

`restore.sh [--role main|worker] [--dry-run] [--only …]`: `--role` beats `~/.config/pi-role`, which beats the
default `main`; a real run writes the role file. Invalid role: exit 2. `save.sh --push` exits 2 when the role is
`worker`.

## Part A: backup (restic)

### Repositories

| Repo | restic path | Runs as | Password file |
|---|---|---|---|
| user | `rclone:gdrive-backup:pi-backups/<host>/user` | `guy` (systemd **user** timer) | `~/.config/pi-backup/restic-password` (0600) |
| system | `rclone:gdrive-backup:pi-backups/<host>/system` | root (systemd **system** timer) | `/root/.config/pi-backup/restic-password` (0600) |

systemd user units don't have Homebrew on `PATH`, and restic's `rclone:` backend runs `rclone` from `PATH`: pass
`-o rclone.program=<absolute path>`. Open question: move rclone to apt too (one source per tool) or keep Homebrew's
for `guy` and a root-owned copy for root.

### Staging (consistent copies)

Live SQLite files must not be copied raw. Before each run, into a fresh 0700 staging dir:

- **Hermes**: wipe staging, `hermes backup -o <staging>/hermes.zip`, `unzip` (Info-ZIP keeps modes) into
  `<staging>/hermes/`, delete the zip. restic dedupes the unzipped tree night to night. Live `~/.hermes` is excluded.
- **Other SQLite**: `sqlite3 <db> ".backup <staging>/..."` for `~/.local/share/mail/mail.db`,
  `~/.local/share/agent-lab/me/facts.db` and `pending.db`, and any other `*.db` found in the include paths.
- **Pi-hole**: a Teleporter export (`docker exec pihole pihole-FTL --teleporter` or the API) into staging.
- **Lab Chromium profile**: copied with the lab's shared browser (`lab-chromium`, a transient unit from agent-lab
  `bin/browser start`) stopped for the copy, then started again with the same command line (decided 2026-11-06).

Use `--ignore-inode --ignore-ctime` on the staging paths so unchanged files aren't re-read.

### What goes in

User repo (live paths unless staged above; resolve symlinks like `~/dev/pihole` to real paths):

| Item | Path | Notes |
|---|---|---|
| Hermes | staging `hermes/` | Includes `.env`, `auth.json`, vault, profiles, cron, kanban, plugins, `_external/` |
| gws | `~/.config/gws/` | OAuth client + tokens |
| rclone | `~/.config/rclone/rclone.conf` | |
| gh | `~/.config/gh/` | |
| gcloud | `~/.config/gcloud/` | Exclude `logs/` |
| todoist-cli (`td`) | `~/.config/todoist-cli/` | Plaintext token by design |
| Claude Code | `~/.claude/.credentials.json`, `~/.claude.json`, `~/.claude/projects/` | Memory and transcripts are in `projects/` |
| SSH | `~/.ssh/` (`id_ed25519*`, `known_hosts`, `config`, `authorized_keys`) | `~/.ssh/config` uses the key for the Mac |
| agent-lab data | `~/.local/share/agent-lab/` (SQLite staged) | `chromium/` ~430 MB: see staging |
| mail | `~/.local/share/mail/` (SQLite staged) | |
| REI | `~/dev/rei/inputs/` | |
| DreamBase | `~/dev/websites/dreambase/dreambase_data.json`, `~/.local/share/dreambase/` | Exclude `photos/` (~2 GB) if `photos_sync.py` re-fetches it |
| Pi-hole | Teleporter export + `~/dev/pihole/.env` | Never `pihole-FTL.db*` (query log) |
| Services' secrets | every gitignored `.env` under `~/dev/*/` | Found with `git ls-files --others --ignored --exclude-standard` per repo, not a fixed list |
| Shared skills | not needed | in the `agent-lab` repo; restore runs `bin/lab skills` |

System repo: `/var/lib/labvault/`, **`/var/lib/systemd/credential.secret`** (labvault's `systemd-creds` files only
decrypt with it), `/etc/agent-lab/` (`billers.toml`, `logins.toml`), `/etc/ssh/ssh_host_*`, `/etc/sudoers.d/agent-lab-*`.

Never backed up: Tailscale state (a new box joins as a new node), `/etc/machine-id`, caches.

### Pieces to build (`raspberry-pi/backup/`)

| File | Does |
|---|---|
| `pi-backup` | `init`, `run [--dry-run]`, `status`, `check`. Stages, runs restic with the lists, applies retention, writes `~/.local/state/pi-backup/last.json` |
| `includes.txt`, `excludes.txt` | Lists above (`--files-from` / `--exclude-file`); `~` paths, no personal values |
| `pi-backup-system`, `system-includes.txt` | Same for the root repo; installed root-owned by `setup` |
| `setup` | `sudo` installer for the root side (copies, units, password file check) |
| `systemd/pi-backup.{service,timer}` | User units, nightly ~03:00, `Persistent=true` |
| `systemd/pi-backup-system.{service,timer}` | System units (installed by `setup`) |
| `pi-restore-state` | **Dry run by default; `--yes` to write.** `[--snapshot ID] [--only hermes\|signins\|data\|system]`. Details below |

`pi-restore-state` details:
- restic restore to a 0700 staging dir; files it replaces go to `~/.pi-restore-backup-<timestamp>/` (like `restore.sh`).
- Hermes: re-zip **from inside** the staging dir (`cd hermes && zip -qr ../hermes.zip .`; the importer only strips a
  `.hermes/` or `hermes/` prefix, `backup_restore.py:395-415`), keep `_external/`, then `hermes import --force`.
  Afterwards `chmod -R go-rwx ~/.hermes`: import tightens only `.env`, `auth.json`, `state.db`, `vault.*`.
- `hermes import` restarts the gateway after a default-home import (`backup.py:1072-1097`). On any Pi that isn't
  the main Pi's replacement, stop/disable the gateway and remove `TELEGRAM_*` from `.env` **before** it starts, or
  two gateways poll one bot.
- System part: create user `labvault` with the **same UID (999)** before restoring `/var/lib/labvault`.
- Print what's left (Tailscale join, the new Pi's API key if it's a worker).

Conventions (this repo's `CLAUDE.md`): bash, `set -euo pipefail`, `--help`/`--dry-run`, exit codes; extend the
shellcheck line to `raspberry-pi/backup/*`.

### User steps (one command at a time, the user runs them)

1. Create a Google OAuth client (Desktop app) for rclone, if the pending own-client work hasn't already.
2. Store the two restic passphrases in the password manager; write the password files.
3. `rclone authorize "drive" <client_id> <secret>` on the Mac (the SSH-from-Mac pattern in `~/.claude/CLAUDE.md`),
   then `rclone config create gdrive-backup drive scope=drive.file client_id=… client_secret=… token='…'` on the Pi.
   Consider extending agent-lab's `bin/rclone-login` with `--remote`/`--scope` rather than a second script.
4. `sudo raspberry-pi/backup/setup`, then `pi-backup init` and the first `pi-backup run`.

### Proving it works

- `pi-backup run --dry-run`: what and how much.
- Restore drill on this Pi into a scratch home: set **both** `HOME` and `HERMES_HOME` to scratch dirs (import writes
  profile wrappers to `~/.local/bin` and `_external/` to the home), gateway disabled; then `hermes status` there.
- labvault drill: restore the system repo to scratch and check one credential decrypts (`web auth login test-creds`).
- Full drill when `pi2` arrives, before it becomes a worker: restore the main Pi's repos there with the gateway off and
  `TELEGRAM_*` removed; check; then wipe `~/.hermes` and set it up as a worker.

### Surfacing

- pi-status: Backup tile (last run, age, ok/fail, size) from `last.json` (user) and a root-written status file.
- `pi-checkup`: warn if the last good backup is older than 36 h or the last `restic check` failed.
- `upd`: run `pi-backup status`; re-run `setup` if the root-side files changed.

## Part B: more Pis

### Roles

| Role | Runs | Pis |
|---|---|---|
| `main` | everything today: Pi-hole, pi-status, websites/DreamBase, REI, mail, Hermes (front door, Telegram) | `raspberrypi` |
| `worker` | base system, Docker, Tailscale, Hermes (no Telegram, `api_server` on), second Pi-hole (on `pi2`) | `pi2`, later `pi3` |

`restore.sh --role main|worker` picks which steps run (default `main`, so today's behavior is unchanged), remembered
in `~/.config/pi-role` so `upd` and `save.sh` know it. Snapshot layout (one folder per Pi, or a shared worker
snapshot): decide when implementing.

### Bringing up `pi2`

1. Imager: Raspberry Pi OS 64-bit, hostname `pi2`, user `guy`, SSH key (README section 1).
2. `bootstrap.sh` with `--role worker`.
3. `sudo tailscale up --ssh`; name it `pi2`. DHCP reservation on the router.
4. Hermes: new Anthropic API key for `pi2`; no Telegram; in `~/.hermes/.env`: `API_SERVER_ENABLED=true`,
   `API_SERVER_KEY=<random>`, `API_SERVER_HOST=<pi2's tailnet IP>` (default is 127.0.0.1:8642; not 0.0.0.0, which
   would open it to the LAN).
5. `pi-backup init` for `pi2`'s own repos; `sudo backup/setup`; timers on.

### Agents across Pis

- One Hermes gateway per Pi. Only `raspberrypi` has Telegram.
- Main: `hermes peer add pi2 --url http://<pi2 tailnet IP>:8642 --key <API_SERVER_KEY>`.
- Handing off work: an agent-lab command (e.g. `tools/bin/peer-run pi2 "<task>"`) wrapping
  `hermes peer run --idempotency-key …` and `peer status`, plus a shared skill telling the main agent when to use it.
  Peer targets inside `message_agent` only exist in Bot Mode Bot Chats, which the Telegram front door doesn't use.
- Each Pi has its own kanban board and dispatcher (default settings).
- Specialist agents are Hermes profiles on whichever Pi has room (8 GB each; one heavy agent per Pi).
- Shared skills: `agent-lab` is cloned on every Pi; `upd` pulls it, `bin/lab skills` installs it.
- Watch API rate limits once several agents run at once.

Read in the installed Hermes before wiring: `reference/cli-commands.md` (`hermes peer`),
`reference/environment-variables.md` (`API_SERVER_*`), `user-guide/features/kanban.md`, `user-guide/profiles.md`,
`user-guide/bot-mode.md`.

### Docker

- Compose files in git (one folder per stack, like `services/pihole/`).
- From main: `docker context create pi2 --docker host=ssh://guy@pi2`. Tailscale SSH's `check` mode asks for a browser
  re-login now and then, which breaks unattended use: add an `accept` rule for main → workers in the tailnet policy,
  or use plain OpenSSH keys.

### DNS

- `pi2` runs Pi-hole from the same `services/pihole/` compose file; keep lists in step (Teleporter import, or
  nebula-sync later).
- Router DHCP hands out both Pis' LAN IPs as DNS.

## Build order

| Step | What | Depends on | Status |
|---|---|---|---|
| 0 | **Rewrite the "not backed up, by choice" rules** so agents don't follow the old policy: this `README.md` (top and section 3 `agents` row), `machine-setup/CLAUDE.md` (Raspberry Pi section), `~/.claude/CLAUDE.md` (`me` section), `agent-lab/me.md`, the `pi-rebuild` memory note. New rule: no secrets in git; everything else in the encrypted restic backup | | ✅ 2026-11-06 (also agent-lab `CLAUDE.md`, `agents.md`, memory notes `rei-on-pi`, `me-data-store`) |
| 1 | Part A on `raspberrypi`: scripts, `setup`, units, user steps, first backup | own OAuth client, passphrases (user) | ✅ set up 2026-11-06: both repos on Drive, timers 03:00 (user) / 03:30 (system), first backups and checks ok (~107 MB on Drive); restore drill into an empty home ok (hermes, signins, data) |
| 2 | Restore drills (scratch home, labvault) | 1 | |
| 3 | pi-status tile, pi-checkup warning, README section | 1 || ✅ code 2026-11-06: pi-status Overview Backup strip + attention items (`/api/backup`), `pi-checkup backup` domain, `upd` step, README "Nightly backup"; shows real data after the first run |
| 4 | `restore.sh --role` | | ✅ 2026-11-06 (worker skips `rei`, `mail`, DreamBase; `save.sh --push` refuses on a worker) |
| 5 | `pi2` up: full restore drill, then worker | 2, 4, hardware | |
| 6 | Hermes on `pi2`, `hermes peer`, `peer-run` command + skill | 5 | |
| 7 | Second Pi-hole, router DNS, Docker contexts | 5 | |
| 8 | Optional: Ansible if Pis drift; Portainer; pi-status multi-Pi view | | |

## Open questions (decided 2026-11-06)

- rclone: **Homebrew for `guy`; `setup` copies that static binary root-owned to `/usr/local/lib/pi-backup/rclone`**
  and records its version. `setup --check` (run by `upd` and `pi-checkup`) flags a stale copy. rei and agent-lab keep
  their Homebrew path.
- Lab Chromium profile: **copied (without caches, ~100 MB) only when Chromium isn't running**. The lab's shared
  browser (`lab-chromium`) runs all day, so a real run stops it for the copy (a few seconds; open tabs are lost, sign-ins
  kept) and starts it again with the unit's own command line and environment. Anything else using the profile (a
  `browser login` window) makes it skip that night, recorded in `last.json`; `pi-checkup` warns when the last copy is
  over 14 days old.
- DreamBase `photos/`: **skipped** (`photos_sync.py` re-fetches from the shared album; the album URL file is kept).
- Snapshot layout: **`snapshot/` stays the main Pi's**; a worker restores from it filtered by role, and `save.sh`
  refuses `--push` on a worker. Decide a per-worker folder in step 5 if they drift.
- Drive quota: checked 2026-11-06, 4.8 TiB free.
