# pi-agent v0.4 — public release (PyPI + free-first UX + web UI)

**Date:** 2026-06-12
**Status:** approved
**Goal owner decision:** primary audience = end users who install and use it;
free-key users must get the best possible experience.

## Goal

Anyone can install pi-agent in one command, get a working agent with a free
API key (or no key, via Ollama) with zero flags, and the hosted web demo
activates first-time visitors instead of stopping them at a paid default.

## Decisions (from brainstorm)

- **PyPI name:** `pi-coding-agent` (`pi-agent` is taken on PyPI). The import
  package stays `pi_agent`, the console script stays `pi`.
- **Publish mechanism:** GitHub Actions **trusted publishing** on tag `v*` —
  no API tokens. One-time manual step: owner creates the PyPI project's
  trusted-publisher entry.
- **Scope:** full funnel (approach C) — packaging + free-first CLI UX +
  web-UI improvements + release automation + README/visuals + contributor
  onramp + Dockerfile.
- **Version:** bump to **0.4.0**; single-source the version from
  `pi_agent.__version__` (pyproject currently says 0.1.0 while
  `__init__.py` says 0.3.0 — that mismatch dies here).
- **Free-first requirement (owner):** with a free API key, people get the
  best result — free providers work on a clean install (openai SDK becomes a
  core dep), are auto-detected, and the web demo defaults to a free provider.

## 1 · Packaging / PyPI

- `pyproject.toml`:
  - `name = "pi-coding-agent"`, `dynamic = ["version"]` via
    `[tool.setuptools.dynamic] version = {attr = "pi_agent.__version__"}`.
  - `readme`, `license = "MIT"` (SPDX string), `authors`, `keywords`,
    PyPI `classifiers`, `[project.urls]` (Homepage, Repository, Issues,
    Changelog, Live Demo).
  - Dependencies: core = `anthropic`, `openai`, `rich` (every free provider
    rides the OpenAI-compatible path — a clean install must not ImportError).
    Extras: `data` (pandas, python-pptx, openpyxl), `dev` (pytest, ruff,
    build, twine), `all`.
- README install section: `pipx install pi-coding-agent`,
  `uv tool install pi-coding-agent`, plain `pip install`.

## 2 · Free-first CLI UX

- **Env auto-detect** (new `detect_provider()` in `llm.py`): when neither
  `--provider` nor `--model` nor `PI_AGENT_MODEL` is given, pick the first
  provider whose env key is set, in order:
  `anthropic → openai → gemini → groq → glm → euri → openrouter`; if none,
  probe Ollama at `localhost:11434` (~0.2 s socket timeout) and use it when
  reachable.
- **No keys at all** → rich onboarding panel (not an error dump): three free
  paths with key URLs (Groq, Gemini) + Ollama instructions, exit code 1.
- `pi --version` flag (argparse `action="version"`).
- Offline unit tests: detection order (monkeypatched env), Ollama probe
  fallback, onboarding path, `--version`.

## 3 · Free-first web UI (streamlit_app.py)

- Provider dropdown **defaults to Groq** (free) instead of Anthropic
  (`index=list(PROVIDERS).index("groq")`); 🆓 labels already exist.
- **Starter prompt chips** rendered when the conversation is empty and a key
  is present: three buttons (write fn + test · explain uploaded zip ·
  analyze CSV → deck). Clicking queues the prompt via
  `st.session_state.queued_prompt` and reruns — the chat turn consumes
  `queued_prompt or st.chat_input(...)`.
- **Live token streaming:** `config.stream=True`; accumulate
  `assistant_delta` events (already emitted, `agent.py:151`) into an
  `st.empty()` placeholder during the turn; final answer replaces it.
  Anthropic + OpenAI-compatible both stream in core since v0.3.x.
- Minor CSS: pill spacing/padding tweak.

## 4 · Release automation

- `.github/workflows/publish.yml`: trigger `push: tags: ['v*']` →
  `python -m build` → `twine check dist/*` →
  `pypa/gh-action-pypi-publish` with `permissions: id-token: write`
  (trusted publishing) → `gh release create` with the matching CHANGELOG
  section as notes.
- `CHANGELOG.md` (keep-a-changelog format): retroactive 0.1.0 / 0.2.0 /
  0.3.0 entries condensed from git history; 0.4.0 = this release.
- `docs/RELEASING.md`: the owner's one-time trusted-publisher setup
  (exact PyPI form values) + the routine release steps (bump, tag, push).

## 5 · README + visuals

- Install + quickstart lead with the free path (Groq/Gemini key → `pi`
  just works; Ollama keyless).
- Fresh hero screenshot of the improved web UI (Playwright capture)
  committed under `docs/assets/` and embedded at the top of the README.
- Badges: PyPI version + downloads added next to CI/license.
- Update feature table/roadmap (streaming shipped; auto-detect added).

## 6 · Contributor onramp

- `CONTRIBUTING.md`: dev setup (`pip install -e ".[dev,data]"`), test/lint
  commands, PR expectations (ruff + pytest green, offline tests only).
- `CODE_OF_CONDUCT.md`: Contributor Covenant v2.1.
- `.github/ISSUE_TEMPLATE/bug_report.yml`, `feature_request.yml`,
  `.github/PULL_REQUEST_TEMPLATE.md`.

## 7 · Docker

- `Dockerfile`: `python:3.12-slim`, `pip install .[data]`, `WORKDIR /work`,
  `ENTRYPOINT ["pi"]`. `.dockerignore` (venv, caches, .git).
- README usage: `docker run -it -e GROQ_API_KEY -v "$PWD":/work pi-agent`.
- No registry publishing (deferred — YAGNI).

## Safety (unchanged, reaffirmed)

Public web app keeps: no raw shell, per-session temp sandbox, BYO key never
stored/logged. CLI onboarding panel prints key *URLs*, never reads keys
itself. No telemetry of any kind.

## Verification

- `ruff check .` + full `pytest` (existing 69 + new) — offline, no keys.
- `python -m build` + `twine check dist/*` pass.
- Fresh-venv smoke: install the wheel → `pi --version` works; `pi` with no
  keys shows the onboarding panel (exit 1).
- Local `streamlit run` + Playwright: Groq default selected, chips render,
  screenshot captured for README.
- `docker build` succeeds (if daemon available).

## Owner actions (the only manual steps)

1. Create/log in to PyPI account → add **trusted publisher** for project
   `pi-coding-agent` (owner `Ashutosh0428`, repo `pi-agent`, workflow
   `publish.yml`) — exact steps land in `docs/RELEASING.md`.
2. Approve the final push + `v0.4.0` tag.

## Out of scope (YAGNI)

GHCR/registry image, paste-box or GitHub-URL code input, concurrent
sub-agents, keyless hosted inference (host-pays rejected in v0.3 design),
skill auto-selection.
