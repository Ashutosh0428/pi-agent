"""Provider-translation tests — no API keys, no network.

These verify that one neutral transcript maps correctly to each vendor's wire
format, which is what makes pi genuinely multi-provider.
"""

from __future__ import annotations

from types import SimpleNamespace

from pi_agent.llm import (
    PROVIDERS,
    OpenAIProvider,
    ToolCall,
    ToolResult,
    Usage,
    estimate_cost,
    infer_provider,
    to_anthropic_messages,
    to_openai_messages,
    to_openai_tools,
)


def _text_chunk(content: str | None = None, finish: str | None = None):
    """A streaming chunk carrying a text delta (and optional finish_reason)."""
    delta = SimpleNamespace(content=content, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=finish)], usage=None)


def _tool_chunk(index, *, id=None, name=None, arguments=None, finish=None):
    """A streaming chunk carrying one tool-call fragment."""
    fn = SimpleNamespace(name=name, arguments=arguments)
    tc = SimpleNamespace(index=index, id=id, function=fn)
    delta = SimpleNamespace(content=None, tool_calls=[tc])
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=finish)], usage=None)


def _usage_chunk(prompt, completion):
    """The trailing usage-only chunk (no choices) emitted with include_usage."""
    return SimpleNamespace(
        choices=[], usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion)
    )


# A small transcript: user -> assistant calls a tool -> tool result -> user.
TRANSCRIPT = [
    {"role": "user", "content": "list files"},
    {
        "role": "assistant",
        "content": "I'll list them.",
        "tool_calls": [ToolCall("call_1", "list_dir", {"path": "."})],
    },
    {"role": "tool", "results": [ToolResult("call_1", "list_dir", "a.py\nb.py")]},
    {"role": "user", "content": "thanks"},
]

NEUTRAL_TOOLS = [
    {
        "name": "list_dir",
        "description": "List a directory.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    }
]


class TestAnthropicTranslation:
    def test_assistant_tool_use_block(self):
        msgs = to_anthropic_messages(TRANSCRIPT)
        assistant = msgs[1]
        assert assistant["role"] == "assistant"
        kinds = [b["type"] for b in assistant["content"]]
        assert kinds == ["text", "tool_use"]
        assert assistant["content"][1]["id"] == "call_1"
        assert assistant["content"][1]["input"] == {"path": "."}

    def test_tool_result_becomes_user_block(self):
        msgs = to_anthropic_messages(TRANSCRIPT)
        tool_msg = msgs[2]
        assert tool_msg["role"] == "user"
        block = tool_msg["content"][0]
        assert block["type"] == "tool_result"
        assert block["tool_use_id"] == "call_1"
        assert block["content"] == "a.py\nb.py"


class TestOpenAITranslation:
    def test_system_prepended(self):
        msgs = to_openai_messages("SYS", TRANSCRIPT)
        assert msgs[0] == {"role": "system", "content": "SYS"}

    def test_assistant_tool_calls_shape(self):
        msgs = to_openai_messages("SYS", TRANSCRIPT)
        assistant = msgs[2]  # after system + user
        assert assistant["role"] == "assistant"
        tc = assistant["tool_calls"][0]
        assert tc["id"] == "call_1"
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "list_dir"
        # arguments must be a JSON string for OpenAI
        assert tc["function"]["arguments"] == '{"path": "."}'

    def test_tool_result_is_role_tool(self):
        msgs = to_openai_messages("SYS", TRANSCRIPT)
        tool_msg = next(m for m in msgs if m["role"] == "tool")
        assert tool_msg["tool_call_id"] == "call_1"
        assert tool_msg["content"] == "a.py\nb.py"

    def test_tools_wrapped_as_function(self):
        wrapped = to_openai_tools(NEUTRAL_TOOLS)
        assert wrapped[0]["type"] == "function"
        fn = wrapped[0]["function"]
        assert fn["name"] == "list_dir"
        assert fn["parameters"]["required"] == ["path"]


class TestOpenAIStreaming:
    """The chunk-assembly logic — pure, so testable without the SDK or network."""

    def test_text_deltas_forwarded_and_assembled(self):
        seen: list[str] = []
        resp = OpenAIProvider._consume_stream(
            [_text_chunk("Hel"), _text_chunk("lo"), _text_chunk(finish="stop")],
            seen.append,
        )
        assert seen == ["Hel", "lo"]  # streamed live, in order
        assert resp.text == "Hello"
        assert resp.stop_reason == "stop"
        assert resp.tool_calls == []

    def test_tool_call_fragments_reassembled(self):
        # id, name, then arguments split across chunks — all under index 0.
        chunks = [
            _tool_chunk(0, id="call_1", name="list_dir"),
            _tool_chunk(0, arguments='{"pa'),
            _tool_chunk(0, arguments='th": "."}', finish="tool_calls"),
        ]
        resp = OpenAIProvider._consume_stream(chunks, lambda _: None)
        assert resp.text == ""
        assert len(resp.tool_calls) == 1
        call = resp.tool_calls[0]
        assert call.id == "call_1"
        assert call.name == "list_dir"
        assert call.args == {"path": "."}  # parsed only after the stream ends

    def test_two_parallel_tool_calls_kept_separate(self):
        chunks = [
            _tool_chunk(0, id="a", name="read_file", arguments='{"path":"x"}'),
            _tool_chunk(1, id="b", name="read_file", arguments='{"path":"y"}'),
        ]
        resp = OpenAIProvider._consume_stream(chunks, lambda _: None)
        assert [c.id for c in resp.tool_calls] == ["a", "b"]
        assert [c.args["path"] for c in resp.tool_calls] == ["x", "y"]

    def test_usage_only_final_chunk(self):
        resp = OpenAIProvider._consume_stream(
            [_text_chunk("hi"), _usage_chunk(12, 3)], lambda _: None
        )
        assert resp.usage == Usage(12, 3)

    def test_malformed_tool_args_coerced_to_empty(self):
        resp = OpenAIProvider._consume_stream(
            [_tool_chunk(0, id="c", name="t", arguments="null")], lambda _: None
        )
        assert resp.tool_calls[0].args == {}

    def test_openai_provider_advertises_streaming(self):
        assert OpenAIProvider.supports_streaming is True
        assert hasattr(OpenAIProvider, "stream")


class TestProviderInference:
    def test_infers_openai(self):
        assert infer_provider("gpt-4o-mini") == "openai"
        assert infer_provider("o4-mini") == "openai"

    def test_infers_anthropic(self):
        assert infer_provider("claude-sonnet-4-6") == "anthropic"


class TestCost:
    def test_known_model_cost(self):
        # 1M in + 1M out on sonnet ($3 + $15).
        cost = estimate_cost("claude-sonnet-4-6", Usage(1_000_000, 1_000_000))
        assert cost == 18.0

    def test_unknown_model_returns_none(self):
        assert estimate_cost("some-local-model", Usage(100, 100)) is None

    def test_fable_5_priced(self):
        assert estimate_cost("claude-fable-5", Usage(1_000_000, 0)) == 15.0

    def test_gemini_flash_priced_not_confused_with_pro(self):
        # The flash key must match flash, not the pro entry listed before it.
        assert estimate_cost("gemini-3.5-flash", Usage(1_000_000, 0)) == 0.075

    def test_free_model_is_zero(self):
        assert estimate_cost("meta-llama/llama-3.3-70b-instruct:free", Usage(100, 100)) == 0.0


class TestProviderRegistry:
    def test_free_tiers_present(self):
        assert PROVIDERS["groq"].free is True
        assert PROVIDERS["openrouter"].free is True
        assert PROVIDERS["groq"].base_url.endswith("/openai/v1")
        assert PROVIDERS["openrouter"].kind == "openai"

    def test_paid_providers_have_no_base_url(self):
        assert PROVIDERS["anthropic"].free is False
        assert PROVIDERS["anthropic"].base_url is None
        assert PROVIDERS["openai"].base_url is None

    def test_every_provider_has_a_key_env(self):
        assert all(s.key_env for s in PROVIDERS.values())
