#!/usr/bin/env bash
# First command on a fresh Raspberry Pi OS image (over SSH, as the normal user):
#   curl -fsSL https://raw.githubusercontent.com/guyguy2/machine-setup/main/raspberry-pi/bootstrap.sh | bash
# Installs git, clones this public repo to ~/dev/machine-setup and runs restore.sh (extra arguments are passed on,
# e.g. `| bash -s -- --dry-run`). See README.md next to this file.
set -euo pipefail

repo=https://github.com/guyguy2/machine-setup.git
dest=$HOME/dev/machine-setup

[[ $(id -u) -ne 0 ]] || { echo "run as your normal user, not root (it uses sudo where needed)" >&2; exit 1; }
command -v git >/dev/null || { sudo apt-get update && sudo apt-get install -y git; }
if [[ -d $dest/.git ]]; then git -C "$dest" pull --ff-only
else mkdir -p "$HOME/dev" && git clone "$repo" "$dest"
fi
# stdin is this script when piped from curl; give restore.sh the terminal for its prompts (sudo, gh, passphrase).
exec "$dest/raspberry-pi/restore.sh" "$@" </dev/tty
