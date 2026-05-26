"""Unit tests for OpenAIProvider.health() — Phase 07.2.

Covers:
  - Identity (provider_id / display_name / auth_methods)
  - Missing key returns RECOMMENDED_MODELS shortlist + PT-BR hint
  - 401 surfaces an actionable PT-BR message
  - 200 filters /models to chat-completion families (gpt-/o1-/o3-)
  - Request exception surfaces 'inalcançável'
"""
from __future__ import annotations

import pytest

from medieval_forge.services.llm.openai_provider import (
    OpenAIProvider,
    RECOMMENDED_MODELS,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        return None


class _FakeAsyncClient:
    _response: _FakeResponse | None = None
    _raise: Exception | None = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None

    async def get(self, url: str, headers: dict | None = None):
        if self._raise is not None:
            raise self._raise
        return self._response


def _patch_client(monkeypatch, client_cls) -> None:
    monkeypatch.setattr(
        "medieval_forge.services.llm.openai_provider.httpx.AsyncClient", client_cls
    )


def test_openai_identity() -> None:
    provider = OpenAIProvider()
    assert provider.provider_id == "openai"
    assert "OpenAI" in provider.display_name


async def test_health_no_key_returns_recommended(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAIProvider()
    result = await provider.health(credentials=None)
    assert result["ok"] is False
    assert "OPENAI_API_KEY" in result["message"]
    assert result["available_models"] == list(RECOMMENDED_MODELS)


async def test_health_401_returns_actionable_message(monkeypatch) -> None:
    class _Client401(_FakeAsyncClient):
        _response = _FakeResponse(401)

    _patch_client(monkeypatch, _Client401)
    provider = OpenAIProvider()
    result = await provider.health(credentials={"key": "bad"})
    assert result["ok"] is False
    assert "401" in result["message"]
    assert "OPENAI_API_KEY" in result["message"]


async def test_health_200_filters_to_chat_families(monkeypatch) -> None:
    payload = {
        "data": [
            {"id": "gpt-4o"},
            {"id": "gpt-4o-mini"},
            {"id": "o1-preview"},
            {"id": "o3-mini"},
            {"id": "whisper-1"},        # drop — not chat
            {"id": "text-embedding-3"}, # drop — not chat
            {"id": "dall-e-3"},         # drop — not chat
        ]
    }

    class _Client200(_FakeAsyncClient):
        _response = _FakeResponse(200, payload=payload)

    _patch_client(monkeypatch, _Client200)
    provider = OpenAIProvider()
    result = await provider.health(credentials={"key": "ok"})
    assert result["ok"] is True
    chat = result["available_models"]
    assert "gpt-4o" in chat
    assert "gpt-4o-mini" in chat
    assert "o1-preview" in chat
    assert "o3-mini" in chat
    assert "whisper-1" not in chat
    assert "text-embedding-3" not in chat
    assert "dall-e-3" not in chat


async def test_health_unreachable_returns_pt_br_message(monkeypatch) -> None:
    class _ClientBoom(_FakeAsyncClient):
        _raise = ConnectionError("dns fail")

    _patch_client(monkeypatch, _ClientBoom)
    provider = OpenAIProvider()
    result = await provider.health(credentials={"key": "x"})
    assert result["ok"] is False
    assert "inalcançável" in result["message"]


async def test_health_500_returns_http_message(monkeypatch) -> None:
    class _Client500(_FakeAsyncClient):
        _response = _FakeResponse(500)

    _patch_client(monkeypatch, _Client500)
    provider = OpenAIProvider()
    result = await provider.health(credentials={"key": "ok"})
    assert result["ok"] is False
    assert "500" in result["message"]
