# Roadmap

Where pi-agent is going. The philosophy stays fixed — minimal, transparent,
provider-neutral, sandboxed — while the agent gets materially smarter each
release. Issues and PRs against any item are welcome.

## Shipped

- **0.3** — public-demo RCE fix · streaming on every provider · read-only
  `git` tool · SSRF-guarded `web_fetch` · context trimming · CI gates
  (ruff + format + mypy + pytest)
- **0.4** — PyPI release (`pi-coding-agent`) · provider auto-detection +
  free-first onboarding · web: Groq default, starter prompts, live streaming ·
  Docker · trusted-publishing release pipeline
- **0.5** — **persistent project memory** (`.pi/memory.md`, auto-recall) ·
  **reflection pass** (`--reflect` self-review) · **skill auto-routing**
  (top-k per prompt) · atomic `apply_patch` · workspace file browser in the
  web app · session cost meter · 18 bundled skills · full usage guide

## Phase 1 — connect (next)

- **MCP support** — consume Model Context Protocol servers as tools: point
  pi at a GitHub/Postgres/Slack/Notion MCP server and its tools appear in
  the registry next to the built-ins. The `ToolRegistry` seam was built for
  exactly this.
- **Local knowledge base** — `pi ingest docs/` → embed into a local store →
  `pi ask "how does auth work?"` answers with citations from *your* docs.
- **Richer memory** — structured preferences (always/never rules) on top of
  the fact log.

## Phase 2 — reach

- **Browser automation** — `browser_open/click/type/screenshot` tools
  (Playwright-backed, local only): research websites, test web apps, fill
  forms — with the same confirmation gates as file mutations.
- **Deep research mode** — `pi research "<topic>"`: plan → search → read
  sources → cross-check → cited report.

## Phase 3 — scale

- **Parallel sub-agents** — researcher + coder + tester running
  concurrently where provider rate limits allow; sequential fallback
  everywhere else.
- **`pi benchmark`** — scripted task suite scoring models on YOUR machine:
  success rate, latency, cost per provider — pick models on evidence.
- **Autonomous loop hardening** — plan → edit → run tests → fix → repeat
  until green (today: planner + `--reflect`; this closes the loop).

## Non-goals

Keyless hosted inference (someone else paying for your tokens), heavyweight
framework dependencies, hidden prompts or telemetry — transparency is the
product.
