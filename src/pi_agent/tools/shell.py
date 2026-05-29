"""Shell tool: run a bash command inside the sandbox working directory."""

from __future__ import annotations

import subprocess
from typing import Any

from pi_agent.sandbox import Sandbox
from pi_agent.tools.base import Tool

TIMEOUT_SECONDS = 60
MAX_OUTPUT_CHARS = 20_000


def _run_bash(args: dict[str, Any], sb: Sandbox) -> str:
    command = args["command"]
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(sb.root),          # confine execution to the working dir
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {TIMEOUT_SECONDS}s."

    out = (result.stdout or "") + (result.stderr or "")
    if len(out) > MAX_OUTPUT_CHARS:
        out = out[:MAX_OUTPUT_CHARS] + "\n... [truncated]"
    return f"(exit {result.returncode})\n{out}".strip()


def shell_tools() -> list[Tool]:
    return [
        Tool(
            name="run_bash",
            description=(
                "Run a bash command in the working directory and return its "
                "combined stdout/stderr and exit code."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The bash command to run."}
                },
                "required": ["command"],
            },
            handler=_run_bash,
            mutating=True,
        )
    ]
