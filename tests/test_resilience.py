"""Tests for transient-error retry and sub-agent delegation (no network)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from pi_agent.agent import Agent, _is_transient
from pi_agent.config import AgentConfig
from pi_agent.llm import AssistantResponse, ToolCall, Usage
from pi_agent.sandbox import Sandbox
from pi_agent.tools.registry import build_default_tools


class _Transient(Exception):
    status_code = 503


class _Permanent(Exception):
    status_code = 400


@dataclass
class FlakyProvider:
    fail: int
    final: AssistantResponse
    exc: Exception
    name: str = "flaky"
    model: str = "m"
    supports_streaming: bool = False
    n: int = field(default=0)

    def complete(self, system, messages, tools):  # noqa: ARG002
        if self.n < self.fail:
            self.n += 1
            raise self.exc
        return self.final


@dataclass
class ScriptedProvider:
    steps: list
    name: str = "scripted"
    model: str = "m"
    supports_streaming: bool = False
    calls: int = field(default=0)

    def complete(self, system, messages, tools):  # noqa: ARG002
        step = self.steps[min(self.calls, len(self.steps) - 1)]
        self.calls += 1
        return step


def _final(text):
    return AssistantResponse(text=text, tool_calls=[], usage=Usage(1, 1))


def _tool(name, args):
    return AssistantResponse(text="", tool_calls=[ToolCall("c", name, args)], usage=Usage(1, 1))


def _agent(provider, tmp_path, **cfg):
    return Agent(
        provider=provider,
        registry=build_default_tools(enable_shell=False, enable_subagents=True),
        sandbox=Sandbox(tmp_path),
        config=AgentConfig(auto_approve=True, **cfg),
    )


class TestTransientClassifier:
    def test_4xx_is_permanent(self):
        assert _is_transient(_Permanent()) is False

    def test_5xx_is_transient(self):
        assert _is_transient(_Transient()) is True

    def test_name_hint_is_transient(self):
        class RateLimitError(Exception):
            pass

        assert _is_transient(RateLimitError()) is True


class TestRetry:
    def test_retries_then_succeeds(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pi_agent.agent.time.sleep", lambda *_: None)
        p = FlakyProvider(fail=2, final=_final("ok"), exc=_Transient())
        assert _agent(p, tmp_path).run("hi") == "ok"
        assert p.n == 2

    def test_permanent_not_retried(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pi_agent.agent.time.sleep", lambda *_: None)
        p = FlakyProvider(fail=99, final=_final("ok"), exc=_Permanent())
        with pytest.raises(_Permanent):
            _agent(p, tmp_path).run("hi")
        assert p.n == 1


class TestDelegate:
    def test_delegate_runs_subagent(self, tmp_path):
        p = ScriptedProvider(
            [
                _tool("delegate", {"task": "subtask"}),  # main delegates
                _final("sub result"),  # sub-agent finishes
                _final("main done"),  # main finishes
            ]
        )
        assert _agent(p, tmp_path).run("big task") == "main done"
        assert p.calls == 3  # main -> sub -> main

    def test_subagent_cannot_delegate(self):
        reg = build_default_tools(enable_shell=False, enable_subagents=True)
        assert "delegate" in reg
        assert "delegate" not in reg.without("delegate")
