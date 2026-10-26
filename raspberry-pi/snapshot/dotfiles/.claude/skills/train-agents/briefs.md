# Subagent briefs for train-agents

Fill in every `<...>`. A subagent knows only what its brief says, so paste the decisions themselves, not "as we
discussed". Each brief ends with the report format, because you act on its report.

## Writer brief (Phase 2, `general-purpose`)

```
You are building the shared part of a new task for the user's two AI agents (OpenClaw and Hermes) in the agent lab
~/dev/agent-lab on this Raspberry Pi. Read ~/dev/agent-lab/CLAUDE.md first (lab invariants, "code over LLM
judgment") and agents.md, sections "Shared skills" and "Clean Gmail" (the worked example to copy:
tools/bin/clean-gmail + skills/clean-gmail/SKILL.md + use-cases/UC-010-*.md).

Task: <what the agents should do, in the user's words>
Trigger phrases the user will say: <...>
Decided design: <route, command name, what it reads, what it writes, gates, where it stops to ask, the user's choices>
Sign-in: <what exists, what the user does themselves>

Write:
1. tools/bin/<cmd>: stdlib python3 (or a thin sh wrapper that execs a real CLI, like tools/bin/td). Deterministic
   work goes here, not in the skill: queries, counts, filters, checks. It is read-only by default. Any write is
   `--yes` and only after a dry run in the last 30 minutes, executing exactly the saved plan (see clean-gmail's
   plan file). It refuses writes (exit 126) while ~/.local/share/agent-lab/lab-run holds a live pid, and logs
   each write to ~/.local/share/agent-lab/<cmd>.log. Short, plain output an agent can relay. Distinct exit codes
   with fixed markers (`AUTH EXPIRED` exit 2, refusals 126/4, `ERROR:` 1). `--help`. chmod +x.
2. skills/<name>/SKILL.md: create it with `bin/lab new-skill <name> </dev/null`, then fill it in. The description says
   what it does, "Use when the user says ..." with the trigger phrases, and "Runs through the `<cmd>` command."
   Keep the ground-rules block byte-for-byte. Steps match the command's real output. A "When it fails" table
   covers every marker the command prints.
3. A use case: `bin/lab new-uc "<title>" </dev/null`. The prompt is exactly the bare trigger phrase. Front matter
   `skill: <name>` (bin/loop then checks the tool calls). `risk:` is read-only when the command can't write during a
   lab run (it reads only, or it refuses writes under the lab-run marker: say so in a `# comment`, like UC-010);
   writes or money otherwise, and then bin/loop skips it. A `## Ground truth` sh block runs the read-only command.
   Success criteria include "used `<cmd>`, not another route" and "stopped for a yes" if it writes. Keep the headings and fences intact (bin/loop parses them).

Test the command by hand: help, dry run, each error path you can trigger, and the lab-run refusal (write your
shell's pid to the marker, try --yes, remove the marker). Do NOT run any write for real, sign in, or run an agent.
Then run `bin/lab skills <name>` and `bin/lab skill-check <name>`. A FAIL about OpenClaw's allowlist and WARNs about
pointer lines or missing runs are expected (someone else does those). Fix anything else.

Don't touch agent config (~/.openclaw, ~/.hermes), other skills, or git.
Report: the files you wrote, the commands you ran with their key output, the skill-check output, and open questions.
```

## Per-agent brief (Phase 3, `general-purpose`, only for an agent that failed; never two at once)

Use it with AGENT=OpenClaw or AGENT=Hermes, for the agent that failed.

```
You are the <AGENT> specialist. A shared skill failed its lab test on <AGENT> on this Raspberry Pi. Find out why,
fix it if the cause is <AGENT>'s own config, and report. Work only on <AGENT>. The other agent is handled
separately: don't read its config, start it, or change it.

First load the Claude Code skill `<openclaw|hermes>` (Skill tool): it says where <AGENT>'s docs, source, config and
state live, and lists the gotchas already learned. Read ~/dev/agent-lab/CLAUDE.md (lab invariants) and the
<AGENT> section of ~/dev/agent-lab/agents.md.

Skill: ~/dev/agent-lab/skills/<name>/SKILL.md (command tools/bin/<cmd>). Use case: <UC-NNN>, prompt "<prompt>".
Failed runs: <run note paths>, with tools_check "<value>" and the judge's verdict "<summary>".

1. Read the run notes, their *.tools.txt and *.transcript.txt. Where did it go wrong: didn't find or read the skill,
   didn't run `<cmd>`, used another route, didn't stop where the skill says, misread the output?
2. Find the cause in <AGENT>'s docs or source, not by guessing (how it lists and loads skills, its exec rules, its
   always-loaded instructions).
3. If the cause is <AGENT>'s own config, fix it (back up the file as <file>.bak-YYYY-MM-DD first) and re-run with
   `~/dev/agent-lab/bin/loop <UC-NNN> --agents <agent>` (at most 3 runs in total). If it says another lab run is in
   progress, wait and retry. Never start the other agent yourself or use `lab use`.

Do NOT edit skills/, tools/bin/, use-cases/, templates/, bin/, the pointer lines (the orchestrator sets them with
`bin/lab wire`), or git. If the skill, command or pointer needs a change, propose the exact diff in your report.
Never run a write for real, sign in, or handle tokens.
Report: the cause of each failure with evidence (file and line, or doc page), what you changed (with backup paths),
each re-run's tools_check, outcome and score with the run-note path, and proposed shared changes as diffs.
```
