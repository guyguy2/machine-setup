#!/usr/bin/env bash
# Snapshot this Pi's settings into ./snapshot (dotfiles, package lists, units, ~/dev repo list).
# Usage: save.sh [--push]   --push: commit the snapshot and push it to origin.
# bash, not zsh: restore.sh runs on a fresh image before zsh is installed.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
snap=$here/snapshot

# Paths under $HOME to back up. Secrets, agent state and caches are deliberately absent:
# ~/.ssh (Raspberry Pi Imager installs the authorized key), ~/.claude.json, ~/.hermes, ~/.openclaw, ~/.config/gws, history files, ~/.cache.
# (~/.hermes holds Hermes's data and its installer checkout: restore.sh reinstalls Hermes with the official installer instead.)
dotfiles=(
  .zshrc .zprofile .gitconfig
  .config/zellij .config/lxterminal .config/kanshi .config/wf-panel-pi
  .config/mimeapps.list
  .config/systemd/user/pi-status.service
  .config/systemd/user/hermes-dashboard.service .config/systemd/user/hermes-proxy.service .config/systemd/user/openclaw-gateway.service
  .claude/CLAUDE.md .claude/settings.json .claude/statusline-eastwood.sh
  .claude/skills/gws .claude/skills/pihole .claude/skills/openclaw .claude/skills/hermes .claude/skills/train-agents
)

say() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

push=0
case "${1:-}" in
  --push) push=1 ;;
  # --to DIR: write the snapshot to a new DIR instead, to compare with ./snapshot (bin/pi-checkup drift does).
  --to)
    snap=${2:?usage: ${0##*/} --to DIR}
    [[ ! -e $snap ]] || { echo "save.sh: $snap already exists; --to needs a new directory" >&2; exit 2; } ;;
  "") ;;
  *) echo "usage: ${0##*/} [--push | --to DIR]" >&2; exit 2 ;;
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
apt-mark showmanual | LC_ALL=C sort > "$snap/apt-manual.txt"
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

say "system settings (hostname, timezone)"
{
  echo "hostname: $(hostname)"
  echo "timezone: $(timedatectl show -p Timezone --value 2>/dev/null || cat /etc/timezone)"
} > "$snap/system.txt"

say "git repos in ~/dev (restore.sh clones the missing ones)"
# "<dir> <origin url>" for real directories; symlinks into this repo are recreated by the links step.
for g in "$HOME"/dev/*/.git; do
  d=${g%/.git}
  [[ -L $d ]] && continue
  u=$(git -C "$d" remote get-url origin 2>/dev/null) || { echo "  no origin, not listed: ${d##*/}" >&2; continue; }
  echo "${d##*/} $u"
done | sort > "$snap/repos.txt"

say "versions (reference only)"
{
  # shellcheck disable=SC1091
  echo "os: $(. /etc/os-release && echo "$PRETTY_NAME")"
  echo "tailscale: $(tailscale version 2>/dev/null | head -1 || echo none)"
  echo "openclaw: $(jq -r .version "$HOME/dev/openclaw_node/node_modules/openclaw/package.json" 2>/dev/null || echo none)"
  echo "hermes: $(hermes --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
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
# The repo is public: keep the tailnet's name out (write <tailnet> instead).
tailnet=$(tailscale status --json 2>/dev/null | jq -r '.MagicDNSSuffix // empty' 2>/dev/null || true)
if [[ -n $tailnet ]] && grep -rIlF "$tailnet" "$snap"; then
  echo "save.sh: the tailnet name $tailnet appears in the files above; replace it with <tailnet>. Not committing." >&2
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

# A restore only gets what is on GitHub, so flag work that isn't there yet (save.sh never commits code).
say "unpushed work in ~/dev"
clean=1
for g in "$HOME"/dev/*/.git; do
  d=${g%/.git}
  [[ -L $d ]] && continue
  dirty=$(git -C "$d" status --porcelain 2>/dev/null | wc -l)
  ahead=$(git -C "$d" rev-list --count '@{u}..HEAD' 2>/dev/null || echo "no upstream")
  if (( dirty )) || [[ $ahead != 0 ]]; then
    clean=0
    printf '  \033[1;33m%s\033[0m: %s uncommitted file(s), %s unpushed commit(s)\n' "${d/#$HOME/~}" "$dirty" "$ahead"
  fi
done
(( clean )) && echo "  none"
say "done: $snap"
