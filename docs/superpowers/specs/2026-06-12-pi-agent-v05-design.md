# pi-agent v0.5 — "smarter + friendlier"

**Date:** 2026-06-12
**Status:** approved
**Owner asks:** deeper agentic ability ("AGI etc"), see uploaded/created file code
anytime in the web app, more skills, step-by-step post-install usage docs,
overall more user-friendly.

## Honest framing

No feature here is AGI. The buildable core of the ask is: **the agent
remembers across sessions, checks its own work, and picks the right knowledge
per task**. Those three, plus the UX asks, are this release.

## 1 · Workspace file viewer (web)

- `_render_workspace_browser()` in `streamlit_app.py`: an `st.expander`
  ("🗂️ Workspace files") rendered above the chat whenever the per-session
  sandbox contains files (uploaded *or* agent-created).
- Inside: relative-path `st.selectbox` over `rglob("*")` files →
  syntax-highlighted `st.code` (language from extension map) for text files
  ≤ 200 KB; images via `st.image`; anything else → size note.
- Every file gets a `st.download_button` (unique keys: `wb_<path>`).
- The existing post-turn "Downloads" artifact strip stays (it covers
  generated decks); the browser is the always-on view.

## 2 · Persistent memory (CLI)

- New tool `remember` in `tools/memory.py`:
  `{"fact": str}` → appends `- [YYYY-MM-DD] <fact>` to `.pi/memory.md`
  under the sandbox root (path via `Sandbox.resolve` — confined).
- Recall: `load_memory(root) -> str` reads `.pi/memory.md`, returns at most
  the **last 4 KB** (prompt-bloat cap). `cli.py` appends a
  `## Project memory (from earlier sessions)` section to the system prompt
  when non-empty.
- System prompt addition tells the model when to call `remember`
  (decisions, conventions, user preferences — not transcripts).
- Registry: `enable_memory=True` from the CLI; **off in the web demo**
  (per-session temp sandboxes die anyway).
- Tests: append/format, 4 KB cap, recall round-trip, registry gating.

## 3 · Reflection pass (CLI flag `--reflect`)

- `AgentConfig.reflect: bool = False`.
- In `Agent.run`: when the main loop finishes with a final text answer and
  `reflect` is on, append one user-role message:
  "Review your work above against the original request. Fix real problems
  with tools; if everything is correct reply with the final answer again."
  Then run the loop once more with `max_iterations=5` and **reflect forced
  off** (no recursion). Emits `info` event `🔍 reflection pass…`.
- The reflected answer (if any) replaces the final text.
- Web demo: not exposed (token cost on free tiers).
- Tests (fake provider): reflection turn happens once, bounded, off by
  default, improved answer wins.

## 4 · Skill auto-routing

- `select_skills(prompt, skills, top_k) -> list[Skill]` in `skills.py`:
  pure function; score = token overlap between the prompt and each skill's
  `name + description + trigger` frontmatter (case-folded, alnum tokens);
  ties break by skill name for determinism.
- `build_system_prompt` gains `top_k: int = 0`; `0` keeps today's behavior
  (inline everything). With `top_k > 0`: full content for the top-k
  *scoring > 0* skills, plus a one-line `name — description` index of all
  skills so the model knows what else exists.
- CLI default: `--skills-top-k 3` when `--skills-dir` is used; web demo
  uses `top_k=3` with its bundled skills.
- Tests: scorer determinism, zero-score exclusion, k=0 backward compat,
  index always present.

## 5 · `apply_patch` tool

- `tools/patch.py`: input
  `{"edits": [{"path", "old_string", "new_string"}, …]}` — **validate all
  hunks first** (file exists via sandbox, `old_string` unique), then write
  all; any failure → no file touched, error names the failing hunk.
- Registered for CLI and web (same mutation boundary as `edit_file`;
  web sandbox is a temp dir with auto-approve already on).
- Tests: multi-file success, atomicity on second-hunk failure, uniqueness
  rejection, sandbox escape rejection.

## 6 · Six new skills (12 → 18)

`security-review` · `performance-review` · `write-readme` ·
`commit-message` · `api-design` · `fix-ci` — same SKILL.md format
(frontmatter + When/How/Avoid/Done-well). Each ≤ 60 lines.

## 7 · docs/USAGE.md — post-install, every step

Sections: install (pipx / uv / pip / docker) → get a key per provider
(eight subsections, exact console URLs, free-tier notes) → first run
(what the onboarding panel shows) → REPL commands with one example each →
all CLI flags table → one-shot mode → skills (using bundled, adding your
own, how auto-routing picks) → memory how-to (`.pi/memory.md`) →
`--reflect` → running the web app locally → troubleshooting table
(≥ 8 real errors: missing key, bad model id, 429, Ollama not running,
python < 3.10, pipx PATH, proxy/SSL, model without tool support) → FAQ.
README links it prominently ("📖 Full usage guide").

## 8 · Web polish

- Sidebar **session cost meter**: accumulate token/cost totals in
  `st.session_state` across turns (today: per-turn captions only).
- **Download chat** button (sidebar): transcript as Markdown.
- File viewer from §1.

## Cross-cutting

- Version → `0.5.0`; CHANGELOG section; README features/roadmap updated
  (tests count, new tools, memory/reflect/routing).
- Commits straight to `main`, **no AI trailers, no PRs** (owner rule;
  PR refs are immortal).
- All gates green before tag: `ruff check` + `ruff format --check` +
  `mypy src` + `pytest -q`.
- Ship: push main → tag `v0.5.0` → trusted publishing → PyPI.

## Out of scope (YAGNI)

True parallel sub-agents (free-tier rate limits), vector/embedding memory,
reflection in the web demo, in-browser file *editing* (view + download
only), charts in analyze_data, keyless hosted inference.
