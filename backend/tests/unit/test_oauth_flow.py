"""Tests for Google OAuth installed-app flow — T-3-02.

Covers CSRF state validation, TTL expiry, successful token exchange, and
expired-state cleanup (Pitfall 5 from RESEARCH.md).
"""
from __future__ import annotations

import time
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, patch


@pytest_asyncio.fixture
async def auth_client():
    from medieval_forge.main import app

    app.state.credentials = {}
    app.state.oauth_states = {}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _make_mock_flow(state: str = "state123", token: str = "ya29.test"):
    """Build a mock google_auth_oauthlib.flow.Flow instance."""
    mock_flow = MagicMock()
    mock_flow.authorization_url.return_value = (
        "https://accounts.google.com/o/oauth2/auth?mock=1",
        state,
    )
    mock_flow.credentials = MagicMock()
    mock_flow.credentials.token = token
    mock_flow.credentials.refresh_token = "1//refresh-token"
    mock_flow.fetch_token = MagicMock(return_value=None)
    return mock_flow


async def test_oauth_start_returns_authorize_url(auth_client, monkeypatch):
    mock_flow = _make_mock_flow(state="state123")

    with patch("medieval_forge.api.auth.Flow") as mock_flow_cls:
        mock_flow_cls.from_client_config.return_value = mock_flow

        resp = await auth_client.post("/api/auth/oauth/gemini/start")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "authorize_url" in data
    assert data["authorize_url"].startswith("https://accounts.google.com")

    from medieval_forge.main import app

    assert "state123" in app.state.oauth_states


async def test_oauth_callback_rejects_unknown_state(auth_client):
    resp = await auth_client.get(
        "/api/auth/oauth/gemini/callback",
        params={"code": "abc", "state": "NEVER_ISSUED"},
    )
    assert resp.status_code == 400
    assert "state" in resp.json()["detail"].lower()


async def test_oauth_callback_rejects_expired_state(auth_client):
    from medieval_forge.main import app

    app.state.oauth_states["expired_state"] = {
        "flow": _make_mock_flow(),
        "provider": "gemini",
        "expires_at": time.time() - 60,
    }

    resp = await auth_client.get(
        "/api/auth/oauth/gemini/callback",
        params={"code": "abc", "state": "expired_state"},
    )
    assert resp.status_code == 400


async def test_oauth_callback_stores_token_in_credentials(auth_client, monkeypatch):
    from medieval_forge.main import app

    mock_flow = _make_mock_flow(token="ya29.test")
    app.state.oauth_states["valid_state"] = {
        "flow": mock_flow,
        "provider": "gemini",
        "expires_at": time.time() + 300,
    }

    resp = await auth_client.get(
        "/api/auth/oauth/gemini/callback",
        params={"code": "auth_code_xyz", "state": "valid_state"},
    )
    assert resp.status_code == 200, resp.text

    stored = app.state.credentials.get("gemini", {})
    assert stored.get("access_token") == "ya29.test"
    # OAuth tokens persist to DB for survival across restarts; source is 'disk'.
    assert stored.get("source") == "disk"


async def test_oauth_start_cleans_expired_states(auth_client):
    """Pitfall 5: expired state entries are cleaned on each /start call."""
    from medieval_forge.main import app

    # Pre-populate with one expired entry
    app.state.oauth_states["stale_entry"] = {
        "flow": _make_mock_flow(),
        "provider": "gemini",
        "expires_at": time.time() - 120,
    }

    with patch("medieval_forge.api.auth.Flow") as mock_flow_cls:
        mock_flow_cls.from_client_config.return_value = _make_mock_flow(state="fresh_state")
        await auth_client.post("/api/auth/oauth/gemini/start")

    assert "stale_entry" not in app.state.oauth_states


async def test_oauth_start_unknown_provider_returns_404(auth_client):
    """OpenAI does not support OAuth per D-12."""
    resp = await auth_client.post("/api/auth/oauth/openai/start")
    assert resp.status_code == 404
