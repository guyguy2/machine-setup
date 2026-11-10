# If you come from bash you might have to change your $PATH.
# export PATH=$HOME/bin:$HOME/.local/bin:/usr/local/bin:$PATH

# Path to your Oh My Zsh installation.
export ZSH="$HOME/.oh-my-zsh"

# Set name of the theme to load --- if set to "random", it will
# load a random theme each time Oh My Zsh is loaded, in which case,
# to know which specific one was loaded, run: echo $RANDOM_THEME
# See https://github.com/ohmyzsh/ohmyzsh/wiki/Themes
ZSH_THEME="robbyrussell"

# Set list of themes to pick from when loading at random
# Setting this variable when ZSH_THEME=random will cause zsh to load
# a theme from this variable instead of looking in $ZSH/themes/
# If set to an empty array, this variable will have no effect.
# ZSH_THEME_RANDOM_CANDIDATES=( "robbyrussell" "agnoster" )

# Uncomment the following line to use case-sensitive completion.
# CASE_SENSITIVE="true"

# Uncomment the following line to use hyphen-insensitive completion.
# Case-sensitive completion must be off. _ and - will be interchangeable.
# HYPHEN_INSENSITIVE="true"

# Uncomment one of the following lines to change the auto-update behavior
# zstyle ':omz:update' mode disabled  # disable automatic updates
# zstyle ':omz:update' mode auto      # update automatically without asking
# zstyle ':omz:update' mode reminder  # just remind me to update when it's time

# Uncomment the following line to change the frequency the auto-updater is run (in days).
# zstyle ':omz:update' frequency 13

# Uncomment the following line to set how old an update must be before it's applied, manually or via the auto-updater (in days).
# zstyle ':omz:update' cooldown 10

# Uncomment the following line if pasting URLs and other text is messed up.
# DISABLE_MAGIC_FUNCTIONS="true"

# Uncomment the following line to disable colors in ls.
# DISABLE_LS_COLORS="true"

# Uncomment the following line to disable auto-setting terminal title.
# DISABLE_AUTO_TITLE="true"

# Uncomment the following line to enable command auto-correction.
# ENABLE_CORRECTION="true"

# Uncomment the following line to display red dots whilst waiting for completion.
# You can also set it to another string to have that shown instead of the default red dots.
# e.g. COMPLETION_WAITING_DOTS="%F{yellow}waiting...%f"
# Caution: this setting can cause issues with multiline prompts in zsh < 5.7.1 (see #5765)
# COMPLETION_WAITING_DOTS="true"

# Uncomment the following line if you want to disable marking untracked files
# under VCS as dirty. This makes repository status check for large repositories
# much, much faster.
# DISABLE_UNTRACKED_FILES_DIRTY="true"

# Uncomment the following line if you want to change the command execution time
# stamp shown in the history command output.
# You can set one of the optional three formats:
# "mm/dd/yyyy"|"dd.mm.yyyy"|"yyyy-mm-dd"
# or set a custom format using the strftime function format specifications,
# see 'man strftime' for details.
# HIST_STAMPS="mm/dd/yyyy"

# Would you like to use another custom folder than $ZSH/custom?
# ZSH_CUSTOM=/path/to/new-custom-folder

# Which plugins would you like to load?
# Standard plugins can be found in $ZSH/plugins/
# Custom plugins may be added to $ZSH_CUSTOM/plugins/
# Example format: plugins=(rails git textmate ruby lighthouse)
# Add wisely, as too many plugins slow down shell startup.
plugins=(git zsh-autosuggestions zsh-completions zsh-syntax-highlighting)  # zsh-syntax-highlighting must stay last

source $ZSH/oh-my-zsh.sh

# User configuration

# export MANPATH="/usr/local/man:$MANPATH"

# You may need to manually set your language environment
# export LANG=en_US.UTF-8

# Preferred editor for local and remote sessions
# if [[ -n $SSH_CONNECTION ]]; then
#   export EDITOR='vim'
# else
#   export EDITOR='nvim'
# fi

# Compilation flags
# export ARCHFLAGS="-arch $(uname -m)"

# Set personal aliases, overriding those provided by Oh My Zsh libs,
# plugins, and themes. Aliases can be placed here, though Oh My Zsh
# users are encouraged to define aliases within a top-level file in
# the $ZSH_CUSTOM folder, with .zsh extension. Examples:
# - $ZSH_CUSTOM/aliases.zsh
# - $ZSH_CUSTOM/macos.zsh
# For a full list of active aliases, run `alias`.
#
# Example aliases
# alias zshconfig="mate ~/.zshrc"
# alias ohmyzsh="mate ~/.oh-my-zsh"
# Homebrew, placed AFTER the system dirs on PATH so brew's dependency formulae
# (util-linux, curl, bash, ...) never shadow core system commands
if [[ -x /home/linuxbrew/.linuxbrew/bin/brew ]]; then
  eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv zsh)"
  path=(${path:#/home/linuxbrew/.linuxbrew/*} /home/linuxbrew/.linuxbrew/bin /home/linuxbrew/.linuxbrew/sbin)
fi
export PATH="$HOME/.local/bin:$PATH"
typeset -U path PATH  # drop duplicates (~/.zprofile, written by the Hermes installer, also adds ~/.local/bin)

# Dev tool shell integrations
command -v fzf >/dev/null && source <(fzf --zsh)
command -v zoxide >/dev/null && eval "$(zoxide init zsh)"
command -v direnv >/dev/null && eval "$(direnv hook zsh)"
alias c='clear'

# Claude
alias cld='claude'
alias clda='cld --dangerously-skip-permissions'
alias clds='cld --dangerously-skip-permissions --model=sonnet'
alias cldo='cld --dangerously-skip-permissions --model="opus"'
alias killClaudes='pkill -9 -f claude'

# Show machine name in prompt
PROMPT="%(?:%{$fg_bold[green]%}%1{➜%} :%{$fg_bold[red]%}%1{➜%} ) %{$fg_bold[yellow]%}%m%{$reset_color%} %{$fg[cyan]%}%~%{$reset_color%}"
PROMPT+=' $(git_prompt_info)'

# ---------------------------------------------------------------------------
# upd: update apt packages + kernel, Pi firmware, manually-installed tools,
# update every git repo under ~/dev (depth 1-2; own repos: pull --ff-only, see gpull), and back up + push
# machine settings; the last two run every 5th run.
# ---------------------------------------------------------------------------
_upd_step() { print -P "\n%F{cyan}==>%f %B$1%b" }

# Sub-step under a group heading: indented title, command output indented beneath it
_upd_sub() {
  local title=$1 rc
  print -P "  %F{magenta}->%f %B$title%b"; shift
  "$@" 2>&1 | sed -u 's/^/     /'
  rc=${pipestatus[1]}
  (( rc )) && _upd_note "$title failed (exit $rc)"
  return $rc
}

# Is this agent paused? ~/dev/agent-lab/on-hold lists them, one per line; delete a line to resume that agent.
_upd_on_hold() { grep -qx "$1" $HOME/dev/agent-lab/on-hold 2>/dev/null }

# Record something that went wrong, for the end-of-run summary. A file, not an array: _upd_sub runs steps in a pipe subshell.
_upd_note() { print -r -- "$1" >> $_upd_log }

# OpenClaw: npm install in ~/dev/openclaw_node (no source checkout is kept; read the docs in node_modules/openclaw)
_upd_openclaw() {
  # Resolve the symlink (to ~/.local/share/openclaw_node): npm run through it writes ../ paths into package-lock.json
  local dir=$HOME/dev/openclaw_node cur latest
  dir=${dir:A}
  latest=$(npm view openclaw version 2>/dev/null) || { echo "could not fetch latest OpenClaw version"; return 1 }
  cur=$(jq -r .version $dir/node_modules/openclaw/package.json 2>/dev/null)
  [[ $cur == $latest ]] && { echo "OpenClaw $cur is up to date"; return 0 }
  echo "OpenClaw ${cur:-not installed} -> $latest"
  npm --prefix $dir install openclaw@latest --no-fund &&
    echo "OpenClaw updated to $latest"
}

# Pi-hole: the image tag is pinned in ~/dev/pihole/docker-compose.yml (bump it there on purpose). Pull it, recreate
# the container only if something changed, and wait for its health check. The old image is removed only once the new
# container is healthy; otherwise the old image is started again (the house's DNS runs on it). (agent-lab/reviews R-084)
# Args (for testing on a throwaway compose project): [compose dir] [service]
_upd_pihole() {
  local dir=${1:-$HOME/dev/pihole} svc=${2:-pihole} ref cid old new over t rc=0
  local -a dc=(sudo docker-compose --project-directory $dir -f $dir/docker-compose.yml)
  ref=$($dc config --images $svc 2>/dev/null | head -1)
  [[ -n $ref ]] || { echo "could not read the image from $dir/docker-compose.yml"; return 1 }
  [[ $ref == *:latest || ${ref##*/} != *:* ]] && print -P "%F{yellow}$ref is not pinned to a release tag%f"
  cid=$($dc ps -aq $svc 2>/dev/null | head -1)
  [[ -n $cid ]] && old=$(sudo docker inspect -f '{{.Image}}' $cid 2>/dev/null)
  $dc pull --quiet $svc || { echo "pull of $ref failed; Pi-hole left as it was"; return 1 }
  new=$(sudo docker image inspect -f '{{.Id}}' $ref 2>/dev/null)
  # up -d leaves the container alone when neither the image nor the compose file changed
  if $dc up -d --wait --wait-timeout 180 $svc; then
    if [[ -n $old && $old != $new ]]; then
      echo "healthy on $ref; removing the previous image ${old#sha256:}"
      for t in ${(z)"$(sudo docker image inspect -f '{{join .RepoTags " "}}' $old 2>/dev/null)"}; do
        sudo docker image rm $t >/dev/null
      done
      sudo docker image rm $old >/dev/null 2>&1; sudo docker image prune -f >/dev/null
    else echo "healthy on $ref${old:+ (image unchanged)}"; fi
    return 0
  fi
  print -P "%F{red}not healthy on $ref%f"
  [[ -n $old && $old != $new ]] || return 1
  echo "rolling back to the previous image ${old#sha256:}"
  over=$(mktemp); printf 'services:\n  %s:\n    image: %s\n' $svc $old > $over
  $dc -f $over up -d --wait --wait-timeout 180 $svc || rc=$?
  rm -f $over
  if (( rc )); then echo "rollback failed too: check docker ps / docker logs now"
  else echo "rolled back; it stays on the old image until the next upd (fix or re-pin the tag in docker-compose.yml)"; fi
  return 1
}

# Hermes: official installer checkout, updated with its own command
_upd_hermes() {
  # Official installer (git checkout in ~/.hermes/hermes-agent); not Homebrew: its package lacked the anthropic library.
  # Call the launcher by path so a shell with a stale PATH (started before ~/.local/bin was added) still finds it
  local bin=$HOME/.local/bin/hermes
  [[ -x $bin ]] || { echo "Hermes not installed ($bin missing)"; return 1 }
  # Stop the dashboard during the update: Hermes counts its restart as a running gateway and then waits a silent
  # 120s for a gateway version row the dashboard never writes (looked like a hang after "Tip:"). Hermes doesn't
  # start a stopped dashboard, so start it again here; it then runs the new code.
  local dash=hermes-dashboard.service was_active=0 rc
  [[ $(systemctl --user is-active $dash 2>/dev/null) == active ]] && was_active=1 && systemctl --user stop $dash
  $bin update --yes; rc=$?
  if (( was_active )); then
    systemctl --user start $dash && echo "Started $dash" || { echo "could not start $dash"; rc=1 }
  fi
  return $rc
}

# Update the git repo in the current dir (or $1). Skips repos with uncommitted changes to tracked files.
# Prints a one-line result.
# - Own repos (upstream remote under github.com/guyguy2): a normal `git pull --ff-only` with full history (unshallowed
#   once if an older version of this function left the clone shallow). It never rewrites local work: if the Pi's
#   branch has diverged from GitHub, the pull fails and says so. (agent-lab/reviews R-044)
# - Upstream reference clones (anyone else's repo): fetch only the newest commit and reset to it, so history never
#   accumulates. Skipped when any local branch has unpushed commits, since the reset and gc would lose them.
gpull() {
  local repo=${1:-.} before after up
  git -C $repo rev-parse --abbrev-ref '@{u}' &>/dev/null || { echo "no upstream, skipped"; return 0 }
  if [[ -n $(git -C $repo status --porcelain --untracked-files=no) ]]; then
    print -P "%F{red}skipped%f (uncommitted changes)"; return 1
  fi
  up=$(git -C $repo rev-parse --abbrev-ref '@{u}')
  before=$(git -C $repo rev-parse HEAD)
  # Big repos take minutes with no output, so say we're working; the note is erased once there's a result
  local note="fetching... "
  print -n $note
  if [[ $(git -C $repo remote get-url ${up%%/*} 2>/dev/null) == (https://github.com/|git@github.com:)guyguy2/* ]]; then
    { [[ $(git -C $repo rev-parse --is-shallow-repository) == false ]] || git -C $repo fetch --unshallow --quiet } &&
      git -C $repo pull --ff-only --quiet || {
      print -n "\e[${#note}D\e[K"
      print -P "%F{red}update failed%f (diverged from $up? see: git -C ${repo/#$HOME/~} status)"; return 1
    }
  else
    if git -C $repo for-each-ref --format='%(upstream:track)' refs/heads | grep -q ahead; then
      print -n "\e[${#note}D\e[K"; print -P "%F{red}skipped%f (unpushed commits on a local branch)"; return 1
    fi
    # Only the tracked branch: a bare `fetch --depth 1` grabs every remote branch and tag (thousands in big repos)
    git -C $repo fetch --depth 1 --no-tags --quiet ${up%%/*} ${up#*/} && git -C $repo reset --hard --quiet '@{u}' || {
      print -n "\e[${#note}D\e[K"; print -P "%F{red}update failed%f"; return 1
    }
    # Each shallow fetch adds a pack and strands the previous commit's objects; drop them or .git grows forever
    git -C $repo reflog expire --expire=now --all && git -C $repo gc --prune=now --quiet
  fi
  print -n "\e[${#note}D\e[K"
  after=$(git -C $repo rev-parse HEAD)
  [[ $before == $after ]] && echo "up to date" || echo "updated ${before[1,7]} -> ${after[1,7]}"
}

# Update every repo under ~/dev (see gpull)
_upd_repos() {
  local git_dir repo
  for git_dir in $HOME/dev/{*,*/*}/.git(N/); do
    repo=${git_dir:h}
    print -n "${repo/#$HOME/~}: "
    _upd_on_hold ${repo:t} && { echo "on hold, skipped"; continue }
    gpull $repo || _upd_note "${repo/#$HOME/~} not updated (see git repos step)"
  done
}

# The status page lives in machine-setup (~/dev/pi-status is a symlink to it). Pulling updates its code;
# this installs any new dependencies and restarts the service so the running page loads that code.
_upd_pi_status() {
  systemctl --user cat pi-status.service &>/dev/null || { echo "pi-status service not installed, skipped"; return 0 }
  uv sync --quiet --project $HOME/dev/pi-status --no-dev --inexact && systemctl --user restart pi-status.service && echo "restarted" || _upd_note "pi-status update failed"
}

# The email sorter (~/dev/mail, private) runs from its own venv each time mail-sync.timer fires, so after a pull it
# only needs its dependencies synced; no service to restart.
_upd_mail() {
  [[ -d $HOME/dev/mail ]] || { echo "~/dev/mail not cloned, skipped"; return 0 }
  uv sync --quiet --project $HOME/dev/mail --no-dev --inexact && echo "synced" || _upd_note "mail sorter update failed"
}

# Restart each running agent service whose code changed after it started (an update above, or a launcher's
# self-update), so it never keeps running the old version. Compares ctime: brew and npm keep packaged mtimes.
_upd_restart_agents() {
  local unit code started changed
  for unit code in \
      hermes-dashboard.service $HOME/.hermes/hermes-agent \
      openclaw-gateway.service $HOME/dev/openclaw_node/node_modules/openclaw/package.json; do
    [[ $(systemctl --user is-active $unit 2>/dev/null) == active ]] || { echo "$unit not running, skipped"; continue }
    started=$(date -d "$(systemctl --user show -p ActiveEnterTimestamp --value $unit)" +%s 2>/dev/null) || continue
    changed=$(stat -c %Z $code 2>/dev/null) || continue
    if (( changed > started )); then
      systemctl --user restart $unit && echo "$unit restarted to load the new version"
    else
      echo "$unit already runs the current version"
    fi
  done
  return 0
}

# Run counter shared by the periodic steps (repo updates, settings backup). Call once per upd run:
# sets _upd_due=1 on the 1st, 6th, 11th, ... run (else 0) and _upd_left to runs until the next due one.
_upd_tick() {
  local f=${XDG_CACHE_HOME:-$HOME/.cache}/upd-runs n
  mkdir -p ${f:h}
  n=0; [[ -r $f ]] && n=$(( $(<$f) % 5 ))
  echo $(( n + 1 )) > $f
  _upd_left=$(( 5 - n ))
  _upd_due=$(( n == 0 ))
}

# Snapshot this machine's settings (dotfiles, package lists) into ~/dev/machine-setup/raspberry-pi
# and push it. A failure here only warns; it never fails the update.
_upd_backup() {
  local dir=$HOME/dev/machine-setup/raspberry-pi
  [[ -x $dir/save.sh ]] || { echo "raspberry-pi backup not found, skipped"; return 0 }
  # snapshot/ is the main Pi's: a worker (~/.config/pi-role) saves locally only, and save.sh --push refuses there
  if [[ $(cat ~/.config/pi-role 2>/dev/null || echo main) != main ]]; then
    echo "worker Pi: saving locally only (snapshot/ belongs to the main Pi)"; $dir/save.sh --to "$(mktemp -d)/snap" >/dev/null
  elif git -C $dir rev-parse --abbrev-ref '@{u}' &>/dev/null; then
    $dir/save.sh --push
  else
    echo "machine-setup has no upstream; saving locally only"; $dir/save.sh
  fi
}

# The nightly restic backup (machine-setup/raspberry-pi/backup): is it current, and do root's installed copies still
# match the repo and Homebrew's rclone (an upgraded rclone or a changed script needs `sudo .../backup/setup` again)?
_upd_restic() {
  local bk=$HOME/dev/machine-setup/raspberry-pi/backup
  [[ -x $bk/pi-backup ]] || { echo "not installed"; return 0 }
  $bk/pi-backup status || _upd_note "nightly backup isn't current (pi-backup status)"
  $bk/setup --check
  case $? in
    0) ;;
    1) _upd_note "root's backup copies differ from the repo or Homebrew's rclone: review, then sudo $bk/setup" ;;
    *) _upd_note "root side of the nightly backup isn't installed: sudo $bk/setup" ;;
  esac
}

# pi-up (machine-setup/raspberry-pi/checkup): red/green "is everything still up?" after the updates. Services that were
# just restarted may need a few seconds, so a red run gets one retry before it lands in the summary.
_upd_pi_up() {
  command -v pi-up >/dev/null || { echo "not installed"; return 0 }
  pi-up && return 0
  echo "retrying in 8 s (services may still be restarting)"; sleep 8
  pi-up || _upd_note "pi-up shows red checks after the update: run pi-up (details: pi-checkup)"
}

# End-of-run summary: work out what is still needed to be fully up to date, list it, and offer to do each item.
# Reads $_upd_log (failures noted by the steps) and $_upd_claude_before / $_upd_omz_before (versions at the start).
_upd_summary() {
  local running=$(uname -r) newest m pid unit uunit comm i claude_now
  local -a todo acts svcs usvcs sess heavy reasons
  local -A seen
  # Deleted shared libraries, /usr binaries, and Homebrew kegs that brew cleanup removed (static binaries like caddy
  # have no .so to catch, R-086)
  local stale_re='\.so[^ ]* \(deleted\)|/usr/s?bin/[^ ]+ \(deleted\)|/home/linuxbrew/\.linuxbrew/Cellar/[^ ]+ \(deleted\)'

  # Reboot reasons: a newer kernel of the running flavour (e.g. rpt-rpi-2712), or packages that ask for it
  newest=$(ls /lib/modules | grep -F -- "+${running#*+}" | sort -V | tail -1)
  [[ -n $newest && $newest != $running ]] && reasons+=("kernel $newest installed, running $running")
  [[ -f /var/run/reboot-required.pkgs ]] && reasons+=("${(j:, :)${(uf)"$(</var/run/reboot-required.pkgs)"}} asked for it")
  [[ -f /var/run/reboot-required && -z $reasons ]] && reasons+=("a package asked for it")

  # Bootloader firmware: applied only on request, and takes effect at the next boot
  if command -v rpi-eeprom-update >/dev/null && sudo rpi-eeprom-update 2>&1 | grep -q 'update available'; then
    todo+=("Apply the bootloader firmware update (takes effect at the next boot)"); acts+=("sudo rpi-eeprom-update -a")
    reasons+=("bootloader update pending")
  fi

  # Processes still running with libraries or binaries that this run replaced on disk
  for m in ${(f)"$(sudo grep -lE $stale_re /proc/[0-9]*/maps 2>/dev/null)"}; do
    pid=${${m#/proc/}%/maps}
    ps -o unit=,uunit=,comm= -p $pid 2>/dev/null | read -r unit uunit comm
    [[ -n $unit && -z $seen[$unit$uunit] ]] || continue
    seen[$unit$uunit]=1
    case $unit in
      ssh.service|sshd.service|systemd-*|dbus.service) heavy+=($unit) ;;
      # A user service (e.g. the Caddy proxies) can be restarted by itself; other session processes need a re-login
      user@*.service) if [[ $uunit == *.service ]]; then usvcs+=($uunit); else sess+=($comm); fi ;;
      session-*.scope) sess+=($comm) ;;
      *.service) svcs+=($unit) ;;
    esac
  done
  if (( $#reasons )); then
    [[ -n $svcs$usvcs$sess$heavy ]] && reasons+=("also refreshes $(( $#svcs + $#usvcs )) service(s) and ${#sess} desktop process(es) on old libraries")
  else
    if (( $#svcs )); then
      todo+=("Restart services running old libraries: ${svcs}. Docker or Pi-hole may drop briefly")
      acts+=("sudo systemctl restart $svcs")
    fi
    if (( $#usvcs )); then
      todo+=("Restart user services running old binaries or libraries: ${usvcs}")
      acts+=("systemctl --user restart $usvcs")
    fi
    if [[ -n $sess$heavy ]]; then
      reasons=(${(u)sess} ${(u)heavy})
      todo+=("Log out and back in (or reboot): ${(j:, :)reasons} run old libraries"); reasons=()
      acts+=("")
    fi
  fi

  claude_now=$(brew list --cask --versions claude-code@latest 2>/dev/null)
  [[ -n $_upd_claude_before && $claude_now != $_upd_claude_before ]] &&
    { todo+=("Restart Claude Code sessions: ${_upd_claude_before#* } -> ${claude_now#* }"); acts+=("") }
  if [[ -n $_upd_omz_before && $_upd_omz_before != $(git -C ${ZSH:-$HOME/.oh-my-zsh} rev-parse HEAD 2>/dev/null) ]] && (( ! $#reasons )); then
    todo+=("Reload the shell, Oh My Zsh was updated"); acts+=("exec zsh")
  fi
  [[ -s $_upd_log ]] && for m in ${(f)"$(<$_upd_log)"}; do todo+=("Needs attention: $m"); acts+=(""); done
  (( $#reasons )) && { todo+=("Reboot: ${(j:; :)reasons}"); acts+=("sudo reboot") }

  if (( ! $#todo )); then
    print -P "\n%F{green}All done.%f Nothing else to do."
    return 0
  fi
  print -P "\n%F{cyan}==>%f %BTo get fully up to date%b"
  for i in {1..$#todo}; do
    print -r -- "  $i. ${todo[i]}${acts[i]:+  [${acts[i]}]}"
  done
  [[ -t 0 ]] || return 0
  print
  for i in {1..$#todo}; do
    [[ -n ${acts[i]} ]] || continue
    if read -q "?Do item $i now? [y/N] "; then print; eval ${acts[i]}; else print; fi
  done
}

upd() {
  sudo true || return 1
  local _upd_due _upd_left
  local _upd_log=$(mktemp) _upd_claude_before _upd_omz_before
  _upd_claude_before=$(command -v brew >/dev/null && brew list --cask --versions claude-code@latest 2>/dev/null)
  _upd_omz_before=$(git -C ${ZSH:-$HOME/.oh-my-zsh} rev-parse HEAD 2>/dev/null)
  _upd_tick

  _upd_step "apt packages + kernel"
  sudo apt-get update && sudo apt-get full-upgrade -y && sudo apt-get autoremove --purge -y && sudo apt-get clean ||
    _upd_note "apt update failed"

  if command -v rpi-eeprom-update >/dev/null; then
    _upd_step "Raspberry Pi bootloader firmware (status only; apply with: sudo rpi-eeprom-update -a)"
    sudo rpi-eeprom-update
  fi

  if command -v brew >/dev/null; then
    _upd_step "Homebrew"
    # --yes: Homebrew 7 asks for confirmation by default (ask mode)
    # gcloud-cli and antigravity-cli are auto_updates casks, which plain `brew upgrade` skips
    brew update && brew upgrade --yes && brew upgrade --yes --cask --greedy gcloud-cli antigravity-cli && brew cleanup ||
      _upd_note "Homebrew update failed"
  fi

  if command -v npm >/dev/null; then
    _upd_step "npm global packages (e.g. pyright)"
    # npm and corepack come with apt's nodejs, so apt updates them.
    # Supply-chain delay (agent-lab/reviews R-083): /usr/etc/npmrc sets min-release-age=7, so only releases at least
    # a week old are eligible. `npm outdated` reports the newest eligible version, which can be OLDER than the one
    # installed; upgrade only when it's newer, so the delay never downgrades anything.
    local -a _npm_pkgs=(${(f)"$(npm outdated -g --json 2>/dev/null |
      jq -r 'to_entries[] | select(.key != "npm" and .key != "corepack") | "\(.key) \(.value.current) \(.value.latest)"' |
      while read -r _p _cur _new; do
        [[ $_cur != $_new && $(printf '%s\n%s\n' $_cur $_new | sort -V | tail -1) == $_new ]] && echo "$_p@$_new"
      done)"})
    if (( $#_npm_pkgs )); then sudo npm install -g --no-fund "${_npm_pkgs[@]}" || _upd_note "npm global update failed"; else echo "up to date"; fi
  fi

  if command -v uv >/dev/null && [[ -n "$(uv tool list 2>/dev/null | grep -v '^No tools')" ]]; then
    _upd_step "uv tools (e.g. sqlite-web)"
    uv tool upgrade --all || _upd_note "uv tool upgrade failed"
  fi

  if [[ -f ~/dev/pihole/docker-compose.yml ]]; then
    _upd_step "Pi-hole (docker image)"
    _upd_pihole || _upd_note "Pi-hole update failed (see above; DNS for the house runs on it: docker ps, ~/dev/pihole)"
  fi

  _upd_step "Agents"
  _upd_sub "Hermes"      _upd_hermes
  # On hold: no update. restore.sh calls _upd_openclaw directly, so a rebuild still installs it.
  _upd_on_hold openclaw || _upd_sub "OpenClaw"    _upd_openclaw
  _upd_sub "Shared skills (agent-lab/skills)" ~/dev/agent-lab/bin/lab skills
  _upd_sub "Todoist skill (td -> Claude Code)" td skill update claude-code
  _upd_sub "Restart updated agent services" _upd_restart_agents

  _upd_step "Oh My Zsh";   ZSH=$ZSH command zsh -f $ZSH/tools/upgrade.sh -v minimal
  _upd_step "Oh My Zsh custom plugins"
  local _upd_plugin
  for _upd_plugin in ${ZSH_CUSTOM:-$ZSH/custom}/plugins/*(N/); do
    [[ -d $_upd_plugin/.git ]] && { git -C $_upd_plugin pull --ff-only -q || _upd_note "plugin ${_upd_plugin:t} pull failed"; }
  done
  if (( _upd_due )); then
    _upd_step "git repos in ~/dev (every 5th run)"; _upd_repos
    _upd_step "pi-status web page (restart to load pulled code)"; _upd_pi_status
    _upd_step "mail sorter (sync its dependencies)"; _upd_mail
  else
    _upd_step "git repos in ~/dev"; echo "skipped, next update in $_upd_left run(s)"
  fi

  if (( _upd_due )); then
    _upd_step "Settings backup (machine-setup/raspberry-pi, every 5th run)"
    _upd_backup || { print -P "%F{yellow}settings backup failed%f (see above)"; _upd_note "settings backup failed" }
  else
    _upd_step "Settings backup (machine-setup/raspberry-pi)"; echo "skipped, next backup in $_upd_left run(s)"
  fi

  _upd_step "Nightly backup (restic): status and root-side copies"; _upd_restic

  _upd_step "Health check (pi-up)"; _upd_pi_up

  _upd_summary
  rm -f $_upd_log
}

# SSH logins land in a shared tmux session "main", so work (e.g. Claude Code) survives a dropped connection.
# Not exec'd: detaching (Ctrl+b d) leaves you in this plain shell. Skips non-SSH terminals, nested tmux, scp/rsync,
# and scripts that need an interactive shell for its functions (NO_TMUX=1 zsh -ic ...: restore.sh, pi-checkup).
if [[ -n $SSH_TTY && -z $TMUX && -z $NO_TMUX && $- == *i* ]] && command -v tmux >/dev/null; then
  tmux new -A -s main
fi
