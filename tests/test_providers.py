"""Provider-translation tests — no API keys, no network.

These verify that one neutral transcript maps correctly to each vendor's wire
format, which is what makes pi genuinely multi-provider.
"""

from __future__ import annotations

from pi_agent.llm import (
    PROVIDERS,
    ToolCall,
    ToolResult,
    Usage,
    estimate_cost,
    infer_provider,
    to_anthropic_messages,
    to_openai_messages,
    to_openai_tools,
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
