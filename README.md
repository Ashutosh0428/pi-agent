# pi-agent

[![CI](https://github.com/Ashutosh0428/pi-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Ashutosh0428/pi-agent/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://mj3ivlmagpfgsjpxirxbpv.streamlit.app/)

> 🚀 **[Try it live →](https://mj3ivlmagpfgsjpxirxbpv.streamlit.app/)** — bring your own key, sandboxed, no install.

A **minimal terminal AI coding agent** — a small, readable harness that lets an
LLM read, edit, and run code in your working directory through a tool-use loop.
Works with **Claude and GPT** from the same loop. Inspired by the
[Pi](https://github.com/badlogic/pi-mono) philosophy: lean, hackable, no bloat.

> Built as a learning + portfolio project. The core loop is ~120 lines; the
> transcript is provider-neutral, so adding a tool *or a model* is trivial.

## What it does

```
you ──prompt──► pi ──► LLM decides ──► calls tools (read/write/edit/grep/bash)
                          ▲                       │
                          └──── tool results ─────┘   (loops until done)
```

- **ReAct tool-use loop** — the model plans, calls tools, observes results, repeats.
- **Planner + live todos** — the model declares a step plan via the `update_plan`
  tool; the web app renders it as a live checklist (⬜→⏳→✅), Claude-Code style.
- **Multi-provider, incl. free** — **Claude**, **GPT**, and free tiers **Groq**
  (`llama-3.3-70b`) and **OpenRouter** (`…:free`) behind one interface; switch
  models *mid-conversation* with `/model` (the transcript is provider-neutral).
- **Streaming** — text streams token-by-token in the REPL (Anthropic).
- **Usage + cost** — per-turn token counts and an estimated session cost (`/cost`).
- **Extended thinking** — opt-in (`--think` / `/think`) on Anthropic.
- **Tools:** `update_plan`, `read_file`, `write_file`, `edit_file`, `list_dir`, `grep`, `run_bash`.
- **Skills** — drop a `SKILL.md` in `skills/<name>/` and its guidance is inlined
  into the system prompt (index + contents), AIOP-style. Ships with `planning`,
  `write-tests`, `code-review`, `refactor`, `debug`, `explain-code`, `write-docs`.
- **Web demo** — sandboxed, bring-your-own-key Streamlit app with file upload and
  free-model support (`streamlit_app.py`).
- **Sandboxed:** every path is confined to the working directory; no `../` escapes.
- **Safe by default:** confirms before mutating tools (write/edit/bash) unless `--yes`.

## What you can do (and why it's useful)

| You ask… | pi does | why it helps |
|---|---|---|
| *"write a function that parses a CSV, save to `csv.py`, add a test"* | plans → `write_file` → `write_file` | scaffolds working code + tests in one go |
| *"review `<uploaded file>`"* | reads it → returns prioritised findings | a second pair of eyes, on your own key |
| *"there's a bug in `x.py`, the output is wrong — fix it"* | reads, diagnoses root cause, `edit_file` | fixes the cause, not the symptom |
| *"refactor `y.py` to be simpler, don't change behaviour"* | small, safe `edit_file`s | cleanup without regressions |
| *"explain what `z.py` does"* | reads + walks the logic | onboard to unfamiliar code fast |

It's a **transparent** agent: you see the plan, every tool call, and the token
cost — nothing hidden. Try it free with a Groq/OpenRouter key, then point it at
your own code (locally, with shell + full tools enabled).

## Install

```bash
pip install -e .              # Anthropic + core
pip install -e ".[openai]"    # add OpenAI / Groq / OpenRouter (all OpenAI-compatible)

cp .env.example .env          # then fill in your key(s)
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
# free tiers (no credit card):
export GROQ_API_KEY=...         # https://console.groq.com/keys
export OPENROUTER_API_KEY=...   # https://openrouter.ai/keys
```

> **Keys never touch the repo.** pi reads them from the environment only — they
> are never stored or logged, `.env` is gitignored, and `.env.example` holds
> placeholders only.

## Use

```bash
# Interactive REPL in the current directory
pi

# One-shot
pi "add a docstring to main.py"

# Options
pi --dir ./myproject          # set the sandbox/working directory
pi --yes                      # auto-approve mutating tools
pi --no-shell                 # disable the run_bash tool
pi --no-stream                # disable streaming
pi --model gpt-4o-mini        # provider inferred from the model id
pi --provider openai --model gpt-4o
pi --provider groq --model llama-3.3-70b-versatile         # free tier
pi --provider openrouter --model "meta-llama/llama-3.3-70b-instruct:free"
pi --skills-dir ./skills      # load the bundled skills
pi --think                    # Anthropic extended thinking (uses extra billed tokens)
```

REPL commands: `/help`, `/tools`, `/model <id>`, `/think`, `/cost`, `/reset`, `/exit`.

## Architecture

```
src/pi_agent/
  config.py        # AgentConfig + system prompt
  sandbox.py       # path-safety boundary (the security choke-point)
  llm.py           # neutral transcript <-> Anthropic / OpenAI; Usage + cost
  agent.py         # the tool-use loop (provider- and UI-agnostic)
  skills.py        # load SKILL.md files, inline them into the system prompt
  repl.py          # terminal front-end (rich): streaming, /model, /cost, /think
  cli.py           # `pi` entry point
  tools/
    base.py        # Tool dataclass (neutral tool spec)
    filesystem.py  # read / write / edit / list
    shell.py       # run_bash (sandboxed)
    search.py      # grep
    registry.py    # holds tools, dispatches calls
streamlit_app.py   # public web demo (BYO key, no shell, temp sandbox)
skills/            # write-tests/ · code-review/ · refactor/  (SKILL.md each)
```

The agent keeps its transcript in a **provider-neutral** shape
(`user` / `assistant` / `tool`); each provider translates it to its own wire
format (Anthropic content blocks vs OpenAI `tool_calls`). That seam is what lets
the same conversation move between Claude and GPT.

## Web demo (Streamlit)

`streamlit_app.py` is a public-safe slice of pi you can host for free:

- **Bring your own key** — the visitor pastes their Anthropic/OpenAI key; it is
  used only for that session and **never stored, logged, or committed**.
- **No shell** — `run_bash` is disabled, so visitors can't run commands on the host.
- **Sandboxed** — file tools are confined to a fresh temp directory per session.

Run locally:

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Deploy on **Streamlit Community Cloud**: push to GitHub → [share.streamlit.io](https://share.streamlit.io)
→ pick this repo, main file `streamlit_app.py` → Deploy. No secrets to configure —
keys are entered in the UI at runtime.

## Skills

A *skill* is a `SKILL.md` describing how to do one task well. At startup pi inlines
a skill index + contents into the system prompt, so the model can apply them
without spending a tool call to read them.

```
skills/<name>/SKILL.md   # frontmatter: name, description, trigger + the guidance
```

```bash
pi --skills-dir ./skills "review llm.py"   # CLI loads skills from a directory
```

Bundled: `planning`, `write-tests`, `code-review`, `refactor`, `debug`,
`explain-code`, `write-docs`. Add your own by dropping a new folder — no code changes.

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

**Add a provider** — implement `LLMProvider.complete(...)` (translate the neutral
transcript, call the API, return an `AssistantResponse`). The agent loop needs no
changes.

## Testing

```bash
pytest          # uses a scripted fake provider — no API key, no network
```

Tests cover the sandbox boundary, every tool, the agent loop (tool execution,
max-iteration guard, confirmation, events, usage accounting), and the
**provider translators** (neutral → Anthropic / OpenAI).

## Notes on cost

`/cost` and the per-turn line show **estimated** USD from an editable price table
in `llm.py` — treat them as ballpark, not billing. Extended thinking (`--think`)
spends extra tokens, so it is **off by default**.

## Roadmap

- More tools (git, web fetch, apply-patch)
- OpenAI streaming (Anthropic streams today; OpenAI uses full-response)
- Skill triggers / auto-selection by relevance

---

*Built by Ashutosh Sharma.*
