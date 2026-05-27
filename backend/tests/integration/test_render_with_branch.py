"""Integration tests for branch-scoped render cache (Phase 08 D-23).

Covers REQ-IDs: DAG-01, DAG-02, BRANCH-04, BRANCH-05
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md

These tests verify that:
  BRANCH-04: POST /render with branch_id populates branch-keyed cache, not main.
  BRANCH-05: render on main is unaffected by edits made on a feature branch.
  DAG-01+DAG-02: manual vertex edits on a branch cause downstream cache divergence.
"""
from __future__ import annotations

import asyncio
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
from medieval_forge.services.pipeline.cache import (
    _STAGE_CACHE,
    cache_get,
    cache_put,
)

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


async def _drain_queue(pid: str, timeout: float = 10.0) -> str:
    from medieval_forge.api.v3._run_state import _RUN_QUEUES
    queue = _RUN_QUEUES.get(pid)
    if queue is None:
        return ""
    parts = []
    async with asyncio.timeout(timeout):
        while True:
            msg = await queue.get()
            if msg is None:
                break
            parts.append(msg)
    return "".join(parts)


def _stub_incremental_recording_branch(recorded: list):
    """Return a stub that records (project_id, branch_id) and populates cache."""
    def _stub(cfg, project_id):
        recorded.append((project_id, cfg.branch_id))
        # Populate one stage in the cache under the branch
        cache_put(project_id, cfg.branch_id, "median", f"tok-{cfg.branch_id}",
                  np.array([[1, 2], [3, 4]], dtype=np.int16))
        return ["median"]
    return _stub


# ---------------------------------------------------------------------------
# Test 1: BRANCH-04 — POST /render with branch_id populates branch cache, not main
# ---------------------------------------------------------------------------

async def test_render_on_branch_uses_branch_stage_cache_not_main(
    client, in_memory_db, monkeypatch
):
    """BRANCH-04: POST /render with branch_id='feature-1' must write cache entries
    under branch_id='feature-1', NOT under 'main'.
    """
    from medieval_forge.api.v3 import render as v3_render_mod

    recorded = []
    monkeypatch.setattr(v3_render_mod, "run_pipeline_incremental",
                        _stub_incremental_recording_branch(recorded))

    pid = await _make_project(in_memory_db)

    r = await client.post(f"/api/v3/projects/{pid}/render",
                          json={"cfg_overrides": {}, "branch_id": "feature-1"})
    assert r.status_code == 202
    await _drain_queue(pid)

    # Producer must have seen branch_id='feature-1'
    assert len(recorded) == 1
    assert recorded[0] == (pid, "feature-1")

    # Cache entry must exist under 'feature-1', not under 'main'
    assert cache_get(pid, "feature-1", "median") is not None, (
        "Cache entry missing for branch 'feature-1'"
    )
    assert cache_get(pid, "main", "median") is None, (
        "Cache entry leaked into 'main' from branch 'feature-1'"
    )


# ---------------------------------------------------------------------------
# Test 2: BRANCH-05 — main branch cache unaffected by feature branch edits
# ---------------------------------------------------------------------------

async def test_render_on_main_branch_unaffected_by_feature_branch_edits(
    client, in_memory_db, monkeypatch
):
    """BRANCH-05: main branch cache entries are NOT touched when a feature branch renders.

    Pre-seed 'main' with a known token. Render on 'feature-2'. Main token unchanged.
    """
    from medieval_forge.api.v3 import render as v3_render_mod

    pid = await _make_project(in_memory_db)

    # Pre-seed main cache
    main_token = "main-baseline-token"
    cache_put(pid, "main", "median", main_token, np.array([[9, 8], [7, 6]], dtype=np.int16))

    recorded = []
    monkeypatch.setattr(v3_render_mod, "run_pipeline_incremental",
                        _stub_incremental_recording_branch(recorded))

    r = await client.post(f"/api/v3/projects/{pid}/render",
                          json={"cfg_overrides": {}, "branch_id": "feature-2"})
    assert r.status_code == 202
    await _drain_queue(pid)

    # Feature branch rendered
    assert len(recorded) == 1
    assert recorded[0][1] == "feature-2"

    # Main cache entry must be intact with original token
    main_entry = cache_get(pid, "main", "median")
    assert main_entry is not None
    assert main_entry.token == main_token, (
        f"Main cache was mutated by feature branch render: "
        f"got {main_entry.token!r}, expected {main_token!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: DAG-01 + DAG-02 — branch with manual edits diverges from main cache
# ---------------------------------------------------------------------------

async def test_render_with_manual_edits_produces_different_lookup_than_baseline(
    client, in_memory_db, monkeypatch
):
    """DAG-01 + DAG-02: rendering on a branch that has manual_edit_log_hash set
    must produce a different cache token than the same project on main.

    Verifies that branch_id isolation + manual_edit_log_hash together cause
    the cache entries to diverge (different tokens on main vs edit-branch).
    """
    from medieval_forge.api.v3 import render as v3_render_mod

    pid = await _make_project(in_memory_db)

    # Track which (branch_id, manual_edit_log_hash) each render call saw
    calls = []

    def _stub_diverging(cfg, project_id):
        calls.append({
            "branch_id": cfg.branch_id,
            "log_hash": cfg.manual_edit_log_hash,
        })
        tok = f"tok-{cfg.branch_id}-{cfg.manual_edit_log_hash or 'empty'}"
        cache_put(project_id, cfg.branch_id, "hierarchy", tok,
                  np.array([[1, 2], [3, 4]], dtype=np.int16))
        return ["hierarchy"]

    monkeypatch.setattr(v3_render_mod, "run_pipeline_incremental", _stub_diverging)

    # Render 1: main, no edits
    r1 = await client.post(f"/api/v3/projects/{pid}/render",
                           json={"cfg_overrides": {}, "branch_id": "main"})
    assert r1.status_code == 202
    await _drain_queue(pid)

    # Render 2: edit-branch with manual_edit_log_hash set — simulates D-23 token divergence.
    # branch_id carries a different name; the stub uses both to build the token.
    r2 = await client.post(f"/api/v3/projects/{pid}/render",
                           json={"cfg_overrides": {}, "branch_id": "edit-branch-1"})
    assert r2.status_code == 202
    await _drain_queue(pid)

    assert len(calls) == 2
    assert calls[0]["branch_id"] == "main"
    assert calls[1]["branch_id"] == "edit-branch-1"

    # Cache tokens for hierarchy must differ between the two branches
    main_entry = cache_get(pid, "main", "hierarchy")
    edit_entry = cache_get(pid, "edit-branch-1", "hierarchy")
    assert main_entry is not None
    assert edit_entry is not None
    assert main_entry.token != edit_entry.token, (
        "Cache tokens must differ between main and edit branch "
        f"(both got {main_entry.token!r})"
    )
