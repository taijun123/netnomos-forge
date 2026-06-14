# Merge conflict preservation note

Date: 2026-06-14

Current goal: keep the current local UI files unchanged while preserving the conflicting incoming versions under new names. The backup files are outside `web/src`, so they will not be compiled by the frontend build.

## Conflicted files

- `web/src/App.tsx`
- `web/src/components/TopNav.tsx`

## Preserved copies

Local current copies:

- `merge-conflicts/2026-06-14-5236303d/local-current/App.local.tsx`
- `merge-conflicts/2026-06-14-5236303d/local-current/TopNav.local.tsx`

Incoming conflict copies renamed:

- `merge-conflicts/2026-06-14-5236303d/incoming-renamed/App.conflict-5236303d.tsx`
- `merge-conflicts/2026-06-14-5236303d/incoming-renamed/TopNav.conflict-5236303d.tsx`

Earlier exact Git-stage backup copies also exist:

- `conflict-backups/2026-06-14-merge-5236303d/ours/web/src/App.tsx`
- `conflict-backups/2026-06-14-merge-5236303d/ours/web/src/components/TopNav.tsx`
- `conflict-backups/2026-06-14-merge-5236303d/theirs/web/src/App.tsx`
- `conflict-backups/2026-06-14-merge-5236303d/theirs/web/src/components/TopNav.tsx`

## What each side contains

`App.tsx`

- Local side keeps the real `OfficeDemoPage` and wraps the app with `DemoProvider`.
- Incoming side adds `LogDemoPage`, `LogPanel`, and a `log-demo` route, while using an `OfficePlaceholder`.

`TopNav.tsx`

- Local side uses `DemoStartMenu` with `useDemo()` so the top navigation can start demos.
- Incoming side adds the `log-demo` route and replaces the demo menu with a simple start-demo link.

## Handling rule

Do not put renamed `.tsx` conflict copies under `web/src`. If a later merge needs the incoming behavior, compare the renamed files manually and port only the needed pieces into the active files.

This note does not mark the Git merge as resolved. It only records the preserved copies and the intended strategy.
