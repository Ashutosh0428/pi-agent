"""Restricted command tool — safe to expose on a public app.

Unlike ``run_bash`` (raw shell, local use only), ``run_command``:

* runs with **no shell** (``shell=False``) — so pipes, redirects, ``&&``,
  ``$(...)`` and other injection vectors are inert (passed as literal args);
* allows only a small **allowlist** of read-only inspection commands;
* **rejects absolute paths and parent-directory traversal**, so it can't reach
  anything outside the per-session sandbox (no ``cat /etc/passwd``);
* runs with a minimal env, a hard timeout, and capped output.

It executes processes on the host, but confined to read-only inspection inside
the sandbox directory — acceptable for an untrusted/public context where
``run_bash`` would be a remote-code-execution hole.

``find`` is deliberately **not** allowed: its ``-exec``/``-delete`` primaries
turn it into a launcher for arbitrary programs (e.g. ``find . -exec sh -c …``),
which would bypass this whole allowlist. File discovery is already covered by the
dedicated ``grep`` tool and ``list_dir``/``ls``. As defense in depth we also
reject the dangerous argument flags outright, so re-adding such a program later
cannot silently reopen the hole.
"""

from __future__ import annotations

import shlex
from typing import Any

from pi_agent.sandbox import Sandbox
from pi_agent.tools._subprocess import SAFE_ENV, is_unsafe_path, run_confined
from pi_agent.tools.base import Tool

ALLOWED = {"ls", "cat", "head", "tail", "wc", "grep"}
# Argument flags that let an otherwise read-only program execute, write, or
# delete. Rejected for every command, regardless of the program in ALLOWED.
_DANGEROUS_FLAGS = {
    "-exec",
    "-execdir",
    "-ok",
    "-okdir",  # find: run arbitrary programs
    "-delete",  # find: delete files
    "-fprint",
    "-fprintf",
    "-fls",  # find: write to arbitrary files
}
MAX_OUTPUT = 4000
TIMEOUT_SECONDS = 10


def _run_command(args: dict[str, Any], sb: Sandbox) -> str:
    raw = (args.get("command") or "").strip()
    if not raw:
        return "Error: empty command."
    try:
        tokens = shlex.split(raw)
    except ValueError as exc:
        return f"Error: could not parse command: {exc}"
    if not tokens:
        return "Error: empty command."

    cmd = tokens[0]
    if cmd not in ALLOWED:
        return f"Error: '{cmd}' is not allowed. Allowed: {', '.join(sorted(ALLOWED))}."

    for tok in tokens[1:]:
        if tok in _DANGEROUS_FLAGS:
            return f"Error: '{tok}' is blocked (it can execute, write, or delete)."
        if not tok.startswith("-") and is_unsafe_path(tok):
            return (
                f"Error: '{tok}' points outside the sandbox "
                "(absolute, home, and parent paths are blocked)."
            )

    result = run_confined(tokens, sb, timeout=TIMEOUT_SECONDS, max_output=MAX_OUTPUT, env=SAFE_ENV)
    return f"$ {raw}\n{result}"


def safe_command_tools() -> list[Tool]:
    """The restricted, read-only command tool (for public/untrusted contexts)."""
    return [
        Tool(
            name="run_command",
            description=(
                "Run ONE read-only inspection command in the workspace. "
                f"Allowed programs: {', '.join(sorted(ALLOWED))}. No shell features "
                "(no pipes, redirects, &&), no network; absolute and parent paths "
                "are blocked. Examples: 'grep -rn TODO .', 'wc -l app.py', 'ls'."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": 'A single command, e.g. "grep -rn def app.py".',
                    }
                },
                "required": ["command"],
            },
            handler=_run_command,
            mutating=False,
        )
    ]
