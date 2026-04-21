"""Integration tests for POST /api/projects/{id}/research SSE endpoint.

Wave 0 test scaffolding. These tests define the contract for Task 3 implementation.
"""
from __future__ import annotations

import asyncio
import json
import pytest
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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def project_with_territories(async_session_factory, tmp_path, monkeypatch):
    """Create a Project row + a minimal territories.geojson on disk."""
    import medieval_forge.services.paths as paths_mod

    fake_root = tmp_path / "projects"
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", fake_root)

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

    # Write a minimal territories.geojson
    out_dir = fake_root / pid / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    territories = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": "c1", "name": "Condado A"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"id": "c2", "name": "Condado B"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]]],
                },
            },
        ],
    }
    (out_dir / "territories.geojson").write_text(json.dumps(territories), encoding="utf-8")

    return pid


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_sse_endpoint_streams_progress(monkeypatch, async_client, project_with_territories):
    """Monkeypatched provider emits 3 progress msgs + RESULT + DONE."""
    from medieval_forge.services.llm import PROVIDERS
    from medieval_forge.services.llm.schemas import ResearchResult, CondadoAssignment

    valid_result = ResearchResult(
        kingdoms={"k1": "Leon"},
        duchies={"d1": ("k1", "Duchy of Leon")},
        condados_assignment=[
            CondadoAssignment(condado_id="c1", kingdom_id="k1", duchy_id="d1"),
            CondadoAssignment(condado_id="c2", kingdom_id="k1", duchy_id="d1"),
        ],
        baronies={"c1": [], "c2": []},
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

    pid = project_with_territories
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


async def test_sse_endpoint_returns_cached_result(monkeypatch, async_client, project_with_territories, async_session_factory, tmp_path):
    """Pre-populated cache → provider.research NOT called; stream emits cached + DONE."""
    from medieval_forge.services.llm import PROVIDERS
    from medieval_forge.services.research_cache import compute_cache_key, set_cached
    from medieval_forge.services.research_runner import PROVIDER_DEFAULT_MODEL

    # Pre-populate cache
    key = compute_cache_key("Q29", 868, 900, "claude", PROVIDER_DEFAULT_MODEL["claude"])
    payload = {
        "kingdoms": {"k1": "Leon"},
        "duchies": {"d1": ["k1", "Duchy of Leon"]},
        "condados_assignment": [
            {"condado_id": "c1", "kingdom_id": "k1", "duchy_id": "d1"},
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

    # Wire the research runner to use our in-memory session factory
    import medieval_forge.services.research_runner as runner_mod
    monkeypatch.setattr(runner_mod, "AsyncSessionLocal", async_session_factory)

    pid = project_with_territories
    body_chunks = []
    async with async_client.stream("POST", f"/api/projects/{pid}/research?provider=claude") as resp:
        assert resp.status_code == 200
        async for chunk in resp.aiter_text():
            body_chunks.append(chunk)

    body = "".join(body_chunks)
    assert "cached" in body
    assert "DONE" in body
    assert not research_called


async def test_sse_endpoint_force_refresh_bypasses_cache(monkeypatch, async_client, project_with_territories, async_session_factory, tmp_path):
    """Pre-populated cache + force_refresh=true → provider.research IS called."""
    from medieval_forge.services.llm import PROVIDERS
    from medieval_forge.services.research_cache import compute_cache_key, set_cached
    from medieval_forge.services.research_runner import PROVIDER_DEFAULT_MODEL
    from medieval_forge.services.llm.schemas import ResearchResult, CondadoAssignment

    # Pre-populate cache
    key = compute_cache_key("Q29", 868, 900, "claude", PROVIDER_DEFAULT_MODEL["claude"])
    payload = {"kingdoms": {}, "duchies": {}, "condados_assignment": [], "baronies": {}}
    async with async_session_factory() as session:
        await set_cached(session, key, payload, "claude", PROVIDER_DEFAULT_MODEL["claude"],
                         "Q29", 868, 900)

    research_called = []

    original_provider = PROVIDERS["claude"]

    valid_result = ResearchResult(
        kingdoms={"k1": "Leon"},
        duchies={"d1": ("k1", "Duchy of Leon")},
        condados_assignment=[
            CondadoAssignment(condado_id="c1", kingdom_id="k1", duchy_id="d1"),
            CondadoAssignment(condado_id="c2", kingdom_id="k1", duchy_id="d1"),
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

    import medieval_forge.services.research_runner as runner_mod
    monkeypatch.setattr(runner_mod, "AsyncSessionLocal", async_session_factory)

    pid = project_with_territories
    body_chunks = []
    async with async_client.stream(
        "POST", f"/api/projects/{pid}/research?provider=claude&force_refresh=true"
    ) as resp:
        assert resp.status_code == 200
        async for chunk in resp.aiter_text():
            body_chunks.append(chunk)

    assert research_called, "provider.research should have been called with force_refresh=true"


async def test_sse_endpoint_404_unknown_provider(async_client, project_with_territories):
    """Unknown provider returns 404 immediately (before streaming)."""
    pid = project_with_territories
    resp = await async_client.post(f"/api/projects/{pid}/research?provider=mistral")
    assert resp.status_code == 404


async def test_sse_endpoint_404_unknown_project(async_client):
    """Non-existent project_id returns 404."""
    resp = await async_client.post(
        "/api/projects/bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb/research?provider=claude"
    )
    assert resp.status_code == 404
