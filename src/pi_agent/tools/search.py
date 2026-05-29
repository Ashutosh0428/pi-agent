"""Search tool: regex grep across files in the working directory."""

from __future__ import annotations

import re
from typing import Any

from pi_agent.sandbox import Sandbox
from pi_agent.tools.base import Tool

MAX_MATCHES = 100
SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache"}


def _grep(args: dict[str, Any], sb: Sandbox) -> str:
    pattern = args["pattern"]
    root = sb.resolve(args.get("path", "."))
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        return f"Error: invalid regex: {exc}"

    matches: list[str] = []
    for file in sorted(root.rglob("*")):
        if not file.is_file():
            continue
        if any(part in SKIP_DIRS for part in file.parts):
            continue
        try:
            text = file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # skip binary / unreadable files
        for lineno, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                matches.append(f"{sb.relpath(file)}:{lineno}: {line.strip()}")
                if len(matches) >= MAX_MATCHES:
                    matches.append("... [more matches truncated]")
                    return "\n".join(matches)
    return "\n".join(matches) if matches else "No matches."


def search_tools() -> list[Tool]:
    return [
        Tool(
            name="grep",
            description="Search files for a regex pattern. Returns file:line: matches.",
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Python regex."},
                    "path": {"type": "string", "description": "Directory to search (default: working dir)."},
                },
                "required": ["pattern"],
            },
            handler=_grep,
        )
    ]
