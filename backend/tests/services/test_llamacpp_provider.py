"""Unit tests for LlamaCppProvider — local llama-server via OpenAI-compatible API.

Etapa 5 (hazy-hatching-abelson) / quick-260428-fjc.
Mocked-httpx style mirroring backend/tests/services/test_llm_providers.py.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from medieval_forge.services.llm.schemas import ResearchResult


_VALID_PAYLOAD = {
    "kingdoms": {"asturias": "Reino de Asturias"},
    "duchies": {"galicia": {"kingdom_id": "asturias", "name": "Ducado de Galicia"}},
    "condados": [
        {
            "id": "C_BRAGA",
            "name": "Condado de Braga",
            "lon": -8.43,
            "lat": 41.55,
            "kingdom_id": "asturias",
            "duchy_id": "galicia",
        },
    ],
    "baronies": {
        "C_BRAGA": [{"name": "Baronia de Braga", "lon": -8.43, "lat": 41.55}],
    },
}
_VALID_JSON = json.dumps(_VALID_PAYLOAD)


def _sse_chunks_for_json(content: str, n_splits: int = 3) -> list[str]:
    """Split `content` into n SSE 'data: {...}' lines mimicking llama.cpp/OpenAI streaming."""
    size = max(1, len(content) // n_splits)
    parts: list[str] = []
    for i in range(0, len(content), size):
        delta = content[i : i + size]
        chunk = {"choices": [{"delta": {"content": delta}}]}
        parts.append(f"data: {json.dumps(chunk)}")
    parts.append("data: [DONE]")
    return parts


class _FakeStreamResponse:
    """Fake httpx streaming response: async context manager + aiter_lines + raise_for_status."""

    def __init__(self, lines: list[str]):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeAsyncClient:
    """Fake httpx.AsyncClient capturing get/stream calls."""

    def __init__(self, *, get_result=None, get_exc=None, stream_lines=None):
        self.get_result = get_result
        self.get_exc = get_exc
        self.stream_lines = stream_lines or []
        self.captured: dict = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def get(self, url, *args, **kwargs):
        self.captured["get_url"] = url
        if self.get_exc is not None:
            raise self.get_exc
        return self.get_result

    def stream(self, method, url, **kwargs):
        self.captured["stream_method"] = method
        self.captured["stream_url"] = url
        self.captured["stream_kwargs"] = kwargs
        return _FakeStreamResponse(self.stream_lines)


# ─── Test 1 — health check OK ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_llamacpp_provider_health_check_calls_v1_models():
    """health_check(None) GETs {DEFAULT_BASE_URL}/v1/models and returns healthy=True on 200."""
    from medieval_forge.services.llm.llamacpp import LlamaCppProvider, DEFAULT_BASE_URL
    from medieval_forge.services.llm.base import HealthStatus

    fake_response = SimpleNamespace(status_code=200, json=lambda: {"data": [{"id": "llama-3"}]})
    fake_client = _FakeAsyncClient(get_result=fake_response)

    provider = LlamaCppProvider()
    with patch("medieval_forge.services.llm.llamacpp.httpx.AsyncClient", return_value=fake_client):
        status = await provider.health_check(None)

    assert isinstance(status, HealthStatus)
    assert status.healthy is True
    assert fake_client.captured["get_url"] == f"{DEFAULT_BASE_URL}/v1/models"


# ─── Test 2 — health check unreachable ────────────────────────────────────────

@pytest.mark.asyncio
async def test_llamacpp_provider_health_check_handles_unreachable_server():
    """health_check(None) returns healthy=False with 'Unreachable' message on ConnectError, no raise."""
    from medieval_forge.services.llm.llamacpp import LlamaCppProvider
    from medieval_forge.services.llm.base import HealthStatus

    fake_client = _FakeAsyncClient(get_exc=httpx.ConnectError("refused"))

    provider = LlamaCppProvider()
    with patch("medieval_forge.services.llm.llamacpp.httpx.AsyncClient", return_value=fake_client):
        status = await provider.health_check(None)

    assert isinstance(status, HealthStatus)
    assert status.healthy is False
    assert "Unreachable" in status.message or "refused" in status.message


# ─── Test 3 — research streaming, server-default model omitted ────────────────

@pytest.mark.asyncio
async def test_llamacpp_provider_research_posts_to_v1_chat_completions_with_streaming():
    """research() POSTs to /v1/chat/completions with messages=[system,user] + stream=True; omits 'model' for sentinel."""
    from medieval_forge.services.llm.llamacpp import LlamaCppProvider

    sse_lines = _sse_chunks_for_json(_VALID_JSON, n_splits=3)
    fake_client = _FakeAsyncClient(stream_lines=sse_lines)

    provider = LlamaCppProvider()
    with patch("medieval_forge.services.llm.llamacpp.httpx.AsyncClient", return_value=fake_client):
        result = await provider.research(
            "prompt-text",
            ResearchResult,
            {"base_url": "http://localhost:8080", "model": "(server-default)"},
            None,
        )

    assert isinstance(result, ResearchResult)
    assert result.kingdoms == {"asturias": "Reino de Asturias"}
    assert "C_BRAGA" in result.baronies

    assert fake_client.captured["stream_method"] == "POST"
    assert fake_client.captured["stream_url"] == "http://localhost:8080/v1/chat/completions"
    body = fake_client.captured["stream_kwargs"]["json"]
    assert body["stream"] is True
    assert isinstance(body["messages"], list) and len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1]["role"] == "user"
    assert body["messages"][1]["content"] == "prompt-text"
    # Sentinel "(server-default)" must NOT be sent as model field
    assert "model" not in body or body["model"] is None


# ─── Test 4 — base_url override ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_llamacpp_provider_research_uses_user_supplied_base_url_override():
    """research() honors credentials['base_url'] override (proves base_url wiring)."""
    from medieval_forge.services.llm.llamacpp import LlamaCppProvider

    sse_lines = _sse_chunks_for_json(_VALID_JSON, n_splits=2)
    fake_client = _FakeAsyncClient(stream_lines=sse_lines)

    provider = LlamaCppProvider()
    with patch("medieval_forge.services.llm.llamacpp.httpx.AsyncClient", return_value=fake_client):
        result = await provider.research(
            "prompt-text",
            ResearchResult,
            {"base_url": "http://10.0.0.5:9090"},
            None,
        )

    assert isinstance(result, ResearchResult)
    assert fake_client.captured["stream_url"].startswith("http://10.0.0.5:9090/v1/chat/completions")
