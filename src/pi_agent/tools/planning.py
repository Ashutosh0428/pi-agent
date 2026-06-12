"""Planning tool: lets the model declare and update a task plan.

This is the mechanism behind the live "todo" panel. The model calls
``update_plan`` with a list of steps; the agent surfaces those steps to the UI
as a ``plan`` event, and the front-end renders them as a checklist. The tool
itself only records state (non-mutating) — it never touches the filesystem.
"""

from __future__ import annotations

from typing import Any

from pi_agent.sandbox import Sandbox
from pi_agent.tools.base import Tool

_VALID_STATUS = {"pending", "in_progress", "done"}


def _update_plan(args: dict[str, Any], sandbox: Sandbox) -> str:  # noqa: ARG001
    steps = args.get("steps", [])
    if not isinstance(steps, list) or not steps:
        return "Error: 'steps' must be a non-empty list."
    done = sum(1 for s in steps if isinstance(s, dict) and s.get("status") == "done")
    in_progress = sum(1 for s in steps if isinstance(s, dict) and s.get("status") == "in_progress")
    return f"Plan updated: {len(steps)} steps ({done} done, {in_progress} in progress)."


def planning_tools() -> list[Tool]:
    """The planning/todo tool. Always available."""
    return [
        Tool(
            name="update_plan",
            description=(
                "Declare or update your step-by-step plan for the current task. "
                "Call this at the start of any multi-step task, and again whenever "
                "a step's status changes. The user sees the plan as a live checklist."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "step": {
                                    "type": "string",
                                    "description": "Short step description.",
                                },
                                "status": {
                                    "type": "string",
                                    "enum": sorted(_VALID_STATUS),
                                    "description": "pending | in_progress | done",
                                },
                            },
                            "required": ["step", "status"],
                        },
                    }
                },
                "required": ["steps"],
            },
            handler=_update_plan,
            mutating=False,
        )
    ]
