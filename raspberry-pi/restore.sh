#!/usr/bin/env bash
# Rebuild this Pi's setup on a fresh Raspberry Pi OS / Debian image from ./snapshot. README.md explains every step.
# No secrets are backed up: logins and API keys are set up by hand afterwards (listed at the end).
# Usage: restore.sh [--dry-run] [--only step,step,...]
# Steps (run in this order): apt-sources apt system tailscale brew uv npm omzsh dotfiles github repos links
#                            pihole agents pi-status shell systemd
# Safe to re-run. Existing files are moved to ~/.pi-restore-backup-<timestamp>/.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
snap=$here/snapshot
all_steps=(apt-sources apt system tailscale brew uv npm omzsh dotfiles github repos links pihole agents pi-status shell systemd)
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

restore_apt_sources() {
  need apt-sources || return 0
  local f
  for f in "$snap"/apt-sources/*; do
    [[ -f $f ]] || continue
    case $f in
      *.gpg|*.asc) run sudo install -m 644 "$f" /usr/share/keyrings/ ;;
      *)           run sudo install -m 644 "$f" /etc/apt/sources.list.d/ ;;
    esac
  done
}

if want apt-sources; then
  say "apt: third-party sources (nodesource, tailscale, ...)"
  restore_apt_sources
fi

if want apt; then
  say "apt: manually installed packages"
  if need apt-manual.txt; then
    run sudo apt-get update
    # Skip names this image's repos don't offer (renamed/removed) instead of failing the lot.
    # comm needs both lists sorted the same way whatever the locale of the machine that saved them.
    mapfile -t avail < <(apt-cache pkgnames | LC_ALL=C sort)
    mapfile -t want_pkgs < <(LC_ALL=C sort "$snap/apt-manual.txt")
    mapfile -t pkgs < <(LC_ALL=C comm -12 <(printf '%s\n' "${want_pkgs[@]}") <(printf '%s\n' "${avail[@]}"))
    LC_ALL=C comm -23 <(printf '%s\n' "${want_pkgs[@]}") <(printf '%s\n' "${avail[@]}") | sed 's/^/  not available: /'
    (( ${#pkgs[@]} )) && run sudo apt-get install -y "${pkgs[@]}"
  fi
fi

# snapshot_value <key>: a "key: value" line from snapshot/system.txt.
snapshot_value() { sed -n "s/^$1: //p" "$snap/system.txt" 2>/dev/null; }

if want system; then
  say "system: hostname, timezone, docker group, persistent journal"
  if need system.txt; then
    h=$(snapshot_value hostname); tz=$(snapshot_value timezone)
    if [[ -n $h && $h != "$(hostname)" ]]; then
      run sudo hostnamectl set-hostname "$h"
      run sudo sed -i "s/^127\.0\.1\.1\s.*/127.0.1.1\t$h/" /etc/hosts
    else echo "  hostname already $(hostname)"; fi
    if [[ -n $tz && $tz != "$(timedatectl show -p Timezone --value 2>/dev/null)" ]]; then run sudo timedatectl set-timezone "$tz"
    else echo "  timezone already ${tz:-unset}"; fi
  fi
  # docker.io comes from the apt step; the group lets you run docker without sudo (after logging in again).
  if getent group docker >/dev/null; then
    if id -nG "$USER" | grep -qw docker; then echo "  $USER already in group docker"; else run sudo usermod -aG docker "$USER"; fi
    run sudo systemctl enable --now docker
  else echo "  docker not installed (run the apt step)"; fi
  # Raspberry Pi OS keeps the journal in RAM, so a power cut erases the logs of the boot that failed.
  jconf=/etc/systemd/journald.conf.d/90-persistent-storage.conf
  jwant=$(printf '%s\n' '# Raspberry Pi OS keeps the journal in RAM (/usr/lib/systemd/journald.conf.d/40-rpi-volatile-storage.conf),' \
    '# so a power cut erases the logs of the boot that failed. Keep it on disk instead; this file sorts later and wins.' \
    '# Written by machine-setup/raspberry-pi/restore.sh (system step).' '[Journal]' 'Storage=persistent' 'SystemMaxUse=200M')
  if [[ $(cat "$jconf" 2>/dev/null) == "$jwant" ]]; then echo "  journal already persistent"
  elif (( dry )); then echo "  [dry-run] write $jconf (persistent journal), restart journald"
  else
    sudo mkdir -p "${jconf%/*}" && printf '%s\n' "$jwant" | sudo tee "$jconf" >/dev/null
    sudo systemctl restart systemd-journald && sudo journalctl --flush
  fi
fi

if want tailscale; then
  say "Tailscale (apt package + tailscaled service)"
  if have tailscale; then echo "  already installed"
  else
    # The apt-sources step restores Tailscale's repo and signing key; do it here too so this step works alone.
    if ! apt-cache policy tailscale 2>/dev/null | grep -q 'Candidate: [0-9]'; then restore_apt_sources; run sudo apt-get update; fi
    run sudo apt-get install -y tailscale
  fi
  run sudo systemctl enable --now tailscaled
  if (( dry )); then echo "  [dry-run] check whether Tailscale is signed in"
  elif tailscale status >/dev/null 2>&1; then echo "  signed in"
  else echo "  not signed in yet: run 'sudo tailscale up' and open the link it prints"
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

if want github; then
  say "GitHub sign-in (needed to clone the private agent-lab repo)"
  if ! have gh; then echo "  gh not installed (run the brew step)"
  elif gh auth status >/dev/null 2>&1; then echo "  already signed in"; run gh auth setup-git
  elif (( dry )); then echo "  [dry-run] gh auth login --web (one-time code: open https://github.com/login/device on any computer)"
  else
    echo "  Open https://github.com/login/device on any computer (e.g. the Mac) and enter the code printed below."
    gh auth login --hostname github.com --git-protocol https --web
    gh auth setup-git
  fi
fi

if want repos; then
  say "git repos -> ~/dev (snapshot/repos.txt)"
  if need repos.txt; then
    while read -r name url; do
      [[ -n $name ]] || continue
      if [[ -e $HOME/dev/$name ]]; then echo "  ~/dev/$name already there"
      elif (( dry )); then echo "  [dry-run] git clone $url ~/dev/$name"
      elif git clone -q "$url" "$HOME/dev/$name"; then echo "  cloned $name"
      else echo "  could not clone $url (private? run the github step first)"
      fi
    done < "$snap/repos.txt"
  fi
fi

# link_dir <directory in this repo> <symlink path>: never replaces something that is already there.
link_dir() {
  local target=$1 link=$2
  if [[ -L $link && $(readlink -f "$link") == "$(readlink -f "$target")" ]]; then echo "  $link already linked"
  elif [[ -e $link || -L $link ]]; then echo "  $link exists and is not this repo's ${target#"$here/"}/; leaving it"
  else run mkdir -p "$(dirname "$link")"; run ln -s "$target" "$link"; echo "  linked $link -> $target"
  fi
}

if want links; then
  say "symlinks into this repo: ~/dev/{scripts,pi-status,pihole,openclaw_node,hermes-proxy}, pi-checkup command + skill"
  link_dir "$here/bin" "$HOME/dev/scripts"
  link_dir "$here/pi-status" "$HOME/dev/pi-status"
  link_dir "$here/services/pihole" "$HOME/dev/pihole"
  link_dir "$here/services/openclaw_node" "$HOME/dev/openclaw_node"
  link_dir "$here/services/hermes-proxy" "$HOME/dev/hermes-proxy"
  link_dir "$here/checkup/pi-checkup" "$HOME/.local/bin/pi-checkup"
  link_dir "$here/checkup/skill" "$HOME/.claude/skills/pi-checkup"
fi

if want pihole; then
  say "Pi-hole (docker compose in ~/dev/pihole; DNS on port 53, admin UI on 127.0.0.1:8081)"
  ph=$here/services/pihole
  if ! have docker-compose; then echo "  docker-compose not installed (run the apt step)"
  else
    if [[ ! -f $ph/.env ]]; then
      if (( dry )); then echo "  [dry-run] ask for the Pi-hole admin password and write $ph/.env"
      else
        read -rsp "  choose a Pi-hole admin password: " pw; echo
        (umask 077; printf 'FTLCONF_webserver_api_password=%s\n' "$pw" > "$ph/.env"); unset pw
      fi
    fi
    if (( dry )); then echo "  [dry-run] (cd $ph && sudo docker-compose up -d)"
    else (cd "$ph" && sudo docker-compose up -d)
    fi
  fi
fi

if want agents; then
  say "agents: OpenClaw (npm, ~/dev/openclaw_node); Hermes (official installer, not Homebrew)"
  # The same install/update functions upd uses, defined in ~/.zshrc (restored by the dotfiles step).
  if ! have zsh || [[ ! -f $HOME/.zshrc ]]; then echo "  zsh or ~/.zshrc missing (run the apt and dotfiles steps)"
  elif (( dry )); then echo "  [dry-run] zsh -ic '_upd_openclaw', then openclaw config set gateway.controlUi.basePath /openclaw"
    echo "  [dry-run] curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash -s -- --skip-browser --skip-computer-use"
  else zsh -ic '_upd_openclaw' || echo "  an agent install failed (see above); re-run: ./restore.sh --only agents"
    # The Control UI is published at /openclaw (see the pi-status step), so it must serve under that path.
    "$HOME/dev/openclaw_node/node_modules/.bin/openclaw" config set gateway.controlUi.basePath /openclaw || true
  fi
  # Hermes: the Homebrew formula (0.22.4) lacked the anthropic library and crashed at startup, so it comes from the
  # official installer (git checkout in ~/.hermes/hermes-agent, command in ~/.local/bin). Non-interactive.
  # ~/.hermes (config, API keys, sessions) is not backed up, by design: set Hermes up again by hand afterwards.
  if (( dry )); then :
  elif [[ -x $HOME/.local/bin/hermes ]]; then echo "  Hermes already installed ($HOME/.local/bin/hermes)"
  else curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash -s -- --skip-browser --skip-computer-use \
    || echo "  Hermes install failed; re-run: ./restore.sh --only agents"
  fi
fi

if want pi-status; then
  say "pi-status web page (service on 127.0.0.1:8080, HTTPS via Tailscale Serve)"
  site=$HOME/dev/pi-status
  unit=$HOME/.config/systemd/user/pi-status.service
  if [[ ! -d $site ]]; then echo "  $site missing (run the links step)"
  elif ! have uv; then echo "  uv not installed (run the brew step)"
  elif [[ ! -f $unit ]] && (( ! dry )); then echo "  $unit missing (run the dotfiles step)"
  else
    run uv sync --project "$site" --no-dev --inexact
    run systemctl --user daemon-reload
    run systemctl --user enable --now pi-status.service
    if (( dry )); then echo "  [dry-run] sudo tailscale serve --bg 8080, --https=8443 --set-path /hermes http://127.0.0.1:9120/hermes, --https=8444 --set-path /openclaw http://127.0.0.1:18789/openclaw, --https=8445 --set-path /pihole http://127.0.0.1:8081 (when Tailscale is signed in)"
    elif tailscale status >/dev/null 2>&1; then
      sudo tailscale serve --bg 8080
      # The Hermes dashboard and OpenClaw Control UI, linked from the Agents tab (DASHBOARDS in collect.py).
      sudo tailscale serve --bg --https=8443 --set-path /hermes http://127.0.0.1:9120/hermes  # via hermes-proxy (Caddy)
      sudo tailscale serve --bg --https=8444 --set-path /openclaw http://127.0.0.1:18789/openclaw
      sudo tailscale serve --bg --https=8445 --set-path /pihole http://127.0.0.1:8081  # Pi-hole UI (~/dev/pihole, docker-compose host port 8081)
      tailscale serve status
    else
      echo "  Tailscale isn't signed in yet: run 'sudo tailscale up', then './restore.sh --only pi-status' to publish the page"
    fi
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
  # Units that live in their own (private) repo, cloned by the repos step: ~/dev/websites (DreamBase)
  if [[ -x $HOME/dev/websites/install.sh ]]; then
    if (( dry )); then "$HOME/dev/websites/install.sh" --dry-run; else "$HOME/dev/websites/install.sh"; fi
  else echo "  ~/dev/websites not cloned (private; run the github and repos steps): DreamBase not set up"; fi
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
  - sudo tailscale up    (open the link it prints), then ./restore.sh --only pi-status to publish the
                         status page over HTTPS. A brand-new tailnet must first enable HTTPS certificates
                         (https://login.tailscale.com/admin/dns) and approve Serve (the link `tailscale serve` prints).
  - claude               (log in; installed via the Brewfile cask)
  - gcloud auth login --no-launch-browser
  - gws: put the OAuth client file at ~/.config/gws/client_secret.json (Google Cloud console > APIs & Services >
    Credentials > download), then gws auth login (see the gws skill for the SSH redirect workaround).
  - Agents: onboard each one the way ~/dev/agent-lab/agents.md records (they use the claude CLI login, no API keys).
  - Router: give this Pi a fixed IP (DHCP reservation for its new MAC) so devices using Pi-hole as DNS find it.
  - Agents are installed but not started (8 GB RAM: run one at a time). Start one with
    ~/dev/agent-lab/bin/lab, the pi-status Agents tab, or: systemctl --user start hermes-dashboard
    (or openclaw-gateway).
MSG
