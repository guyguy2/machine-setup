# Machine: Raspberry Pi 5 (Raspberry Pi OS / Debian, arm64), shell zsh + Oh My Zsh

## Installing software: which package manager

Install each tool from exactly one source. Before installing, check `whence -a <tool>` so you don't create a duplicate.

- **apt** for the system: kernel, firmware, drivers, libraries, desktop apps, compilers and build tools
  (build-essential, cmake), the login shell (zsh), git, and anything a system service depends on
  (tailscale, docker, nodejs via the NodeSource repo).
- **Homebrew** (`/home/linuxbrew/.linuxbrew`) for user command-line tools where a recent version matters, e.g.
  fzf, ripgrep, gh, neovim, yq (mikefarah, Go), gcloud (cask `gcloud-cli`), and Claude Code (cask
  `claude-code@latest`; the plain `claude-code` cask is the lagging stable channel). Install new CLI tools with
  `brew install` unless they belong on apt per the line above. If one is already on apt, remove the apt copy after
  switching. The full list isn't kept here: `~/dev/machine-setup/raspberry-pi/snapshot/Brewfile` records what was
  installed as of the last `upd` (which regenerates it with `brew bundle dump` and pushes it), and `brew leaves`
  plus `brew list --cask` show what's installed right now.
- **uv** (`uv tool install`) for Python CLI tools; **npm -g** (`sudo npm install -g`, apt's NodeSource npm) only for
  Node tools. pyright is one (a Node tool, even though it checks Python).
- **Manual installs** only when there's no package. Currently that's just Hermes: the Homebrew formula (0.22.4) was
  missing the `anthropic` library, so Hermes crashed at startup. It's installed with its official installer
  (`curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`, a git checkout in `~/.hermes/hermes-agent`,
  command in `~/.local/bin`) and updated with `hermes update --yes`. Switch back to brew if the formula is fixed.

## Python code intelligence

The `pyright-lsp` Claude Code plugin (user scope) runs pyright on Python files: after each edit Claude sees new type
errors, and the `LSP` tool finds definitions and references by symbol. Use the LSP tool instead of grep when following
a Python symbol across files (callers, overrides, where a name is defined), and fix new diagnostics before running
tests. For a project's imports to resolve, its `pyproject.toml` needs `[tool.pyright]` with `venvPath = "."` and
`venv = ".venv"`. Run `pyright` in the project for a full check.

The Homebrew directories are deliberately placed *after* `/usr/bin` on PATH (see `~/.zshrc`), so brew's dependency
formulae (util-linux, curl, bash, ncurses, ...) never shadow system commands. Don't "fix" this ordering.

## Browser sign-ins over SSH

I usually work on this Pi over SSH from a Mac, so an OAuth login that redirects to `http://localhost:<port>`
(gws, gh, gcloud, etc.) opens on the Mac and fails with "site can't be reached". To finish it without the Pi's
desktop: have me paste the failed redirect URL, confirm the CLI is still listening (`ss -ltnp | grep <port>`), then
`curl '<that URL>'` on the Pi to hand it the code. The code is single-use and expires within minutes, so do it right
away. Alternative for next time: `ssh -L <port>:localhost:<port>` from the Mac before opening the link. Prefer a
CLI's `--no-launch-browser`/device-code mode when it has one.

## Personal data store (`me`)

The user's personal details (name, address, email, phone, family, accounts) live in a SQLite store at
`/home/guy/.local/share/agent-lab/me/facts.db` (with `pending.db` for agents' proposals), not in any repo and not backed up by choice. Built and
documented in `~/dev/agent-lab/me.md`: read that first. Look things up with `~/dev/agent-lab/tools/bin/me get|search|show`
or browse with `~/dev/agent-lab/bin/me-admin view`; only the user changes values (`bin/me-admin set|edit|review`).
Don't read the database files directly or copy its values into docs, commits or memory notes unless asked.
If a task needs a personal detail the store lacks, or `me get` returns CHOOSE/MISSING, tell the user what to add and the
`bin/me-admin set` command (or record it with `me propose --missing`); `bin/me-admin gaps` ranks what's been missed.

## Updating

`upd` (defined in `~/.zshrc`) updates everything: apt (packages + kernel), Pi bootloader status, Homebrew
(including Claude Code), npm global packages, OpenClaw, Hermes (its own `hermes update`), uv, Oh My Zsh, and `git pull --ff-only` for repos in `~/dev`. When adding a tool that
`upd` doesn't already cover, add an update step for it to `upd`.

## Code over LLM judgment

Use LLMs where judgment is needed (understanding a request, talking to the user, reading unstructured text), not for
everything. Anything that can be deterministic code should be code: queries and filters, counts, parsing, checks and
verification, safety gates (e.g. "dry run before --yes"), and repeatable steps in a runbook, skill or my own
workflow. A skill or prompt then says which command to run and what to tell the user, and the command enforces the
rest. When I notice a mechanical step being left to a model (an agent's or my own), turn it into a script, or a check
in an existing one.
