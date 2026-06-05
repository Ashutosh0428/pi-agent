"""The agent loop.

This is the heart of pi: a ReAct-style tool-use loop.

    user prompt
        │
        ▼
   ┌─► ask the LLM ─────────────► no tool calls ──► return final text
   │        │
   │   tool calls?
   │        ▼
   │   run each tool (with optional confirmation / sub-agent delegation)
   │        ▼
   └── feed results back to the LLM   (repeat, up to max_iterations)

The loop is provider-agnostic (talks to :class:`LLMProvider`) and UI-agnostic
(emits events via a callback). It keeps the transcript in a **neutral** shape so
the same conversation can be handed to any provider. Transient model errors are
retried with backoff; the model may also ``delegate`` a subtask to a sub-agent.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
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

EventCallback = Callable[[str, Any], None]
ConfirmCallback = Callable[[ToolCall], bool]

# 4xx (except 408/409/429) are permanent — retrying wastes tokens. Everything
# else (429, 5xx, timeouts, dropped connections) is worth retrying.
_PERMANENT_CODES = {400, 401, 403, 404, 422}
_TRANSIENT_NAME_HINTS = (
    "ratelimit", "timeout", "connection", "overloaded",
    "serviceunavailable", "internalserver", "apistatus",
)


def _is_transient(exc: Exception) -> bool:
    """Decide whether a model-call error is worth retrying."""
    code = getattr(exc, "status_code", None)
    if isinstance(code, int):
        return code not in _PERMANENT_CODES and (code in (408, 409, 429) or code >= 500)
    name = type(exc).__name__.lower()
    return any(hint in name for hint in _TRANSIENT_NAME_HINTS)


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

    def _with_retry(self, fn: Callable[[], Any]) -> Any:
        """Call ``fn``; retry transient errors up to ``config.max_retries``."""
        attempt = 0
        while True:
            try:
                return fn()
            except Exception as exc:
                attempt += 1
                if attempt > self.config.max_retries or not _is_transient(exc):
                    raise
                self._emit(
                    "info",
                    f"Transient error ({type(exc).__name__}); "
                    f"retrying {attempt}/{self.config.max_retries}…",
                )
                time.sleep(min(2 ** (attempt - 1), 16))

    def _ask(self, tools: list[dict[str, Any]]) -> tuple[AssistantResponse, bool]:
        """One model turn (with retry). Returns (response, streamed?)."""
        can_stream = (
            self.config.stream
            and getattr(self.provider, "supports_streaming", False)
            and hasattr(self.provider, "stream")
            and self.on_event is not None
        )
        if can_stream:
            response = self._with_retry(
                lambda: self.provider.stream(  # type: ignore[attr-defined]
                    self.config.system_prompt,
                    self.messages,
                    tools,
                    lambda delta: self._emit("assistant_delta", delta),
                )
            )
            return response, True
        response = self._with_retry(
            lambda: self.provider.complete(self.config.system_prompt, self.messages, tools)
        )
        return response, False

    def _run_subagent(self, args: dict[str, Any]) -> str:
        """Run a focused sub-agent to completion on the same workspace."""
        task = (args.get("task") or "").strip()
        if not task:
            return "Error: 'task' is required for delegate."
        self._emit("info", f"🤝 delegating to sub-agent: {task[:100]}")
        sub = Agent(
            provider=self.provider,
            registry=self.registry.without("delegate"),  # no recursive delegation
            sandbox=self.sandbox,
            config=replace(self.config, max_iterations=min(self.config.max_iterations, 12)),
        )
        try:
            result = sub.run(task)
        except Exception as exc:  # report failure back to the parent, don't crash
            return f"Sub-agent failed: {type(exc).__name__}."
        self.total_usage += sub.total_usage
        return result or "(sub-agent returned no text)"

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

            if response.text and not streamed:
                self._emit("assistant_text", response.text)

            if not response.tool_calls:
                return response.text

            results: list[ToolResult] = []
            for call in response.tool_calls:
                self._emit("tool_call", call)
                if call.name == "update_plan":
                    self._emit("plan", call.args.get("steps", []))

                if call.name == "delegate":
                    output = self._run_subagent(call.args)
                elif self._should_run(call):
                    output = self.registry.run(call.name, call.args, self.sandbox)
                else:
                    output = "Skipped by user."

                self._emit("tool_result", {"call": call, "output": output})
                results.append(ToolResult(id=call.id, name=call.name, output=output))

            self.messages.append({"role": "tool", "results": results})

        self._emit("info", "Reached max iterations.")
        return "Stopped: reached the maximum number of tool iterations."
