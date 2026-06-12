"""Skills — reusable instructions inlined into the system prompt.

Inspired by the same idea used in larger agent platforms: a *skill* is a small
markdown file describing how to do one kind of task well. Skills live in a
directory, one folder per skill, each holding a ``SKILL.md`` with frontmatter:

    ---
    name: write-tests
    description: Write focused pytest tests for a module.
    trigger: when the user asks for tests
    ---
    <the actual guidance the model should follow>

At startup we load them and inline both an *index* (so the model sees every
trigger before deciding) and the full *contents*. That avoids spending a tool
call to read a skill — the guidance is already in context.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Skill:
    name: str
    description: str
    trigger: str
    content: str


def _parse_skill(text: str, fallback_name: str) -> Skill:
    """Parse a SKILL.md with optional ``--- key: value ---`` frontmatter."""
    name, description, trigger = fallback_name, "", ""
    body = text.strip()

    if body.startswith("---"):
        _, _, rest = body.partition("---")
        front, sep, after = rest.partition("---")
        if sep:  # well-formed frontmatter block
            body = after.strip()
            for line in front.strip().splitlines():
                key, _, value = line.partition(":")
                key, value = key.strip().lower(), value.strip()
                if key == "name" and value:
                    name = value
                elif key == "description":
                    description = value
                elif key == "trigger":
                    trigger = value

    return Skill(name=name, description=description, trigger=trigger, content=body)


def load_skills(skills_dir: Path | str | None) -> list[Skill]:
    """Load every ``<skills_dir>/<skill>/SKILL.md``. Missing dir -> empty list."""
    if skills_dir is None:
        return []
    root = Path(skills_dir)
    if not root.is_dir():
        return []

    skills: list[Skill] = []
    for skill_md in sorted(root.glob("*/SKILL.md")):
        skills.append(_parse_skill(skill_md.read_text(encoding="utf-8"), skill_md.parent.name))
    return skills


def _tokens(text: str) -> set[str]:
    """Lowercase alphanumeric tokens for crude relevance scoring."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def select_skills(prompt: str, skills: list[Skill], top_k: int) -> list[Skill]:
    """Rank skills by token overlap with the prompt and keep the ``top_k``.

    Pure and deterministic: score descending, ties broken by name. Zero-score
    skills never make the cut. ``top_k <= 0`` (or a set already small enough)
    returns everything — the pre-routing behavior.
    """
    if top_k <= 0 or len(skills) <= top_k:
        return list(skills)
    prompt_toks = _tokens(prompt)
    scored = sorted(
        ((len(prompt_toks & _tokens(f"{s.name} {s.description} {s.trigger}")), s) for s in skills),
        key=lambda pair: (-pair[0], pair[1].name),
    )
    return [s for score, s in scored[:top_k] if score > 0]


def build_system_prompt(base: str, skills: list[Skill], *, prompt: str = "", top_k: int = 0) -> str:
    """Compose the base prompt with a skills index and skill contents.

    With ``top_k > 0`` only the skills most relevant to ``prompt`` are inlined
    in full (token saver); the one-line index always lists every skill so the
    model knows what else exists. ``top_k=0`` inlines everything (legacy).
    """
    if not skills:
        return base

    chosen = select_skills(prompt, skills, top_k) if top_k > 0 else skills
    index = "\n".join(f"- **{s.name}** — {s.description or s.trigger or 'skill'}" for s in skills)
    contents = "\n\n".join(f"#### {s.name}\n{s.content}" for s in chosen)
    return (
        f"{base}\n\n"
        "--- Available skills ---\n"
        "Use these when the task matches; otherwise ignore them.\n\n"
        f"### Skills index\n{index}\n\n"
        f"### Skill contents\n{contents}\n"
    )
