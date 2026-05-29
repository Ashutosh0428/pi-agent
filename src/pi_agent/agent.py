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

The loop is deliberately provider-agnostic (talks to :class:`LLMProvider`) and
UI-agnostic (emits events via a callback). The same Agent powers the terminal
REPL and any other front-end.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from pi_agent.config import AgentConfig
from pi_agent.llm import LLMProvider, ToolCall
from pi_agent.sandbox import Sandbox
from pi_agent.tools.registry import ToolRegistry

# UI hooks ------------------------------------------------------------------
# on_event(kind, payload): kind in {"assistant_text", "tool_call",
#   "tool_result", "info"}. confirm(tool_call) -> bool, asked before a mutating
# tool runs (unless auto_approve).
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
    messages: list[dict[str, Any]] = field(default_factory=list)

    def _emit(self, kind: str, payload: Any) -> None:
        if self.on_event is not None:
            self.on_event(kind, payload)

    def reset(self) -> None:
        """Clear the conversation transcript."""
        self.messages = []

    def _should_run(self, call: ToolCall) -> bool:
        """Confirm a mutating tool unless auto-approve or no confirm hook set."""
        tool = self.registry.get(call.name)
        if tool is None or not tool.mutating or self.config.auto_approve:
            return True
        if self.confirm is None:
            return True
        return self.confirm(call)

    def run(self, user_input: str) -> str:
        """Process one user turn; returns the final assistant text."""
        self.messages.append({"role": "user", "content": user_input})

        for _ in range(self.config.max_iterations):
            response = self.provider.complete(
                self.config.system_prompt, self.messages, self.registry.schemas()
            )
            self.messages.append(response.assistant_message)

            if response.text:
                self._emit("assistant_text", response.text)

            if not response.tool_calls:
                return response.text

            tool_results = []
            for call in response.tool_calls:
                self._emit("tool_call", call)
                if self._should_run(call):
                    output = self.registry.run(call.name, call.args, self.sandbox)
                else:
                    output = "Skipped by user."
                self._emit("tool_result", {"call": call, "output": output})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": output,
                    }
                )

            self.messages.append({"role": "user", "content": tool_results})

        self._emit("info", "Reached max iterations.")
        return "Stopped: reached the maximum number of tool iterations."
