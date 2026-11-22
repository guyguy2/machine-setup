#!/usr/bin/env zsh

# backup-ai-settings.zsh
# Backs up Claude Code, Gemini Antigravity (CLI + global config), and shared ~/.agents skills
# to a timestamped zip file.

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

Backs up Claude Code, Gemini Antigravity (CLI & ~/.gemini/config), and shared global skills
(~/.agents) to a zip file in the data/ directory.

Backs up essential settings for Claude Code and Gemini Antigravity on a new Mac:
  Claude Code:
    - ~/.claude/settings.json     (hooks, statusline, preferences)
    - ~/.claude/CLAUDE.md         (global instructions for Claude Code)
    - ~/.claude/statusline-*.sh   (custom statusline scripts)
    - ~/.claude/commands/         (personal slash commands, if present)
    - ~/.claude/skills/           (personal skills, if present)
    - ~/.claude/agents/           (custom agents, if present)
    - ~/.claude/plugins/          (installed plugins and marketplaces, if present)

  Note: ~/.claude.json is intentionally excluded. It stores MCP server
  credentials and other API keys/tokens in plaintext, so it is not safe
  to bundle into a backup that may be copied elsewhere (e.g. git).

  Shared Global Skills:
    - ~/.agents/skills/           (canonical cross-agent skills, e.g. browser-feedback-loop, rex)
    - ~/.agents/.skill-lock.json  (skill lock metadata, if present)
    - ~/.local/bin/*              (only symlinks pointing into ~/.agents/skills/)

  Gemini Antigravity CLI & Global Customizations:
    - ~/.gemini/antigravity-cli/settings.json     (main CLI configuration file)
    - ~/.gemini/antigravity-cli/keybindings.json  (custom shortcut keybindings, if present)
    - ~/.gemini/antigravity-cli/bin/              (custom scripts such as statusline.py; excludes webm_encoder)
    - ~/.gemini/antigravity-cli/commands/         (personal slash commands, if present)
    - ~/.gemini/antigravity-cli/skills/           (personal skills, if present)
    - ~/.gemini/antigravity-cli/agents/           (custom agents, if present)
    - ~/.gemini/antigravity-cli/plugins/          (installed plugins, if present)
    - ~/.gemini/config/config.json                (enabled Antigravity plugins & user settings)
    - ~/.gemini/config/mcp_config.json            (global MCP servers config)
    - ~/.gemini/config/hooks.json                 (global lifecycle hooks, if present)
    - ~/.gemini/config/{skills,plugins,rules}.json (explicit customization manifests, if present)
    - ~/.gemini/config/skills/                    (global Antigravity skills)
    - ~/.gemini/config/rules/                     (global Antigravity rules, if present)
    - ~/.gemini/config/plugins/                   (installed Antigravity plugins)
    - ~/.gemini/config/sidecars/                  (sidecar configs, if present)
    - ~/.gemini/GEMINI.md                         (global Gemini/Antigravity user rules)
    - ~/.gemini/agents/                           (global custom subagents, if present)
    - ~/.gemini/commands/                         (global custom slash commands, if present)
    - ~/.gemini/skills/                           (top-level Gemini skills, if present)

Options:
  -o, --output FILE     Custom output filename in current directory (default: data/ai-settings-TIMESTAMP.zip)
  -v, --verbose         Verbose output
  -h, --help            Show this help message

Examples:
  $(basename "$0")                                   # Create timestamped backup in data/
  $(basename "$0") -o my-ai-backup.zip               # Custom filename in current directory
  $(basename "$0") --verbose                         # Show detailed output

Restoring from backup:
  Recommended (rewrites home paths and preserves symlinks):
    ./restore-ai-settings.zsh data/ai-settings-TIMESTAMP.zip

  Or extract directly to your home directory:
    unzip data/ai-settings-TIMESTAMP.zip -d ~

Exit codes:
  0 - Success
  1 - General error
  2 - Missing settings (neither Claude, Antigravity, nor ~/.agents settings found)
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

# Create a relative symlink inside TEMP_DIR pointing from $link_dir/$name to $TEMP_DIR/$rel_target
# Using relative symlinks makes `unzip` work cleanly on macOS (which rejects absolute symlink targets)
# and stays portable across different usernames / $HOME directories automatically.
make_relative_staged_symlink() {
    local link_dir="$1"
    local name="$2"
    local target_abs="$3"
    local rel_from_home="${target_abs#$HOME/}"
    local staged_target="$TEMP_DIR/$rel_from_home"
    local rel_link
    rel_link="$(python3 -c 'import os, sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$staged_target" "$link_dir")"
    ln -s "$rel_link" "$link_dir/$name"
}

# Copy a skills directory while:
#   - preserving symlinks that point inside ~/.agents/ as portable relative symlinks
#   - dereferencing symlinks that point outside ~/.agents/ (e.g. ~/dev/...) so skills remain self-contained
#   - excluding .git/ and __pycache__/
copy_skills_dir() {
    local src_dir="$1"
    local dst_dir="$2"

    mkdir -p "$dst_dir"

    local entry name target resolved
    for entry in "$src_dir"/*(ND); do
        name="${entry:t}"
        if [[ -L "$entry" ]]; then
            target="$(readlink "$entry")"
            resolved="$(python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$entry")"
            if [[ "$resolved" == "$HOME/.agents/"* ]]; then
                log_verbose "Preserving relative symlink to ~/.agents: $name -> $resolved"
                make_relative_staged_symlink "$dst_dir" "$name" "$resolved"
            elif [[ -e "$entry" ]]; then
                log_verbose "Dereferencing external skill symlink: $name -> $target"
                if [[ -d "$entry" ]]; then
                    mkdir -p "$dst_dir/$name"
                    rsync -aL --exclude='.git/' --exclude='__pycache__/' --exclude='*.pyc' "$entry/" "$dst_dir/$name/"
                else
                    cp -L "$entry" "$dst_dir/$name"
                fi
            else
                log_verbose "Skipping broken skill symlink: $name -> $target"
            fi
        elif [[ -d "$entry" ]]; then
            mkdir -p "$dst_dir/$name"
            rsync -a --exclude='.git/' --exclude='__pycache__/' --exclude='*.pyc' "$entry/" "$dst_dir/$name/"
        else
            cp -a "$entry" "$dst_dir/$name"
        fi
    done
}

# Define paths to essential Claude Code settings
CLAUDE_SETTINGS="$HOME/.claude/settings.json"
CLAUDE_MD="$HOME/.claude/CLAUDE.md"
CLAUDE_DIR="$HOME/.claude"

# Define paths to shared global skills
AGENTS_DIR="$HOME/.agents"

# Define paths to essential Antigravity / Gemini settings
GEMINI_DIR="$HOME/.gemini"
GEMINI_CONFIG_DIR="$HOME/.gemini/config"
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

# Check shared ~/.agents skills
if [[ -d "$AGENTS_DIR/skills" ]]; then
    log_verbose "Found shared global skills: $AGENTS_DIR/skills"
    FOUND_SETTINGS=true
fi

# Check Antigravity / Gemini
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
if [[ -d "$GEMINI_CONFIG_DIR" ]]; then
    log_verbose "Found Antigravity global config directory: $GEMINI_CONFIG_DIR"
    FOUND_SETTINGS=true
fi
if [[ -f "$GEMINI_DIR/GEMINI.md" ]]; then
    log_verbose "Found global GEMINI.md: $GEMINI_DIR/GEMINI.md"
    FOUND_SETTINGS=true
fi

if [[ "$FOUND_SETTINGS" == false ]]; then
    log_error "No essential settings found for Claude Code, Gemini Antigravity, or ~/.agents"
    log_error "Expected to find ~/.claude/, ~/.gemini/antigravity-cli/, ~/.gemini/config/, or ~/.agents/skills/"
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
        OUTPUT_PATH="$OUTPUT_FILE"
    else
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

# Copy statusline scripts if they exist
STATUSLINE_SCRIPTS=("$CLAUDE_DIR"/statusline-*.sh(N))
if [[ ${#STATUSLINE_SCRIPTS[@]} -gt 0 ]]; then
    log_verbose "Copying Claude statusline scripts"
    cp "${STATUSLINE_SCRIPTS[@]}" "$TEMP_DIR/.claude/"
fi

# Copy personal slash commands directory if it exists
if [[ -d "$CLAUDE_DIR/commands" ]]; then
    log_verbose "Copying Claude personal slash commands"
    cp -R "$CLAUDE_DIR/commands" "$TEMP_DIR/.claude/commands"
fi

# Copy personal skills directory if it exists
if [[ -d "$CLAUDE_DIR/skills" ]]; then
    log_verbose "Copying Claude personal skills"
    copy_skills_dir "$CLAUDE_DIR/skills" "$TEMP_DIR/.claude/skills"
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

# ----------------- Copy Shared Global Skills (~/.agents) -----------------
if [[ -d "$AGENTS_DIR/skills" || -f "$AGENTS_DIR/.skill-lock.json" ]]; then
    mkdir -p "$TEMP_DIR/.agents"
fi

if [[ -d "$AGENTS_DIR/skills" ]]; then
    log_verbose "Copying shared global skills (~/.agents/skills)"
    mkdir -p "$TEMP_DIR/.agents/skills"
    rsync -a \
        --exclude='.git/' \
        --exclude='__pycache__/' \
        --exclude='*.pyc' \
        "$AGENTS_DIR/skills/" "$TEMP_DIR/.agents/skills/"
fi

if [[ -f "$AGENTS_DIR/.skill-lock.json" ]]; then
    log_verbose "Copying ~/.agents/.skill-lock.json"
    cp "$AGENTS_DIR/.skill-lock.json" "$TEMP_DIR/.agents/.skill-lock.json"
fi

# Back up ~/.local/bin symlinks that point into ~/.agents/skills/ (e.g. chrome-debug, browser-ctl)
if [[ -d "$HOME/.local/bin" ]]; then
    for bin_entry in "$HOME/.local/bin"/*(N); do
        if [[ -L "$bin_entry" ]]; then
            bin_resolved="$(python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$bin_entry")"
            if [[ "$bin_resolved" == "$HOME/.agents/skills/"* ]]; then
                log_verbose "Preserving skill CLI symlink: ~/.local/bin/${bin_entry:t} -> $bin_resolved"
                mkdir -p "$TEMP_DIR/.local/bin"
                make_relative_staged_symlink "$TEMP_DIR/.local/bin" "${bin_entry:t}" "$bin_resolved"
            fi
        fi
    done
fi

# ----------------- Copy Antigravity CLI Files (~/.gemini/antigravity-cli) -----------------
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
    log_verbose "Copying Antigravity bin directory (excluding webm_encoder binary)"
    mkdir -p "$TEMP_DIR/.gemini/antigravity-cli/bin"
    rsync -a --exclude='webm_encoder' "$ANTIGRAVITY_DIR/bin/" "$TEMP_DIR/.gemini/antigravity-cli/bin/"
fi

if [[ -d "$ANTIGRAVITY_DIR/commands" ]]; then
    log_verbose "Copying Antigravity personal slash commands"
    cp -R "$ANTIGRAVITY_DIR/commands" "$TEMP_DIR/.gemini/antigravity-cli/commands"
fi

if [[ -d "$ANTIGRAVITY_DIR/skills" ]]; then
    log_verbose "Copying Antigravity CLI personal skills"
    copy_skills_dir "$ANTIGRAVITY_DIR/skills" "$TEMP_DIR/.gemini/antigravity-cli/skills"
fi

if [[ -d "$ANTIGRAVITY_DIR/agents" ]]; then
    log_verbose "Copying Antigravity custom agents"
    cp -R "$ANTIGRAVITY_DIR/agents" "$TEMP_DIR/.gemini/antigravity-cli/agents"
fi

if [[ -d "$ANTIGRAVITY_DIR/plugins" ]]; then
    log_verbose "Copying Antigravity CLI installed plugins"
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

# ----------------- Copy Antigravity Global Config (~/.gemini/config) -----------------
if [[ -d "$GEMINI_CONFIG_DIR" ]]; then
    mkdir -p "$TEMP_DIR/.gemini/config"

    for cfg_file in config.json mcp_config.json hooks.json skills.json plugins.json rules.json; do
        if [[ -f "$GEMINI_CONFIG_DIR/$cfg_file" ]]; then
            log_verbose "Copying Antigravity config/$cfg_file"
            cp "$GEMINI_CONFIG_DIR/$cfg_file" "$TEMP_DIR/.gemini/config/$cfg_file"
        fi
    done

    if [[ -d "$GEMINI_CONFIG_DIR/skills" ]]; then
        log_verbose "Copying Antigravity global skills (~/.gemini/config/skills)"
        copy_skills_dir "$GEMINI_CONFIG_DIR/skills" "$TEMP_DIR/.gemini/config/skills"
    fi

    if [[ -d "$GEMINI_CONFIG_DIR/rules" ]]; then
        log_verbose "Copying Antigravity global rules (~/.gemini/config/rules)"
        cp -R "$GEMINI_CONFIG_DIR/rules" "$TEMP_DIR/.gemini/config/rules"
    fi

    if [[ -d "$GEMINI_CONFIG_DIR/plugins" ]]; then
        log_verbose "Copying Antigravity global plugins (~/.gemini/config/plugins)"
        mkdir -p "$TEMP_DIR/.gemini/config/plugins"
        rsync -a \
            --exclude='cache/' \
            --exclude='.git/' \
            --exclude='node_modules/' \
            --exclude='__pycache__/' \
            "$GEMINI_CONFIG_DIR/plugins/" "$TEMP_DIR/.gemini/config/plugins/"
    fi

    if [[ -d "$GEMINI_CONFIG_DIR/sidecars" ]]; then
        log_verbose "Copying Antigravity sidecars (~/.gemini/config/sidecars)"
        mkdir -p "$TEMP_DIR/.gemini/config/sidecars"
        rsync -a --exclude='.git/' "$GEMINI_CONFIG_DIR/sidecars/" "$TEMP_DIR/.gemini/config/sidecars/"
    fi
fi

# ----------------- Copy Gemini / Antigravity Root Customizations (~/.gemini) -----------------
if [[ -f "$GEMINI_DIR/GEMINI.md" || -d "$GEMINI_DIR/agents" || -d "$GEMINI_DIR/commands" || -d "$GEMINI_DIR/skills" ]]; then
    mkdir -p "$TEMP_DIR/.gemini"
fi

if [[ -f "$GEMINI_DIR/GEMINI.md" ]]; then
    log_verbose "Copying global ~/.gemini/GEMINI.md"
    cp "$GEMINI_DIR/GEMINI.md" "$TEMP_DIR/.gemini/GEMINI.md"
fi

if [[ -d "$GEMINI_DIR/agents" ]]; then
    log_verbose "Copying global ~/.gemini/agents"
    cp -R "$GEMINI_DIR/agents" "$TEMP_DIR/.gemini/agents"
fi

if [[ -d "$GEMINI_DIR/commands" ]]; then
    log_verbose "Copying global ~/.gemini/commands"
    cp -R "$GEMINI_DIR/commands" "$TEMP_DIR/.gemini/commands"
fi

if [[ -d "$GEMINI_DIR/skills" ]]; then
    log_verbose "Copying global ~/.gemini/skills"
    copy_skills_dir "$GEMINI_DIR/skills" "$TEMP_DIR/.gemini/skills"
fi

# Create zip file preserving staged symlinks (-y) (remove any stale archive first so old entries can't linger)
log_verbose "Creating zip archive..."
rm -f "$OUTPUT_PATH"
if ! (cd "$TEMP_DIR" && zip -ry "$OUTPUT_PATH" . > /dev/null 2>&1); then
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
