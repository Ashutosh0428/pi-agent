---
name: refactor
description: Refactor code safely without changing behaviour.
trigger: when the user asks to refactor, clean up, or simplify code
---
When refactoring:

1. Read the file and, if present, its tests first.
2. Preserve behaviour — a refactor must not change observable output.
3. Make one focused change at a time with `edit_file` using an exact, unique
   old_string; do not rewrite unrelated code.
4. Keep names and style consistent with the surrounding code.
5. If tests exist, suggest running them after each change.
6. End with a one-line summary of what changed and why it's safe.
