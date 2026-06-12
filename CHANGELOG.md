# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
semantic versioning.

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
