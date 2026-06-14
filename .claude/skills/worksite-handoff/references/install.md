# Installing Worksite Handoff

This skill is repository-local at `skills/worksite-handoff`. To make it automatically discoverable by a tool, copy the whole folder to that tool's skill directory.

## Codex

Recommended per-user install:

```powershell
$src = "E:\yanchh\model_control\netnomos-forge\skills\worksite-handoff"
$dst = "$env:USERPROFILE\.codex\skills\worksite-handoff"
New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null
Copy-Item -Recurse -Force $src $dst
```

Then start a new Codex session and invoke:

```text
Use $worksite-handoff to load the project state, continue the current task, and update the handoff before stopping.
```

## Claude

Recommended project install:

```powershell
$src = "E:\yanchh\model_control\netnomos-forge\skills\worksite-handoff"
$dst = "E:\yanchh\model_control\netnomos-forge\.claude\skills\worksite-handoff"
New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null
Copy-Item -Recurse -Force $src $dst
```

Recommended per-user install, if Claude is configured to load user skills:

```powershell
$src = "E:\yanchh\model_control\netnomos-forge\skills\worksite-handoff"
$dst = "$env:USERPROFILE\.claude\skills\worksite-handoff"
New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null
Copy-Item -Recurse -Force $src $dst
```

Then start Claude in the repo and ask:

```text
Use $worksite-handoff. Read AI_WORKSITE_HANDOFF.md and CLAUDE_HANDOFF.md, inspect live repo state, then continue the task.
```

## Updating Installed Copies

After editing the repo-local skill, repeat the copy command for each installed location. Restart the AI session if the host loads skills only at session start.
