# Handoff Schema

Use this structure for `AI_WORKSITE_HANDOFF.md`.

## Current Snapshot

- `Updated`: local timestamp and timezone if known.
- `Repo`: absolute repo path.
- `Branch`: current branch or `unknown`.
- `Last Commit`: short hash and subject or `unknown`.
- `Objective`: current task in one concrete sentence.
- `Current Status`: what is done now, not what is intended.

## Changed Files

List modified, added, deleted, and untracked files. Keep generated caches out unless they matter.

## Validation

Use `command => result`. Include failures and skipped checks.

## Services

List service name, URL, port, PID, and health result when relevant.

## Decisions And Boundaries

Examples:

- `forge/contracts.py` is frozen.
- Do not kill unrelated Node processes.
- Office demo uses browser-side pcap parsing; backend pcap parser is not implemented.

## Blockers

List only real blockers. Do not use this section for ordinary next steps.

## Next Steps

Write in execution order. Each item should be actionable by a fresh agent.

## Agent Notes

Record subagent IDs, names, ownership, outputs, and reliability notes.
