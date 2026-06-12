"""apply_patch: multiple exact-string edits across files in one atomic call.

Same matching rules as ``edit_file`` (exact, unique ``old_string``), but every
hunk is validated up front and the writes happen only if *all* hunks pass —
a failing hunk leaves every file untouched. That makes multi-file refactors
(rename a symbol + its imports + its tests) a single recoverable step instead
of a half-applied mess.
"""

from __future__ import annotations

from typing import Any

from pi_agent.sandbox import Sandbox
from pi_agent.tools.base import Tool

MAX_EDITS = 20


def _apply_patch(args: dict[str, Any], sb: Sandbox) -> str:
    edits = args.get("edits")
    if not isinstance(edits, list) or not edits:
        return "Error: 'edits' must be a non-empty list."
    if len(edits) > MAX_EDITS:
        return f"Error: at most {MAX_EDITS} edits per call."

    # Pass 1 — validate every hunk against the current file contents.
    staged: list[tuple[Any, str]] = []  # (resolved path, new file text)
    texts: dict[Any, str] = {}
    for i, edit in enumerate(edits, start=1):
        if not isinstance(edit, dict):
            return f"Error: edit #{i} must be an object."
        rel = edit.get("path", "")
        old, new = edit.get("old_string", ""), edit.get("new_string", "")
        if not rel or not old:
            return f"Error: edit #{i} needs 'path' and a non-empty 'old_string'."
        path = sb.resolve(rel)  # raises SandboxError on escape -> caught by registry
        if path not in texts:
            if not path.is_file():
                return f"Error: edit #{i}: '{rel}' is not a file."
            texts[path] = path.read_text(encoding="utf-8")
        count = texts[path].count(old)
        if count == 0:
            return f"Error: edit #{i}: old_string not found in '{rel}' (nothing was applied)."
        if count > 1:
            return (
                f"Error: edit #{i}: old_string is not unique in '{rel}' "
                f"({count} matches; nothing was applied)."
            )
        texts[path] = texts[path].replace(old, new, 1)

    staged = [(path, text) for path, text in texts.items()]

    # Pass 2 — all hunks valid: write everything.
    for path, text in staged:
        path.write_text(text, encoding="utf-8")
    return f"Applied {len(edits)} edit(s) across {len(staged)} file(s)."


def patch_tools() -> list[Tool]:
    """The atomic multi-file edit tool."""
    return [
        Tool(
            name="apply_patch",
            description=(
                "Apply several exact-string edits across one or more files in a "
                "single atomic step: every edit is validated first, and if any "
                "old_string is missing or ambiguous, no file is changed. Use for "
                "multi-file changes (rename + imports + tests); use edit_file for "
                "a single small edit."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "edits": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"},
                                "old_string": {
                                    "type": "string",
                                    "description": "Exact, unique span in the file.",
                                },
                                "new_string": {"type": "string"},
                            },
                            "required": ["path", "old_string", "new_string"],
                        },
                    }
                },
                "required": ["edits"],
            },
            handler=_apply_patch,
            mutating=True,
        )
    ]
