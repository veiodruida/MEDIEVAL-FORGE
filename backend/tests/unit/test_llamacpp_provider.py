"""SC-3a..c + review-fix #7 + review-fix #8 — 11 tests for LlamaCppProvider.

Plan 07.1-03 (Wave 2). Replaces Wave 0 scaffold (all @pytest.mark.skip removed).

Tests cover:
  - SC-3a identity (provider_id, display_name, auth_methods)
  - SC-3b health() shape variants (missing binary, idle server, live server, gguf listing)
  - SC-3c research() streaming via httpx + queue
  - review-fix #7: partial SSE buffering, malformed SSE error, final payload shape
  - review-fix #8: no-launcher-state raises LlamaCppProviderError (no silent localhost:8080)
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from medieval_forge.services.llm.llamacpp import LlamaCppProvider, LlamaCppProviderError
from medieval_forge.services.llm.llamacpp_launcher import _reset_state_for_tests


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_launcher():
    """Ensure launcher module state is clean before and after each test."""
    _reset_state_for_tests()
    yield
    _reset_state_for_tests()


@pytest.fixture
def models_dir_with_files(tmp_path, monkeypatch):
    """Set MEDIEVAL_FORGE_LLAMACPP_MODELS_DIR to a tmp_path controlled by us."""
    monkeypatch.setenv("MEDIEVAL_FORGE_LLAMACPP_MODELS_DIR", str(tmp_path))
    monkeypatch.setenv("MEDIEVAL_FORGE_LLAMACPP_EXTRA_DIRS", "")
    return tmp_path


@pytest.fixture
def fake_binary(monkeypatch):
    """Ensure LLAMA_SERVER_BIN points to a fake path so _resolve_binary() is non-None."""
    monkeypatch.setenv("LLAMA_SERVER_BIN", "/fake/llama-server")


# ---------------------------------------------------------------------------
# Test 1: SC-3a identity
# ---------------------------------------------------------------------------


def test_llamacpp_provider_provider_id_is_llamacpp() -> None:
    """SC-3a: provider_id, display_name, and single NoAuth auth_method."""
    from medieval_forge.services.llm.base import NoAuth

    provider = LlamaCppProvider()
    assert provider.provider_id == "llamacpp"
    assert provider.display_name == "Llama.cpp (local)"
    assert len(provider.auth_methods) == 1
    assert isinstance(provider.auth_methods[0], NoAuth)


# ---------------------------------------------------------------------------
# Tests 2-5: SC-3b health() shape
# ---------------------------------------------------------------------------


async def test_health_empty_models_dir_returns_empty_list(
    models_dir_with_files, fake_binary
) -> None:
    """Test 2: empty tmp dir -> available_models == [] and ok=False (server idle)."""
    # Monkeypatch status() to return None (server idle) so we hit the idle branch
    with patch("medieval_forge.services.llm.llamacpp.status", return_value=None):
        provider = LlamaCppProvider()
        result = await provider.health()

    assert result["available_models"] == []
    assert result["ok"] is False
    assert "não está ativo" in result["message"]


async def test_health_lists_only_gguf_alphabetical_with_3_files_plus_txt_noise(
    models_dir_with_files, fake_binary
) -> None:
    """Test 3: tmp_path with c.gguf, a.gguf, b.gguf, noise.txt -> sorted gguf list only."""
    (models_dir_with_files / "c.gguf").write_text("fake")
    (models_dir_with_files / "a.gguf").write_text("fake")
    (models_dir_with_files / "b.gguf").write_text("fake")
    (models_dir_with_files / "noise.txt").write_text("ignored")

    with patch("medieval_forge.services.llm.llamacpp.status", return_value=None):
        provider = LlamaCppProvider()
        result = await provider.health()

    basenames = [p.split("\\")[-1].split("/")[-1] for p in result["available_models"]]
    assert basenames == ["a.gguf", "b.gguf", "c.gguf"]


async def test_health_case_insensitive_suffix_GGUF_uppercase(
    models_dir_with_files, fake_binary
) -> None:
    """Test 4: X.GGUF (uppercase) -> included in available_models."""
    (models_dir_with_files / "X.GGUF").write_text("fake")

    with patch("medieval_forge.services.llm.llamacpp.status", return_value=None):
        provider = LlamaCppProvider()
        result = await provider.health()

    basenames = [p.split("\\")[-1].split("/")[-1] for p in result["available_models"]]
    assert "X.GGUF" in basenames


async def test_health_missing_binary_returns_ok_false_with_pt_br_message(
    models_dir_with_files, monkeypatch
) -> None:
    """Test 5: _resolve_binary() returns None -> ok=False, PT-BR message contains 'llama-server'
    AND 'não encontrado'."""
    # Ensure LLAMA_SERVER_BIN is unset so _resolve_binary falls back to shutil.which
    monkeypatch.delenv("LLAMA_SERVER_BIN", raising=False)
    # Monkeypatch shutil.which to return None (binary not found)
    with patch("medieval_forge.services.llm.llamacpp_launcher.shutil.which", return_value=None):
        provider = LlamaCppProvider()
        result = await provider.health()

    assert result["ok"] is False
    assert "llama-server" in result["message"]
    assert "não encontrado" in result["message"]


async def test_health_running_server_returns_ok_true_with_base_url(
    models_dir_with_files, fake_binary, monkeypatch
) -> None:
    """Test 6: launcher.status() returns live dict and /v1/models returns 200
    -> ok=True + 'Reachable at ...' message."""
    live_status = {
        "pid": 12345,
        "model": "mistral-7b.gguf",
        "base_url": "http://127.0.0.1:38291",
        "started_at": "2026-05-16T10:00:00Z",
    }

    class _FakeGetResponse:
        status_code = 200

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def get(self, url: str):
            return _FakeGetResponse()

    with (
        patch("medieval_forge.services.llm.llamacpp.status", return_value=live_status),
        patch("medieval_forge.services.llm.llamacpp.httpx.AsyncClient", _FakeAsyncClient),
    ):
        provider = LlamaCppProvider()
        result = await provider.health()

    assert result["ok"] is True
    assert "Reachable at http://127.0.0.1:38291" in result["message"]
    # available_models populated from filesystem (may be empty if dir empty, but key present)
    assert "available_models" in result


# ---------------------------------------------------------------------------
# Tests 7-10: SC-3c research() streaming
# ---------------------------------------------------------------------------


def _make_sse_line(content_delta: str) -> str:
    """Build a well-formed SSE data line from a delta string."""
    payload = json.dumps({"choices": [{"delta": {"content": content_delta}}]})
    return f"data: {payload}"


def _make_done_line() -> str:
    return "data: [DONE]"


async def _collect_queue(queue: asyncio.Queue, timeout: float = 2.0) -> list:
    """Drain an asyncio.Queue into a list, stopping at None sentinel."""
    items = []
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            break
        try:
            item = await asyncio.wait_for(queue.get(), timeout=remaining)
        except asyncio.TimeoutError:
            break
        if item is None:
            items.append(None)
            break
        items.append(item)
    return items


def _make_non_stream_response(content: str):
    """Build a fake httpx response object exposing .raise_for_status + .json().

    UAT 2026-05-22: provider switched from SSE streaming to a single
    `client.post()` call because llama-server occasionally never emits the
    SSE `[DONE]` sentinel, leaving aiter_lines() blocked forever. Tests
    follow the new shape: one full response body matching the OpenAI
    chat-completion contract.
    """

    class _FakeResp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [
                    {"message": {"role": "assistant", "content": content}}
                ]
            }

    return _FakeResp()


def _fake_async_client_factory(response_obj):
    """Build a fake httpx.AsyncClient class returning `response_obj` from post()."""

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, url, json=None, **kwargs):
            return response_obj

    return _FakeAsyncClient


async def test_research_via_httpx_post_returns_parsed_result(monkeypatch) -> None:
    """Provider posts a single chat-completion request and parses the
    `choices[0].message.content` as ResearchResult JSON."""
    research_json = '{"kingdoms": {}, "duchies": {}, "condados": [], "baronies": {}}'
    fake_client = _fake_async_client_factory(_make_non_stream_response(research_json))

    queue: asyncio.Queue = asyncio.Queue()
    provider = LlamaCppProvider()
    provider._test_only_base_url = "http://127.0.0.1:38291"

    from medieval_forge.services.llm.schemas import ResearchResult

    with patch("medieval_forge.services.llm.llamacpp.httpx.AsyncClient", fake_client):
        result = await provider.research(
            prompt="Test prompt",
            schema=ResearchResult,
            credentials={"model": "test.gguf"},
            queue=queue,
        )

    # `started` envelope must land on the queue at least once.
    items: list = []
    while not queue.empty():
        items.append(queue.get_nowait())
    assert len(items) >= 1
    assert isinstance(result, ResearchResult)


async def test_research_rejects_malformed_response_body(monkeypatch) -> None:
    """A non-JSON response body raises LlamaCppProviderError (typed)."""

    class _BadResp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            raise ValueError("not json")

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def post(self, url, json=None, **kwargs):
            return _BadResp()

    queue: asyncio.Queue = asyncio.Queue()
    provider = LlamaCppProvider()
    provider._test_only_base_url = "http://127.0.0.1:38291"

    from medieval_forge.services.llm.schemas import ResearchResult

    with (
        patch("medieval_forge.services.llm.llamacpp.httpx.AsyncClient", _FakeAsyncClient),
        pytest.raises(LlamaCppProviderError),
    ):
        await provider.research(
            prompt="Test malformed body",
            schema=ResearchResult,
            credentials={"model": "test.gguf"},
            queue=queue,
        )


async def test_research_final_payload_extraction_matches_claude_ollama_shape(
    monkeypatch,
) -> None:
    """Well-formed chat-completion body yields a ResearchResult shape identical
    to Ollama provider output for the same prompt."""
    research_json = json.dumps(
        {"kingdoms": {}, "duchies": {}, "condados": [], "baronies": {}}
    )
    fake_client = _fake_async_client_factory(_make_non_stream_response(research_json))

    queue: asyncio.Queue = asyncio.Queue()
    provider = LlamaCppProvider()
    provider._test_only_base_url = "http://127.0.0.1:38291"

    from medieval_forge.services.llm.schemas import ResearchResult

    with patch("medieval_forge.services.llm.llamacpp.httpx.AsyncClient", fake_client):
        result = await provider.research(
            prompt="Test final payload",
            schema=ResearchResult,
            credentials={"model": "test.gguf"},
            queue=queue,
        )

    # Structural comparison with Ollama's expected output shape:
    # Ollama.research also returns ResearchResult (same type check)
    assert isinstance(result, ResearchResult), (
        f"Expected ResearchResult, got {type(result)}"
    )
    # Key-level comparison: ResearchResult has kingdoms, duchies, condados, baronies
    assert hasattr(result, "kingdoms")
    assert hasattr(result, "duchies")
    assert hasattr(result, "condados")
    assert hasattr(result, "baronies")
    assert isinstance(result.kingdoms, dict)
    assert isinstance(result.duchies, dict)
    assert isinstance(result.condados, list)
    assert isinstance(result.baronies, dict)


# ---------------------------------------------------------------------------
# Test 11: review-fix #8 — no launcher state -> raises (no silent fallback)
# ---------------------------------------------------------------------------


async def test_provider_raises_when_no_launcher_state() -> None:
    """Test 11 (review-fix #8): research() with idle launcher raises LlamaCppProviderError.

    The provider MUST NOT silently target http://localhost:8080.
    _reset_state_for_tests() ensures no live PID. No _test_only_base_url set.
    """
    # _reset_state_for_tests() already called by autouse fixture
    provider = LlamaCppProvider()
    # Do NOT set provider._test_only_base_url — must go through launcher.status()

    from medieval_forge.services.llm.schemas import ResearchResult

    queue: asyncio.Queue = asyncio.Queue()
    with pytest.raises(LlamaCppProviderError, match="no llama-server alive"):
        await provider.research(
            prompt="Will not reach server",
            schema=ResearchResult,
            credentials={"model": "test.gguf"},
            queue=queue,
        )
