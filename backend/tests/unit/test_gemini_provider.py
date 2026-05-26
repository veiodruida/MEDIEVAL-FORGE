"""Unit tests for GeminiProvider.health() — Phase 07.2.

Covers:
  - Identity (provider_id / display_name / 3 auth_methods incl. GEMINI_API_KEY alias)
  - Missing key returns RECOMMENDED_MODELS shortlist + PT-BR hint
  - 401 / 403 surface 'rejeitada' actionable message
  - 200 filters models to documented gemini-* families AND drops
    antigravity / preview-tts / audio variants
  - Ranking puts pro families before flash before rest
  - Models without `generateContent` are dropped
"""
from __future__ import annotations

import pytest

from medieval_forge.services.llm.gemini import (
    GeminiProvider,
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
        "medieval_forge.services.llm.gemini.httpx.AsyncClient", client_cls
    )


def test_gemini_identity() -> None:
    provider = GeminiProvider()
    assert provider.provider_id == "gemini"
    assert "Gemini" in provider.display_name
    assert len(provider.auth_methods) == 3


async def test_health_no_key_returns_recommended(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = GeminiProvider()
    result = await provider.health(credentials=None)
    assert result["ok"] is False
    assert "GOOGLE_API_KEY" in result["message"]
    assert result["available_models"] == list(RECOMMENDED_MODELS)


async def test_health_401_returns_rejected_message(monkeypatch) -> None:
    class _Client401(_FakeAsyncClient):
        _response = _FakeResponse(401)

    _patch_client(monkeypatch, _Client401)
    provider = GeminiProvider()
    result = await provider.health(credentials={"key": "bad"})
    assert result["ok"] is False
    assert "rejeitada" in result["message"]
    assert "401" in result["message"]


async def test_health_403_returns_rejected_message(monkeypatch) -> None:
    class _Client403(_FakeAsyncClient):
        _response = _FakeResponse(403)

    _patch_client(monkeypatch, _Client403)
    provider = GeminiProvider()
    result = await provider.health(credentials={"key": "bad"})
    assert result["ok"] is False
    assert "rejeitada" in result["message"]
    assert "403" in result["message"]


async def test_health_200_filters_to_gemini_family_and_ranks(monkeypatch) -> None:
    """Drop antigravity/audio variants, keep gemini-1.5/2.* and rank pro > flash."""
    payload = {
        "models": [
            {
                "name": "models/gemini-1.5-flash",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                "name": "models/gemini-1.5-pro",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                "name": "models/gemini-2.0-flash-exp",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                # DROP — antigravity preview
                "name": "models/gemini-antigravity-preview-1",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                # DROP — audio preview
                "name": "models/gemini-2.5-flash-audio",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                # DROP — preview-tts
                "name": "models/gemini-flash-preview-tts-1",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                # DROP — embedding only (no generateContent)
                "name": "models/embedding-001",
                "supportedGenerationMethods": ["embedContent"],
            },
            {
                # DROP — non-gemini prefix
                "name": "models/text-bison",
                "supportedGenerationMethods": ["generateContent"],
            },
        ]
    }

    class _Client200(_FakeAsyncClient):
        _response = _FakeResponse(200, payload=payload)

    _patch_client(monkeypatch, _Client200)
    provider = GeminiProvider()
    result = await provider.health(credentials={"key": "ok"})
    assert result["ok"] is True
    models = result["available_models"]
    # Pro before flash, no preview/audio/antigravity/embedding/non-gemini
    assert models[0] == "gemini-1.5-pro"
    assert "gemini-1.5-flash" in models
    assert "gemini-2.0-flash-exp" in models
    assert all("antigravity" not in m for m in models)
    assert all("preview-tts" not in m for m in models)
    assert all("audio" not in m for m in models)
    assert "embedding-001" not in models
    assert "text-bison" not in models
    # Flash entries appear before "rest"; pro stays first
    flash_idx = next(i for i, m in enumerate(models) if "flash" in m)
    pro_idx = next(i for i, m in enumerate(models) if "pro" in m)
    assert pro_idx < flash_idx


async def test_health_unreachable_returns_pt_br_message(monkeypatch) -> None:
    class _ClientBoom(_FakeAsyncClient):
        _raise = ConnectionError("dns fail")

    _patch_client(monkeypatch, _ClientBoom)
    provider = GeminiProvider()
    result = await provider.health(credentials={"key": "x"})
    assert result["ok"] is False
    assert "inalcançável" in result["message"]


async def test_health_resolves_gemini_api_key_alias(monkeypatch) -> None:
    """GEMINI_API_KEY env should resolve when GOOGLE_API_KEY missing."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "alias-key")

    captured: dict[str, str] = {}

    class _ClientCapture(_FakeAsyncClient):
        _response = _FakeResponse(200, payload={"models": []})

        async def get(self, url, headers=None):
            captured["key_header"] = (headers or {}).get("x-goog-api-key", "")
            return self._response

    _patch_client(monkeypatch, _ClientCapture)
    provider = GeminiProvider()
    await provider.health(credentials=None)
    assert captured["key_header"] == "alias-key"
