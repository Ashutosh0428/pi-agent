<h1 align="center">🤖 pi-agent</h1>

<p align="center">
  <em>Open-source AI coding agent with <b>persistent memory</b>, <b>self-review</b>, and autonomous tool-use —<br/>
  any model (Claude · GPT · free tiers · local Ollama), skills, sub-agents, data → slides.<br/>
  Minimal and transparent: you see every tool call, and the whole core fits in your head.</em>
</p>

<p align="center">
  <a href="https://github.com/Ashutosh0428/pi-agent/actions/workflows/ci.yml"><img src="https://github.com/Ashutosh0428/pi-agent/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/pi-coding-agent/"><img src="https://img.shields.io/pypi/v/pi-coding-agent" alt="PyPI"></a>
  <a href="https://pypi.org/project/pi-coding-agent/"><img src="https://img.shields.io/pypi/dm/pi-coding-agent" alt="Downloads"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT"></a>
  <a href="https://mj3ivlmagpfgsjpxirxbpv.streamlit.app/"><img src="https://static.streamlit.io/badges/streamlit_badge_black_white.svg" alt="Open in Streamlit"></a>
</p>

<p align="center">
  <b><a href="https://mj3ivlmagpfgsjpxirxbpv.streamlit.app/">🚀 Try it live</a></b> &nbsp;·&nbsp;
  <a href="#-install">Install</a> &nbsp;·&nbsp;
  <a href="docs/USAGE.md">📖 Usage guide</a> &nbsp;·&nbsp;
  <a href="#-skills">Skills</a> &nbsp;·&nbsp;
  <a href="#-architecture">Architecture</a> &nbsp;·&nbsp;
  <a href="ROADMAP.md">Roadmap</a>
</p>

---

<p align="center">
  <a href="https://mj3ivlmagpfgsjpxirxbpv.streamlit.app/"><img src="docs/assets/web-demo.png" alt="pi-agent web demo — free Groq default, BYO key" width="85%"></a>
</p>

pi lets an LLM **read, edit, and run code** in your working directory through a
tool-use loop — and shows you everything it does. It speaks to **Claude, GPT,
free models (Groq · OpenRouter · Gemini), and local Ollama** through one
provider-neutral core. Inspired by the [Pi](https://github.com/badlogic/pi-mono)
philosophy: lean, hackable, no bloat.

> Built as a learning + portfolio project. The core loop is ~150 lines; the
> transcript is provider-neutral, so adding a tool *or a model* is trivial.

## 🔁 How it works

```mermaid
flowchart TD
    U(["🧑 You — prompt"]) --> AG["🤖 Agent loop"]
    AG -->|"ask (+ tools + skills)"| LLM{{"LLM"}}
    LLM -->|"tool calls"| T["🔧 Run tools"]
    T -->|"results"| AG
    LLM -->|"no more tools"| OUT(["✅ Answer + live plan + token cost"])
    AG -. "retry transient errors (≤5×)" .-> LLM
```

The model plans, calls tools, observes the results, and repeats until done —
streaming text, a live to-do checklist, and the running token cost as it goes.

## ✨ Features

| | |
|---|---|
| 🧠 **Multi-provider** | Claude · GPT · **Groq** · **OpenRouter** · **Gemini** · **EURI** · **GLM** (free) · **Ollama** (local, no key) — switch mid-chat with `/model`; bare `pi` auto-detects from your env keys |
| 🧬 **Persistent memory** | the agent saves project facts to `.pi/memory.md` (`remember` tool) and recalls them next session — day 5 continues day 1 |
| 🔍 **Self-review** | `--reflect`: after answering, one bounded pass that re-checks the work and fixes real problems |
| 🎯 **Skill routing** | only the most relevant skills are inlined per prompt — leaner prompts, better adherence, cheaper free tiers |
| 📋 **Planner + live todos** | declares a plan via `update_plan`; the web app renders a live ⬜→⏳→✅ checklist |
| 🤝 **Sub-agents** | `delegate` a focused subtask to a sequential sub-agent (no recursion) for big jobs |
| 📦 **Project ZIP upload** | drop a zipped repo (zip-slip-safe) → *"explain this project"* (purpose, flow, components) |
| 📊 **Data analysis** | `analyze_data` profiles a CSV/Excel like a data scientist (stats, missing %, correlations) |
| 📑 **Slide generation** | `make_slides` builds a downloadable `.pptx` from an outline |
| 🔁 **Resilient** | transient errors (429/5xx/timeout) auto-retry ≤5× w/ jittered backoff; bad key/request fail fast; long sessions trim history to fit the context window |
| 🌊 **Streaming + cost** | token-by-token streaming on **every** provider (Anthropic + all OpenAI-compatible), per-turn token counts, estimated session cost (`/cost`) |
| 🔧 **git + web** | read-only `git` inspection and an SSRF-guarded `web_fetch`, locally |
| 📜 **Skills** | `SKILL.md` files inlined into the prompt — 12 bundled, add your own with zero code |
| 🔒 **Sandboxed & safe** | paths confined to the workspace; public web demo runs no raw shell |

**Tools:** `update_plan` · `delegate` · `remember` (persistent memory, local) ·
`read_file` · `write_file` · `edit_file` · `apply_patch` (atomic multi-file) ·
`list_dir` · `grep` · `git` (read-only, local) · `web_fetch` (SSRF-guarded, local) ·
`run_command` (restricted, public-safe) · `run_bash` (full shell, local only) ·
`analyze_data` · `make_slides`.

## 🚀 Install

```bash
pipx install pi-coding-agent        # recommended for the CLI
uv tool install pi-coding-agent     # or with uv
pip install "pi-coding-agent[data]" # or plain pip (+ data analysis & slides)
```

(For hacking on it: `git clone https://github.com/Ashutosh0428/pi-agent && cd pi-agent && pip install -e ".[data,dev]"` — see [CONTRIBUTING.md](CONTRIBUTING.md).)

**No key? Just run `pi`.** It auto-detects whichever provider key you've set —
and with none at all it shows a quick-setup panel with three free paths (Groq,
Gemini, Ollama) instead of an error.

Pick a provider and set its key (env var, or `cp .env.example .env`):

| Provider | Cost | Setup |
|---|---|---|
| Anthropic | paid | `export ANTHROPIC_API_KEY=sk-ant-...` |
| OpenAI | paid | `export OPENAI_API_KEY=sk-...` |
| Groq | 🆓 free | `export GROQ_API_KEY=...` · [get a key](https://console.groq.com/keys) |
| OpenRouter | 🆓 free | `export OPENROUTER_API_KEY=...` · [get a key](https://openrouter.ai/keys) |
| Gemini | 🆓 free + paid | `export GEMINI_API_KEY=...` · [get a key](https://aistudio.google.com/apikey) |
| EURI | 🆓 free | `export EURI_API_KEY=...` · [get a key](https://docs.euri.ai/) · 40+ models (OpenAI-compatible) |
| GLM (Z.ai) | 🆓 free + paid | `export ZAI_API_KEY=...` · [get a key](https://z.ai/manage-apikey/apikey-list) · `glm-4.5-flash` free, `glm-5.1` paid |
| **Ollama** | 🆓 local, no key | install Ollama → `ollama pull llama3.1` (runs at `localhost:11434`) |

**Any model works** — the web app has a per-provider model dropdown (+ a custom
field), and `--model` takes any id the provider offers, free or paid:
`gemini-3.5-flash` (free) / `gemini-3.1-pro` (paid), `gpt-4o-mini` / `gpt-4o`,
`claude-sonnet-4-6` / `claude-opus-4-8`, `llama-3.3-70b-versatile`, etc.

```bash
pi                                                          # REPL — provider auto-detected from your env keys
pi "explain this repo"                                      # one-shot, same auto-detection
pi --provider groq --model llama-3.3-70b-versatile "explain this repo"
pi --provider gemini --model gemini-3.5-flash "summarise what this project does"  # free
pi --provider gemini --model gemini-3.1-pro  "deep-review this module"             # paid (student Pro)
pi --provider ollama --model qwen2.5-coder:7b "write a string-reverse fn and a test"
pi --skills-dir ./skills "review src/pi_agent/llm.py"
pi --reflect "refactor utils.py, keep behavior identical"   # + one self-review pass
pi "remember that this repo uses pytest fixtures, never mocks"  # persists to .pi/memory.md
pi --no-shell                                               # safe mode (disable run_bash)
```

REPL commands: `/help` · `/tools` · `/model <id>` · `/think` · `/cost` · `/reset` · `/exit`.
Flags: `--provider` · `--model` · `--dir` · `--yes` · `--no-shell` · `--no-stream` · `--think` · `--skills-dir` · `--version`.

### 🐳 Docker

```bash
docker build -t pi-agent .
docker run -it --rm -e GROQ_API_KEY -v "$PWD":/work pi-agent "explain this repo"
```

> **Keys never touch the repo** — read from the environment only, never stored or
> logged; `.env` is gitignored.

### 🖥️ Why Ollama instead of a cloud AI tool (Copilot / ChatGPT / Cursor)?

- 🔒 **Private** — your code never leaves your machine. Ideal for proprietary/regulated code you can't paste into a cloud tool.
- 💸 **Free, no limits** — no key, no per-token bill, no rate limits, no subscription.
- 📴 **Offline** — works on a plane or air-gapped network.
- ⚖️ **Honest trade-off** — local models are smaller/slower than frontier Claude/GPT; great for everyday review/refactor, switch to a cloud model (one flag) for the hardest reasoning.

## 🌐 Web demo

A public-safe slice of pi ([live](https://mj3ivlmagpfgsjpxirxbpv.streamlit.app/)) — or run it yourself:

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py      # http://localhost:8501
```

- **Free by default** — opens on Groq (🆓 key, no card); one-click **starter prompts** on an empty chat.
- **Live streaming** — the answer renders token by token while tool steps stay visible.
- **Bring your own key** — used only for the session; never stored, logged, or committed.
- **No raw shell** — visitors get `run_command` (read-only allowlist, no network, sandboxed) instead of `run_bash`.
- **Upload a file, a project `.zip`, or a CSV** — then *review*, *explain the project*, or *analyze the data and make a deck*.
- **Sandboxed** — file tools + ZIP extraction confined to a fresh per-session temp dir (zip-slip-guarded).

Locally the web app can also reach **Ollama**; the hosted demo can't (no localhost
Ollama on the cloud server).

## 🧩 Architecture

```mermaid
flowchart LR
    CLI["💻 CLI / REPL"] --> AG
    WEB["🌐 Streamlit<br/>(BYO key)"] --> AG
    AG["🤖 Agent<br/>provider/UI-agnostic<br/>neutral transcript + retry"]
    AG --> P["🧠 Providers<br/>Claude · GPT · Groq · OpenRouter<br/>Gemini · EURI · GLM · Ollama"]
    AG --> T["🔧 Tools<br/>plan · fs · grep · delegate · git · web_fetch<br/>run_command · run_bash<br/>analyze_data · make_slides"]
    AG --> S["📜 Skills<br/>SKILL.md inlined"]
    T --> SB["🔒 Sandbox<br/>path-confined workspace"]
```

```
src/pi_agent/
  config.py        # AgentConfig + system prompt
  sandbox.py       # path-safety boundary (the security choke-point)
  llm.py           # provider registry + neutral transcript ↔ each wire format; usage/cost
  agent.py         # the tool-use loop: ReAct, retry, delegate (provider/UI-agnostic)
  skills.py        # load SKILL.md files, inline them into the system prompt
  upload.py        # zip-slip-safe project extraction
  repl.py          # terminal front-end (rich): streaming, /model, /cost, /think
  cli.py           # `pi` entry point
  tools/
    base.py registry.py        # Tool spec + dispatch
    planning.py                # update_plan (live todos)
    filesystem.py search.py    # read/write/edit/list + grep
    _subprocess.py             # shared path-guard + confined runner
    shell.py safe_exec.py      # run_bash (local) + run_command (public-safe)
    vcs.py web.py              # git (read-only) + web_fetch (SSRF-guarded)
    subagent.py                # delegate
    datasci.py                 # analyze_data + make_slides
streamlit_app.py   # public web demo (BYO key, no shell, temp sandbox)
skills/            # 12 SKILL.md skills
```

The agent keeps its transcript **provider-neutral** (`user` / `assistant` /
`tool`); each provider translates it to its own wire format (Anthropic content
blocks vs OpenAI `tool_calls`). That single seam is what lets one conversation
move between Claude, GPT, Groq, OpenRouter, and Ollama — even mid-chat.

## 📜 Skills

A *skill* is a `SKILL.md` describing how to do one task well; pi inlines a skill
index + contents into the system prompt, so the model applies them without
spending a tool call to read them.

```
skills/<name>/SKILL.md   # frontmatter (name, description, trigger) + When / How / Avoid / Done-well
```

Bundled (18): `planning` · `orchestrate` · `write-tests` · `code-review` ·
`security-review` · `performance-review` · `refactor` · `debug` · `fix-ci` ·
`explain-code` · `explain-project` · `architecture` · `write-docs` ·
`write-readme` · `commit-message` · `api-design` · `data-analysis` ·
`make-deck`. Add your own by dropping a new folder — no code changes.

**Auto-routing:** pi scores skills against your prompt and inlines only the
top 3 in full (the index of all 18 stays visible) — leaner prompts, cheaper
free tiers. `--skills-top-k 0` restores inline-everything.

## 🛠️ Extending it (the whole point)

**Add a tool** — write a handler + a `Tool`, register it:

```python
Tool(
    name="word_count",
    description="Count words in a file.",
    input_schema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    handler=lambda args, sb: str(len(sb.resolve(args["path"]).read_text().split())),
)
```

**Add a provider** — implement `LLMProvider.complete(...)` (translate the neutral
transcript, call the API, return an `AssistantResponse`). The agent loop is unchanged.

## ✅ Testing

```bash
pytest          # 136 tests — scripted fake provider, no API key, no network
```

Covers the sandbox boundary, every tool (including the `run_command` RCE guard,
the read-only `git` tool, and the `web_fetch` SSRF guard), the agent loop (tool
execution, max-iteration guard, confirmation, events, usage, retry, history
trimming, delegation), the provider translators, streaming chunk-assembly, and
zip-slip safety.

## 🗺️ Roadmap

Next up: **MCP server support**, a local **knowledge base** (`pi ingest docs/`
→ `pi ask`), **browser automation**, deep-research mode, parallel sub-agents,
and `pi benchmark` — the full plan with phases lives in
[ROADMAP.md](ROADMAP.md). Release history: [CHANGELOG.md](CHANGELOG.md).

---

<p align="center"><em>Built by Ashutosh Sharma.</em></p>
