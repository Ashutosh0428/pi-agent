"""LLM provider abstraction.

The agent loop talks to an LLM only through :class:`LLMProvider`. This keeps the
loop provider-agnostic: today there is one implementation (Anthropic), and
adding OpenAI / local models later means writing one more class — no changes to
the agent. Tests use a scripted fake provider, so they never need an API key.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    """A single tool invocation requested by the model."""

    id: str
    name: str
    args: dict[str, Any]


@dataclass
class AssistantResponse:
    """Normalised result of one model turn.

    ``assistant_message`` is the provider-native message dict to append to the
    running transcript; the agent loop treats it as opaque.
    """

    text: str
    tool_calls: list[ToolCall]
    assistant_message: dict[str, Any]
    stop_reason: str = ""


class LLMProvider(Protocol):
    """Interface every provider must implement."""

    name: str

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AssistantResponse: ...


@dataclass
class AnthropicProvider:
    """Anthropic Claude provider using the Messages API with tool use."""

    model: str
    max_tokens: int = 4096
    api_key: str | None = None
    name: str = field(default="anthropic", init=False)

    def __post_init__(self) -> None:
        # Imported lazily so importing this module (e.g. in tests) does not
        # require the anthropic package or an API key.
        import anthropic

        self._client = anthropic.Anthropic(api_key=self.api_key)

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AssistantResponse:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=messages,
            tools=tools,
        )

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        content_blocks: list[dict[str, Any]] = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
                content_blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, args=dict(block.input))
                )
                content_blocks.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )

        return AssistantResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            assistant_message={"role": "assistant", "content": content_blocks},
            stop_reason=response.stop_reason or "",
        )
