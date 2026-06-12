"""Memory tool: persistent project facts across sessions.

The model calls ``remember`` to save one durable fact (a decision, a
convention, a user preference) to ``.pi/memory.md`` under the workspace root.
On the next session the CLI inlines that file back into the system prompt
(see :func:`load_memory`), so the agent picks up where it left off.

Plain markdown on purpose: the user can read, edit, or delete the agent's
memory with any editor — transparency over magic.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from pi_agent.sandbox import Sandbox
from pi_agent.tools.base import Tool

MEMORY_RELPATH = ".pi/memory.md"
MEMORY_RECALL_CAP = 4096  # max bytes of memory inlined into the prompt
MEMORY_FACT_CAP = 500  # max characters per saved fact


def _remember(args: dict[str, Any], sandbox: Sandbox) -> str:
    fact = str(args.get("fact", "")).strip()
    if not fact:
        return "Error: 'fact' must be a non-empty string."
    if len(fact) > MEMORY_FACT_CAP:
        return f"Error: keep each fact under {MEMORY_FACT_CAP} characters."
    path = sandbox.resolve(MEMORY_RELPATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"- [{date.today().isoformat()}] {fact}\n")
    return f"Remembered: {fact}"


def load_memory(root: Path | str) -> str:
    """Workspace memory for prompt recall, capped to the trailing bytes.

    Returns the *last* ``MEMORY_RECALL_CAP`` bytes (oldest facts age out
    first), snapped to a line boundary; "" when no memory exists.
    """
    path = Path(root) / MEMORY_RELPATH
    if not path.is_file():
        return ""
    data = path.read_text(encoding="utf-8", errors="replace")
    if len(data) > MEMORY_RECALL_CAP:
        data = data[-MEMORY_RECALL_CAP:]
        newline = data.find("\n")
        if newline != -1:
            data = data[newline + 1 :]
    return data.strip()


def memory_tools() -> list[Tool]:
    """The persistent-memory tool (CLI/local sessions)."""
    return [
        Tool(
            name="remember",
            description=(
                "Save one durable project fact to memory (.pi/memory.md) so future "
                "sessions start with it: a convention ('tests use pytest fixtures'), "
                "a decision ('API errors return RFC7807'), or a user preference. "
                "Do NOT save transcripts, file contents, or anything transient."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "fact": {
                        "type": "string",
                        "description": f"The fact to remember (≤{MEMORY_FACT_CAP} chars).",
                    }
                },
                "required": ["fact"],
            },
            handler=_remember,
            mutating=True,
        )
    ]
