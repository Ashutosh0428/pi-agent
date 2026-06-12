"""Safe extraction of an uploaded project ZIP into a sandbox.

Treats the archive as untrusted. Guards against:

* **zip-slip** — members like ``../../etc/cron.d/x`` that escape the sandbox.
  Every member is resolved through :class:`Sandbox`; escapes are skipped.
* **symlinks** — never created (they could point outside the sandbox).
* **zip bombs** — total uncompressed size, file count, and per-file size are
  all capped.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field

from pi_agent.sandbox import Sandbox, SandboxError

MAX_FILES = 1000
MAX_TOTAL_BYTES = 20 * 1024 * 1024  # 20 MB uncompressed total
MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MB per file
_SKIP_PREFIXES = ("__MACOSX/", ".git/")


@dataclass
class ExtractResult:
    extracted: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    error: str | None = None


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return (info.external_attr >> 16) & 0o170000 == 0o120000


def extract_zip_into_sandbox(data: bytes, sandbox: Sandbox) -> ExtractResult:
    """Extract a project ZIP into ``sandbox.root``, safely. Never raises."""
    result = ExtractResult()
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        result.error = "Not a valid ZIP file."
        return result

    total = 0
    for info in zf.infolist():
        name = info.filename
        if info.is_dir() or name.endswith("/"):
            continue
        if any(name.startswith(p) or f"/{p}" in name for p in _SKIP_PREFIXES):
            result.skipped.append(name)
            continue
        if _is_symlink(info):
            result.skipped.append(f"{name} (symlink)")
            continue
        if info.file_size > MAX_FILE_BYTES:
            result.skipped.append(f"{name} (too large)")
            continue
        if len(result.extracted) >= MAX_FILES or total + info.file_size > MAX_TOTAL_BYTES:
            result.skipped.append(f"{name} (archive limit reached)")
            continue

        try:
            dest = sandbox.resolve(name)  # rejects absolute paths + ../ escapes
        except SandboxError:
            result.skipped.append(f"{name} (path escapes sandbox)")
            continue

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(info))
        except OSError:
            result.skipped.append(f"{name} (write failed)")
            continue

        total += info.file_size
        result.extracted.append(sandbox.relpath(dest))

    return result
