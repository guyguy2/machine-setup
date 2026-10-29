---
name: pi-checkup
description: Scan this Raspberry Pi for anything that needs attention (CPU, memory, disk, temperature, failed or missing services, websites, Docker, git repos, pending updates, security exposure, the Hermes/OpenClaw agents and their logins, drift from the machine-setup snapshot) and report system stats, what's running and what to do. Runs the deterministic `pi-checkup` script, then sends one read-only agent per domain that has warnings. Use when the user asks to scan/check the Pi, for a status update or health check, "anything weird", "what's running", "any drift", "what needs updating", or runs /pi-checkup.
---

# Pi checkup

The checks are code: `pi-checkup` (on PATH via `~/.local/bin`; source and this skill live in `~/dev/machine-setup/raspberry-pi/checkup/`).
Agents only investigate what it flags. Everything here is read-only. Fix nothing without the user's go-ahead.

## 1. Run the script

```sh
pi-checkup > <scratchpad>/checkup.txt 2>&1; echo "exit $?"
```

- Takes about 20s. `--no-fetch` skips `git fetch`; pass domain names to run only some (`pi-checkup --list`).
- Lines are `OK`, `INFO` or `WARN <message> [key]`. The last line is `ALL OK` (exit 0) or
  `WARNINGS health=1 repos=3 ...` (exit 1): those are the domains with warnings.
- Domains: health, services (units, timers, tailnet routes, websites), docker, repos, updates, security, agents
  (Hermes, OpenClaw, shared skills, gws/gh/Claude logins), drift (snapshot and backup coverage).

## 2. One agent per domain with warnings

Send all of them in one message so they run in parallel (`general-purpose` agents). Leave out a domain only when
every WARN in it already states its own fix and there's nothing to find out (e.g. just `updates.brew`); say so in
the report. With `ALL OK`, send none.

Prompt for each (fill in the domain and paste its WARN lines verbatim):

> Read-only investigation of the `<domain>` warnings from `pi-checkup` on this Raspberry Pi 5
> (Raspberry Pi OS, user guy, passwordless sudo). Do NOT change anything: no edits, restarts, kills, installs,
> commits or messages. Only reads and status/--check/--dry-run commands. Never print secret values.
> Re-run `pi-checkup --no-fetch <domain>` first to see the domain's full output.
> Warnings: <WARN lines>
> For each warning: the cause, the evidence (command + key output), whether it looks intentional (check
> `~/dev/machine-setup/raspberry-pi/README.md`, `~/dev/agent-lab` docs, unit comments, git log), the exact fix
> command(s), and the risk of the fix. Then list anything else wrong in this domain that the script missed, noting
> which of those a script could check. Under 300 words, most important first.

Domain hints to add to the prompt: **agents**: load the `openclaw` and `hermes` skills first. Agents run one at a
time (started from pi-status), so a stopped agent is normal. **docker**: load the `pihole` skill. **security**: the
LAN ports meant to be open are listed at the top of the script. **drift/repos**: `save.sh` and `restore.sh` are in
`~/dev/machine-setup/raspberry-pi`. Uncommitted work there may belong to another session, so don't suggest
discarding it.

## 3. Report

Merge the script output and the agents' findings into one terminal report:
1. **System stats**: a small table from the health OK lines (uptime/load, temp/throttling, RAM/swap, disks, kernel).
2. **What's running / what should be**: services, websites, containers, agents (which one is on), and anything
   expected but down.
3. **Findings, ranked**: severity, what's wrong, the fix. Group trivial ones at the end.
4. **Script gaps**: mechanical things the agents found that `pi-checkup` doesn't check yet. Offer to add them.

Then offer to apply fixes, and ask before anything that kills processes, changes security settings or touches
another session's uncommitted work.

## Changing the script

- A new check goes in the domain's `check_<domain>` function as `warn <domain>.<name> "message with the fix"`, or as
  `ok`/`info`. A new domain needs a `check_<x>` function and an entry in `DOMAINS`. Expected units, LAN ports,
  websites and secret files are arrays at the top.
- When the user says a warning is fine as it is, add its `[key]` to `ACCEPTED` (it then shows as INFO). Don't just
  remember it.
- Afterwards: `shellcheck -S warning ~/dev/machine-setup/raspberry-pi/checkup/pi-checkup`, run the domain, and commit
  in machine-setup.
