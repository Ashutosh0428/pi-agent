"""Tests for the planning/update_plan tool (no network)."""

from __future__ import annotations

from pi_agent.sandbox import Sandbox
from pi_agent.tools.planning import planning_tools
from pi_agent.tools.registry import build_default_tools


class TestPlanningTool:
    def test_registered_even_without_shell(self):
        assert "update_plan" in build_default_tools(enable_shell=False)

    def test_not_mutating(self):
        assert planning_tools()[0].mutating is False

    def test_summary_counts(self, tmp_path):
        out = build_default_tools().run(
            "update_plan",
            {"steps": [
                {"step": "a", "status": "done"},
                {"step": "b", "status": "in_progress"},
                {"step": "c", "status": "pending"},
            ]},
            Sandbox(tmp_path),
        )
        assert "3 steps" in out and "1 done" in out and "1 in progress" in out

    def test_rejects_empty(self, tmp_path):
        out = build_default_tools().run("update_plan", {"steps": []}, Sandbox(tmp_path))
        assert "Error" in out
