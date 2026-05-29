"""Tool definition.

A :class:`Tool` bundles everything the system needs about one capability:
its name, a description (shown to the model), a JSON-schema for its arguments,
the function that runs it, and whether it mutates state (so the UI can ask for
confirmation). Adding a new tool later is just creating one more ``Tool``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pi_agent.sandbox import Sandbox

# A handler takes parsed args + the sandbox and returns a string result that is
# fed back to the model as the tool's output.
ToolHandler = Callable[[dict[str, Any], Sandbox], str]


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler
    mutating: bool = False  # True for write/edit/bash -> may require confirmation

    def to_schema(self) -> dict[str, Any]:
        """Return the tool definition in the Anthropic tools format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
