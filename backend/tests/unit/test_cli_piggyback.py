"""Tests for CLI credential piggyback and resolve_credentials priority chain.

Covers:
- read_claude_cli_token() with missing/valid/expired/malformed files
- resolve_credentials() priority ordering per D-10..D-13
"""
from __future__ import annotations

import json
import pathlib
import time
import pytest


# ---------------------------------------------------------------------------
# read_claude_cli_token tests
# ---------------------------------------------------------------------------


def test_read_claude_cli_token_returns_none_when_no_file(tmp_path, monkeypatch):
    """No credential file → None."""
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: tmp_path))

    from medieval_forge.services.llm import auth as auth_mod
    import importlib
    importlib.reload(auth_mod)

    assert auth_mod.read_claude_cli_token() is None


def test_read_claude_cli_token_returns_token_when_valid(tmp_path, monkeypatch):
    """Valid, non-expired credential file → returns accessToken."""
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: tmp_path))

    creds_dir = tmp_path / ".claude"
    creds_dir.mkdir(parents=True)
    creds_file = creds_dir / ".credentials.json"
    expires_at_ms = int((time.time() + 3600) * 1000)
    creds_file.write_text(
        json.dumps({
            "claudeAiOauth": {
                "accessToken": "sk-ant-oat01-valid",
                "expiresAt": expires_at_ms,
            }
        }),
        encoding="utf-8",
    )

    from medieval_forge.services.llm import auth as auth_mod
    import importlib
    importlib.reload(auth_mod)

    assert auth_mod.read_claude_cli_token() == "sk-ant-oat01-valid"


def test_read_claude_cli_token_returns_none_when_expired(tmp_path, monkeypatch):
    """Token expiresAt in the past → None."""
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: tmp_path))

    creds_dir = tmp_path / ".claude"
    creds_dir.mkdir(parents=True)
    creds_file = creds_dir / ".credentials.json"
    expired_ms = int((time.time() - 3600) * 1000)
    creds_file.write_text(
        json.dumps({
            "claudeAiOauth": {
                "accessToken": "sk-ant-oat01-expired",
                "expiresAt": expired_ms,
            }
        }),
        encoding="utf-8",
    )

    from medieval_forge.services.llm import auth as auth_mod
    import importlib
    importlib.reload(auth_mod)

    assert auth_mod.read_claude_cli_token() is None


def test_read_claude_cli_token_handles_malformed_json(tmp_path, monkeypatch):
    """Malformed JSON file → None (no exception raised)."""
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: tmp_path))

    creds_dir = tmp_path / ".claude"
    creds_dir.mkdir(parents=True)
    creds_file = creds_dir / ".credentials.json"
    creds_file.write_text("{ not valid json }", encoding="utf-8")

    from medieval_forge.services.llm import auth as auth_mod
    import importlib
    importlib.reload(auth_mod)

    result = auth_mod.read_claude_cli_token()
    assert result is None


# ---------------------------------------------------------------------------
# resolve_credentials tests
# ---------------------------------------------------------------------------


def test_resolve_credentials_priority_session_over_env(monkeypatch):
    """Session credential wins over env var (D-10)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key-should-not-win")

    from medieval_forge.services.llm.auth import resolve_credentials

    class FakeState:
        credentials = {"claude": {"type": "api_key", "key": "session-key", "source": "session"}}

    result = resolve_credentials("claude", FakeState())
    assert result["key"] == "session-key"
    assert result["source"] == "session"


def test_resolve_credentials_priority_env_over_cli(monkeypatch):
    """Env var wins when no session; CLI file is NOT consulted (D-10)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key-wins")

    import medieval_forge.services.llm.auth as auth_mod

    def should_not_be_called():
        raise AssertionError("CLI token should not be read when env var is set")

    monkeypatch.setattr(auth_mod, "read_claude_cli_token", should_not_be_called)

    class FakeState:
        credentials: dict = {}

    result = auth_mod.resolve_credentials("claude", FakeState())
    assert result["source"] == "env"
    assert result["key"] == "env-key-wins"


def test_resolve_credentials_falls_through_to_cli(monkeypatch, tmp_path):
    """No session, no env → CLI token returned with source=='cli' (D-10)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: tmp_path))

    creds_dir = tmp_path / ".claude"
    creds_dir.mkdir(parents=True)
    creds_file = creds_dir / ".credentials.json"
    creds_file.write_text(
        json.dumps({
            "claudeAiOauth": {
                "accessToken": "sk-ant-oat01-cli-token",
                "expiresAt": int((time.time() + 3600) * 1000),
            }
        }),
        encoding="utf-8",
    )

    from medieval_forge.services.llm import auth as auth_mod
    import importlib
    importlib.reload(auth_mod)

    class FakeState:
        credentials: dict = {}

    result = auth_mod.resolve_credentials("claude", FakeState())
    assert result["source"] == "cli"
    assert result["key"] == "sk-ant-oat01-cli-token"
