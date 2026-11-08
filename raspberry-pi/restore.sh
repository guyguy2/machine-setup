#!/usr/bin/env bash
# Rebuild a Pi's setup on a fresh Raspberry Pi OS / Debian image from ./snapshot. README.md explains every step.
# No secrets are in git (this repo is public): sign-ins, agent state and data come back from the encrypted restic
# backup (raspberry-pi/backup/) with pi-restore-state. What's left by hand is listed at the end.
# Usage: restore.sh [--role main|worker] [--dry-run] [--only step,step,...]
# Steps (run in this order): apt-sources apt system tailscale brew uv npm omzsh dotfiles github repos links
#                            pihole agents pi-status rei mail shell systemd
# --role: main (the default: every step) or worker (skips the main-only steps rei and mail, and DreamBase in the
#   systemd step; see MULTI-PI.md). The flag beats ~/.config/pi-role, which beats the default; a real run writes
#   the role to ~/.config/pi-role so save.sh and upd know it. snapshot/ is the main Pi's: a worker restores from it.
# Safe to re-run. Existing files are moved to ~/.pi-restore-backup-<timestamp>/.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
snap=$here/snapshot
all_steps=(apt-sources apt system tailscale brew uv npm omzsh dotfiles github repos links pihole agents pi-status rei mail shell systemd)
# The only per-role filter: what a worker skips. Step names, plus "dreambase" (~/dev/websites/install.sh, run in the
# systemd step). Everything else runs on both, including pihole (the worker runs a second Pi-hole) and pi-status.
main_only=(rei mail dreambase)
brew_bin=/home/linuxbrew/.linuxbrew/bin/brew
role_file=$HOME/.config/pi-role

usage() { echo "usage: ${0##*/} [--role main|worker] [--dry-run] [--only step,step,...]" >&2; exit 2; }

dry=0
role=
only=("${all_steps[@]}")
while (( $# )); do
  case $1 in
    --dry-run) dry=1 ;;
    --only) shift; IFS=, read -ra only <<< "${1:?--only needs a list}" ;;
    --role) (( $# > 1 )) || usage; shift; role=$1; role_src=--role ;;
    *) usage ;;
  esac
  shift
done
for s in "${only[@]}"; do
  [[ " ${all_steps[*]} " == *" $s "* ]] || { echo "${0##*/}: unknown step '$s' in --only (steps: ${all_steps[*]})" >&2; exit 2; }
done
if [[ -z $role ]]; then
  role=$(tr -d '[:space:]' 2>/dev/null < "$role_file" || true); role_src=$role_file
  [[ -n $role ]] || { role=main; role_src=default; }
fi
case $role in
  main|worker) ;;
  *) echo "${0##*/}: invalid role '$role' (from $role_src): must be main or worker" >&2; usage ;;
esac

say() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }
# The one dry-run gate. run <command...>: print it in a dry run, run it otherwise.
run() { if (( dry )); then printf '  [dry-run] %s\n' "$*"; else "$@"; fi; }
# would <what it does>: for steps that aren't one command (pipes, prompts, several commands). In a dry run, print
# the description and return 1; otherwise return 0. Use: `if would "write X"; then ...; fi`, or `would "..." || :`.
would() { if (( dry )); then printf '  [dry-run] %s\n' "$*"; return 1; fi; }
# Steps that failed but let the rest run; listed at the end (exit 1).
failed=()
step_failed() { echo "  $1 failed (above); re-run: ./restore.sh --only $1"; failed+=("$1"); }
dry_flag=(); (( dry )) && dry_flag=(--dry-run)
# role_skips <step or part>: true when this Pi's role doesn't run it (see main_only).
role_skips() {
  local s
  [[ $role == main ]] && return 1
  for s in "${main_only[@]}"; do [[ $s == "$1" ]] && return 0; done
  return 1
}
# want <step>: asked for (all steps, or --only), and run by this role.
want() {
  local s
  for s in "${only[@]}"; do
    [[ $s == "$1" ]] || continue
    if role_skips "$1"; then say "$1: skipped (main only)"; return 1; fi
    return 0
  done
  return 1
}
need() { [[ -e $snap/$1 ]] || { echo "  missing snapshot/$1, skipping"; return 1; }; }

[[ -d $snap ]] || { echo "no snapshot/ next to restore.sh" >&2; exit 1; }
echo "Role: $role ($role_src)"
(( dry )) || sudo true
if [[ $(tr -d '[:space:]' 2>/dev/null < "$role_file" || true) != "$role" ]]; then
  if would "write '$role' to ~/.config/pi-role"; then
    mkdir -p "${role_file%/*}" && printf '%s\n' "$role" > "$role_file" && echo "  wrote '$role' to ~/.config/pi-role"
  fi
fi

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
  say "system: hostname, timezone, docker group, persistent journal, sshd root logins, rpcbind"
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
  elif would "write $jconf (persistent journal), restart journald"; then
    sudo mkdir -p "${jconf%/*}" && printf '%s\n' "$jwant" | sudo tee "$jconf" >/dev/null
    sudo systemctl restart systemd-journald && sudo journalctl --flush
  fi
  # No root logins over SSH, even with a key (the OpenSSH default, prohibit-password, allows key logins).
  sconf=/etc/ssh/sshd_config.d/10-hardening.conf
  swant=$(printf '%s\n' '# No root logins over SSH, even with a key (the OpenSSH default allows key logins).' \
    '# Written by machine-setup/raspberry-pi/restore.sh (system step).' 'PermitRootLogin no')
  if [[ $(sudo cat "$sconf" 2>/dev/null) == "$swant" ]]; then echo "  sshd already refuses root logins"
  elif would "write $sconf (PermitRootLogin no), reload ssh"; then
    printf '%s\n' "$swant" | sudo tee "$sconf" >/dev/null && sudo chmod 600 "$sconf"
    sudo sshd -t && sudo systemctl reload ssh
  fi
  # rpcbind comes with nfs-common (required by the desktop's rpd-common) and listens on the LAN on port 111.
  # NFS isn't used, so mask it rather than purge it (that would remove rpd-common). Unmask to mount NFS.
  if [[ $(systemctl is-enabled rpcbind.service 2>/dev/null) == masked ]]; then echo "  rpcbind already masked"
  else
    run sudo systemctl disable --now rpcbind.service rpcbind.socket nfs-blkmap.service
    run sudo systemctl mask rpcbind.service rpcbind.socket nfs-blkmap.service
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
  if would "check whether Tailscale is signed in"; then
    if tailscale status >/dev/null 2>&1; then echo "  signed in"
    else echo "  not signed in yet: run 'sudo tailscale up' and open the link it prints"; fi
  fi
fi

if want brew; then
  say "Homebrew + Brewfile"
  if [[ ! -x $brew_bin ]]; then
    echo "  installing Homebrew"
    if would "official Homebrew install.sh (NONINTERACTIVE=1)"; then
      NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
  fi
  if need Brewfile; then
    run "$brew_bin" bundle --file="$snap/Brewfile"
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
    # Only install releases at least a week old (supply-chain delay; upd relies on it too)
    run sudo npm config set min-release-age 7 --location=global
    mapfile -t n < "$snap/npm-global.txt"
    if (( ! ${#n[@]} )); then echo "  none"
    else run sudo npm install -g "${n[@]}" || step_failed npm; fi
  fi
fi

if want omzsh; then
  say "Oh My Zsh"
  if [[ -d $HOME/.oh-my-zsh ]]; then echo "  already installed"
  elif would "official Oh My Zsh install.sh (RUNZSH=no CHSH=no KEEP_ZSHRC=yes)"; then
    RUNZSH=no CHSH=no KEEP_ZSHRC=yes sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
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
      case $rel in .gemini/*) run chmod 600 "$dest" ;; esac  # agy keeps its settings private
    done < <(find "$snap/dotfiles" -type f -print0)
    [[ -d $bak ]] && echo "  previous versions saved in $bak"
  fi
fi

if want github; then
  say "GitHub sign-in (needed to clone the private agent-lab repo)"
  if ! have gh; then echo "  gh not installed (run the brew step)"
  elif gh auth status >/dev/null 2>&1; then echo "  already signed in"; run gh auth setup-git
  elif would "gh auth login --web (one-time code: open https://github.com/login/device on any computer)"; then
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
      elif would "git clone $url ~/dev/$name"; then
        if git clone -q "$url" "$HOME/dev/$name"; then echo "  cloned $name"
        else echo "  could not clone $url (private? run the github step first)"; fi
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
  say "symlinks into this repo: ~/dev/{scripts,pi-status,pihole,openclaw_node,hermes-proxy}, pi-checkup command + skill, pi-backup, pi-restore-state"
  link_dir "$here/bin" "$HOME/dev/scripts"
  link_dir "$here/pi-status" "$HOME/dev/pi-status"
  link_dir "$here/services/pihole" "$HOME/dev/pihole"
  link_dir "$here/services/openclaw_node" "$HOME/dev/openclaw_node"
  link_dir "$here/services/hermes-proxy" "$HOME/dev/hermes-proxy"
  link_dir "$here/checkup/pi-checkup" "$HOME/.local/bin/pi-checkup"
  link_dir "$here/checkup/skill" "$HOME/.claude/skills/pi-checkup"
  # The encrypted restic backup's user-side commands (README.md, "Nightly backup"); link_dir links files too.
  # pi-checkup's drift.links check runs this step as a dry run and warns about any link it would make.
  link_dir "$here/backup/pi-backup" "$HOME/.local/bin/pi-backup"
  link_dir "$here/backup/pi-restore-state" "$HOME/.local/bin/pi-restore-state"
fi

if want pihole; then
  say "Pi-hole (docker compose in ~/dev/pihole; DNS on port 53, admin UI on 127.0.0.1:8081)"
  ph=$here/services/pihole
  if ! have docker-compose; then echo "  docker-compose not installed (run the apt step)"
  else
    if [[ ! -f $ph/.env ]]; then
      if would "ask for the Pi-hole admin password and write $ph/.env"; then
        read -rsp "  choose a Pi-hole admin password: " pw; echo
        (umask 077; printf 'FTLCONF_webserver_api_password=%s\n' "$pw" > "$ph/.env"); unset pw
      fi
    fi
    if would "(cd $ph && sudo docker-compose up -d --wait)"; then (cd "$ph" && sudo docker-compose up -d --wait); fi
  fi
fi

if want agents; then
  say "agents: OpenClaw (npm, ~/dev/openclaw_node); Hermes (official installer, not Homebrew)"
  # The same install/update functions upd uses, defined in ~/.zshrc (restored by the dotfiles step).
  if ! have zsh || [[ ! -f $HOME/.zshrc ]]; then echo "  zsh or ~/.zshrc missing (run the apt and dotfiles steps)"
  # NO_TMUX: over SSH, ~/.zshrc would otherwise attach to tmux and the rebuild would stop there (R-038).
  elif would "NO_TMUX=1 zsh -ic '_upd_openclaw', then openclaw config set gateway.controlUi.basePath /openclaw"; then
    NO_TMUX=1 zsh -ic '_upd_openclaw' || step_failed agents
    # The Control UI is published at /openclaw (see the pi-status step), so it must serve under that path.
    "$HOME/dev/openclaw_node/node_modules/.bin/openclaw" config set gateway.controlUi.basePath /openclaw || true
  fi
  # Hermes: the Homebrew formula (0.22.4) lacked the anthropic library and crashed at startup, so it comes from the
  # official installer (git checkout in ~/.hermes/hermes-agent, command in ~/.local/bin). Non-interactive.
  # ~/.hermes (config, API keys, sessions) is never in git: it comes back from the encrypted restic backup with
  # pi-restore-state (dry run first, then --yes; it runs hermes import). A worker sets up its own instead.
  if [[ -x $HOME/.local/bin/hermes ]]; then echo "  Hermes already installed ($HOME/.local/bin/hermes)"
  elif would "curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash -s -- --skip-browser --skip-computer-use"; then
    curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash -s -- --skip-browser --skip-computer-use \
      || step_failed agents
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
    if ! would "sudo tailscale serve --bg 8080, --https=8443 --set-path /hermes http://127.0.0.1:9120/hermes, --https=8444 --set-path /openclaw http://127.0.0.1:18789/openclaw, --https=8445 --set-path /pihole http://127.0.0.1:8081 (when Tailscale is signed in)"; then :
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

if want rei; then
  say "REI dashboard (private repo ~/dev/rei: uvicorn on 127.0.0.1:8420, Caddy on 8421, tailnet-only HTTPS on :8446)"
  rei=$HOME/dev/rei
  if [[ -d $rei ]]; then echo "  $rei already there"
  elif ! have gh || ! gh auth status >/dev/null 2>&1; then echo "  gh not signed in (private repo; run the github step first)"
  else run gh repo clone guyguy2/rei "$rei"
  fi
  if [[ ! -d $rei ]]; then
    would "uv sync, deploy/pi/install.sh, sudo tailscale serve --bg --https=8446 http://127.0.0.1:8421" || :
  elif ! have uv; then echo "  uv not installed (run the brew step)"
  else
    run uv sync --project "$rei"
    # Links rei.service, rei-proxy.service and rei-vault-sync.{service,timer} into ~/.config/systemd/user and enables
    # the first two; the sync timer only once the rclone remote gdrive: exists (follow-up below, then re-run this).
    "$rei/deploy/pi/install.sh" "${dry_flag[@]}"
    if ! would "sudo tailscale serve --bg --https=8446 http://127.0.0.1:8421 (when Tailscale is signed in)"; then :
    elif tailscale status >/dev/null 2>&1; then sudo tailscale serve --bg --https=8446 http://127.0.0.1:8421  # tailnet only, no LAN port
    else echo "  Tailscale isn't signed in yet: run 'sudo tailscale up', then './restore.sh --only rei' to publish it"
    fi
  fi
  cat <<'MSG'
  By hand:
    - inputs/ and the rclone remote gdrive: come back from the encrypted backup: pi-restore-state (a dry run),
      then pi-restore-state --yes; then re-run ./restore.sh --only rei to enable rei-vault-sync.timer.
    - First setup only (nothing to restore): copy ~/dev/rei/inputs/ from the Mac, and for the vault sync run
      rclone authorize "drive" on a machine with a browser (the Mac), then on the Pi:
      rclone config create gdrive drive scope=drive.readonly token='<the JSON it printed>'
      and re-run ./restore.sh --only rei to enable rei-vault-sync.timer. Details: ~/dev/rei/deploy/pi/README.md
    - Start it: systemctl --user start rei.service (rei-proxy.service comes with it); the pi-status REI tab shows it
MSG
fi

if want mail; then
  say "Email sorter (private repo ~/dev/mail: mail-sync.timer every hour writes the state Home Base's Emails tab shows)"
  mail=$HOME/dev/mail
  if [[ -d $mail ]]; then echo "  $mail already there"
  elif ! have gh || ! gh auth status >/dev/null 2>&1; then echo "  gh not signed in (private repo; run the github step first)"
  else run gh repo clone guyguy2/mail "$mail"
  fi
  if [[ ! -d $mail ]]; then
    would "uv sync, link deploy/mail-sync.{service,timer}, enable mail-sync.timer" || :
  elif ! have uv; then echo "  uv not installed (run the brew step)"
  else
    run uv sync --project "$mail"
    run mkdir -p "$HOME/.config/systemd/user"
    run ln -sf "$mail/deploy/mail-sync.service" "$mail/deploy/mail-sync.timer" "$HOME/.config/systemd/user/"
    run systemctl --user daemon-reload
    run systemctl --user enable --now mail-sync.timer
  fi
  cat <<'MSG'
  It needs the gws Gmail sign-in and Claude Code signed in; those and its data (~/.local/share/mail) come back
  from the encrypted backup: pi-restore-state (a dry run), then pi-restore-state --yes. First setup only (nothing
  to restore): ~/dev/agent-lab/bin/gws-login, claude, then `uv run mail bootstrap` in ~/dev/mail to learn the last
  two weeks. Logs: journalctl --user -u mail-sync
MSG
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
  if role_skips dreambase; then echo "  DreamBase (~/dev/websites/install.sh): skipped (main only)"
  elif [[ -x $HOME/dev/websites/install.sh ]]; then
    "$HOME/dev/websites/install.sh" "${dry_flag[@]}"
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

if (( ${#failed[@]} )); then
  printf '\n\033[1;31m==>\033[0m Failed steps (the rest ran): %s. Re-run: ./restore.sh --only %s\n' "${failed[*]}" "$(IFS=,; echo "${failed[*]}")"
fi
say "Restore finished. Manual follow-ups"
if [[ $role == main ]]; then
cat <<'MSG'
  - Open a new terminal (or log out/in) so zsh and ~/.zshrc take effect.
  - sudo tailscale up    (open the link it prints), then ./restore.sh --only pi-status to publish the
                         status page over HTTPS. A brand-new tailnet must first enable HTTPS certificates
                         (https://login.tailscale.com/admin/dns) and approve Serve (the link `tailscale serve` prints).
  - Restore state: no secrets are in git; ~/.hermes, the sign-ins (claude, gcloud, gws, gh, rclone, ...) and data
    (~/.local/share/mail, ~/dev/rei/inputs/, the services' .env files, ...) come back from the encrypted restic
    backup: pi-restore-state (a dry run: shows what it would restore), then pi-restore-state --yes. Needs the
    restic passphrases and ~/.config/gws/client_secret.json (password manager), the gdrive-backup: rclone remote
    (~/dev/agent-lab/bin/rclone-login --remote gdrive-backup) and sudo backup/setup first: README.md,
    "New Pi from backup". Then ./restore.sh --only rei to enable the REI vault sync, and
    systemctl --user start rei.service.
  - Only if not restoring state (a first-ever setup), or for what pi-restore-state reports missing:
    - claude             (log in; installed via the Brewfile cask)
    - agy                (Antigravity CLI: run `agy` and sign in; installed via the Brewfile cask, settings and status line from the dotfiles step)
    - gcloud auth login --no-launch-browser
    - gws: put the OAuth client file at ~/.config/gws/client_secret.json (Google Cloud console > APIs & Services >
      Credentials > download), then gws auth login (see the gws skill for the SSH redirect workaround).
    - Agents: onboard each one the way ~/dev/agent-lab/agents.md records (they use the claude CLI login, no API keys).
    - REI dashboard: copy ~/dev/rei/inputs/ from the Mac, set up the rclone remote gdrive: (printed by the rei step).
  - Router: give this Pi a fixed IP (DHCP reservation for its new MAC) so devices using Pi-hole as DNS find it.
  - Nightly backup (README.md), only after restoring state: pi-backup init and
    sudo /usr/local/lib/pi-backup/pi-backup-system init (they refuse on an unrestored Pi whose hostname has
    backups on Drive; --fresh starts over on purpose).
  - Agents are installed but not started (8 GB RAM: run one at a time). Start one with
    ~/dev/agent-lab/bin/lab, the pi-status Agents tab, or: systemctl --user start hermes-dashboard
    (or openclaw-gateway).
MSG
else
cat <<'MSG'
  - Open a new terminal (or log out/in) so zsh and ~/.zshrc take effect.
  - sudo tailscale up --ssh   (open the link it prints); name this machine (pi2, pi3) in the admin console, then
                              ./restore.sh --only pi-status to publish its own status page over HTTPS.
  - Router: give this Pi a fixed IP (DHCP reservation for its MAC), and hand out both Pis' LAN IPs as DNS (this
    Pi runs a second Pi-hole).
  - claude               (log in, if you'll use Claude Code here)
  - agy                  (sign in, if you'll use the Antigravity CLI here)
  - Hermes (a worker: no Telegram; only the main Pi has the bot, and two gateways can't share one bot token):
    - A new Anthropic API key for this Pi (same account; per-Pi usage, revoke one Pi alone).
    - In ~/.hermes/.env: API_SERVER_ENABLED=true, API_SERVER_KEY=<random>, API_SERVER_HOST=<this Pi's tailnet IP>
      (tailscale ip -4; not 0.0.0.0, which would open it to the LAN). Port 8642.
    - On the main Pi: hermes peer add <this Pi> --url http://<tailnet IP>:8642 --key <API_SERVER_KEY>
  - This Pi's own nightly backup (README.md): sudo ~/dev/machine-setup/raspberry-pi/backup/setup, then
    pi-backup init and sudo /usr/local/lib/pi-backup/pi-backup-system init.
  - Agents are installed but not started. Start one with ~/dev/agent-lab/bin/lab, the pi-status Agents tab,
    or: systemctl --user start hermes-dashboard
MSG
fi
(( ! ${#failed[@]} ))
