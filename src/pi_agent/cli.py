"""Command-line entry point: `pi`."""

from __future__ import annotations

import argparse
import os
import sys

from pi_agent.agent import Agent
from pi_agent.config import AgentConfig
from pi_agent.llm import AnthropicProvider
from pi_agent.sandbox import Sandbox
from pi_agent.tools.registry import build_default_tools


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pi", description="A minimal terminal AI coding agent."
    )
    parser.add_argument("prompt", nargs="*", help="One-shot prompt (omit for REPL).")
    parser.add_argument("--model", help="Model id (overrides PI_AGENT_MODEL).")
    parser.add_argument("--dir", default=".", help="Working directory (sandbox root).")
    parser.add_argument("--yes", action="store_true", help="Auto-approve mutating tools.")
    parser.add_argument("--no-shell", action="store_true", help="Disable the run_bash tool.")
    args = parser.parse_args(argv)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "Error: ANTHROPIC_API_KEY is not set. Export it first:\n"
            "    export ANTHROPIC_API_KEY=sk-ant-...",
            file=sys.stderr,
        )
        return 1

    config = AgentConfig.from_env()
    if args.model:
        config.model = args.model
    config.auto_approve = args.yes
    config.enable_shell = not args.no_shell

    provider = AnthropicProvider(model=config.model, max_tokens=config.max_tokens)
    registry = build_default_tools(enable_shell=config.enable_shell)
    sandbox = Sandbox(args.dir)
    agent = Agent(provider=provider, registry=registry, sandbox=sandbox, config=config)

    if args.prompt:
        # One-shot mode: print the final answer and exit.
        from pi_agent.repl import _make_event_handler

        agent.on_event = _make_event_handler()
        agent.config.auto_approve = True  # non-interactive => can't prompt
        agent.run(" ".join(args.prompt))
        return 0

    from pi_agent.repl import run_repl

    run_repl(agent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
