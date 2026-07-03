#!/usr/bin/env zsh

# restore-ai-settings.zsh
# Restores Claude Code and Gemini Antigravity settings from a backup zip file and fixes absolute paths

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

log_verbose() {
    if [[ "$VERBOSE" == true ]]; then
        echo "[VERBOSE] $*"
    fi
}

# Show help message
show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] BACKUP_ZIP

Restores Claude Code and Gemini Antigravity CLI global settings from a backup zip file.

Arguments:
  BACKUP_ZIP            Path to the backup zip file (e.g. data/ai-settings-TIMESTAMP.zip)

Options:
  -v, --verbose         Verbose output
  -h, --help            Show this help message
  --dry-run             Show what would be restored and path replacements, without writing any files

Examples:
  $(basename "$0") data/ai-settings-20260703-120000.zip
  $(basename "$0") --dry-run data/ai-settings-20260703-120000.zip

Exit codes:
  0 - Success
  1 - General/argument error
  2 - Backup file not found or invalid
  3 - Extraction/Restoration failed

EOF
}

# Parse command-line arguments
VERBOSE=false
DRY_RUN=false
BACKUP_ZIP=""

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
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -*)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
        *)
            if [[ -z "$BACKUP_ZIP" ]]; then
                BACKUP_ZIP="$1"
                shift
            else
                log_error "Multiple backup files specified: $BACKUP_ZIP and $1"
                exit 1
            fi
            ;;
    esac
done

if [[ -z "$BACKUP_ZIP" ]]; then
    log_error "No backup zip file specified."
    echo "Usage: $(basename "$0") [OPTIONS] BACKUP_ZIP"
    exit 1
fi

# Verify backup zip exists
if [[ ! -f "$BACKUP_ZIP" ]]; then
    log_error "Backup file not found: $BACKUP_ZIP"
    exit 2
fi

log_info "Analyzing backup: $BACKUP_ZIP"

# Create temporary directory for extraction
TEMP_DIR=$(mktemp -d)
trap "rm -rf '$TEMP_DIR'" EXIT

log_verbose "Using temporary directory: $TEMP_DIR"

# Extract to temp directory
if ! unzip -q "$BACKUP_ZIP" -d "$TEMP_DIR"; then
    log_error "Failed to extract backup zip file"
    exit 3
fi

# Path correction logic
OLD_HOME=""
ANTIGRAVITY_SETTINGS_FILE="$TEMP_DIR/.gemini/antigravity-cli/settings.json"
CLAUDE_SETTINGS_FILE="$TEMP_DIR/.claude/settings.json"

# Try to detect old home directory from Antigravity settings
if [[ -f "$ANTIGRAVITY_SETTINGS_FILE" ]]; then
    log_verbose "Checking Antigravity settings.json for old home directory..."
    OLD_HOME=$(grep -oE '"command": *"[^"]+/.gemini/antigravity-cli' "$ANTIGRAVITY_SETTINGS_FILE" | sed -E 's/.*"command": *"([^"]+)\/.gemini\/antigravity-cli.*/\1/' || true)
fi

# Fallback to Claude settings
if [[ -z "$OLD_HOME" ]] && [[ -f "$CLAUDE_SETTINGS_FILE" ]]; then
    log_verbose "Checking Claude settings.json for old home directory..."
    OLD_HOME=$(grep -oE '"command": *"[^"]+/.claude' "$CLAUDE_SETTINGS_FILE" | sed -E 's/.*"command": *"([^"]+)\/.claude.*/\1/' || true)
fi

if [[ -n "$OLD_HOME" ]]; then
    log_info "Detected old home directory prefix in backup: $OLD_HOME"
    if [[ "$OLD_HOME" != "$HOME" ]]; then
        log_info "Updating absolute paths to match current home: $HOME"
        
        # Define files that may contain absolute paths
        FILES_TO_FIX=()
        [[ -f "$ANTIGRAVITY_SETTINGS_FILE" ]] && FILES_TO_FIX+=("$ANTIGRAVITY_SETTINGS_FILE")
        [[ -f "$CLAUDE_SETTINGS_FILE" ]] && FILES_TO_FIX+=("$CLAUDE_SETTINGS_FILE")
        
        for json_file in "${FILES_TO_FIX[@]}"; do
            log_verbose "Fixing paths in $(basename "$json_file")..."
            if [[ "$DRY_RUN" == true ]]; then
                log_verbose "[DRY-RUN] sed "s|$OLD_HOME|$HOME|g" $json_file"
            else
                # Portable in-place sed replacement
                sed -i '' "s|$OLD_HOME|$HOME|g" "$json_file" 2>/dev/null || sed -i "s|$OLD_HOME|$HOME|g" "$json_file"
            fi
        done
    else
        log_verbose "Old home directory matches current home. No path updates required."
    fi
else
    log_verbose "No absolute script paths detected in settings.json files."
fi

# Safely back up existing configuration directories before replacing
if [[ "$DRY_RUN" == false ]]; then
    if [[ -d "$HOME/.claude" ]]; then
        log_info "Backing up existing ~/.claude to ~/.claude.backup"
        rm -rf "$HOME/.claude.backup"
        cp -R "$HOME/.claude" "$HOME/.claude.backup"
    fi
    if [[ -f "$HOME/.claude.json" ]]; then
        log_info "Backing up existing ~/.claude.json to ~/.claude.json.backup"
        cp "$HOME/.claude.json" "$HOME/.claude.json.backup"
    fi
    if [[ -d "$HOME/.gemini/antigravity-cli" ]]; then
        log_info "Backing up existing ~/.gemini/antigravity-cli to ~/.gemini/antigravity-cli.backup"
        rm -rf "$HOME/.gemini/antigravity-cli.backup"
        cp -R "$HOME/.gemini/antigravity-cli" "$HOME/.gemini/antigravity-cli.backup"
    fi

    # Perform restoration
    log_info "Writing settings to home directory..."
    mkdir -p "$HOME"
    mkdir -p "$HOME/.gemini"

    if [[ -d "$TEMP_DIR/.claude" ]]; then
        mkdir -p "$HOME/.claude"
        cp -R "$TEMP_DIR/.claude/"* "$HOME/.claude/"
        log_verbose "Restored ~/.claude/"
    fi
    
    if [[ -f "$TEMP_DIR/.claude.json" ]]; then
        cp "$TEMP_DIR/.claude.json" "$HOME/.claude.json"
        log_verbose "Restored ~/.claude.json"
    fi
    
    if [[ -d "$TEMP_DIR/.gemini/antigravity-cli" ]]; then
        mkdir -p "$HOME/.gemini/antigravity-cli"
        cp -R "$TEMP_DIR/.gemini/antigravity-cli/"* "$HOME/.gemini/antigravity-cli/"
        log_verbose "Restored ~/.gemini/antigravity-cli/"
    fi

    # Make scripts executable
    log_verbose "Restoring script executable permissions..."
    if [[ -d "$HOME/.gemini/antigravity-cli/bin" ]]; then
        chmod +x "$HOME"/.gemini/antigravity-cli/bin/* 2>/dev/null || true
    fi
    if [[ -d "$HOME/.claude" ]]; then
        chmod +x "$HOME"/.claude/statusline-*.sh 2>/dev/null || true
    fi

    log_success "Settings restored successfully!"
else
    log_info "[DRY-RUN] The following configurations would be restored to ~:"
    if [[ -d "$TEMP_DIR/.claude" ]]; then
        echo "  - ~/.claude/"
    fi
    if [[ -f "$TEMP_DIR/.claude.json" ]]; then
        echo "  - ~/.claude.json"
    fi
    if [[ -d "$TEMP_DIR/.gemini/antigravity-cli" ]]; then
        echo "  - ~/.gemini/antigravity-cli/"
    fi
    log_success "[DRY-RUN] Dry run completed. No files were modified."
fi

exit 0
