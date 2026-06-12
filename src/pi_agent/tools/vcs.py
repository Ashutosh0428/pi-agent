"""Read-only git tool.

Lets the agent inspect a repository's state — ``status``, ``diff``, ``log``,
``show``, ``branch``, ``ls-files``, ``blame`` — without being able to mutate
history. Only those subcommands are allowed, so ``commit``, ``push``, ``reset``,
``checkout`` and friends are rejected before git ever runs.

Like ``run_bash``, this is a **local/trusted** tool: it inherits the real
environment (to find the ``git`` binary and the user's repo) and runs confined to
the sandbox working directory. It is not exposed on the public web demo.
"""

from __future__ import annotations

import shlex
from typing import Any

from pi_agent.sandbox import Sandbox
from pi_agent.tools._subprocess import is_unsafe_path, run_confined
from pi_agent.tools.base import Tool

# Read-only porcelain/plumbing only. Anything that writes refs, the index, or the
# working tree is intentionally absent.
ALLOWED_SUBCOMMANDS = {
    "status",
    "diff",
    "log",
    "show",
    "branch",
    "ls-files",
    "blame",
    "remote",
}
MAX_OUTPUT = 20_000
TIMEOUT_SECONDS = 20


def _git(args: dict[str, Any], sb: Sandbox) -> str:
    subcommand = (args.get("subcommand") or "").strip()
    if subcommand not in ALLOWED_SUBCOMMANDS:
        allowed = ", ".join(sorted(ALLOWED_SUBCOMMANDS))
        return f"Error: 'git {subcommand}' is not allowed (read-only). Allowed: {allowed}."

    extra = args.get("args") or ""
    try:
        extra_tokens = shlex.split(extra)
    except ValueError as exc:
        return f"Error: could not parse args: {exc}"

    for tok in extra_tokens:
        if not tok.startswith("-") and is_unsafe_path(tok):
            return f"Error: '{tok}' points outside the sandbox (absolute/parent paths blocked)."

    # ``-c`` could set arbitrary config (e.g. a pager that runs a command); forbid
    # any extra options that smuggle in a subcommand-like escape.
    if "-c" in extra_tokens or "--exec-path" in extra_tokens:
        return "Error: passing git -c/--exec-path is not allowed."

    # ``--no-pager`` keeps git from invoking an interactive pager on long output.
    tokens = ["git", "--no-pager", subcommand, *extra_tokens]
    return run_confined(tokens, sb, timeout=TIMEOUT_SECONDS, max_output=MAX_OUTPUT, env=None)


def git_tools() -> list[Tool]:
    """The read-only git inspection tool (local/trusted contexts only)."""
    return [
        Tool(
            name="git",
            description=(
                "Inspect a git repository (read-only). subcommand is one of: "
                f"{', '.join(sorted(ALLOWED_SUBCOMMANDS))}. Pass extra flags in 'args' "
                "(e.g. subcommand='log', args='--oneline -10'; subcommand='diff', "
                "args='HEAD~1'). Cannot commit, push, or change anything."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "subcommand": {
                        "type": "string",
                        "enum": sorted(ALLOWED_SUBCOMMANDS),
                        "description": "The read-only git subcommand to run.",
                    },
                    "args": {
                        "type": "string",
                        "description": "Optional extra arguments, e.g. '--oneline -10'.",
                    },
                },
                "required": ["subcommand"],
            },
            handler=_git,
            mutating=False,
        )
    ]
