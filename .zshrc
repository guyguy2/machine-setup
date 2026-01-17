# Path to oh-my-zsh installation
export ZSH="$HOME/.oh-my-zsh"

# Set theme
ZSH_THEME="robbyrussell"

# Plugins
plugins=(git docker)

# Load oh-my-zsh
source $ZSH/oh-my-zsh.sh

# ------------------------------------------------------------------------------
# Environment Variables
# ------------------------------------------------------------------------------

export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"

# PATH configuration
path=(
    "$HOME/.local/bin"
    "/opt/homebrew/bin"
    "$HOME/Library/Android/sdk/platform-tools"
    $path
)

# ------------------------------------------------------------------------------
# Completions
# ------------------------------------------------------------------------------

fpath=("$HOME/.docker/completions" $fpath)

# ------------------------------------------------------------------------------
# Aliases
# ------------------------------------------------------------------------------

# General
alias c='clear'

# Python
alias pip='pip3'
alias python='python3'
alias py='python3'

# npm
alias ni='npm install'
alias ns='npm start'

# Git
alias gacp='git add . && git commit -m "progress" && git push'

# Claude
alias cld='claude'
alias clda='cld --dangerously-skip-permissions'
alias clds='cld --dangerously-skip-permissions --model=sonnet'
alias cldo='cld --dangerously-skip-permissions --model=opus'

# Misc
alias fabric='fabric-ai'
alias gemini='gemini -y'
alias md='mkdir'

# ------------------------------------------------------------------------------
# Functions
# ------------------------------------------------------------------------------

upd() {
    local counter_file="$HOME/.upd_counter"

    # Run update and upgrade
    brew update && brew upgrade

    # Update docker-compose if Docker is running
    if docker info &>/dev/null; then
        local compose_dirs=(
            "/Users/guy/dev/tools/n8n"
            "/Users/guy/dev/tools/agent_zero"
        )

        for compose_dir in "${compose_dirs[@]}"; do
            if [[ -f "$compose_dir/docker-compose.yml" ]] || [[ -f "$compose_dir/docker-compose.yaml" ]]; then
                echo "Updating docker-compose in $compose_dir..."
                (cd "$compose_dir" && docker-compose pull && docker-compose up -d)
            else
                echo "Skipping $compose_dir (no docker-compose.yml found)"
            fi
        done

        echo "Cleaning up old Docker images..."
        docker image prune -f
    else
        echo "Skipping docker-compose (Docker not running)"
    fi

    # Track cleanup runs
    local count=0
    if [[ -f "$counter_file" ]]; then
        count=$(cat "$counter_file")
    fi

    count=$((count + 1))

    if [[ $count -ge 5 ]]; then
        echo "Running brew cleanup (run $count/5)..."
        brew cleanup
        count=0
    else
        echo "Skipping brew cleanup (run $count/5)"
    fi

    echo "$count" >| "$counter_file"
}

# ------------------------------------------------------------------------------
# Tool Integrations
# ------------------------------------------------------------------------------

[[ "$TERM_PROGRAM" == "kiro" ]] && . "$(kiro --locate-shell-integration-path zsh)"

# Initialize zoxide (smarter cd command)
eval "$(zoxide init zsh)"
