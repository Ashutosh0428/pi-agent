---
name: debug
description: Find and fix the root cause of a bug, not just the symptom.
trigger: when the user reports an error, failure, or wrong output
---
When debugging:

1. Read the error/traceback and the relevant file before changing anything.
2. Form a hypothesis about the root cause and state it briefly.
3. Make the smallest change that fixes the cause (not the symptom) with `edit_file`.
4. If a test reproduces the bug, mention running it to confirm the fix.
5. Do not refactor unrelated code while fixing a bug.
6. End with: what was wrong, why, and what you changed.
