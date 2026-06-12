"""apply_patch tests — multi-file success, atomicity, validation (no network)."""

from __future__ import annotations

from pi_agent.sandbox import Sandbox
from pi_agent.tools.patch import patch_tools
from pi_agent.tools.registry import build_default_tools

APPLY = patch_tools()[0]


def _setup(tmp_path):
    (tmp_path / "a.py").write_text("def old_name():\n    return 1\n")
    (tmp_path / "b.py").write_text("from a import old_name\nprint(old_name())\n")
    return Sandbox(tmp_path)


def test_multi_file_patch_applies_all(tmp_path):
    sb = _setup(tmp_path)
    out = APPLY.handler(
        {
            "edits": [
                {"path": "a.py", "old_string": "def old_name", "new_string": "def new_name"},
                {
                    "path": "b.py",
                    "old_string": "from a import old_name",
                    "new_string": "from a import new_name",
                },
            ]
        },
        sb,
    )
    assert "Applied 2 edit(s) across 2 file(s)" in out
    assert "def new_name" in (tmp_path / "a.py").read_text()
    assert "import new_name" in (tmp_path / "b.py").read_text()


def test_failing_hunk_leaves_everything_untouched(tmp_path):
    sb = _setup(tmp_path)
    before_a = (tmp_path / "a.py").read_text()
    out = APPLY.handler(
        {
            "edits": [
                {"path": "a.py", "old_string": "def old_name", "new_string": "def new_name"},
                {"path": "b.py", "old_string": "NOT-IN-FILE", "new_string": "x"},
            ]
        },
        sb,
    )
    assert out.startswith("Error: edit #2")
    assert (tmp_path / "a.py").read_text() == before_a  # first hunk NOT applied


def test_ambiguous_old_string_rejected(tmp_path):
    sb = Sandbox(tmp_path)
    (tmp_path / "c.py").write_text("x = 1\nx = 1\n")
    out = APPLY.handler(
        {"edits": [{"path": "c.py", "old_string": "x = 1", "new_string": "x = 2"}]}, sb
    )
    assert "not unique" in out
    assert (tmp_path / "c.py").read_text() == "x = 1\nx = 1\n"


def test_two_edits_same_file_sequential(tmp_path):
    sb = _setup(tmp_path)
    out = APPLY.handler(
        {
            "edits": [
                {"path": "a.py", "old_string": "def old_name", "new_string": "def renamed"},
                {"path": "a.py", "old_string": "return 1", "new_string": "return 2"},
            ]
        },
        sb,
    )
    assert "Applied 2 edit(s) across 1 file(s)" in out
    text = (tmp_path / "a.py").read_text()
    assert "def renamed" in text and "return 2" in text


def test_sandbox_escape_rejected_via_registry(tmp_path):
    sb = Sandbox(tmp_path)
    reg = build_default_tools()
    out = reg.run(
        "apply_patch",
        {"edits": [{"path": "../evil.py", "old_string": "a", "new_string": "b"}]},
        sb,
    )
    assert "Error" in out and "escapes" in out


def test_validation_errors(tmp_path):
    sb = Sandbox(tmp_path)
    assert APPLY.handler({"edits": []}, sb).startswith("Error")
    assert APPLY.handler(
        {"edits": [{"path": "", "old_string": "x", "new_string": "y"}]}, sb
    ).startswith("Error")


def test_registered_by_default():
    assert "apply_patch" in build_default_tools().names()
