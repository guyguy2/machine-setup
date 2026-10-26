---
name: train-agents
description: Teach the user's two agents on this Pi, OpenClaw and Hermes, a new real-world task (or fix how they do one), the same way for both. Covers exploring routes, building a deterministic command, one shared skill, wiring each agent, and verifying with real lab runs. Use when the user says "train/teach the agents (or Hermes / OpenClaw) to ...", "add a skill for both agents", "make the agents able to ...", "explore how the agents could ...", or runs /train-agents.
argument-hint: <the task, in the user's words>
---

# Train the agents: $ARGUMENTS

You are the **orchestrator**. The user wants OpenClaw and Hermes to learn the task above so that it works the same
way in both, as one shared skill and one shared command. You own the conversation with the user, every decision,
and every check. Subagents do focused work and report back to you. Don't hand them decisions.

The lab's scripts do the mechanical parts; your job is the judgment around them:

| Script | Does |
|---|---|
| `bin/lab new-skill NAME`, `bin/lab new-uc "TITLE"` | scaffold the skill (with the ground rules) and the use case |
| `bin/lab skills NAME` | install the skill to both agents |
| `bin/lab wire NAME --pointer "..." [--args REGEX]` | OpenClaw allowlist entry + the same pointer line for both agents, with backups |
| `bin/lab skill-check NAME` | is it ready? FAIL / WARN / TESTED (latest run per agent, with its tools check) |
| `bin/loop UC-NNN` | run both agents (one at a time, read-only), check their tool calls (`tools_check`), judge, compare |

## Before anything

1. Load the `openclaw` and `hermes` Claude Code skills. Read `~/dev/agent-lab/CLAUDE.md` (lab invariants, "code
   over LLM judgment"), `agents.md` sections "Shared skills" and the section of any related skill, and the newest
   file in `docs/`. Check the existing skills (`ls ~/dev/agent-lab/skills`) and use cases (`use-cases/`): extend
   one rather than adding a near-duplicate.
2. Run `~/dev/agent-lab/bin/lab skill-check` so you know the starting state.

## Phase 1: explore and decide (you; read-only)

Find out what the task really involves before building anything:

- The exact words the user will say (these become the skill's trigger phrases and the test prompt).
- What "done" looks like, what it reads, and what it changes, sends, deletes or pays.
- Every route: an official CLI or API, an existing wrapper in `tools/bin` (`gws`, `web`, `me`, ...), the shared
  browser (`bin/browser`, browser.md variants), each agent's native skill (OpenClaw bundled
  `node_modules/openclaw/skills/`, Hermes `~/.hermes/hermes-agent/skills/`). For each route: how it signs in
  (who does the login, how long it lasts, whether it works over SSH, what the user must do), what it can and can't do,
  what it costs, and how it can be held read-only or gated.
- Explore with read-only commands only. Never sign in, submit, pay or send while exploring. Personal details come
  from `me get`, never from guesses.

If the user asked for exploration or a report, stop here. Write the report (options compared, recommendation,
what the user must do), publish it as an Artifact page, and wait. Otherwise ask the user with AskUserQuestion when
there is a real choice (shared vs an agent's native route, scope, where to stop and ask). Their answer is a decision:
record it in agents.md later.

## Phase 2: build and wire (writer subagent, then you)

1. Spawn one `general-purpose` subagent with the **writer brief** from `briefs.md` (in this skill's folder),
   filled in with the decided design. It writes `tools/bin/<cmd>`, `skills/<name>/SKILL.md` and the use case.
2. Check its work yourself. You own it now.
   - Read the command and the skill.
   - Run the command by hand: the read-only/dry-run path, every error path you can trigger, and that writes refuse
     while `~/.local/share/agent-lab/lab-run` exists.
   - The use case has `skill: <name>` in its front matter, so `bin/loop` checks the tool calls. Its `risk:` follows
     the rule in the writer brief.
3. `bin/lab skills <name>`.
4. Write the pointer line: one sentence the agents always see, saying when to use the command and naming the skill,
   in the style of the existing ones (`grep -h 'skill: ' ~/.hermes/memories/USER.md`). Run
   `bin/lab wire <name> --pointer "<text with (skill: name)>" [--args '<argPattern>'] --dry-run`, read the diff,
   then run it without `--dry-run`. `--args` is a regex over the command's arguments for OpenClaw's allowlist; give
   one when the command takes a fixed set (clean-gmail: `^(--yes|--help|-h|help)?$`).
5. `bin/lab skill-check <name>`: no FAIL. WARNs left: "never run", and "no lab-run check" if the command only reads.

## Phase 3: test both agents, fix at the root

1. `bin/loop UC-NNN --repeat 2` (both agents, one after the other, judged): the same prompt, word for word, for
   both. A pass needs **both** `tools_check: pass` in the run note (code: read the skill, ran its command, no
   `--yes`, no other lab command) and the judge's pass (answered correctly, stopped for a yes where the skill says
   so). Read both run notes and the comparison in `comparisons/`.
2. When an agent fails and the cause isn't plain from its run note and `*.tools.txt`, spawn the **per-agent
   subagent** for that agent only (`briefs.md`). It reads only that agent's docs, source and config, so the two
   agents' quirks don't get mixed up. Never have two running at once: only one agent fits in the Pi's RAM, and
   `bin/loop` refuses to start while another lab run holds the `lab-run` marker.
3. Fix at the root, and once, so both agents keep the same skill. A missing gate belongs in the command; an agent
   that doesn't find the skill needs a better description or pointer line (`bin/lab wire` again); a config gap
   goes in agents.md. After a shared change, run `bin/lab skills <name>` and test both agents again. Never reword
   the use-case prompt to make an agent pass.
4. Write tasks: lab runs stay read-only (the `lab-run` marker). The first real write is done with the user, one
   agent at a time, by hand: give them the exact prompt to type and what to check afterwards.

## Phase 4: record and report

- agents.md: a section for the task (command, gates, the `wire` pointer and argPattern, the user's decisions and
  dates). README's layout and CLAUDE.md's command list if new commands were added. A
  `docs/<task>-session-YYYY-MM-DD.md` if work remains.
- `bin/lab table`. Update the shared-skills list in the memory note `agents-native-vs-shared`.
- Ask before committing; agent-lab is a private repo you commit and push like any other once the user agrees.
- Tell the user: what each agent can do now and the exact words to say, the scores and tools checks, the WARNs
  left, and plainly, anything they must do themselves (logins, tokens, console settings, approvals).

## Never

- Weaken a lab invariant (CLAUDE.md "Lab invariants"), widen Hermes' lab toolsets, or add an API key to OpenClaw.
- Edit installed copies of skills (`~/.agents/skills/mine`, `~/.openclaw/workspace/skills`): edit only the source in
  `skills/`, then `bin/lab skills`.
- Let an agent, a subagent or yourself complete a payment, send a message or delete anything without the user's yes
  in the moment.
- Handle the user's passwords or tokens. Logins are theirs (see the SSH OAuth note in the global CLAUDE.md).
- Edit an agent config file by hand without a backup (`<file>.bak-YYYY-MM-DD`); `bin/lab wire` makes its own.
