"""Unit tests for OpenRouterProvider.health() — Phase 07.2.

Covers the cloud-aggregator surface added alongside Claude:
  - Identity (provider_id / display_name / auth_methods)
  - Missing key returns recommended free-model shortlist
  - 401 / non-200 responses are reported with PT-BR actionable messages
  - 200 response with the live-filter rules from `/models`:
      * `supported_parameters` empty -> excluded
      * `output_modalities` missing 'text' -> excluded
      * `max_tokens` missing from supported_parameters -> excluded
      * Surviving entries sorted with `:free` first
"""
from __future__ import annotations

import json

import pytest

from medieval_forge.services.llm.openrouter import (
    OpenRouterProvider,
    RECOMMENDED_FREE_MODELS,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, raw: bytes = b""):
        self.status_code = status_code
        self._payload = payload or {}
        self._raw = raw

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        return None


class _FakeAsyncClient:
    """Minimal httpx.AsyncClient stand-in. Override `_response` on subclass."""

    _response: _FakeResponse | None = None
    _raise: Exception | None = None
    last_url: str = ""
    last_headers: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None

    async def get(self, url: str, headers: dict | None = None):
        type(self).last_url = url
        type(self).last_headers = headers or {}
        if self._raise is not None:
            raise self._raise
        return self._response


def _patch_client(monkeypatch, client_cls) -> None:
    monkeypatch.setattr(
        "medieval_forge.services.llm.openrouter.httpx.AsyncClient", client_cls
    )


def test_openrouter_identity() -> None:
    provider = OpenRouterProvider()
    assert provider.provider_id == "openrouter"
    assert "OpenRouter" in provider.display_name
    assert len(provider.auth_methods) == 2


async def test_health_returns_recommended_when_no_key(monkeypatch) -> None:
    """No env var, no credentials -> ok=False + PT-BR hint + shortlist."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    provider = OpenRouterProvider()
    result = await provider.health(credentials=None)
    assert result["ok"] is False
    assert "OPENROUTER_API_KEY" in result["message"]
    assert result["available_models"] == list(RECOMMENDED_FREE_MODELS)


async def test_health_401_returns_actionable_message(monkeypatch) -> None:
    class _Client401(_FakeAsyncClient):
        _response = _FakeResponse(401)

    _patch_client(monkeypatch, _Client401)
    provider = OpenRouterProvider()
    result = await provider.health(credentials={"key": "bad"})
    assert result["ok"] is False
    assert "401" in result["message"]
    assert "OPENROUTER_API_KEY" in result["message"]
    assert result["available_models"] == list(RECOMMENDED_FREE_MODELS)


async def test_health_500_returns_generic_http_message(monkeypatch) -> None:
    class _Client500(_FakeAsyncClient):
        _response = _FakeResponse(500)

    _patch_client(monkeypatch, _Client500)
    provider = OpenRouterProvider()
    result = await provider.health(credentials={"key": "ok"})
    assert result["ok"] is False
    assert "500" in result["message"]


async def test_health_200_filters_live_models_and_sorts_free_first(monkeypatch) -> None:
    """Models without max_tokens / text modality / supported_parameters are dropped."""
    payload = {
        "data": [
            # KEEP — alive chat model with :free suffix
            {
                "id": "meta-llama/llama-3.2-3b-instruct:free",
                "supported_parameters": ["max_tokens", "temperature"],
                "architecture": {"output_modalities": ["text"]},
            },
            # KEEP — alive paid chat model
            {
                "id": "openai/gpt-4o",
                "supported_parameters": ["max_tokens", "tools"],
                "architecture": {"output_modalities": ["text"]},
            },
            # DROP — no supported_parameters (model offline)
            {
                "id": "deprecated/zombie",
                "supported_parameters": [],
                "architecture": {"output_modalities": ["text"]},
            },
            # DROP — image-only output
            {
                "id": "vision-only/model",
                "supported_parameters": ["max_tokens"],
                "architecture": {"output_modalities": ["image"]},
            },
            # DROP — completions-only (no max_tokens)
            {
                "id": "legacy/completions",
                "supported_parameters": ["temperature"],
                "architecture": {"output_modalities": ["text"]},
            },
        ]
    }

    class _Client200(_FakeAsyncClient):
        _response = _FakeResponse(200, payload=payload)

    _patch_client(monkeypatch, _Client200)
    provider = OpenRouterProvider()
    result = await provider.health(credentials={"key": "ok"})
    assert result["ok"] is True
    assert result["available_models"] == [
        "meta-llama/llama-3.2-3b-instruct:free",
        "openai/gpt-4o",
    ]
    assert "Conectado a OpenRouter" in result["message"]
    assert "2 modelos ativos" in result["message"]


async def test_health_request_exception_returns_unreachable(monkeypatch) -> None:
    class _ClientBoom(_FakeAsyncClient):
        _raise = ConnectionError("dns fail")

    _patch_client(monkeypatch, _ClientBoom)
    provider = OpenRouterProvider()
    result = await provider.health(credentials={"key": "x"})
    assert result["ok"] is False
    assert "inalcançável" in result["message"]


async def test_health_resolves_key_from_env_when_credentials_missing(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")

    captured: dict[str, str] = {}

    class _ClientCapture(_FakeAsyncClient):
        _response = _FakeResponse(200, payload={"data": []})

        async def get(self, url, headers=None):
            captured["auth"] = (headers or {}).get("Authorization", "")
            return self._response

    _patch_client(monkeypatch, _ClientCapture)
    provider = OpenRouterProvider()
    await provider.health(credentials=None)
    assert captured["auth"] == "Bearer env-key"
