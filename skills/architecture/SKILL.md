---
name: architecture
description: Map a codebase's modules, responsibilities, and dependencies.
trigger: when the user asks about architecture, structure, or how modules relate
---
When mapping architecture:

1. List the tree and group files into modules/layers (UI, API, core, data, etc.).
2. For each module: one line on its responsibility and what it depends on.
3. Identify the **boundaries** — where modules talk to each other — and any
   tangled spots (a file doing too much, circular-looking imports).
4. Prefer a short diagram (arrows: module → depends-on) plus a few sentences.
5. Base every claim on files you actually read; flag what you didn't inspect.
