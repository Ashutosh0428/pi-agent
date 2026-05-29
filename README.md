# pi-agent

A **minimal terminal AI coding agent** — a small, readable harness that lets an
LLM read, edit, and run code in your working directory through a tool-use loop.
Inspired by the [Pi](https://github.com/badlogic/pi-mono) philosophy: lean,
hackable, no feature bloat.

> Built as a learning + portfolio project. The core loop is ~100 lines; the
> design makes adding new tools (and later, new LLM providers) trivial.

## What it does

```
you ──prompt──► pi ──► LLM decides ──► calls tools (read/write/edit/grep/bash)
                          ▲                       │
                          └──── tool results ─────┘   (loops until done)
```

- **ReAct tool-use loop** — the model plans, calls tools, observes results, repeats.
- **Tools:** `read_file`, `write_file`, `edit_file`, `list_dir`, `grep`, `run_bash`.
- **Sandboxed:** every path is confined to the working directory; no `../` escapes.
- **Safe by default:** confirms before mutating tools (write/edit/bash) unless `--yes`.
- **Provider-agnostic core:** the loop talks to an interface, so new models slot in later.

## Install

```bash
pip install -e .
export ANTHROPIC_API_KEY=sk-ant-...
```

## Use

```bash
# Interactive REPL in the current directory
pi

# One-shot
pi "add a docstring to main.py"

# Options
pi --dir ./myproject      # set the sandbox/working directory
pi --yes                  # auto-approve mutating tools
pi --no-shell             # disable the run_bash tool
pi --model claude-opus-4-7
```

REPL commands: `/help`, `/tools`, `/reset`, `/exit`.

## Architecture

```
src/pi_agent/
  config.py        # AgentConfig + system prompt
  sandbox.py       # path-safety boundary (the security choke-point)
  llm.py           # LLMProvider interface + AnthropicProvider
  agent.py         # the tool-use loop (provider- and UI-agnostic)
  repl.py          # terminal front-end (rich)
  cli.py           # `pi` entry point
  tools/
    base.py        # Tool dataclass
    filesystem.py  # read / write / edit / list
    shell.py       # run_bash (sandboxed)
    search.py      # grep
    registry.py    # holds tools, dispatches calls
```

## Extending it (the whole point)

**Add a tool** — write a handler and a `Tool`, register it:

```python
Tool(
    name="word_count",
    description="Count words in a file.",
    input_schema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    handler=lambda args, sb: str(len(sb.resolve(args["path"]).read_text().split())),
)
```

**Add a provider** — implement `LLMProvider.complete(...)` returning an
`AssistantResponse`. The agent loop needs no changes.

## Testing

```bash
pytest          # uses a scripted fake provider — no API key required
```

Tests cover the sandbox boundary, every tool, and the agent loop (tool
execution, max-iteration guard, confirmation, event emission).

## Roadmap

- More tools (git, web fetch, apply-patch)
- Multi-provider routing (OpenAI / local) + `/model` switch
- Streaming output
- Optional web playground (file-tools only, sandboxed)

---

*Built by Ashutosh Sharma.*
