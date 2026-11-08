---
name: hermes
description: Find your way around the Hermes agent (Nous Research) installed on this Pi (where its docs, source, config and state live, its CLI, and the gotchas already learned) before changing or debugging it. Use whenever a task touches Hermes (config.yaml, skills, the skill index and curator, memories/USER.md, terminal tool, toolsets, sessions, the gateway and Telegram bot, the dashboard, updates), or the user mentions Hermes, the agent lab or "both agents".
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
| Source (this is what runs) | `~/.hermes/hermes-agent` (git checkout from the official installer; the only copy: don't clone another, a newer `main` would mislead). Terminal tool: `tools/terminal_tool.py`, `tools/environments/local.py`; config loader: `hermes_cli/config.py`; skill index: `agent/prompt_builder.py`, `agent/skill_utils.py`; memory files: `tools/memory_tool_store.py`. Read the source when docs are thin |
| Running Hermes' own code | Its bundled Python, not the system one: `hermes --print-runtime-command` prints it. In a `-I -c` snippet, `sys.path.insert(0, '~/.hermes/hermes-agent')` (expanded), then `import hermes_bootstrap` before other Hermes modules so their dependencies load |
| Bundled skills | `~/.hermes/hermes-agent/skills/` (e.g. `productivity/google-workspace`), optional ones in `optional-skills/` |
| Binary | `~/.local/bin/hermes` (on PATH). Version: `hermes --version`. Update: `hermes update --yes` (part of `upd`) |
| Config | `~/.hermes/config.yaml` (secrets in `~/.hermes/.env`); check with `hermes config check`, `hermes status` |
| Always-loaded notes | `~/.hermes/memories/USER.md` (and `MEMORY.md`): entries separated by a line with `§` (`"\n§\n"`); the agent edits them with its `memory` tool, so keep entries short and self-contained. `~/.hermes/SOUL.md` is identity |
| Sessions / tool calls | SQLite `~/.hermes/state.db`, table `messages` (`session_id`, `role`, `tool_calls` JSON, `tool_call_id`, `content`); `--oneshot` prints `session_id: ...` at the end. Text log: `~/.hermes/logs/agent.log` |
| Services | systemd user unit **`hermes-gateway.service`** (enabled, linger on): the messaging gateway that serves the Telegram bot; oneshots also run through it and it caches provider plugins, so `systemctl --user restart hermes-gateway` after plugin or config changes. Lab runs stop it and `bin/lab restore` starts it again. `hermes-dashboard.service` is disabled (the dashboard runs on demand); `hermes-proxy.service` is static |

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
- **Skills**: `skills.external_dirs: [~/.agents/skills]` (shared skills, copied to `~/.agents/skills/mine/` by
  `~/dev/agent-lab/bin/lab skills`, read-only; the parent folder is the category, so they show as "mine"); the agent
  loads one with its `skill_view` tool. `skill_manage` writes new skills to `~/.hermes/skills` (or `skills.create_dir`
  when set; not set here) and patches existing skills where they live, external dirs included (hence the read-only
  copies; `hermes curator lock NAME` is the built-in way to stop it).
- **The skill index shows only 60 characters of each description** (`SKILL_PROMPT_DESC_LIMIT` in
  `agent/skill_utils.py`, cut at a word and ended with "..."; `skill_manage` refuses a new or changed description
  longer than that). A "Use when the user says ..." later in the description never reaches Hermes, so start every
  description with a routing phrase of at most ~56 characters naming the domain or command. `bin/lab skill-check`
  prints that head (HEAD) and fails one that names neither. The index is cached in
  `~/.hermes/.skills_prompt_snapshot.json`, which rebuilds itself when a SKILL.md changes; a running Telegram session
  keeps its prompt until `/new`.
- **USER.md budget**: `memory.user_char_limit` (2800 here) caps `USER.md`, and the memory tool refuses additions past
  it. It holds one routing rule, marked `(skills: mine)`, instead of a pointer per skill; add a per-skill pointer
  (`bin/lab wire`, which warns above 90% and keeps the last 3 backups) only for a hard rule such as clean-gmail's or
  pay-bills'.
- **Curator**: a background pass over *agent-created* skills in `~/.hermes/skills` (never external dirs or hub skills,
  and bundled ones only if `curator.prune_builtins` is on): marks unused ones stale after 14 days and archives them to
  `~/.hermes/skills/.archive/` after 30; the LLM consolidation pass is off. `hermes curator status | run --dry-run |
  pin NAME | lock NAME`. It and the agent's own `skill_manage` are where skills under `~/.hermes/skills` that aren't in
  any repo come from.
- **Bundled skills edited locally** stop updating: `hermes skills list-modified`, `hermes skills diff NAME`, `hermes
  skills reset NAME [--restore]`. To keep a bundled skill from competing with a shared one, add it to
  `skills.disabled` (as `obsidian` is) rather than editing it.
- **No exec allowlist**: the terminal only has a denylist of dangerous patterns plus `approvals.deny` globs. Wrappers
  on PATH are a convention, not a barrier; in lab runs `bin/loop` limits Hermes to the `terminal,skills` toolsets and
  never passes `--yolo`.
- **Model / auth**: provider `anthropic`, `claude-sonnet-5-5`. An API key in `~/.hermes/.env` wins over the
  borrowed Claude Code login (`auth.adopt_external_logins: true`); the user chose to leave it so (agents.md).
- **Fallback to `agy`** (2026-11-07): `fallback_providers` → Gemini via the user plugin
  `~/.hermes/plugins/model-providers/antigravity` (`agy acp`). Details and why not Claude-via-agy: agents.md, "Backup
  model". Oneshots go through `hermes-gateway.service`, which caches provider plugins: restart it after plugin changes.
- Back up a config file before editing it (`config.yaml.bak-YYYY-MM-DD`, `USER.md.bak-YYYY-MM-DD`), keep only the
  newest 3 backups of each (older ones pile up; the nightly backup has history), and never copy `~/.hermes/.env` or
  `auth.json` (each copy is another copy of the keys). Once the Hermes config is versioned in a git repo (planned),
  commit before editing instead. Then prove the change with a real oneshot or `~/dev/agent-lab/bin/loop UC-NNN
  --agents hermes` (both cost money) and read `runs/*_hermes.tools.txt`.
