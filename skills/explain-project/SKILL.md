---
name: explain-project
description: Explain what a whole project does, the problem it solves, and its flow.
trigger: when the user uploads a project / asks what a codebase does or how it flows
---
When asked to explain a project (e.g. after a ZIP upload):

1. **Map it first.** Use `list_dir` (and `run_command` with `find`/`grep` if
   available) to see the structure. Read the `README` if present.
2. **Find the entry points** — `main.py`, `app.py`, `cli`, `index.*`, server
   setup, or `__main__`. Read them.
3. Then explain, in this order:
   - **What problem it solves** — one or two sentences on the purpose.
   - **End-to-end flow** — how a request/run moves through the modules
     (input → processing → output), naming the key files.
   - **Key components** — the main modules and what each is responsible for.
   - **Notable tech / patterns** and anything risky or unclear.
4. For a large repo, `delegate` the exploration (“map the repo and list the
   entry points and key modules”) to a sub-agent, then synthesise its findings.
5. Keep it concrete and tied to real files — cite paths. Don't invent features.
