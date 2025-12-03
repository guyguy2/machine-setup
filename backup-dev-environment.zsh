#!/usr/bin/env zsh

# backup-dev-environment.zsh
# Orchestrates backup of development environment settings including Claude Code and dotfiles

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

log_warning() {
    echo "[WARNING] $*" >&2
}

# Show help message
show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Orchestrates comprehensive backup of development environment settings including:
  - Claude Code settings (via backup-claude-settings.zsh)
  - Shell configuration (.zshrc)
  - Git configuration (.gitconfig)
  - SSH configuration (.ssh/config)

Creates two timestamped zip files in a data/ directory for easy restoration.

Options:
  -v, --verbose         Verbose output (passed to backup-claude-settings.zsh)
  -h, --help            Show this help message
  --skip-claude         Skip Claude Code settings backup
  --skip-dotfiles       Skip dotfiles backup

Examples:
  $(basename "$0")                              # Create timestamped backups
  $(basename "$0") --verbose                    # Show detailed output
  $(basename "$0") --skip-dotfiles              # Only backup Claude settings

Directory structure:
  data/
    ├── claude-settings-20251116-120000.zip    # Claude Code backup
    └── dotfiles-20251116-120000.zip           # Dotfiles backup (.zshrc, .gitconfig, .ssh/config)

Restoring from backup:
  1. Extract Claude settings:
     unzip data/claude-settings-*.zip -d ~

  2. Extract dotfiles:
     unzip data/dotfiles-*.zip -d ~

  3. Restart terminal and Claude Code

Exit codes:
  0 - Success
  1 - General error
  2 - Missing required files
  3 - Backup creation failed

EOF
}

# Parse command-line arguments
VERBOSE=false
VERBOSE_FLAG=""
SKIP_CLAUDE=false
SKIP_DOTFILES=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--verbose)
            VERBOSE=true
            VERBOSE_FLAG="--verbose"
            shift
            ;;
        --skip-claude)
            SKIP_CLAUDE=true
            shift
            ;;
        --skip-dotfiles)
            SKIP_DOTFILES=true
            shift
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

# Get script directory (where backup-claude-settings.zsh should be)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_BACKUP_SCRIPT="$SCRIPT_DIR/backup-claude-settings.zsh"

# Verify backup-claude-settings.zsh exists
if [[ "$SKIP_CLAUDE" == false ]] && [[ ! -f "$CLAUDE_BACKUP_SCRIPT" ]]; then
    log_error "Cannot find backup-claude-settings.zsh in $SCRIPT_DIR"
    log_error "Please ensure backup-claude-settings.zsh is in the same directory as this script"
    exit 2
fi

# Use data/ directory in current location
DATA_DIR="$(pwd)/data"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

log_info "Creating development environment backup..."
log_verbose "Output directory: $DATA_DIR"

# Create data directory
if ! mkdir -p "$DATA_DIR"; then
    log_error "Failed to create data directory: $DATA_DIR"
    exit 3
fi

# Track what was backed up
BACKED_UP_FILES=()

# Backup Claude Code settings
if [[ "$SKIP_CLAUDE" == false ]]; then
    CLAUDE_ZIP_NAME="claude-settings-${TIMESTAMP}.zip"

    if "$CLAUDE_BACKUP_SCRIPT" -o "$DATA_DIR/$CLAUDE_ZIP_NAME" $VERBOSE_FLAG; then
        log_verbose "Claude settings backed up to data/$CLAUDE_ZIP_NAME"
        BACKED_UP_FILES+=("$CLAUDE_ZIP_NAME")
    else
        log_error "Failed to backup Claude Code settings"
        exit 3
    fi
else
    log_verbose "Skipping Claude Code settings backup"
fi

# Backup dotfiles
if [[ "$SKIP_DOTFILES" == false ]]; then
    log_info "Backing up dotfiles..."

    # Create temporary directory for dotfiles
    TEMP_DOTFILES_DIR=$(mktemp -d)
    DOTFILES_COLLECTED=false

    # Backup .zshrc
    if [[ -f "$HOME/.zshrc" ]]; then
        log_verbose "Copying .zshrc"
        if cp "$HOME/.zshrc" "$TEMP_DOTFILES_DIR/.zshrc"; then
            DOTFILES_COLLECTED=true
        else
            log_warning "Failed to copy .zshrc"
        fi
    else
        log_verbose ".zshrc not found, skipping"
    fi

    # Backup .gitconfig
    if [[ -f "$HOME/.gitconfig" ]]; then
        log_verbose "Copying .gitconfig"
        if cp "$HOME/.gitconfig" "$TEMP_DOTFILES_DIR/.gitconfig"; then
            DOTFILES_COLLECTED=true
        else
            log_warning "Failed to copy .gitconfig"
        fi
    else
        log_verbose ".gitconfig not found, skipping"
    fi

    # Backup .ssh/config
    if [[ -f "$HOME/.ssh/config" ]]; then
        log_verbose "Copying .ssh/config"
        if cp "$HOME/.ssh/config" "$TEMP_DOTFILES_DIR/.ssh-config"; then
            DOTFILES_COLLECTED=true
        else
            log_warning "Failed to copy .ssh/config"
        fi
    else
        log_verbose ".ssh/config not found, skipping"
    fi

    # Create zip file if we collected any dotfiles
    if [[ "$DOTFILES_COLLECTED" == true ]]; then
        DOTFILES_ZIP_NAME="dotfiles-${TIMESTAMP}.zip"
        log_verbose "Creating dotfiles zip: $DOTFILES_ZIP_NAME"

        if (cd "$TEMP_DOTFILES_DIR" && zip -q -r "$DATA_DIR/$DOTFILES_ZIP_NAME" .); then
            log_verbose "Dotfiles backed up to data/$DOTFILES_ZIP_NAME"
            BACKED_UP_FILES+=("$DOTFILES_ZIP_NAME")
        else
            log_error "Failed to create dotfiles zip"
            rm -rf "$TEMP_DOTFILES_DIR"
            exit 3
        fi
    else
        log_warning "No dotfiles found to backup"
    fi

    # Clean up temporary directory
    rm -rf "$TEMP_DOTFILES_DIR"
else
    log_verbose "Skipping dotfiles backup"
fi

# Verify at least something was backed up
if [[ ${#BACKED_UP_FILES[@]} -eq 0 ]]; then
    log_error "No files were backed up"
    rm -rf "$DATA_DIR"
    exit 2
fi

# Clean up old backups (keep only 1 most recent of each type)
log_verbose "Cleaning up old backups in $DATA_DIR"

# Clean up old claude-settings-*.zip files (keep 1 most recent)
OLD_CLAUDE_BACKUPS=($(ls -t "$DATA_DIR"/claude-settings-*.zip 2>/dev/null | tail -n +2))
if [[ ${#OLD_CLAUDE_BACKUPS[@]} -gt 0 ]]; then
    log_verbose "Removing ${#OLD_CLAUDE_BACKUPS[@]} old claude-settings backup(s)"
    for old_backup in "${OLD_CLAUDE_BACKUPS[@]}"; do
        log_verbose "Deleting: $(basename "$old_backup")"
        rm -f "$old_backup"
    done
fi

# Clean up old dotfiles-*.zip files (keep 1 most recent)
OLD_DOTFILES_BACKUPS=($(ls -t "$DATA_DIR"/dotfiles-*.zip 2>/dev/null | tail -n +2))
if [[ ${#OLD_DOTFILES_BACKUPS[@]} -gt 0 ]]; then
    log_verbose "Removing ${#OLD_DOTFILES_BACKUPS[@]} old dotfiles backup(s)"
    for old_backup in "${OLD_DOTFILES_BACKUPS[@]}"; do
        log_verbose "Deleting: $(basename "$old_backup")"
        rm -f "$old_backup"
    done
fi

# Get directory size for display
DIR_SIZE=$(du -sh "$DATA_DIR" | cut -f1)

log_success "Development environment backup completed successfully"
log_info "Output directory: data/ ($DIR_SIZE)"
log_info "Zip files created: ${#BACKED_UP_FILES[@]}"

# Show contents if verbose
if [[ "$VERBOSE" == true ]]; then
    log_verbose "Backup contents:"
    ls -lha "$DATA_DIR"
fi

exit 0
