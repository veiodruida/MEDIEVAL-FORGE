"""UAT 2026-05-23 — `.env` parser unit tests.

Covers the shapes the user can actually paste into the upload box: bare
KEY=VALUE, `export KEY=VALUE`, single/double quoted values, comments,
unknown vars, blank values, duplicate keys (last wins).
"""
from __future__ import annotations

import pytest

from medieval_forge.services.llm.dotenv_import import (
    ENV_VAR_TO_PROVIDER,
    known_env_vars,
    parse_dotenv,
)


def test_known_env_vars_includes_all_major_clouds() -> None:
    """All shipping cloud providers must be mappable from a `.env`."""
    names = set(known_env_vars())
    assert "ANTHROPIC_API_KEY" in names
    assert "OPENROUTER_API_KEY" in names
    assert "OPENAI_API_KEY" in names
    assert "GOOGLE_API_KEY" in names or "GEMINI_API_KEY" in names


def test_parse_dotenv_basic_pairs() -> None:
    text = (
        "ANTHROPIC_API_KEY=sk-ant-abc\n"
        "OPENROUTER_API_KEY=sk-or-xyz\n"
    )
    out = parse_dotenv(text)
    assert out["claude"] == "sk-ant-abc"
    assert out["openrouter"] == "sk-or-xyz"


def test_parse_dotenv_strips_quotes() -> None:
    text = (
        'ANTHROPIC_API_KEY="sk-ant-abc"\n'
        "OPENROUTER_API_KEY='sk-or-xyz'\n"
    )
    out = parse_dotenv(text)
    assert out["claude"] == "sk-ant-abc"
    assert out["openrouter"] == "sk-or-xyz"


def test_parse_dotenv_accepts_export_prefix() -> None:
    text = "export ANTHROPIC_API_KEY=sk-ant-abc\n"
    assert parse_dotenv(text)["claude"] == "sk-ant-abc"


def test_parse_dotenv_ignores_comments_and_blanks() -> None:
    text = (
        "# this is a comment\n"
        "\n"
        "ANTHROPIC_API_KEY=sk-ant-abc\n"
        "# OPENROUTER_API_KEY=fake\n"
    )
    out = parse_dotenv(text)
    assert out == {"claude": "sk-ant-abc"}


def test_parse_dotenv_ignores_unknown_keys() -> None:
    text = "FOO_BAR_KEY=should-not-leak\nANTHROPIC_API_KEY=sk-ant-abc\n"
    out = parse_dotenv(text)
    assert "foo_bar_key" not in out
    assert out["claude"] == "sk-ant-abc"


def test_parse_dotenv_empty_value_dropped() -> None:
    """Empty values are treated as 'no key', NOT persisted as blanks."""
    text = "ANTHROPIC_API_KEY=\n"
    assert parse_dotenv(text) == {}


def test_parse_dotenv_last_write_wins_for_gemini_aliases() -> None:
    """When both GOOGLE_API_KEY and GEMINI_API_KEY are set, the LAST line wins."""
    text = "GOOGLE_API_KEY=first\nGEMINI_API_KEY=second\n"
    out = parse_dotenv(text)
    assert out["gemini"] == "second"


def test_parse_dotenv_strips_inline_comments() -> None:
    text = "ANTHROPIC_API_KEY=sk-ant-abc # comment\n"
    assert parse_dotenv(text)["claude"] == "sk-ant-abc"


@pytest.mark.parametrize(
    "env_var, expected_provider",
    [
        ("ANTHROPIC_API_KEY", "claude"),
        ("OPENROUTER_API_KEY", "openrouter"),
        ("OPENAI_API_KEY", "openai"),
        ("GOOGLE_API_KEY", "gemini"),
        ("GEMINI_API_KEY", "gemini"),
    ],
)
def test_env_var_to_provider_mapping(env_var: str, expected_provider: str) -> None:
    assert ENV_VAR_TO_PROVIDER[env_var] == expected_provider
