"""Shared primitives for the read-only subprocess tools.

The restricted command tool (:mod:`~pi_agent.tools.safe_exec`) and the git tool
(:mod:`~pi_agent.tools.vcs`) both need the same two things: a check that an
argument can't point outside the sandbox, and a way to run a process with **no
shell**, confined to the sandbox directory, with a timeout and capped output.

Centralising them here keeps the safety behaviour identical across tools — a
hardening change lands in one place, not several.
"""

from __future__ import annotations

import subprocess
from typing import Any

from pi_agent.sandbox import Sandbox

# Minimal environment for the public, restricted runner. Local/trusted tools
# (git, web_fetch) pass ``env=None`` to inherit the real environment instead.
SAFE_ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "LANG": "C.UTF-8"}


def is_unsafe_path(token: str) -> bool:
    """True if a token is an absolute path, home expansion, or parent traversal."""
    if token.startswith(("/", "~")):
        return True
    return ".." in token.split("/")


def run_confined(
    tokens: list[str],
    sb: Sandbox,
    *,
    timeout: int,
    max_output: int,
    env: dict[str, str] | None = SAFE_ENV,
) -> str:
    """Run ``tokens`` with no shell inside the sandbox; return its combined output.

    Never raises: timeouts and OS errors are returned as a string so the model
    can read what went wrong. ``env=None`` inherits the real environment (used by
    local/trusted tools that need the user's PATH, e.g. to find ``git``).
    """
    kwargs: dict[str, Any] = {
        "cwd": str(sb.root),  # confine execution to the working dir
        "shell": False,  # no pipes/redirects/$(...) — args are literal
        "capture_output": True,
        "text": True,
        "timeout": timeout,
    }
    if env is not None:
        kwargs["env"] = env
    try:
        proc = subprocess.run(tokens, **kwargs)
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s."
    except (OSError, ValueError) as exc:
        return f"Error running command: {exc}"

    out = (proc.stdout or "") + (proc.stderr or "")
    if len(out) > max_output:
        out = out[:max_output] + "\n... [truncated]"
    return f"(exit {proc.returncode})\n{out}".rstrip()
