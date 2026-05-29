"""Tests for the agent loop using a scripted fake provider (no API key)."""

from __future__ import annotations

from dataclasses import dataclass, field

from pi_agent.agent import Agent
from pi_agent.config import AgentConfig
from pi_agent.llm import AssistantResponse, ToolCall
from pi_agent.sandbox import Sandbox
from pi_agent.tools.registry import build_default_tools


@dataclass
class FakeProvider:
    """Returns pre-scripted responses, one per ``complete`` call."""

    steps: list[AssistantResponse]
    name: str = "fake"
    calls: int = field(default=0)

    def complete(self, system, messages, tools):  # noqa: ARG002 - interface
        step = self.steps[min(self.calls, len(self.steps) - 1)]
        self.calls += 1
        return step


def _tool_step(text, call: ToolCall) -> AssistantResponse:
    return AssistantResponse(
        text=text,
        tool_calls=[call],
        assistant_message={"role": "assistant", "content": text},
    )


def _final_step(text) -> AssistantResponse:
    return AssistantResponse(
        text=text, tool_calls=[], assistant_message={"role": "assistant", "content": text}
    )


def _make_agent(provider, tmp_path, **cfg):
    return Agent(
        provider=provider,
        registry=build_default_tools(enable_shell=True),
        sandbox=Sandbox(tmp_path),
        config=AgentConfig(auto_approve=True, **cfg),
    )


class TestAgentLoop:
    def test_runs_tool_then_returns_final_text(self, tmp_path):
        provider = FakeProvider([
            _tool_step(
                "creating file",
                ToolCall("t1", "write_file", {"path": "hi.py", "content": "print(1)"}),
            ),
            _final_step("Done."),
        ])
        agent = _make_agent(provider, tmp_path)
        result = agent.run("create hi.py")
        assert result == "Done."
        assert (tmp_path / "hi.py").read_text() == "print(1)"

    def test_no_tools_returns_immediately(self, tmp_path):
        provider = FakeProvider([_final_step("Hello!")])
        agent = _make_agent(provider, tmp_path)
        assert agent.run("hi") == "Hello!"
        assert provider.calls == 1

    def test_max_iterations_guard(self, tmp_path):
        # Provider always asks for a tool -> loop must stop at the cap.
        looping = _tool_step(
            "again", ToolCall("t", "list_dir", {"path": "."})
        )
        provider = FakeProvider([looping])
        agent = _make_agent(provider, tmp_path, max_iterations=3)
        result = agent.run("loop forever")
        assert "maximum number of tool iterations" in result
        assert provider.calls == 3

    def test_confirm_false_skips_mutation(self, tmp_path):
        provider = FakeProvider([
            _tool_step(
                "writing",
                ToolCall("t1", "write_file", {"path": "x.txt", "content": "data"}),
            ),
            _final_step("ok"),
        ])
        agent = Agent(
            provider=provider,
            registry=build_default_tools(enable_shell=True),
            sandbox=Sandbox(tmp_path),
            config=AgentConfig(auto_approve=False),
            confirm=lambda call: False,  # user declines
        )
        agent.run("write x.txt")
        assert not (tmp_path / "x.txt").exists()

    def test_events_are_emitted(self, tmp_path):
        events = []
        provider = FakeProvider([
            _tool_step("t", ToolCall("t1", "list_dir", {"path": "."})),
            _final_step("done"),
        ])
        agent = _make_agent(provider, tmp_path)
        agent.on_event = lambda kind, payload: events.append(kind)
        agent.run("list")
        assert "tool_call" in events
        assert "tool_result" in events
        assert "assistant_text" in events
