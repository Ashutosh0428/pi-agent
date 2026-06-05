"""The agent loop.

This is the heart of pi: a ReAct-style tool-use loop.

    user prompt
        │
        ▼
   ┌─► ask the LLM ─────────────► no tool calls ──► return final text
   │        │
   │   tool calls?
   │        ▼
   │   run each tool (with optional confirmation)
   │        ▼
   └── feed results back to the LLM   (repeat, up to max_iterations)

The loop is provider-agnostic (talks to :class:`LLMProvider`) and UI-agnostic
(emits events via a callback). It keeps the transcript in a **neutral** shape
— ``user`` / ``assistant`` / ``tool`` entries — so the same conversation can be
handed to any provider, even switching models mid-session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from pi_agent.config import AgentConfig
from pi_agent.llm import (
    AssistantResponse,
    LLMProvider,
    NeutralMessage,
    ToolCall,
    ToolResult,
    Usage,
)
from pi_agent.sandbox import Sandbox
from pi_agent.tools.registry import ToolRegistry

# UI hooks ------------------------------------------------------------------
# on_event(kind, payload): kind in {"assistant_text", "assistant_delta",
#   "tool_call", "tool_result", "usage", "info"}.
# confirm(tool_call) -> bool, asked before a mutating tool runs (unless
# auto_approve).
EventCallback = Callable[[str, Any], None]
ConfirmCallback = Callable[[ToolCall], bool]


@dataclass
class Agent:
    provider: LLMProvider
    registry: ToolRegistry
    sandbox: Sandbox
    config: AgentConfig
    on_event: EventCallback | None = None
    confirm: ConfirmCallback | None = None
    messages: list[NeutralMessage] = field(default_factory=list)
    total_usage: Usage = field(default_factory=Usage)

    def _emit(self, kind: str, payload: Any) -> None:
        if self.on_event is not None:
            self.on_event(kind, payload)

    def reset(self) -> None:
        """Clear the conversation transcript (keeps cumulative usage)."""
        self.messages = []

    def _should_run(self, call: ToolCall) -> bool:
        """Confirm a mutating tool unless auto-approve or no confirm hook set."""
        tool = self.registry.get(call.name)
        if tool is None or not tool.mutating or self.config.auto_approve:
            return True
        if self.confirm is None:
            return True
        return self.confirm(call)

    def _ask(self, tools: list[dict[str, Any]]) -> tuple[AssistantResponse, bool]:
        """One model turn. Returns (response, streamed?)."""
        can_stream = (
            self.config.stream
            and getattr(self.provider, "supports_streaming", False)
            and hasattr(self.provider, "stream")
            and self.on_event is not None
        )
        if can_stream:
            response = self.provider.stream(  # type: ignore[attr-defined]
                self.config.system_prompt,
                self.messages,
                tools,
                lambda delta: self._emit("assistant_delta", delta),
            )
            return response, True
        response = self.provider.complete(
            self.config.system_prompt, self.messages, tools
        )
        return response, False

    def run(self, user_input: str) -> str:
        """Process one user turn; returns the final assistant text."""
        self.messages.append({"role": "user", "content": user_input})
        tools = self.registry.schemas()

        for _ in range(self.config.max_iterations):
            response, streamed = self._ask(tools)

            self.total_usage += response.usage
            self._emit("usage", {"turn": response.usage, "total": self.total_usage})

            self.messages.append(
                {
                    "role": "assistant",
                    "content": response.text,
                    "tool_calls": response.tool_calls,
                }
            )

            # In streaming mode the text was already delivered via deltas.
            if response.text and not streamed:
                self._emit("assistant_text", response.text)

            if not response.tool_calls:
                return response.text

            results: list[ToolResult] = []
            for call in response.tool_calls:
                self._emit("tool_call", call)
                if call.name == "update_plan":
                    self._emit("plan", call.args.get("steps", []))
                if self._should_run(call):
                    output = self.registry.run(call.name, call.args, self.sandbox)
                else:
                    output = "Skipped by user."
                self._emit("tool_result", {"call": call, "output": output})
                results.append(ToolResult(id=call.id, name=call.name, output=output))

            self.messages.append({"role": "tool", "results": results})

        self._emit("info", "Reached max iterations.")
        return "Stopped: reached the maximum number of tool iterations."
