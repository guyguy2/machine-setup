#!/bin/bash

# Gemini CLI Update Script
# Author: Auto-generated improvement
# Version: 2.0.0
# Description: Checks and updates the Gemini CLI tool with enhanced error handling and features

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Exit codes
EXIT_SUCCESS=0
EXIT_GENERAL_ERROR=1
EXIT_MISSING_DEPENDENCY=2
EXIT_NETWORK_ERROR=3
EXIT_UPDATE_FAILED=4

# Global options
VERBOSE=false
DRY_RUN=false
FORCE_UPDATE=false

# Logging functions
log_info() {
    echo "[INFO] $*"
}

log_verbose() {
    if [[ "$VERBOSE" == true ]]; then
        echo "[VERBOSE] $*"
    fi
}

log_error() {
    echo "[ERROR] $*" >&2
}

log_warning() {
    echo "[WARNING] $*" >&2
}

# Help function
show_help() {
    cat << EOF
Gemini CLI Update Script v2.0.0

Usage: $0 [OPTIONS]

OPTIONS:
    -h, --help      Show this help message
    -v, --verbose   Enable verbose output
    -d, --dry-run   Show what would be done without executing
    -f, --force     Force update even if versions are equal

EXAMPLES:
    $0                    # Check and update if newer version available
    $0 --dry-run          # Show what would be updated without doing it
    $0 --verbose --force  # Force update with detailed output

EXIT CODES:
    0  Success
    1  General error
    2  Missing dependency
    3  Network error
    4  Update failed
EOF
}

# Check dependencies
check_dependencies() {
    log_verbose "Checking required dependencies..."

    local missing_deps=()

    if ! command -v npm &> /dev/null; then
        missing_deps+=("npm")
    fi

    if ! command -v curl &> /dev/null; then
        missing_deps+=("curl")
    fi

    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "Missing required dependencies: ${missing_deps[*]}"
        log_error "Please install the missing dependencies and try again."
        exit $EXIT_MISSING_DEPENDENCY
    fi

    log_verbose "All dependencies are available"
}

# Check network connectivity
check_network() {
    log_verbose "Checking network connectivity..."

    if ! curl -s --connect-timeout 5 https://registry.npmjs.org > /dev/null; then
        log_error "Cannot connect to npm registry. Please check your internet connection."
        exit $EXIT_NETWORK_ERROR
    fi

    log_verbose "Network connectivity confirmed"
}

# Get available version from npm
get_available_version() {
    log_verbose "Fetching available version from npm..."

    local version
    if ! version=$(npm view @google/gemini-cli version 2>/dev/null); then
        log_error "Failed to fetch available version from npm registry"
        exit $EXIT_NETWORK_ERROR
    fi

    if [[ -z "$version" ]]; then
        log_error "Empty version received from npm registry"
        exit $EXIT_NETWORK_ERROR
    fi

    echo "$version"
}

# Get current installed version
get_current_version() {
    log_verbose "Checking current installed version..."

    local version
    if command -v gemini &> /dev/null; then
        version=$(gemini -v 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "")
        if [[ -z "$version" ]]; then
            log_warning "Gemini CLI is installed but version could not be determined"
            echo "0.0.0"
        else
            echo "$version"
        fi
    else
        log_verbose "Gemini CLI not found, treating as not installed"
        echo "0.0.0"
    fi
}

# Function to compare versions (fixed logic)
version_compare() {
    local v1=$1
    local v2=$2

    log_verbose "Comparing versions: $v1 vs $v2"

    # Split versions into arrays
    IFS='.' read -ra V1 <<< "$v1"
    IFS='.' read -ra V2 <<< "$v2"

    # Compare each part
    for i in 0 1 2; do
        local part1=${V1[i]:-0}
        local part2=${V2[i]:-0}

        if [[ $part1 -gt $part2 ]]; then
            log_verbose "$v1 > $v2"
            return 0  # v1 > v2
        elif [[ $part1 -lt $part2 ]]; then
            log_verbose "$v1 < $v2"
            return 1  # v1 < v2
        fi
    done

    log_verbose "$v1 = $v2"
    return 2  # versions are equal (FIXED: was returning 1)
}

# Perform the update
perform_update() {
    local from_version=$1
    local to_version=$2

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would update Gemini CLI from $from_version to $to_version"
        log_info "[DRY RUN] Command: npm install -g @google/gemini-cli@latest"
        return $EXIT_SUCCESS
    fi

    log_info "Updating Gemini CLI from $from_version to $to_version..."
    log_verbose "Running: npm install -g @google/gemini-cli@latest"

    if ! npm install -g @google/gemini-cli@latest; then
        log_error "Failed to update Gemini CLI"
        exit $EXIT_UPDATE_FAILED
    fi

    # Verify the update
    local new_version
    new_version=$(get_current_version)
    if [[ "$new_version" == "$to_version" ]]; then
        echo -e "\033[0;32mSuccessfully updated from $from_version to version $new_version\033[0m"
    else
        log_warning "Update completed but version mismatch. Expected: $to_version, Got: $new_version"
    fi
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit $EXIT_SUCCESS
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -d|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -f|--force)
                FORCE_UPDATE=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit $EXIT_GENERAL_ERROR
                ;;
        esac
    done
}

# Main function
main() {
    log_info "Gemini CLI Update Script v2.0.0"

    # Check dependencies and network
    check_dependencies
    check_network

    log_info "Checking Gemini CLI version..."

    # Get versions
    local available_version current_version
    available_version=$(get_available_version)
    current_version=$(get_current_version)

    log_info "Available version: $available_version"
    log_info "Current version: $current_version"

    # Compare versions
    local comparison_result
    version_compare "$available_version" "$current_version"
    comparison_result=$?

    case $comparison_result in
        0)
            # Available version is newer
            log_info "New version available!"
            perform_update "$current_version" "$available_version"
            ;;
        1)
            # Current version is newer (shouldn't happen normally)
            log_warning "Current version ($current_version) is newer than available version ($available_version)"
            if [[ "$FORCE_UPDATE" == true ]]; then
                log_info "Force update requested"
                perform_update "$current_version" "$available_version"
            else
                log_info "No action needed. Use --force to downgrade if desired."
            fi
            ;;
        2)
            # Versions are equal
            if [[ "$FORCE_UPDATE" == true ]]; then
                log_info "Versions are equal but force update requested"
                perform_update "$current_version" "$available_version"
            else
                log_info "Already up to date (version $current_version)"
            fi
            ;;
    esac

    log_info "Done."
}

# Parse arguments and run main function
parse_args "$@"
main