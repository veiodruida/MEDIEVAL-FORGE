"""Integration tests for GET /api/llm/providers and GET /api/llm/health endpoints.

Wave 0 test scaffolding. These tests define the contract for Task 3 implementation.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from medieval_forge.main import app
from medieval_forge.database import get_db
from medieval_forge.models import Base


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_session_factory(async_engine):
    return async_sessionmaker(async_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def async_client(async_session_factory):
    async def _override():
        async with async_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_get_providers_returns_all_four(async_client):
    """GET /api/llm/providers returns 4 entries with required fields."""
    resp = await async_client.get("/api/llm/providers")
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 4

    provider_ids = {p["provider_id"] for p in data}
    assert provider_ids == {"claude", "openai", "gemini", "ollama"}

    for entry in data:
        assert "display_name" in entry
        assert "auth_methods" in entry
        assert isinstance(entry["auth_methods"], list)
        assert "configured" in entry
        assert isinstance(entry["configured"], bool)
        assert "healthy" in entry
        assert isinstance(entry["healthy"], bool)


async def test_get_providers_marks_configured_when_env_var_set(monkeypatch, async_client):
    """OPENAI_API_KEY set → openai.configured == True."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-for-test")

    resp = await async_client.get("/api/llm/providers")
    assert resp.status_code == 200

    data = resp.json()
    openai_entry = next(p for p in data if p["provider_id"] == "openai")
    assert openai_entry["configured"] is True


async def test_get_providers_marks_unconfigured_when_no_credentials(monkeypatch, async_client):
    """No env keys + empty session + no CLI token → non-Ollama providers show configured=False."""
    # Clear all relevant env vars
    for var in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY"]:
        monkeypatch.delenv(var, raising=False)

    # Ensure app.state.credentials is empty
    app.state.credentials = {}

    # Also block CLI piggyback so the claude-code credential file on disk
    # doesn't make Claude appear configured in CI / dev environments.
    import medieval_forge.services.llm.auth as auth_mod
    monkeypatch.setattr(auth_mod, "read_claude_cli_token", lambda: None)

    resp = await async_client.get("/api/llm/providers")
    assert resp.status_code == 200

    data = resp.json()
    for entry in data:
        if entry["provider_id"] != "ollama":
            assert entry["configured"] is False, (
                f"Expected {entry['provider_id']} to be unconfigured, got configured=True"
            )


async def test_get_health_returns_per_provider_status(async_client):
    """GET /api/llm/health returns a dict with 4 providers, each having healthy+message."""
    resp = await async_client.get("/api/llm/health")
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data, dict)
    assert len(data) == 4

    for pid in ["claude", "openai", "gemini", "ollama"]:
        assert pid in data
        assert "healthy" in data[pid]
        assert "message" in data[pid]
        assert isinstance(data[pid]["healthy"], bool)
        assert isinstance(data[pid]["message"], str)


async def test_new_provider_in_registry_appears_in_endpoint(monkeypatch, async_client):
    """Monkeypatching PROVIDERS to add a 5th stub → /api/llm/providers returns 5 entries.

    Proves RESEARCH-09: plugin auto-discovery via registry.
    """
    import medieval_forge.api.llm as llm_mod
    from medieval_forge.services.llm.base import HealthStatus, NoAuth

    class _StubProvider:
        provider_id = "stub"
        display_name = "Stub Provider"
        auth_methods = [NoAuth()]

        async def health_check(self, creds):
            return HealthStatus(healthy=True, message="stub ok")

        async def research(self, prompt, schema, credentials, queue):
            pass

    extended = dict(llm_mod.PROVIDERS)
    extended["stub"] = _StubProvider()
    monkeypatch.setattr(llm_mod, "PROVIDERS", extended)

    resp = await async_client.get("/api/llm/providers")
    assert resp.status_code == 200

    data = resp.json()
    assert len(data) == 5
    provider_ids = {p["provider_id"] for p in data}
    assert "stub" in provider_ids
