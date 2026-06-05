"""The ``delegate`` tool — hand a focused subtask to a sub-agent.

The schema lives here so the model can see it, but the *execution* is handled by
the :class:`~pi_agent.agent.Agent` itself (it owns the provider and config, which
a plain tool handler does not). The Agent intercepts ``delegate`` calls, runs a
fresh sub-agent sequentially on the same workspace, and returns its result. The
sub-agent's toolset excludes ``delegate``, so recursion is capped at one level.
"""

from __future__ import annotations

from typing import Any

from pi_agent.sandbox import Sandbox
from pi_agent.tools.base import Tool


def _delegate_stub(args: dict[str, Any], sandbox: Sandbox) -> str:  # noqa: ARG001
    # Never reached: the Agent intercepts "delegate" before dispatching tools.
    return "Error: delegate must be handled by the agent."


def subagent_tools() -> list[Tool]:
    return [
        Tool(
            name="delegate",
            description=(
                "Delegate a focused subtask to a sub-agent that works on the same "
                "workspace and reports back a concise result. Use for a self-contained "
                "piece of a larger job (e.g. 'explore the repo and summarise its "
                "structure', 'review auth.py for bugs'). The sub-agent runs to "
                "completion before you continue. It cannot delegate further."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "A clear, self-contained instruction for the sub-agent.",
                    }
                },
                "required": ["task"],
            },
            handler=_delegate_stub,
            mutating=False,
        )
    ]
