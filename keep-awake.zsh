#!/usr/bin/env zsh

# keep-awake.zsh
# Temporarily keeps the Mac awake with the lid closed (works on battery, no display)
# using `pmset disablesleep`, then restores normal sleep behavior automatically.

set -euo pipefail

DEFAULT_MINUTES=60
SCRIPT_NAME=$(basename "$0")

# Logging functions
log_info() {
    echo "[INFO] $*"
}

log_error() {
    echo "[ERROR] $*" >&2
}

log_warning() {
    echo "[WARNING] $*" >&2
}

log_success() {
    echo "[SUCCESS] $*"
}

# Show help message
show_help() {
    cat << EOF
Usage: $SCRIPT_NAME [OPTIONS]

Temporarily prevents this Mac from sleeping when the lid is closed, even on
battery with no external display. Uses 'pmset disablesleep', then turns it
back off when the time is up, on Ctrl-C, or when the terminal closes.

The script runs in the foreground and must stay running. It re-runs itself
with sudo once at the start so the revert later does not need a password
prompt (nobody is there to type it with the lid closed).

Options:
  -m, --minutes N       Minutes to stay awake (default: $DEFAULT_MINUTES)
      --off             Turn lid-closed sleep prevention off now and exit
      --status          Show whether sleep prevention is currently on
  -v, --verbose         Verbose output
  -h, --help            Show this help message

Examples:
  $SCRIPT_NAME                 # Stay awake for $DEFAULT_MINUTES minutes
  $SCRIPT_NAME -m 120          # Stay awake for 2 hours
  $SCRIPT_NAME --status        # Check current state
  $SCRIPT_NAME --off           # Recover if the script was killed (kill -9, crash)

Notes:
  - The Mac stays fully active and drains the battery quickly. Avoid putting
    it in a bag; the closed lid and covered vents can cause overheating.
  - macOS still sleeps or shuts down when the battery reaches a critical level.
  - The setting persists across reboots until turned off. If the script is
    force-killed, run '$SCRIPT_NAME --off'.

Exit codes:
  0 - Success
  1 - General error
  2 - Invalid input
EOF
}

# Parse command-line arguments
VERBOSE=false
MINUTES=$DEFAULT_MINUTES
ACTION="run"

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
        -m|--minutes)
            if [[ $# -lt 2 ]]; then
                log_error "$1 requires a value"
                exit 2
            fi
            MINUTES="$2"
            shift 2
            ;;
        --off)
            ACTION="off"
            shift
            ;;
        --status)
            ACTION="status"
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 2
            ;;
    esac
done

# Function for verbose logging
log_verbose() {
    if [[ "$VERBOSE" == true ]]; then
        echo "[VERBOSE] $*"
    fi
}

if [[ "$(uname)" != "Darwin" ]]; then
    log_error "This script only works on macOS (requires pmset)"
    exit 1
fi

if ! [[ "$MINUTES" =~ ^[0-9]+$ ]] || (( MINUTES < 1 )); then
    log_error "Minutes must be a positive whole number, got: $MINUTES"
    exit 2
fi

# Prints "1" or "0"
sleep_disabled() {
    pmset -g | awk '/SleepDisabled/ {print $2}'
}

if [[ "$ACTION" == "status" ]]; then
    if [[ "$(sleep_disabled)" == "1" ]]; then
        log_info "Lid-closed sleep prevention is ON"
    else
        log_info "Lid-closed sleep prevention is OFF"
    fi
    exit 0
fi

# Run as root for the whole session so the revert never needs a password
if [[ $EUID -ne 0 ]]; then
    log_verbose "Re-running with sudo"
    exec sudo -- "$0" "$@"
fi

if [[ "$ACTION" == "off" ]]; then
    pmset disablesleep 0
    log_success "Lid-closed sleep prevention turned OFF"
    exit 0
fi

SLEEP_PID=""

cleanup() {
    trap - EXIT INT TERM HUP
    if [[ -n "$SLEEP_PID" ]]; then
        kill "$SLEEP_PID" 2>/dev/null || true
    fi
    pmset disablesleep 0
    log_info "Lid-closed sleep prevention turned OFF"
}

# Registered before enabling so an interrupt can never leave it on
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

pmset disablesleep 1
END_TIME=$(date -v+"${MINUTES}"M "+%H:%M")
log_success "Lid-closed sleep prevention ON for $MINUTES minute(s), until $END_TIME"
log_warning "Keep this terminal session running. Ctrl-C to stop early."

# Background sleep + wait so signals are handled immediately
sleep $(( MINUTES * 60 )) &
SLEEP_PID=$!
log_verbose "Waiting on sleep pid $SLEEP_PID"
wait "$SLEEP_PID"
