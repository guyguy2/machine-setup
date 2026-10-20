#!/bin/bash
# Eastwood-themed status line for Claude Code
# Matches the oh-my-zsh eastwood theme format:
# [git_dirty][branch][~/path] $

set -euo pipefail

# Read JSON input from stdin
input=$(cat)

# Extract values from JSON
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd')
model=$(echo "$input" | jq -r '.model.display_name // .model.id')
version=$(echo "$input" | jq -r '.version')
elapsed_ms=$(echo "$input" | jq -r '.cost.total_duration_ms // 0')

# Extract context window information
context_size=$(echo "$input" | jq -r '.context_window.context_window_size // 200000')
current_usage=$(echo "$input" | jq -r '.context_window.current_usage')

# Convert session duration from milliseconds to minutes and seconds
elapsed_seconds=$((elapsed_ms / 1000))
elapsed_minutes=$((elapsed_seconds / 60))
elapsed_seconds_remainder=$((elapsed_seconds % 60))

# Color codes (dimmed for status line)
GREEN='\033[32m'
CYAN='\033[36m'
RED='\033[31m'
YELLOW='\033[33m'
MAGENTA='\033[35m'
RESET='\033[0m'

# Hostname (so it's obvious which machine this session is on)
host_display="${MAGENTA}[🖥 $(hostname -s)]${RESET}"

# Git status detection
git_status=""
if git -C "$cwd" rev-parse --git-dir > /dev/null 2>&1; then
    # Get current branch
    branch=$(git -C "$cwd" branch --show-current 2>/dev/null || echo "")

    if [ -n "$branch" ]; then
        # Check if dirty (using --no-optional-locks to avoid lock issues)
        if ! git -C "$cwd" --no-optional-locks diff-index --quiet HEAD -- 2>/dev/null; then
            dirty="${RED}*${RESET}"
        else
            dirty=""
        fi

        # Build git status in eastwood format: [dirty][branch] with emoji
        if [ -n "$dirty" ]; then
            git_status="${RED}🔥${RESET} ${dirty}${GREEN}[${branch}]${RESET}"
        else
            git_status="${GREEN}🌿 [${branch}]${RESET}"
        fi
    fi
fi

# Convert full path to ~-based path
display_path="${cwd/#$HOME/\~}"

# Format session duration display
if [ "$elapsed_ms" -gt 0 ]; then
    elapsed_display="${YELLOW}[⏱ ${elapsed_minutes}m ${elapsed_seconds_remainder}s]${RESET}"
else
    elapsed_display=""
fi

# Calculate context window usage using current_usage field
if [ "$current_usage" != "null" ]; then
    # Extract individual token counts from current_usage
    input_tokens=$(echo "$current_usage" | jq -r '.input_tokens // 0')
    cache_creation=$(echo "$current_usage" | jq -r '.cache_creation_input_tokens // 0')
    cache_read=$(echo "$current_usage" | jq -r '.cache_read_input_tokens // 0')

    # Calculate total current context (input + cache creation + cache read)
    total_tokens=$((input_tokens + cache_creation + cache_read))

    if [ "$context_size" -gt 0 ]; then
        percent_used=$((total_tokens * 100 / context_size))
        # Format with K suffix for readability
        total_tokens_k=$((total_tokens / 1000))
        context_size_k=$((context_size / 1000))

        # Color code based on usage percentage
        if [ "$percent_used" -ge 80 ]; then
            context_color="${RED}"
        elif [ "$percent_used" -ge 60 ]; then
            context_color="${YELLOW}"
        else
            context_color="${GREEN}"
        fi

        context_display="${context_color}[📊 ${total_tokens_k}k/${context_size_k}k ${percent_used}%]${RESET}"
    else
        context_display=""
    fi
else
    context_display=""
fi

# Build a dotted matrix progress bar (width=10 braille cells)
make_bar() {
    local pct=$1
    local width=10
    local filled=$(( (pct * width + 50) / 100 ))
    local empty=$(( width - filled ))
    local bar=""
    local i
    for ((i=0; i<filled; i++)); do bar="${bar}⣿"; done
    for ((i=0; i<empty; i++)); do bar="${bar}⠂"; done
    printf '%s' "$bar"
}

# Format a resets_at Unix epoch timestamp as local time (e.g., "1am", "5pm")
format_reset_time() {
    local resets_at="$1"
    [ -z "$resets_at" ] && return
    # resets_at is a Unix epoch integer
    local epoch
    epoch=$(echo "$resets_at" | grep -E '^[0-9]+$') || return
    [ -z "$epoch" ] && return
    date -d "@$epoch" "+%I%p" 2>/dev/null | sed 's/^0//' | tr '[:upper:]' '[:lower:]'
}

# Rate limits display (5-hour and 7-day windows)
rate_display=""
rate_5h_pct=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
rate_7d_pct=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')
rate_5h_reset=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // empty')
rate_7d_reset=$(echo "$input" | jq -r '.rate_limits.seven_day.resets_at // empty')

if [ -n "$rate_5h_pct" ] || [ -n "$rate_7d_pct" ]; then
    if [ -n "$rate_5h_pct" ]; then
        rate_5h_int=${rate_5h_pct%.*}
        if [ "${rate_5h_int:-0}" -ge 80 ]; then
            rate_color="${RED}"
        elif [ "${rate_5h_int:-0}" -ge 60 ]; then
            rate_color="${YELLOW}"
        else
            rate_color="${GREEN}"
        fi
        reset_5h=$(format_reset_time "$rate_5h_reset") || true
        reset_5h_suffix=""
        [ -n "$reset_5h" ] && reset_5h_suffix="→${reset_5h}"
        bar_5h=$(make_bar "${rate_5h_int:-0}")
        rate_display="${rate_color}5h ${bar_5h} ${rate_5h_int}%${reset_5h_suffix}${RESET}"
    fi
    if [ -n "$rate_7d_pct" ]; then
        rate_7d_int=${rate_7d_pct%.*}
        if [ "${rate_7d_int:-0}" -ge 80 ]; then
            rate_color="${RED}"
        elif [ "${rate_7d_int:-0}" -ge 60 ]; then
            rate_color="${YELLOW}"
        else
            rate_color="${GREEN}"
        fi
        bar_7d=$(make_bar "${rate_7d_int:-0}")
        if [ -n "$rate_display" ]; then
            rate_display="${rate_display}  ${rate_color}7d ${bar_7d} ${rate_7d_int}%${RESET}"
        else
            rate_display="${rate_color}7d ${bar_7d} ${rate_7d_int}%${RESET}"
        fi
    fi
fi

# Effort level display (optional - only shown when present)
effort_level=$(echo "$input" | jq -r '.effort.level // empty')
effort_display=""
if [ -n "$effort_level" ]; then
    case "$effort_level" in
        low)    effort_emoji="💤" ;;
        medium) effort_emoji="🧠" ;;
        high)   effort_emoji="⚡" ;;
        xhigh)  effort_emoji="🔥" ;;
        max)    effort_emoji="🚀" ;;
        *)      effort_emoji="🤔" ;;
    esac
    effort_display="${YELLOW}[${effort_emoji} ${effort_level}]${RESET}"
fi

# Line 1: hostname, git status, path, model, version, effort, context usage, session duration
echo -e "${host_display} ${git_status} ${CYAN}[${display_path}]${RESET} ${YELLOW}[🤔 ${model}]${RESET} ${effort_display} ${GREEN}[v${version}]${RESET} ${context_display} ${elapsed_display}"
# Line 2: rate limits with progress bars (only when data is available)
if [ -n "$rate_display" ]; then
    echo -e "    ${rate_display}"
fi
