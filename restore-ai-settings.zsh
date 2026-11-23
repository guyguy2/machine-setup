#!/usr/bin/env zsh

# restore-ai-settings.zsh
# Restores Claude Code, Gemini Antigravity (CLI + ~/.gemini/config), and shared ~/.agents skills
# from a backup zip file and fixes absolute home directory paths and symlinks.

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

Restores Claude Code, Gemini Antigravity (CLI & ~/.gemini/config), and shared ~/.agents
skills from a backup zip file. Automatically rewrites old home directory prefixes in JSON
settings and preserved symlinks.

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

# Extract to temp directory (unzip preserves symlinks archived with zip -y)
if ! unzip -q "$BACKUP_ZIP" -d "$TEMP_DIR"; then
    log_error "Failed to extract backup zip file"
    exit 3
fi

# Path correction logic
OLD_HOME=""
ANTIGRAVITY_SETTINGS_FILE="$TEMP_DIR/.gemini/antigravity-cli/settings.json"
ANTIGRAVITY_MCP_FILE="$TEMP_DIR/.gemini/config/mcp_config.json"
ANTIGRAVITY_AGENTAPI_FILE="$TEMP_DIR/.gemini/antigravity-cli/bin/agentapi"
CLAUDE_SETTINGS_FILE="$TEMP_DIR/.claude/settings.json"

# 1. Try to detect old home directory from Antigravity settings
if [[ -f "$ANTIGRAVITY_SETTINGS_FILE" ]]; then
    log_verbose "Checking Antigravity settings.json for old home directory..."
    OLD_HOME=$(grep -oE '"command": *"[^"]+/.gemini/antigravity-cli' "$ANTIGRAVITY_SETTINGS_FILE" | head -n 1 | sed -E 's/.*"command": *"([^"]+)\/.gemini\/antigravity-cli.*/\1/' || true)
fi

# 2. Fallback to Antigravity mcp_config.json
if [[ -z "$OLD_HOME" ]] && [[ -f "$ANTIGRAVITY_MCP_FILE" ]]; then
    log_verbose "Checking Antigravity mcp_config.json for old home directory..."
    OLD_HOME=$(grep -oE '"command": *"[^"]+/.local/bin/' "$ANTIGRAVITY_MCP_FILE" | head -n 1 | sed -E 's/.*"command": *"([^"]+)\/.local\/bin\/.*/\1/' || true)
fi

# 3. Fallback to Claude settings
if [[ -z "$OLD_HOME" ]] && [[ -f "$CLAUDE_SETTINGS_FILE" ]]; then
    log_verbose "Checking Claude settings.json for old home directory..."
    OLD_HOME=$(grep -oE '"command": *"[^"]+/.claude' "$CLAUDE_SETTINGS_FILE" | head -n 1 | sed -E 's/.*"command": *"([^"]+)\/.claude.*/\1/' || true)
fi

# 4. Fallback to any preserved symlink pointing into /.agents/
if [[ -z "$OLD_HOME" ]]; then
    local link_path link_target
    while IFS= read -r link_path; do
        [[ -z "$link_path" ]] && continue
        link_target="$(readlink "$link_path")"
        if [[ "$link_target" == *"/.agents/"* ]]; then
            OLD_HOME="${link_target%%/.agents/*}"
            break
        fi
    done < <(find "$TEMP_DIR" -type l 2>/dev/null)
fi

if [[ -n "$OLD_HOME" ]]; then
    log_info "Detected old home directory prefix in backup: $OLD_HOME"
    if [[ "$OLD_HOME" != "$HOME" ]]; then
        log_info "Updating absolute paths and symlinks to match current home: $HOME"

        # Files that may contain absolute home paths
        FILES_TO_FIX=()
        [[ -f "$ANTIGRAVITY_SETTINGS_FILE" ]] && FILES_TO_FIX+=("$ANTIGRAVITY_SETTINGS_FILE")
        [[ -f "$ANTIGRAVITY_MCP_FILE" ]] && FILES_TO_FIX+=("$ANTIGRAVITY_MCP_FILE")
        [[ -f "$ANTIGRAVITY_AGENTAPI_FILE" ]] && FILES_TO_FIX+=("$ANTIGRAVITY_AGENTAPI_FILE")
        [[ -f "$CLAUDE_SETTINGS_FILE" ]] && FILES_TO_FIX+=("$CLAUDE_SETTINGS_FILE")

        esc_old=${OLD_HOME//\\/\\\\}
        esc_old=${esc_old//|/\\|}
        esc_old=${esc_old//\./\\.}
        esc_old=${esc_old//\*/\\*}
        esc_old=${esc_old//[/\\[}
        esc_old=${esc_old//]/\\]}
        esc_old=${esc_old//^/\\^}
        esc_old=${esc_old//$/\\$}
        esc_new=${HOME//\\/\\\\}
        esc_new=${esc_new//|/\\|}
        esc_new=${esc_new//&/\\&}
        for cfg_file in "${FILES_TO_FIX[@]}"; do
            log_verbose "Fixing paths in ${cfg_file#$TEMP_DIR/}..."
            if [[ "$DRY_RUN" == true ]]; then
                log_verbose "[DRY-RUN] sed 's|$esc_old|$esc_new|g' $cfg_file"
            else
                # Portable in-place sed replacement (BSD sed first, then GNU)
                sed -i '' "s|$esc_old|$esc_new|g" "$cfg_file" 2>/dev/null || sed -i "s|$esc_old|$esc_new|g" "$cfg_file"
            fi
        done

        # Rewrite preserved symlinks whose target starts with $OLD_HOME/
        while IFS= read -r link_path; do
            [[ -z "$link_path" ]] && continue
            link_target="$(readlink "$link_path")"
            if [[ "$link_target" == "$OLD_HOME/"* ]]; then
                new_target="${HOME}${link_target#$OLD_HOME}"
                if [[ "$DRY_RUN" == true ]]; then
                    log_verbose "[DRY-RUN] relink ${link_path#$TEMP_DIR/}: $link_target -> $new_target"
                else
                    log_verbose "Relinking ${link_path#$TEMP_DIR/}: $link_target -> $new_target"
                    ln -sfn "$new_target" "$link_path"
                fi
            fi
        done < <(find "$TEMP_DIR" -type l 2>/dev/null)
    else
        log_verbose "Old home directory matches current home. No path updates required."
    fi
else
    log_verbose "No absolute script paths detected in backup."
fi

# Helper to copy directory preserving symlinks (BSD & GNU compatible)
copy_tree() {
    local src="$1"
    local dst="$2"
    mkdir -p "$dst"
    cp -a "$src/." "$dst/"
}

# Safely back up existing configuration directories before replacing
if [[ "$DRY_RUN" == false ]]; then
    if [[ -d "$TEMP_DIR/.claude" && -d "$HOME/.claude" ]]; then
        log_info "Backing up existing ~/.claude to ~/.claude.backup"
        rm -rf "$HOME/.claude.backup"
        cp -a "$HOME/.claude" "$HOME/.claude.backup"
    fi
    if [[ -f "$TEMP_DIR/.claude.json" && -f "$HOME/.claude.json" ]]; then
        log_info "Backing up existing ~/.claude.json to ~/.claude.json.backup"
        cp "$HOME/.claude.json" "$HOME/.claude.json.backup"
    fi
    if [[ -d "$TEMP_DIR/.agents" && -d "$HOME/.agents" ]]; then
        log_info "Backing up existing ~/.agents to ~/.agents.backup"
        rm -rf "$HOME/.agents.backup"
        cp -a "$HOME/.agents" "$HOME/.agents.backup"
    fi
    if [[ -d "$TEMP_DIR/.gemini/antigravity-cli" && -d "$HOME/.gemini/antigravity-cli" ]]; then
        log_info "Backing up existing ~/.gemini/antigravity-cli to ~/.gemini/antigravity-cli.backup"
        rm -rf "$HOME/.gemini/antigravity-cli.backup"
        cp -a "$HOME/.gemini/antigravity-cli" "$HOME/.gemini/antigravity-cli.backup"
    fi
    if [[ -d "$TEMP_DIR/.gemini/config" && -d "$HOME/.gemini/config" ]]; then
        log_info "Backing up existing ~/.gemini/config to ~/.gemini/config.backup"
        rm -rf "$HOME/.gemini/config.backup"
        cp -a "$HOME/.gemini/config" "$HOME/.gemini/config.backup"
    fi

    # Perform restoration
    log_info "Writing settings to home directory..."
    mkdir -p "$HOME" "$HOME/.gemini"

    if [[ -d "$TEMP_DIR/.claude" ]]; then
        rm -rf "$HOME/.claude"
        cp -a "$TEMP_DIR/.claude" "$HOME/.claude"
        log_verbose "Restored ~/.claude/"
    fi

    if [[ -f "$TEMP_DIR/.claude.json" ]]; then
        cp "$TEMP_DIR/.claude.json" "$HOME/.claude.json"
        log_verbose "Restored ~/.claude.json"
    fi

    if [[ -d "$TEMP_DIR/.agents" ]]; then
        rm -rf "$HOME/.agents"
        cp -a "$TEMP_DIR/.agents" "$HOME/.agents"
        log_verbose "Restored ~/.agents/"
    fi

    if [[ -d "$TEMP_DIR/.gemini/antigravity-cli" ]]; then
        mkdir -p "$HOME/.gemini/antigravity-cli"
        # Overlay settings/bin/customizations without deleting local conversations/brain if present
        copy_tree "$TEMP_DIR/.gemini/antigravity-cli" "$HOME/.gemini/antigravity-cli"
        log_verbose "Restored ~/.gemini/antigravity-cli/ settings"
    fi

    if [[ -d "$TEMP_DIR/.gemini/config" ]]; then
        rm -rf "$HOME/.gemini/config"
        cp -a "$TEMP_DIR/.gemini/config" "$HOME/.gemini/config"
        log_verbose "Restored ~/.gemini/config/"
    fi

    if [[ -f "$TEMP_DIR/.gemini/GEMINI.md" ]]; then
        cp "$TEMP_DIR/.gemini/GEMINI.md" "$HOME/.gemini/GEMINI.md"
        log_verbose "Restored ~/.gemini/GEMINI.md"
    fi

    for sub in agents commands skills; do
        if [[ -d "$TEMP_DIR/.gemini/$sub" ]]; then
            rm -rf "$HOME/.gemini/$sub"
            cp -a "$TEMP_DIR/.gemini/$sub" "$HOME/.gemini/$sub"
            log_verbose "Restored ~/.gemini/$sub/"
        fi
    done

    # Restore skill CLI symlinks into ~/.local/bin without touching other binaries
    if [[ -d "$TEMP_DIR/.local/bin" ]]; then
        mkdir -p "$HOME/.local/bin"
        for bin_entry in "$TEMP_DIR/.local/bin"/*(N); do
            cp -a "$bin_entry" "$HOME/.local/bin/${bin_entry:t}"
            log_verbose "Restored ~/.local/bin/${bin_entry:t}"
        done
    fi

    # Make scripts executable
    log_verbose "Restoring script executable permissions..."
    if [[ -d "$HOME/.gemini/antigravity-cli/bin" ]]; then
        chmod +x "$HOME"/.gemini/antigravity-cli/bin/* 2>/dev/null || true
    fi
    if [[ -d "$HOME/.claude" ]]; then
        chmod +x "$HOME"/.claude/statusline-*.sh 2>/dev/null || true
    fi
    if [[ -d "$HOME/.agents/skills" ]]; then
        find "$HOME/.agents/skills" -type f \( -name '*.sh' -o -name '*.py' -o -name '*.zsh' \) -exec chmod +x {} + 2>/dev/null || true
    fi

    log_success "Settings restored successfully!"
else
    log_info "[DRY-RUN] The following configurations would be restored to ~:"
    [[ -d "$TEMP_DIR/.claude" ]] && echo "  - ~/.claude/"
    [[ -f "$TEMP_DIR/.claude.json" ]] && echo "  - ~/.claude.json"
    [[ -d "$TEMP_DIR/.agents" ]] && echo "  - ~/.agents/ (shared global skills)"
    [[ -d "$TEMP_DIR/.gemini/antigravity-cli" ]] && echo "  - ~/.gemini/antigravity-cli/"
    [[ -d "$TEMP_DIR/.gemini/config" ]] && echo "  - ~/.gemini/config/ (Antigravity global skills, plugins, rules, mcp_config.json)"
    [[ -f "$TEMP_DIR/.gemini/GEMINI.md" ]] && echo "  - ~/.gemini/GEMINI.md"
    [[ -d "$TEMP_DIR/.gemini/agents" ]] && echo "  - ~/.gemini/agents/"
    [[ -d "$TEMP_DIR/.gemini/commands" ]] && echo "  - ~/.gemini/commands/"
    [[ -d "$TEMP_DIR/.gemini/skills" ]] && echo "  - ~/.gemini/skills/"
    [[ -d "$TEMP_DIR/.local/bin" ]] && echo "  - ~/.local/bin/ (skill CLI symlinks: $(ls "$TEMP_DIR/.local/bin" | tr '\n' ' '))"
    log_success "[DRY-RUN] Dry run completed. No files were modified."
fi

exit 0
