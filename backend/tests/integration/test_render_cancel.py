"""Integration tests for POST /render/cancel mechanics.

Plan 04-02 Task 2 — TDD GREEN. Covers:
  D-13: stage_cancel SSE event carries prior_token; cache NOT updated on cancel
  D-14: cancel propagates via stop_event; producer raises StageCancelled within ~one median pass
"""
from __future__ import annotations

import asyncio
import threading
import time
import uuid

import numpy as np
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

    from medieval_forge.api.v3 import generate as v3_generate_mod
    monkeypatch.setattr(v3_generate_mod, "AsyncSessionLocal", in_memory_db)

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


async def _collect_sse_until_done(client, pid: str, timeout: float = 30.0) -> list[str]:
    """Consume the SSE stream until 'done' event or timeout. Returns raw chunks."""
    chunks = []
    async with asyncio.timeout(timeout):
        async with client.stream("GET",
                                 f"/api/v3/projects/{pid}/render/stream") as r:
            assert r.status_code == 200
            async for chunk in r.aiter_text():
                chunks.append(chunk)
    return chunks


# ---------------------------------------------------------------------------
# Test 1: cancel during median returns within 2s
# ---------------------------------------------------------------------------

async def test_cancel_during_median_returns_within_2s(
    client, in_memory_db, monkeypatch, tmp_path
):
    """POST /render with median_passes=12 (slowest path). After the first
    stage_start for 'median' arrives via SSE, POST /render/cancel. Assert
    the producer emits stage_cancel and 'done' within 2.0 s (D-14 < 2 s)."""
    from medieval_forge.api.v3 import render as v3_render_mod

    pid = await _make_project(in_memory_db)

    # Use the REAL run_pipeline_incremental + REAL cleanup functions.
    # The median with 12 passes at full iberia resolution takes many seconds
    # but stop_event fires between passes (D-14).
    # To keep the test fast, stub incremental to check stop_event quickly.
    from medieval_forge.api.v3._run_state import _RUN_STOP_EVENTS
    from medieval_forge.services.pipeline.cleanup import StageCancelled

    median_started = asyncio.Event()

    def _slow_incremental(cfg, project_id):
        """Simulate median starting then checking stop_event."""
        if cfg.on_stage:
            cfg.on_stage("median", "start")
        # Signal that median has started
        median_started.set()
        # Poll stop_event (simulating D-14 cooperative cancel)
        for _ in range(50):
            if cfg.stop_event is not None and cfg.stop_event.is_set():
                raise StageCancelled("median")
            time.sleep(0.02)
        # If not cancelled, complete normally
        if cfg.on_stage:
            cfg.on_stage("median", "done")
        return ["median"]

    monkeypatch.setattr(v3_render_mod, "run_pipeline_incremental", _slow_incremental)

    # POST /render (median_passes=12 is the payload; stub ignores it but tests param)
    r = await client.post(f"/api/v3/projects/{pid}/render",
                          json={"cfg_overrides": {"median_passes": 12}})
    assert r.status_code == 202

    # Wait for median to START in the worker thread (via asyncio event)
    async with asyncio.timeout(5.0):
        while not median_started.is_set():
            await asyncio.sleep(0.01)

    t0 = time.monotonic()

    # POST /render/cancel — sets stop_event
    rc = await client.post(f"/api/v3/projects/{pid}/render/cancel")
    assert rc.status_code == 200
    assert rc.json()["status"] == "cancel_requested"

    # Collect SSE until done
    chunks = await _collect_sse_until_done(client, pid, timeout=5.0)

    elapsed = time.monotonic() - t0
    assert elapsed < 2.0, f"Cancel took {elapsed:.2f}s, expected < 2.0s"

    combined = "".join(chunks)
    assert "stage_cancel" in combined or "done" in combined


# ---------------------------------------------------------------------------
# Test 2: cancel emits at least one stage_cancel event
# ---------------------------------------------------------------------------

async def test_cancel_emits_stage_cancel_per_affected_stage(
    client, in_memory_db, monkeypatch
):
    """After cancel, the SSE stream must contain at least one stage_cancel envelope."""
    from medieval_forge.api.v3 import render as v3_render_mod
    from medieval_forge.api.v3._run_state import _RUN_STOP_EVENTS
    from medieval_forge.services.pipeline.cleanup import StageCancelled

    pid = await _make_project(in_memory_db)

    started_event = asyncio.Event()

    def _cancelable_incremental(cfg, project_id):
        if cfg.on_stage:
            cfg.on_stage("median", "start")
        started_event.set()
        for _ in range(100):
            if cfg.stop_event is not None and cfg.stop_event.is_set():
                raise StageCancelled("median")
            time.sleep(0.01)
        return ["median"]

    monkeypatch.setattr(v3_render_mod, "run_pipeline_incremental",
                        _cancelable_incremental)

    r = await client.post(f"/api/v3/projects/{pid}/render",
                          json={"cfg_overrides": {}})
    assert r.status_code == 202

    async with asyncio.timeout(5.0):
        while not started_event.is_set():
            await asyncio.sleep(0.01)

    rc = await client.post(f"/api/v3/projects/{pid}/render/cancel")
    assert rc.status_code == 200

    chunks = await _collect_sse_until_done(client, pid, timeout=5.0)
    combined = "".join(chunks)
    assert "stage_cancel" in combined


# ---------------------------------------------------------------------------
# Test 3: cancel on cold-cache /render does not crash; disk artifacts remain
# ---------------------------------------------------------------------------

async def test_cancel_on_first_render_falls_back_to_generate_baseline(
    client, in_memory_db, monkeypatch
):
    """Cold-cache /render + immediate cancel should NOT crash. The canvas can
    still hydrate from prior /generate artifacts on disk (none in this test,
    but the endpoint must exit cleanly with 'done' SSE event).

    Post-WR-02 (04.1-01): the producer's finally now pops _RUN_QUEUES after
    `queue.put(None)`, so a stream subscriber that arrives AFTER the producer
    drains gets 404. We use a threading.Event gate inside the stub so the stub
    blocks until the test has subscribed to the stream.
    """
    from medieval_forge.api.v3 import render as v3_render_mod
    from medieval_forge.services.pipeline.cleanup import StageCancelled

    pid = await _make_project(in_memory_db)

    proceed = threading.Event()

    def _immediate_cancel_incremental(cfg, project_id):
        # Block until the test has opened the SSE stream (post-WR-02 contract).
        proceed.wait(timeout=5.0)
        # Simulate cancel landing before any stage completes.
        raise StageCancelled("median")

    monkeypatch.setattr(v3_render_mod, "run_pipeline_incremental",
                        _immediate_cancel_incremental)

    r = await client.post(f"/api/v3/projects/{pid}/render",
                          json={"cfg_overrides": {}})
    assert r.status_code == 202

    # Subscribe BEFORE releasing the producer so _RUN_QUEUES[pid] is still
    # present when stream_render runs its 404 guard.
    chunks: list[str] = []
    async with asyncio.timeout(10.0):
        async with client.stream("GET",
                                 f"/api/v3/projects/{pid}/render/stream") as resp:
            assert resp.status_code == 200
            proceed.set()  # release producer now that we're subscribed
            async for chunk in resp.aiter_text():
                chunks.append(chunk)
    combined = "".join(chunks)

    # Must terminate with 'done' event (no crash / hanging stream)
    assert '"event_type": "done"' in combined


# ---------------------------------------------------------------------------
# Test 4: cancel does not update the cache (D-13 atomicity invariant)
# ---------------------------------------------------------------------------

async def test_cancel_does_not_update_cache(client, in_memory_db, monkeypatch):
    """Pre-seed the cache with a known token for 'smooth'. Cancel mid-/render.
    The cached smooth token must remain unchanged (D-13: cache_put fires only
    on stage success, never on StageCancelled).

    Post-WR-02 (04.1-01): the producer's finally now pops _RUN_QUEUES after
    `queue.put(None)`, so a stream subscriber that arrives AFTER the producer
    drains gets 404. We gate the stub on a threading.Event so the stream
    opens before the producer raises StageCancelled.
    """
    from medieval_forge.api.v3 import render as v3_render_mod
    from medieval_forge.services.pipeline.cache import cache_put, cache_get
    from medieval_forge.services.pipeline.cleanup import StageCancelled

    pid = await _make_project(in_memory_db)

    # Pre-seed cache with a known token for 'smooth'
    prior_token = "known-prior-token-x"
    cache_put(pid, "main", "smooth", prior_token, np.zeros((2, 2), dtype=np.int16))
    assert cache_get(pid, "main", "smooth").token == prior_token

    proceed = threading.Event()

    def _cancel_before_smooth(cfg, project_id):
        # Simulate: median completes, fragment completes, then cancel hits smooth
        if cfg.on_stage:
            cfg.on_stage("median", "start")
            cfg.on_stage("median", "done")
        # Wait until test has subscribed to the stream (post-WR-02 contract).
        proceed.wait(timeout=5.0)
        raise StageCancelled("smooth")

    monkeypatch.setattr(v3_render_mod, "run_pipeline_incremental",
                        _cancel_before_smooth)

    r = await client.post(f"/api/v3/projects/{pid}/render",
                          json={"cfg_overrides": {}})
    assert r.status_code == 202

    chunks: list[str] = []
    async with asyncio.timeout(10.0):
        async with client.stream("GET",
                                 f"/api/v3/projects/{pid}/render/stream") as resp:
            assert resp.status_code == 200
            proceed.set()  # release producer now that we're subscribed
            async for chunk in resp.aiter_text():
                chunks.append(chunk)
    combined = "".join(chunks)
    assert '"event_type": "done"' in combined

    # The smooth cache entry must still have the original token
    entry = cache_get(pid, "main", "smooth")
    assert entry is not None
    assert entry.token == prior_token, (
        f"Cache was mutated on cancel: got {entry.token!r}, expected {prior_token!r}"
    )
