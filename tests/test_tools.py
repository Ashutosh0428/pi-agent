"""Tests for tools and the sandbox safety boundary."""

from __future__ import annotations

import pytest

from pi_agent.sandbox import Sandbox, SandboxError
from pi_agent.tools.registry import build_default_tools


@pytest.fixture()
def sandbox(tmp_path):
    return Sandbox(tmp_path)


@pytest.fixture()
def registry():
    return build_default_tools(enable_shell=True)


class TestSandbox:
    def test_resolves_inside_root(self, sandbox):
        p = sandbox.resolve("sub/file.txt")
        assert str(p).startswith(str(sandbox.root))

    def test_blocks_traversal(self, sandbox):
        with pytest.raises(SandboxError):
            sandbox.resolve("../../etc/passwd")

    def test_blocks_absolute_escape(self, sandbox):
        with pytest.raises(SandboxError):
            sandbox.resolve("/etc/passwd")


class TestFilesystemTools:
    def test_write_then_read(self, registry, sandbox):
        registry.run("write_file", {"path": "a.py", "content": "print('hi')"}, sandbox)
        out = registry.run("read_file", {"path": "a.py"}, sandbox)
        assert "print('hi')" in out
        assert "1\t" in out or "1 " in out  # line numbering present

    def test_edit_unique(self, registry, sandbox):
        registry.run("write_file", {"path": "a.txt", "content": "foo bar"}, sandbox)
        msg = registry.run(
            "edit_file",
            {"path": "a.txt", "old_string": "foo", "new_string": "baz"},
            sandbox,
        )
        assert "Edited" in msg
        assert "baz bar" in registry.run("read_file", {"path": "a.txt"}, sandbox)

    def test_edit_ambiguous_is_rejected(self, registry, sandbox):
        registry.run("write_file", {"path": "a.txt", "content": "x x"}, sandbox)
        msg = registry.run(
            "edit_file",
            {"path": "a.txt", "old_string": "x", "new_string": "y"},
            sandbox,
        )
        assert "not unique" in msg

    def test_edit_missing_is_rejected(self, registry, sandbox):
        registry.run("write_file", {"path": "a.txt", "content": "hello"}, sandbox)
        msg = registry.run(
            "edit_file",
            {"path": "a.txt", "old_string": "zzz", "new_string": "y"},
            sandbox,
        )
        assert "not found" in msg

    def test_list_dir(self, registry, sandbox):
        registry.run("write_file", {"path": "a.txt", "content": "1"}, sandbox)
        out = registry.run("list_dir", {"path": "."}, sandbox)
        assert "a.txt" in out


class TestSearchTool:
    def test_grep_finds_matches(self, registry, sandbox):
        registry.run("write_file", {"path": "a.py", "content": "import os\nx = 1"}, sandbox)
        out = registry.run("grep", {"pattern": r"import\s+\w+"}, sandbox)
        assert "a.py:1" in out


class TestRegistry:
    def test_unknown_tool(self, registry, sandbox):
        assert "unknown tool" in registry.run("nope", {}, sandbox)

    def test_shell_toggle(self):
        assert "run_bash" in build_default_tools(enable_shell=True)
        assert "run_bash" not in build_default_tools(enable_shell=False)

    def test_shell_runs(self, registry, sandbox):
        out = registry.run("run_bash", {"command": "echo hello"}, sandbox)
        assert "hello" in out
        assert "exit 0" in out
