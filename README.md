# Scripts

Setup, backup and restore scripts for my machines (Mac and Raspberry Pi), plus a few utilities.

## Contents

- **raspberry-pi/** - Back up and restore a Raspberry Pi's setup (zshrc, apt/Homebrew packages, app config) with `save.sh` and `restore.sh`; also the Hermes/OpenClaw/OpenHuman launchers. See [raspberry-pi/README.md](raspberry-pi/README.md)
- **backup-ai-settings.zsh** - Backs up Claude Code and Gemini Antigravity CLI settings to a timestamped zip file
- **restore-ai-settings.zsh** - Restores Claude Code and Gemini Antigravity CLI settings from a backup zip, fixing absolute home directory paths
- **backup-dev-environment.zsh** - Orchestrates comprehensive backup of settings and dotfiles (.zshrc, .gitconfig, Homebrew packages, etc.)
- **google-voice-call.zsh** - Enhanced Google Voice call launcher with contacts and call history
- **install-homebrew-new-mac.zsh** - Comprehensive Mac setup script with Homebrew installation and app configuration

## Usage

Each script is executable and includes a `--help` option for detailed usage information:

```bash
./script-name.sh --help
```

Example usage:

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

Make sure scripts have execution permissions:

```bash
chmod +x script-name.sh
```

## Requirements

- macOS for the scripts at the repo root (tailored for Mac); Raspberry Pi OS / Debian for `raspberry-pi/` (bash)
- Zsh shell (default on macOS)
- Individual scripts may require:
  - Homebrew (install-homebrew-new-mac.zsh installs it automatically)
  - Chrome browser (google-voice-call.zsh)
  - Claude Code or Gemini Antigravity CLI installed (backup-ai-settings.zsh / restore-ai-settings.zsh)

## License

MIT
