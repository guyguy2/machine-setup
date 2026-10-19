# Machine: Raspberry Pi 5 (Raspberry Pi OS / Debian, arm64), shell zsh + Oh My Zsh

## Installing software: which package manager

Install each tool from exactly one source. Before installing, check `whence -a <tool>` so you don't create a duplicate.

- **apt** for the system: kernel, firmware, drivers, libraries, desktop apps, compilers and build tools
  (build-essential, cmake), the login shell (zsh), git, and anything a system service depends on
  (tailscale, docker, nodejs via the NodeSource repo).
- **Homebrew** (`/home/linuxbrew/.linuxbrew`) for user command-line tools where a recent version matters:
  fzf, bat, jq, ripgrep, fd, tmux, zellij, gh, git-delta, eza, tree, zoxide, direnv, neovim, yq (mikefarah, Go),
  shellcheck, sqlite, btop, just, entr, hyperfine, tealdeer, and Claude Code (cask `claude-code@latest`; the
  plain `claude-code` cask is the lagging stable channel). Install new CLI tools with `brew install`
  unless they belong on apt per the line above. If one is already on apt, remove the apt copy after switching.
- **uv** (`uv tool install`) for Python CLI tools; **npm -g** only for Node tools.
- **Manual GitHub-release installs** only when there's no package. Currently that's just OpenHuman
  (`open-human` .deb + `/opt/openhuman-core`).

The Homebrew directories are deliberately placed *after* `/usr/bin` on PATH (see `~/.zshrc`), so brew's dependency
formulae (util-linux, curl, bash, ncurses, ...) never shadow system commands. Don't "fix" this ordering.

## Updating

`upd` (defined in `~/.zshrc`) updates everything: apt (packages + kernel), Pi bootloader status, Homebrew
(including Claude Code and Hermes), OpenClaw, OpenHuman, uv, Oh My Zsh, and `git pull --ff-only` for repos in `~/dev`. When adding a tool that
`upd` doesn't already cover, add an update step for it to `upd`.
