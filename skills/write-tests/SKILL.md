---
name: write-tests
description: Write focused, fast pytest tests for a module.
trigger: when the user asks for tests or to improve coverage
---
When asked to write tests:

1. First `read_file` the target module so the tests match the real API.
2. Put tests in `tests/test_<module>.py`. Use plain `pytest` (functions or
   simple classes), no heavy fixtures unless needed.
3. Cover: the happy path, one edge case, and one failure/error path.
4. Keep each test small and independent — no shared mutable state.
5. Prefer asserting on behaviour and return values, not on internal calls.
6. After writing, state which cases you covered and what you deliberately left out.
