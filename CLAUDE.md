# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a collection of utility scripts for macOS automation and development tasks. The scripts are primarily written in Bash, Zsh, and Python, focusing on system setup, browser automation, and communication tools.

## Core Scripts

### install-homebrew-new-mac.sh
Comprehensive Mac setup script that automates Homebrew installation and configuration of development environment.

**Key features:**
- Modular package organization (development core tools, CLI utilities, containers, network tools, GUI apps)
- Supports command-line options: `--verbose`, `--dry-run`, `--skip-homebrew`, `--skip-terminal`, `--skip-cli-tools`, `--skip-gui-apps`
- Configuration file support via `--config FILE`
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
./install-homebrew-new-mac.sh                      # Install everything
./install-homebrew-new-mac.sh --dry-run            # Preview changes
./install-homebrew-new-mac.sh --skip-gui-apps      # Skip GUI applications
./install-homebrew-new-mac.sh --config setup.conf  # Use custom config
```

### walmart_add_to_cart.py
Browser automation script using Playwright to search for and add water to Walmart cart.

**Key architecture:**
- Uses Chrome remote debugging (port 9222) to connect to existing browser sessions
- Chrome 136+ requires non-default profile for debugging (uses `~/.walmart-chrome-debug`)
- Handles login detection and waits for user authentication
- Implements multiple selector strategies for robust element detection
- Prioritizes "Great Value water 24 count" in product search

**Requirements:**
```bash
pip install playwright
playwright install chromium
```

**Usage:**
```bash
./run_walmart.sh  # Uses uv to run with Playwright dependency
```

**Important notes:**
- Automatically launches Chrome with debugging if not already running
- Pauses for 60 seconds if user not logged into Walmart
- Saves debug screenshots to script directory on failures
- Keeps browser tab open after adding to cart for user review

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

### update-gemini-cli.sh
Version-aware updater for Google's Gemini CLI tool.

**Key features:**
- Semantic version comparison (major.minor.patch)
- Network connectivity validation
- Support for force updates and dry-run mode
- Verification of successful updates

**Usage:**
```bash
./update-gemini-cli.sh                    # Update if newer version available
./update-gemini-cli.sh --dry-run          # Preview update
./update-gemini-cli.sh --force --verbose  # Force update with details
```

## Development Environment

### Python Scripts
- Use Python 3.11+ (virtual environment in `.venv/`)
- Playwright for browser automation
- Uses `uv` for dependency management

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
- `upd` - Update Homebrew packages and Gemini CLI (uses update-gemini-cli.sh:112)
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

### Browser Automation Best Practices
When working with Playwright scripts:
1. Use remote debugging for Chrome (port 9222) to maintain user sessions
2. Implement multiple selector strategies for resilience
3. Take screenshots on failures for debugging
4. Handle login states gracefully with user prompts
5. Keep tabs open for user verification after operations

## Testing Scripts

To test scripts safely:
1. Use `--dry-run` flag where available to preview actions
2. Use `--verbose` for detailed execution logging
3. Test with `--help` to verify command-line interface

## macOS-Specific Considerations

- Scripts are tailored for macOS environment
- Apple Silicon (M1/M2) vs Intel chip detection for Homebrew paths
- Uses `open` command for launching applications
- AppleScript integration in some utilities (walmart_add_to_cart.sh)
