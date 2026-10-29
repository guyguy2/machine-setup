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

health (load, temperature, throttling, RAM/swap, disks, kernel vs reboot, OOM, SD errors, journal), services
(units, recurring failures, tailnet routes, websites and their certificates), docker (containers, compose
services, unused images, Pi-hole versions), repos (git state of `~/dev`, untracked folders, broken links, bogus
lockfile entries), updates (apt, bootloader, brew, npm, uv, OpenClaw, Hermes, last `upd`), security (LAN
listeners, ad-hoc servers, rpcbind, firewall, sshd, auto-updates, credential permissions, dead tailnet devices),
agents (Hermes/OpenClaw up and answering, shared skills, gws/gh/Claude logins), drift (snapshot vs this machine,
files `save.sh` doesn't back up, PATH duplicates, Brewfile).

## Changing it

Add a check as `warn <domain>.<name> "message that says the fix"` (or `ok`/`info`) in `check_<domain>`. Expected
units, LAN ports, websites and secret files are arrays at the top. A warning you've decided is fine goes in
`ACCEPTED` by its key. Then `shellcheck -S warning pi-checkup` and commit.
