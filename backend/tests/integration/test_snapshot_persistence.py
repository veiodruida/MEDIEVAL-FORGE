"""Phase 08 plan 08-03b — Snapshot + EditEvent persistence integration tests.

Covers REQ-IDs: PERSIST-01, PERSIST-02, BRANCH-02, BRANCH-03, TELEM-01
Decisions: D-10, D-12, D-37

Test inventory (8 + 1 threat-mitigation):
  1. POST /snapshots {trigger:"manual"} → 201 + {snapshot_id, seq:1}
  2. Second POST → seq:2 (monotonic per branch)
  3. GET /snapshots → list reverse-chronological by seq
  4. POST /snapshots/{sid}/restore → 200 + decoded SnapshotPayload
  5. POST with 11 MB decompressed payload → 413 (Pitfall 9 + V12)
  6. POST /edit-events {op_type:"move"} → 201; edits_since_snapshot increments to 1
  7. 25th edit-event POST triggers auto-snapshot with trigger="auto"; edits_since_snapshot resets to 0
  8. Serializer round-trip: geojson + config + log preserved exactly
  9. [T-08-03b-02] 10001st edit-event → 409 EDIT_LOG_FULL
"""
from __future__ import annotations

import json

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from medieval_forge.database import get_db
from medieval_forge.main import app
from medieval_forge.models import Base, Project, Branch


pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_engine):
    """AsyncClient with in-memory DB override."""
    async def _override():
        async with db_engine() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def project_id(db_engine):
    """Create a Project row and return its id."""
    async with db_engine() as session:
        proj = Project(name="Snapshot Test Project", region_key="iberia_868")
        session.add(proj)
        await session.commit()
        await session.refresh(proj)
        return proj.id


@pytest_asyncio.fixture
async def branch_id(client, project_id):
    """Lazy-create main branch and return its id."""
    resp = await client.get(f"/api/v3/projects/{project_id}/branches")
    assert resp.status_code == 200
    branches = resp.json()
    main = next(b for b in branches if b["is_main"])
    return main["id"]


MINIMAL_PAYLOAD = {
    "geojson": {"type": "FeatureCollection", "features": []},
    "region_config": {"region_key": "iberia_868", "rng_seed": 42},
    "edit_log": [{"op": "move", "vertex_id": "v-001", "to": [1.23, 4.56]}],
}


# ---------------------------------------------------------------------------
# Test 1: POST /snapshots → 201 + {snapshot_id, seq:1}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_POST_snapshots_manual_trigger_returns_201_with_snapshot_id_and_seq_1(
    client, project_id, branch_id
):
    """PERSIST-01: first manual snapshot → 201 + snapshot_id + seq=1."""
    resp = await client.post(
        f"/api/v3/projects/{project_id}/branches/{branch_id}/snapshots",
        json={"trigger": "manual", "payload": MINIMAL_PAYLOAD},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "snapshot_id" in data
    assert data["seq"] == 1
    assert "created_at" in data


# ---------------------------------------------------------------------------
# Test 2: second POST → seq:2 (monotonic)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_POST_snapshots_second_call_returns_seq_2(client, project_id, branch_id):
    """PERSIST-01: seq increments monotonically — first=1, second=2."""
    resp1 = await client.post(
        f"/api/v3/projects/{project_id}/branches/{branch_id}/snapshots",
        json={"trigger": "manual", "payload": MINIMAL_PAYLOAD},
    )
    assert resp1.status_code == 201
    assert resp1.json()["seq"] == 1

    resp2 = await client.post(
        f"/api/v3/projects/{project_id}/branches/{branch_id}/snapshots",
        json={"trigger": "manual", "payload": MINIMAL_PAYLOAD},
    )
    assert resp2.status_code == 201
    assert resp2.json()["seq"] == 2


# ---------------------------------------------------------------------------
# Test 3: GET /snapshots → reverse-chronological
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_GET_snapshots_returns_reverse_chronological_list_by_seq(
    client, project_id, branch_id
):
    """PERSIST-02: GET /snapshots returns snapshots with highest seq first."""
    for trigger in ("manual", "manual", "pre_slider_change"):
        r = await client.post(
            f"/api/v3/projects/{project_id}/branches/{branch_id}/snapshots",
            json={"trigger": trigger, "payload": MINIMAL_PAYLOAD},
        )
        assert r.status_code == 201

    resp = await client.get(
        f"/api/v3/projects/{project_id}/branches/{branch_id}/snapshots"
    )
    assert resp.status_code == 200
    snaps = resp.json()
    assert len(snaps) == 3
    # Reverse-chronological: seq should be descending
    seqs = [s["seq"] for s in snaps]
    assert seqs == sorted(seqs, reverse=True), f"expected descending seqs, got {seqs}"
    # First item has the highest seq
    assert snaps[0]["seq"] == 3
    assert snaps[-1]["seq"] == 1


# ---------------------------------------------------------------------------
# Test 4: POST /snapshots/{sid}/restore → 200 + decoded SnapshotPayload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_POST_restore_snapshot_returns_200_with_original_geojson_and_config(
    client, project_id, branch_id
):
    """PERSIST-02: restore endpoint returns decoded SnapshotPayload with exact data."""
    create_resp = await client.post(
        f"/api/v3/projects/{project_id}/branches/{branch_id}/snapshots",
        json={"trigger": "manual", "payload": MINIMAL_PAYLOAD},
    )
    assert create_resp.status_code == 201
    snapshot_id = create_resp.json()["snapshot_id"]

    restore_resp = await client.post(
        f"/api/v3/projects/{project_id}/branches/{branch_id}/snapshots/{snapshot_id}/restore"
    )
    assert restore_resp.status_code == 200
    restored = restore_resp.json()
    assert restored["geojson"] == MINIMAL_PAYLOAD["geojson"]
    assert restored["region_config"] == MINIMAL_PAYLOAD["region_config"]
    assert restored["edit_log"] == MINIMAL_PAYLOAD["edit_log"]


# ---------------------------------------------------------------------------
# Test 5: 11 MB payload → 413 (Pitfall 9 + V12)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_POST_snapshots_with_11mb_payload_returns_413(
    client, project_id, branch_id
):
    """T-08-03b-01: payload exceeding 10 MB decompressed cap returns 413."""
    # 11 MB of raw ASCII data (compressible, but we check pre-compress size)
    oversized_string = "A" * (11 * 1024 * 1024)
    large_payload = {
        "geojson": {"type": "FeatureCollection", "features": [], "oversized": oversized_string},
        "region_config": {},
        "edit_log": [],
    }
    resp = await client.post(
        f"/api/v3/projects/{project_id}/branches/{branch_id}/snapshots",
        json={"trigger": "manual", "payload": large_payload},
    )
    assert resp.status_code == 413


# ---------------------------------------------------------------------------
# Test 6: POST /edit-events → 201; edits_since_snapshot increments to 1
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_POST_edit_event_returns_201_and_increments_edits_since_snapshot_to_1(
    client, project_id, branch_id
):
    """D-35 + D-37: first edit-event increments counter from 0 to 1; no auto-snapshot."""
    resp = await client.post(
        f"/api/v3/projects/{project_id}/branches/{branch_id}/edit-events",
        json={"op_type": "vertex_move", "payload": {"vertex_id": "v-001", "to": [1.23, 4.56]}},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "event_id" in data
    assert data["edits_since_snapshot"] == 1
    assert data["auto_snapshot"] is None


# ---------------------------------------------------------------------------
# Test 7: 25th edit-event triggers auto-snapshot, counter resets to 0
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_POST_25th_edit_event_triggers_auto_snapshot_and_resets_counter_to_0(
    client, project_id, branch_id
):
    """D-37: auto-snapshot fires at edits_since_snapshot == 25; counter resets to 0."""
    # Post 24 edit-events without snapshot_payload_if_due
    for i in range(24):
        r = await client.post(
            f"/api/v3/projects/{project_id}/branches/{branch_id}/edit-events",
            json={
                "op_type": "vertex_move",
                "payload": {"vertex_id": f"v-{i:03d}", "to": [float(i), float(i)]},
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["auto_snapshot"] is None
        assert data["edits_since_snapshot"] == i + 1

    # 25th edit-event — include snapshot_payload_if_due to trigger auto-snapshot
    resp25 = await client.post(
        f"/api/v3/projects/{project_id}/branches/{branch_id}/edit-events",
        json={
            "op_type": "vertex_move",
            "payload": {"vertex_id": "v-024", "to": [24.0, 24.0]},
            "snapshot_payload_if_due": MINIMAL_PAYLOAD,
        },
    )
    assert resp25.status_code == 201
    data25 = resp25.json()
    # Auto-snapshot was created
    assert data25["auto_snapshot"] is not None
    assert "snapshot_id" in data25["auto_snapshot"]
    assert data25["auto_snapshot"]["seq"] == 1  # first snapshot on this branch
    # Counter reset to 0
    assert data25["edits_since_snapshot"] == 0


# ---------------------------------------------------------------------------
# Test 8: Serializer round-trip (pure unit — no HTTP)
# ---------------------------------------------------------------------------

def test_snapshot_serializer_roundtrip_preserves_geojson_config_and_edit_log_exactly():
    """BRANCH-03: serialize → deserialize identity; gzip header present; no data loss."""
    from medieval_forge.services.branches.snapshot import serialize, deserialize

    payload = {
        "geojson": {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-9.1, 38.7]},
             "properties": {"id": "barony-001", "name": "Lisboa", "original_idx": 1}}
        ]},
        "region_config": {"region_key": "iberia_868", "rng_seed": 42, "sigma": 3.5},
        "edit_log": [
            {"op": "vertex_move", "vertex_id": "v-001", "from": [0.0, 0.0], "to": [1.23, 4.56]},
            {"op": "vertex_add", "polygon_id": "p-002", "at": [2.34, 5.67]},
        ],
    }

    blob = serialize(payload)
    # gzip magic bytes: 0x1f 0x8b
    assert blob[:2] == b"\x1f\x8b", "blob should start with gzip magic bytes"

    restored = deserialize(blob)
    assert restored == payload


# ---------------------------------------------------------------------------
# Test 9 [T-08-03b-02]: 10001st edit-event → 409 EDIT_LOG_FULL
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_POST_edit_event_returns_409_edit_log_full_after_10000_events(
    client, project_id, branch_id, db_engine
):
    """T-08-03b-02 mitigate: cap edit log at 10,000 ops per branch → 409 EDIT_LOG_FULL."""
    from sqlalchemy import insert
    from medieval_forge.models import EditEvent

    # Bulk-insert 10,000 EditEvent rows directly (avoid 10k HTTP calls)
    async with db_engine() as session:
        await session.execute(
            insert(EditEvent),
            [
                {"branch_id": branch_id, "op_type": "vertex_move",
                 "payload": {"vertex_id": f"v-{i}"}}
                for i in range(10_000)
            ],
        )
        await session.commit()

    # 10001st edit-event via HTTP → should be blocked
    resp = await client.post(
        f"/api/v3/projects/{project_id}/branches/{branch_id}/edit-events",
        json={"op_type": "vertex_move", "payload": {"vertex_id": "v-overflow"}},
    )
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "EDIT_LOG_FULL" in str(detail)
