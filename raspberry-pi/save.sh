#!/usr/bin/env bash
# Snapshot this Pi's settings into ./snapshot (dotfiles, package lists, units).
# Usage: save.sh [--push]   --push: commit the snapshot and push it to origin.
# bash, not zsh: restore.sh runs on a fresh image before zsh is installed.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
snap=$here/snapshot

# Paths under $HOME to back up. Secrets and caches are deliberately absent:
# ~/.ssh, ~/.claude.json, ~/.hermes, ~/.openclaw, history files, ~/.cache.
dotfiles=(
  .zshrc .gitconfig
  .config/zellij .config/lxterminal .config/kanshi .config/wf-panel-pi
  .config/mimeapps.list
  .config/systemd/user/openhuman.service
  .claude/CLAUDE.md .claude/settings.json .claude/statusline-eastwood.sh
)

say() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

push=0
case "${1:-}" in
  --push) push=1 ;;
  "") ;;
  *) echo "usage: ${0##*/} [--push]" >&2; exit 2 ;;
esac

# Start clean so files deleted on this machine disappear from the snapshot.
rm -rf "$snap"
mkdir -p "$snap/dotfiles" "$snap/apt-sources"

say "dotfiles"
for p in "${dotfiles[@]}"; do
  if [[ -e $HOME/$p ]]; then
    (cd "$HOME" && cp -a --parents "$p" "$snap/dotfiles/")
  else
    echo "  skip (missing): $p"
  fi
done

say "apt: manual packages + third-party sources"
apt-mark showmanual | sort > "$snap/apt-manual.txt"
# Everything except the stock Debian and Raspberry Pi lists (the image supplies those).
for f in /etc/apt/sources.list.d/*; do
  case ${f##*/} in debian.sources|raspi.sources|raspi.list) continue ;; esac
  cp "$f" "$snap/apt-sources/"
  # Public signing keys the source refers to.
  grep -ho '/usr/share/keyrings/[^] ]*' "$f" 2>/dev/null | sort -u | while read -r k; do
    [[ -f $k ]] && cp "$k" "$snap/apt-sources/"
  done
done

if have brew; then
  say "homebrew: Brewfile"
  brew bundle dump --force --no-npm --no-uv --no-describe --file="$snap/Brewfile" >/dev/null
fi

if have uv; then
  say "uv tools"
  uv tool list 2>/dev/null | awk '!/^-/ && !/^No tools/ && NF {print $1}' | sort > "$snap/uv-tools.txt"
fi

if have npm; then
  say "npm global packages"
  npm ls -g --depth=0 --json 2>/dev/null | jq -r '.dependencies // {} | keys[]' \
    | grep -vxE 'npm|corepack' | sort > "$snap/npm-global.txt" || true
fi

say "systemd enabled units"
systemctl list-unit-files --state=enabled --no-legend 2>/dev/null | awk '{print $1}' | sort > "$snap/systemd-system-enabled.txt"
systemctl --user list-unit-files --state=enabled --no-legend 2>/dev/null | awk '{print $1}' | sort > "$snap/systemd-user-enabled.txt"

say "versions (reference only)"
{
  # shellcheck disable=SC1091
  echo "os: $(. /etc/os-release && echo "$PRETTY_NAME")"
  echo "open-human: $(dpkg-query -W -f='${Version}' open-human 2>/dev/null || echo none)"
  echo "openclaw: $(jq -r .version "$HOME/dev/openclaw_node/node_modules/openclaw/package.json" 2>/dev/null || echo none)"
  echo "hermes-agent: $(brew list --versions hermes-agent 2>/dev/null | awk '{print $2}' || true)"
} > "$snap/versions.txt"

# Keep the snapshot small and free of credentials: text and scripts only.
say "size + secret scan"
big=$(find "$snap" -type f -size +100k)
if [[ -n $big ]]; then
  echo "save.sh: files over 100 KB in the snapshot, not committing:" >&2
  echo "$big" >&2
  exit 1
fi
pat='(api[_-]?key|token|secret|passw(or)?d)["'"'"']?[[:space:]]*[=:][[:space:]]*["'"'"']?[A-Za-z0-9_./+-]{16,}|sk-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|BEGIN [A-Z ]*PRIVATE KEY'
if grep -rEIn --exclude='*.gpg' --exclude='*.asc' "$pat" "$snap"; then
  echo "save.sh: possible secrets in the snapshot (above); not committing." >&2
  exit 1
fi
echo "  clean"

if (( push )); then
  say "git commit + push"
  root=$(git -C "$here" rev-parse --show-toplevel)
  rel=$(realpath --relative-to="$root" "$snap")
  git -C "$root" add -A -- "$rel"
  if git -C "$root" diff --cached --quiet -- "$rel"; then
    echo "  no changes"
  else
    git -C "$root" commit -q -m "raspberry-pi: snapshot $(date +%F) $(hostname)" -- "$rel"
    git -C "$root" push -q && echo "  pushed"
  fi
fi
say "done: $snap"
