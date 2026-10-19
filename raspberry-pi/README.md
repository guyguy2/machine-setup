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
   Steps in order: apt-sources apt brew uv npm omzsh dotfiles links shell systemd.
3. Manual follow-ups (also printed at the end): `gh auth login`, `tailscale up`, log in to
   `claude`, run `~/dev/scripts/openhuman` and `~/dev/scripts/openclaw` once to self-install, recreate `~/.ssh` keys.

Existing files are never overwritten: they are moved to `~/.pi-restore-backup-<timestamp>/`.

## What is in snapshot/

| File | Contents |
|---|---|
| `dotfiles/` | `.zshrc` (aliases, `upd`), `.gitconfig`, `~/.config/{zellij,lxterminal,kanshi,wf-panel-pi}`, `mimeapps.list`, user systemd unit, Claude Code `CLAUDE.md`/`settings.json`/status line |
| `apt-manual.txt` | `apt-mark showmanual` |
| `apt-sources/` | third-party apt sources and their public keys (NodeSource, Tailscale) |
| `Brewfile` | Homebrew formulae, taps and casks (includes Claude Code) |
| `uv-tools.txt`, `npm-global.txt` | `uv tool` / `npm -g` installs |
| `systemd-*-enabled.txt` | enabled units. User units with a restored file are enabled; system-unit differences are only reported |
| `versions.txt` | OS and agent versions at save time (reference) |

`bin/` holds the launch wrappers for Hermes, OpenClaw and OpenHuman; each updates its tool on launch.
`~/dev/scripts` is a symlink to this `bin/` (created by the `links` step of `restore.sh`), so run the agents from there: `~/dev/scripts/hermes`, `~/dev/scripts/openclaw`, `~/dev/scripts/openhuman`.

To back up another file, add it to the `dotfiles` list at the top of `save.sh`.
