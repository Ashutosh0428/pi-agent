---
name: code-review
description: Review code for correctness, clarity, and safety.
trigger: when the user asks you to review or critique code
---
When reviewing code:

1. `read_file` the code before commenting — never review from memory.
2. Report findings in priority order: correctness bugs first, then security,
   then clarity/maintainability, then style.
3. For each issue give: the location, why it matters, and a concrete fix.
4. Be specific and terse. Skip praise and filler.
5. Do not rewrite the whole file unless asked — point to the lines.
6. If nothing is wrong, say so plainly rather than inventing nits.
