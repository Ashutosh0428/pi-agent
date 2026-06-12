# Contributing to pi-agent

Thanks for helping! pi-agent stays deliberately small and hackable — most
contributions are a new tool, a new provider, a new skill, or a fix.

## Dev setup

```bash
git clone https://github.com/Ashutosh0428/pi-agent && cd pi-agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[data,dev]"
```

## Checks (CI runs exactly these)

```bash
ruff check .            # lint
ruff format --check .   # formatting
mypy src                # types
pytest -q               # tests — offline, no API key, no network
```

All four must pass. Tests use a scripted fake provider — **never** add a test
that needs a real API key or network access.

## Adding things

- **Tool:** handler + `Tool` spec in `src/pi_agent/tools/`, register it in
  `registry.py`, add tests in `tests/test_tools.py`. Mind the sandbox — all
  paths go through `Sandbox.resolve()`.
- **Provider:** add a `ProviderSpec` to `PROVIDERS` in `llm.py`. If it's
  OpenAI-compatible you're done; otherwise implement `LLMProvider.complete()`.
- **Skill:** drop `skills/<name>/SKILL.md` (frontmatter + When/How/Avoid) —
  no code changes needed.

## Pull requests

- One focused change per PR; include tests for behavior changes.
- The public web demo is security-sensitive: anything touching
  `safe_exec.py`, `sandbox.py`, `upload.py`, or `streamlit_app.py` gets extra
  scrutiny — call out the threat model in the PR description.
- Update `CHANGELOG.md` under an `Unreleased`/next-version heading when the
  change is user-visible.
