"""Tests for the skills loader and system-prompt composition (no network)."""

from __future__ import annotations

from pi_agent.skills import build_system_prompt, load_skills

SKILL_MD = """\
---
name: write-tests
description: Write focused pytest tests.
trigger: when asked for tests
---
Read the module first, then cover happy path + one edge + one failure.
"""


def _make_skill(tmp_path, folder: str, text: str):
    d = tmp_path / folder
    d.mkdir()
    (d / "SKILL.md").write_text(text, encoding="utf-8")


class TestLoadSkills:
    def test_missing_dir_returns_empty(self, tmp_path):
        assert load_skills(tmp_path / "nope") == []
        assert load_skills(None) == []

    def test_parses_frontmatter_and_body(self, tmp_path):
        _make_skill(tmp_path, "write-tests", SKILL_MD)
        skills = load_skills(tmp_path)
        assert len(skills) == 1
        s = skills[0]
        assert s.name == "write-tests"
        assert s.description == "Write focused pytest tests."
        assert s.trigger == "when asked for tests"
        assert "happy path" in s.content
        assert "---" not in s.content  # frontmatter stripped

    def test_name_falls_back_to_folder(self, tmp_path):
        _make_skill(tmp_path, "refactor", "Just do safe refactors.")
        s = load_skills(tmp_path)[0]
        assert s.name == "refactor"
        assert s.content == "Just do safe refactors."

    def test_loads_multiple_sorted(self, tmp_path):
        _make_skill(tmp_path, "b-skill", "B body")
        _make_skill(tmp_path, "a-skill", "A body")
        names = [s.name for s in load_skills(tmp_path)]
        assert names == ["a-skill", "b-skill"]


class TestBuildSystemPrompt:
    def test_no_skills_returns_base(self):
        assert build_system_prompt("BASE", []) == "BASE"

    def test_inlines_index_and_contents(self, tmp_path):
        _make_skill(tmp_path, "write-tests", SKILL_MD)
        prompt = build_system_prompt("BASE", load_skills(tmp_path))
        assert prompt.startswith("BASE")
        assert "Skills index" in prompt
        assert "write-tests" in prompt
        assert "happy path" in prompt  # full content inlined
