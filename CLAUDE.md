# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a collection of utility scripts for macOS automation and development tasks. The scripts are written in Bash and Zsh, focusing on system setup, Claude Code backup, and communication tools.

## Core Scripts

### backup-dev-environment.zsh
Orchestrates comprehensive backup of development environment settings including Claude Code configuration and dotfiles.

**Key features:**
- Orchestrates backup of Claude Code settings and essential dotfiles in one operation
- Creates a timestamped directory containing all backup files
- Backs up .zshrc, .gitconfig, and .ssh/config alongside Claude settings
- Supports `--skip-claude` and `--skip-dotfiles` flags for selective backups
- Verbose mode for detailed output
- Structured exit codes (0=success, 1=general error, 2=missing files, 3=backup failed)

**What gets backed up:**
- Claude Code settings (via backup-claude-settings.zsh)
- `~/.zshrc` - Shell configuration
- `~/.gitconfig` - Git configuration
- `~/.ssh/config` - SSH configuration (if present)

**Usage:**
```bash
./backup-dev-environment.zsh                    # Create full backup
./backup-dev-environment.zsh -o my-backup       # Custom directory name
./backup-dev-environment.zsh --verbose          # Show detailed output
./backup-dev-environment.zsh --skip-dotfiles    # Only backup Claude settings
```

**Directory structure created:**
```
dev-backup-20251116-120000/
├── claude-settings-20251116-120000.zip
├── .zshrc
├── .gitconfig
└── .ssh-config (if ~/.ssh/config exists)
```

**Restoring from backup:**
```bash
# Extract Claude settings
unzip dev-backup-*/claude-settings-*.zip -d ~

# Restore dotfiles
cp dev-backup-*/.zshrc ~
cp dev-backup-*/.gitconfig ~
cp dev-backup-*/.ssh-config ~/.ssh/config  # if present

# Restart terminal and Claude Code
```

### backup-claude-settings.zsh
Backs up essential Claude Code settings to a timestamped zip file for easy restoration on a new Mac.

**Note:** This script is also used by `backup-dev-environment.zsh` for orchestrated backups.

**Key features:**
- Backs up settings.json, .claude.json, statusline scripts, custom agents, and slash commands
- Creates timestamped zip files (e.g., claude-settings-20251114-211800.zip)
- Supports custom output filenames with `--output` option
- Verbose mode for detailed output
- Structured exit codes (0=success, 1=general error, 2=missing settings, 3=zip creation failed)

**Files backed up:**
- `~/.claude/settings.json` - Hooks, statusline, preferences
- `~/.claude/CLAUDE.md` - Global instructions for Claude Code
- `~/.claude.json` - Main config file with MCP servers
- `~/.claude/statusline-*.sh` - Custom statusline scripts
- `~/.claude/commands/` - Personal slash commands (if present)
- `~/.claude/skills/` - Personal skills (if present)
- `~/.claude/agents/` - Custom agents (if present)
- `~/.claude/plugins/` - Installed plugins and marketplaces (if present)

**Usage:**
```bash
./backup-claude-settings.zsh                    # Create timestamped backup
./backup-claude-settings.zsh -o my-backup.zip   # Custom filename
./backup-claude-settings.zsh --verbose          # Show detailed output
```

**Restoring from backup:**
```bash
unzip claude-settings-20251114-211800.zip -d ~
# Restart Claude Code to load restored settings
```

### install-homebrew-new-mac.zsh
Comprehensive Mac setup script that automates Homebrew installation and configuration of development environment.

**Key features:**
- Modular package organization (development core tools, CLI utilities, containers, network tools, GUI apps)
- Supports command-line options: `--verbose`, `--dry-run`, `--skip-homebrew`, `--skip-terminal`, `--skip-cli-tools`, `--skip-gui-apps`
- Structured exit codes (0=success, 1=general error, 2=missing dependency, 3=network error, 4=install failed, 5=disk space error)
- Progress indicators and comprehensive validation

**Package groups:**
- DEV_CORE_TOOLS: git, gh, node, python, uv, bun
- DEV_CLI_UTILS: eza, ripgrep, tree, ffmpeg
- CONTAINER_TOOLS: docker
- NETWORK_TOOLS: telnet
- TERMINAL_APPS: warp
- DEV_GUI_APPS: visual-studio-code, docker-desktop, jetbrains-toolbox, opencode, claude
- PRODUCTIVITY_APPS: rectangle, todoist, dropbox, macwhisper, iina
- COMMUNICATION_APPS: whatsapp, zoom, google-chrome

**Usage:**
```bash
./install-homebrew-new-mac.zsh                      # Install everything
./install-homebrew-new-mac.zsh --dry-run            # Preview changes
./install-homebrew-new-mac.zsh --skip-gui-apps      # Skip GUI applications
```

### google-voice-call.zsh
Enhanced Google Voice call launcher with multi-browser support, contacts, and call history.

**Key features:**
- Multi-browser support (Chrome, Safari, Firefox, Edge)
- Contact management system (`~/.google-voice-contacts.txt`)
- Call history tracking (`~/.google-voice-history.txt`)
- Phone number format validation and normalization
- Configuration file support (`~/.google-voice-call.conf`)

**Phone number formats supported:**
- 10-digit US: `8558701311`
- International: `+44-20-7946-0958`
- Formatted: `(855) 870-1311`, `855.870.1311`

**Usage:**
```bash
./google-voice-call.zsh 8558701311                          # Call number
./google-voice-call.zsh -b safari 8558701311                # Use Safari
./google-voice-call.zsh --add-contact "Pizza Place" 8558701311  # Save contact
./google-voice-call.zsh "Pizza Place"                       # Call saved contact
./google-voice-call.zsh --history                           # View call history
./google-voice-call.zsh --list-contacts                     # List contacts
```

## Development Environment

### Shell Scripts
- All shell scripts use `set -euo pipefail` for strict error handling
- Consistent exit code patterns across scripts
- Logging functions: `log_info()`, `log_verbose()`, `log_error()`, `log_warning()`
- Command-line parsing with GNU-style options (`--help`, `--verbose`, `--dry-run`)

### Shell Configuration (.zshrc)
Personal Zsh configuration file with oh-my-zsh setup and custom aliases.

**Key configuration:**
- oh-my-zsh framework with "eastwood" theme
- Git plugin enabled for enhanced git command completion
- Python 3.13 from Homebrew (`/opt/homebrew/opt/python@3.13/bin/python3.13`)
- Node.js 16 from Homebrew
- Android SDK platform-tools in PATH
- JAVA_HOME points to Android Studio's JBR

**Useful aliases:**
- `c` - clear terminal
- `ni` - npm install
- `ns` - npm start
- `python` - Python 3.13 from Homebrew
- `py` - python3
- `gacp` - git add, commit with "progress" message, and push
- `cld` - claude CLI shortcut
- `clda` - claude --dangerously-skip-permissions
- `upd` - Update Homebrew packages and Gemini CLI
- `gemini` - Gemini CLI with auto-yes flag

**Integrations:**
- Docker CLI completions
- Kiro terminal shell integration
- Local bin directory (`~/.local/bin`) in PATH

## Common Development Patterns

### Exit Codes
Scripts follow a consistent exit code pattern:
- 0: Success
- 1: General error
- 2: Invalid input/missing dependency
- 3: Network error
- 4: Installation/update failed
- 5: Disk space error (install script only)

### Logging Standards
All enhanced scripts use standardized logging:
- `log_info()` - General information messages
- `log_verbose()` - Debug output (enabled with `-v` or `--verbose`)
- `log_error()` - Error messages (stderr)
- `log_warning()` - Warning messages (stderr)
- `log_success()` - Success messages (used in backup-claude-settings.zsh)

## Testing Scripts

To test scripts safely:
1. Use `--dry-run` flag where available to preview actions
2. Use `--verbose` for detailed execution logging
3. Test with `--help` to verify command-line interface

## macOS-Specific Considerations

- Scripts are tailored for macOS environment
- Apple Silicon (M1/M2) vs Intel chip detection for Homebrew paths
- Uses `open` command for launching applications
- Zsh is the default shell on macOS (all .zsh scripts)

## Additional Resources

### Claude Code Plugin Marketplaces

#### wshobson/agents
Production-ready marketplace of 63 focused plugins containing 85 specialized AI agents, 47 agent skills, and 44 development tools for intelligent automation and multi-agent orchestration.

- GitHub: https://github.com/wshobson/agents
- Offers domain expertise across 23 categories (development, infrastructure, security, AI/ML, business operations)
- Emphasizes modularity and token efficiency with granular, focused plugins
- Agents strategically assigned to Claude Haiku (fast tasks) or Claude Sonnet (complex reasoning)

#### jeremylongshore/claude-code-plugins-plus
Comprehensive marketplace with 253 production-ready Claude Code plugins for automation, development, and AI workflows.

- GitHub: https://github.com/jeremylongshore/claude-code-plugins-plus
- Web: https://claudecodeplugins.io
- 185 plugins with Agent Skills v1.2.0 support
- 100% compliant with Anthropic's 2025 Skills schema
- Categories include DevOps, Security, AI/ML, Database, Testing, and Business Tools
- One-command installation: `/plugin install [plugin-name]@claude-code-plugins-plus`
- Tool permission system and comprehensive activation guides
