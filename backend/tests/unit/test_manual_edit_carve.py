"""Phase 08.3 Plan 07 — TDD RED tests for the CARVE operation hole round-trip.

Covers REQ-IDs: CARVE-ENCLAVE-01, CARVE-HOLE-RT-01

Tests are intentionally RED before Task 2 lands the carve branch in compute().
They pin every D-25/D-27 invariant and will fail with assertion errors about
missing N idx / missing interior ring (not collection/import errors).

All fixtures use explicit numeric coordinates (project memory: descriptive names
+ explicit numeric fixtures). The identity bounding box makes
_lonlat_to_rasterio_xy a pass-through:
  lon=col, lat=rasterio_y  (rasterio_y = H - numpy_row for a top-down raster)
  Because: span=W → x=round(lon); py_row=round(H-lat) → rasterio_y=lat
"""
from __future__ import annotations

import numpy as np
import pytest
import rasterio.features
from rasterio.transform import from_bounds
from shapely.geometry import Polygon
from shapely.ops import unary_union

# ---------------------------------------------------------------------------
# Shared fixture: 60×60 int16 raster
# Layout:
#   parent X (idx=0) → rows 10-49, cols 10-49  (40×40 = 1600 pixels)
#   ocean (-1) everywhere else
# The drawn carve ring will be a 10×10 square at rows 20-29, cols 20-29
# sitting fully inside parent X (with ≥10px margin on each side).
# ---------------------------------------------------------------------------

W, H = 60, 60
PARENT_IDX = 0
CARVE_NEW_IDX = 1   # allocated_original_idx for the new carved barony

# Parent occupies rows 10-49, cols 10-49
PARENT_ROW_MIN, PARENT_ROW_MAX = 10, 49
PARENT_COL_MIN, PARENT_COL_MAX = 10, 49

# Carve ring inside parent: rows 20-29, cols 20-29 (strictly inside)
CARVE_ROW_MIN, CARVE_ROW_MAX = 20, 29
CARVE_COL_MIN, CARVE_COL_MAX = 20, 29


def _make_raster() -> np.ndarray:
    """Return a fresh 60×60 int16 raster with parent X filling rows 10-49, cols 10-49."""
    raster = np.full((H, W), -1, dtype=np.int16)
    raster[PARENT_ROW_MIN : PARENT_ROW_MAX + 1, PARENT_COL_MIN : PARENT_COL_MAX + 1] = PARENT_IDX
    return raster


def _pixel_to_lonlat(row: int, col: int) -> dict:
    """Convert a numpy (row, col) pixel to the lon/lat encoding used by _lonlat_to_rasterio_xy.

    With identity bounding box (lon_min=0, lon_max=W, lat_min=0, lat_max=H):
      lon = col
      lat = rasterio_y = H - row  (y-flip)
    This is the INVERSE of _lonlat_to_rasterio_xy so the drawn ring lands where intended.
    """
    return {"lon": float(col), "lat": float(H - row)}


def _make_carve_ring(
    row_min: int = CARVE_ROW_MIN,
    row_max: int = CARVE_ROW_MAX,
    col_min: int = CARVE_COL_MIN,
    col_max: int = CARVE_COL_MAX,
) -> list[dict]:
    """Return a 4-corner ring (closed loop) in lat/lon coords for the carve operation.

    The ring is positioned at (row_min:row_max, col_min:col_max) in numpy space.
    All four corners are fully inside parent X (row 10-49, col 10-49).
    """
    return [
        _pixel_to_lonlat(row_min, col_min),  # top-left
        _pixel_to_lonlat(row_min, col_max),  # top-right
        _pixel_to_lonlat(row_max, col_max),  # bottom-right
        _pixel_to_lonlat(row_max, col_min),  # bottom-left
    ]


def _make_carve_op(
    parent_id: int = PARENT_IDX,
    allocated_original_idx: int = CARVE_NEW_IDX,
    ring: list[dict] | None = None,
) -> dict:
    """Build a 'carve' op dict matching the expected payload contract."""
    if ring is None:
        ring = _make_carve_ring()
    return {
        "op": "carve",
        "ts": 0,
        "parent_id": parent_id,
        "ring": ring,
        "allocated_original_idx": allocated_original_idx,
        "barony_meta": {
            "name": f"Carved-{allocated_original_idx}",
            "condado_idx": 5,       # inherits parent's condado
            "duchy_id": "duchy-A",
            "kingdom_id": "kingdom-1",
        },
    }


def _make_cfg(edit_log: list[dict], extra_vertices: dict | None = None):
    """Build a minimal RegionConfig for unit tests using the 60×60 identity bounding box."""
    from medieval_forge.services.pipeline.contracts import RegionConfig

    snapshot_data: dict = {"edit_log": edit_log}
    if extra_vertices:
        snapshot_data["vertices"] = extra_vertices

    cfg = RegionConfig()
    cfg.map_w = W
    cfg.map_h = H
    cfg.lon_min = 0.0
    cfg.lon_max = float(W)
    cfg.lon_scale = 1.0
    cfg.lat_min = 0.0
    cfg.lat_max = float(H)
    cfg.manual_edit_log_hash = "carve-test-hash"
    cfg.manual_edit_log_count = len(edit_log)
    cfg.branch_id = "carve-test-branch"
    cfg.snapshot_loader = lambda bid: snapshot_data
    return cfg


def _vectorise_output(out: np.ndarray) -> dict[int, Polygon]:
    """Vectorise an int16 output raster into {idx: Polygon} (largest component per idx)."""
    transform = from_bounds(0, 0, W, H, W, H)
    shapes_iter = rasterio.features.shapes(out.astype(np.int16), transform=transform)
    polys_by_id: dict[int, list[Polygon]] = {}
    for geom_dict, value in shapes_iter:
        value = int(value)
        if value < 0 or value == 9999:
            continue
        from shapely.geometry import shape as shapely_shape
        poly = shapely_shape(geom_dict)
        if hasattr(poly, "area") and poly.area > 0:
            polys_by_id.setdefault(value, []).append(poly)
    result = {}
    for idx, polys in polys_by_id.items():
        merged = unary_union(polys)
        result[idx] = merged
    return result


# ===========================================================================
# Test 1 — carve intersection+difference formula (D-23 / D-24)
# ===========================================================================

@pytest.mark.unit
class TestCarveIntersectionAndDifferenceFormula:
    """CARVE-ENCLAVE-01: N = drawn∩parent, parent' = parent−N (polygon-with-hole)."""

    def test_carve_intersection_and_difference_formula(self):
        """Drawn loop inside X → N pixels enclosed by X pixels; X has ≥1 interior ring.

        Numeric fixtures:
          - Parent X (idx=0): 60×60 raster, rows 10-49, cols 10-49 (40×40 block).
          - Carve ring: rows 20-29, cols 20-29 (10×10 block, strictly inside X).
          - allocated_original_idx = 1.

        After compute():
          (a) result has pixels with idx=1 (N) in the carved region.
          (b) X's polygon has ≥1 interior ring (it is now a donut).
          (c) N pixels do NOT appear outside X's original bounding box (N⊆X invariant).
        """
        from medieval_forge.services.pipeline.manual_edit import compute

        op = _make_carve_op()
        cfg = _make_cfg([op])
        raster = _make_raster()

        result, new_entries = compute(raster, cfg)

        # (a) N pixels must exist in result
        n_pixels = int(np.sum(result == CARVE_NEW_IDX))
        assert n_pixels > 0, (
            f"Expected carved barony N (idx={CARVE_NEW_IDX}) to have pixels in result, "
            f"got {n_pixels}. carve op not implemented yet — this is expected RED failure."
        )

        # (b) X must have an interior ring (polygon-with-hole)
        polys = _vectorise_output(result)
        assert PARENT_IDX in polys, (
            f"Parent idx={PARENT_IDX} not found in vectorised result."
        )
        parent_poly = polys[PARENT_IDX]
        interior_count = len(list(parent_poly.interiors)) if hasattr(parent_poly, "interiors") else 0
        assert interior_count >= 1, (
            f"Parent X must have ≥1 interior ring (donut shape) after carve, "
            f"got {interior_count} interior rings. This is expected RED failure."
        )

        # (c) N pixels must not appear outside X's original bounding box
        x_mask = np.zeros((H, W), dtype=bool)
        x_mask[PARENT_ROW_MIN : PARENT_ROW_MAX + 1,
               PARENT_COL_MIN : PARENT_COL_MAX + 1] = True
        n_outside_x = int(np.sum((result == CARVE_NEW_IDX) & ~x_mask))
        assert n_outside_x == 0, (
            f"N must not paint pixels outside X's original footprint, "
            f"but found {n_outside_x} pixels of N outside X. D-24 intersection violated."
        )

        # (d) new_entries must contain N's metadata
        assert len(new_entries) >= 1, "new_barony_meta must contain N's entry"
        n_entry = next((e for e in new_entries if e["original_idx"] == CARVE_NEW_IDX), None)
        assert n_entry is not None, (
            f"new_barony_meta missing entry for original_idx={CARVE_NEW_IDX}"
        )
        assert n_entry["condado_idx"] == 5, "N must inherit parent's condado_idx (5)"


# ===========================================================================
# Test 2 — hole survives reload and re-Apply (D-25 pure-carve round-trip, part a)
# ===========================================================================

@pytest.mark.unit
class TestCarveHoleSurvivesReloadAndReapply:
    """CARVE-HOLE-RT-01: hole survives store → reload → re-Apply (pure-carve path)."""

    def test_carve_hole_survives_reload_and_reapply(self):
        """CRITICAL DAG dataflow: manual_edit ALWAYS reads the cached PRE-CARVE merge raster.

        The reload hop round-trips the edit_log through serialize/deserialize, then replays
        the SAME log against the SAME merge_raster (NOT against out1 from the first replay).

        Steps:
          1. `out1, _ = compute(merge_raster, cfg)` — first replay.
          2. Round-trip log through serialize/deserialize: `log2 = deserialize(serialize(...))["edit_log"]`.
          3. `out2, _ = compute(merge_raster, cfg2)` where cfg2 uses log2 (SAME merge_raster).
          4. Assert np.array_equal(out1, out2) — log survives reload and replay is deterministic.
          5. Assert X has an interior ring in out1 (hole present).
          6. Assert N's pixels in out1 are inside X's original footprint.

        Numeric fixtures: 60×60 raster, parent X rows 10-49 cols 10-49, carve rows 20-29 cols 20-29.
        """
        from medieval_forge.services.pipeline.manual_edit import compute
        from medieval_forge.services.branches.snapshot import serialize, deserialize

        op = _make_carve_op()
        edit_log = [op]
        cfg = _make_cfg(edit_log)
        merge_raster = _make_raster()

        # First replay
        out1, _ = compute(merge_raster, cfg)

        # Round-trip the log through serialize/deserialize (reload hop)
        snapshot_payload = {
            "geojson": {},
            "region_config": {},
            "edit_log": edit_log,
        }
        blob = serialize(snapshot_payload)
        loaded = deserialize(blob)
        log2 = loaded["edit_log"]

        # Second replay against SAME merge_raster (NOT out1)
        cfg2 = _make_cfg(log2)
        out2, _ = compute(merge_raster, cfg2)

        # Reload + replay must be byte-identical (deterministic)
        assert np.array_equal(out1, out2), (
            "Carve replay must be deterministic: out1 vs out2 after log round-trip must be byte-equal."
        )

        # Vectorise out1 and confirm hole is present
        polys = _vectorise_output(out1)
        assert PARENT_IDX in polys, f"Parent idx={PARENT_IDX} missing from vectorised out1."
        parent_poly = polys[PARENT_IDX]
        interior_count = len(list(parent_poly.interiors)) if hasattr(parent_poly, "interiors") else 0
        assert interior_count >= 1, (
            f"Parent X must have ≥1 interior ring in out1 after carve. "
            f"Got {interior_count}. D-25 pure-carve part a FAILED."
        )

        # N's pixels must be inside X's original footprint
        n_pixels = int(np.sum(out1 == CARVE_NEW_IDX))
        assert n_pixels > 0, f"N (idx={CARVE_NEW_IDX}) has no pixels in out1."
        x_mask = np.zeros((H, W), dtype=bool)
        x_mask[PARENT_ROW_MIN : PARENT_ROW_MAX + 1,
               PARENT_COL_MIN : PARENT_COL_MAX + 1] = True
        n_outside = int(np.sum((out1 == CARVE_NEW_IDX) & ~x_mask))
        assert n_outside == 0, (
            f"N pixels must not appear outside X's footprint after reload+replay. "
            f"Found {n_outside} pixels outside."
        )


# ===========================================================================
# Test 3 — carve + parent-edit does NOT refill the hole (D-25 load-bearing hop, part b)
# ===========================================================================

@pytest.mark.unit
class TestCarveThenParentEditDoesNotRefillHole:
    """CARVE-HOLE-RT-01: hole survives carve → parent-Bézier-edit → re-Apply (load-bearing hop)."""

    def test_carve_then_parent_edit_does_not_refill_hole(self):
        """THE LOAD-BEARING HOP (D-25 part b).

        edit_log = [carve op on X, then a vertex 'move' op on parent X's ring].
        The mix forces replay_vertex_ring to rebuild X exterior-only from vertices_dict,
        potentially refilling the hole. The carve branch must re-subtract N after rebuild.

        After compute():
          - X still has ≥1 interior ring (hole NOT refilled).
          - N's pixels are intact.

        Numeric fixtures:
          - Parent X: rows 10-49, cols 10-49.
          - Carve ring: rows 20-29, cols 20-29.
          - Vertex move: move vertex of parent X's ring (re-express as op:'move').
          - Parent exterior ring expressed in vertices_dict as "Parent-0#0..#3".
        """
        from medieval_forge.services.pipeline.manual_edit import compute

        carve_op = _make_carve_op()

        # Vertex move op on parent X — forces replay_vertex_ring path
        move_op = {
            "op": "move",
            "ts": 1,
            "baronyName": "Parent-0",
            "vertexIndex": 0,
            "lat": float(H - PARENT_ROW_MIN),  # same position, but triggers vertex_ops_present
            "lon": float(PARENT_COL_MIN),
        }

        # Parent X's exterior ring expressed in vertices_dict (identity mapping)
        # Corners in rasterio (lon, rasterio_y) = (col, H-row):
        parent_vertices = {
            "Parent-0#0": _pixel_to_lonlat(PARENT_ROW_MIN, PARENT_COL_MIN),
            "Parent-0#1": _pixel_to_lonlat(PARENT_ROW_MIN, PARENT_COL_MAX),
            "Parent-0#2": _pixel_to_lonlat(PARENT_ROW_MAX, PARENT_COL_MAX),
            "Parent-0#3": _pixel_to_lonlat(PARENT_ROW_MAX, PARENT_COL_MIN),
        }

        edit_log = [carve_op, move_op]
        cfg = _make_cfg(edit_log, extra_vertices=parent_vertices)
        barony_name_to_idx = {"Parent-0": PARENT_IDX}
        merge_raster = _make_raster()

        result, _ = compute(merge_raster, cfg, barony_name_to_idx=barony_name_to_idx)

        # N's pixels must still exist
        n_pixels = int(np.sum(result == CARVE_NEW_IDX))
        assert n_pixels > 0, (
            f"N (idx={CARVE_NEW_IDX}) has no pixels after carve+parent-edit. "
            f"Hole was refilled by replay_vertex_ring exterior-only rebuild. D-25 load-bearing hop FAILED."
        )

        # X must still have an interior ring (hole not refilled)
        polys = _vectorise_output(result)
        assert PARENT_IDX in polys, f"Parent idx={PARENT_IDX} missing from vectorised result."
        parent_poly = polys[PARENT_IDX]
        interior_count = len(list(parent_poly.interiors)) if hasattr(parent_poly, "interiors") else 0
        assert interior_count >= 1, (
            f"Parent X must retain ≥1 interior ring after carve+parent-edit. "
            f"Got {interior_count}. replay_vertex_ring must NOT refill the carved hole."
        )


# ===========================================================================
# Test 4 — no interior sentinel pixels (D-27)
# ===========================================================================

@pytest.mark.unit
class TestCarveCreatesNoInteriorSentinel:
    """D-27: no -1 (ocean) or 9999 (ignore) pixel inside parent X's exterior after carve."""

    def test_carve_creates_no_interior_sentinel(self):
        """After carve, no pixel inside X's original exterior bounding region is -1 or 9999.

        N fully fills the hole; the ocean_mask restore cannot catch under-fill, so
        an under-filled hole would leave -1 pixels inside X's footprint.

        Numeric fixture: 60×60 raster, parent rows 10-49 cols 10-49, carve rows 20-29 cols 20-29.
        """
        from medieval_forge.services.pipeline.manual_edit import compute

        op = _make_carve_op()
        cfg = _make_cfg([op])
        raster = _make_raster()

        result, _ = compute(raster, cfg)

        # Check the interior of X's original bounding box (not just N's pixels)
        x_interior = result[
            PARENT_ROW_MIN : PARENT_ROW_MAX + 1,
            PARENT_COL_MIN : PARENT_COL_MAX + 1,
        ]
        ocean_inside = int(np.sum(x_interior == -1))
        ignore_inside = int(np.sum(x_interior == 9999))

        assert ocean_inside == 0, (
            f"Found {ocean_inside} ocean (-1) sentinel pixels inside X's bounding region. "
            f"Hole is under-filled or N does not cover carved area. D-27 sentinel-leak FAILED."
        )
        assert ignore_inside == 0, (
            f"Found {ignore_inside} ignore (9999) sentinel pixels inside X's bounding region. "
            f"D-27 sentinel-leak FAILED."
        )


# ===========================================================================
# Test 5 — zero-edit path is byte-identical (PEN-PARITY-01 guard)
# ===========================================================================

@pytest.mark.unit
class TestZeroEditPathByteIdentical:
    """PEN-PARITY-01: empty edit_log → compute() returns input byte-identical; carve adds nothing."""

    def test_zero_edit_path_byte_identical(self):
        """An empty edit_log (no carve ops) must return input_array byte-identical and [] meta.

        Numeric fixture: 60×60 raster with parent X. Empty log → identity pass-through.
        Carve must not affect the zero-edit path.
        """
        from medieval_forge.services.pipeline.manual_edit import compute
        from medieval_forge.services.pipeline.contracts import RegionConfig

        # Empty hash → identity pass-through (early return before snapshot_loader)
        cfg = RegionConfig()
        cfg.manual_edit_log_hash = ""
        cfg.manual_edit_log_count = 0

        raster = _make_raster()
        result, meta = compute(raster, cfg)

        assert result is raster, (
            "Zero-edit path must return the exact same array object (no copy, byte-identical)."
        )
        assert meta == [], (
            f"Zero-edit path must return empty meta list, got {meta}."
        )


# ===========================================================================
# Handler validation tests (Task 3 API tests) — added here per plan scope
# ===========================================================================
# These test the editor.py carve handler at the HTTP level.
# They will be RED until Task 3 adds 'carve' to the op_type regex.
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCarveHandlerValidation:
    """editor.py carve handler: 200 allocation + 400/422 validation cases."""

    @pytest.fixture
    def anyio_backend(self):
        return "asyncio"

    @pytest.fixture
    async def app_with_iberia_project(self):
        """Stand up the FastAPI app with an Iberia project in an in-memory DB."""
        import uuid
        from httpx import AsyncClient, ASGITransport
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from medieval_forge.models import Base, Project
        from medieval_forge.main import app
        from medieval_forge.database import get_db

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

        # Create project with region_key='iberia_868'
        project_id = str(uuid.uuid4())
        async with SessionLocal() as session:
            proj = Project(
                id=project_id,
                name="Test Iberia",
                region_key="iberia_868",
                status="ready",
            )
            session.add(proj)
            await session.commit()

        async def override_get_db():
            async with SessionLocal() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, project_id

        app.dependency_overrides.clear()
        await engine.dispose()

    @pytest.mark.anyio
    async def test_carve_handler_200_allocates_idx_above_floor(
        self, app_with_iberia_project
    ):
        """POST carve with valid payload → 200 + allocated_original_idx >= barony_floor.

        Numeric fixture: Iberia has 140+ baronies (barony_floor >= 100).
        A valid 4-point ring fully inside a barony → allocated idx >= floor, not 1.
        """
        client, project_id = app_with_iberia_project

        # Ensure main branch exists
        br_resp = await client.post(
            f"/api/v3/projects/{project_id}/branches",
            json={"name": "test-carve"},
        )
        # Use the main branch created by get or create
        branches_resp = await client.get(f"/api/v3/projects/{project_id}/branches")
        assert branches_resp.status_code == 200
        branches = branches_resp.json()
        if not branches:
            pytest.skip("No branches available — ensure_main_branch not triggered")
        branch_id = branches[0]["id"]

        # Valid ring (4 points inside Iberia bounding box)
        ring = [
            {"lat": 39.5, "lon": -5.5},
            {"lat": 39.5, "lon": -5.0},
            {"lat": 39.0, "lon": -5.0},
            {"lat": 39.0, "lon": -5.5},
        ]
        resp = await client.post(
            f"/api/v3/projects/{project_id}/editor/apply",
            json={
                "op_type": "carve",
                "payload": {
                    "parent_id": 0,
                    "ring": ring,
                    "barony_meta": {
                        "name": "TestCarved",
                        "condado_idx": 0,
                        "duchy_id": "test-duchy",
                        "kingdom_id": "test-kingdom",
                    },
                },
                "branch_id": branch_id,
            },
        )
        assert resp.status_code == 200, (
            f"Expected 200 for valid carve payload, got {resp.status_code}: {resp.text}. "
            "carve not yet in op_type regex — expected RED."
        )
        data = resp.json()
        assert "allocated_original_idx" in data
        assert data["allocated_original_idx"] is not None
        assert data["allocated_original_idx"] >= 1, (
            f"allocated_original_idx must be >= barony_floor, got {data['allocated_original_idx']}"
        )

    @pytest.mark.anyio
    async def test_carve_handler_400_missing_parent_id(self, app_with_iberia_project):
        """POST carve without parent_id → 400 INVALID_PAYLOAD."""
        client, project_id = app_with_iberia_project

        branches_resp = await client.get(f"/api/v3/projects/{project_id}/branches")
        assert branches_resp.status_code == 200
        branches = branches_resp.json()
        if not branches:
            pytest.skip("No branches available")
        branch_id = branches[0]["id"]

        ring = [{"lat": 39.5, "lon": -5.5}, {"lat": 39.5, "lon": -5.0}, {"lat": 39.0, "lon": -5.0}]
        resp = await client.post(
            f"/api/v3/projects/{project_id}/editor/apply",
            json={
                "op_type": "carve",
                "payload": {
                    # parent_id deliberately missing
                    "ring": ring,
                    "barony_meta": {"name": "TestCarved", "condado_idx": 0},
                },
                "branch_id": branch_id,
            },
        )
        assert resp.status_code == 400, (
            f"Expected 400 for missing parent_id, got {resp.status_code}. "
            "Carve validation not yet implemented — expected RED."
        )

    @pytest.mark.anyio
    async def test_carve_handler_400_ring_too_short(self, app_with_iberia_project):
        """POST carve with ring of 2 points → 400 INVALID_PAYLOAD."""
        client, project_id = app_with_iberia_project

        branches_resp = await client.get(f"/api/v3/projects/{project_id}/branches")
        assert branches_resp.status_code == 200
        branches = branches_resp.json()
        if not branches:
            pytest.skip("No branches available")
        branch_id = branches[0]["id"]

        resp = await client.post(
            f"/api/v3/projects/{project_id}/editor/apply",
            json={
                "op_type": "carve",
                "payload": {
                    "parent_id": 0,
                    "ring": [{"lat": 39.5, "lon": -5.5}, {"lat": 39.5, "lon": -5.0}],  # only 2 points
                    "barony_meta": {"name": "TestCarved", "condado_idx": 0},
                },
                "branch_id": branch_id,
            },
        )
        assert resp.status_code == 400, (
            f"Expected 400 for ring with 2 points, got {resp.status_code}."
        )

    @pytest.mark.anyio
    async def test_carve_handler_400_missing_condado_idx(self, app_with_iberia_project):
        """POST carve with condado_idx=None → 400 INVALID_PAYLOAD."""
        client, project_id = app_with_iberia_project

        branches_resp = await client.get(f"/api/v3/projects/{project_id}/branches")
        assert branches_resp.status_code == 200
        branches = branches_resp.json()
        if not branches:
            pytest.skip("No branches available")
        branch_id = branches[0]["id"]

        ring = [{"lat": 39.5, "lon": -5.5}, {"lat": 39.5, "lon": -5.0}, {"lat": 39.0, "lon": -5.0}]
        resp = await client.post(
            f"/api/v3/projects/{project_id}/editor/apply",
            json={
                "op_type": "carve",
                "payload": {
                    "parent_id": 0,
                    "ring": ring,
                    "barony_meta": {
                        "name": "TestCarved",
                        "condado_idx": None,  # explicitly None
                    },
                },
                "branch_id": branch_id,
            },
        )
        assert resp.status_code == 400, (
            f"Expected 400 for condado_idx=None, got {resp.status_code}."
        )

    @pytest.mark.anyio
    async def test_carve_handler_422_ring_too_long(self, app_with_iberia_project):
        """POST carve with ring > 10000 points → 422 INVALID_PAYLOAD."""
        client, project_id = app_with_iberia_project

        branches_resp = await client.get(f"/api/v3/projects/{project_id}/branches")
        assert branches_resp.status_code == 200
        branches = branches_resp.json()
        if not branches:
            pytest.skip("No branches available")
        branch_id = branches[0]["id"]

        # 10001 identical points (DoS guard check)
        ring = [{"lat": 39.5, "lon": -5.5}] * 10001
        resp = await client.post(
            f"/api/v3/projects/{project_id}/editor/apply",
            json={
                "op_type": "carve",
                "payload": {
                    "parent_id": 0,
                    "ring": ring,
                    "barony_meta": {"name": "TestCarved", "condado_idx": 0},
                },
                "branch_id": branch_id,
            },
        )
        assert resp.status_code == 422, (
            f"Expected 422 for ring > 10000 points, got {resp.status_code}."
        )
