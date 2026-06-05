"""Tests for analyze_data + make_slides. Guards run offline; exec needs [data]."""

from __future__ import annotations

import pytest

from pi_agent.sandbox import Sandbox
from pi_agent.tools.datasci import data_tools
from pi_agent.tools.registry import build_default_tools


def _reg():
    return build_default_tools(enable_shell=False, enable_data=True)


class TestRegistration:
    def test_registered_only_when_enabled(self):
        r = _reg()
        assert "analyze_data" in r and "make_slides" in r
        assert "analyze_data" not in build_default_tools(enable_shell=False)

    def test_mutating_flags(self):
        by_name = {t.name: t for t in data_tools()}
        assert by_name["make_slides"].mutating is True
        assert by_name["analyze_data"].mutating is False


class TestGuards:
    def test_analyze_requires_path(self, tmp_path):
        assert "required" in _reg().run("analyze_data", {}, Sandbox(tmp_path))

    def test_analyze_blocks_path_escape(self, tmp_path):
        out = _reg().run("analyze_data", {"path": "/etc/passwd"}, Sandbox(tmp_path))
        assert "outside the sandbox" in out

    def test_make_slides_rejects_empty(self, tmp_path):
        out = _reg().run("make_slides", {"title": "x", "slides": []}, Sandbox(tmp_path))
        assert "non-empty list" in out


class TestExecution:
    def test_analyze_runs(self, tmp_path):
        pytest.importorskip("pandas")
        (tmp_path / "d.csv").write_text("a,b\n1,2\n3,4\n5,6\n")
        out = _reg().run("analyze_data", {"path": "d.csv", "target": "b"}, Sandbox(tmp_path))
        assert "Data profile" in out and "rows" in out

    def test_make_slides_runs(self, tmp_path):
        pytest.importorskip("pptx")
        out = _reg().run(
            "make_slides",
            {"title": "T", "slides": [{"heading": "H", "bullets": ["one", "two"]}]},
            Sandbox(tmp_path),
        )
        assert "Created" in out and (tmp_path / "deck.pptx").exists()
