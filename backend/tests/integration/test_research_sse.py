"""Integration tests for POST /api/projects/{id}/research SSE endpoint."""
from __future__ import annotations

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from medieval_forge.main import app
from medieval_forge.database import get_db
from medieval_forge.models import Base, Project


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def async_engine():
    """In-memory SQLite engine with all tables."""
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
    """AsyncClient wired to in-memory DB."""
    async def _override():
        async with async_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    app.state._test_session_factory = async_session_factory
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    if hasattr(app.state, "_test_session_factory"):
        del app.state._test_session_factory


@pytest_asyncio.fixture
async def project_row(async_session_factory):
    """Create a Project row (no geojson needed — LLM generates condados freely)."""
    pid = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
    async with async_session_factory() as session:
        session.add(Project(
            id=pid,
            name="Test Kingdom",
            country_qid="Q29",
            period_start=868,
            period_end=900,
            status="generated",
        ))
        await session.commit()
    return pid


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_sse_endpoint_streams_progress(monkeypatch, async_client, project_row):
    """Monkeypatched provider emits 3 progress msgs + RESULT + DONE."""
    from medieval_forge.services.llm import PROVIDERS
    from medieval_forge.services.llm.schemas import ResearchResult, Condado, Duchy

    valid_result = ResearchResult(
        kingdoms={"k1": "Leon"},
        duchies={"d1": Duchy(kingdom_id="k1", name="Duchy of Leon")},
        condados=[
            Condado(id="C_ONE", name="Condado One", lon=-5.5, lat=42.6,
                    kingdom_id="k1", duchy_id="d1"),
            Condado(id="C_TWO", name="Condado Two", lon=-5.8, lat=43.1,
                    kingdom_id="k1", duchy_id="d1"),
        ],
        baronies={"C_ONE": [], "C_TWO": []},
    )

    original_provider = PROVIDERS["claude"]

    class _FakeProvider:
        provider_id = "claude"
        display_name = "Claude (fake)"
        auth_methods = original_provider.auth_methods

        async def health_check(self, creds):
            from medieval_forge.services.llm.base import HealthStatus
            return HealthStatus(healthy=True, message="ok")

        async def research(self, prompt, schema, credentials, queue):
            if queue:
                await queue.put("data: progress 1\n\n")
                await queue.put("data: progress 2\n\n")
                await queue.put("data: progress 3\n\n")
            return valid_result

    monkeypatch.setitem(PROVIDERS, "claude", _FakeProvider())

    pid = project_row
    body_chunks = []
    async with async_client.stream("POST", f"/api/projects/{pid}/research?provider=claude") as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        async for chunk in resp.aiter_text():
            body_chunks.append(chunk)

    body = "".join(body_chunks)
    assert "progress 1" in body
    assert "progress 2" in body
    assert "progress 3" in body
    assert "DONE" in body


async def test_sse_endpoint_returns_cached_result(monkeypatch, async_client, project_row, async_session_factory):
    """Pre-populated cache → provider.research NOT called; stream emits cached + DONE."""
    from medieval_forge.services.llm import PROVIDERS
    from medieval_forge.services.research_cache import compute_cache_key, set_cached
    from medieval_forge.services.research_runner import PROVIDER_DEFAULT_MODEL

    key = compute_cache_key("Q29", 868, 900, "claude", PROVIDER_DEFAULT_MODEL["claude"])
    payload = {
        "kingdoms": {"k1": "Leon"},
        "duchies": {"d1": {"kingdom_id": "k1", "name": "Duchy of Leon"}},
        "condados": [
            {"id": "C_ONE", "name": "One", "lon": -5.5, "lat": 42.6,
             "kingdom_id": "k1", "duchy_id": "d1"},
        ],
        "baronies": {},
    }
    async with async_session_factory() as session:
        await set_cached(session, key, payload, "claude", PROVIDER_DEFAULT_MODEL["claude"],
                         "Q29", 868, 900)

    research_called = []
    original_provider = PROVIDERS["claude"]

    class _FakeProvider:
        provider_id = "claude"
        display_name = "Claude (fake)"
        auth_methods = original_provider.auth_methods

        async def health_check(self, creds):
            from medieval_forge.services.llm.base import HealthStatus
            return HealthStatus(healthy=True, message="ok")

        async def research(self, prompt, schema, credentials, queue):
            research_called.append(True)
            raise AssertionError("Should not be called — cache hit expected")

    monkeypatch.setitem(PROVIDERS, "claude", _FakeProvider())

    pid = project_row
    body_chunks = []
    async with async_client.stream("POST", f"/api/projects/{pid}/research?provider=claude") as resp:
        assert resp.status_code == 200
        async for chunk in resp.aiter_text():
            body_chunks.append(chunk)

    body = "".join(body_chunks)
    assert "cached" in body
    assert "DONE" in body
    assert not research_called


async def test_sse_endpoint_force_refresh_bypasses_cache(monkeypatch, async_client, project_row, async_session_factory):
    """Pre-populated cache + force_refresh=true → provider.research IS called."""
    from medieval_forge.services.llm import PROVIDERS
    from medieval_forge.services.research_cache import compute_cache_key, set_cached
    from medieval_forge.services.research_runner import PROVIDER_DEFAULT_MODEL
    from medieval_forge.services.llm.schemas import ResearchResult, Condado, Duchy

    key = compute_cache_key("Q29", 868, 900, "claude", PROVIDER_DEFAULT_MODEL["claude"])
    stale_payload = {"kingdoms": {}, "duchies": {}, "condados": [], "baronies": {}}
    async with async_session_factory() as session:
        await set_cached(session, key, stale_payload, "claude", PROVIDER_DEFAULT_MODEL["claude"],
                         "Q29", 868, 900)

    research_called = []
    original_provider = PROVIDERS["claude"]

    valid_result = ResearchResult(
        kingdoms={"k1": "Leon"},
        duchies={"d1": Duchy(kingdom_id="k1", name="Duchy of Leon")},
        condados=[
            Condado(id="C_ONE", name="One", lon=-5.5, lat=42.6,
                    kingdom_id="k1", duchy_id="d1"),
        ],
        baronies={},
    )

    class _FakeProvider:
        provider_id = "claude"
        display_name = "Claude (fake)"
        auth_methods = original_provider.auth_methods

        async def health_check(self, creds):
            from medieval_forge.services.llm.base import HealthStatus
            return HealthStatus(healthy=True, message="ok")

        async def research(self, prompt, schema, credentials, queue):
            research_called.append(True)
            return valid_result

    monkeypatch.setitem(PROVIDERS, "claude", _FakeProvider())

    pid = project_row
    body_chunks = []
    async with async_client.stream(
        "POST", f"/api/projects/{pid}/research?provider=claude&force_refresh=true"
    ) as resp:
        assert resp.status_code == 200
        async for chunk in resp.aiter_text():
            body_chunks.append(chunk)

    assert research_called, "provider.research should have been called with force_refresh=true"


async def test_sse_endpoint_404_unknown_provider(async_client, project_row):
    """Unknown provider returns 404 immediately (before streaming)."""
    pid = project_row
    resp = await async_client.post(f"/api/projects/{pid}/research?provider=mistral")
    assert resp.status_code == 404


async def test_sse_endpoint_404_unknown_project(async_client):
    """Non-existent project_id returns 404."""
    resp = await async_client.post(
        "/api/projects/bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb/research?provider=claude"
    )
    assert resp.status_code == 404
