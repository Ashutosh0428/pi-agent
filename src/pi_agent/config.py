"""Agent configuration.

Everything tunable lives here so the rest of the code reads cleanly and new
options are easy to add later.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from pi_agent.guardrails import GuardrailConfig

DEFAULT_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You are pi, a concise terminal coding assistant. You help the user write, edit, \
and understand code in their working directory.

Guidelines:
- Use the provided tools to read and modify files and run commands. Prefer \
reading a file before editing it.
- Make the smallest change that solves the task. Do not add unrelated changes.
- When you edit a file, use the edit_file tool with an exact, unique old_string.
- After finishing, give a one or two sentence summary of what you did.
- If a request is ambiguous, ask a brief clarifying question instead of guessing.
"""


@dataclass
class AgentConfig:
    """Runtime configuration for an agent session."""

    model: str = DEFAULT_MODEL
    provider: str | None = None  # None -> inferred from the model id
    max_tokens: int = 4096
    max_iterations: int = 25  # tool-use loop safety cap
    system_prompt: str = SYSTEM_PROMPT
    enable_shell: bool = True  # expose the run_bash tool
    auto_approve: bool = False  # skip confirmation for write/edit/bash
    stream: bool = True  # stream text deltas when the provider can
    thinking: bool = False  # Anthropic extended thinking (opt-in, billed)
    thinking_budget: int = 2048  # thinking tokens when enabled
    reflect: bool = False  # one bounded self-review pass after the answer (extra tokens)
    max_retries: int = 5  # retry transient model errors (rate limit, 5xx, timeout)
    # Cap how many recent transcript messages are sent to the model, so long
    # sessions don't grow past the context window. 0 disables trimming. The full
    # transcript is still kept locally (for /cost); only the request is trimmed.
    max_history_messages: int = 80
    guardrails: GuardrailConfig = field(default_factory=GuardrailConfig)

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Build config, letting env vars override defaults."""
        return cls(
            model=os.environ.get("PI_AGENT_MODEL", DEFAULT_MODEL),
            max_tokens=int(os.environ.get("PI_AGENT_MAX_TOKENS", "4096")),
            max_iterations=int(os.environ.get("PI_AGENT_MAX_ITERS", "25")),
        )
