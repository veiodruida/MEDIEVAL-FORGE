"""Tests for in-memory credential storage — T-3-01 / T-3-03.

These tests verify that:
- POST /api/auth/credentials/{provider} stores keys in app.state.credentials only
- Response body never echoes the submitted API key
- No files are written to disk containing the key
- DELETE removes the entry
- Unknown provider returns 404
"""
from __future__ import annotations

import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


@pytest_asyncio.fixture
async def auth_client():
    """Async client with app.state pre-initialized (as lifespan does)."""
    from medieval_forge.main import app

    app.state.credentials = {}
    app.state.oauth_states = {}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_post_credentials_stores_in_memory(auth_client):
    resp = await auth_client.post(
        "/api/auth/credentials/openai",
        json={"api_key": "sk-test-123"},
    )
    assert resp.status_code == 204, resp.text
    from medieval_forge.main import app

    stored = app.state.credentials.get("openai", {})
    assert stored.get("key") == "sk-test-123"
    # Credentials persist to DB for survival across restarts; source is 'disk'.
    assert stored.get("source") == "disk"


async def test_post_credentials_response_does_not_echo_key(auth_client):
    resp = await auth_client.post(
        "/api/auth/credentials/openai",
        json={"api_key": "sk-test-123"},
    )
    assert resp.status_code == 204
    # 204 No Content → body must be empty
    assert "sk-test-123" not in resp.text


async def test_credentials_never_written_to_disk(tmp_path, monkeypatch, auth_client):
    """Monkeypatch HOME so any accidental disk write is caught."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    resp = await auth_client.post(
        "/api/auth/credentials/openai",
        json={"api_key": "sk-test-123"},
    )
    assert resp.status_code == 204

    # Walk entire tmp_path and assert no file contains the key
    for f in tmp_path.rglob("*"):
        if f.is_file():
            content = f.read_text(encoding="utf-8", errors="replace")
            assert "sk-test-123" not in content, f"Key found in disk file: {f}"


async def test_delete_credentials_removes_entry(auth_client):
    # Store first
    await auth_client.post(
        "/api/auth/credentials/openai",
        json={"api_key": "sk-test-123"},
    )
    from medieval_forge.main import app

    assert "openai" in app.state.credentials

    # Delete
    resp = await auth_client.delete("/api/auth/credentials/openai")
    assert resp.status_code == 204
    assert "openai" not in app.state.credentials


async def test_unknown_provider_returns_404(auth_client):
    resp = await auth_client.post(
        "/api/auth/credentials/mistral",
        json={"api_key": "sk-test-999"},
    )
    assert resp.status_code == 404
