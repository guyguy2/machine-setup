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

Backs up Claude Code global settings to a zip file in the current directory.

Backs up essential settings for Claude Code on a new Mac:
  - ~/.claude/settings.json     (hooks, statusline, preferences)
  - ~/.claude/statusline-*.sh   (custom statusline scripts)
  - ~/.claude/.agents/          (custom agents, if present)
  - ~/.claude/.commands/        (custom slash commands, if present)
  - ~/.claude.json              (main config file - MCP servers, settings)

Options:
  -o, --output FILE     Custom output filename (default: claude-settings-TIMESTAMP.zip)
  -v, --verbose         Verbose output
  -h, --help            Show this help message

Examples:
  $(basename "$0")                                   # Create timestamped backup
  $(basename "$0") -o my-claude-backup.zip           # Custom filename
  $(basename "$0") --verbose                         # Show detailed output

Restoring from backup:
  To restore Claude Code settings from a backup zip file on a new Mac:

  1. Extract the backup to your home directory:
     unzip claude-settings-20251114-211800.zip -d ~

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
CLAUDE_JSON="$HOME/.claude.json"
CLAUDE_DIR="$HOME/.claude"

# Check if any essential settings exist
FOUND_SETTINGS=false

if [[ -f "$CLAUDE_SETTINGS" ]]; then
    log_verbose "Found Claude settings: $CLAUDE_SETTINGS"
    FOUND_SETTINGS=true
fi

if [[ -f "$CLAUDE_JSON" ]]; then
    log_verbose "Found Claude config: $CLAUDE_JSON"
    FOUND_SETTINGS=true
fi

if [[ "$FOUND_SETTINGS" == false ]]; then
    log_error "No essential Claude Code settings found"
    log_error "Expected to find: ~/.claude/settings.json or ~/.claude.json"
    exit 2
fi

# Generate output filename if not provided
if [[ -z "$OUTPUT_FILE" ]]; then
    TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    OUTPUT_FILE="claude-settings-${TIMESTAMP}.zip"
fi

# Ensure .zip extension
if [[ "$OUTPUT_FILE" != *.zip ]]; then
    OUTPUT_FILE="${OUTPUT_FILE}.zip"
fi

# Get absolute path for output file in current directory
OUTPUT_PATH="$(pwd)/${OUTPUT_FILE}"

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

# Copy custom agents directory if it exists
if [[ -d "$CLAUDE_DIR/.agents" ]]; then
    log_verbose "Copying custom agents"
    cp -R "$CLAUDE_DIR/.agents" "$TEMP_DIR/.claude/.agents"
fi

# Copy custom commands directory if it exists
if [[ -d "$CLAUDE_DIR/.commands" ]]; then
    log_verbose "Copying custom slash commands"
    cp -R "$CLAUDE_DIR/.commands" "$TEMP_DIR/.claude/.commands"
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

log_success "Claude Code settings backed up successfully"
log_info "Output: $OUTPUT_FILE ($FILE_SIZE)"

# Show contents if verbose
if [[ "$VERBOSE" == true ]]; then
    log_verbose "Archive contents:"
    unzip -l "$OUTPUT_PATH"
fi

exit 0
