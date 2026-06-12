# pi-agent — complete usage guide

Everything from `pip install` to advanced flags, step by step. For the short
version see the [README](../README.md).

## 1 · Install

| Method | Command | Notes |
|---|---|---|
| **pipx** (recommended) | `pipx install pi-coding-agent` | isolated, `pi` on PATH |
| uv | `uv tool install pi-coding-agent` | same idea, uv-managed |
| pip | `pip install "pi-coding-agent[data]"` | `[data]` adds CSV analysis + slide generation |
| Docker | `docker build -t pi-agent . && docker run -it --rm -e GROQ_API_KEY -v "$PWD":/work pi-agent` | repo clone needed for the build |

Requires Python ≥ 3.10. Check: `pi --version`.

> pipx installed but `pi` not found? Run `pipx ensurepath`, then open a new
> terminal.

## 2 · Get an API key (pick ONE to start)

| Provider | Cost | Where | Then |
|---|---|---|---|
| **Groq** ⭐ easiest | 🆓 no card | <https://console.groq.com/keys> | `export GROQ_API_KEY=gsk_…` |
| Gemini | 🆓 no card | <https://aistudio.google.com/apikey> | `export GEMINI_API_KEY=…` |
| OpenRouter | 🆓 no card | <https://openrouter.ai/keys> | `export OPENROUTER_API_KEY=…` |
| GLM (Z.ai) | 🆓 flash model | <https://z.ai/manage-apikey/apikey-list> | `export ZAI_API_KEY=…` |
| EURI | 🆓 tier | <https://docs.euri.ai/> | `export EURI_API_KEY=…` |
| Anthropic | paid | <https://console.anthropic.com/settings/keys> | `export ANTHROPIC_API_KEY=sk-ant-…` |
| OpenAI | paid | <https://platform.openai.com/api-keys> | `export OPENAI_API_KEY=sk-…` |
| **Ollama** | 🆓 100% local | <https://ollama.com/download> | `ollama pull qwen2.5-coder:7b` — no key at all |

Put exports in your `~/.zshrc` / `~/.bashrc` to persist, or copy
`.env.example` to `.env` in your project (auto-gitignored pattern).

## 3 · First run

```bash
cd your-project
pi
```

- **A key is set** → pi auto-detects the provider (paid → best free → local
  Ollama) and opens the REPL on that provider's default model. No flags.
- **No key anywhere** → pi prints a quick-setup panel with the three free
  paths above and exits. Set one, run `pi` again.

One-shot mode (no REPL — prints the answer and exits):

```bash
pi "explain this repository"
pi "write a function that parses RFC3339 timestamps, with tests"
```

## 4 · REPL commands

| Command | Does |
|---|---|
| `/help` | list commands |
| `/tools` | list active tools |
| `/model <id>` | switch model (works mid-conversation, even across providers) |
| `/think` | toggle extended thinking (Anthropic only, billed) |
| `/cost` | session token count + estimated cost |
| `/reset` | clear the conversation |
| `/exit` | quit |

## 5 · All CLI flags

| Flag | Default | Meaning |
|---|---|---|
| `--provider <name>` | auto-detected | anthropic · openai · groq · openrouter · gemini · euri · glm · ollama |
| `--model <id>` | provider default | any model id the provider serves |
| `--dir <path>` | `.` | workspace root — the agent cannot touch files outside it |
| `--yes` | off | auto-approve mutating tools (write/edit/bash) |
| `--no-shell` | off | disable `run_bash` entirely |
| `--no-stream` | off | disable token streaming |
| `--think` | off | Anthropic extended thinking |
| `--reflect` | off | one self-review pass after the answer (see §8) |
| `--skills-dir <dir>` | none | load `SKILL.md` skills into the prompt |
| `--skills-top-k <n>` | 3 | one-shot mode: inline only the n most relevant skills (0 = all) |
| `--version` | — | print version |

## 6 · Skills

A skill is a folder with a `SKILL.md` (frontmatter + guidance). 18 are
bundled: planning, orchestrate, write-tests, code-review, security-review,
performance-review, refactor, debug, fix-ci, explain-code, explain-project,
architecture, write-docs, write-readme, commit-message, api-design,
data-analysis, make-deck.

```bash
pi --skills-dir ./skills "security-review src/auth.py"
```

**Auto-routing:** in one-shot mode pi scores skills against your prompt and
inlines only the top 3 (`--skills-top-k`); the index of all skills stays
visible to the model. The REPL inlines everything.

**Write your own:** create `myskills/<name>/SKILL.md`:

```markdown
---
name: my-skill
description: One line on what it does.
trigger: when the user asks for X
---
## How
1. …
```

No code changes — just point `--skills-dir` at it.

## 7 · Memory (persistent, per project)

The agent saves durable facts with its `remember` tool to
`.pi/memory.md` in your workspace — conventions, decisions, preferences.
Next session in the same directory, that memory is loaded back into its
context automatically: *day 5 continues where day 1 stopped.*

- Plain markdown — open it, edit it, delete lines you don't want kept.
- Capped recall (last 4 KB) — old facts age out.
- Ask for it explicitly: `pi "remember that we use pytest fixtures, never mocks"`.
- Add `.pi/` to your `.gitignore` if you don't want memory committed.

## 8 · Reflection (`--reflect`)

```bash
pi --reflect "refactor utils.py to remove the duplicated parsing logic"
```

After answering, the agent re-reads what it changed, hunts for bugs/missed
requirements, fixes real problems with tools, then restates the final answer.
One bounded pass (≤5 tool iterations). Costs extra tokens — that's why it's
opt-in.

## 9 · MCP servers (connect external tools)

pi speaks the Model Context Protocol over stdio, so any MCP server becomes a
set of pi tools. Drop a standard `mcpServers` config (same shape as Claude
Desktop / Cursor) at `.pi/mcp.json` in your project, or `~/.pi/mcp.json`
globally, or pass `--mcp-config <path>`:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_TOKEN": "ghp_…" }
    },
    "postgres": {
      "command": "uvx",
      "args": ["mcp-server-postgres", "postgresql://localhost/mydb"]
    }
  }
}
```

Run `pi`, then `/mcp` to see connected tools — they're named
`mcp__github__create_issue`, etc. MCP tools are confirmation-gated (they may
change external state). A server that fails to start is skipped with a warning,
not a crash. MCP runs in the local CLI only — the hosted web demo never spawns
subprocesses.

## 10 · Knowledge base (`pi ingest` / `pi ask`)

Turn a folder of docs into a searchable, citable knowledge base — fully offline
(no embeddings, no API calls for retrieval):

```bash
pi ingest ./docs                       # indexes .md/.txt/.rst → .pi/kb.sqlite3
pi ask "how does authentication work?" # grounded answer with [source] citations
```

In a normal `pi` chat, once a KB exists the agent gets a `search_knowledge`
tool and pulls from your docs automatically. Re-run `pi ingest` to rebuild
after the docs change. `pi ask` needs a model (for the answer); ingest and
search need no key at all.

## 11 · Guardrails (safe by default)

Deterministic safety checks run on every tool call (no LLM judge):

- **Secret exfiltration blocked** — a `web_fetch`/`run_bash`/MCP call whose
  arguments contain one of your secret-env values is refused.
- **Destructive commands confirmed** — `rm -rf /`, `curl|sh`, `sudo`, fork
  bombs, `git push --force` require confirmation *even under `--yes`*.
- **Untrusted content spotlighted** — text from `web_fetch`/MCP is wrapped so
  the model treats it as data, not instructions (prompt-injection defense).
- **Secrets redacted** — key-shaped strings are masked in tool output.

All on by default. `--no-guardrails` disables them (not recommended).

## 12 · The web app locally

```bash
git clone https://github.com/Ashutosh0428/pi-agent && cd pi-agent
pip install -r requirements.txt
streamlit run streamlit_app.py        # http://localhost:8501
```

Same BYO-key model as the hosted demo, plus: workspace file browser (view
any uploaded/created file with syntax highlighting), starter prompts, live
streaming, session cost meter, chat transcript download. Locally it can also
reach your Ollama at `localhost:11434`.

## 10 · Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `No API key found` panel | no provider key in env → §2, pick one free option |
| `pi: command not found` | pipx PATH → `pipx ensurepath`, new terminal |
| `requires a different Python: 3.9…` | Python too old → install 3.10+ (`brew install python@3.12`) |
| `model_not_found` / 404 from provider | model id wrong for that provider → `pi "list models my key supports"` or check the provider console |
| `429` / rate limit | free-tier burst limit → wait a minute; pi already retries ≤5× with backoff |
| Ollama: connection refused | server not running → `ollama serve`, and `ollama pull <model>` first |
| Tools never get called | model too weak for tool use → try `llama-3.3-70b-versatile` (Groq) or any Claude/GPT |
| Corporate proxy / SSL errors | export `HTTPS_PROXY` / `REQUESTS_CA_BUNDLE` for your proxy; vendor SDKs honor them |

## 11 · FAQ

**Is my code sent anywhere?** Only to the model provider you chose, only the
parts the agent reads. With Ollama, nothing leaves your machine.

**Where do keys live?** Environment variables only. Never written, logged, or
committed by pi.

**Can it touch files outside my project?** No — every path resolves through
a sandbox rooted at `--dir`; escapes raise an error.

**Free vs paid — what should I use?** Groq llama-3.3-70b is the best free
default for coding. Switch one flag (`--provider anthropic`) when you want
frontier reasoning.
