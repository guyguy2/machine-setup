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
plugins=(git)

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
# shallow-update (depth 1) every git repo under ~/dev (depth 1-2), and back up + push
# machine settings; the last two run every 5th run.
# ---------------------------------------------------------------------------
_upd_step() { print -P "\n%F{cyan}==>%f %B$1%b" }

# Sub-step under a group heading: indented title, command output indented beneath it
_upd_sub() {
  print -P "  %F{magenta}->%f %B$1%b"; shift
  "$@" 2>&1 | sed -u 's/^/     /'
}

# OpenClaw: npm install in ~/dev/openclaw_node (~/dev/openclaw is the source checkout)
_upd_openclaw() {
  local dir=$HOME/dev/openclaw_node cur latest
  latest=$(npm view openclaw version 2>/dev/null) || { echo "could not fetch latest OpenClaw version"; return 1 }
  cur=$(jq -r .version $dir/node_modules/openclaw/package.json 2>/dev/null)
  [[ $cur == $latest ]] && { echo "OpenClaw $cur is up to date"; return 0 }
  echo "OpenClaw ${cur:-not installed} -> $latest"
  npm --prefix $dir install openclaw@latest --no-fund &&
    echo "OpenClaw updated to $latest"
}

# Hermes: official installer checkout, updated with its own command
_upd_hermes() {
  # Official installer (git checkout in ~/.hermes/hermes-agent); not Homebrew: its package lacked the anthropic library.
  # Call the launcher by path so a shell with a stale PATH (started before ~/.local/bin was added) still finds it
  local bin=$HOME/.local/bin/hermes
  [[ -x $bin ]] || { echo "Hermes not installed ($bin missing)"; return 1 }
  $bin update --yes
}

# Shallow-update the git repo in the current dir (or $1): fetch only the newest
# commit of the upstream branch and reset to it, so history never accumulates.
# Skips repos with uncommitted changes to tracked files. Prints a one-line result.
gpull() {
  local repo=${1:-.} before after
  git -C $repo rev-parse --abbrev-ref '@{u}' &>/dev/null || { echo "no upstream, skipped"; return 0 }
  if [[ -n $(git -C $repo status --porcelain --untracked-files=no) ]]; then
    print -P "%F{red}skipped%f (uncommitted changes)"; return 1
  fi
  if [[ $(git -C $repo rev-list --count '@{u}..HEAD' 2>/dev/null) -gt 0 ]]; then
    print -P "%F{red}skipped%f (unpushed commits)"; return 1
  fi
  before=$(git -C $repo rev-parse HEAD)
  # Big repos take minutes with no output, so say we're working; the note is erased once there's a result
  local note="fetching... "
  print -n $note
  # Only the tracked branch: a bare `fetch --depth 1` grabs every remote branch and tag (thousands in hermes-agent)
  local up=$(git -C $repo rev-parse --abbrev-ref '@{u}')
  git -C $repo fetch --depth 1 --no-tags --quiet ${up%%/*} ${up#*/} && git -C $repo reset --hard --quiet '@{u}' || {
    print -n "\e[${#note}D\e[K"; print -P "%F{red}update failed%f"; return 1
  }
  print -n "\e[${#note}D\e[K"
  # Each shallow fetch adds a pack and strands the previous commit's objects; drop them or .git grows forever
  git -C $repo reflog expire --expire=now --all && git -C $repo gc --prune=now --quiet
  after=$(git -C $repo rev-parse HEAD)
  [[ $before == $after ]] && echo "up to date" || echo "updated ${before[1,7]} -> ${after[1,7]}"
}

# Shallow-update every repo under ~/dev
_upd_repos() {
  local git_dir repo
  for git_dir in $HOME/dev/{*,*/*}/.git(N/); do
    repo=${git_dir:h}
    print -n "${repo/#$HOME/~}: "
    gpull $repo
  done
}

# The status page lives in machine-setup (~/dev/pi-status is a symlink to it). Pulling updates its code;
# this installs any new dependencies and restarts the service so the running page loads that code.
_upd_pi_status() {
  systemctl --user cat pi-status.service &>/dev/null || { echo "pi-status service not installed, skipped"; return 0 }
  uv sync --quiet --project $HOME/dev/pi-status --no-dev --inexact && systemctl --user restart pi-status.service && echo "restarted"
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
  if git -C $dir rev-parse --abbrev-ref '@{u}' &>/dev/null; then
    $dir/save.sh --push
  else
    echo "machine-setup has no upstream; saving locally only"; $dir/save.sh
  fi
}

upd() {
  sudo true || return 1
  local _upd_due _upd_left
  _upd_tick

  _upd_step "apt packages + kernel"
  sudo apt-get update && sudo apt-get full-upgrade -y && sudo apt-get autoremove --purge -y && sudo apt-get clean

  if command -v rpi-eeprom-update >/dev/null; then
    _upd_step "Raspberry Pi bootloader firmware (status only; apply with: sudo rpi-eeprom-update -a)"
    sudo rpi-eeprom-update
  fi

  if command -v brew >/dev/null; then
    _upd_step "Homebrew"
    # --yes: Homebrew 7 asks for confirmation by default (ask mode)
    # gcloud-cli is an auto_updates cask, which plain `brew upgrade` skips
    brew update && brew upgrade --yes && brew upgrade --yes --cask --greedy gcloud-cli && brew cleanup
  fi

  if command -v npm >/dev/null; then
    _upd_step "npm global packages (e.g. pyright)"
    # npm and corepack come with apt's nodejs, so apt updates them
    local -a _npm_pkgs=(${(f)"$(npm ls -g --depth=0 --json 2>/dev/null | jq -r '.dependencies // {} | keys[]' | grep -vxE 'npm|corepack')"})
    if (( $#_npm_pkgs )); then sudo npm install -g --no-fund "${_npm_pkgs[@]/%/@latest}"; else echo "none"; fi
  fi

  if command -v uv >/dev/null && [[ -n "$(uv tool list 2>/dev/null | grep -v '^No tools')" ]]; then
    _upd_step "uv tools (e.g. sqlite-web)"
    uv tool upgrade --all
  fi

  if [[ -f ~/dev/pihole/docker-compose.yml ]]; then
    _upd_step "Pi-hole (docker image)"
    (cd ~/dev/pihole && sudo docker-compose pull && sudo docker-compose up -d && sudo docker image prune -f)
  fi

  _upd_step "Agents"
  _upd_sub "Hermes"      _upd_hermes
  _upd_sub "OpenClaw"    _upd_openclaw
  _upd_sub "Restart updated agent services" _upd_restart_agents

  _upd_step "Oh My Zsh";   ZSH=$ZSH command zsh -f $ZSH/tools/upgrade.sh -v minimal
  if (( _upd_due )); then
    _upd_step "git repos in ~/dev (every 5th run)"; _upd_repos
    _upd_step "pi-status web page (restart to load pulled code)"; _upd_pi_status
  else
    _upd_step "git repos in ~/dev"; echo "skipped, next update in $_upd_left run(s)"
  fi

  if (( _upd_due )); then
    _upd_step "Settings backup (machine-setup/raspberry-pi, every 5th run)"
    _upd_backup || print -P "%F{yellow}settings backup failed%f (see above)"
  else
    _upd_step "Settings backup (machine-setup/raspberry-pi)"; echo "skipped, next backup in $_upd_left run(s)"
  fi

  # Reboot needed if a newer kernel of the running flavour (e.g. rpt-rpi-2712) is installed
  local running=$(uname -r) newest
  newest=$(ls /lib/modules | grep -F -- "+${running#*+}" | sort -V | tail -1)
  if [[ -f /var/run/reboot-required || ( -n $newest && $newest != $running ) ]]; then
    print -P "\n%F{yellow}Reboot required%f (running $running, installed $newest)"
  else
    print -P "\n%F{green}All done.%f"
  fi
}
