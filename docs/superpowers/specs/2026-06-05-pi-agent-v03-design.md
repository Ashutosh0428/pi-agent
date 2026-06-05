# pi-agent v0.3 — "Claude-Code-like" web app

**Date:** 2026-06-05
**Status:** approved → implemented

## Goal
Make the pi-agent web demo more capable and more accessible: let people try it
on a **free** model, give it a **planner with a live todo list**, let them
**upload code** to review, and add **more skills** — while keeping the public
app safe.

## Decisions
- **Free models:** add Groq and OpenRouter. Both are OpenAI-compatible, so reuse
  `OpenAIProvider` with a `base_url` from a provider registry. Users bring their
  own **free** key (no card). A truly keyless app (host pays for everyone) is
  rejected — abuse + cost.
- **Parallel/agentic feel = planner + todos**, not true concurrent sub-agents
  (rate limits on free tiers + complexity). One `update_plan` tool + a `plan`
  event rendered as a live checklist.
- **Code input = file upload** only (paste/URL deferred). Upload writes into the
  per-session sandbox; filename is basename-only (no traversal).

## Components
- `llm.py` — `ProviderSpec` + `PROVIDERS` registry (anthropic, openai, groq,
  openrouter); `build_provider` derives kind + base_url from it. `estimate_cost`
  treats `:free` models as $0.
- `tools/planning.py` — `update_plan` tool (non-mutating, records steps). Agent
  emits a `plan` event when it sees an `update_plan` call.
- `skills/` — add `planning`, `debug`, `explain-code`, `write-docs` (7 total).
- `streamlit_app.py` — provider dropdown (free-tagged) from the registry, model
  prefill, BYO-key, file uploader → sandbox, live plan checklist, free/cost label.
- `cli.py` — provider env keys + `--provider` choices come from the registry.

## Safety (unchanged, reaffirmed)
Public app: shell disabled, file tools confined to a per-session temp sandbox,
key is session-only and never stored/logged/committed.

## Testing
Offline only (no SDK construction, no network): provider registry shape, free
cost, `update_plan` tool behaviour + registration, agent `plan` event emission,
skills loader. `ruff` + `pytest` green in CI.

## Out of scope (YAGNI)
True concurrent multi-agent execution; paste-box and GitHub-URL code input;
OpenAI/Groq token streaming in the web UI.
