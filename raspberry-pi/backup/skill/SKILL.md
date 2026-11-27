---
name: pi-backup
description: Use for Pi backup status, debugging, or adding tools.
---

# Pi backup (restic to Google Drive)

Two independent nightly jobs, code in `~/dev/machine-setup/raspberry-pi/backup/` (contract: `../MULTI-PI.md`, "Interfaces"):
- **user side** `pi-backup`: systemd *user* timer `pi-backup.timer` (~03:00), runs from the repo, repo `rclone:gdrive-backup:pi-backups/<host>/user`, state `~/.local/state/pi-backup/`.
- **system side** `pi-backup-system`: root *system* timer `pi-backup-system.timer` (~03:30), runs a root-owned copy in `/usr/local/lib/pi-backup/`, repo `.../system`, state `/var/lib/pi-backup/` (last.json is world-readable).

## Did it run? Any errors? (read-only, no sudo needed)
1. `~/dev/machine-setup/raspberry-pi/backup/pi-backup status` (exit 0 = OK; last run, last good, last weekly check, per-item status).
2. `cat /var/lib/pi-backup/last.json` for the system side (same schema).
3. Timers: `systemctl list-timers --all | grep backup` (system) and `systemctl --user list-timers --all` (user). Check LAST is last night; Persistent=true catch-up can hide a missed slot.
4. Logs: `journalctl --user -u pi-backup --since '7 days ago' --no-pager` and `journalctl -u pi-backup-system --no-pager`. The success line ("snapshot ...: +X added") is emitted by a child process with a different PID, so a PID filter or `-u` plus grep can make it look missing; read a `--since/--until` window around the run. If the user-side script has the run log, `pi-backup log [N]` shows `pi-backup.log` and `history.jsonl`.
5. Drive side: `export PATH=/home/linuxbrew/.linuxbrew/bin:$PATH RESTIC_PASSWORD_FILE=~/.config/pi-backup/restic-password RESTIC_REPOSITORY=rclone:gdrive-backup:pi-backups/$(hostname -s)/user; restic snapshots --compact`. rclone lives in linuxbrew, so restic fails with "rclone: executable file not found" without that PATH. `rclone lsd/size gdrive-backup:pi-backups` confirms the remote. guy cannot open the system repo (root-only password): rely on its journal and last.json.
6. Report per side: scheduled vs actual time, exit code, snapshot id, bytes, duration, last check result, anything odd. A recently installed setup has few nightly runs to judge by; say so.

Exit codes: 0 ok, 1 failed, 2 setup/usage, 3 Drive unreachable, 4 finished but an item (e.g. chromium profile) was incomplete.

## Side effects to mention
The user run stops and restarts `lab-chromium` (the shared agent browser) for a few seconds to copy its profile; a real or test run during browser use interrupts it.

## Editing the scripts (logging, behavior)
- The system job must never log file names (guy can read the system journal): no `--verbose`, parse restic JSON, blank paths in error text. Logging added there is counts, phases, exit codes, timings only.
- Editing the repo does not change the system job: the timer runs the root copy. Deploy needs the user to run `sudo raspberry-pi/backup/setup`; the agent shell blocks `sudo`, so hand that step over explicitly.
- Update the contract in `MULTI-PI.md` with the code when adding state files.
- Logging pattern on the user side: `start_log` (tee stdout+stderr to the journal and a timestamped `$state/pi-backup.log`, rotate at 1 MB x3), a `phase` variable set at each stage, `log_end` called from the EXIT trap for the final line and a `history.jsonl` row (last.json only keeps the latest run), keep restic stderr warnings even on success. Real runs only, not `--dry-run`.
- The user-side timer runs the script straight from the repo checkout, so an uncommitted edit is live at the next ~03:00 run. After editing, show `git diff` when asked, offer a commit (message like `pi-backup: <what>`), and push only when the user says so (preferably after an observed good run).
- Once the user says to stop testing and watch the next nightly run, stop: finish docs/skill notes only, then end with a short report (did it run, what changed, what is not done such as system-side deploy or alerting). Next-day check = `pi-backup log` + `history.jsonl` + journal window, then decide whether more logging is needed.
- Adding a CLI/tool (its install, settings, sign-in, data) to backup and restore: see `references/adding-a-tool.md` (three places to edit, cheap verification, what to leave out of the commit).
- Work on a branch off `main`, never on `main` itself; the live timer follows whatever branch the checkout is on, so a branch with new includes goes live at the next run, which is the point. Tell the user which branch is checked out and that merge/push waits for their yes.
- Test against a throwaway repo with env overrides (`PI_BACKUP_REPO PI_BACKUP_PASSWORD_FILE PI_BACKUP_STATE_DIR`), never the live Drive repo (create it first with `restic init -r <dir> --password-file <pw>`); `bash -n` first. Check both a good run and a failing one (point `PI_BACKUP_REPO` at a nonexistent dir: expect exit 2 and `FAILED ... during phase "setup"` plus a history row); a full run takes ~25 s. Staging still restarts lab-chromium, so ask first. Commands containing `rm -rf` raise an approval prompt that times out unanswered on Telegram: use a fresh uniquely-named scratch dir instead of clearing one, and ask the user before running anything that needs approval.
