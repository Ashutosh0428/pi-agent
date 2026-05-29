"""Terminal REPL front-end.

Renders the agent's events with `rich` and handles a few slash commands. All
agent logic lives in :class:`Agent`; this file is purely presentation + input.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from pi_agent.agent import Agent
from pi_agent.llm import ToolCall

console = Console()

HELP = """\
Commands:
  /help     show this help
  /tools    list available tools
  /reset    clear the conversation
  /exit     quit
Anything else is sent to the agent.
"""


def _make_event_handler():
    def on_event(kind: str, payload) -> None:
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
        elif kind == "info":
            console.print(f"[yellow]{payload}[/yellow]")

    return on_event


def _fmt_args(args: dict) -> str:
    parts = []
    for key, value in args.items():
        text = str(value).replace("\n", " ")
        if len(text) > 40:
            text = text[:40] + "…"
        parts.append(f"{key}={text!r}")
    return ", ".join(parts)


def _confirm(call: ToolCall) -> bool:
    answer = console.input(
        f"[yellow]Run mutating tool [bold]{call.name}[/bold]? [y/N][/yellow] "
    )
    return answer.strip().lower() in {"y", "yes"}


def run_repl(agent: Agent) -> None:
    """Start the interactive loop."""
    agent.on_event = _make_event_handler()
    if agent.confirm is None and not agent.config.auto_approve:
        agent.confirm = _confirm

    console.print(
        Panel.fit(
            "pi — minimal coding agent. Type /help for commands, /exit to quit.",
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
        if user_input == "/reset":
            agent.reset()
            console.print("[dim]conversation cleared[/dim]")
            continue

        try:
            agent.run(user_input)
        except Exception as exc:  # keep the REPL alive on errors
            console.print(f"[red]Error: {exc}[/red]")
