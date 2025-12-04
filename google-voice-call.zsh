#!/bin/zsh

# Google Voice Call Script
# Author: Auto-generated improvement
# Version: 2.0.0
# Description: Enhanced Google Voice call launcher with multi-browser support and validation

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Exit codes
EXIT_SUCCESS=0
EXIT_GENERAL_ERROR=1
EXIT_INVALID_INPUT=2
EXIT_NO_BROWSER=3
EXIT_NETWORK_ERROR=4

# Configuration
DEFAULT_BROWSER="chrome"
CONTACTS_FILE="$HOME/.google-voice-contacts.txt"
HISTORY_FILE="$HOME/.google-voice-history.txt"
MAX_HISTORY_ENTRIES=50

# Global options
VERBOSE=false
DRY_RUN=false
BROWSER=""
SHOW_HISTORY=false
ADD_CONTACT=false
CONTACT_NAME=""

# Browser configurations
declare -A BROWSERS=(
    ["chrome"]="Google Chrome"
    ["safari"]="Safari"
    ["firefox"]="Firefox"
    ["edge"]="Microsoft Edge"
    ["default"]="default"
)

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
Google Voice Call Script v2.0.0

Usage: $0 [OPTIONS] <phone_number_or_contact>

ARGUMENTS:
    phone_number    Phone number to call (various formats supported)
    contact         Contact name from your contact list

OPTIONS:
    -h, --help              Show this help message
    -v, --verbose           Enable verbose output
    -d, --dry-run           Show what would be done without executing
    -b, --browser BROWSER   Specify browser (chrome, safari, firefox, edge, default)
    -c, --add-contact NAME  Add number to contacts with given name
    --history               Show call history
    --list-contacts         Show saved contacts

SUPPORTED PHONE NUMBER FORMATS:
    8558701311              # 10-digit US number
    +1-855-870-1311         # International format with country code
    (855) 870-1311          # US format with parentheses
    855.870.1311            # Dotted format

EXAMPLES:
    $0 8558701311                           # Call US number using default browser
    $0 +44-20-7946-0958                     # Call UK number
    $0 -b safari 8558701311                 # Use Safari browser
    $0 --add-contact "Pizza Place" 8558701311  # Add to contacts
    $0 "Pizza Place"                        # Call saved contact
    $0 --history                            # Show call history
    $0 --dry-run 8558701311                # Preview without calling

BROWSERS:
    chrome      Google Chrome (default)
    safari      Safari
    firefox     Firefox
    edge        Microsoft Edge
    default     System default browser

EXIT CODES:
    0  Success
    1  General error
    2  Invalid input
    3  No browser available
    4  Network error
EOF
}

# Validate phone number format
validate_phone_number() {
    local number=$1

    # Remove all non-digit characters except + at the start
    local clean_number
    if [[ "$number" == +* ]]; then
        clean_number=$(echo "$number" | sed 's/[^+0-9]//g')
    else
        clean_number=$(echo "$number" | sed 's/[^0-9]//g')
    fi

    log_verbose "Validating phone number: $number -> $clean_number"

    # Check if empty after cleaning
    if [[ -z "$clean_number" ]]; then
        log_error "No valid digits found in phone number: $number"
        return 1
    fi

    # Check for international format
    if [[ "$clean_number" == +* ]]; then
        # International number should have at least 7 digits after country code
        local digits_only=${clean_number#+*}
        if [[ ${#digits_only} -lt 7 ]] || [[ ${#digits_only} -gt 15 ]]; then
            log_error "Invalid international phone number length: $clean_number"
            return 1
        fi
    else
        # US number should be exactly 10 digits
        if [[ ${#clean_number} -eq 10 ]]; then
            # Valid 10-digit US number
            return 0
        elif [[ ${#clean_number} -eq 11 ]] && [[ "$clean_number" == 1* ]]; then
            # Valid 11-digit US number starting with 1
            return 0
        else
            log_error "Invalid US phone number length: $clean_number (expected 10 or 11 digits)"
            return 1
        fi
    fi

    return 0
}

# Format phone number for Google Voice
format_phone_number() {
    local number=$1

    # Check if the input starts with a plus sign
    if [[ "$number" == +* ]]; then
        # Keep the plus sign and clean everything else except digits
        echo "$number" | sed 's/[^+0-9]//g'
    else
        # Get digits only
        local digits_only=$(echo "$number" | sed 's/[^0-9]//g')

        # Handle different US number formats
        if [[ ${#digits_only} -eq 10 ]]; then
            # 10-digit number, add +1
            echo "+1${digits_only}"
        elif [[ ${#digits_only} -eq 11 ]] && [[ "$digits_only" == 1* ]]; then
            # 11-digit number starting with 1, just add +
            echo "+${digits_only}"
        else
            # Assume US format and add +1
            echo "+1${digits_only}"
        fi
    fi
}

# Check if browser is available
check_browser() {
    local browser=$1

    log_verbose "Checking browser availability: $browser"

    case $browser in
        "default")
            return 0  # Default browser is always "available"
            ;;
        "chrome"|"safari"|"firefox"|"edge")
            local app_name=${BROWSERS[$browser]}
            if [[ -d "/Applications/${app_name}.app" ]]; then
                log_verbose "Found browser: $app_name"
                return 0
            else
                log_verbose "Browser not found: $app_name"
                return 1
            fi
            ;;
        *)
            log_error "Unknown browser: $browser"
            return 1
            ;;
    esac
}

# Find available browser
find_available_browser() {
    log_verbose "Looking for available browsers..."

    # Try preferred browser first
    if [[ -n "$BROWSER" ]]; then
        if check_browser "$BROWSER"; then
            echo "$BROWSER"
            return
        fi
    fi

    # Try default browser from config
    if check_browser "$DEFAULT_BROWSER"; then
        echo "$DEFAULT_BROWSER"
        return
    fi

    # Try browsers in order of preference
    local browsers=("chrome" "safari" "firefox" "edge")
    for browser in "${browsers[@]}"; do
        if check_browser "$browser"; then
            echo "$browser"
            return
        fi
    done

    # Fall back to default system browser
    echo "default"
}

# Open URL in browser
open_in_browser() {
    local url=$1
    local browser=$2

    log_verbose "Opening URL in $browser: $url"

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would open URL in $browser: $url"
        return
    fi

    case $browser in
        "default")
            open "$url"
            ;;
        "chrome")
            open -na "Google Chrome" --args --new-tab "$url"
            ;;
        "safari")
            open -na "Safari" "$url"
            ;;
        "firefox")
            open -na "Firefox" --args --new-tab "$url"
            ;;
        "edge")
            open -na "Microsoft Edge" --args --new-tab "$url"
            ;;
        *)
            log_error "Unsupported browser: $browser"
            exit $EXIT_GENERAL_ERROR
            ;;
    esac
}

# Add contact to contact list
add_contact() {
    local name=$1
    local number=$2

    log_verbose "Adding contact: $name -> $number"

    if [[ "$DRY_RUN" == true ]]; then
        log_info "[DRY RUN] Would add contact: $name -> $number"
        return
    fi

    # Create contacts file if it doesn't exist
    touch "$CONTACTS_FILE"

    # Check if contact already exists
    if grep -q "^${name}:" "$CONTACTS_FILE" 2>/dev/null; then
        log_warning "Contact '$name' already exists, updating..."
        # Remove existing entry
        grep -v "^${name}:" "$CONTACTS_FILE" > "${CONTACTS_FILE}.tmp" 2>/dev/null || touch "${CONTACTS_FILE}.tmp"
        mv "${CONTACTS_FILE}.tmp" "$CONTACTS_FILE"
    fi

    # Add new contact
    echo "${name}:${number}" >> "$CONTACTS_FILE"
    log_info "Contact added: $name -> $number"
}

# Look up contact by name
lookup_contact() {
    local name=$1

    if [[ ! -f "$CONTACTS_FILE" ]]; then
        return 1
    fi

    log_verbose "Looking up contact: $name"

    # Try exact match first
    local number
    number=$(grep "^${name}:" "$CONTACTS_FILE" 2>/dev/null | cut -d':' -f2)

    if [[ -n "$number" ]]; then
        echo "$number"
        return 0
    fi

    # Try case-insensitive match
    number=$(grep -i "^${name}:" "$CONTACTS_FILE" 2>/dev/null | cut -d':' -f2 | head -1)

    if [[ -n "$number" ]]; then
        echo "$number"
        return 0
    fi

    return 1
}

# Show contacts
show_contacts() {
    if [[ ! -f "$CONTACTS_FILE" ]]; then
        log_info "No contacts found. Add contacts with --add-contact option."
        return
    fi

    log_info "Saved contacts:"
    while IFS=':' read -r name number; do
        printf "  %-20s %s\n" "$name" "$number"
    done < "$CONTACTS_FILE"
}

# Add to call history
add_to_history() {
    local number=$1

    if [[ "$DRY_RUN" == true ]]; then
        return
    fi

    log_verbose "Adding to call history: $number"

    # Create history file if it doesn't exist
    touch "$HISTORY_FILE"

    # Add timestamp and number
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "${timestamp}:${number}" >> "$HISTORY_FILE"

    # Keep only last N entries
    tail -$MAX_HISTORY_ENTRIES "$HISTORY_FILE" > "${HISTORY_FILE}.tmp"
    mv "${HISTORY_FILE}.tmp" "$HISTORY_FILE"
}

# Show call history
show_history() {
    if [[ ! -f "$HISTORY_FILE" ]]; then
        log_info "No call history found."
        return
    fi

    log_info "Recent call history:"
    while IFS=':' read -r timestamp number; do
        printf "  %-19s %s\n" "$timestamp" "$number"
    done < "$HISTORY_FILE" | tail -20
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
            -b|--browser)
                if [[ -n "$2" ]]; then
                    BROWSER="$2"
                    shift 2
                else
                    log_error "Browser name required"
                    exit $EXIT_GENERAL_ERROR
                fi
                ;;
            -c|--add-contact)
                if [[ -n "$2" ]]; then
                    ADD_CONTACT=true
                    CONTACT_NAME="$2"
                    shift 2
                else
                    log_error "Contact name required"
                    exit $EXIT_GENERAL_ERROR
                fi
                ;;
            --history)
                SHOW_HISTORY=true
                shift
                ;;
            --list-contacts)
                show_contacts
                exit $EXIT_SUCCESS
                ;;
            -*)
                log_error "Unknown option: $1"
                show_help
                exit $EXIT_GENERAL_ERROR
                ;;
            *)
                # This is the phone number or contact name
                PHONE_INPUT="$1"
                shift
                ;;
        esac
    done
}

# Main function
main() {
    log_verbose "Google Voice Call Script v2.0.0"

    # Handle history display
    if [[ "$SHOW_HISTORY" == true ]]; then
        show_history
        exit $EXIT_SUCCESS
    fi

    # Check if phone number/contact was provided
    if [[ -z "${PHONE_INPUT:-}" ]]; then
        log_error "Phone number or contact name required"
        show_help
        exit $EXIT_INVALID_INPUT
    fi

    local phone_number="$PHONE_INPUT"

    # Try to look up as contact first
    local contact_number
    if contact_number=$(lookup_contact "$PHONE_INPUT"); then
        log_verbose "Found contact: $PHONE_INPUT -> $contact_number"
        phone_number="$contact_number"
    elif [[ ! "$PHONE_INPUT" =~ [0-9] ]]; then
        # Input doesn't contain digits and wasn't found as contact
        log_error "Contact '$PHONE_INPUT' not found and doesn't appear to be a phone number"
        log_info "Use --list-contacts to see available contacts"
        exit $EXIT_INVALID_INPUT
    fi

    # Validate phone number
    if ! validate_phone_number "$phone_number"; then
        exit $EXIT_INVALID_INPUT
    fi

    # Format phone number
    local formatted_number
    formatted_number=$(format_phone_number "$phone_number")
    log_verbose "Formatted number: $formatted_number"

    # Add contact if requested
    if [[ "$ADD_CONTACT" == true ]]; then
        add_contact "$CONTACT_NAME" "$formatted_number"
    fi

    # Find available browser
    local browser
    browser=$(find_available_browser)

    if [[ "$browser" == "default" ]] && ! check_browser "default"; then
        log_error "No suitable browser found"
        exit $EXIT_NO_BROWSER
    fi

    # Construct Google Voice URL
    local url_encoded_number=$(echo "$formatted_number" | sed 's/+/%2B/g')
    local url="https://voice.google.com/calls?a=nc,${url_encoded_number}"

    # Add to history
    add_to_history "$formatted_number"

    # Open in browser
    open_in_browser "$url" "$browser"

    # Display confirmation
    local browser_name=${BROWSERS[$browser]:-$browser}
    log_info "Opening Google Voice call to $formatted_number in $browser_name"
}

# Parse arguments and run main function
parse_args "$@"
main