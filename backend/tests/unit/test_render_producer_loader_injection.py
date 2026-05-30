"""Phase 08.2 Wave 0: _render_producer loader-injection scaffold + snapshot serialize gate.

REQ-IDs: BEZ-CONV-03

Three mock-DB tests (skip-marked until Plan 02 wires _render_producer):
  test_branch_with_vertex_hash_sets_cfg_manual_edit_log_hash_and_count
  test_snapshot_loader_returns_captured_data_not_none
  test_branch_with_empty_hash_leaves_snapshot_loader_unset

One serialize round-trip gate (PASSES TODAY — RESEARCH Open Q#2):
  test_snapshot_serialize_round_trip_preserves_vertices_key

RESEARCH Open Q#2 (RESOLVED 2026-05-30):
  The extra `vertices` key survives gzip+json serialize -> deserialize because:
  - SnapshotPayload is a TypedDict (NOT runtime-enforced; plain dict at runtime)
  - serialize() calls json.dumps(payload) on the whole dict (key-preserving)
  - deserialize() calls json.loads() (key-preserving)
  - branches.py:146 declares payload: dict[str, Any] (not a Pydantic model)
  This test locks that contract so a future serializer change is caught BEFORE
  Wave 1 wires the loader — otherwise compute() silently returns identity (G8 no-op).

Pitfall 0 reference: the real wire format uses snake_case `edit_log` key.
  snapshots.ts:58 sends { vertices, editLog } (camelCase) — this is the BLOCKER.
  Plan 03 Apply handler must rename editLog -> edit_log before serialize().
  The mock-DB tests and the e2e test use snake_case edit_log throughout.

Pitfall 1 reference: by-value closure capture for snapshot_loader.
  test_snapshot_loader_returns_captured_data_not_none calls the loader AFTER
  the simulated async-with scope to catch reference-capture bugs.
"""
from __future__ import annotations

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
# Mock-DB tests (skip-marked until Plan 02 wires _render_producer)
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Wave 1: _render_producer wiring not yet added")
def test_branch_with_vertex_hash_sets_cfg_manual_edit_log_hash_and_count():
    """BEZ-CONV-03: _render_producer fetches branch.manual_edit_log_hash/count
    and sets cfg.manual_edit_log_hash + cfg.manual_edit_log_count.

    Plan 02 wire: after the existing landmask_override fetch block (render.py lines
    148-167), fetch branch.manual_edit_log_hash / manual_edit_log_count from DB and
    set cfg fields if non-empty. Mirror the landmask_override pattern exactly.

    Pitfall 0: the branch row uses snake_case manual_edit_log_hash (DB column name).
    """
    # When Plan 02 un-skips this test, implement as follows:
    # 1. Import _render_producer (or the extracted fetch block) from render.py.
    # 2. Mock AsyncSessionLocal to return a DB session with a Branch row:
    #    branch_row.manual_edit_log_hash = "abc123"
    #    branch_row.manual_edit_log_count = 5
    # 3. Create a RegionConfig with empty hash (default state).
    # 4. Run the fetch block (the new Wave 1 code after landmask_override block).
    # 5. Assert cfg.manual_edit_log_hash == "abc123"
    # 6. Assert cfg.manual_edit_log_count == 5
    from medieval_forge.services.pipeline.contracts import RegionConfig

    cfg = RegionConfig()
    # Placeholder: will be replaced by real mock-DB assertion in Plan 02
    assert cfg.manual_edit_log_hash == "", (
        "Precondition: default cfg has empty manual_edit_log_hash"
    )
    assert cfg.manual_edit_log_count == 0, (
        "Precondition: default cfg has zero manual_edit_log_count"
    )
    # TODO (Plan 02): after _render_producer fetch block runs against mock branch row,
    # assert cfg.manual_edit_log_hash == "abc123" and cfg.manual_edit_log_count == 5.
    pytest.fail("Not implemented yet — Plan 02 must implement the fetch block and this assertion.")


@pytest.mark.skip(reason="Wave 1: _render_producer wiring not yet added")
def test_snapshot_loader_returns_captured_data_not_none():
    """BEZ-CONV-03: cfg.snapshot_loader returns the captured snapshot dict (NOT None).

    Proves by-value capture (Pitfall 1): loader is called AFTER the simulated async-with
    scope to catch reference-capture bugs where the closure captured a variable that
    became None after the scope exited.

    Plan 02 wire: use the by-value default-arg idiom:
        cfg.snapshot_loader = lambda _bid, _d=snapshot_data: _d
    NOT: cfg.snapshot_loader = lambda _: snapshot_data  (reference capture; Pitfall 1)

    The loader is keyed by branch_id (first positional arg); the test calls it with
    any string to prove the capture is by value.
    """
    # When Plan 02 un-skips this test, implement as follows:
    # 1. Simulate _render_producer's async-with DB session:
    #    async with AsyncSessionLocal() as db:
    #        snap = await latest_snapshot_for_branch(db, branch_id)
    #        snapshot_data = deserialize(snap.blob)
    #        # by-value capture:
    #        cfg.snapshot_loader = lambda _bid, _d=snapshot_data: _d
    # 2. snapshot_data = {"edit_log": [...], "vertices": {...}} (snake_case, Pitfall 0)
    # 3. After the simulated async-with scope exits, call cfg.snapshot_loader("any-branch").
    # 4. Assert the result is the same dict (not None, not empty).
    # This proves by-value capture is used (Pitfall 1 fix).
    from medieval_forge.services.pipeline.contracts import RegionConfig

    # Simulate the by-value capture pattern _render_producer MUST use:
    snapshot_data = {
        "edit_log": [{"op": "move", "ts": 1, "vertexIds": ["X#0"]}],  # snake_case
        "vertices": {"X#0": {"lat": 40.0, "lon": -5.0}},
    }
    cfg = RegionConfig()
    # By-value capture (the correct pattern):
    cfg.snapshot_loader = lambda _bid, _d=snapshot_data: _d
    # Simulate scope exit — in the real case, the async-with block has exited
    snapshot_data = None  # type: ignore[assignment]  # simulate reference becoming None

    # Call AFTER scope exit — by-value capture must still return the original dict
    result = cfg.snapshot_loader("any-branch")
    assert result is not None, (
        "Pitfall 1: snapshot_loader returned None after scope exit. "
        "Use by-value capture: lambda _bid, _d=snapshot_data: _d"
    )
    assert "edit_log" in result, (
        "Pitfall 0: snapshot_loader result must have edit_log key (snake_case). "
        "Plan 02 Apply handler must rename editLog -> edit_log before serialize()."
    )
    assert "vertices" in result, (
        "snapshot_loader result must have vertices key. "
        "RESEARCH Open Q#2 gate proves vertices survives serialize->deserialize."
    )


@pytest.mark.skip(reason="Wave 1: _render_producer wiring not yet added")
def test_branch_with_empty_hash_leaves_snapshot_loader_unset():
    """BEZ-CONV-03: branch with empty manual_edit_log_hash leaves cfg.snapshot_loader None.

    The zero-edit identity path must be untouched — only non-empty hash branches
    inject a loader. This prevents snapshot DB fetch for projects with no edits,
    preserving the D-05 performance contract.
    """
    # When Plan 02 un-skips this test, implement as follows:
    # 1. Mock branch row with manual_edit_log_hash = "" (empty string).
    # 2. Run the new Wave 1 fetch block in _render_producer.
    # 3. Assert cfg.snapshot_loader is None (not set).
    from medieval_forge.services.pipeline.contracts import RegionConfig

    cfg = RegionConfig()
    branch_hash = ""  # empty — zero-edit path
    # The fetch block MUST NOT set snapshot_loader when hash is empty:
    if branch_hash:
        # This branch would be taken in Plan 02 for non-empty hash
        cfg.snapshot_loader = lambda _bid: {}  # placeholder

    # Assert loader is NOT set for empty hash
    assert cfg.snapshot_loader is None, (
        "BEZ-CONV-03: empty manual_edit_log_hash must leave cfg.snapshot_loader None. "
        "Plan 02 must guard: if not branch_hash: skip snapshot fetch. "
        "This preserves D-05 zero-edit identity path."
    )
