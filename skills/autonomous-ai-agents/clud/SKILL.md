---
name: clud
description: Delegate autonomous runs to the clud harness.
version: 1.0.0
author: Zach Vorhies (@zackees) + Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [clud, delegation, autonomous-agent, claude-code, codex]
    category: autonomous-ai-agents
    related_skills: [claude-code, codex]
---

# clud Skill

`clud` launches a fully autonomous agent run in a target directory — Claude Code
by default, or Codex — in permissive mode, and streams the result back. Use it
for self-contained coding, investigation, or multi-agent pipelines that need
their own terminal and no supervision. It is not a chat surface: one prompt in,
one transcriptable run out.

## When to Use

- A task is big enough to want its own agent session: port a file, fix a batch
  of issues, audit a repo, run a plan → implement → review pipeline.
- The run must outlive the current turn (detached) and be harvested later.
- You want a second opinion from a different harness or model.

Decision-making counts as work. When the question is a judgment call - which
approach, which root cause, whether this is worth doing - hand it to clud rather
than deciding it alone: the child sees the code in its own context and its
answers are usually better. Ask for the decision *and* its evidence, then verify
the evidence yourself.

Use `delegate_task` instead when the work is a quick bounded subtask inside this
conversation; use a plain `terminal` call when one command answers the question.

## Prerequisites

- `clud` on `PATH` (`clud --help`).
- The backend's own credentials: Claude Code OAuth for the default harness, or
  Codex/OpenAI credentials for `--codex`. A failed smoke run usually means
  credentials, not clud.
- A git repository to run in — clud records the repo root and worktrees.

## How to Run

One-shot run in the current directory, prompt passed as a single argument:

```text
clud -p "<prompt>"
```

Long or quote-heavy prompts: write the prompt to a file with `write_file`, then
pass it through the shell:

```text
PROMPT="$(cat /path/to/prompt.md)" && clud --detach --name <slug> -p "$PROMPT"
```

`--detach` forks a daemon-owned session and prints
`session sess-<id> running in background; attach with: clud attach sess-<id>`
(the launcher exits 0 immediately — that is the fork, not the result).

## Quick Reference

| Action | Command |
| --- | --- |
| One-shot | `clud -p "<prompt>"` |
| Backend | `--claude` (default) / `--codex` |
| Model | `--model <model>` |
| Effort | `--effort low\|medium\|high` (CLI only) |
| Detach | `--detach --name <slug>` |
| Rejoin | `clud attach <id>` |
| List | `clud list` |
| Logs | `clud logs <id>` |
| End one | `clud kill <id>` |
| End all | `clud slay` |
| Daemon API | `clud daemon api-info --json` |

## Procedure

1. **Write a self-contained prompt.** The child knows nothing about this
   conversation: put the repo path, the reading order (`AGENTS.md` first), the
   exact deliverable, the file allowlist, and the hard rules in the prompt
   itself.
2. **Smoke-test the model first** with a one-line prompt, then confirm the
   transcript's `"model"` field rather than the echoed name.
3. **Launch detached** from the target directory:
   `clud --detach --name <slug> -p "$PROMPT"`. Do not wrap it in `nohup` or
   `disown` — the daemon already owns the process.
4. **Monitor without polling transcripts in a tight loop**: read the session
   record under `$HOME/.clud/state/sessions/<id>.json` (`exit_code` stays
   `null` until the run ends), tail `clud logs <id>`, or gate a cron job on a
   script that prints only `RUNNING`/`DONE`.
5. **Harvest the deliverable** from the harness transcript: Claude runs under
   `$HOME/.claude/projects/<dashed-cwd>/`, Codex under
   `$HOME/.codex/sessions/<YYYY>/<MM>/<DD>/`; for Codex, the final text is the
   `task_complete` payload's `last_agent_message`.
6. **Verify independently.** Confirm the artifact the run claims (commit, PR,
   file) with `terminal`/`search_files`, not with the run's self-report.

## Pitfalls

- **The MCP bridge caps at 420 s** and reports a timeout while the child keeps
  running. Prefer the CLI with `--detach` for anything longer than a smoke test;
  recover an in-flight run from its transcript instead of relaunching.
- **`HOME` traps.** Launched from a Hermes gateway, the child may see a profile
  home instead of the real one and fail auth instantly. Set
  `HOME=/home/niteris` (or the real user home) on the launch, and prefer a
  real-home smoke test that fails fast.
- **`--detach` exit codes lie.** The launch record's `exit_code` flips to 0 at
  fork time; it tracks the launcher, not the child.
- **Disk.** Detached runs accumulate worktrees and temp data; a full disk looks
  like a mysterious build failure. Check free space before a fleet of runs.
- **Prompt hazards.** A prompt containing a shell-dangerous literal can trip a
  guard before `clud` starts; assemble such strings at runtime in a script
  instead of inlining them.
- **Model names drift.** Confirm the exact registered model string from the
  transcript's `"model"` field, not from memory or the echoed argument.

## Verification

- The run is done when `exit_code` in the session record is non-null and the
  transcript's last assistant message (or Codex `task_complete`) exists.
- The work is done when the artifact it claims exists on disk or in git:
  check with `terminal` (`git log`, `git status`) or `read_file`.
- If a run stalls, `clud logs <id>` shows the last streamed events; kill it with
  `clud kill <id>` rather than starting a second run against the same repo.
