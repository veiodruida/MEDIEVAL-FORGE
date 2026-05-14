# Plan 07-04 Task 1 — integration tests for the Claude D-07 auth chain.
#
# Per WARNING 6: these tests use mocks (no live network) but are gated by the
# `anthropic` pytest marker (registered in pyproject.toml) so they only run
# when the suite is invoked with `pytest -m anthropic`. They MUST RUN, not skip.
#
# BLOCKER 1: black-box on ClaudeProvider.research(). Test 2 + Test 5 exercise
# the 401-retry-with-skip_cli=True fallback inside the provider.
"""D-07 Claude auth chain integration tests (CLI -> DB -> env -> dialog) + BLOCKER 1 401-retry."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest

from medieval_forge.services.llm.claude import ClaudeProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeToolBlock:
    """Minimal stand-in for an Anthropic tool_use content block."""

    def __init__(self, payload: dict) -> None:
        self.type = "tool_use"
        self.input = payload


class _FakeFinalMessage:
    def __init__(self, payload: dict) -> None:
        self.content = [_FakeToolBlock(payload)]


class _FakeStream:
    """Minimal async-context-manager replacement for AsyncAnthropic.messages.stream."""

    def __init__(self, payload: dict, raise_on_enter: Exception | None = None) -> None:
        self._payload = payload
        self._raise = raise_on_enter

        async def _empty_iter():
            if False:
                yield ""

        self.text_stream = _empty_iter()

    async def __aenter__(self):
        if self._raise is not None:
            raise self._raise
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get_final_message(self):
        return _FakeFinalMessage(self._payload)


def _make_async_anthropic_factory(streams: list):
    """Build a fake AsyncAnthropic class that yields the supplied streams in order."""

    calls = {"count": 0}

    class _FakeMessages:
        def stream(self, **kwargs):
            idx = calls["count"]
            calls["count"] += 1
            return streams[idx]

    class _FakeAsyncAnthropic:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.messages = _FakeMessages()

    return _FakeAsyncAnthropic, calls


class _FakeSchema:
    """Minimal schema with model_json_schema() + model_validate() for tool_use return."""

    @classmethod
    def model_json_schema(cls) -> dict:
        return {"type": "object", "properties": {}}

    @classmethod
    def model_validate(cls, data: dict):
        return data


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.anthropic
async def test_claude_auth_chain_uses_cli_token_when_claude_auth_status_exits_zero():
    """Test 1: CLI succeeds -> CLI token is used; AsyncAnthropic is called with CLI key."""
    provider = ClaudeProvider()
    fake_cls, calls = _make_async_anthropic_factory([
        _FakeStream({"ok": "yes"}),
    ])

    with patch.object(ClaudeProvider, "_resolve_key", wraps=provider._resolve_key) as spy, \
         patch("medieval_forge.services.llm.claude._read_claude_cli_token", return_value="cli-token-abc"), \
         patch("medieval_forge.services.llm.claude.AsyncAnthropic", fake_cls):
        result = await provider.research("prompt", _FakeSchema, None, None)

    assert result == {"ok": "yes"}
    # _resolve_key must have been called at least once with skip_cli=False.
    skip_cli_kwargs = [
        c.kwargs.get("skip_cli", c.args[1] if len(c.args) > 1 else None)
        for c in spy.call_args_list
    ]
    assert False in skip_cli_kwargs or None in skip_cli_kwargs
    assert calls["count"] == 1


@pytest.mark.anthropic
async def test_claude_auth_chain_falls_through_to_db_when_cli_token_rejected_with_401():
    """Test 2 (BLOCKER 1): first call (CLI token) raises 401 -> retry with skip_cli=True succeeds."""
    provider = ClaudeProvider()

    # First .stream() raises AuthenticationError on __aenter__; second succeeds.
    auth_err = anthropic.AuthenticationError.__new__(anthropic.AuthenticationError)
    auth_err.args = ("401 Unauthorized",)
    fake_cls, calls = _make_async_anthropic_factory([
        _FakeStream({}, raise_on_enter=auth_err),
        _FakeStream({"ok": "from-db"}),
    ])

    db_payload = {"key": "db-api-key-xyz"}
    resolve_spy = MagicMock(side_effect=["cli-token", "db-api-key-xyz"])

    with patch.object(ClaudeProvider, "_resolve_key", resolve_spy), \
         patch("medieval_forge.services.llm.claude.AsyncAnthropic", fake_cls):
        result = await provider.research("p", _FakeSchema, db_payload, None)

    assert result == {"ok": "from-db"}
    # Called twice: first skip_cli=False, then skip_cli=True
    assert resolve_spy.call_count == 2
    first_call = resolve_spy.call_args_list[0]
    second_call = resolve_spy.call_args_list[1]
    assert first_call.kwargs.get("skip_cli") is False or False in first_call.args
    assert second_call.kwargs.get("skip_cli") is True or True in second_call.args
    assert calls["count"] == 2


@pytest.mark.anthropic
async def test_claude_auth_chain_falls_through_to_env_when_cli_and_db_empty(monkeypatch):
    """Test 3: no CLI, no DB -> ANTHROPIC_API_KEY env is used."""
    provider = ClaudeProvider()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key-123")

    fake_cls, calls = _make_async_anthropic_factory([
        _FakeStream({"ok": "from-env"}),
    ])
    with patch("medieval_forge.services.llm.claude._read_claude_cli_token", return_value=None), \
         patch("medieval_forge.services.llm.claude.AsyncAnthropic", fake_cls):
        result = await provider.research("p", _FakeSchema, None, None)

    assert result == {"ok": "from-env"}
    assert calls["count"] == 1


@pytest.mark.anthropic
async def test_claude_resolve_key_returns_none_when_chain_bottoms_out(monkeypatch):
    """Test 4: no CLI, no DB, no env -> _resolve_key returns None."""
    provider = ClaudeProvider()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with patch("medieval_forge.services.llm.claude._read_claude_cli_token", return_value=None):
        assert provider._resolve_key(None, skip_cli=False) is None
        assert provider._resolve_key({}, skip_cli=False) is None
        assert provider._resolve_key(None, skip_cli=True) is None


@pytest.mark.anthropic
async def test_claude_research_raises_when_both_cli_and_db_keys_yield_401():
    """Test 5 (BLOCKER 1): CLI key + DB key both raise 401 -> RuntimeError propagates."""
    provider = ClaudeProvider()
    auth_err_a = anthropic.AuthenticationError.__new__(anthropic.AuthenticationError)
    auth_err_a.args = ("401 first",)
    auth_err_b = anthropic.AuthenticationError.__new__(anthropic.AuthenticationError)
    auth_err_b.args = ("401 second",)

    fake_cls, calls = _make_async_anthropic_factory([
        _FakeStream({}, raise_on_enter=auth_err_a),
        _FakeStream({}, raise_on_enter=auth_err_b),
    ])
    resolve_spy = MagicMock(side_effect=["cli-token", "db-key"])

    with patch.object(ClaudeProvider, "_resolve_key", resolve_spy), \
         patch("medieval_forge.services.llm.claude.AsyncAnthropic", fake_cls):
        with pytest.raises(anthropic.AuthenticationError):
            await provider.research("p", _FakeSchema, {"key": "db-key"}, None)

    assert resolve_spy.call_count == 2
    assert calls["count"] == 2
