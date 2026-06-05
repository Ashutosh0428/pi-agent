"""Tests for safe project-ZIP extraction (zip-slip, bad zip)."""

from __future__ import annotations

import io
import zipfile

from pi_agent.sandbox import Sandbox
from pi_agent.upload import extract_zip_into_sandbox


def _zip(members: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, content in members.items():
            z.writestr(name, content)
    return buf.getvalue()


class TestExtractZip:
    def test_extracts_safe_files(self, tmp_path):
        data = _zip({"proj/main.py": "print(1)", "proj/README.md": "# hi"})
        res = extract_zip_into_sandbox(data, Sandbox(tmp_path))
        assert sorted(res.extracted) == ["proj/README.md", "proj/main.py"]
        assert (tmp_path / "proj" / "main.py").read_text() == "print(1)"

    def test_blocks_zip_slip(self, tmp_path):
        data = _zip({"../evil.txt": "pwned", "ok.txt": "fine"})
        res = extract_zip_into_sandbox(data, Sandbox(tmp_path))
        assert "ok.txt" in res.extracted
        assert not (tmp_path.parent / "evil.txt").exists()  # escape blocked
        assert any("evil" in s for s in res.skipped)

    def test_skips_junk_dirs(self, tmp_path):
        data = _zip({"__MACOSX/x": "junk", "real.py": "x = 1"})
        res = extract_zip_into_sandbox(data, Sandbox(tmp_path))
        assert "real.py" in res.extracted
        assert not (tmp_path / "__MACOSX").exists()

    def test_bad_zip_reports_error(self, tmp_path):
        res = extract_zip_into_sandbox(b"not a zip", Sandbox(tmp_path))
        assert res.error and not res.extracted
