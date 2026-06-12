"""Filesystem sandbox.

Every file path a tool touches is resolved through :class:`Sandbox`, which
guarantees the path stays inside the agent's working directory. This is the
single choke-point that prevents an LLM from reading or writing arbitrary files
like ``/etc/passwd`` via ``../`` traversal.
"""

from __future__ import annotations

from pathlib import Path


class SandboxError(Exception):
    """Raised when a path would escape the sandbox root."""


class Sandbox:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def resolve(self, relative: str) -> Path:
        """Resolve a (possibly relative) path and assert it stays in root.

        Raises :class:`SandboxError` if the resolved path is outside the root.
        """
        candidate = (self.root / relative).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise SandboxError(f"Path '{relative}' escapes the sandbox root '{self.root}'.")
        return candidate

    def relpath(self, path: Path) -> str:
        """Return a path relative to the root for display."""
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)
