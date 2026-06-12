"""Command-line entry point: `pi`."""

from __future__ import annotations

import argparse
import atexit
import os
import sys

from pi_agent import __version__
from pi_agent.agent import Agent
from pi_agent.config import AgentConfig
from pi_agent.guardrails import GuardrailConfig
from pi_agent.kb import format_context, ingest, kb_exists, knowledge_tools, search
from pi_agent.llm import PROVIDERS, build_provider, detect_provider, infer_provider
from pi_agent.mcp_client import load_mcp_servers, mcp_tools, start_mcp_servers
from pi_agent.sandbox import Sandbox
from pi_agent.tools.memory import load_memory
from pi_agent.tools.registry import build_default_tools

# Which environment variable holds the key for each provider. The key itself is
# never read, printed, or stored by pi — the vendor SDK reads it from the env.
PROVIDER_ENV_KEY = {name: spec.key_env for name, spec in PROVIDERS.items()}


def resolve_selection(provider_arg: str | None, model_arg: str | None) -> tuple[str | None, str]:
    """Resolve (provider, model) from flags, env, or API-key auto-detection.

    Explicit flags win (``PI_AGENT_MODEL`` counts as an explicit model). A
    provider chosen without a model serves *that provider's* default model —
    not the global Claude default. With nothing given, auto-detect from the
    keys present in the environment; ``(None, "")`` means nothing is
    configured and the caller should show onboarding.
    """
    model = model_arg or os.environ.get("PI_AGENT_MODEL")
    if model:
        return provider_arg or infer_provider(model), model
    if provider_arg:
        return provider_arg, PROVIDERS[provider_arg].default_model
    detected = detect_provider()
    if detected is None:
        return None, ""
    return detected, PROVIDERS[detected].default_model


def _print_onboarding() -> None:
    """First-run screen: how to get a working (free) setup in under a minute."""
    from rich.console import Console
    from rich.panel import Panel

    body = (
        "[bold]No API key found.[/bold] pi works with several [bold green]free[/bold green] options:\n\n"
        "  [bold cyan]1. Groq[/bold cyan] — free key, no card, very fast\n"
        "     [dim]export GROQ_API_KEY=...[/dim]   → https://console.groq.com/keys\n"
        "  [bold cyan]2. Gemini[/bold cyan] — free key, no card\n"
        "     [dim]export GEMINI_API_KEY=...[/dim] → https://aistudio.google.com/apikey\n"
        "  [bold cyan]3. Ollama[/bold cyan] — 100% local & private, no key at all\n"
        "     [dim]ollama pull qwen2.5-coder:7b[/dim] → https://ollama.com/download\n\n"
        "Paid keys work too ([dim]ANTHROPIC_API_KEY[/dim], [dim]OPENAI_API_KEY[/dim], …).\n"
        "Set one, then just run [bold]pi[/bold] — it picks up whichever key you set."
    )
    Console(stderr=True).print(Panel(body, title="🤖 pi — quick setup", border_style="cyan"))


def _cmd_ingest(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="pi ingest", description="Build a local knowledge base.")
    p.add_argument("docs_dir", help="Directory of .md/.txt/.rst files to ingest.")
    p.add_argument("--dir", default=".", help="Workspace root (where .pi/kb.sqlite3 is written).")
    a = p.parse_args(argv)
    if not os.path.isdir(a.docs_dir):
        print(f"Error: '{a.docs_dir}' is not a directory.", file=sys.stderr)
        return 1
    stats = ingest(a.docs_dir, a.dir)
    print(
        f"Ingested {stats['files']} files → {stats['chunks']} chunks "
        f"({stats['bytes']:,} bytes) into {a.dir}/.pi/kb.sqlite3"
    )
    return 0 if stats["files"] else 1


def _cmd_ask(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="pi ask", description="Answer from the knowledge base.")
    p.add_argument("question", nargs="+", help="Your question.")
    p.add_argument("--dir", default=".", help="Workspace root (where .pi/kb.sqlite3 lives).")
    p.add_argument("--provider", choices=sorted(PROVIDER_ENV_KEY))
    p.add_argument("--model")
    a = p.parse_args(argv)
    question = " ".join(a.question)
    if not kb_exists(a.dir):
        print("No knowledge base found. Run `pi ingest <dir>` first.", file=sys.stderr)
        return 1
    hits = search(question, a.dir)
    context = format_context(hits)
    if not context:
        print("I don't find anything about that in the knowledge base.")
        return 0
    provider_name, model = resolve_selection(a.provider, a.model)
    if provider_name is None:
        _print_onboarding()
        return 1
    prov = build_provider(model, provider_name)
    grounded = (
        "Answer the question using ONLY the context below. Cite sources in [brackets]. "
        "If the context does not contain the answer, say so.\n\n"
        f"## Context\n{context}\n\n## Question\n{question}"
    )
    resp = prov.complete(
        "You are a precise, citation-grounded assistant.",
        [{"role": "user", "content": grounded}],
        [],
    )
    print(resp.text)
    return 0


def main(argv: list[str] | None = None) -> int:
    raw = sys.argv[1:] if argv is None else argv
    if raw and raw[0] == "ingest":
        return _cmd_ingest(raw[1:])
    if raw and raw[0] == "ask":
        return _cmd_ask(raw[1:])

    parser = argparse.ArgumentParser(prog="pi", description="A minimal terminal AI coding agent.")
    parser.add_argument("prompt", nargs="*", help="One-shot prompt (omit for REPL).")
    parser.add_argument("--model", help="Model id (overrides PI_AGENT_MODEL).")
    parser.add_argument(
        "--provider",
        choices=sorted(PROVIDER_ENV_KEY),
        help="LLM provider (default: inferred from the model id).",
    )
    parser.add_argument("--dir", default=".", help="Working directory (sandbox root).")
    parser.add_argument("--yes", action="store_true", help="Auto-approve mutating tools.")
    parser.add_argument("--no-shell", action="store_true", help="Disable the run_bash tool.")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming output.")
    parser.add_argument(
        "--think",
        action="store_true",
        help="Enable extended thinking (Anthropic only; uses extra billed tokens).",
    )
    parser.add_argument(
        "--reflect",
        action="store_true",
        help="After answering, run one bounded self-review pass that re-checks "
        "the work and fixes problems (uses extra tokens).",
    )
    parser.add_argument(
        "--no-guardrails",
        action="store_true",
        help="Disable safety guardrails (secret-exfiltration block, destructive-"
        "command confirmation, output redaction). Not recommended.",
    )
    parser.add_argument(
        "--skills-dir",
        help="Directory of skills (<dir>/<skill>/SKILL.md) to inline into the prompt.",
    )
    parser.add_argument(
        "--skills-top-k",
        type=int,
        default=3,
        help="One-shot mode: inline only the K most relevant skills (0 = all). "
        "The REPL always inlines all skills.",
    )
    parser.add_argument(
        "--mcp-config",
        help="Path to an mcpServers JSON config (default: .pi/mcp.json then ~/.pi/mcp.json).",
    )
    parser.add_argument("--version", action="version", version=f"pi-agent {__version__}")
    args = parser.parse_args(argv)

    config = AgentConfig.from_env()
    selected_provider, selected_model = resolve_selection(args.provider, args.model)
    if selected_provider is None:
        _print_onboarding()
        return 1
    config.provider, config.model = selected_provider, selected_model
    config.auto_approve = args.yes
    config.enable_shell = not args.no_shell
    config.stream = not args.no_stream
    config.thinking = args.think and config.provider == "anthropic"
    config.reflect = args.reflect
    if args.no_guardrails:
        config.guardrails = GuardrailConfig(enabled=False)

    if args.skills_dir:
        from pi_agent.skills import build_system_prompt, load_skills

        one_shot = " ".join(args.prompt) if args.prompt else ""
        config.system_prompt = build_system_prompt(
            config.system_prompt,
            load_skills(args.skills_dir),
            prompt=one_shot,
            top_k=args.skills_top_k if one_shot else 0,
        )

    spec = PROVIDERS[config.provider]
    if spec.requires_key and not os.environ.get(spec.key_env):
        print(
            f"Error: {spec.key_env} is not set. Export it first:\n    export {spec.key_env}=...",
            file=sys.stderr,
        )
        return 1

    provider = build_provider(
        config.model,
        config.provider,
        max_tokens=config.max_tokens,
        thinking=config.thinking,
        thinking_budget=config.thinking_budget,
    )
    # The CLI is always local/trusted, so the read-only git tool, the
    # SSRF-guarded web_fetch, and persistent memory are safe here (all are
    # left off the public demo).
    registry = build_default_tools(
        enable_shell=config.enable_shell, enable_vcs=True, enable_web=True, enable_memory=True
    )
    sandbox = Sandbox(args.dir)
    memory = load_memory(sandbox.root)
    if memory:
        config.system_prompt += (
            "\n\n## Project memory (from earlier sessions)\n"
            "Facts you saved with the remember tool — apply them without re-deriving:\n" + memory
        )

    # MCP: connect configured servers and expose their tools (CLI/local only —
    # the web demo never spawns subprocesses). A KB in the workspace adds
    # search_knowledge so the agent can pull from ingested docs.
    mcp_servers = start_mcp_servers(load_mcp_servers(args.mcp_config))
    registry.extend(mcp_tools(mcp_servers))

    def _close_mcp() -> None:
        for server in mcp_servers:
            server.close()

    atexit.register(_close_mcp)
    registry.extend(knowledge_tools(sandbox.root))

    agent = Agent(provider=provider, registry=registry, sandbox=sandbox, config=config)

    if args.prompt:
        # One-shot mode: print the final answer and exit.
        from pi_agent.repl import make_event_handler

        agent.on_event = make_event_handler()
        agent.config.auto_approve = True  # non-interactive => can't prompt
        agent.run(" ".join(args.prompt))
        return 0

    from pi_agent.repl import run_repl

    run_repl(agent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
