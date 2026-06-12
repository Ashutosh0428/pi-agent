## What & why

<!-- One or two sentences. Link the issue if there is one. -->

## Checklist

- [ ] `ruff check .` + `ruff format --check .` pass
- [ ] `mypy src` passes
- [ ] `pytest -q` passes — tests stay offline (no API key, no network)
- [ ] CHANGELOG.md updated (user-visible changes)
- [ ] Touches `safe_exec.py` / `sandbox.py` / `upload.py` / `streamlit_app.py`?
      → threat model called out below

## Security notes (if applicable)

<!-- What could a malicious input/visitor do with this change? -->
