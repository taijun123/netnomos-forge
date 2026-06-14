---
name: worksite-handoff
description: Capture, load, and refresh project working context for Codex, Claude, subagents, or any AI model handoff. Use when the user asks to save memory, preserve the worksite, continue from another AI, switch models, split work across agents, resume a repo task, read handoff docs, or update CLAUDE_HANDOFF/HANDOFF-style project state before stopping.
---

# Worksite Handoff

Use this skill to keep a project resumable across AI models without relying on chat history. Treat the handoff file as the portable source of truth for current objective, repo state, services, validations, decisions, blockers, and next actions.

## Default Files

Prefer these files in order:

1. `AI_WORKSITE_HANDOFF.md` - generated current snapshot and history.
2. `CLAUDE_HANDOFF.md` - existing project handoff, if present.
3. `product/HANDOFF.md` or other `*HANDOFF*.md` files - external or product-specific handoffs.

Do not overwrite large existing handoff documents unless the user asks. Update `AI_WORKSITE_HANDOFF.md` by default.

## Load Workflow

When starting or resuming work:

1. Locate the repo root with `git rev-parse --show-toplevel` when available.
2. Read `AI_WORKSITE_HANDOFF.md` if it exists.
3. Read `CLAUDE_HANDOFF.md` and relevant `*HANDOFF*.md` files mentioned by the user.
4. Run a quick state inspection:
   - `git status --short`
   - current branch and last commit
   - relevant service ports or health endpoints if the handoff mentions running services
   - current task-specific docs/tests only as needed
5. Reconcile handoff claims with live state before acting. If a handoff fact is stale, say it is stale and update the new snapshot after verification.

## Save Workflow

Before stopping, switching agents, handing off, or after any meaningful milestone:

1. Summarize what changed in plain terms.
2. Record exact files changed or created.
3. Record commands/tests run and their results.
4. Record service state: ports, URLs, PIDs when relevant.
5. Record decisions and boundaries, especially frozen files or things not to touch.
6. Record blockers and next steps in execution order.
7. Refresh the handoff using the helper script:

```powershell
python skills\worksite-handoff\scripts\update_handoff.py `
  --root . `
  --objective "current concrete objective" `
  --summary "short status summary" `
  --verification "command => result" `
  --decision "important decision or boundary" `
  --next "next action"
```

Use repeated flags for multiple entries. If Python is unavailable, manually edit `AI_WORKSITE_HANDOFF.md` using the same section names produced by the script.

## Snapshot Contract

Each snapshot must include:

- `Objective`
- `Current Status`
- `Changed Files`
- `Validation`
- `Services`
- `Decisions And Boundaries`
- `Blockers`
- `Next Steps`
- `Agent Notes`

Keep entries factual. Avoid optimism, vague claims, or undocumented assumptions. State whether facts are verified in the current run or inherited from a previous handoff.

## Multi-Agent Rules

When splitting work across agents:

1. Give every subagent the path to this skill and the current handoff file.
2. Assign one bounded responsibility per subagent.
3. Require each subagent to return:
   - files touched
   - commands run
   - verification result
   - remaining risk or blocker
4. Merge their results into one `AI_WORKSITE_HANDOFF.md` snapshot before finalizing.

## Project Safety Rules

- Never revert user changes just to make the handoff cleaner.
- Do not edit frozen files listed in the handoff unless the user explicitly permits it.
- Do not present stale handoff claims as current facts.
- Prefer exact paths, command outputs, URLs, PIDs, and test counts.
- If the repo has a canonical handoff file, keep `AI_WORKSITE_HANDOFF.md` concise and point to that canonical file instead of duplicating it.

## References

- Read `references/install.md` when installing this skill into Codex or Claude skill directories.
- Read `references/schema.md` when manually editing the handoff or adapting it for another repo.
