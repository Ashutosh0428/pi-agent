"""Terminal REPL front-end.

Renders the agent's events with `rich` and handles a few slash commands. All
agent logic lives in :class:`Agent`; this file is purely presentation, input,
and session controls (switch model, toggle thinking, show cost).
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from pi_agent.agent import Agent
from pi_agent.llm import ToolCall, Usage, build_provider, estimate_cost, infer_provider

console = Console()

HELP = """\
Commands:
  /help            show this help
  /tools           list available tools
  /model <id>      switch model (keeps the conversation; can cross providers)
  /think           toggle Anthropic extended thinking (uses extra billed tokens)
  /cost            show token usage and estimated cost this session
  /reset           clear the conversation
  /exit            quit
Anything else is sent to the agent.
"""


def _fmt_args(args: dict) -> str:
    parts = []
    for key, value in args.items():
        text = str(value).replace("\n", " ")
        if len(text) > 40:
            text = text[:40] + "…"
        parts.append(f"{key}={text!r}")
    return ", ".join(parts)


def _usage_line(model: str, turn: Usage) -> str:
    cost = estimate_cost(model, turn)
    base = f"· {turn.input_tokens}+{turn.output_tokens} tok"
    return f"{base}, ~${cost:.4f}" if cost is not None else base


def make_event_handler(agent: Agent | None = None):
    """Build an event handler. Pass ``agent`` to show cost using its model."""
    state = {"streaming": False}

    def close_stream() -> None:
        if state["streaming"]:
            console.print()  # end the streamed line
            state["streaming"] = False

    def on_event(kind: str, payload) -> None:
        if kind == "assistant_delta":
            if not state["streaming"]:
                console.print("[bold cyan]pi[/bold cyan] ", end="")
                state["streaming"] = True
            console.print(payload, end="", markup=False, highlight=False)
            return

        close_stream()  # any non-delta event ends the streamed line

        if kind == "assistant_text":
            if payload.strip():
                console.print(Panel(payload, title="pi", border_style="cyan"))
        elif kind == "tool_call":
            call: ToolCall = payload
            console.print(f"[dim]→ {call.name}({_fmt_args(call.args)})[/dim]")
        elif kind == "tool_result":
            output = payload["output"]
            preview = output if len(output) < 800 else output[:800] + " …"
            console.print(f"[dim]{preview}[/dim]")
        elif kind == "usage":
            model = agent.config.model if agent is not None else ""
            console.print(f"[dim]{_usage_line(model, payload['turn'])}[/dim]")
        elif kind == "info":
            console.print(f"[yellow]{payload}[/yellow]")

    return on_event


def _confirm(call: ToolCall) -> bool:
    answer = console.input(f"[yellow]Run mutating tool [bold]{call.name}[/bold]? [y/N][/yellow] ")
    return answer.strip().lower() in {"y", "yes"}


def _switch_model(agent: Agent, model: str) -> None:
    model = model.strip()
    if not model:
        console.print("[yellow]usage: /model <model-id>[/yellow]")
        return
    provider_name = infer_provider(model)
    agent.config.model = model
    agent.config.provider = provider_name
    agent.config.thinking = agent.config.thinking and provider_name == "anthropic"
    agent.provider = build_provider(
        model,
        provider_name,
        max_tokens=agent.config.max_tokens,
        thinking=agent.config.thinking,
        thinking_budget=agent.config.thinking_budget,
    )
    console.print(f"[dim]model → {model} ({provider_name}); conversation kept[/dim]")


def _toggle_thinking(agent: Agent) -> None:
    if agent.config.provider != "anthropic":
        console.print("[yellow]thinking is Anthropic-only[/yellow]")
        return
    agent.config.thinking = not agent.config.thinking
    agent.provider = build_provider(
        agent.config.model,
        "anthropic",
        max_tokens=agent.config.max_tokens,
        thinking=agent.config.thinking,
        thinking_budget=agent.config.thinking_budget,
    )
    s = "on (uses extra billed tokens)" if agent.config.thinking else "off"
    console.print(f"[dim]thinking {s}[/dim]")


def _show_cost(agent: Agent) -> None:
    total = agent.total_usage
    cost = estimate_cost(agent.config.model, total)
    line = (
        f"session: {total.input_tokens} in + {total.output_tokens} out "
        f"= {total.total_tokens} tokens"
    )
    if cost is not None:
        line += f"  (~${cost:.4f} at {agent.config.model} rates)"
    console.print(f"[cyan]{line}[/cyan]")


def run_repl(agent: Agent) -> None:
    """Start the interactive loop."""
    agent.on_event = make_event_handler(agent)
    if agent.confirm is None and not agent.config.auto_approve:
        agent.confirm = _confirm

    console.print(
        Panel.fit(
            f"pi — minimal coding agent ({agent.config.model}).\n"
            "Type /help for commands, /exit to quit.",
            border_style="green",
        )
    )

    while True:
        try:
            user_input = console.input("[bold green]›[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nbye")
            return

        if not user_input:
            continue
        if user_input in {"/exit", "/quit"}:
            console.print("bye")
            return
        if user_input == "/help":
            console.print(HELP)
            continue
        if user_input == "/tools":
            console.print(", ".join(agent.registry.names()))
            continue
        if user_input.startswith("/model"):
            _switch_model(agent, user_input[len("/model") :])
            continue
        if user_input == "/think":
            _toggle_thinking(agent)
            continue
        if user_input == "/cost":
            _show_cost(agent)
            continue
        if user_input == "/reset":
            agent.reset()
            console.print("[dim]conversation cleared[/dim]")
            continue

        try:
            agent.run(user_input)
        except Exception as exc:  # keep the REPL alive on errors
            console.print(f"[red]Error: {exc}[/red]")
