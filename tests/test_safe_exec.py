"""Tests for the restricted run_command tool (real subprocess, no network)."""

from __future__ import annotations

from pi_agent.sandbox import Sandbox
from pi_agent.tools.registry import build_default_tools
from pi_agent.tools.safe_exec import safe_command_tools


def _registry():
    return build_default_tools(enable_shell=False, enable_safe_command=True)


class TestRunCommand:
    def test_registered_only_when_enabled(self):
        assert "run_command" in build_default_tools(enable_shell=False, enable_safe_command=True)
        assert "run_command" not in build_default_tools(enable_shell=False)

    def test_not_mutating(self):
        assert safe_command_tools()[0].mutating is False

    def test_runs_allowed_command(self, tmp_path):
        (tmp_path / "a.txt").write_text("hello\nworld\n")
        out = _registry().run("run_command", {"command": "wc -l a.txt"}, Sandbox(tmp_path))
        assert "exit 0" in out and "a.txt" in out

    def test_rejects_disallowed_program(self, tmp_path):
        out = _registry().run("run_command", {"command": "python -c x"}, Sandbox(tmp_path))
        assert "not allowed" in out

    def test_rejects_absolute_path(self, tmp_path):
        out = _registry().run("run_command", {"command": "cat /etc/passwd"}, Sandbox(tmp_path))
        assert "outside the sandbox" in out

    def test_rejects_parent_traversal(self, tmp_path):
        out = _registry().run("run_command", {"command": "cat ../secret"}, Sandbox(tmp_path))
        assert "outside the sandbox" in out

    def test_empty_command(self, tmp_path):
        assert "empty" in _registry().run("run_command", {"command": "   "}, Sandbox(tmp_path))
