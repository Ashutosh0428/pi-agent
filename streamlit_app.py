"""pi-agent — public web demo (bring your own API key).

A safe, hosted slice of pi: chat with the agent and watch it use file tools in
an isolated per-session workspace.

Safety model (important — this is a public app):
  * **No shell.** ``run_bash`` is disabled, so visitors can never execute
    commands on the host.
  * **Sandboxed.** File tools are confined to a fresh temp directory per
    session; the Sandbox blocks ``../`` escapes, so the agent cannot read the
    server's files.
  * **Your key, your session.** The API key you paste is used only for this
    session to talk to the model — it is never stored, logged, or committed.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))

from pi_agent.agent import Agent  # noqa: E402
from pi_agent.config import SYSTEM_PROMPT, AgentConfig  # noqa: E402
from pi_agent.llm import Usage, build_provider, estimate_cost  # noqa: E402
from pi_agent.sandbox import Sandbox  # noqa: E402
from pi_agent.skills import build_system_prompt, load_skills  # noqa: E402
from pi_agent.tools.registry import build_default_tools  # noqa: E402

SKILLS_DIR = Path(__file__).parent / "skills"
DEFAULT_MODELS = {"anthropic": "claude-sonnet-4-6", "openai": "gpt-4o-mini"}
KEY_LINKS = {
    "anthropic": "https://console.anthropic.com/settings/keys",
    "openai": "https://platform.openai.com/api-keys",
}

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


# ── Sidebar: provider, model, key, controls ──────────────────────────────────
with st.sidebar:
    st.header("⚙️ Setup")
    provider = st.radio("Provider", ["anthropic", "openai"], format_func=str.title)
    model = st.text_input("Model", value=DEFAULT_MODELS[provider])
    api_key = st.text_input(
        f"{provider.title()} API key",
        type="password",
        help="Used only for this session. Never stored, logged, or sent anywhere "
        "except the model provider.",
    )
    st.caption(f"[Get a {provider.title()} key →]({KEY_LINKS[provider]})")
    use_skills = st.toggle("Use skills (write-tests, code-review, refactor)", value=True)

    if st.button("🧹 Clear conversation", use_container_width=True):
        for k in ("messages", "agent", "agent_key", "total_in", "total_out"):
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
    "A minimal terminal AI coding agent — now in your browser. It reads, writes, "
    "and edits files in a sandboxed workspace via an LLM tool-use loop. "
    "**Bring your own key** and try it."
)

if not api_key:
    st.info(
        "👈 Paste your Anthropic or OpenAI API key in the sidebar to start. "
        "Then ask it to, e.g., *“write a Python function that reverses a string, "
        "save it to utils.py, then add a test.”*"
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
                stream=False,       # render tool steps + final answer in Streamlit
            ),
        )
        st.session_state.agent = agent
        st.session_state.agent_key = fingerprint
        st.session_state.messages = []
    return st.session_state.agent


agent = _get_agent()
st.session_state.setdefault("messages", [])

# Replay history.
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Chat turn ────────────────────────────────────────────────────────────────
prompt = st.chat_input("Ask pi to write or edit code…")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        status = st.status("pi is working…", expanded=True)
        usage_box = {"in": 0, "out": 0}

        def on_event(kind, payload):
            if kind == "tool_call":
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
        except Exception as exc:  # never leak the key; show a clean message
            status.update(label="error", state="error")
            st.error(f"Request failed: {type(exc).__name__}. Check your key/model and try again.")
            answer = None

        # Show workspace files + cost for this turn.
        files = sorted(p.name for p in Path(_sandbox_dir()).glob("*") if p.is_file())
        cols = st.columns(2)
        if files:
            cols[0].caption("🗂️ workspace: " + ", ".join(files))
        tok = usage_box["in"] + usage_box["out"]
        if tok:
            est = estimate_cost(model, Usage(usage_box["in"], usage_box["out"]))
            label = f"📊 {tok} tokens"
            if est is not None:
                label += f" · ~${est:.4f}"
            cols[1].caption(label)
