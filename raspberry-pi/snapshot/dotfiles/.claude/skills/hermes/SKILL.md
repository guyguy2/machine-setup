---
name: hermes
description: Find your way around the Hermes agent (Nous Research) installed on this Pi (where its docs, source, config and state live, its CLI, and the gotchas already learned) before changing or debugging it. Use whenever a task touches Hermes (config.yaml, skills, memories/USER.md, terminal tool, toolsets, sessions, the dashboard, updates), or the user mentions Hermes, the agent lab or "both agents".
---

# Hermes on this Pi

Hermes is one of the two agents the user trains and compares in `~/dev/agent-lab` (the other is OpenClaw; see the
`openclaw` skill). **Start with `~/dev/agent-lab/agents.md`**: it records how Hermes is installed, configured and
limited *here*, plus every change made so far and why. `~/dev/agent-lab/CLAUDE.md` has the lab's safety rules.
The newest file in `~/dev/agent-lab/docs/` says where the work stands.

## Where things are

| What | Where |
|---|---|
| Docs (match the installed version) | `~/.hermes/hermes-agent/website/docs/` (Markdown/MDX). Start with `user-guide/configuration.md`, `user-guide/which-file-does-what.md` (SOUL/USER/MEMORY/AGENTS files), `user-guide/features/skills.md`, `user-guide/security.md`, `reference/faq.md`, `user-guide/cli.md`. Grep the tree for a config key |
| Live docs | https://hermes-agent.nousresearch.com/docs/ |
| Source (this is what runs) | `~/.hermes/hermes-agent` (git checkout from the official installer). Terminal tool: `tools/terminal_tool.py`, `tools/environments/local.py`; config loader: `hermes_cli/config.py`. Read the source when docs are thin |
| Bundled skills | `~/.hermes/hermes-agent/skills/` (e.g. `productivity/google-workspace`), optional ones in `optional-skills/` |
| Binary | `~/.local/bin/hermes` (on PATH). Version: `hermes --version`. Update: `hermes update --yes` (part of `upd`) |
| Config | `~/.hermes/config.yaml` (secrets in `~/.hermes/.env`); check with `hermes config check`, `hermes status` |
| Always-loaded notes | `~/.hermes/memories/USER.md` (and `MEMORY.md`): entries separated by a line with `§` (`"\n§\n"`); the agent edits them with its `memory` tool, so keep entries short and self-contained. `~/.hermes/SOUL.md` is identity |
| Sessions / tool calls | SQLite `~/.hermes/state.db`, table `messages` (`session_id`, `role`, `tool_calls` JSON, `tool_call_id`, `content`); `--oneshot` prints `session_id: ...` at the end. Text log: `~/.hermes/logs/agent.log` |
| Dashboard | systemd user unit `hermes-dashboard.service` (and `hermes-proxy.service`) |

## CLI essentials

`hermes --help`, `hermes <cmd> --help`. One unattended turn (what the lab uses):
`hermes chat --oneshot --quiet --query "<prompt>" --toolsets terminal,skills`. `hermes status` (model, auth),
`hermes model`, `hermes skills ...`, `hermes logs`.

## Learned the hard way

- **Terminal PATH**: the terminal tool rebuilds its environment from a bash login shell, so the PATH Hermes was
  started with does **not** reach its commands. Use `terminal.shell_init_files` in config.yaml (setting it replaces
  the default `~/.profile`/`~/.bash_profile`/`~/.bashrc` auto-source, so list those too). Here it sources
  `~/dev/agent-lab/tools/hermes-env.sh`, which puts the lab's wrappers first. Check with a oneshot that runs
  `echo $PATH; command -v gws`.
- **Skills**: `skills.external_dirs: [~/.agents/skills]` (shared skills, copied there by
  `~/dev/agent-lab/bin/lab skills`); the agent loads one with its `skill_view` tool. `skill_manage` can write skills
  to `~/.hermes/skills`.
- **No exec allowlist**: the terminal only has a denylist of dangerous patterns plus `approvals.deny` globs. Wrappers
  on PATH are a convention, not a barrier; in lab runs `bin/loop` limits Hermes to the `terminal,skills` toolsets and
  never passes `--yolo`.
- **Model / auth**: provider `anthropic`, `claude-sonnet-5-5`. An API key in `~/.hermes/.env` wins over the
  borrowed Claude Code login (`auth.adopt_external_logins: true`); the user chose to leave it so (agents.md).
- Back up config files before editing (`config.yaml.bak-YYYY-MM-DD`, `USER.md.bak-YYYY-MM-DD`), then prove the change
  with a real oneshot or `~/dev/agent-lab/bin/loop UC-NNN --agents hermes` and read `runs/*_hermes.tools.txt`.
