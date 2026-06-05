---
name: planning
description: Break a task into steps and track them with a live plan.
trigger: any non-trivial or multi-step task
---
For any task with more than one step:

1. **First**, call the `update_plan` tool with a short, ordered list of steps,
   each marked `pending` (mark the first `in_progress`).
2. Work the steps in order. After finishing one, call `update_plan` again with
   that step `done` and the next `in_progress`.
3. Keep steps small and concrete (3–6 is usually right). Don't over-plan.
4. When everything is `done`, give a one or two sentence summary.

The plan is shown to the user as a live checklist — keep it honest and current.
