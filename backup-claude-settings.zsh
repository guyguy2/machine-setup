#!/usr/bin/env zsh

# backup-claude-settings.zsh
# Backs up Claude Code global settings to a timestamped zip file

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

Backs up Claude Code global settings to a zip file in the data/ directory.

Backs up essential settings for Claude Code on a new Mac:
  - ~/.claude/settings.json     (hooks, statusline, preferences)
  - ~/.claude/CLAUDE.md         (global instructions for Claude Code)
  - ~/.claude/statusline-*.sh   (custom statusline scripts)
  - ~/.claude/commands/         (personal slash commands, if present)
  - ~/.claude/skills/           (personal skills, if present)
  - ~/.claude/agents/           (custom agents, if present)
  - ~/.claude/plugins/          (installed plugins and marketplaces, if present)
  - ~/.claude.json              (main config file - MCP servers, settings)

Options:
  -o, --output FILE     Custom output filename in current directory (default: data/claude-settings-TIMESTAMP.zip)
  -v, --verbose         Verbose output
  -h, --help            Show this help message

Examples:
  $(basename "$0")                                   # Create timestamped backup in data/
  $(basename "$0") -o my-claude-backup.zip           # Custom filename in current directory
  $(basename "$0") --verbose                         # Show detailed output

Restoring from backup:
  To restore Claude Code settings from a backup zip file on a new Mac:

  1. Extract the backup to your home directory:
     unzip data/claude-settings-20251114-211800.zip -d ~

  2. Verify the files were extracted:
     ls -la ~/.claude/
     ls -la ~/.claude.json

  3. Restart Claude Code to load the restored settings:
     # Close and reopen Claude Code, or restart the terminal

  Note: The zip file contains the .claude directory and .claude.json file
        with the correct paths, so extracting to ~ will place everything
        in the right location.

Exit codes:
  0 - Success
  1 - General error
  2 - Missing Claude Code settings
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

# Check if any essential settings exist
FOUND_SETTINGS=false

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

if [[ "$FOUND_SETTINGS" == false ]]; then
    log_error "No essential Claude Code settings found"
    log_error "Expected to find: ~/.claude/settings.json, ~/.claude/CLAUDE.md, or ~/.claude.json"
    exit 2
fi

# Generate output filename if not provided
if [[ -z "$OUTPUT_FILE" ]]; then
    TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    OUTPUT_FILE="claude-settings-${TIMESTAMP}.zip"

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

log_info "Backing up Claude Code settings..."
log_verbose "Output file: $OUTPUT_PATH"

# Create temporary directory for organizing files
TEMP_DIR=$(mktemp -d)
trap "rm -rf '$TEMP_DIR'" EXIT

log_verbose "Using temporary directory: $TEMP_DIR"

# Create .claude directory in temp
mkdir -p "$TEMP_DIR/.claude"

# Copy essential files to temp directory
if [[ -f "$CLAUDE_SETTINGS" ]]; then
    log_verbose "Copying settings.json"
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
if [[ -e "${STATUSLINE_SCRIPTS[1]}" ]]; then
    log_verbose "Copying statusline scripts"
    cp "$CLAUDE_DIR"/statusline-*.sh "$TEMP_DIR/.claude/"
fi

# Copy personal slash commands directory if it exists
if [[ -d "$CLAUDE_DIR/commands" ]]; then
    log_verbose "Copying personal slash commands"
    cp -R "$CLAUDE_DIR/commands" "$TEMP_DIR/.claude/commands"
fi

# Copy personal skills directory if it exists
if [[ -d "$CLAUDE_DIR/skills" ]]; then
    log_verbose "Copying personal skills"
    cp -R "$CLAUDE_DIR/skills" "$TEMP_DIR/.claude/skills"
fi

# Copy custom agents directory if it exists
if [[ -d "$CLAUDE_DIR/agents" ]]; then
    log_verbose "Copying custom agents"
    cp -R "$CLAUDE_DIR/agents" "$TEMP_DIR/.claude/agents"
fi

# Copy plugins directory if it exists
if [[ -d "$CLAUDE_DIR/plugins" ]]; then
    log_verbose "Copying installed plugins and marketplaces"
    cp -R "$CLAUDE_DIR/plugins" "$TEMP_DIR/.claude/plugins"
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

# Clean up old backups in data directory (keep only 1 most recent)
if [[ "$OUTPUT_PATH" == *"/data/"* ]]; then
    DATA_DIR="$(dirname "$OUTPUT_PATH")"
    log_verbose "Cleaning up old backups in $DATA_DIR"

    # Find all claude-settings-*.zip files sorted by modification time (newest first)
    # Keep the 1 most recent, delete the rest
    OLD_BACKUPS=($(ls -t "$DATA_DIR"/claude-settings-*.zip 2>/dev/null | tail -n +2))

    if [[ ${#OLD_BACKUPS[@]} -gt 0 ]]; then
        log_verbose "Removing ${#OLD_BACKUPS[@]} old backup(s)"
        for old_backup in "${OLD_BACKUPS[@]}"; do
            log_verbose "Deleting: $(basename "$old_backup")"
            rm -f "$old_backup"
        done
    else
        log_verbose "No old backups to clean up"
    fi
fi

log_success "Claude Code settings backed up successfully"
log_info "Output: $OUTPUT_FILE ($FILE_SIZE)"

# Show contents if verbose
if [[ "$VERBOSE" == true ]]; then
    log_verbose "Archive contents:"
    unzip -l "$OUTPUT_PATH"
fi

exit 0
