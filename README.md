# Machine Setup

Setup, backup and restore scripts for my machines, plus a few utilities.

| Directory | For | What it does |
|---|---|---|
| repo root (`*.zsh`) | macOS | Back up and restore Claude Code / Antigravity settings and dotfiles, set up a new Mac with Homebrew, and a Google Voice launcher |
| [`raspberry-pi/`](raspberry-pi/README.md) | Raspberry Pi OS / Debian | Snapshot and restore the whole Pi setup (shell config, apt and Homebrew packages, Tailscale, app settings), plus the Hermes / OpenClaw launchers and the [`pi-status`](raspberry-pi/pi-status/README.md) status web page |

## Raspberry Pi

`raspberry-pi/save.sh` snapshots this Pi's settings into `raspberry-pi/snapshot/` (text only: no secrets, no files over 100 KB). The Pi's `upd` command runs it after every update and pushes the result here. `raspberry-pi/restore.sh` rebuilds a fresh image from that snapshot.

```bash
# On a new Pi / fresh image
git clone https://github.com/guyguy2/machine-setup ~/dev/machine-setup
cd ~/dev/machine-setup/raspberry-pi
./restore.sh --dry-run     # preview
./restore.sh               # apt, Tailscale, Homebrew, Oh My Zsh, dotfiles, status page, systemd
```

The agent launchers live in `raspberry-pi/bin/` and the status web page in `raspberry-pi/pi-status/`; `~/dev/scripts` and `~/dev/pi-status` are symlinks to them. See [raspberry-pi/README.md](raspberry-pi/README.md) for the steps, options and what is (and is not) backed up.

## macOS scripts

- **backup-ai-settings.zsh** - Backs up Claude Code and Gemini Antigravity CLI settings to a timestamped zip file
- **restore-ai-settings.zsh** - Restores Claude Code and Gemini Antigravity CLI settings from a backup zip, fixing absolute home directory paths
- **backup-dev-environment.zsh** - Orchestrates a comprehensive backup of settings and dotfiles (.zshrc, .gitconfig, Homebrew packages, etc.)
- **google-voice-call.zsh** - Enhanced Google Voice call launcher with contacts and call history
- **install-homebrew-new-mac.zsh** - Comprehensive Mac setup script with Homebrew installation and app configuration

Each macOS script is executable and includes a `--help` option for detailed usage information:

```bash
# Backup Claude Code and Gemini Antigravity settings
./backup-ai-settings.zsh

# Restore settings and fix paths
./restore-ai-settings.zsh data/ai-settings-TIMESTAMP.zip

# Backup entire development environment (settings + dotfiles)
./backup-dev-environment.zsh

# Make a Google Voice call
./google-voice-call.zsh 8558701311

# Set up a new Mac with Homebrew
./install-homebrew-new-mac.zsh
```

Make sure scripts have execution permissions: `chmod +x script-name.zsh`

## Requirements

- macOS scripts: macOS and Zsh (the macOS default). Individual scripts may also need:
  - Homebrew (`install-homebrew-new-mac.zsh` installs it automatically)
  - Chrome browser (`google-voice-call.zsh`)
  - Claude Code or Gemini Antigravity CLI installed (`backup-ai-settings.zsh` / `restore-ai-settings.zsh`)
- `raspberry-pi/` scripts: Raspberry Pi OS / Debian (arm64). `save.sh` and `restore.sh` are bash, so they run on a fresh image; the agent launchers use zsh.

## License

MIT
