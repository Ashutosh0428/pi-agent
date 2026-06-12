# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
semantic versioning.

## [0.6.0] — 2026-06-12

### Added
- **MCP (Model Context Protocol) support.** A pure-stdlib stdio client
  (`mcp_client.py`) connects to MCP servers declared in the standard
  `mcpServers` JSON (paste your Claude Desktop / Cursor config unchanged):
  `initialize` handshake, paginated `tools/list`, id-matched `tools/call`.
  Each server tool becomes a pi tool `mcp__<server>__<tool>`, confirmation-
  gated. A server that fails to start is skipped with a warning. `--mcp-config`
  flag; `/mcp` REPL command; auto-discovers `.pi/mcp.json` then `~/.pi/mcp.json`.
  CLI/local only — the web demo never spawns subprocesses. **No new
  dependency** — the wire protocol is implemented directly.
- **Local knowledge base.** `pi ingest <dir>` chunks `.md/.txt/.rst` files and
  builds a **pure-python BM25** index in a stdlib **sqlite** database
  (`.pi/kb.sqlite3`). `pi ask "<question>"` answers grounded in those docs with
  `[source]` citations; a `search_knowledge` tool auto-registers in chat when a
  KB exists. Fully offline (pairs with local Ollama). No embeddings, no API
  calls, no new dependency.
- **Safety guardrails (on by default).** Deterministic checks at the single
  tool-dispatch choke-point, so the CLI and web app are protected identically:
  - *Secret-exfiltration block* — an external tool (`web_fetch`/`run_bash`/MCP)
    whose arguments contain a live secret-env value is refused.
  - *Destructive-command confirmation* — `rm -rf /`, `curl|sh`, `sudo`, fork
    bombs, force pushes require confirmation even under `--yes`.
  - *Untrusted-content spotlighting* — `web_fetch`/MCP output is wrapped so the
    model treats it as data, blunting prompt injection.
  - *Output secret redaction* — key-shaped substrings are masked in every tool
    result. `--no-guardrails` opts out.
- **Three new skills** (21 total): `use-mcp`, `knowledge-base`, `secure-tools`.

## [0.5.0] — 2026-06-12

### Added
- **Persistent project memory.** New `remember` tool appends durable facts
  to `.pi/memory.md` (plain markdown, user-editable); the CLI auto-recalls
  the trailing 4 KB into the system prompt next session. CLI/local only.
- **Reflection pass (`--reflect`).** After a successful answer, one bounded
  self-review turn (≤5 tool iterations, never recursive) re-checks the work,
  fixes real problems with tools, and restates the final answer.
- **Skill auto-routing.** Skills are scored against the prompt and only the
  top-k (default 3) are inlined in full; the one-line index of all skills
  stays visible. One-shot CLI flag `--skills-top-k`; the web demo routes
  per message. `0` restores inline-everything.
- **`apply_patch` tool** — several exact-string edits across files in one
  atomic call: all hunks validated first, any failure leaves every file
  untouched.
- **Web: workspace file browser** — view any uploaded or agent-created file
  with syntax highlighting and download it, mid-conversation; auto-expands
  when a deck/report artifact appears (replaces the Downloads strip).
- **Web: session cost meter** (sidebar, accumulates across turns) and
  **chat transcript download** (.md).
- **Six new skills** (18 bundled): security-review, performance-review,
  write-readme, commit-message, api-design, fix-ci.
- **docs/USAGE.md** — complete post-install guide (keys for all 8 providers,
  every flag, troubleshooting, FAQ) and **ROADMAP.md** (MCP, knowledge base,
  browser automation, parallel agents, benchmark — phased).

### Fixed
- Web demo: skills toggle now also benefits from routing instead of
  inlining all skill bodies into every request.

## [0.4.0] — 2026-06-12

### Added
- **Published on PyPI as [`pi-coding-agent`](https://pypi.org/project/pi-coding-agent/)**
  (`pi-agent` was taken) — install with `pipx install pi-coding-agent`,
  `uv tool install pi-coding-agent`, or plain `pip install pi-coding-agent`.
  The import package `pi_agent` and the `pi` command are unchanged.
- **Free-first onboarding.** Bare `pi` now auto-detects the provider from
  whichever API key is set (paid → strongest free tiers → aggregators → a
  running local Ollama). With no keys at all it shows a quick-setup panel
  with three free paths (Groq, Gemini, Ollama) instead of an error.
- `pi --version`.
- **Web demo:** provider dropdown defaults to Groq (free), starter-prompt
  chips on an empty conversation, and live token streaming of the answer.
- Tag-driven release workflow (`v*` → build → PyPI trusted publishing →
  GitHub release), contributor docs (CONTRIBUTING, code of conduct,
  issue/PR templates), and a Dockerfile.

### Changed
- The `openai` SDK is now a **core dependency** — Groq, Gemini, OpenRouter,
  EURI, GLM and Ollama all use the OpenAI-compatible path, so a clean
  install works with a free key. `[openai]` remains as an empty
  backward-compat extra.
- A provider chosen without a model now serves *that provider's* default
  model instead of the global Claude default.
- Version is single-sourced from `pi_agent.__version__`.

### Fixed
- `pi --provider groq` (without `--model`) no longer sends the Claude
  default model id to Groq.
- Web demo: the workspace file listing was built but never sent with the
  prompt; uploads are visible to the model again.
- GLM is now marked free in the provider registry (`glm-4.5-flash`).

## [0.3.0] — 2026-06-12

### Security
- **Closed a remote-code-execution hole in the public web demo.** The restricted
  `run_command` tool allowlisted `find`, whose `-exec`/`-delete` primaries launch
  arbitrary programs and bypassed the allowlist entirely. `find` is removed and a
  program-agnostic denylist now rejects exec/write/delete flags.

### Added
- **Streaming for every OpenAI-compatible provider** (Groq, OpenRouter, Gemini,
  EURI, GLM, Ollama) — previously only Anthropic streamed. Tool-call fragments
  are reassembled across chunks; token usage is captured when the server allows.
- **`git` tool** — read-only repository inspection (`status`, `diff`, `log`,
  `show`, `branch`, `ls-files`, `blame`, `remote`). Mutating subcommands and
  config injection are rejected. Local/trusted only.
- **`web_fetch` tool** — fetch a public page as readable text, with an SSRF guard
  that rejects private/loopback/link-local hosts and re-validates redirects.
  Local/trusted only.
- **Context-window trimming** — long sessions trim the transcript sent to the
  model (`max_history_messages`, default 80), snapped to a user-message boundary.
- `claude-fable-5` added to the Anthropic model picker and the cost table.

### Changed
- Retry backoff now uses full jitter to de-synchronise concurrent retries.
- Extracted `tools/_subprocess.py` so `run_command` and `git` share one
  path-guard and confined runner.

### Tooling
- CI now enforces `ruff format --check` and `mypy src` in addition to `ruff check`
  and `pytest`. Repo formatted ruff-clean throughout. Test suite: 100 tests.

## [0.1.0]
- Initial release: provider-neutral tool-use loop (Anthropic + OpenAI-compatible),
  sandboxed filesystem/shell tools, planner, sub-agents, skills, data analysis and
  slide generation, and the Streamlit web demo.
