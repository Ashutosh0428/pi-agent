"""Memory tool tests — append, caps, recall, registry gating (no network)."""

from __future__ import annotations

from datetime import date

from pi_agent.sandbox import Sandbox
from pi_agent.tools.memory import (
    MEMORY_FACT_CAP,
    MEMORY_RECALL_CAP,
    MEMORY_RELPATH,
    load_memory,
    memory_tools,
)
from pi_agent.tools.registry import build_default_tools

REMEMBER = memory_tools()[0]


def test_remember_appends_dated_facts(tmp_path):
    sb = Sandbox(tmp_path)
    assert "Remembered" in REMEMBER.handler({"fact": "tests use pytest"}, sb)
    assert "Remembered" in REMEMBER.handler({"fact": "API lives in src/api"}, sb)
    lines = (tmp_path / MEMORY_RELPATH).read_text().splitlines()
    assert len(lines) == 2
    assert lines[0] == f"- [{date.today().isoformat()}] tests use pytest"


def test_remember_rejects_empty_and_oversize(tmp_path):
    sb = Sandbox(tmp_path)
    assert REMEMBER.handler({"fact": "  "}, sb).startswith("Error")
    assert REMEMBER.handler({"fact": "x" * (MEMORY_FACT_CAP + 1)}, sb).startswith("Error")
    assert not (tmp_path / MEMORY_RELPATH).exists()


def test_load_memory_missing_is_empty(tmp_path):
    assert load_memory(tmp_path) == ""


def test_recall_round_trip(tmp_path):
    sb = Sandbox(tmp_path)
    REMEMBER.handler({"fact": "prefers dataclasses"}, sb)
    assert "prefers dataclasses" in load_memory(tmp_path)


def test_recall_caps_to_tail_on_line_boundary(tmp_path):
    sb = Sandbox(tmp_path)
    for i in range(300):
        REMEMBER.handler({"fact": f"fact number {i:03d}"}, sb)
    recalled = load_memory(tmp_path)
    assert len(recalled.encode()) <= MEMORY_RECALL_CAP
    assert recalled.startswith("- [")  # snapped to a whole line
    assert "fact number 299" in recalled  # newest survives
    assert "fact number 000" not in recalled  # oldest aged out


def test_registry_gating():
    assert "remember" not in build_default_tools().names()
    assert "remember" in build_default_tools(enable_memory=True).names()
