# Plan 07-04 Task 2 — OllamaProvider health-check unit tests.
#
# Wave 0 gate (VALIDATION row 07-XX-OLLAMA-HEALTH) + REVIEWS fix #5
# (available_models surfaced for ProviderSelector dropdown).
"""Unit tests for OllamaProvider.health() — 3s timeout + available_models surfacing."""
from __future__ import annotations

import asyncio

import pytest

from medieval_forge.services.llm.ollama import OllamaProvider


class _FakeResponse:
    """Minimal httpx-style Response stand-in."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    """Minimal AsyncClient stand-in with controllable response / exception."""

    last_kwargs: dict = {}

    def __init__(self, *, base_url: str = "", timeout: float = 0, **kwargs) -> None:
        _FakeAsyncClient.last_kwargs = {"base_url": base_url, "timeout": timeout}

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *a) -> None:
        return None

    async def get(self, path: str) -> _FakeResponse:
        return _FakeResponse({"models": [{"name": "qwen2.5:7b"}]})


async def test_ollama_health_check_returns_healthy_when_async_client_list_succeeds_within_3s(
    monkeypatch,
):
    """Test 1: client succeeds -> ok=True + reachable message."""
    monkeypatch.setattr(
        "medieval_forge.services.llm.ollama.httpx.AsyncClient", _FakeAsyncClient
    )
    provider = OllamaProvider()
    result = await provider.health()
    assert result["ok"] is True
    assert "available_models" in result
    assert "qwen2.5:7b" in result["available_models"]


async def test_ollama_health_check_returns_unhealthy_with_timeout_message_when_async_client_list_exceeds_3s(
    monkeypatch,
):
    """Test 2: asyncio.TimeoutError -> ok=False + 'timeout after 3s' message + empty list."""

    class _TimeoutClient(_FakeAsyncClient):
        async def get(self, path: str):
            raise asyncio.TimeoutError()

    monkeypatch.setattr(
        "medieval_forge.services.llm.ollama.httpx.AsyncClient", _TimeoutClient
    )
    provider = OllamaProvider()
    result = await provider.health()
    assert result["ok"] is False
    assert "timeout" in result["message"].lower()
    assert "3s" in result["message"]
    assert result["available_models"] == []


async def test_ollama_health_check_returns_unhealthy_with_exception_message_when_async_client_raises(
    monkeypatch,
):
    """Test 3: arbitrary Exception -> ok=False + error surfaced in message + empty list."""

    class _BoomClient(_FakeAsyncClient):
        async def get(self, path: str):
            raise ConnectionError("connection refused")

    monkeypatch.setattr(
        "medieval_forge.services.llm.ollama.httpx.AsyncClient", _BoomClient
    )
    provider = OllamaProvider()
    result = await provider.health()
    assert result["ok"] is False
    assert "connection refused" in result["message"]
    assert result["available_models"] == []


async def test_ollama_health_returns_available_models_list_from_client_list(monkeypatch):
    """Test 4 (REVIEWS fix #5): available_models list extracted from client.list()."""

    class _MultiModelClient(_FakeAsyncClient):
        async def get(self, path: str) -> _FakeResponse:
            return _FakeResponse(
                {
                    "models": [
                        {"name": "qwen2.5-coder:14b"},
                        {"name": "gemma4:26b"},
                    ]
                }
            )

    monkeypatch.setattr(
        "medieval_forge.services.llm.ollama.httpx.AsyncClient", _MultiModelClient
    )
    provider = OllamaProvider()
    result = await provider.health()
    assert result["ok"] is True
    assert "available_models" in result
    assert result["available_models"] == ["qwen2.5-coder:14b", "gemma4:26b"]
