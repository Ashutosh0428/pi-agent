"""Tests for the read-only git tool (real git, no network)."""

from __future__ import annotations

import subprocess

import pytest

from pi_agent.sandbox import Sandbox
from pi_agent.tools.registry import build_default_tools
from pi_agent.tools.vcs import git_tools


def _registry():
    return build_default_tools(enable_shell=False, enable_vcs=True)


def _init_repo(path):
    """Create a tiny git repo with one commit at ``path``."""
    run = lambda *a: subprocess.run(  # noqa: E731
        ["git", *a],
        cwd=path,
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
        },
    )
    run("init", "-q")
    (path / "a.txt").write_text("hello\n")
    run("add", "a.txt")
    run("commit", "-q", "-m", "first")


def _has_git() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


pytestmark = pytest.mark.skipif(not _has_git(), reason="git not installed")


class TestGitTool:
    def test_registered_only_when_enabled(self):
        assert "git" in build_default_tools(enable_shell=False, enable_vcs=True)
        assert "git" not in build_default_tools(enable_shell=False)

    def test_not_mutating(self):
        assert git_tools()[0].mutating is False

    def test_status_runs(self, tmp_path):
        _init_repo(tmp_path)
        out = _registry().run("git", {"subcommand": "status"}, Sandbox(tmp_path))
        assert "exit 0" in out and "branch" in out.lower()

    def test_log_with_args(self, tmp_path):
        _init_repo(tmp_path)
        out = _registry().run(
            "git", {"subcommand": "log", "args": "--oneline -1"}, Sandbox(tmp_path)
        )
        assert "first" in out

    def test_rejects_mutating_subcommand(self, tmp_path):
        _init_repo(tmp_path)
        out = _registry().run("git", {"subcommand": "commit", "args": "-m x"}, Sandbox(tmp_path))
        assert "not allowed" in out

    def test_rejects_push(self, tmp_path):
        out = _registry().run("git", {"subcommand": "push"}, Sandbox(tmp_path))
        assert "not allowed" in out

    def test_rejects_config_injection(self, tmp_path):
        _init_repo(tmp_path)
        out = _registry().run(
            "git", {"subcommand": "log", "args": "-c core.pager=touch\\ pwned"}, Sandbox(tmp_path)
        )
        assert "not allowed" in out

    def test_rejects_absolute_path_arg(self, tmp_path):
        _init_repo(tmp_path)
        out = _registry().run(
            "git", {"subcommand": "show", "args": "/etc/passwd"}, Sandbox(tmp_path)
        )
        assert "outside the sandbox" in out
