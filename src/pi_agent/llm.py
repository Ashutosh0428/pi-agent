"""LLM provider abstraction — the seam that makes pi multi-provider.

The agent loop talks to an LLM only through :class:`LLMProvider`, and it keeps
its transcript in a **provider-neutral** shape (see :mod:`pi_agent.agent`).
Each provider translates that neutral transcript into its own wire format:

* Anthropic uses ``content`` blocks (``text`` / ``tool_use`` / ``tool_result``).
* OpenAI uses ``tool_calls`` on the assistant message and ``role="tool"``
  follow-ups.

Because the transcript is neutral, you can switch models *mid-conversation*
(``/model``) and even cross providers. Tests use a scripted fake provider, so
they never need an API key or network access.

No API key is ever read, stored, or logged here beyond handing it to the
vendor SDK — keys come from the environment (see :mod:`pi_agent.cli`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable

# --- core data types -------------------------------------------------------


@dataclass
class ToolCall:
    """A single tool invocation requested by the model."""

    id: str
    name: str
    args: dict[str, Any]


@dataclass
class ToolResult:
    """The output of running one :class:`ToolCall`."""

    id: str
    name: str
    output: str


@dataclass
class Usage:
    """Token counts for one or more model turns."""

    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
        )

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class AssistantResponse:
    """Normalised result of one model turn (provider-independent)."""

    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    stop_reason: str = ""


# --- cost estimation -------------------------------------------------------

# Approximate USD per 1M tokens (input, output). Matched by substring on the
# model id. These are estimates for display only — update as prices change.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus": (15.0, 75.0),
    "claude-sonnet": (3.0, 15.0),
    "claude-haiku": (0.80, 4.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.0),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.0, 8.0),
    "o4-mini": (1.10, 4.40),
    "o3": (2.0, 8.0),
}


def estimate_cost(model: str, usage: Usage) -> float | None:
    """Rough USD cost for ``usage`` on ``model``; ``None`` if price unknown."""
    if ":free" in model:  # OpenRouter free models
        return 0.0
    for key, (in_price, out_price) in MODEL_PRICING.items():
        if key in model:
            return (
                usage.input_tokens / 1_000_000 * in_price
                + usage.output_tokens / 1_000_000 * out_price
            )
    return None


# --- neutral transcript -> provider wire formats ---------------------------
# A neutral message is one of:
#   {"role": "user", "content": str}
#   {"role": "assistant", "content": str, "tool_calls": list[ToolCall]}
#   {"role": "tool", "results": list[ToolResult]}

NeutralMessage = dict[str, Any]


def to_anthropic_messages(messages: list[NeutralMessage]) -> list[dict[str, Any]]:
    """Translate the neutral transcript into Anthropic Messages format."""
    out: list[dict[str, Any]] = []
    for msg in messages:
        role = msg["role"]
        if role == "user":
            out.append({"role": "user", "content": msg["content"]})
        elif role == "assistant":
            blocks: list[dict[str, Any]] = []
            if msg.get("content"):
                blocks.append({"type": "text", "text": msg["content"]})
            for call in msg.get("tool_calls", []):
                blocks.append(
                    {"type": "tool_use", "id": call.id, "name": call.name, "input": call.args}
                )
            out.append({"role": "assistant", "content": blocks or msg.get("content", "")})
        elif role == "tool":
            out.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": r.id, "content": r.output}
                        for r in msg["results"]
                    ],
                }
            )
    return out


def to_openai_messages(system: str, messages: list[NeutralMessage]) -> list[dict[str, Any]]:
    """Translate the neutral transcript into OpenAI Chat Completions format."""
    out: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for msg in messages:
        role = msg["role"]
        if role == "user":
            out.append({"role": "user", "content": msg["content"]})
        elif role == "assistant":
            # Some OpenAI-compatible servers (e.g. Groq) reject ``content: null``
            # on an assistant message; an empty string is accepted everywhere.
            entry: dict[str, Any] = {"role": "assistant", "content": msg.get("content") or ""}
            calls = msg.get("tool_calls", [])
            if calls:
                entry["tool_calls"] = [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": json.dumps(c.args)},
                    }
                    for c in calls
                ]
            out.append(entry)
        elif role == "tool":
            for r in msg["results"]:
                out.append({"role": "tool", "tool_call_id": r.id, "content": r.output})
    return out


def to_openai_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Wrap neutral tool specs into OpenAI's ``function`` tool format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]


# --- provider interface ----------------------------------------------------

DeltaCallback = Callable[[str], None]


@runtime_checkable
class LLMProvider(Protocol):
    """Interface every provider implements."""

    name: str
    model: str
    supports_streaming: bool

    def complete(
        self, system: str, messages: list[NeutralMessage], tools: list[dict[str, Any]]
    ) -> AssistantResponse: ...


@dataclass
class AnthropicProvider:
    """Anthropic Claude provider (Messages API with tool use)."""

    model: str
    max_tokens: int = 4096
    thinking: bool = False
    thinking_budget: int = 2048
    api_key: str | None = None
    name: str = field(default="anthropic", init=False)

    def __post_init__(self) -> None:
        # Lazy import so importing this module (e.g. in tests) needs neither the
        # anthropic package nor an API key.
        import anthropic

        self._client = anthropic.Anthropic(api_key=self.api_key)

    @property
    def supports_streaming(self) -> bool:
        # Extended thinking is sent over the non-streaming path for simplicity.
        return not self.thinking

    def _request_kwargs(
        self, system: str, messages: list[NeutralMessage], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        max_tokens = self.max_tokens
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": to_anthropic_messages(messages),
            "tools": tools,
        }
        if self.thinking:
            # max_tokens must exceed the thinking budget.
            kwargs["max_tokens"] = max(max_tokens, self.thinking_budget + 1024)
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": self.thinking_budget}
        return kwargs

    @staticmethod
    def _parse(content: list[Any]) -> tuple[str, list[ToolCall]]:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, args=dict(block.input or {})))
            # "thinking" blocks are intentionally not surfaced to the transcript.
        return "".join(text_parts), tool_calls

    def complete(
        self, system: str, messages: list[NeutralMessage], tools: list[dict[str, Any]]
    ) -> AssistantResponse:
        response = self._client.messages.create(**self._request_kwargs(system, messages, tools))
        text, tool_calls = self._parse(response.content)
        return AssistantResponse(
            text=text,
            tool_calls=tool_calls,
            usage=Usage(response.usage.input_tokens, response.usage.output_tokens),
            stop_reason=response.stop_reason or "",
        )

    def stream(
        self,
        system: str,
        messages: list[NeutralMessage],
        tools: list[dict[str, Any]],
        on_delta: DeltaCallback,
    ) -> AssistantResponse:
        """Stream text deltas via ``on_delta``; return the full normalised turn."""
        kwargs = self._request_kwargs(system, messages, tools)
        with self._client.messages.stream(**kwargs) as stream:
            for chunk in stream.text_stream:
                on_delta(chunk)
            final = stream.get_final_message()
        text, tool_calls = self._parse(final.content)
        return AssistantResponse(
            text=text,
            tool_calls=tool_calls,
            usage=Usage(final.usage.input_tokens, final.usage.output_tokens),
            stop_reason=final.stop_reason or "",
        )


@dataclass
class OpenAIProvider:
    """OpenAI (and OpenAI-compatible) provider via Chat Completions."""

    model: str
    api_key: str | None = None
    base_url: str | None = None
    name: str = field(default="openai", init=False)
    supports_streaming: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        import openai

        self._client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

    def complete(
        self, system: str, messages: list[NeutralMessage], tools: list[dict[str, Any]]
    ) -> AssistantResponse:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=to_openai_messages(system, messages),
            tools=to_openai_tools(tools),
        )
        choice = response.choices[0]
        message = choice.message
        tool_calls = []
        for tc in message.tool_calls or []:
            try:
                parsed = json.loads(tc.function.arguments or "{}")
            except (ValueError, TypeError):
                parsed = {}
            # Weaker models sometimes emit "null" or a non-object — coerce to {}.
            tool_calls.append(
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    args=parsed if isinstance(parsed, dict) else {},
                )
            )
        usage = Usage(0, 0)
        if response.usage is not None:
            usage = Usage(response.usage.prompt_tokens, response.usage.completion_tokens)
        return AssistantResponse(
            text=message.content or "",
            tool_calls=tool_calls,
            usage=usage,
            stop_reason=choice.finish_reason or "",
        )


def infer_provider(model: str) -> str:
    """Guess the provider from a model id."""
    if model.startswith(("gpt", "o1", "o3", "o4", "chatgpt")):
        return "openai"
    if model.startswith("gemini"):
        return "gemini"
    return "anthropic"


@dataclass(frozen=True)
class ProviderSpec:
    """Static facts about a provider, used to build it and to drive the UI."""

    name: str
    kind: str             # "anthropic" or "openai" (which client to use)
    default_model: str
    key_env: str          # environment variable holding the key
    key_url: str          # where a user gets a key
    base_url: str | None = None   # OpenAI-compatible endpoint (Groq / OpenRouter / Ollama)
    free: bool = False    # has a usable free tier (no credit card)
    requires_key: bool = True     # Ollama (local) needs no key
    models: tuple[str, ...] = ()  # suggested model ids for the UI picker (any id still works)


# Groq and OpenRouter are OpenAI-compatible, so they reuse OpenAIProvider with a
# base_url — no new client code. Both offer free keys + strong free models.
PROVIDERS: dict[str, ProviderSpec] = {
    "anthropic": ProviderSpec(
        "anthropic", "anthropic", "claude-sonnet-4-6",
        "ANTHROPIC_API_KEY", "https://console.anthropic.com/settings/keys",
        models=("claude-sonnet-4-6", "claude-opus-4-8", "claude-haiku-4-5-20251001"),
    ),
    "openai": ProviderSpec(
        "openai", "openai", "gpt-4o-mini",
        "OPENAI_API_KEY", "https://platform.openai.com/api-keys",
        models=("gpt-4o-mini", "gpt-4o", "gpt-4.1", "o4-mini"),
    ),
    "groq": ProviderSpec(
        "groq", "openai", "llama-3.3-70b-versatile",
        "GROQ_API_KEY", "https://console.groq.com/keys",
        base_url="https://api.groq.com/openai/v1", free=True,
        models=("llama-3.3-70b-versatile", "llama-3.1-8b-instant"),
    ),
    "openrouter": ProviderSpec(
        "openrouter", "openai", "meta-llama/llama-3.3-70b-instruct:free",
        "OPENROUTER_API_KEY", "https://openrouter.ai/keys",
        base_url="https://openrouter.ai/api/v1", free=True,
        models=("meta-llama/llama-3.3-70b-instruct:free", "deepseek/deepseek-chat"),
    ),
    # Google Gemini exposes an OpenAI-compatible endpoint, so it reuses
    # OpenAIProvider. Free tier + paid (Pro) models; supports function calling.
    "gemini": ProviderSpec(
        "gemini", "openai", "gemini-3.5-flash",
        "GEMINI_API_KEY", "https://aistudio.google.com/apikey",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/", free=True,
        models=("gemini-3.5-flash", "gemini-3.1-pro", "gemini-3.1-flash", "gemini-2.5-flash"),
    ),
    # Local + private + free: runs against an Ollama server on the same machine.
    # No key needed; only reachable when pi runs locally (not on cloud hosting).
    "ollama": ProviderSpec(
        "ollama", "openai", "qwen2.5-coder:7b",
        "OLLAMA_API_KEY", "https://ollama.com/download",
        base_url="http://localhost:11434/v1", free=True, requires_key=False,
        models=("qwen2.5-coder:7b", "llama3.1", "deepseek-coder"),
    ),
}


def build_provider(
    model: str,
    provider: str | None = None,
    *,
    max_tokens: int = 4096,
    thinking: bool = False,
    thinking_budget: int = 2048,
    api_key: str | None = None,
) -> LLMProvider:
    """Construct a provider for ``model`` (provider inferred unless given).

    ``api_key`` is passed straight to the vendor SDK (used by the web demo to
    run on the visitor's own key). When ``None`` the SDK reads it from the
    environment. The key is never stored or logged by pi.
    """
    chosen = provider or infer_provider(model)
    spec = PROVIDERS.get(chosen)
    kind = spec.kind if spec else ("openai" if chosen == "openai" else "anthropic")
    base_url = spec.base_url if spec else None

    # Keyless local providers (Ollama) still need a non-empty string for the SDK.
    if spec is not None and not spec.requires_key and not api_key:
        api_key = "ollama"

    if kind == "openai":
        return OpenAIProvider(model=model, api_key=api_key, base_url=base_url)
    return AnthropicProvider(
        model=model,
        max_tokens=max_tokens,
        thinking=thinking,
        thinking_budget=thinking_budget,
        api_key=api_key,
    )


def list_models(provider: str | None = None, *, api_key: str | None = None) -> list[str]:
    """Return the model ids this key can actually use (the provider's own list).

    The single source of truth — provider model ids drift, so ask the API rather
    than trusting a hardcoded list. Raises if the key/provider is unreachable.
    """
    spec = PROVIDERS.get(provider or "")
    seed = spec.default_model if spec else "x"
    client = getattr(build_provider(seed, provider, api_key=api_key), "_client", None)
    if client is None:
        return []
    return sorted({getattr(m, "id", str(m)) for m in client.models.list()})
