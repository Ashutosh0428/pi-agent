"""CLI provider/model resolution + onboarding tests — no API keys, no network."""

from __future__ import annotations

import pytest

import pi_agent.llm as llm
from pi_agent import __version__
from pi_agent.cli import main, resolve_selection
from pi_agent.llm import detect_provider

ALL_KEY_ENVS = [spec.key_env for spec in llm.PROVIDERS.values()]


@pytest.fixture()
def no_keys(monkeypatch):
    """Environment with every provider key unset and Ollama unreachable."""
    for var in [*ALL_KEY_ENVS, "PI_AGENT_MODEL"]:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(llm, "ollama_running", lambda **_: False)


# --- detect_provider ---------------------------------------------------------


def test_detect_prefers_paid_over_free():
    assert detect_provider({"ANTHROPIC_API_KEY": "a", "GROQ_API_KEY": "g"}) == "anthropic"


def test_detect_follows_declared_order():
    # gemini precedes groq in DETECTION_ORDER
    assert detect_provider({"GROQ_API_KEY": "g", "GEMINI_API_KEY": "y"}) == "gemini"


def test_detect_single_free_key():
    assert detect_provider({"ZAI_API_KEY": "z"}) == "glm"


def test_detect_nothing_configured(no_keys):
    assert detect_provider({}) is None


def test_detect_falls_back_to_running_ollama(monkeypatch):
    monkeypatch.setattr(llm, "ollama_running", lambda **_: True)
    assert detect_provider({}) == "ollama"


# --- resolve_selection -------------------------------------------------------


def test_resolve_explicit_model_wins(no_keys):
    assert resolve_selection(None, "gpt-4o") == ("openai", "gpt-4o")


def test_resolve_provider_without_model_uses_its_default(no_keys):
    assert resolve_selection("groq", None) == ("groq", llm.PROVIDERS["groq"].default_model)


def test_resolve_env_model_counts_as_explicit(no_keys, monkeypatch):
    monkeypatch.setenv("PI_AGENT_MODEL", "glm-4.5-flash")
    assert resolve_selection(None, None) == ("glm", "glm-4.5-flash")


def test_resolve_detects_free_key(no_keys, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    assert resolve_selection(None, None) == ("groq", llm.PROVIDERS["groq"].default_model)


def test_resolve_nothing_configured(no_keys):
    assert resolve_selection(None, None) == (None, "")


# --- main() ------------------------------------------------------------------


def test_main_without_keys_shows_free_onboarding(no_keys, capsys):
    assert main([]) == 1
    err = capsys.readouterr().err
    assert "quick setup" in err
    assert "GROQ_API_KEY" in err
    assert "Ollama" in err


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out
