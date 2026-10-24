---
name: openclaw
description: Find your way around the OpenClaw agent installed on this Pi (where its docs, source, config and state live, its CLI, and the gotchas already learned) before changing or debugging it. Use whenever a task touches OpenClaw (gateway, workspace, AGENTS.md, skills, exec allowlist/approvals, tools.fs, models, channels), or the user mentions OpenClaw, the agent lab or "both agents".
---

# OpenClaw on this Pi

OpenClaw is one of the two agents the user trains and compares in `~/dev/agent-lab` (the other is Hermes; see the
`hermes` skill). **Start with `~/dev/agent-lab/agents.md`**: it records how OpenClaw is installed, configured and
locked down *here*, plus every change made so far and why. `~/dev/agent-lab/CLAUDE.md` has the lab's safety rules.
The newest file in `~/dev/agent-lab/docs/` says where the work stands.

## Where things are

| What | Where |
|---|---|
| Docs (match the installed version) | `~/dev/openclaw_node/node_modules/openclaw/docs/` (Markdown). **Index: `docs/docs_map.md`** (every page's headings: grep it to find the page). Key pages: `tools/skills.md`, `tools/skills-config.md`, `tools/exec.md`, `concepts/system-prompt.md`, `concepts/agent-workspace.md`, `gateway/security/`, `cli/` |
| Live docs | https://docs.openclaw.ai (also `openclaw docs <query>`, which searches them) |
| Installed package | `~/dev/openclaw_node` (npm; `~/dev/openclaw_node` is a symlink into `~/dev/machine-setup/raspberry-pi/services/`). Bundled skills: `node_modules/openclaw/skills/`. Built JS: `node_modules/openclaw/dist/*.mjs` (grep it when the docs are silent) |
| Source checkout | `~/dev/openclaw` (reference only; not what runs) |
| Binary | `~/dev/openclaw_node/node_modules/.bin/openclaw` (not on PATH) |
| Config | `~/.openclaw/openclaw.json` (read/write with `openclaw config get|set|unset <path>`) |
| Exec approvals / allowlist | SQLite state in `~/.openclaw/state/`; `openclaw approvals get --json`, `approvals set --stdin`, `exec-policy show --agent main` |
| Workspace (agent `main`) | `~/.openclaw/workspace/`: `AGENTS.md` (always-loaded instructions; tool notes under `## Tools`), `SOUL.md`, `USER.md`, `IDENTITY.md`, `memory/`, `skills/` |
| Logs / Claude sessions | OpenClaw runs the `claude` CLI in the workspace, so its tool calls are in `~/.claude/projects/-home-guy--openclaw-workspace/*.jsonl` |

## CLI essentials

`openclaw --help` and `openclaw <cmd> --help` at every level. Most commands need the gateway: start it with
`~/dev/agent-lab/bin/lab use openclaw` (transient unit `lab-openclaw`, loopback :18789) and stop it with
`lab use none` (one agent at a time: RAM). One turn: `openclaw agent --agent main -m "<prompt>"`. Health:
`openclaw health --json`, `openclaw doctor`. Skills: `openclaw skills list`.

## Learned the hard way

- **Skills**: OpenClaw lists skills from `<workspace>/skills` (highest), `<workspace>/.agents/skills`,
  `~/.agents/skills`, `~/.openclaw/skills`, bundled, and `skills.load.extraDirs`. The model then `read`s the
  SKILL.md at the listed path. With **`tools.fs.workspaceOnly: true`** (set here, to keep it out of the `me`
  database) the read tool refuses anything outside the workspace ("Path escapes sandbox root"), so skills in
  `~/.agents/skills` are listed but unreadable. That's why the lab copies its shared skills into
  `~/.openclaw/workspace/skills` too (`~/dev/agent-lab/bin/lab skills`). Symlinks out of the workspace are
  rejected; copies work.
- **Exec**: `tools.exec.mode: allowlist`; only the lab wrappers in `~/dev/agent-lab/tools/bin` are allowed
  (`tools.exec.pathPrepend` puts that dir first). An entry can carry an `argPattern` regex over the arguments;
  `openclaw approvals allowlist add` can't set it, so edit the JSON from `approvals get --json` and apply it with
  `approvals set --stdin`. A path-only entry for the same binary makes the pattern moot. Allowlist misses are
  denied without asking (`ask: off`).
- **Runtime**: model `anthropic/claude-sonnet-5-5` on the `claude-cli` runtime (the installed `claude` with its own
  login). No API key is configured; keep it that way (house rule in the lab's CLAUDE.md).
- The workspace dir is a git repo with no commits; it isn't in agent-lab's git. Back up a file before editing it
  (`*.bak-YYYY-MM-DD`).
- After changing config, skills or the allowlist, prove it with a real turn (or `~/dev/agent-lab/bin/loop UC-NNN
  --agents openclaw`) and read the tool log (`runs/*_openclaw.tools.txt`).
