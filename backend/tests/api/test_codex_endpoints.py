"""Etapa 9 (master plan H.9 / quick-260428-l0l): /codex API endpoints.

POST /api/projects/{id}/codex            — SSE stream
GET  /api/projects/{id}/codex/cached    — cached payload or 404
GET  /api/projects/{id}/codex/prompt    — built prompt (manual flow)

Mirrors test_research_sse.py wiring (in-memory aiosqlite + ASGITransport).
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from medieval_forge.main import app
from medieval_forge.database import get_db
from medieval_forge.models import Base, Project


PROJECT_ID = "deadbeef-dead-4bee-8ead-ddddddddeeee"


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
async def session_factory(async_engine):
    return async_sessionmaker(async_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def async_client(session_factory):
    async def _override():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    app.state._test_session_factory = session_factory
    # Provide credentials so resolve_credentials succeeds for non-Ollama providers.
    app.state.credentials = {"claude": {"api_key": "test-key"}}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    if hasattr(app.state, "_test_session_factory"):
        del app.state._test_session_factory


@pytest_asyncio.fixture
async def project_row(session_factory):
    async with session_factory() as session:
        session.add(Project(
            id=PROJECT_ID,
            name="Iberia",
            country_qid="Q29",
            period_start=868,
            period_end=1100,
            status="generated",
        ))
        await session.commit()
    return PROJECT_ID


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def _empty_codex_payload() -> dict:
    cats = ("currency", "attributes", "health", "traits", "feudal", "politics",
            "dynasty", "religion", "culture", "economy", "military", "events")
    return {c: {"summary": "", "entries": []} for c in cats}


@pytest.mark.asyncio
async def test_post_codex_streams_sse_chunks_through_done(
    monkeypatch, async_client, project_row,
):
    """POST /codex returns SSE with starting + RESULT + DONE."""
    from medieval_forge.services.llm import PROVIDERS
    from medieval_forge.services.llm.base import HealthStatus
    from medieval_forge.services.llm.schemas import CodexResult

    payload = _empty_codex_payload()
    payload["currency"]["summary"] = "Test codex"
    valid_result = CodexResult.model_validate(payload)

    original = PROVIDERS["claude"]

    class _Fake:
        provider_id = "claude"
        display_name = "Claude (fake)"
        auth_methods = original.auth_methods

        async def health_check(self, creds):
            return HealthStatus(healthy=True, message="ok")

        async def research(self, prompt, schema, credentials, queue):
            return valid_result

    monkeypatch.setitem(PROVIDERS, "claude", _Fake())

    body_chunks: list[str] = []
    async with async_client.stream(
        "POST", f"/api/projects/{project_row}/codex?provider=claude"
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        async for chunk in resp.aiter_text():
            body_chunks.append(chunk)

    body = "".join(body_chunks)
    assert "data: starting" in body
    assert "data: RESULT" in body
    assert "data: DONE" in body
    assert "Test codex" in body


@pytest.mark.asyncio
async def test_post_codex_returns_400_for_invalid_uuid(async_client):
    """Non-UUID project_id → 400 Invalid project_id."""
    resp = await async_client.post("/api/projects/not-a-uuid/codex?provider=claude")
    assert resp.status_code == 400
    assert "Invalid project_id" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_post_codex_returns_404_for_unknown_provider_or_project(
    async_client, project_row,
):
    """Unknown project → 404 Project not found; unknown provider → 404 Unknown provider."""
    # (a) valid UUID but no row in DB
    missing_id = "ffffffff-ffff-4fff-8fff-ffffffffffff"
    resp_a = await async_client.post(f"/api/projects/{missing_id}/codex?provider=claude")
    assert resp_a.status_code == 404
    assert "Project not found" in resp_a.json()["detail"]

    # (b) existing project but unknown provider
    resp_b = await async_client.post(f"/api/projects/{project_row}/codex?provider=ghost")
    assert resp_b.status_code == 404
    assert "Unknown provider" in resp_b.json()["detail"]
    assert "ghost" in resp_b.json()["detail"]


@pytest.mark.asyncio
async def test_get_codex_cached_returns_payload_when_cached_else_404(
    async_client, project_row, session_factory,
):
    """Pre-populate cache for (claude, default model) → 200; different provider → 404."""
    from medieval_forge.services.codex_cache import compute_codex_cache_key, set_codex_cached

    expected_model = "claude-opus-4-7"
    payload = _empty_codex_payload()
    payload["currency"]["summary"] = "cached-200-payload"
    key = compute_codex_cache_key("Q29", 868, 1100, "claude", expected_model)
    async with session_factory() as session:
        await set_codex_cached(
            session, key, payload, "claude", expected_model,
            "Q29", 868, 1100,
        )

    # (a) hit
    resp_a = await async_client.get(
        f"/api/projects/{project_row}/codex/cached?provider=claude"
    )
    assert resp_a.status_code == 200
    body = resp_a.json()
    assert body["currency"]["summary"] == "cached-200-payload"

    # (b) miss for different provider
    resp_b = await async_client.get(
        f"/api/projects/{project_row}/codex/cached?provider=openai"
    )
    assert resp_b.status_code == 404
    assert "No cached codex" in resp_b.json()["detail"]
