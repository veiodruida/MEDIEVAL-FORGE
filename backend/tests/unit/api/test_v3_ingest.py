"""Unit tests for /api/v3/projects/{id}/ingest SSE endpoint (Plan 04 D-14)."""
from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from medieval_forge.database import get_db
from medieval_forge.main import app
from medieval_forge.models import Base, Project


@pytest_asyncio.fixture
async def in_memory_db():
    """Spin up an in-memory SQLite + create tables; yield session factory; teardown."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(in_memory_db, monkeypatch):
    """ASGI client with get_db overridden + AsyncSessionLocal monkey-patched.

    Uses monkeypatch (not dependency_overrides) for AsyncSessionLocal because
    _adapter_producer references it as a module-level global, not via Depends.
    Mirrors Plan 02 Task 1's PROJECTS_ROOT monkeypatch pattern + v1 api/ingest.py.

    httpx ≥ 0.28 dropped the ``app=`` kwarg on AsyncClient — use ASGITransport
    explicitly (mirrors backend/tests/conftest.py).
    """
    async def _override_get_db():
        async with in_memory_db() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    # Critical: _adapter_producer reads AsyncSessionLocal from module scope at
    # call time. Monkey-patch the module global so _set_status writes to the
    # in-memory DB.
    from medieval_forge.api.v3 import ingest as v3_ingest_mod
    monkeypatch.setattr(v3_ingest_mod, "AsyncSessionLocal", in_memory_db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


async def _make_project(
    factory: async_sessionmaker,
    *,
    project_id: str | None = None,
    status: str = "draft",
    with_bbox: bool = True,
    country_qid: str = "Q29,Q45",  # Iberia preset
) -> str:
    """Insert a Project row in the in-memory DB and return its UUID.

    period_start/period_end are NOT NULL on the Project model — supply
    historically-meaningful Iberia 868 defaults so the tests document
    what they're modelling.
    """
    pid = project_id or str(uuid.uuid4())
    async with factory() as s:
        kwargs: dict = dict(
            id=pid,
            name="test",
            country_qid=country_qid,
            period_start=868,
            period_end=1492,
            status=status,
        )
        if with_bbox:
            kwargs.update(
                bbox_lon_min=-9.5, bbox_lat_min=36.0,
                bbox_lon_max=4.3,  bbox_lat_max=44.0,
            )
        s.add(Project(**kwargs))
        await s.commit()
    return pid


# ---- 1. UUID guard (T-02-04-01 / V5 input validation) ----
async def test_v3_ingest_returns_400_when_project_id_is_not_uuid(client):
    r = await client.get("/api/v3/projects/not-a-uuid/ingest")
    assert r.status_code == 400
    assert "UUID" in r.json()["detail"]


# ---- 2. 404 for missing project ----
async def test_v3_ingest_returns_404_when_project_does_not_exist(client):
    r = await client.get(f"/api/v3/projects/{uuid.uuid4()}/ingest")
    assert r.status_code == 404
    assert r.json()["detail"] == "project not found"


# ---- 3. 409 anti-overlap ----
async def test_v3_ingest_returns_409_when_project_status_is_generating(client, in_memory_db):
    pid = await _make_project(in_memory_db, status="generating")
    r = await client.get(f"/api/v3/projects/{pid}/ingest")
    assert r.status_code == 409
    assert "generating" in r.json()["detail"]


# ---- 4. 400 for missing bbox ----
async def test_v3_ingest_returns_400_when_project_has_no_bbox(client, in_memory_db):
    pid = await _make_project(in_memory_db, with_bbox=False)
    r = await client.get(f"/api/v3/projects/{pid}/ingest")
    assert r.status_code == 400
    assert "bbox" in r.json()["detail"]


# ---- 5. Happy path: stream contains terminal sentinel + status updated ----
async def test_v3_ingest_streams_terminal_sentinel_and_updates_status_on_success(
    client, in_memory_db, monkeypatch,
):
    from pathlib import Path

    from medieval_forge.api.v3 import ingest as v3_ingest_mod
    from medieval_forge.services.pipeline.contracts import ProjectDataset

    pid = await _make_project(in_memory_db, status="draft")

    async def _fake_adapter(project_id, bbox, iso_codes, queue, **kwargs):  # noqa: ARG001
        await queue.put("data: fake-step-1\n\n")
        await queue.put("data: fake-step-2\n\n")
        return ProjectDataset(
            pt_geojson=Path("/tmp/pt.geojson"),
            es_input=Path("/tmp/es.geojson"),
            mountain_river_json=Path("/tmp/mr.json"),
        )

    monkeypatch.setattr(v3_ingest_mod, "build_dataset_from_osm", _fake_adapter)

    async with client.stream("GET", f"/api/v3/projects/{pid}/ingest") as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = ""
        async for chunk in r.aiter_text():
            body += chunk

    assert "fake-step-1" in body
    assert "fake-step-2" in body
    assert "DONE" in body  # producer's success terminator before None sentinel

    # Status updated to "ingested"
    async with in_memory_db() as s:
        proj = await s.get(Project, pid)
        assert proj.status == "ingested"


# ---- 6. Error path: terminal sentinel still emitted; status set to error ----
async def test_v3_ingest_emits_terminal_sentinel_even_when_adapter_raises(
    client, in_memory_db, monkeypatch,
):
    from medieval_forge.api.v3 import ingest as v3_ingest_mod

    pid = await _make_project(in_memory_db, status="draft")

    async def _failing_adapter(project_id, bbox, iso_codes, queue, **kwargs):  # noqa: ARG001
        raise RuntimeError("adapter blew up")

    monkeypatch.setattr(v3_ingest_mod, "build_dataset_from_osm", _failing_adapter)

    async with client.stream("GET", f"/api/v3/projects/{pid}/ingest") as r:
        assert r.status_code == 200  # SSE response itself is 200; error in body
        body = ""
        # Bound the read so a leaked task can't hang the test.
        async with asyncio.timeout(10.0):
            async for chunk in r.aiter_text():
                body += chunk

    assert "ERROR" in body
    assert "RuntimeError" in body  # T-02-04-05: class name only

    # Status updated to "error_ingesting"
    async with in_memory_db() as s:
        proj = await s.get(Project, pid)
        assert proj.status == "error_ingesting"
