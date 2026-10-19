#!/usr/bin/env bash
# Rebuild this Pi's setup on a fresh Raspberry Pi OS / Debian image from ./snapshot.
# Usage: restore.sh [--dry-run] [--only step,step,...]
# Steps (run in this order): apt-sources apt brew uv npm omzsh dotfiles shell systemd
# Safe to re-run. Existing dotfiles are moved to ~/.pi-restore-backup-<timestamp>/.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
snap=$here/snapshot
all_steps=(apt-sources apt brew uv npm omzsh dotfiles shell systemd)
brew_bin=/home/linuxbrew/.linuxbrew/bin/brew

dry=0
only=("${all_steps[@]}")
while (( $# )); do
  case $1 in
    --dry-run) dry=1 ;;
    --only) shift; IFS=, read -ra only <<< "${1:?--only needs a list}" ;;
    *) echo "usage: ${0##*/} [--dry-run] [--only step,step,...]" >&2; exit 2 ;;
  esac
  shift
done

say() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }
run() { if (( dry )); then printf '  [dry-run] %s\n' "$*"; else "$@"; fi; }
want() { local s; for s in "${only[@]}"; do [[ $s == "$1" ]] && return 0; done; return 1; }
need() { [[ -e $snap/$1 ]] || { echo "  missing snapshot/$1, skipping"; return 1; }; }

[[ -d $snap ]] || { echo "no snapshot/ next to restore.sh" >&2; exit 1; }
(( dry )) || sudo true

if want apt-sources; then
  say "apt: third-party sources (nodesource, tailscale, ...)"
  if need apt-sources; then
    for f in "$snap"/apt-sources/*; do
      [[ -f $f ]] || continue
      case $f in
        *.gpg|*.asc) run sudo install -m 644 "$f" /usr/share/keyrings/ ;;
        *)           run sudo install -m 644 "$f" /etc/apt/sources.list.d/ ;;
      esac
    done
  fi
fi

if want apt; then
  say "apt: manually installed packages"
  if need apt-manual.txt; then
    run sudo apt-get update
    # Skip names this image's repos don't offer (renamed/removed) instead of failing the lot.
    mapfile -t avail < <(apt-cache pkgnames | sort)
    mapfile -t pkgs < <(comm -12 "$snap/apt-manual.txt" <(printf '%s\n' "${avail[@]}"))
    comm -23 "$snap/apt-manual.txt" <(printf '%s\n' "${avail[@]}") | sed 's/^/  not available: /'
    (( ${#pkgs[@]} )) && run sudo apt-get install -y "${pkgs[@]}"
  fi
fi

if want brew; then
  say "Homebrew + Brewfile"
  if [[ ! -x $brew_bin ]]; then
    echo "  installing Homebrew"
    if (( dry )); then echo "  [dry-run] official Homebrew install.sh (NONINTERACTIVE=1)"
    else NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
  fi
  if need Brewfile; then
    if (( dry )); then echo "  [dry-run] brew bundle --file=snapshot/Brewfile"
    else "$brew_bin" bundle --file="$snap/Brewfile"
    fi
  fi
fi

# Tools installed by uv/npm may live under brew's bin, so look there too.
export PATH="$PATH:/home/linuxbrew/.linuxbrew/bin"

if want uv; then
  say "uv tools"
  if need uv-tools.txt && have uv; then
    while read -r t; do [[ -n $t ]] && run uv tool install "$t"; done < "$snap/uv-tools.txt"
  fi
fi

if want npm; then
  say "npm global packages"
  if need npm-global.txt && have npm; then
    mapfile -t n < "$snap/npm-global.txt"
    (( ${#n[@]} )) && run sudo npm install -g "${n[@]}" || echo "  none"
  fi
fi

if want omzsh; then
  say "Oh My Zsh"
  if [[ -d $HOME/.oh-my-zsh ]]; then echo "  already installed"
  elif (( dry )); then echo "  [dry-run] official Oh My Zsh install.sh (RUNZSH=no CHSH=no KEEP_ZSHRC=yes)"
  else RUNZSH=no CHSH=no KEEP_ZSHRC=yes sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
  fi
fi

if want dotfiles; then
  say "dotfiles -> \$HOME"
  if need dotfiles; then
    bak=$HOME/.pi-restore-backup-$(date +%Y%m%d-%H%M%S)
    while IFS= read -r -d '' f; do
      rel=${f#"$snap/dotfiles/"}
      dest=$HOME/$rel
      if [[ -e $dest ]] && cmp -s "$f" "$dest"; then continue; fi
      if [[ -e $dest ]]; then
        run mkdir -p "$bak/$(dirname "$rel")"
        run mv "$dest" "$bak/$rel"
      fi
      run mkdir -p "$(dirname "$dest")"
      run cp -a "$f" "$dest"
      echo "  restored ~/$rel"
    done < <(find "$snap/dotfiles" -type f -print0)
    [[ -d $bak ]] && echo "  previous versions saved in $bak"
  fi
fi

if want shell; then
  say "login shell -> zsh"
  zsh_path=$(command -v zsh || true)
  if [[ -z $zsh_path ]]; then echo "  zsh not installed (run the apt step)"
  elif [[ $(getent passwd "$USER" | cut -d: -f7) == "$zsh_path" ]]; then echo "  already zsh"
  else run sudo chsh -s "$zsh_path" "$USER"
  fi
fi

if want systemd; then
  say "systemd"
  if need systemd-user-enabled.txt; then
    run systemctl --user daemon-reload
    # Only enable user units whose file we restored; stock ones come with the image.
    while read -r u; do
      [[ -f $HOME/.config/systemd/user/$u ]] && run systemctl --user enable "$u"
    done < "$snap/systemd-user-enabled.txt"
  fi
  if [[ -f $snap/systemd-system-enabled.txt ]]; then
    now=$(mktemp); systemctl list-unit-files --state=enabled --no-legend | awk '{print $1}' | sort > "$now"
    missing=$(comm -23 "$snap/systemd-system-enabled.txt" "$now" | tr '\n' ' ')
    rm -f "$now"
    [[ -n $missing ]] && echo "  enabled on the old system but not here (review; not auto-enabled): $missing"
  fi
fi

say "Restore finished. Manual follow-ups"
cat <<'MSG'
  - Open a new terminal (or log out/in) so zsh and ~/.zshrc take effect.
  - gh auth login        (then: gh auth setup-git)
  - tailscale up
  - claude               (log in; installed via the Brewfile cask)
  - OpenHuman / OpenClaw: run raspberry-pi/bin/openhuman and raspberry-pi/bin/openclaw once;
    each installs itself on first run (see snapshot/versions.txt for last-known versions).
  - Re-create ~/.ssh keys and any API tokens yourself; they are intentionally not backed up.
MSG
