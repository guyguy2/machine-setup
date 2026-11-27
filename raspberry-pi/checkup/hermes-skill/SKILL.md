---
name: pi-checkup
description: "Scan this Raspberry Pi with pi-checkup for health and drift."
---

# Pi checkup

The checks are deterministic code: `pi-checkup` (on PATH via `~/.local/bin`; source and tests live in `~/dev/machine-setup/raspberry-pi/checkup/`). Agents only investigate what it flags. Everything here is read-only — fix nothing without the user's go-ahead.

## 1. Run the script

```sh
pi-checkup > /tmp/pi-checkup.txt 2>&1; echo "exit $?"
```

- Takes ~30s. `--no-fetch` skips `git fetch` and package audits; pass domain names to run only some (`pi-checkup --list`).
- Output lines are `OK`, `INFO`, or `WARN <message> [key]`. Final line is `ALL OK` (exit 0) or `WARNINGS health=1 repos=3 ...` (exit 1).
- Domains: `health`, `services`, `docker`, `repos`, `updates`, `packages`, `security`, `agents`, `backup`, `drift`.

## 2. One subagent per domain with warnings

Use `delegate_task(tasks=[...])` in one batch so warning domains run in parallel. Skip a domain only when every `WARN` in it already states its own trivial fix (e.g. just `updates.brew`); say so in the report. With `ALL OK`, spawn no subagents.

Prompt template for each warning domain:

> Read-only investigation of the `<domain>` warnings from `pi-checkup` on this Raspberry Pi 5 (Raspberry Pi OS, user guy). Do NOT change anything: no edits, restarts, kills, installs, commits, or messages. Never use `sudo` (blocked by `approvals.deny`) and never print secret values.
> Re-run `pi-checkup --no-fetch <domain>` first to see the domain's full output.
> Warnings: <WARN lines verbatim>
> For each warning: state the cause, evidence (command + key output), whether it looks intentional (check `~/dev/machine-setup/raspberry-pi/README.md`, `~/dev/agent-lab` docs, unit comments, git log), exact fix command(s), and risk. Then note anything else wrong in this domain that the script missed (and whether code could check it). Under 300 words, most important first.

Domain hints to include:
- **agents**: note OpenClaw is on hold (`~/dev/agent-lab/on-hold`), so a stopped OpenClaw unit is intentional.
- **docker**: load the `pihole` skill.
- **security**: expected open LAN ports are listed at the top of `~/dev/machine-setup/raspberry-pi/checkup/pi-checkup`.
- **backup**: load the `pi-backup` skill and read `~/dev/machine-setup/raspberry-pi/MULTI-PI.md` (Interfaces); never run `pi-backup run`/`check`/`setup` (only `status`).
- **drift/repos**: `save.sh` and `restore.sh` are in `~/dev/machine-setup/raspberry-pi`. Uncommitted work may belong to another session; never suggest discarding it.

## 3. Report

Merge the script output and subagent findings into one concise report:
1. **System stats**: compact table from `health` OK lines (uptime/load, temp/throttling, RAM/swap, disks, kernel).
2. **What's running / expected**: services, websites, containers, active agent (`hermes-gateway.service`), anything expected down.
3. **Findings, ranked**: severity, cause, fix (group trivial ones at the end).
4. **Script gaps**: mechanical checks `pi-checkup` missed; offer to add them.

Ask before applying any fixes.

## Changing the script

- Add checks inside `check_<domain>` as `warn <domain>.<name> "message with the fix"`, `ok`, or `info`.
- Accepted warnings go in `ACCEPTED` in `pi-checkup` (renders as `INFO`).
- Verify edits with `shellcheck -S warning ~/dev/machine-setup/raspberry-pi/checkup/pi-checkup`, run the domain, and run pytest in `~/dev/machine-setup/raspberry-pi/checkup/`.
