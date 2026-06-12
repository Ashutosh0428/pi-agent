# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
semantic versioning.

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
