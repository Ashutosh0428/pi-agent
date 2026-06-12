"""Tests for the agent loop using a scripted fake provider (no API key)."""

from __future__ import annotations

from dataclasses import dataclass, field

from pi_agent.agent import Agent
from pi_agent.config import AgentConfig
from pi_agent.llm import AssistantResponse, ToolCall, Usage
from pi_agent.sandbox import Sandbox
from pi_agent.tools.registry import build_default_tools


@dataclass
class FakeProvider:
    """Returns pre-scripted responses, one per ``complete`` call."""

    steps: list[AssistantResponse]
    name: str = "fake"
    model: str = "fake-model"
    supports_streaming: bool = False
    calls: int = field(default=0)

    def complete(self, system, messages, tools):  # noqa: ARG002 - interface
        step = self.steps[min(self.calls, len(self.steps) - 1)]
        self.calls += 1
        return step


def _tool_step(text, call: ToolCall) -> AssistantResponse:
    return AssistantResponse(text=text, tool_calls=[call], usage=Usage(10, 5))


def _final_step(text) -> AssistantResponse:
    return AssistantResponse(text=text, tool_calls=[], usage=Usage(8, 3))


def _make_agent(provider, tmp_path, **cfg):
    return Agent(
        provider=provider,
        registry=build_default_tools(enable_shell=True),
        sandbox=Sandbox(tmp_path),
        config=AgentConfig(auto_approve=True, **cfg),
    )


class TestAgentLoop:
    def test_runs_tool_then_returns_final_text(self, tmp_path):
        provider = FakeProvider(
            [
                _tool_step(
                    "creating file",
                    ToolCall("t1", "write_file", {"path": "hi.py", "content": "print(1)"}),
                ),
                _final_step("Done."),
            ]
        )
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
        looping = _tool_step("again", ToolCall("t", "list_dir", {"path": "."}))
        provider = FakeProvider([looping])
        agent = _make_agent(provider, tmp_path, max_iterations=3)
        result = agent.run("loop forever")
        assert "maximum number of tool iterations" in result
        assert provider.calls == 3

    def test_confirm_false_skips_mutation(self, tmp_path):
        provider = FakeProvider(
            [
                _tool_step(
                    "writing",
                    ToolCall("t1", "write_file", {"path": "x.txt", "content": "data"}),
                ),
                _final_step("ok"),
            ]
        )
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
        provider = FakeProvider(
            [
                _tool_step("t", ToolCall("t1", "list_dir", {"path": "."})),
                _final_step("done"),
            ]
        )
        agent = _make_agent(provider, tmp_path)
        agent.on_event = lambda kind, payload: events.append(kind)
        agent.run("list")
        assert "tool_call" in events
        assert "tool_result" in events
        assert "assistant_text" in events
        assert "usage" in events

    def test_usage_accumulates_across_turns(self, tmp_path):
        provider = FakeProvider(
            [
                _tool_step("t", ToolCall("t1", "list_dir", {"path": "."})),  # 10 + 5
                _final_step("done"),  # 8 + 3
            ]
        )
        agent = _make_agent(provider, tmp_path)
        agent.run("list")
        assert agent.total_usage.input_tokens == 18
        assert agent.total_usage.output_tokens == 8
        assert agent.total_usage.total_tokens == 26

    def test_plan_event_emitted_for_update_plan(self, tmp_path):
        provider = FakeProvider(
            [
                _tool_step(
                    "planning",
                    ToolCall(
                        "p1", "update_plan", {"steps": [{"step": "do it", "status": "in_progress"}]}
                    ),
                ),
                _final_step("done"),
            ]
        )
        agent = _make_agent(provider, tmp_path)
        events = []
        agent.on_event = lambda kind, payload: events.append((kind, payload))
        agent.run("x")
        plans = [p for k, p in events if k == "plan"]
        assert plans and plans[0][0]["step"] == "do it"

    def test_neutral_transcript_shape(self, tmp_path):
        provider = FakeProvider(
            [
                _tool_step("t", ToolCall("t1", "list_dir", {"path": "."})),
                _final_step("done"),
            ]
        )
        agent = _make_agent(provider, tmp_path)
        agent.run("list")
        roles = [m["role"] for m in agent.messages]
        assert roles == ["user", "assistant", "tool", "assistant"]


class TestHistoryTrimming:
    def _agent(self, tmp_path, cap):
        return _make_agent(FakeProvider([_final_step("x")]), tmp_path, max_history_messages=cap)

    def test_no_trim_under_cap(self, tmp_path):
        agent = self._agent(tmp_path, cap=80)
        agent.messages = [{"role": "user", "content": "hi"}]
        assert agent._history_for_request() is agent.messages

    def test_disabled_when_cap_zero(self, tmp_path):
        agent = self._agent(tmp_path, cap=0)
        agent.messages = [{"role": "user", "content": str(i)} for i in range(200)]
        assert len(agent._history_for_request()) == 200

    def test_trims_and_snaps_to_user_boundary(self, tmp_path):
        # A long transcript of repeated user/assistant/tool triples. Trimming to
        # a small cap must never start on an assistant or tool message, or the
        # provider would receive a tool_use without its result.
        agent = self._agent(tmp_path, cap=4)
        msgs: list = []
        for i in range(10):
            msgs.append({"role": "user", "content": f"u{i}"})
            msgs.append(
                {"role": "assistant", "content": "", "tool_calls": [ToolCall("c", "list_dir", {})]}
            )
            msgs.append({"role": "tool", "results": []})
        agent.messages = msgs
        sent = agent._history_for_request()
        assert sent[0]["role"] == "user"  # snapped to a user boundary
        assert len(sent) <= 4


class TestReflection:
    def test_off_by_default_single_pass(self, tmp_path):
        provider = FakeProvider([_final_step("First answer.")])
        agent = _make_agent(provider, tmp_path)
        assert agent.run("do something") == "First answer."
        assert provider.calls == 1

    def test_reflect_runs_one_review_and_returns_reviewed_text(self, tmp_path):
        provider = FakeProvider([_final_step("Draft answer."), _final_step("Reviewed answer.")])
        agent = _make_agent(provider, tmp_path, reflect=True)
        assert agent.run("do something") == "Reviewed answer."
        assert provider.calls == 2  # exactly one extra turn, no recursion
        assert agent.config.reflect is True  # restored after the pass
        assert agent.config.max_iterations == 25  # restored after the pass

    def test_reflection_can_use_tools_before_final(self, tmp_path):
        provider = FakeProvider(
            [
                _final_step("Draft."),
                _tool_step(
                    "fixing",
                    ToolCall("t1", "write_file", {"path": "fix.py", "content": "ok"}),
                ),
                _final_step("Fixed and final."),
            ]
        )
        agent = _make_agent(provider, tmp_path, reflect=True)
        assert agent.run("task") == "Fixed and final."
        assert (tmp_path / "fix.py").read_text() == "ok"

    def test_no_reflection_on_max_iteration_stop(self, tmp_path):
        looping = _tool_step(
            "again", ToolCall("t1", "write_file", {"path": "a.txt", "content": "x"})
        )
        provider = FakeProvider([looping])
        agent = _make_agent(provider, tmp_path, reflect=True, max_iterations=2)
        out = agent.run("task")
        assert out.startswith("Stopped:")
        assert provider.calls == 2  # no review turn appended


class TestGuardrailsInLoop:
    def test_destructive_forces_confirm_even_under_auto_approve(self, tmp_path):
        called = _tool_step("deleting", ToolCall("t1", "run_bash", {"command": "rm -rf /"}))
        provider = FakeProvider([called, _final_step("done")])
        seen = {"confirmed": False}

        def deny(_call):
            seen["confirmed"] = True
            return False  # user says no

        agent = _make_agent(provider, tmp_path)  # auto_approve=True
        agent.confirm = deny
        agent.run("clean up")
        assert seen["confirmed"] is True  # confirm was demanded despite auto_approve

    def test_destructive_blocked_when_non_interactive(self, tmp_path):
        called = _tool_step("rm", ToolCall("t1", "run_bash", {"command": "sudo rm -rf /"}))
        provider = FakeProvider([called, _final_step("done")])
        agent = _make_agent(provider, tmp_path)  # no confirm hook
        agent.run("danger")
        # the tool result fed back must be the guardrail block, not execution
        tool_msg = next(m for m in agent.messages if m["role"] == "tool")
        assert "Blocked by guardrail" in tool_msg["results"][0].output

    def test_safe_command_runs_normally(self, tmp_path):
        called = _tool_step(
            "writing", ToolCall("t1", "write_file", {"path": "ok.txt", "content": "hi"})
        )
        provider = FakeProvider([called, _final_step("done")])
        agent = _make_agent(provider, tmp_path)
        agent.run("make a file")
        assert (tmp_path / "ok.txt").read_text() == "hi"
