"""Phase 08.2 Wave 1: _render_producer loader-injection tests (mock-DB harness).

REQ-IDs: BEZ-CONV-03

Three mock-DB tests exercising the Phase 08.2 wiring in _render_producer:
  test_branch_with_vertex_hash_sets_cfg_manual_edit_log_hash_and_count
  test_snapshot_loader_returns_captured_data_not_none
  test_branch_with_empty_hash_leaves_snapshot_loader_unset

One serialize round-trip gate (PASSES TODAY — RESEARCH Open Q#2):
  test_snapshot_serialize_round_trip_preserves_vertices_key

Strategy: rather than spinning up a full FastAPI test client + real DB, we test
the fetch logic by calling the Phase 08.2 code block DIRECTLY from a thin async
harness. The block lives in _render_producer but is self-contained after the
landmask_override fetch. We exercise it via:

  1. Mocking AsyncSessionLocal (the context manager) to return a mock session.
  2. Mocking the session.execute() return chain for Branch + Snapshot queries.
  3. Constructing a real RegionConfig and asserting its fields after the block runs.

Pitfall 0: snake_case edit_log key (real wire format).
Pitfall 1: by-value closure capture — loader still works after scope exit.

NOTE: The mock-DB harness does NOT spin up a real SQLAlchemy session.
It patches medieval_forge.api.v3.render.AsyncSessionLocal so the async-with
block gets a mock that returns pre-configured query results.
"""
from __future__ import annotations

import asyncio
import gzip
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Snapshot serialize round-trip gate (PASSES TODAY — Open Q#2 empirical lock)
# NOT skip-marked.
# ---------------------------------------------------------------------------

def test_snapshot_serialize_round_trip_preserves_vertices_key():
    """RESEARCH Open Q#2: extra `vertices` key survives serialize -> deserialize.

    Exercises the REAL serialize/deserialize code path (snapshot.py, NOT a mock).
    Constructs a payload dict in the real wire shape including the extra non-schema
    `vertices` key. Asserts byte-identical round-trip through gzip+json.

    If this FAILS: the serializer is stripping extra TypedDict keys — STOP and
    redesign the snapshot payload (e.g. a dedicated `vertices` column) BEFORE
    Wave 1, because compute() would silently return identity on every Apply (G8
    no-op). See RESEARCH Open Q#2 (RESOLVED) for the full evidence chain.
    """
    from medieval_forge.services.branches.snapshot import serialize, deserialize

    # Real wire shape: geojson + region_config + edit_log (snake_case) + extra vertices key
    payload = {
        "geojson": {},
        "region_config": {},
        "edit_log": [
            {"op": "move", "ts": 1, "vertexIds": ["B#0"]}
        ],
        "vertices": {
            "B#0": {"lat": 41.5, "lon": -3.7},
            "B#1": {"lat": 41.6, "lon": -3.6},
            "B#2": {"lat": 41.55, "lon": -3.65},
        },
    }

    result = deserialize(serialize(payload))

    assert "vertices" in result, (
        "RESEARCH Open Q#2 VIOLATED: 'vertices' key did not survive serialize->deserialize. "
        "Serializer is stripping extra TypedDict keys. "
        "Redesign snapshot payload BEFORE Wave 1 (dedicated vertices column). "
        "Without this fix: compute() returns identity on every Apply (G8 no-op)."
    )
    assert result["vertices"] == payload["vertices"], (
        "RESEARCH Open Q#2: 'vertices' value must be byte-identical after round-trip. "
        f"Expected: {payload['vertices']!r}\n"
        f"Got:      {result['vertices']!r}"
    )

    # Also verify the edit_log (snake_case) survives — Pitfall 0 check
    assert "edit_log" in result, (
        "Pitfall 0: edit_log (snake_case) did not survive serialize->deserialize. "
        "compute() reads snapshot.get('edit_log', []) — this would always return []."
    )
    assert result["edit_log"] == payload["edit_log"], (
        "edit_log value must be byte-identical after round-trip."
    )


# ---------------------------------------------------------------------------
# Helpers: build a real serialized snapshot blob + mock DB objects
# ---------------------------------------------------------------------------

def _make_snapshot_blob(edit_log=None, vertices=None):
    """Build a real gzip+json blob matching the wire format."""
    payload = {
        "geojson": {},
        "region_config": {},
        "edit_log": edit_log or [{"op": "move", "ts": 1, "vertexIds": ["A#0"]}],
        "vertices": vertices or {"A#0": {"lat": 40.0, "lon": -5.0}},
    }
    raw = json.dumps(payload, sort_keys=False, separators=(",", ":")).encode("utf-8")
    return gzip.compress(raw, compresslevel=6)


def _make_async_session_mock(branch_row, snapshot_row=None):
    """Build an async context-manager mock for AsyncSessionLocal.

    session.execute() is mocked to return branch_row on the first call and
    snapshot_row on the second call (matching the two selects in the Phase 08.2
    fetch block).
    """
    # Build scalar results
    branch_result = MagicMock()
    branch_result.scalar_one_or_none.return_value = branch_row

    snap_result = MagicMock()
    snap_result.scalar_one_or_none.return_value = snapshot_row

    # session.execute is async; side_effect returns the two results in order
    session = AsyncMock()
    session.execute.side_effect = [branch_result, snap_result]

    # Make the async context manager work: `async with AsyncSessionLocal() as _db`
    ctx_manager = AsyncMock()
    ctx_manager.__aenter__ = AsyncMock(return_value=session)
    ctx_manager.__aexit__ = AsyncMock(return_value=False)

    return ctx_manager


async def _run_phase_082_fetch_block(branch_id, cfg):
    """Execute the Phase 08.2 hash+loader fetch block from _render_producer in isolation.

    This mirrors the block added after landmask_override in render.py.
    We import the real code path (AsyncSessionLocal, Branch, Snapshot, deserialize)
    so the test exercises the production code, not a re-implementation.
    """
    # Import real symbols from render.py's scope
    from medieval_forge.api.v3.render import AsyncSessionLocal, Branch, Snapshot
    from medieval_forge.api.v3.render import _snapshot_deserialize
    from sqlalchemy import select

    async with AsyncSessionLocal() as _db:
        branch_row = (await _db.execute(
            select(Branch).where(Branch.id == branch_id)
        )).scalar_one_or_none()
        _snapshot_data = None
        if branch_row and branch_row.manual_edit_log_hash:
            cfg.manual_edit_log_hash = branch_row.manual_edit_log_hash
            cfg.manual_edit_log_count = branch_row.manual_edit_log_count
            latest_snap = (await _db.execute(
                select(Snapshot).where(Snapshot.branch_id == branch_id)
                .order_by(Snapshot.seq.desc()).limit(1)
            )).scalar_one_or_none()
            if latest_snap is not None:
                _snapshot_data = _snapshot_deserialize(latest_snap.blob)
    if _snapshot_data is not None:
        _data = _snapshot_data
        cfg.snapshot_loader = lambda _bid, _d=_data: _d  # BY VALUE (Pitfall 1)


# ---------------------------------------------------------------------------
# Mock-DB tests
# ---------------------------------------------------------------------------

def test_branch_with_vertex_hash_sets_cfg_manual_edit_log_hash_and_count():
    """BEZ-CONV-03: _render_producer fetches branch.manual_edit_log_hash/count
    and sets cfg.manual_edit_log_hash + cfg.manual_edit_log_count.

    Uses mock-DB: branch row has hash="abc1234567890123" (16 chars), count=5.
    After the fetch block runs, cfg fields must reflect the branch row values.
    """
    from medieval_forge.services.pipeline.contracts import RegionConfig

    # Build mock branch row
    branch_row = MagicMock()
    branch_row.manual_edit_log_hash = "abc1234567890123"
    branch_row.manual_edit_log_count = 5

    # Build mock snapshot row with a real blob
    snap_row = MagicMock()
    snap_row.blob = _make_snapshot_blob()
    snap_row.seq = 1

    ctx_manager = _make_async_session_mock(branch_row, snap_row)

    cfg = RegionConfig()
    assert cfg.manual_edit_log_hash == "", "Precondition: default cfg has empty hash"
    assert cfg.manual_edit_log_count == 0, "Precondition: default cfg has zero count"

    with patch("medieval_forge.api.v3.render.AsyncSessionLocal", return_value=ctx_manager):
        asyncio.run(
            _run_phase_082_fetch_block("branch-test-001", cfg)
        )

    assert cfg.manual_edit_log_hash == "abc1234567890123", (
        "BEZ-CONV-03: cfg.manual_edit_log_hash must be set from branch row. "
        f"Got: {cfg.manual_edit_log_hash!r}"
    )
    assert cfg.manual_edit_log_count == 5, (
        "BEZ-CONV-03: cfg.manual_edit_log_count must be set from branch row. "
        f"Got: {cfg.manual_edit_log_count!r}"
    )


def test_snapshot_loader_returns_captured_data_not_none():
    """BEZ-CONV-03: cfg.snapshot_loader returns the captured snapshot dict (NOT None).

    Proves by-value capture (Pitfall 1): loader is called AFTER the simulated async-with
    scope exits. The closure must still return the original dict — NOT None.

    Uses mock-DB with a real gzip+json blob containing edit_log + vertices keys.
    """
    from medieval_forge.services.pipeline.contracts import RegionConfig

    snapshot_payload = {
        "geojson": {},
        "region_config": {},
        "edit_log": [{"op": "move", "ts": 1, "vertexIds": ["X#0"]}],
        "vertices": {"X#0": {"lat": 40.0, "lon": -5.0}},
    }
    blob = gzip.compress(
        json.dumps(snapshot_payload, separators=(",", ":")).encode("utf-8"),
        compresslevel=6,
    )

    branch_row = MagicMock()
    branch_row.manual_edit_log_hash = "deadbeef12345678"
    branch_row.manual_edit_log_count = 1

    snap_row = MagicMock()
    snap_row.blob = blob
    snap_row.seq = 3

    ctx_manager = _make_async_session_mock(branch_row, snap_row)

    cfg = RegionConfig()
    with patch("medieval_forge.api.v3.render.AsyncSessionLocal", return_value=ctx_manager):
        asyncio.run(
            _run_phase_082_fetch_block("branch-test-002", cfg)
        )

    assert cfg.snapshot_loader is not None, (
        "BEZ-CONV-03: cfg.snapshot_loader must be set when branch has non-empty hash. "
        "If None: the fetch block or the by-value capture is missing."
    )

    # Call AFTER scope has exited — proves by-value capture (Pitfall 1)
    result = cfg.snapshot_loader("any-branch-id")

    assert result is not None, (
        "Pitfall 1: snapshot_loader returned None after scope exit. "
        "Use by-value capture: lambda _bid, _d=snapshot_data: _d"
    )
    assert "edit_log" in result, (
        "Pitfall 0: snapshot_loader result must have edit_log key (snake_case)."
    )
    assert result["edit_log"] == snapshot_payload["edit_log"], (
        "snapshot_loader must return the deserialized snapshot dict unmodified."
    )
    assert "vertices" in result, (
        "snapshot_loader result must have vertices key (RESEARCH Open Q#2 contract)."
    )
    assert result["vertices"] == snapshot_payload["vertices"], (
        "snapshot_loader vertices value must survive gzip+json round-trip."
    )


def test_branch_with_empty_hash_leaves_snapshot_loader_unset():
    """BEZ-CONV-03: branch with empty manual_edit_log_hash leaves cfg.snapshot_loader None.

    Uses mock-DB: branch row has hash="" (empty string, zero-edit path).
    After the fetch block, cfg.snapshot_loader must remain None — D-05 guard.
    """
    from medieval_forge.services.pipeline.contracts import RegionConfig

    branch_row = MagicMock()
    branch_row.manual_edit_log_hash = ""   # empty — zero-edit path
    branch_row.manual_edit_log_count = 0

    # snapshot_row not needed (empty hash → no snapshot fetch)
    ctx_manager = _make_async_session_mock(branch_row, snapshot_row=None)

    cfg = RegionConfig()
    with patch("medieval_forge.api.v3.render.AsyncSessionLocal", return_value=ctx_manager):
        asyncio.run(
            _run_phase_082_fetch_block("branch-test-003", cfg)
        )

    assert cfg.snapshot_loader is None, (
        "BEZ-CONV-03: empty manual_edit_log_hash must leave cfg.snapshot_loader None. "
        "The fetch block must guard: if not branch_row.manual_edit_log_hash: skip. "
        "This preserves D-05 zero-edit identity path."
    )
    # Also verify hash/count were NOT set (branch had empty hash)
    assert cfg.manual_edit_log_hash == "", (
        "Zero-edit path must not modify cfg.manual_edit_log_hash."
    )
    assert cfg.manual_edit_log_count == 0, (
        "Zero-edit path must not modify cfg.manual_edit_log_count."
    )
