"""Unit tests for /api/v3/projects/{id}/generate (Plan 03-02 D-22).

Covers:
  1. UUID guard (400)
  2. 404 when project missing
  3. 409 single-flight gate (T-03-03)
  4. Happy path POST: 202 + run_id + status='generating' before response
  5. Stream without active run → 404
  6. Stream happy path: started → stage_start → stage_done → done events,
     final status='generated'
  7. Stream error path: producer raises → 'error' event + status='error_generating'
  8. updated_at bumped on success (D-19 cache-bust precondition)
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from medieval_forge.database import get_db
from medieval_forge.main import app
from medieval_forge.models import Base, Project
from medieval_forge.services import paths as paths_mod


@pytest_asyncio.fixture
async def in_memory_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(in_memory_db, monkeypatch, tmp_path):
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")

    async def _override_get_db():
        async with in_memory_db() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    # Critical: _generate_producer reads AsyncSessionLocal from module scope
    # at call time — monkey-patch it so _set_status writes to in-memory DB.
    from medieval_forge.api.v3 import generate as v3_generate_mod

    monkeypatch.setattr(v3_generate_mod, "AsyncSessionLocal", in_memory_db)

    # Reset the module-level run-tracking state between tests.
    # These dicts now live in _run_state.py and are re-imported by generate.py;
    # clearing via v3_generate_mod works because Python import binds the same dict.
    v3_generate_mod._RUN_QUEUES.clear()
    v3_generate_mod._RUN_TASKS.clear()
    v3_generate_mod._RUN_KIND.clear()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    v3_generate_mod._RUN_QUEUES.clear()
    v3_generate_mod._RUN_TASKS.clear()
    v3_generate_mod._RUN_KIND.clear()


async def _make_project(
    factory: async_sessionmaker,
    *,
    project_id: str | None = None,
    status: str = "draft",
) -> str:
    pid = project_id or str(uuid.uuid4())
    async with factory() as s:
        s.add(
            Project(
                id=pid,
                name="test",
                country_qid="Q29,Q45",
                period_start=868,
                period_end=1492,
                status=status,
            )
        )
        await s.commit()
    return pid


# ---- 1. UUID guard ----
async def test_generate_returns_400_when_project_id_is_not_uuid(client):
    r = await client.post("/api/v3/projects/not-a-uuid/generate")
    assert r.status_code == 400


# ---- 2. 404 when project absent ----
async def test_generate_returns_404_when_project_does_not_exist(client):
    r = await client.post(f"/api/v3/projects/{uuid.uuid4()}/generate")
    assert r.status_code == 404


# ---- 3. 409 single-flight gate (T-03-03) ----
async def test_generate_returns_409_when_run_already_alive(
    client, in_memory_db, monkeypatch
):
    """Seed _RUN_TASKS with a never-completing task and status='generating'
    so the second POST hits the gate. Mirrors advisor's recommended pattern."""
    from medieval_forge.api.v3 import generate as v3_generate_mod

    pid = await _make_project(in_memory_db, status="generating")

    # Park a task that never finishes — simulates an in-flight run.
    never_event = asyncio.Event()

    async def _hang() -> None:
        await never_event.wait()

    parked = asyncio.create_task(_hang())
    v3_generate_mod._RUN_TASKS[pid] = parked
    v3_generate_mod._RUN_QUEUES[pid] = asyncio.Queue()
    v3_generate_mod._RUN_KIND[pid] = "generate"  # required for is_run_alive to report kind

    try:
        r = await client.post(f"/api/v3/projects/{pid}/generate")
        assert r.status_code == 409
        assert "already generate" in r.json()["detail"]
    finally:
        never_event.set()
        parked.cancel()
        try:
            await parked
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass


# ---- 4. Happy path POST: 202 + run_id + status='generating' ----
async def test_generate_post_returns_202_and_schedules_run(
    client, in_memory_db, monkeypatch
):
    from medieval_forge.api.v3 import generate as v3_generate_mod

    pid = await _make_project(in_memory_db, status="draft")

    # Stub run_pipeline to be a near-no-op so the producer completes fast.
    def _stub_run_pipeline(cfg):  # noqa: ARG001
        if cfg.on_stage:
            cfg.on_stage("voronoi", "start")
            cfg.on_stage("voronoi", "done")

    monkeypatch.setattr(v3_generate_mod, "run_pipeline", _stub_run_pipeline)

    r = await client.post(f"/api/v3/projects/{pid}/generate")
    assert r.status_code == 202
    body = r.json()
    assert "run_id" in body
    assert body["status"] == "scheduled"
    # run_id is a uuid string
    uuid.UUID(body["run_id"])

    # status committed BEFORE the response returned
    async with in_memory_db() as s:
        proj = await s.get(Project, pid)
        assert proj.status in ("generating", "generated")  # task may have completed already

    # Drain the queue so the parked task can clean up before fixture teardown.
    queue = v3_generate_mod._RUN_QUEUES.get(pid)
    if queue is not None:
        async with asyncio.timeout(5.0):
            while True:
                msg = await queue.get()
                if msg is None:
                    break


# ---- 5. Stream without active run → 404 ----
async def test_stream_returns_404_when_no_active_run(client, in_memory_db):
    pid = await _make_project(in_memory_db, status="draft")
    r = await client.get(f"/api/v3/projects/{pid}/generate/stream")
    assert r.status_code == 404
    assert "no active generate run" in r.json()["detail"]


# ---- 6. Stream happy path: started + stage_start + stage_done + done ----
async def test_stream_emits_stage_events_on_happy_path(
    client, in_memory_db, monkeypatch
):
    """POST then immediately consume the stream; assert structured SSE events."""
    from medieval_forge.api.v3 import generate as v3_generate_mod

    pid = await _make_project(in_memory_db, status="draft")

    # Stub run_pipeline: invoke on_stage for one stage then return.
    def _stub_run_pipeline(cfg):
        cfg.on_stage("voronoi", "start")
        cfg.on_stage("voronoi", "done")

    monkeypatch.setattr(v3_generate_mod, "run_pipeline", _stub_run_pipeline)

    post_resp = await client.post(f"/api/v3/projects/{pid}/generate")
    assert post_resp.status_code == 202

    body = ""
    async with client.stream("GET", f"/api/v3/projects/{pid}/generate/stream") as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        async with asyncio.timeout(10.0):
            async for chunk in r.aiter_text():
                body += chunk

    assert '"event_type": "started"' in body
    assert '"event_type": "stage_start"' in body
    assert '"stage": "voronoi"' in body
    assert '"event_type": "stage_done"' in body
    assert '"event_type": "done"' in body

    # Final status should be 'generated'.
    async with in_memory_db() as s:
        proj = await s.get(Project, pid)
        assert proj.status == "generated"


# ---- 7. Stream error path ----
async def test_stream_emits_error_event_when_pipeline_raises(
    client, in_memory_db, monkeypatch
):
    from medieval_forge.api.v3 import generate as v3_generate_mod

    pid = await _make_project(in_memory_db, status="draft")

    def _failing_run_pipeline(cfg):  # noqa: ARG001
        raise RuntimeError("boom")

    monkeypatch.setattr(v3_generate_mod, "run_pipeline", _failing_run_pipeline)

    post_resp = await client.post(f"/api/v3/projects/{pid}/generate")
    assert post_resp.status_code == 202

    body = ""
    async with client.stream("GET", f"/api/v3/projects/{pid}/generate/stream") as r:
        assert r.status_code == 200
        async with asyncio.timeout(10.0):
            async for chunk in r.aiter_text():
                body += chunk

    assert '"event_type": "error"' in body
    assert "RuntimeError" in body  # T-03-05: class name only

    async with in_memory_db() as s:
        proj = await s.get(Project, pid)
        assert proj.status == "error_generating"


# ---- 8. updated_at bumped on success (D-19 cache-bust precondition) ----
async def test_generate_bumps_updated_at_on_success(
    client, in_memory_db, monkeypatch
):
    """The frontend appends ?v={updated_at}; the timestamp MUST change between
    successive successful runs so cached artifacts get invalidated."""
    from medieval_forge.api.v3 import generate as v3_generate_mod

    pid = await _make_project(in_memory_db, status="draft")

    # Capture the initial updated_at AFTER project creation.
    async with in_memory_db() as s:
        proj = await s.get(Project, pid)
        initial_updated = proj.updated_at

    def _stub_run_pipeline(cfg):
        cfg.on_stage("voronoi", "start")
        cfg.on_stage("voronoi", "done")

    monkeypatch.setattr(v3_generate_mod, "run_pipeline", _stub_run_pipeline)

    # Sleep briefly so the new timestamp is strictly greater.
    await asyncio.sleep(0.01)

    post_resp = await client.post(f"/api/v3/projects/{pid}/generate")
    assert post_resp.status_code == 202

    # Drain the stream so the producer finishes its work.
    body = ""
    async with client.stream("GET", f"/api/v3/projects/{pid}/generate/stream") as r:
        async with asyncio.timeout(10.0):
            async for chunk in r.aiter_text():
                body += chunk

    async with in_memory_db() as s:
        proj = await s.get(Project, pid)
        assert proj.status == "generated"
        # updated_at must be strictly greater than at creation time.
        # Both come back as naive datetimes from sqlite; compare directly.
        bumped = proj.updated_at
        if bumped.tzinfo is None and initial_updated.tzinfo is not None:
            initial_updated = initial_updated.replace(tzinfo=None)
        elif bumped.tzinfo is not None and initial_updated.tzinfo is None:
            bumped = bumped.replace(tzinfo=None)
        assert bumped > initial_updated
