---
name: write-docs
description: Add clear docstrings / comments without changing behaviour.
trigger: when the user asks to document code or add docstrings
---
When documenting:

1. Read the file first so docs match the real behaviour.
2. Add concise docstrings: what the function does, its args, its return, and any
   non-obvious side effects or errors. Skip restating the obvious.
3. Use `edit_file` to insert docs; do not change logic.
4. Match the existing docstring style in the file (Google / NumPy / plain).
5. Add comments only where the *why* isn't clear from the code — not the *what*.
