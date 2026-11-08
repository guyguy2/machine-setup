# checkup: scan the Pi for anything that needs attention

| File | What it is | Linked from |
|---|---|---|
| `pi-checkup` | Read-only bash script with all the checks. Prints `OK` / `INFO` / `WARN … [key]` and exits 1 on any warning. | `~/.local/bin/pi-checkup` (on PATH) |
| `skill/SKILL.md` | Claude Code skill: runs the script, sends one read-only agent per domain with warnings, merges a report. | `~/.claude/skills/pi-checkup` |

`restore.sh` (links step) creates both links on a rebuild.

## Which to run when

- **Quick look, no AI (about 20s, free):** `pi-checkup` in a terminal. Only problems: `pi-checkup --warn-only`.
  One area: `pi-checkup security` (domains: `pi-checkup --list`). Offline or in a hurry: `--no-fetch`.
- **Full scan with explanations and fixes:** in Claude Code, type `/pi-checkup` (or ask "scan the Pi"). It costs
  agent tokens only for domains that have warnings.
- Good times to run it: after `upd`, after setting up or removing a service, before a rebuild/backup, or when
  something feels off.

## Domains

health (load, temperature, throttling, RAM/swap, disks, kernel vs reboot, OOM, SD errors, unclean shutdown, journal), services
(always-on units and timers, recurring failures, tailnet routes, websites and their certificates), docker (containers, compose
services, unpinned `:latest` images, unused images, Pi-hole versions and image tag), repos (git state of `~/dev`, untracked folders, broken links, bogus
lockfile entries), updates (apt, bootloader, brew, npm, uv, OpenClaw, Hermes, last `upd`), security (LAN
listeners, ad-hoc servers, rpcbind, firewall, sshd, auto-updates, credential permissions, dead tailnet devices),
agents (Hermes/OpenClaw dashboards up and answering, the Hermes Telegram gateway, shared skills, gws/gh/Claude logins), backup (`pi-backup status` for both
restic repos, timers enabled, root-side copies match the repo, lab Chromium profile copied in the last 14 days),
drift (snapshot vs this machine, links `restore.sh` would make,
files `save.sh` doesn't back up, PATH duplicates, Brewfile).

## Changing it

Add a check as `warn <domain>.<name> "message that says the fix"` (or `ok`/`info`) in `check_<domain>`. Expected
units (`MAIN_ONLY` ones are skipped on a worker Pi), agents (their ports are read from their units), LAN ports,
websites and secret files are arrays at the top. A warning you've decided is fine goes in
`ACCEPTED` by its key. Put parsing in a small helper function that takes its input as an argument or on stdin, and
test it in `tests/test_pi_checkup.py` (it sources the script, which then defines the functions without running any
check). Then `shellcheck -S warning pi-checkup`, `uvx pytest tests` (from this folder) and commit.
