"""Tests for the skills loader and system-prompt composition (no network)."""

from __future__ import annotations

from pi_agent.skills import Skill, build_system_prompt, load_skills, select_skills

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


def _skill(name: str, description: str = "", trigger: str = "", content: str = "BODY") -> Skill:
    return Skill(name=name, description=description, trigger=trigger, content=content)


class TestSelectSkills:
    SKILLS = [
        _skill("write-tests", "Write focused pytest tests", "asked for tests", "TESTS-BODY"),
        _skill("debug", "Find and fix bugs from a traceback", "an error occurs", "DEBUG-BODY"),
        _skill("make-deck", "Build a pptx slide deck", "asked for slides", "DECK-BODY"),
        _skill("refactor", "Restructure code safely", "asked to refactor", "REFACTOR-BODY"),
    ]

    def test_picks_most_relevant(self):
        chosen = select_skills("please write pytest tests for utils", self.SKILLS, top_k=1)
        assert [s.name for s in chosen] == ["write-tests"]

    def test_deterministic_tie_break_by_name(self):
        tied = [_skill("b-skill", "zzz"), _skill("a-skill", "zzz")]
        chosen = select_skills("zzz", tied + [_skill("c-skill", "qqq")], top_k=2)
        assert [s.name for s in chosen] == ["a-skill", "b-skill"]

    def test_zero_score_skills_excluded(self):
        chosen = select_skills("completely unrelated words here", self.SKILLS, top_k=2)
        assert chosen == []

    def test_top_k_zero_returns_all(self):
        assert select_skills("anything", self.SKILLS, top_k=0) == self.SKILLS

    def test_small_set_returned_whole(self):
        two = self.SKILLS[:2]
        assert select_skills("unrelated", two, top_k=3) == two


class TestRoutedSystemPrompt:
    def test_top_k_inlines_only_relevant_content_but_full_index(self):
        skills = TestSelectSkills.SKILLS
        prompt = build_system_prompt("BASE", skills, prompt="fix this bug traceback", top_k=1)
        assert "DEBUG-BODY" in prompt  # routed skill inlined
        assert "DECK-BODY" not in prompt  # unrelated content omitted
        assert "make-deck" in prompt  # but still listed in the index

    def test_top_k_zero_keeps_legacy_inline_all(self):
        skills = TestSelectSkills.SKILLS
        prompt = build_system_prompt("BASE", skills, prompt="", top_k=0)
        for s in skills:
            assert s.content in prompt
