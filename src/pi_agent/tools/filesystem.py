"""Filesystem tools: read, write, edit, list. All paths go through the sandbox."""

from __future__ import annotations

from typing import Any

from pi_agent.sandbox import Sandbox
from pi_agent.tools.base import Tool

MAX_READ_CHARS = 50_000


def _read_file(args: dict[str, Any], sb: Sandbox) -> str:
    path = sb.resolve(args["path"])
    if not path.is_file():
        return f"Error: '{args['path']}' is not a file."
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > MAX_READ_CHARS:
        text = text[:MAX_READ_CHARS] + "\n... [truncated]"
    # Number lines so the model can refer to them precisely.
    lines = text.splitlines()
    return "\n".join(f"{i + 1:>5}\t{line}" for i, line in enumerate(lines))


def _write_file(args: dict[str, Any], sb: Sandbox) -> str:
    path = sb.resolve(args["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    content = args["content"]
    path.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} chars to {sb.relpath(path)}."


def _edit_file(args: dict[str, Any], sb: Sandbox) -> str:
    path = sb.resolve(args["path"])
    if not path.is_file():
        return f"Error: '{args['path']}' is not a file."
    text = path.read_text(encoding="utf-8")
    old, new = args["old_string"], args["new_string"]
    count = text.count(old)
    if count == 0:
        return "Error: old_string not found. Read the file and copy an exact span."
    if count > 1:
        return (
            f"Error: old_string is not unique ({count} matches). "
            "Include more surrounding context to make it unique."
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return f"Edited {sb.relpath(path)}."


def _list_dir(args: dict[str, Any], sb: Sandbox) -> str:
    path = sb.resolve(args.get("path", "."))
    if not path.is_dir():
        return f"Error: '{args.get('path', '.')}' is not a directory."
    entries = sorted(
        p.name + ("/" if p.is_dir() else "") for p in path.iterdir()
    )
    return "\n".join(entries) if entries else "(empty)"


def filesystem_tools() -> list[Tool]:
    return [
        Tool(
            name="read_file",
            description="Read a text file. Returns the content with line numbers.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to the working directory."}
                },
                "required": ["path"],
            },
            handler=_read_file,
        ),
        Tool(
            name="write_file",
            description="Create or overwrite a file with the given content.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            handler=_write_file,
            mutating=True,
        ),
        Tool(
            name="edit_file",
            description=(
                "Replace an exact, unique substring in a file. old_string must "
                "match exactly once."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                },
                "required": ["path", "old_string", "new_string"],
            },
            handler=_edit_file,
            mutating=True,
        ),
        Tool(
            name="list_dir",
            description="List entries in a directory (defaults to the working directory).",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
            handler=_list_dir,
        ),
    ]
