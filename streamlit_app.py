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
from pi_agent.llm import PROVIDERS, Usage, build_provider, estimate_cost  # noqa: E402
from pi_agent.sandbox import Sandbox  # noqa: E402
from pi_agent.skills import build_system_prompt, load_skills  # noqa: E402
from pi_agent.tools.registry import build_default_tools  # noqa: E402

SKILLS_DIR = Path(__file__).parent / "skills"
STATUS_ICON = {"done": "✅", "in_progress": "⏳", "pending": "⬜"}
UPLOAD_TYPES = ["py", "js", "ts", "java", "go", "rs", "c", "cpp", "sh", "txt", "md", "json", "yaml", "yml", "html", "css"]

st.set_page_config(page_title="pi-agent — try it", page_icon="🤖", layout="centered")


def _fmt_args(args: dict) -> str:
    parts = []
    for key, value in args.items():
        text = str(value).replace("\n", " ")
        parts.append(f"{key}={text[:50] + '…' if len(text) > 50 else text}")
    return ", ".join(parts)


def _sandbox_dir() -> str:
    if "sandbox_dir" not in st.session_state:
        st.session_state.sandbox_dir = tempfile.mkdtemp(prefix="pi_demo_")
    return st.session_state.sandbox_dir


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

    provider = st.selectbox(
        "Provider",
        list(PROVIDERS),
        format_func=lambda p: f"{p.title()}  🆓" if PROVIDERS[p].free else p.title(),
    )
    spec = PROVIDERS[provider]
    model = st.text_input("Model", value=spec.default_model)
    api_key = st.text_input(
        f"{provider.title()} API key",
        type="password",
        help="Used only for this session. Never stored, logged, or sent anywhere "
        "except the model provider.",
    )
    free_note = " — 🆓 free, no credit card" if spec.free else ""
    st.caption(f"[Get a {provider.title()} key →]({spec.key_url}){free_note}")

    use_skills = st.toggle("Use skills (plan, tests, review, debug, …)", value=True)

    uploaded = st.file_uploader(
        "📎 Upload a file to review", type=UPLOAD_TYPES,
        help="Lands in the sandbox; then ask: “review <filename>”.",
    )
    if uploaded is not None:
        if uploaded.size > 200_000:
            st.warning("File too large (>200 KB).")
        else:
            dest = Path(_sandbox_dir()) / Path(uploaded.name).name  # strip any path
            try:
                dest.write_bytes(uploaded.getvalue())
                st.success(f"Uploaded **{dest.name}** — ask me to review it.")
            except OSError:
                st.warning("Could not save that file.")

    if st.button("🧹 Clear conversation", use_container_width=True):
        for k in ("messages", "agent", "agent_key"):
            st.session_state.pop(k, None)
        st.rerun()

    st.markdown("---")
    st.caption(
        "🔒 **Safe demo:** shell disabled, file tools sandboxed to a temporary "
        "per-session folder. Your key stays in your session."
    )
    st.caption("[Source on GitHub](https://github.com/Ashutosh0428/pi-agent)")

# ── Header ───────────────────────────────────────────────────────────────────
st.title("🤖 pi-agent")
st.caption(
    "A minimal AI coding agent — it **plans**, then reads, writes, and edits files "
    "in a sandboxed workspace via an LLM tool-use loop. Works with Claude, GPT, "
    "and **free** models (Groq, OpenRouter). **Bring your own key** and try it."
)

if not api_key:
    st.info(
        "👈 Pick a provider and paste an API key to start. "
        "**No paid key?** Choose **Groq** or **OpenRouter** (🆓) — free key, no card. "
        "Then ask, e.g., *“write a Python function that reverses a string, save it to "
        "utils.py, then add a test.”*"
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
            registry=build_default_tools(enable_shell=False),  # no shell on a public app
            sandbox=Sandbox(_sandbox_dir()),
            config=AgentConfig(
                model=model,
                provider=provider,
                system_prompt=system_prompt,
                enable_shell=False,
                auto_approve=True,  # mutations are confined to the temp sandbox
                stream=False,       # render plan + tool steps + final answer in Streamlit
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

# ── Chat turn ────────────────────────────────────────────────────────────────
prompt = st.chat_input("Ask pi to plan, write, review, or edit code…")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Tell the model what's already in its workspace (uploaded files), so weaker
    # tool-users don't have to discover files — they just read_file by name.
    workspace = sorted(p.name for p in Path(_sandbox_dir()).glob("*") if p.is_file())
    effective_prompt = prompt
    if workspace:
        effective_prompt = (
            f"(Files in your working directory: {', '.join(workspace)}. "
            "Use read_file to open one before reviewing or editing it.)\n\n" + prompt
        )

    with st.chat_message("assistant"):
        plan_box = st.empty()
        status = st.status("pi is working…", expanded=True)
        usage_box = {"in": 0, "out": 0}

        def on_event(kind, payload):
            if kind == "plan":
                _render_plan(plan_box, payload)
            elif kind == "tool_call":
                status.write(f"🔧 `{payload.name}({_fmt_args(payload.args)})`")
            elif kind == "tool_result":
                out = payload["output"]
                status.write(f"```\n{out[:500] + ' …' if len(out) > 500 else out}\n```")
            elif kind == "usage":
                usage_box["in"] += payload["turn"].input_tokens
                usage_box["out"] += payload["turn"].output_tokens

        agent.on_event = on_event
        try:
            answer = agent.run(prompt)
            status.update(label="done", state="complete", expanded=False)
            st.markdown(answer or "_(no text response)_")
            st.session_state.messages.append(
                {"role": "assistant", "content": answer or "_(no text response)_"}
            )
        except Exception as exc:  # provider error body has no key; scrub anyway, to be safe
            status.update(label="error", state="error")
            detail = str(exc)
            if api_key:
                detail = detail.replace(api_key, "***")
            st.error(f"Request failed ({type(exc).__name__}): {detail[:500]}")

        files = sorted(p.name for p in Path(_sandbox_dir()).glob("*") if p.is_file())
        cols = st.columns(2)
        if files:
            cols[0].caption("🗂️ workspace: " + ", ".join(files))
        tok = usage_box["in"] + usage_box["out"]
        if spec.free:
            cols[1].caption(f"🆓 free tier · {tok} tokens" if tok else "🆓 free tier")
        elif tok:
            est = estimate_cost(model, Usage(usage_box["in"], usage_box["out"]))
            cols[1].caption(f"📊 {tok} tokens" + (f" · ~${est:.4f}" if est is not None else ""))
