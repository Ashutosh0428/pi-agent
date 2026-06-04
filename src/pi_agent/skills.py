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


def build_system_prompt(base: str, skills: list[Skill]) -> str:
    """Compose the base prompt with a skills index and their full contents."""
    if not skills:
        return base

    index = "\n".join(
        f"- **{s.name}** — {s.description or s.trigger or 'skill'}" for s in skills
    )
    contents = "\n\n".join(f"#### {s.name}\n{s.content}" for s in skills)
    return (
        f"{base}\n\n"
        "--- Available skills ---\n"
        "Use these when the task matches; otherwise ignore them.\n\n"
        f"### Skills index\n{index}\n\n"
        f"### Skill contents\n{contents}\n"
    )
