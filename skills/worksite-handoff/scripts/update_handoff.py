#!/usr/bin/env python3
"""Update a portable AI worksite handoff markdown file."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
import socket
import subprocess
from typing import Iterable


def run(cmd: list[str], cwd: pathlib.Path) -> str:
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:  # pragma: no cover - environment dependent
        return f"unavailable ({exc})"
    output = (completed.stdout or completed.stderr or "").strip()
    return output if output else f"exit {completed.returncode}"


def git_value(args: list[str], root: pathlib.Path) -> str:
    return run(["git", *args], root)


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def bullet(items: Iterable[str], fallback: str = "None recorded.") -> str:
    clean = [item.strip() for item in items if item and item.strip()]
    if not clean:
        return f"- {fallback}"
    return "\n".join(f"- {item}" for item in clean)


def section(title: str, body: str) -> str:
    return f"## {title}\n\n{body.strip()}\n"


def build_snapshot(args: argparse.Namespace, root: pathlib.Path) -> str:
    now = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    branch = git_value(["branch", "--show-current"], root)
    last_commit = git_value(["log", "-1", "--pretty=%h %s"], root)
    status = git_value(["status", "--short"], root)
    changed_files = status if status and not status.startswith("unavailable") else "None detected."

    detected_services = []
    for port in args.detect_port:
        state = "listening" if port_open(port) else "not listening"
        detected_services.append(f"127.0.0.1:{port} {state}")

    header = "\n".join(
        [
            "# AI Worksite Handoff",
            "",
            "<!-- Maintained by skills/worksite-handoff/scripts/update_handoff.py. -->",
            "",
            f"- Updated: {now}",
            f"- Repo: {root}",
            f"- Branch: {branch or 'unknown'}",
            f"- Last Commit: {last_commit or 'unknown'}",
        ]
    )

    parts = [
        header,
        section("Objective", args.objective or "Not specified."),
        section("Current Status", args.summary or "Not specified."),
        section("Changed Files", f"```text\n{changed_files}\n```"),
        section("Validation", bullet(args.verification)),
        section("Services", bullet([*detected_services, *args.service])),
        section("Decisions And Boundaries", bullet(args.decision)),
        section("Blockers", bullet(args.blocker)),
        section("Next Steps", bullet(args.next)),
        section("Agent Notes", bullet(args.agent)),
    ]
    return "\n".join(parts).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root or working directory.")
    parser.add_argument("--handoff", default="AI_WORKSITE_HANDOFF.md", help="Markdown handoff path, relative to root unless absolute.")
    parser.add_argument("--objective", default="", help="Current concrete objective.")
    parser.add_argument("--summary", default="", help="Current status summary.")
    parser.add_argument("--verification", action="append", default=[], help="Validation entry. Repeatable.")
    parser.add_argument("--service", action="append", default=[], help="Service state entry. Repeatable.")
    parser.add_argument("--decision", action="append", default=[], help="Decision or boundary. Repeatable.")
    parser.add_argument("--blocker", action="append", default=[], help="Blocker. Repeatable.")
    parser.add_argument("--next", action="append", default=[], help="Next action. Repeatable.")
    parser.add_argument("--agent", action="append", default=[], help="Agent note. Repeatable.")
    parser.add_argument("--detect-port", type=int, action="append", default=[8000, 5173], help="Port to probe. Repeatable.")
    parser.add_argument("--append-history", action="store_true", help="Append previous snapshot under History.")
    args = parser.parse_args()

    root = pathlib.Path(args.root).resolve()
    handoff = pathlib.Path(args.handoff)
    if not handoff.is_absolute():
        handoff = root / handoff

    snapshot = build_snapshot(args, root)
    if args.append_history and handoff.exists():
        previous = handoff.read_text(encoding="utf-8")
        snapshot = snapshot + "\n## History\n\n" + previous

    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(snapshot, encoding="utf-8", newline="\n")
    print(f"updated {handoff}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
