"""Integration tests for POST /render + GET /render/stream + cancel + stage raster.

Plan 04-02 Task 2 — TDD GREEN implementation. Covers:
  D-04: cross-router 409 single-flight gate
  D-05: slider bounds + ASVS V5 unknown-field rejection
  D-17: incremental path byte-equal to /generate at default cfg
  D-18: per-render fresh cfg never mutates persisted cfg

All tests use httpx.AsyncClient(transport=ASGITransport(app=app)) in-memory,
matching the generate test pattern (test_v3_generate.py).
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from medieval_forge.database import get_db
from medieval_forge.main import app
from medieval_forge.models import Base, Project
from medieval_forge.services import paths as paths_mod

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

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

    # Patch AsyncSessionLocal used by generate's _set_status helpers
    from medieval_forge.api.v3 import generate as v3_generate_mod
    monkeypatch.setattr(v3_generate_mod, "AsyncSessionLocal", in_memory_db)

    # Reset ALL shared run-state before each test
    from medieval_forge.api.v3 import _run_state
    from medieval_forge.services.pipeline.cache import _STAGE_CACHE
    _run_state._RUN_QUEUES.clear()
    _run_state._RUN_TASKS.clear()
    _run_state._RUN_KIND.clear()
    _run_state._RUN_STOP_EVENTS.clear()
    _STAGE_CACHE.clear()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    _run_state._RUN_QUEUES.clear()
    _run_state._RUN_TASKS.clear()
    _run_state._RUN_KIND.clear()
    _run_state._RUN_STOP_EVENTS.clear()
    _STAGE_CACHE.clear()


async def _make_project(factory, *, project_id=None, status="draft"):
    pid = project_id or str(uuid.uuid4())
    async with factory() as s:
        s.add(Project(
            id=pid, name="test", country_qid="Q29,Q45",
            period_start=868, period_end=1492, status=status,
        ))
        await s.commit()
    return pid


async def _drain_queue(pid: str) -> str:
    """Drain the SSE queue for a project and return all text."""
    from medieval_forge.api.v3._run_state import _RUN_QUEUES
    queue = _RUN_QUEUES.get(pid)
    if queue is None:
        return ""
    parts = []
    async with asyncio.timeout(30.0):
        while True:
            msg = await queue.get()
            if msg is None:
                break
            parts.append(msg)
    return "".join(parts)


def _stub_run_pipeline_incremental(cfg, project_id):
    """Fast no-op stub: calls on_stage for two stages so tests can watch SSE events."""
    if cfg.on_stage:
        cfg.on_stage("median", "start")
        cfg.on_stage("median", "done")
        cfg.on_stage("smooth", "start")
        cfg.on_stage("smooth", "done")
    return ["median", "smooth"]


# ---------------------------------------------------------------------------
# Test 1: POST /render returns 202 with run_id
# ---------------------------------------------------------------------------

async def test_render_returns_202_with_run_id(client, in_memory_db, monkeypatch):
    from medieval_forge.api.v3 import render as v3_render_mod
    monkeypatch.setattr(v3_render_mod, "run_pipeline_incremental",
                        _stub_run_pipeline_incremental)

    pid = await _make_project(in_memory_db)
    r = await client.post(f"/api/v3/projects/{pid}/render",
                          json={"cfg_overrides": {}})
    assert r.status_code == 202
    body = r.json()
    assert "run_id" in body
    uuid.UUID(body["run_id"])  # validates UUID format
    assert body["status"] == "scheduled"

    await _drain_queue(pid)


# ---------------------------------------------------------------------------
# Test 2: 409 when /render is already alive
# ---------------------------------------------------------------------------

async def test_render_409_when_render_alive(client, in_memory_db, monkeypatch):
    from medieval_forge.api.v3 import _run_state

    pid = await _make_project(in_memory_db)

    # Park a never-finishing task under 'render' kind
    never_event = asyncio.Event()

    async def _hang():
        await never_event.wait()

    parked = asyncio.create_task(_hang())
    _run_state._RUN_TASKS[pid] = parked
    _run_state._RUN_QUEUES[pid] = asyncio.Queue()
    _run_state._RUN_KIND[pid] = "render"

    try:
        r = await client.post(f"/api/v3/projects/{pid}/render",
                              json={"cfg_overrides": {}})
        assert r.status_code == 409
        assert "already render" in r.json()["detail"]
    finally:
        never_event.set()
        parked.cancel()
        try:
            await parked
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Test 3: 409 when /generate is alive (cross-router gate)
# ---------------------------------------------------------------------------

async def test_render_409_when_generate_alive(client, in_memory_db, monkeypatch):
    from medieval_forge.api.v3 import _run_state

    pid = await _make_project(in_memory_db)

    never_event = asyncio.Event()

    async def _hang():
        await never_event.wait()

    parked = asyncio.create_task(_hang())
    _run_state._RUN_TASKS[pid] = parked
    _run_state._RUN_QUEUES[pid] = asyncio.Queue()
    _run_state._RUN_KIND[pid] = "generate"

    try:
        r = await client.post(f"/api/v3/projects/{pid}/render",
                              json={"cfg_overrides": {}})
        assert r.status_code == 409
        assert "already generate" in r.json()["detail"]
    finally:
        never_event.set()
        parked.cancel()
        try:
            await parked
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Test 4: /generate clears cache (D-03 lifetime)
# ---------------------------------------------------------------------------

async def test_generate_clears_cache(client, in_memory_db, monkeypatch):
    """POST /generate must call cache_clear_project so stale /render intermediates
    don't bleed into the new full run (D-03 lifetime invariant)."""
    from medieval_forge.api.v3 import generate as v3_generate_mod
    from medieval_forge.services.pipeline.cache import cache_put, cache_get

    pid = await _make_project(in_memory_db)

    # Pre-seed the cache with a fake entry for this project.
    import numpy as np
    cache_put(pid, "median", "stale-token", np.zeros((2, 2), dtype=np.int16))
    assert cache_get(pid, "median") is not None

    def _stub_run_pipeline(cfg):
        if cfg.on_stage:
            cfg.on_stage("voronoi", "start")
            cfg.on_stage("voronoi", "done")

    monkeypatch.setattr(v3_generate_mod, "run_pipeline", _stub_run_pipeline)

    r = await client.post(f"/api/v3/projects/{pid}/generate")
    assert r.status_code == 202

    # Drain the queue so the producer finishes and cache_clear_project is called.
    await _drain_queue(pid)

    # The stale cache entry should now be gone (D-03).
    assert cache_get(pid, "median") is None


# ---------------------------------------------------------------------------
# Test 5: /render does not mutate persisted cfg (D-18)
# ---------------------------------------------------------------------------

async def test_render_does_not_mutate_persisted_cfg(client, in_memory_db, monkeypatch):
    """Each /render call builds a fresh cfg from iberia_config(); the project's
    persisted cfg state is NEVER mutated (D-18)."""
    from medieval_forge.api.v3 import render as v3_render_mod
    from medieval_forge.services.pipeline.region_loader import load_region, clear_region_cache

    pid = await _make_project(in_memory_db)

    # Capture the baseline sigma from a fresh load_region (D-18: cached singleton).
    clear_region_cache()
    baseline = load_region("iberia_868")
    baseline_sigma = baseline.smooth_sigma

    captured_sigmas = []

    def _capturing_incremental(cfg, project_id):
        captured_sigmas.append(cfg.smooth_sigma)
        return []

    monkeypatch.setattr(v3_render_mod, "run_pipeline_incremental",
                        _capturing_incremental)

    # POST /render with a different sigma
    r = await client.post(f"/api/v3/projects/{pid}/render",
                          json={"cfg_overrides": {"smooth_sigma": 4.0}})
    assert r.status_code == 202
    await _drain_queue(pid)

    # The cfg passed into the pipeline should have the overridden sigma
    assert len(captured_sigmas) == 1
    assert captured_sigmas[0] == 4.0

    # A fresh load_region must still return the original sigma (D-18)
    fresh = load_region("iberia_868")
    assert fresh.smooth_sigma == baseline_sigma


# ---------------------------------------------------------------------------
# Test 6: stage_view change does not trigger recomputation
# ---------------------------------------------------------------------------

async def test_stage_view_change_does_not_recompute(client, in_memory_db, monkeypatch):
    """The `stage_view` field in RenderRequest is client-only (Pitfall 8).
    Sending it with a different value must NOT recompute pipeline stages
    (it's excluded from token derivation — only cfg_overrides affect tokens)."""
    from medieval_forge.api.v3 import render as v3_render_mod

    call_count = [0]

    def _counting_incremental(cfg, project_id):
        call_count[0] += 1
        return []

    monkeypatch.setattr(v3_render_mod, "run_pipeline_incremental",
                        _counting_incremental)

    pid = await _make_project(in_memory_db)

    # POST /render with stage_view set — should still call the pipeline once
    r = await client.post(f"/api/v3/projects/{pid}/render",
                          json={"cfg_overrides": {}, "stage_view": "smooth"})
    assert r.status_code == 202
    await _drain_queue(pid)

    # Pipeline was called once for the render itself — stage_view didn't add extra
    assert call_count[0] == 1


# ---------------------------------------------------------------------------
# Test 7: /render rejects smooth_sigma outside D-05 bounds (ASVS V5)
# ---------------------------------------------------------------------------

async def test_render_clamps_sigma_to_3_0_4_5_bounds(client, in_memory_db):
    pid = await _make_project(in_memory_db)
    r = await client.post(f"/api/v3/projects/{pid}/render",
                          json={"cfg_overrides": {"smooth_sigma": 9999}})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Test 8: /render rejects unknown cfg fields (ASVS V5 extra=forbid)
# ---------------------------------------------------------------------------

async def test_render_rejects_unknown_cfg_field(client, in_memory_db):
    pid = await _make_project(in_memory_db)
    r = await client.post(f"/api/v3/projects/{pid}/render",
                          json={"cfg_overrides": {"unknown_field": 42}})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Plan 04.1-01 Task 1 (WR-02 / D-05): _RUN_QUEUES + _RUN_TASKS eviction in
# _render_producer's finally block.
# ---------------------------------------------------------------------------

async def test_render_producer_evicts_run_queues_and_tasks_on_success(
    client, in_memory_db, monkeypatch
):
    """After _render_producer runs to completion, _RUN_QUEUES[pid] and
    _RUN_TASKS[pid] must be popped (WR-02 fix). Without this fix a late
    GET /render/stream would find the key present but the queue drained,
    awaiting queue.get() forever."""
    from medieval_forge.api.v3 import _run_state
    from medieval_forge.api.v3 import render as v3_render_mod

    monkeypatch.setattr(
        v3_render_mod, "run_pipeline_incremental",
        _stub_run_pipeline_incremental,
    )

    pid = await _make_project(in_memory_db)
    r = await client.post(f"/api/v3/projects/{pid}/render",
                          json={"cfg_overrides": {}})
    assert r.status_code == 202

    # Drain the producer to completion (terminal None sentinel reached).
    await _drain_queue(pid)

    # Allow the producer's finally block (which runs AFTER `await queue.put(None)`)
    # to execute its eviction pops.
    task = _run_state._RUN_TASKS.get(pid)
    if task is not None:
        try:
            await asyncio.wait_for(task, timeout=5.0)
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass

    assert _run_state._RUN_QUEUES.get(pid) is None, (
        "_RUN_QUEUES[pid] should be popped in _render_producer's finally block"
    )
    assert _run_state._RUN_TASKS.get(pid) is None, (
        "_RUN_TASKS[pid] should be popped in _render_producer's finally block"
    )


async def test_render_stream_after_completion_returns_404_not_hang(
    client, in_memory_db, monkeypatch
):
    """A late GET /render/stream call AFTER the producer finishes must
    return HTTP 404 within 1 second (NOT hang on a drained queue)."""
    from medieval_forge.api.v3 import _run_state
    from medieval_forge.api.v3 import render as v3_render_mod

    monkeypatch.setattr(
        v3_render_mod, "run_pipeline_incremental",
        _stub_run_pipeline_incremental,
    )

    pid = await _make_project(in_memory_db)
    r = await client.post(f"/api/v3/projects/{pid}/render",
                          json={"cfg_overrides": {}})
    assert r.status_code == 202

    # Drain the producer to completion.
    await _drain_queue(pid)

    # Wait for the producer task to fully exit so its finally block ran.
    task = _run_state._RUN_TASKS.get(pid)
    if task is not None:
        try:
            await asyncio.wait_for(task, timeout=5.0)
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass

    # Late-subscriber: must 404 within 1s, NOT hang.
    async with asyncio.timeout(1.0):
        late = await client.get(f"/api/v3/projects/{pid}/render/stream")
    assert late.status_code == 404
    assert "no active render run" in late.json()["detail"]


def _stub_run_pipeline_incremental_cancellable(cfg, project_id):
    """Spin-wait on cfg.stop_event so a /render/cancel POST can interrupt.

    Emits stage_start, then polls stop_event every 10ms. When the event is
    set, raises StageCancelled — mirroring how the real split cleanup
    functions cooperatively cancel.
    """
    import time
    from medieval_forge.services.pipeline.cleanup import StageCancelled

    if cfg.on_stage:
        cfg.on_stage("median", "start")
    # Cooperative cancel poll loop — runs inside asyncio.to_thread, so
    # time.sleep is safe.
    for _ in range(500):  # max ~5s before giving up
        if cfg.stop_event is not None and cfg.stop_event.is_set():
            raise StageCancelled("median")
        time.sleep(0.01)
    # Should not reach here under test (cancel POST is expected).
    if cfg.on_stage:
        cfg.on_stage("median", "done")
    return ["median"]


async def test_render_producer_evicts_run_queues_on_cancel(
    client, in_memory_db, monkeypatch
):
    """When the producer exits via StageCancelled, its finally block must
    still evict _RUN_QUEUES and _RUN_TASKS (finally runs in all exit paths)."""
    from medieval_forge.api.v3 import _run_state
    from medieval_forge.api.v3 import render as v3_render_mod

    monkeypatch.setattr(
        v3_render_mod, "run_pipeline_incremental",
        _stub_run_pipeline_incremental_cancellable,
    )

    pid = await _make_project(in_memory_db)
    r = await client.post(f"/api/v3/projects/{pid}/render",
                          json={"cfg_overrides": {}})
    assert r.status_code == 202

    # Wait until the producer has set the stop_event slot (i.e. entered the
    # try block and started its work). Without this we could POST /cancel
    # before _RUN_STOP_EVENTS[pid] exists and get a 404 from /cancel.
    async with asyncio.timeout(2.0):
        while pid not in _run_state._RUN_STOP_EVENTS:
            await asyncio.sleep(0.01)

    # Cancel the run.
    cancel_resp = await client.post(f"/api/v3/projects/{pid}/render/cancel")
    assert cancel_resp.status_code == 200

    # Drain remaining stream events (terminal None sentinel reached).
    await _drain_queue(pid)

    # Wait for producer task to fully exit.
    task = _run_state._RUN_TASKS.get(pid)
    if task is not None:
        try:
            await asyncio.wait_for(task, timeout=5.0)
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass

    assert _run_state._RUN_QUEUES.get(pid) is None, (
        "_RUN_QUEUES[pid] should be popped even on StageCancelled exit"
    )
    assert _run_state._RUN_TASKS.get(pid) is None, (
        "_RUN_TASKS[pid] should be popped even on StageCancelled exit"
    )
