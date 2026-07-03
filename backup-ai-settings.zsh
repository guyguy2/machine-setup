#!/usr/bin/env zsh

# backup-ai-settings.zsh
# Backs up Claude Code and Gemini Antigravity settings to a timestamped zip file

set -euo pipefail

# Logging functions
log_info() {
    echo "[INFO] $*"
}

log_error() {
    echo "[ERROR] $*" >&2
}

log_success() {
    echo "[SUCCESS] $*"
}

# Show help message
show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Backs up Claude Code and Gemini Antigravity CLI global settings to a zip file in the data/ directory.

Backs up essential settings for Claude Code and Gemini Antigravity on a new Mac:
  Claude Code:
    - ~/.claude/settings.json     (hooks, statusline, preferences)
    - ~/.claude/CLAUDE.md         (global instructions for Claude Code)
    - ~/.claude/statusline-*.sh   (custom statusline scripts)
    - ~/.claude/commands/         (personal slash commands, if present)
    - ~/.claude/skills/           (personal skills, if present)
    - ~/.claude/agents/           (custom agents, if present)
    - ~/.claude/plugins/          (installed plugins and marketplaces, if present)
    - ~/.claude.json              (main config file - MCP servers, settings)

  Gemini Antigravity CLI:
    - ~/.gemini/antigravity-cli/settings.json     (main configuration file)
    - ~/.gemini/antigravity-cli/keybindings.json  (custom shortcut keybindings)
    - ~/.gemini/antigravity-cli/bin/              (custom scripts, including statusline.py)
    - ~/.gemini/antigravity-cli/commands/         (personal slash commands, if present)
    - ~/.gemini/antigravity-cli/skills/           (personal skills, if present)
    - ~/.gemini/antigravity-cli/agents/           (custom agents, if present)
    - ~/.gemini/antigravity-cli/plugins/          (installed plugins, if present)

Options:
  -o, --output FILE     Custom output filename in current directory (default: data/ai-settings-TIMESTAMP.zip)
  -v, --verbose         Verbose output
  -h, --help            Show this help message

Examples:
  $(basename "$0")                                   # Create timestamped backup in data/
  $(basename "$0") -o my-ai-backup.zip               # Custom filename in current directory
  $(basename "$0") --verbose                         # Show detailed output

Restoring from backup:
  To restore settings from a backup zip file on a new Mac:

  1. Extract the backup to your home directory:
     unzip data/ai-settings-20260703-120000.zip -d ~

  2. Verify the files were extracted:
     ls -la ~/.claude/
     ls -la ~/.gemini/antigravity-cli/

  3. Restart the respective CLI tools or terminal to load the restored settings.

  Note: The zip file contains the directory structures with correct paths,
        so extracting to ~ will place everything in the right location.

Exit codes:
  0 - Success
  1 - General error
  2 - Missing settings (neither Claude nor Antigravity settings found)
  3 - Zip creation failed

EOF
}

# Parse command-line arguments
VERBOSE=false
OUTPUT_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Function for verbose logging
log_verbose() {
    if [[ "$VERBOSE" == true ]]; then
        echo "[VERBOSE] $*"
    fi
}

# Define paths to essential Claude Code settings
CLAUDE_SETTINGS="$HOME/.claude/settings.json"
CLAUDE_MD="$HOME/.claude/CLAUDE.md"
CLAUDE_JSON="$HOME/.claude.json"
CLAUDE_DIR="$HOME/.claude"

# Define paths to essential Antigravity settings
ANTIGRAVITY_SETTINGS="$HOME/.gemini/antigravity-cli/settings.json"
ANTIGRAVITY_KEYBINDINGS="$HOME/.gemini/antigravity-cli/keybindings.json"
ANTIGRAVITY_DIR="$HOME/.gemini/antigravity-cli"

# Check if any settings exist
FOUND_SETTINGS=false

# Check Claude
if [[ -f "$CLAUDE_SETTINGS" ]]; then
    log_verbose "Found Claude settings: $CLAUDE_SETTINGS"
    FOUND_SETTINGS=true
fi
if [[ -f "$CLAUDE_MD" ]]; then
    log_verbose "Found global CLAUDE.md: $CLAUDE_MD"
    FOUND_SETTINGS=true
fi
if [[ -f "$CLAUDE_JSON" ]]; then
    log_verbose "Found Claude config: $CLAUDE_JSON"
    FOUND_SETTINGS=true
fi

# Check Antigravity
if [[ -f "$ANTIGRAVITY_SETTINGS" ]]; then
    log_verbose "Found Antigravity settings: $ANTIGRAVITY_SETTINGS"
    FOUND_SETTINGS=true
fi
if [[ -f "$ANTIGRAVITY_KEYBINDINGS" ]]; then
    log_verbose "Found Antigravity keybindings: $ANTIGRAVITY_KEYBINDINGS"
    FOUND_SETTINGS=true
fi
if [[ -d "$ANTIGRAVITY_DIR/bin" ]]; then
    log_verbose "Found Antigravity bin directory: $ANTIGRAVITY_DIR/bin"
    FOUND_SETTINGS=true
fi

if [[ "$FOUND_SETTINGS" == false ]]; then
    log_error "No essential settings found for Claude Code or Gemini Antigravity"
    log_error "Expected to find Claude settings (e.g. ~/.claude/) or Antigravity settings (e.g. ~/.gemini/antigravity-cli/)"
    exit 2
fi

# Generate output filename if not provided
if [[ -z "$OUTPUT_FILE" ]]; then
    TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    OUTPUT_FILE="ai-settings-${TIMESTAMP}.zip"

    # When using default filename, create and use data/ directory
    DATA_DIR="$(pwd)/data"
    if [[ ! -d "$DATA_DIR" ]]; then
        log_verbose "Creating data directory: $DATA_DIR"
        mkdir -p "$DATA_DIR"
    fi
    OUTPUT_PATH="$DATA_DIR/$OUTPUT_FILE"
else
    # User provided custom filename
    # Ensure .zip extension
    if [[ "$OUTPUT_FILE" != *.zip ]]; then
        OUTPUT_FILE="${OUTPUT_FILE}.zip"
    fi

    # Check if OUTPUT_FILE is already an absolute path
    if [[ "$OUTPUT_FILE" == /* ]]; then
        # Absolute path provided, use as-is
        OUTPUT_PATH="$OUTPUT_FILE"
    else
        # Relative path provided, prepend current directory
        OUTPUT_PATH="$(pwd)/${OUTPUT_FILE}"
    fi
fi

log_info "Backing up settings..."
log_verbose "Output file: $OUTPUT_PATH"

# Create temporary directory for organizing files
TEMP_DIR=$(mktemp -d)
trap "rm -rf '$TEMP_DIR'" EXIT

log_verbose "Using temporary directory: $TEMP_DIR"

# ----------------- Copy Claude Code Files -----------------
if [[ -f "$CLAUDE_SETTINGS" || -f "$CLAUDE_MD" || -d "$CLAUDE_DIR/commands" || -d "$CLAUDE_DIR/skills" || -d "$CLAUDE_DIR/agents" || -d "$CLAUDE_DIR/plugins" ]]; then
    mkdir -p "$TEMP_DIR/.claude"
fi

if [[ -f "$CLAUDE_SETTINGS" ]]; then
    log_verbose "Copying Claude settings.json"
    cp "$CLAUDE_SETTINGS" "$TEMP_DIR/.claude/settings.json"
fi

if [[ -f "$CLAUDE_MD" ]]; then
    log_verbose "Copying CLAUDE.md"
    cp "$CLAUDE_MD" "$TEMP_DIR/.claude/CLAUDE.md"
fi

if [[ -f "$CLAUDE_JSON" ]]; then
    log_verbose "Copying .claude.json"
    cp "$CLAUDE_JSON" "$TEMP_DIR/.claude.json"
fi

# Copy statusline scripts if they exist
STATUSLINE_SCRIPTS=("$CLAUDE_DIR"/statusline-*.sh)
if [[ -e "${STATUSLINE_SCRIPTS[1]:-}" ]]; then
    log_verbose "Copying Claude statusline scripts"
    cp "$CLAUDE_DIR"/statusline-*.sh "$TEMP_DIR/.claude/"
fi

# Copy personal slash commands directory if it exists
if [[ -d "$CLAUDE_DIR/commands" ]]; then
    log_verbose "Copying Claude personal slash commands"
    cp -R "$CLAUDE_DIR/commands" "$TEMP_DIR/.claude/commands"
fi

# Copy personal skills directory if it exists
if [[ -d "$CLAUDE_DIR/skills" ]]; then
    log_verbose "Copying Claude personal skills"
    cp -R "$CLAUDE_DIR/skills" "$TEMP_DIR/.claude/skills"
fi

# Copy custom agents directory if it exists
if [[ -d "$CLAUDE_DIR/agents" ]]; then
    log_verbose "Copying Claude custom agents"
    cp -R "$CLAUDE_DIR/agents" "$TEMP_DIR/.claude/agents"
fi

# Copy plugins directory if it exists (excluding cache, git history, build artifacts)
if [[ -d "$CLAUDE_DIR/plugins" ]]; then
    log_verbose "Copying Claude installed plugins and marketplaces"
    mkdir -p "$TEMP_DIR/.claude/plugins"
    rsync -a \
        --exclude='cache/' \
        --exclude='.git/' \
        --exclude='node_modules/' \
        --exclude='backups/*.db' \
        --exclude='marketplace/public/fonts/' \
        --exclude='archive/releases/' \
        --exclude='pnpm-lock.yaml' \
        "$CLAUDE_DIR/plugins/" "$TEMP_DIR/.claude/plugins/"
fi

# ----------------- Copy Antigravity CLI Files -----------------
if [[ -f "$ANTIGRAVITY_SETTINGS" || -f "$ANTIGRAVITY_KEYBINDINGS" || -d "$ANTIGRAVITY_DIR/bin" || -d "$ANTIGRAVITY_DIR/commands" || -d "$ANTIGRAVITY_DIR/skills" || -d "$ANTIGRAVITY_DIR/agents" || -d "$ANTIGRAVITY_DIR/plugins" ]]; then
    mkdir -p "$TEMP_DIR/.gemini/antigravity-cli"
fi

if [[ -f "$ANTIGRAVITY_SETTINGS" ]]; then
    log_verbose "Copying Antigravity settings.json"
    cp "$ANTIGRAVITY_SETTINGS" "$TEMP_DIR/.gemini/antigravity-cli/settings.json"
fi

if [[ -f "$ANTIGRAVITY_KEYBINDINGS" ]]; then
    log_verbose "Copying Antigravity keybindings.json"
    cp "$ANTIGRAVITY_KEYBINDINGS" "$TEMP_DIR/.gemini/antigravity-cli/keybindings.json"
fi

if [[ -d "$ANTIGRAVITY_DIR/bin" ]]; then
    log_verbose "Copying Antigravity bin directory"
    cp -R "$ANTIGRAVITY_DIR/bin" "$TEMP_DIR/.gemini/antigravity-cli/bin"
fi

if [[ -d "$ANTIGRAVITY_DIR/commands" ]]; then
    log_verbose "Copying Antigravity personal slash commands"
    cp -R "$ANTIGRAVITY_DIR/commands" "$TEMP_DIR/.gemini/antigravity-cli/commands"
fi

if [[ -d "$ANTIGRAVITY_DIR/skills" ]]; then
    log_verbose "Copying Antigravity personal skills"
    cp -R "$ANTIGRAVITY_DIR/skills" "$TEMP_DIR/.gemini/antigravity-cli/skills"
fi

if [[ -d "$ANTIGRAVITY_DIR/agents" ]]; then
    log_verbose "Copying Antigravity custom agents"
    cp -R "$ANTIGRAVITY_DIR/agents" "$TEMP_DIR/.gemini/antigravity-cli/agents"
fi

if [[ -d "$ANTIGRAVITY_DIR/plugins" ]]; then
    log_verbose "Copying Antigravity installed plugins"
    mkdir -p "$TEMP_DIR/.gemini/antigravity-cli/plugins"
    rsync -a \
        --exclude='cache/' \
        --exclude='.git/' \
        --exclude='node_modules/' \
        --exclude='backups/*.db' \
        --exclude='marketplace/public/fonts/' \
        --exclude='archive/releases/' \
        --exclude='pnpm-lock.yaml' \
        "$ANTIGRAVITY_DIR/plugins/" "$TEMP_DIR/.gemini/antigravity-cli/plugins/"
fi

# Create zip file
log_verbose "Creating zip archive..."
if ! (cd "$TEMP_DIR" && zip -r "$OUTPUT_PATH" . > /dev/null 2>&1); then
    log_error "Failed to create zip archive"
    exit 3
fi

# Verify zip was created
if [[ ! -f "$OUTPUT_PATH" ]]; then
    log_error "Zip file was not created: $OUTPUT_PATH"
    exit 3
fi

# Get file size for display
FILE_SIZE=$(du -h "$OUTPUT_PATH" | cut -f1)

log_success "Settings backed up successfully"
log_info "Output: $OUTPUT_FILE ($FILE_SIZE)"

# Show contents if verbose
if [[ "$VERBOSE" == true ]]; then
    log_verbose "Archive contents:"
    unzip -l "$OUTPUT_PATH"
fi

exit 0
