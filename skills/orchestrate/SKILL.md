---
name: orchestrate
description: Split a big job into focused sub-agent tasks via delegate.
trigger: large or multi-part tasks (whole-repo review, explain + fix, multi-file change)
---
When a task is large or has clearly separable parts, and the `delegate` tool is
available:

1. First `update_plan` with the high-level steps.
2. For each self-contained part, `delegate` a focused, specific task to a
   sub-agent — e.g. "explore the repo and list entry points + key modules",
   then "review auth.py and list bugs". Give the sub-agent everything it needs
   in the task description; it has the same workspace but a fresh context.
3. Delegate **one at a time**; wait for each result before the next.
4. Synthesise the sub-agents' results into a single coherent answer — don't just
   paste them.
5. Don't over-delegate: small tasks you can do directly; delegation costs extra
   tokens and time.
