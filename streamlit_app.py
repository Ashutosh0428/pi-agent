"""pi-agent — public web demo (bring your own API key).

A safe, hosted slice of pi: chat with the agent and watch it plan, then use file
tools in an isolated per-session workspace.

Safety model (important — this is a public app):
  * **No shell.** ``run_bash`` is disabled, so visitors can never execute
    commands on the host.
  * **Sandboxed.** File tools (and uploads) are confined to a fresh temp
    directory per session; the Sandbox blocks ``../`` escapes.
  * **Your key, your session.** The API key you paste is used only for this
    session to talk to the model — never stored, logged, or committed.

Providers include free tiers (Groq, OpenRouter) so anyone can try it with a
free key — no credit card.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))

from pi_agent.agent import Agent  # noqa: E402
from pi_agent.config import SYSTEM_PROMPT, AgentConfig  # noqa: E402
from pi_agent.llm import PROVIDERS, Usage, build_provider, estimate_cost, list_models  # noqa: E402
from pi_agent.sandbox import Sandbox  # noqa: E402
from pi_agent.skills import build_system_prompt, load_skills  # noqa: E402
from pi_agent.tools.registry import build_default_tools  # noqa: E402
from pi_agent.upload import extract_zip_into_sandbox  # noqa: E402

SKILLS_DIR = Path(__file__).parent / "skills"
STATUS_ICON = {"done": "✅", "in_progress": "⏳", "pending": "⬜"}
UPLOAD_TYPES = [
    "zip",
    "csv",
    "tsv",
    "xlsx",
    "py",
    "js",
    "ts",
    "java",
    "go",
    "rs",
    "c",
    "cpp",
    "sh",
    "txt",
    "md",
    "json",
    "yaml",
    "yml",
    "html",
    "css",
]
DATA_EXTS = {"csv", "tsv", "xlsx", "json"}

st.set_page_config(
    page_title="pi-agent — try it",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      #MainMenu, footer { visibility: hidden; }
      /* never hide the sidebar open/close control */
      [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"],
      [data-testid="stSidebarCollapseButton"], [data-testid="stExpandSidebarButton"] {
        visibility: visible !important; }
      .block-container { padding-top: 2.2rem; padding-bottom: 7rem; max-width: 840px; }
      /* gradient divider under the hero */
      .hero-rule { height: 3px; border: 0; border-radius: 3px; margin: .4rem 0 1.4rem;
        background: linear-gradient(90deg, #7c5cff, #22d3ee, transparent); }
      /* buttons */
      .stButton button, .stDownloadButton button {
        border-radius: 10px; border: 1px solid rgba(124,92,255,.4); font-weight: 600;
        transition: transform .12s ease, border-color .12s ease; }
      .stButton button:hover, .stDownloadButton button:hover {
        border-color: #7c5cff; transform: translateY(-1px); }
      /* chat bubbles + inputs */
      [data-testid="stChatMessage"] { border-radius: 14px; }
      [data-baseweb="input"], [data-baseweb="select"], [data-baseweb="textarea"] { border-radius: 10px; }
      /* sidebar */
      [data-testid="stSidebar"] { border-right: 1px solid rgba(255,255,255,.06); }
      /* provider pills */
      .pill { display:inline-block; padding:.2rem .65rem; margin:.15rem .25rem; border-radius:999px;
        font-size:.78rem; background:rgba(124,92,255,.14); border:1px solid rgba(124,92,255,.3);
        color:#cdb8ff; white-space:nowrap; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _fmt_args(args: dict | None) -> str:
    parts = []
    for key, value in (args or {}).items():
        text = str(value).replace("\n", " ")
        parts.append(f"{key}={text[:50] + '…' if len(text) > 50 else text}")
    return ", ".join(parts)


def _sandbox_dir() -> str:
    if "sandbox_dir" not in st.session_state:
        st.session_state.sandbox_dir = tempfile.mkdtemp(prefix="pi_demo_")
    return st.session_state.sandbox_dir


@st.cache_data(show_spinner="Fetching available models…", ttl=3600)
def _available_models(provider: str, key: str) -> list[str]:
    """Live model ids for this key (cached per provider+key). [] on failure."""
    try:
        return list_models(provider, api_key=key or None)
    except Exception:  # noqa: BLE001 - any failure -> fall back to presets
        return []


_LANG_BY_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".sh": "bash",
    ".md": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".html": "html",
    ".css": "css",
}
_IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif"}
_ARTIFACT_EXTS = {".pptx", ".pdf", ".docx", ".xlsx"}
_MAX_VIEW_BYTES = 200_000


def _render_workspace_browser() -> None:
    """Always-available view of every workspace file (uploaded or agent-made).

    Rendered last so files created during *this* turn are already visible —
    pick a file to read it with syntax highlighting, or download it.
    """
    root = Path(_sandbox_dir())
    files = sorted(p for p in root.rglob("*") if p.is_file())
    if not files:
        return
    rels = [str(p.relative_to(root)) for p in files]
    has_artifact = any(p.suffix.lower() in _ARTIFACT_EXTS for p in files)
    with st.expander(f"🗂️ Workspace files ({len(rels)}) — view & download", expanded=has_artifact):
        sel = st.selectbox("File", rels, key="wb_file")
        path = root / sel
        st.download_button(
            f"⬇ Download {Path(sel).name}",
            data=path.read_bytes(),
            file_name=Path(sel).name,
            key=f"wb_dl_{sel}",
        )
        suffix = path.suffix.lower()
        if suffix in _IMG_EXTS:
            st.image(str(path))
        elif path.stat().st_size > _MAX_VIEW_BYTES:
            st.caption(f"{path.stat().st_size:,} bytes — too large to preview, download instead.")
        else:
            try:
                st.code(path.read_text(encoding="utf-8"), language=_LANG_BY_EXT.get(suffix, "text"))
            except UnicodeDecodeError:
                st.caption("Binary file — download instead.")


def _render_plan(box, steps) -> None:
    rows = [
        f"{STATUS_ICON.get(s.get('status'), '⬜')} {s.get('step', '')}"
        for s in steps
        if isinstance(s, dict)
    ]
    if rows:
        box.markdown("**📋 Plan**\n\n" + "\n\n".join(rows))


# ── Sidebar: provider, model, key, upload, controls ──────────────────────────
with st.sidebar:
    st.header("⚙️ Setup")

    # Default to Groq: free key (no card), fast, and tool-capable — a first-time
    # visitor should land on a provider they can actually use in one minute.
    provider = st.selectbox(
        "Provider",
        list(PROVIDERS),
        index=list(PROVIDERS).index("groq"),
        format_func=lambda p: f"{p.title()}  🆓" if PROVIDERS[p].free else p.title(),
    )
    spec = PROVIDERS[provider]
    api_key = st.text_input(
        f"{provider.title()} API key",
        type="password",
        help="Used only for this session. Never stored, logged, or sent anywhere "
        "except the model provider.",
    )
    if spec.requires_key:
        free_note = " — 🆓 free, no credit card" if spec.free else ""
        st.caption(f"[Get a {provider.title()} key →]({spec.key_url}){free_note}")
    else:
        st.caption(
            "🖥️ Local & free — runs against Ollama at localhost:11434 "
            "(works when you run this app locally, not on the hosted demo)."
        )

    # Model picker — populated live from the provider's /models endpoint when a
    # key is present (always the real, current ids), else falls back to presets.
    _options = list(spec.models)
    if api_key or not spec.requires_key:
        _fetched = _available_models(provider, api_key or "")
        if _fetched:
            _options = _fetched
    _CUSTOM = "✏️ custom…"
    _picked = st.selectbox(f"Model ({len(_options)} available)", [*_options, _CUSTOM], index=0)
    model = (
        st.text_input("Custom model id", value=spec.default_model)
        if _picked == _CUSTOM
        else _picked
    )

    use_skills = st.toggle("Use skills (plan, tests, review, debug, …)", value=True)

    uploaded = st.file_uploader(
        "📎 Upload a file or project .zip",
        type=UPLOAD_TYPES,
        help="A file (or a zipped project) lands in the sandbox; then ask "
        "“review <file>” or “explain this project”.",
    )
    if uploaded is not None:
        ext = uploaded.name.lower().rsplit(".", 1)[-1]
        if ext == "zip":
            res = extract_zip_into_sandbox(uploaded.getvalue(), Sandbox(_sandbox_dir()))
            if res.error:
                st.warning(res.error)
            else:
                st.success(
                    f"Extracted **{len(res.extracted)}** files — ask me to *explain this project*."
                )
                if res.skipped:
                    st.caption(f"Skipped {len(res.skipped)} (limits / unsafe paths).")
        elif ext in DATA_EXTS:
            if uploaded.size > 10_000_000:
                st.warning("Data file too large (>10 MB).")
            else:
                dest = Path(_sandbox_dir()) / Path(uploaded.name).name
                try:
                    dest.write_bytes(uploaded.getvalue())
                    st.success(
                        f"Uploaded **{dest.name}** — ask me to *analyze it* (and make slides)."
                    )
                except OSError:
                    st.warning("Could not save that file.")
        elif uploaded.size > 200_000:
            st.warning("File too large (>200 KB). Zip it and upload as a project instead.")
        else:
            dest = Path(_sandbox_dir()) / Path(uploaded.name).name  # strip any path
            try:
                dest.write_bytes(uploaded.getvalue())
                st.success(f"Uploaded **{dest.name}** — ask me to review it.")
            except OSError:
                st.warning("Could not save that file.")

    if st.button("🧹 Clear conversation", use_container_width=True):
        for k in ("messages", "agent", "agent_key", "sess_in", "sess_out"):
            st.session_state.pop(k, None)
        st.rerun()

    if st.session_state.get("messages"):
        _transcript = "\n\n".join(
            f"**{m['role']}**:\n\n{m['content']}" for m in st.session_state.messages
        )
        st.download_button(
            "💬 Download chat (.md)",
            _transcript,
            file_name="pi-agent-chat.md",
            use_container_width=True,
        )

    st.markdown("---")
    _cost_box = st.empty()

    def _render_session_meter() -> None:
        tin = st.session_state.get("sess_in", 0)
        tout = st.session_state.get("sess_out", 0)
        if not (tin or tout):
            return
        if spec.free:
            tail = "🆓 free tier"
        else:
            est = estimate_cost(model, Usage(tin, tout))
            tail = f"~${est:.4f}" if est is not None else "cost n/a"
        _cost_box.caption(f"📊 Session: {tin + tout:,} tokens · {tail}")

    _render_session_meter()
    st.caption(
        "🔒 **Safe demo:** shell disabled, file tools sandboxed to a temporary "
        "per-session folder. Your key stays in your session."
    )
    st.caption("[Source on GitHub](https://github.com/Ashutosh0428/pi-agent)")

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="text-align:center;">
      <div style="font-size:2.6rem; font-weight:800; letter-spacing:-.5px;
           background:linear-gradient(90deg,#7c5cff,#22d3ee);
           -webkit-background-clip:text; -webkit-text-fill-color:transparent;">
        🤖 pi-agent
      </div>
      <div style="color:#9aa0aa; font-size:.97rem; margin-top:.3rem;">
        A transparent AI coding agent — it <b>plans</b>, runs tools, and explains
        code &amp; data in a sandboxed workspace. Bring your own key (free options too).
      </div>
      <div style="margin-top:.7rem;">
        <span class="pill">🧠 8 providers</span>
        <span class="pill">📋 planner</span>
        <span class="pill">🤝 sub-agents</span>
        <span class="pill">📊 data → slides</span>
        <span class="pill">🔒 sandboxed</span>
      </div>
    </div>
    <hr class="hero-rule"/>
    """,
    unsafe_allow_html=True,
)

if spec.requires_key and not api_key:
    st.info(
        "👈 Pick a provider and paste an API key to start. "
        "**No paid key?** Choose **Groq** or **OpenRouter** (🆓) — free key, no card. "
        "Then ask, e.g., *“write a Python function that reverses a string, save it to "
        "utils.py, then add a test.”* Or upload a project **.zip** and ask me to "
        "*explain this project*."
    )
    st.stop()


def _get_agent() -> Agent:
    """Build (or reuse) an agent for the current provider/model/key/skills."""
    fingerprint = f"{provider}|{model}|{api_key[-6:]}|{use_skills}"
    if st.session_state.get("agent_key") != fingerprint:
        system_prompt = SYSTEM_PROMPT
        if use_skills:
            system_prompt = build_system_prompt(SYSTEM_PROMPT, load_skills(SKILLS_DIR))
        agent = Agent(
            provider=build_provider(model, provider, api_key=api_key),
            registry=build_default_tools(
                enable_shell=False,  # no raw shell on a public app
                enable_safe_command=True,  # restricted, read-only run_command is safe
                enable_subagents=True,  # sequential delegate (no recursion)
                enable_data=True,  # analyze_data + make_slides (fixed/safe)
            ),
            sandbox=Sandbox(_sandbox_dir()),
            config=AgentConfig(
                model=model,
                provider=provider,
                system_prompt=system_prompt,
                enable_shell=False,
                auto_approve=True,  # mutations are confined to the temp sandbox
                stream=True,  # live token streaming via assistant_delta events
            ),
        )
        st.session_state.agent = agent
        st.session_state.agent_key = fingerprint
        st.session_state.messages = []
    return st.session_state.agent


agent = _get_agent()
st.session_state.setdefault("messages", [])

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Starter prompts — shown only on an empty conversation, so a first-time
# visitor can click once instead of inventing a prompt.
STARTERS = (
    (
        "✍️ Write a function + test",
        "Write a Python function that reverses a string, save it to utils.py, then write a pytest test for it and show me both files.",
    ),
    (
        "📦 Explain my uploaded project",
        "Explain this project: its purpose, how the pieces flow together, and the main components. If the workspace is empty, tell me to upload a project .zip in the sidebar first.",
    ),
    (
        "📊 Analyze data → slide deck",
        "Analyze the uploaded data file like a data scientist (stats, missing values, correlations), then make a short .pptx slide deck of the findings. If the workspace is empty, tell me to upload a CSV in the sidebar first.",
    ),
)
if not st.session_state.messages:
    st.caption("✨ Try one:")
    _chip_cols = st.columns(len(STARTERS))
    for _col, (_label, _text) in zip(_chip_cols, STARTERS):
        if _col.button(_label, use_container_width=True):
            st.session_state.queued_prompt = _text

# ── Chat turn ────────────────────────────────────────────────────────────────
prompt = st.session_state.pop("queued_prompt", None) or st.chat_input(
    "Ask pi to plan, write, review, or edit code…"
)
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Tell the model what's already in its workspace (uploaded files / extracted
    # projects), so weaker tool-users don't have to discover files. rglob so files
    # inside an extracted project's subfolders are listed too; cap to keep it lean.
    root = Path(_sandbox_dir())
    all_files = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
    workspace = all_files[:60]
    effective_prompt = prompt
    if workspace:
        more = (
            f" (+{len(all_files) - len(workspace)} more)" if len(all_files) > len(workspace) else ""
        )
        effective_prompt = (
            f"(Files in your working directory: {', '.join(workspace)}{more}. "
            "Use read_file / list_dir to open them before reviewing or editing.)\n\n" + prompt
        )

    # Route the most relevant skills for THIS prompt (token saver on free tiers);
    # the index of all skills stays in the prompt so the model knows the rest.
    if use_skills:
        agent.config.system_prompt = build_system_prompt(
            SYSTEM_PROMPT, load_skills(SKILLS_DIR), prompt=prompt, top_k=3
        )

    with st.chat_message("assistant"):
        plan_box = st.empty()
        status = st.status("pi is working…", expanded=True)
        answer_box = st.empty()
        usage_box = {"in": 0, "out": 0}
        stream_buf = {"text": ""}

        def on_event(kind, payload):
            if kind == "plan":
                _render_plan(plan_box, payload)
            elif kind == "assistant_delta":
                # Live token stream. Text emitted before a tool call is interim
                # narration — the tool_call branch clears it so only the final
                # answer remains in the box.
                stream_buf["text"] += payload
                answer_box.markdown(stream_buf["text"] + "▌")
            elif kind == "tool_call":
                stream_buf["text"] = ""
                answer_box.empty()
                status.write(f"🔧 `{payload.name}({_fmt_args(payload.args)})`")
            elif kind == "tool_result":
                out = payload["output"]
                status.write(f"```\n{out[:500] + ' …' if len(out) > 500 else out}\n```")
            elif kind == "usage":
                usage_box["in"] += payload["turn"].input_tokens
                usage_box["out"] += payload["turn"].output_tokens

        agent.on_event = on_event
        try:
            answer = agent.run(effective_prompt)
            status.update(label="done", state="complete", expanded=False)
            answer_box.markdown(answer or "_(no text response)_")
            st.session_state.messages.append(
                {"role": "assistant", "content": answer or "_(no text response)_"}
            )
        except Exception as exc:  # provider error body has no key; scrub anyway, to be safe
            status.update(label="error", state="error")
            detail = str(exc)
            if api_key:
                detail = detail.replace(api_key, "***")
            st.error(f"Request failed ({type(exc).__name__}): {detail[:500]}")

        tok = usage_box["in"] + usage_box["out"]
        if spec.free:
            st.caption(f"🆓 free tier · {tok} tokens" if tok else "🆓 free tier")
        elif tok:
            est = estimate_cost(model, Usage(usage_box["in"], usage_box["out"]))
            st.caption(f"📊 {tok} tokens" + (f" · ~${est:.4f}" if est is not None else ""))

        # Session totals (sidebar meter) — accumulated across turns.
        st.session_state.sess_in = st.session_state.get("sess_in", 0) + usage_box["in"]
        st.session_state.sess_out = st.session_state.get("sess_out", 0) + usage_box["out"]
        _render_session_meter()


# Workspace browser — rendered LAST, so files the agent created during this
# very turn (code, decks, reports) are already listed, viewable, downloadable.
_render_workspace_browser()
