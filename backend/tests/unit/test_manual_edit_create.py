"""Phase 08.3 Plan 01 — TDD RED tests for CREATE convergence + allocator seeding + EXTEND regression.

Covers REQ-IDs: PEN-CREATE-01, PEN-CONV-01, PEN-ASSIGN-01, PEN-EXTEND-01, PEN-PARITY-01

Tests call signatures that do NOT yet exist:
  - allocate_next_original_idx(db, branch_id, min_floor=nb)   ← Task 2(A) will add min_floor
  - result, new_barony_entries = compute(...)                  ← Task 2(B) will change return type

All fixtures are explicit numeric (user feedback memory — descriptive names + explicit numeric fixtures).
"""
from __future__ import annotations

import numpy as np
import pytest
import pytest_asyncio
from shapely.geometry import Polygon

# ---------------------------------------------------------------------------
# Shared fixture: 40×40 int16 raster with 3 known baronies (nb=3)
# Layout:
#   idx 0  → rows 10-19, cols 10-19  (10×10 = 100 pixels)
#   idx 1  → rows 10-19, cols 20-29  (10×10 = 100 pixels)
#   idx 2  → rows 20-29, cols 10-29  (10×20 = 200 pixels)
#   ocean (-1) everywhere else
# nb = 3
# ---------------------------------------------------------------------------

W, H = 40, 40


def _make_raster() -> np.ndarray:
    """Return a fresh 40×40 int16 raster with 3 pre-seeded baronies."""
    raster = np.full((H, W), -1, dtype=np.int16)
    raster[10:20, 10:20] = 0  # barony 0
    raster[10:20, 20:30] = 1  # barony 1
    raster[20:30, 10:30] = 2  # barony 2
    return raster


def _make_bars():
    """Return a list of 3 barony metadata dicts."""
    return [
        {"name": "Barony-0", "condado_idx": 0, "duchy_id": "duchy-A", "kingdom_id": "kingdom-1"},
        {"name": "Barony-1", "condado_idx": 0, "duchy_id": "duchy-A", "kingdom_id": "kingdom-1"},
        {"name": "Barony-2", "condado_idx": 1, "duchy_id": "duchy-B", "kingdom_id": "kingdom-1"},
    ]


NB = 3  # number of baronies in the raster


def _make_bc():
    return np.array([0, 0, 1], dtype=np.int32)


def _make_bd():
    return np.array([0, 0, 1], dtype=np.int32)


def _make_bk():
    return np.array([0, 0, 0], dtype=np.int32)


# ---------------------------------------------------------------------------
# CREATE op payload factory — the contract shape defined by RESEARCH Target 6
# ---------------------------------------------------------------------------

def _create_op(
    *,
    allocated_original_idx: int = 3,
    row_min: int = 5,
    row_max: int = 9,
    col_min: int = 5,
    col_max: int = 9,
) -> dict:
    """Create a 'create' op with a square ring in rasterio pixel coords.

    The ring is expressed as lat/lon but with identity mapping:
    lon = col, lat = H - row  (so _lonlat_to_rasterio_xy round-trips correctly
    on a unit [0,W]×[0,H] raster built with from_bounds(0,0,W,H,W,H)).
    """
    # In the rasterio coordinate system used by manual_edit:
    # x = lon (col), rasterio_y = H - row
    # With span=W (lon_scale=1, lon_min=0, lon_max=W):
    #   _lonlat_to_rasterio_xy(lon=col, lat=..., cfg, W, H)
    #     x = round((col - 0) * 1 / W * W) = round(col) = col
    #     py_row = round((1 - (lat - 0) / H) * H) = round(H - lat) = H - lat
    #     rasterio_y = H - py_row = lat
    # So: lon=col, lat = rasterio_y (row from bottom)
    # For a pixel at (row_min:row_max in numpy top-down):
    #   rasterio_y_of_numpy_row = H - numpy_row  (y-flip)
    # We want corners of a rectangle in rasterio (x, rasterio_y):
    #   (col_min, H-row_min), (col_max, H-row_min), (col_max, H-row_max), (col_min, H-row_max)
    # In our lat/lon encoding: lat = rasterio_y, lon = x
    corners = [
        {"lon": col_min, "lat": H - row_min},
        {"lon": col_max, "lat": H - row_min},
        {"lon": col_max, "lat": H - row_max},
        {"lon": col_min, "lat": H - row_max},
    ]
    return {
        "op": "create",
        "ts": 0,
        "ring": corners,
        "allocated_original_idx": allocated_original_idx,
        "barony_meta": {
            "name": f"Baronato-{allocated_original_idx}",
            "condado_idx": 0,
            "duchy_id": "duchy-A",
            "kingdom_id": "kingdom-1",
            "country": "PT",
        },
    }


# ---------------------------------------------------------------------------
# Minimal RegionConfig stand-in and snapshot_loader
# ---------------------------------------------------------------------------

def _make_cfg(edit_log: list[dict], extra_vertices: dict | None = None):
    """Build a minimal RegionConfig-like object for unit tests.

    Uses the identity bounding box that makes _lonlat_to_rasterio_xy pass through:
      lon_min=0, lon_max=W, lon_scale=1 → span=W
      lat_min=0, lat_max=H
    """
    from medieval_forge.services.pipeline.contracts import RegionConfig

    snapshot_data = {"edit_log": edit_log}
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
    cfg.manual_edit_log_hash = "test-hash"
    cfg.manual_edit_log_count = len(edit_log)
    cfg.branch_id = "test-branch"
    cfg.snapshot_loader = lambda bid: snapshot_data
    return cfg


# ---------------------------------------------------------------------------
# Async DB fixture (mirrors test_models_branches.py pattern)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db():
    """In-memory SQLite session with all tables created."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from medieval_forge.models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


# ===========================================================================
# T1 — Allocator seeding: min_floor parameter on allocate_next_original_idx
# ===========================================================================

class TestAllocatorSeeding:
    """PEN-CREATE-01: allocate_next_original_idx must accept min_floor so CREATE
    avoids aliasing existing barony raster indices 0..nb-1."""

    @pytest.mark.asyncio
    async def test_allocator_seed_advances_to_nb_when_below(self, db):
        """When high_water=0 and min_floor=3, first allocation returns 4 — NOT 1.

        Existing barony idx 1 is NOT aliased.
        Numeric fixture: nb=3, high_water starts at 0 (DB default).
        """
        from medieval_forge.models import Branch
        from medieval_forge.services.branches.service import allocate_next_original_idx

        branch = Branch(project_id="p-seed-1", name="main", is_main=True)
        db.add(branch)
        await db.commit()
        await db.refresh(branch)

        # Before: high_water=0, min_floor=3 → high_water becomes 3, then +1 = 4
        # Because: if high_water < min_floor: set to min_floor; then +=1
        # Wait — the plan says min_floor=nb and we want idx=nb.
        # Fix: if high_water < min_floor: set to min_floor - 1; then +=1 = min_floor
        # Actually the plan says:
        #   if branch.original_idx_high_water < min_floor:
        #       branch.original_idx_high_water = min_floor
        #   branch.original_idx_high_water += 1
        # So: 0 < 3 → set to 3 → +1 = 4? No: set to min_floor=3, then +=1 gives 4.
        # But plan says "first allocation returns 3 (not 1)".
        # Actually re-reading Task 2(A): "set to min_floor; then += 1; new_idx = high_water"
        # So first call → high_water set to min_floor=3, then +=1, new_idx=4? That's nb+1.
        # But plan objective says "allocated idx = nb (not 1)". Let me check RESEARCH:
        # "if branch.original_idx_high_water < nb: branch.original_idx_high_water = nb"
        # then "+= 1" → new_idx = nb+1??? That conflicts with "returns idx=nb".
        # Resolution from RESEARCH p.229-230: after "set to nb", "+= 1" → new_idx = nb+1.
        # But then the comment "first allocation returns 3 (not 1) on first call" for nb=3
        # means new_idx=4? That still aliases if nb grew to 4 after this op.
        # Actually: the intent is first allocation returns >= nb (safely outside 0..nb-1).
        # For nb=3, first call should return 3 (= old_nb) OR 4. Both are safe.
        # Plan task 2(A) says "+= 1 after setting to min_floor" → first alloc = min_floor + 1.
        # But test_behavior says "returns 3 (not 1)". Contradiction → test what the plan specifies:
        # "if branch.original_idx_high_water < min_floor: branch.original_idx_high_water = min_floor"
        # "branch.original_idx_high_water += 1; new_idx = branch.original_idx_high_water"
        # For min_floor=3, high_water=0: 0<3 → hw=3; hw+=1; hw=4; new_idx=4
        # For min_floor=3, high_water=0: result = 4. SAFELY OUTSIDE 0..2.
        # The plan test name says "returns 3" but the algorithm gives 4.
        # Following the plan algorithm (which is the source of truth for production code):
        new_idx = await allocate_next_original_idx(db, branch.id, min_floor=3)

        # new_idx must be safely outside existing barony indices 0..2
        assert new_idx >= 3, (
            f"Expected new_idx >= 3 (safely outside barony range 0..2), got {new_idx}"
        )
        # Existing barony idx 1 must NOT be returned
        assert new_idx != 1, "Allocator must not return idx=1 (aliases existing barony)"

    @pytest.mark.asyncio
    async def test_allocator_seed_noop_when_already_above(self, db):
        """When high_water=5 and min_floor=3, allocation returns 6 (no floor applied).

        Numeric fixture: high_water=5, min_floor=3 → 5 >= 3, no seed → +=1 → 6.
        """
        from medieval_forge.models import Branch
        from medieval_forge.services.branches.service import allocate_next_original_idx

        branch = Branch(project_id="p-seed-2", name="main", is_main=True,
                        original_idx_high_water=5)
        db.add(branch)
        await db.commit()
        await db.refresh(branch)

        new_idx = await allocate_next_original_idx(db, branch.id, min_floor=3)
        assert new_idx == 6, (
            f"Expected new_idx=6 (high_water was 5, min_floor=3 noop, +1=6), got {new_idx}"
        )

    @pytest.mark.asyncio
    async def test_split_path_also_seeded(self, db):
        """Simulate split allocation with min_floor=nb → child idx safely outside 0..nb-1.

        Regression: split was allocating idx=1 (aliases existing barony 1).
        Numeric fixture: nb=3, high_water=0 → first alloc with min_floor=3 returns >= 3.
        """
        from medieval_forge.models import Branch
        from medieval_forge.services.branches.service import allocate_next_original_idx

        branch = Branch(project_id="p-split-seed", name="main", is_main=True)
        db.add(branch)
        await db.commit()
        await db.refresh(branch)

        # Simulate split handler calling allocate with min_floor=nb=3
        child_idx = await allocate_next_original_idx(db, branch.id, min_floor=3)

        # Must NOT be 1 (the old broken behavior)
        assert child_idx != 1, "Split allocator bug: returned idx=1, aliases existing barony"
        # Must be safely outside 0..nb-1
        assert child_idx >= 3, (
            f"Split child idx={child_idx} aliases existing barony range 0..2"
        )


# ===========================================================================
# T2 — compute() returns tuple
# ===========================================================================

class TestComputeReturnsTuple:
    """PEN-CONV-01: compute() must return (ndarray, list) not bare ndarray."""

    def test_compute_returns_tuple_on_empty_log_hash(self):
        """compute() with empty log_hash returns (ndarray, []) — early return path 1.

        Numeric fixture: 40×40 raster with 3 baronies. Empty manual_edit_log_hash.
        """
        from medieval_forge.services.pipeline.manual_edit import compute
        from medieval_forge.services.pipeline.contracts import RegionConfig

        cfg = RegionConfig()
        cfg.manual_edit_log_hash = ""
        cfg.manual_edit_log_count = 0
        raster = _make_raster()

        result, new_barony_entries = compute(raster, cfg)  # must unpack
        assert isinstance(result, np.ndarray), "First element must be ndarray"
        assert isinstance(new_barony_entries, list), "Second element must be list"
        assert len(new_barony_entries) == 0

    def test_compute_returns_tuple_on_empty_edit_log(self):
        """compute() with non-empty hash but empty edit_log returns (ndarray, []).

        Early return path 2 (empty-log identity).
        Numeric fixture: 40×40 raster, hash set, snapshot has no ops.
        """
        from medieval_forge.services.pipeline.manual_edit import compute

        cfg = _make_cfg(edit_log=[])
        raster = _make_raster()

        result, new_barony_entries = compute(raster, cfg)
        assert isinstance(result, np.ndarray)
        assert isinstance(new_barony_entries, list)
        assert len(new_barony_entries) == 0


# ===========================================================================
# T3 — CREATE op: overpaint, no collision, hierarchy coverage
# ===========================================================================

class TestCreateOverpaint:
    """PEN-CREATE-01 + PEN-CONV-01: create op overpaints raster at allocated idx."""

    def test_create_overpaint_into_raster(self):
        """A 'create' op at idx=3 overpaints the merged raster; existing barony 1 unchanged.

        Numeric fixture: 40×40 raster (nb=3). Ring occupies rows 5-9, cols 5-9.
        """
        from medieval_forge.services.pipeline.manual_edit import compute

        op = _create_op(allocated_original_idx=3, row_min=5, row_max=9, col_min=5, col_max=9)
        cfg = _make_cfg(edit_log=[op])
        raster = _make_raster()

        result, new_barony_entries = compute(raster, cfg)

        # The CREATE ring covers rows 5..8, cols 5..8 in the numpy top-down raster.
        # At least some pixels in that region must now be idx=3.
        create_pixels = np.sum(result == 3)
        assert create_pixels > 0, (
            f"Expected create op to paint pixels at idx=3, got {create_pixels} pixels"
        )

        # Existing barony 1 (rows 10-19, cols 20-29) must be unchanged
        barony1_pixels_original = 100  # 10×10
        barony1_pixels_now = int(np.sum(result == 1))
        assert barony1_pixels_now == barony1_pixels_original, (
            f"Barony 1 should still have 100 pixels, got {barony1_pixels_now} — collision!"
        )

    def test_create_new_barony_entries_contains_metadata(self):
        """compute() with create op returns new_barony_entries with the barony metadata.

        Numeric fixture: ring at rows 5-9, cols 5-9 → new_barony_entries[0] has original_idx=3.
        """
        from medieval_forge.services.pipeline.manual_edit import compute

        op = _create_op(allocated_original_idx=3, row_min=5, row_max=9, col_min=5, col_max=9)
        cfg = _make_cfg(edit_log=[op])
        raster = _make_raster()

        result, new_barony_entries = compute(raster, cfg)

        assert len(new_barony_entries) == 1
        entry = new_barony_entries[0]
        assert entry["original_idx"] == 3
        assert entry["name"] == "Baronato-3"
        assert entry["condado_idx"] == 0


class TestCreateHierarchyCoverage:
    """PEN-CONV-01: after bars extension, build_hierarchy_maps covers CREATE idx."""

    def test_create_hierarchy_coverage(self):
        """After orchestrator extends bars/bc/bd/bk/nb, pc[CREATE pixels] != -1.

        Numeric fixture: 40×40 raster, create op at idx=3. After bars extension
        nb=4, build_hierarchy_maps loops range(4) and assigns condado for idx=3.
        """
        from medieval_forge.services.pipeline.manual_edit import compute
        from medieval_forge.services.pipeline.voronoi import build_hierarchy_maps

        op = _create_op(allocated_original_idx=3, row_min=5, row_max=9, col_min=5, col_max=9)
        cfg = _make_cfg(edit_log=[op])
        raster = _make_raster()

        result, new_barony_entries = compute(raster, cfg)

        # Simulate orchestrator bars extension
        bars = _make_bars()
        bc = _make_bc()
        bd = _make_bd()
        bk = _make_bk()

        for entry in sorted(new_barony_entries, key=lambda e: e["original_idx"]):
            idx = entry["original_idx"]
            while len(bars) < idx:
                bars.append({"name": "", "condado_idx": -1, "duchy_id": "", "kingdom_id": ""})
                bc = np.append(bc, -1)
                bd = np.append(bd, 0)
                bk = np.append(bk, 0)
            assert len(bars) == idx, f"Alignment broken: len(bars)={len(bars)} idx={idx}"
            bars.append({
                "name": entry["name"],
                "condado_idx": entry["condado_idx"],
                "duchy_id": entry.get("duchy_id", ""),
                "kingdom_id": entry.get("kingdom_id", ""),
            })
            bc = np.append(bc, entry["condado_idx"])
            bd = np.append(bd, 0)
            bk = np.append(bk, 0)
        nb = len(bars)  # now 4

        pc, pd, pk = build_hierarchy_maps(result, bc, bd, bk, nb)

        # Pixels at CREATE ring location should have a real condado (not -1)
        create_pixels_mask = result == 3
        if np.any(create_pixels_mask):
            condado_at_create = pc[create_pixels_mask][0]
            assert condado_at_create != -1, (
                f"CREATE barony pixels got pc=-1 (hierarchy coverage gap). Got {condado_at_create}"
            )

    def test_create_appears_in_lookup(self):
        """After bars extension, generate_lookup_map assigns non-ocean RGB at idx=3.

        Numeric fixture: 40×40 raster. After extension nb=4, lookup covers idx=3.
        """
        from medieval_forge.services.pipeline.manual_edit import compute
        from medieval_forge.services.pipeline.lookup import generate_lookup_map

        op = _create_op(allocated_original_idx=3, row_min=5, row_max=9, col_min=5, col_max=9)
        cfg = _make_cfg(edit_log=[op])
        raster = _make_raster()

        result, new_barony_entries = compute(raster, cfg)

        # Extend bars/bc/bd/bk
        bars = _make_bars()
        bc = _make_bc()
        bd = _make_bd()
        bk = _make_bk()

        for entry in sorted(new_barony_entries, key=lambda e: e["original_idx"]):
            idx = entry["original_idx"]
            while len(bars) < idx:
                bars.append({"name": "", "condado_idx": -1, "duchy_id": "", "kingdom_id": ""})
                bc = np.append(bc, -1)
                bd = np.append(bd, 0)
                bk = np.append(bk, 0)
            bars.append({
                "name": entry["name"],
                "condado_idx": entry["condado_idx"],
                "duchy_id": entry.get("duchy_id", ""),
                "kingdom_id": entry.get("kingdom_id", ""),
            })
            bc = np.append(bc, entry["condado_idx"])
            bd = np.append(bd, 0)
            bk = np.append(bk, 0)
        nb = len(bars)  # 4

        lk, cmap = generate_lookup_map(result, result, nb, cfg, "barony")

        # The CREATE barony (idx=3) must appear in the color map
        # cmap maps "R,G,B" → idx string; check some pixel that is idx=3 in result
        create_pixels = np.argwhere(result == 3)
        assert len(create_pixels) > 0, "No CREATE pixels found in result"
        row, col = create_pixels[0]
        rgb = tuple(lk[row, col])
        rgb_key = f"{rgb[0]},{rgb[1]},{rgb[2]}"
        # Must not be ocean color (ocean is typically rendered as [0,0,0] or similar)
        assert rgb != (0, 0, 0), (
            f"CREATE barony got lookup RGB=(0,0,0) (ocean), expected a real color"
        )

    def test_create_appears_in_metadata(self):
        """After bars extension, export_metadata() contains the new barony entry.

        Numeric fixture: 40×40 raster. After extension nb=4, enumerate(bars)
        covers idx=3 → new barony appears in territory_metadata.json baronies list.
        """
        from medieval_forge.services.pipeline.manual_edit import compute
        from medieval_forge.services.pipeline.voronoi import build_hierarchy_maps
        from medieval_forge.services.pipeline.export import export_metadata
        from medieval_forge.services.pipeline.contracts import RegionConfig as _RC

        op = _create_op(allocated_original_idx=3, row_min=5, row_max=9, col_min=5, col_max=9)
        cfg = _make_cfg(edit_log=[op])
        raster = _make_raster()

        result, new_barony_entries = compute(raster, cfg)

        bars = _make_bars()
        bc = _make_bc()
        bd = _make_bd()
        bk = _make_bk()

        for entry in sorted(new_barony_entries, key=lambda e: e["original_idx"]):
            idx = entry["original_idx"]
            while len(bars) < idx:
                bars.append({"name": "", "condado_idx": -1, "duchy_id": "", "kingdom_id": ""})
                bc = np.append(bc, -1)
                bd = np.append(bd, 0)
                bk = np.append(bk, 0)
            bars.append({
                "name": entry["name"],
                "condado_idx": entry["condado_idx"],
                "duchy_id": entry.get("duchy_id", "duchy-A"),
                "kingdom_id": entry.get("kingdom_id", "kingdom-1"),
            })
            bc = np.append(bc, entry["condado_idx"])
            bd = np.append(bd, 0)
            bk = np.append(bk, 0)
        nb = len(bars)

        pc, pd, pk = build_hierarchy_maps(result, bc, bd, bk, nb)

        # Build minimal condados/duchies/kingdoms for export_metadata
        condados = [
            ("c0", "Condado-0", 0.0, 0.0, "duchy-A", [("Barony-0", 5.0, 5.0)]),
            ("c1", "Condado-1", 0.0, 0.0, "duchy-B", [("Barony-2", 15.0, 15.0)]),
        ]
        duchies = {"duchy-A": ("kingdom-1", "Duchy-A"), "duchy-B": ("kingdom-1", "Duchy-B")}
        kingdoms = {"kingdom-1": ["Kingdom-1"]}

        metadata = export_metadata(condados, duchies, kingdoms, bars, result, pc, cfg)

        # The new barony (Baronato-3) must appear in the baronies list
        barony_names = [b["name"] for b in metadata.get("baronies", [])]
        assert "Baronato-3" in barony_names, (
            f"New CREATE barony 'Baronato-3' not found in metadata baronies. "
            f"Got: {barony_names}"
        )


# ===========================================================================
# T4 — Clip single-poly guard (08.2-05 GUARD)
# ===========================================================================

class TestCreateClipSinglePoly:
    """PEN-CONV-01 + T-08.3-01-03: clip against neighbors → largest-component guard."""

    def test_create_clip_singlepoly(self):
        """A 'create' ring overlapping a neighbor → after clip, result has single Polygon pixels.

        Numeric fixture: ring at rows 8-28, cols 8-28 overlaps barony 1 (10-19, 20-29).
        The clip must not produce a MultiPolygon error — largest-component guard applies.
        """
        from medieval_forge.services.pipeline.manual_edit import compute

        # Large ring that covers the entire raster except ocean — will overlap all neighbors
        op = _create_op(allocated_original_idx=3, row_min=1, row_max=38, col_min=1, col_max=38)
        cfg = _make_cfg(edit_log=[op])
        raster = _make_raster()

        # Must not raise; MultiPolygon guard keeps the largest component
        result, new_barony_entries = compute(raster, cfg)

        # The CREATE ring was clipped — it may have shrunk but must not crash
        assert result.dtype == np.int16


# ===========================================================================
# T5 — Two sequential CREATE ops (Q3 / Assumption A4)
# ===========================================================================

class TestTwoCreatesSequentialIndices:
    """PEN-CONV-01 Q3: two CREATE ops with idx=3 and idx=4 processed sorted → bars[3], bars[4] align."""

    def test_two_creates_sequential_indices(self):
        """Two 'create' ops in one log → new_barony_entries sorted by original_idx;
        after extension: len(bars)=5, bars[3].name='Baronato-3', bars[4].name='Baronato-4'.

        Numeric fixture: 40×40 raster, nb=3.
        Op-A: idx=3, rows 0-4, cols 0-4  (top-left corner, no overlap with existing)
        Op-B: idx=4, rows 0-4, cols 31-35 (top-right corner, no overlap)
        """
        from medieval_forge.services.pipeline.manual_edit import compute

        op_a = _create_op(allocated_original_idx=3, row_min=0, row_max=4, col_min=0, col_max=4)
        op_b = _create_op(allocated_original_idx=4, row_min=0, row_max=4, col_min=31, col_max=35)
        op_b["barony_meta"]["name"] = "Baronato-4"

        cfg = _make_cfg(edit_log=[op_a, op_b])
        raster = _make_raster()

        result, new_barony_entries = compute(raster, cfg)

        # Entries must be sorted by original_idx
        assert len(new_barony_entries) == 2
        assert new_barony_entries[0]["original_idx"] == 3
        assert new_barony_entries[1]["original_idx"] == 4

        # Simulate orchestrator extension
        bars = _make_bars()
        bc = _make_bc()
        bd = _make_bd()
        bk = _make_bk()

        for entry in new_barony_entries:
            idx = entry["original_idx"]
            while len(bars) < idx:
                bars.append({"name": "", "condado_idx": -1, "duchy_id": "", "kingdom_id": ""})
                bc = np.append(bc, -1)
                bd = np.append(bd, 0)
                bk = np.append(bk, 0)
            assert len(bars) == idx, (
                f"Alignment broken: len(bars)={len(bars)} expected={idx}"
            )
            bars.append({
                "name": entry["name"],
                "condado_idx": entry["condado_idx"],
                "duchy_id": entry.get("duchy_id", ""),
                "kingdom_id": entry.get("kingdom_id", ""),
            })
            bc = np.append(bc, entry["condado_idx"])
            bd = np.append(bd, 0)
            bk = np.append(bk, 0)

        nb = len(bars)
        assert nb == 5, f"Expected nb=5 after two CREATEs, got {nb}"
        assert bars[3]["name"] == "Baronato-3"
        assert bars[4]["name"] == "Baronato-4"


# ===========================================================================
# T6 — EXTEND via existing replay_vertex_ring (no new backend op)
# ===========================================================================

class TestExtendViaVertexRing:
    """PEN-EXTEND-01: EXTEND expressed as op:move on existing barony ring.

    Existing replay_vertex_ring handles this with NO new op type.
    The barony stays in range(nb) (no hierarchy extension needed).
    """

    def test_extend_via_vertex_ring(self):
        """An EXTEND op expressed as standard move/add vertices on barony-1's ring
        replays through replay_vertex_ring with NO new op type.

        Numeric fixture: 40×40 raster, barony 1 at rows 10-19, cols 20-29.
        We modify its vertex ring (a 10×10 square shifted by 2px in each direction).
        After compute(), barony-1 stays in range(nb=3) — no new_barony_entries.
        """
        from medieval_forge.services.pipeline.manual_edit import compute

        # Barony-1 ring in rasterio pixel coords: (col_min, H-row_min) corners
        # Original: cols 20-29, rows 10-19 → rasterio corners:
        #   (20, H-10)=(20,30), (29, H-10)=(29,30), (29, H-19)=(29,21), (20, H-19)=(20,21)
        # Modified: extend right by 2px → col_max=31
        #   (20, 30), (31, 30), (31, 21), (20, 21)
        # In our lat=rasterio_y, lon=col encoding:
        modified_vertices = {}
        corners = [
            {"lon": 20, "lat": 30},
            {"lon": 31, "lat": 30},
            {"lon": 31, "lat": 21},
            {"lon": 20, "lat": 21},
        ]
        for i, corner in enumerate(corners):
            modified_vertices[f"Barony-1#{i}"] = corner

        # Use a move op to trigger vertex_ops_present=True
        move_op = {"op": "move", "ts": 0, "baronyName": "Barony-1",
                   "vertexIndex": 1, "lat": 30, "lon": 31}

        cfg = _make_cfg(edit_log=[move_op], extra_vertices=modified_vertices)
        barony_name_to_idx = {"Barony-0": 0, "Barony-1": 1, "Barony-2": 2}
        raster = _make_raster()

        result, new_barony_entries = compute(raster, cfg, barony_name_to_idx=barony_name_to_idx)

        # EXTEND leaves no new_barony_entries (barony-1 already in range(nb))
        assert new_barony_entries == [], (
            f"EXTEND via vertex ring must not produce new_barony_entries, got {new_barony_entries}"
        )

        # Barony-1 still exists in the result (extended, not removed)
        barony1_pixels = np.sum(result == 1)
        assert barony1_pixels > 0, "Barony-1 should still have pixels after EXTEND replay"

        # No new idx=3 was created
        new_idx_pixels = np.sum(result == 3)
        assert new_idx_pixels == 0, "EXTEND should not create new barony at idx=3"


# ===========================================================================
# T7 — Split: existing child allocation still works after signature change
# ===========================================================================

class TestSplitRegressionAfterSignatureChange:
    """Regression: split path must still work after compute() return type changes to tuple."""

    def test_split_compute_still_returns_tuple(self):
        """compute() with a split op returns (ndarray, ...) not bare ndarray.

        Numeric fixture: 40×40 raster. Split barony-2 with a vertical line.
        compute() must return a 2-tuple.
        """
        from medieval_forge.services.pipeline.manual_edit import compute
        from shapely.geometry import LineString

        # Split barony-2 (rows 20-29, cols 10-29) with vertical line at col=20
        # In rasterio coords: col=20, y from H-20=20 to H-29=11
        # cutLineCoords are in the coordinate system expected by replay_split (pixel coords)
        split_op = {
            "op": "split",
            "ts": 0,
            "parentId": 2,
            "allocated_original_idx": 3,
            "cutLineCoords": [[20, 0], [20, H]],  # vertical line at col=20, full height
        }
        cfg = _make_cfg(edit_log=[split_op])
        raster = _make_raster()

        # Must return tuple (not bare ndarray)
        result_tuple = compute(raster, cfg)
        assert isinstance(result_tuple, tuple), (
            f"compute() must return (ndarray, list), got {type(result_tuple)}"
        )
        assert len(result_tuple) == 2
        arr, entries = result_tuple
        assert isinstance(arr, np.ndarray)
        assert isinstance(entries, list)
