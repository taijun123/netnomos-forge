# AI Worksite Handoff

<!-- Maintained by skills/worksite-handoff/scripts/update_handoff.py. -->

- Updated: 2026-06-13 20:43:06 +0800
- Repo: E:\yanchh\model_control\netnomos-forge
- Branch: main
- Last Commit: 80ab1e0 Initial NetNomos Forge implementation
## Objective

Keep NetNomos Forge resumable across Codex, Claude, and subagents while office/finance/network demo integration continues.

## Current Status

Created a reusable worksite-handoff skill for multi-model operation. The skill is committed-ready in the repo, installed for Codex globally, installed for Claude at project scope, and generated AI_WORKSITE_HANDOFF.md as the concise current worksite snapshot.

## Changed Files

```text
M CLAUDE_HANDOFF.md
 M server/app.py
 M server/pipeline.py
 M server/store.py
 M web/package-lock.json
 M web/package.json
 M web/src/App.tsx
 M web/src/components/TopNav.tsx
 M web/src/lib/apiClient.ts
 M web/src/types/api.ts
?? .claude/
?? AI_WORKSITE_HANDOFF.md
?? docs/OFFICE_DEMO_OPERATION_GUIDE.md
?? docs/OFFICE_DEMO_TECHNICAL_REPORT.md
?? docs/OFFICE_DEMO_USE_CASES.md
?? forge/scenarios/office_demo/
?? skills/
?? tests/test_office_demo.py
?? web/public/
?? web/src/office/
?? web/src/pages/OfficeDemoPage.tsx
```

## Validation

- python quick_validate.py skills\worksite-handoff => Skill is valid
- python -m py_compile skills\worksite-handoff\scripts\update_handoff.py => passed
- python quick_validate.py C:\Users\A\.codex\skills\worksite-handoff => Skill is valid
- python quick_validate.py .claude\skills\worksite-handoff => Skill is valid

## Services

- 127.0.0.1:8000 listening
- 127.0.0.1:5173 listening

## Decisions And Boundaries

- forge/contracts.py remains frozen unless the user explicitly permits edits.
- AI_WORKSITE_HANDOFF.md is the concise current snapshot; CLAUDE_HANDOFF.md remains extended project history.
- The skill is installed at C:\Users\A\.codex\skills\worksite-handoff and E:\yanchh\model_control\netnomos-forge\.claude\skills\worksite-handoff.

## Blockers

- None recorded.

## Next Steps

- In a new Codex or Claude session, prompt: Use $worksite-handoff to load AI_WORKSITE_HANDOFF.md and continue.
- Before stopping or switching models, rerun update_handoff.py with the latest objective, validation, blockers, and next actions.

## Agent Notes

- Main agent created, validated, installed, and documented worksite-handoff.
