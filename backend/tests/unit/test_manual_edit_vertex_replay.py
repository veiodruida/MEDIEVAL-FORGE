"""Phase 08.2 Wave 0: vertex-replay test scaffold + round-trip identity gate.

REQ-IDs: BEZ-CONV-01, BEZ-CONV-02, BEZ-CONV-04

GROUP A (passes TODAY) — round-trip identity:
  test_round_trip_identity_unedited_real_iberia_barony_ring_is_byte_equal_to_raster_mask

GROUP B (skip-marked; Plan 02 removes skips when Wave 1 lands):
  test_move_op_re_rasterises_edited_barony_ring_pixels_differ_from_identity
  test_add_op_grows_barony_ring
  test_multi_delete_op_shrinks_barony_ring
  test_barony_name_to_idx_built_from_bars_not_frontend

GROUP C (skip-marked; Plan 02 removes skip when Wave 1 lands) — BEZ-CONV-04:
  test_landmask_only_branch_with_nonempty_hash_returns_byte_identical

Key Finding (A1 verification — 2026-05-30):
  The baronies.geojson sidecar ring IS the full pixel-staircase polygon from
  rasterio.features.shapes (NOT simplified/curve-fit). Each vertex is an integer
  pixel coord stored as lon/lat via _ring_to_lonlat.

  Coordinate convention for Plan 02 replay_vertex_ring:
  - geo_to_pixel(lon, lat, cfg) returns (px_col, py_row) where py_row is row index
    (row 0 = top, grows DOWN). Uses int() truncation.
  - rasterio.features.rasterize with from_bounds(0,0,W,H,W,H) requires RASTERIO world y
    where y grows UP (y=0 = bottom, y=H = top).
  - Conversion: rasterio_y = H - py_row (from geo_to_pixel).
  - CRITICAL: use round() NOT int() for lon/lat -> pixel conversion in replay!
    geo_to_pixel uses int() (floor truncation). For ring re-rasterisation, FP noise
    causes int(959.57) = 959 but round(959.57) = 960 — byte-exact match requires
    round() for the pixel_coords passed to rasterize. geo_to_pixel is parity-frozen
    and MUST NOT be changed; Plan 02 must implement its own rounding helper.
    Verified: round() + H-row flip -> 0 diff pixels; int() + H-row flip -> 34 diff pixels.

ESCALATION path:
  If test_round_trip_identity fails, it calls pytest.fail() with escalation message.
  DO NOT relax the assertion. DO NOT substitute a synthetic rectangle.
  A1 failure means ring re-rasterisation from lon/lat is the wrong mechanism and
  Plan 02 is unbuildable as written — surface it at Wave 0.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import replace
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import rasterio.features
from rasterio.transform import from_bounds
from shapely.geometry import Polygon

from medieval_forge.services.pipeline.contracts import RegionConfig, geo_to_pixel


# ---------------------------------------------------------------------------
# Helper: convert lon/lat to rasterio world y using ROUND (not int truncation).
# This is the conversion Plan 02's replay_vertex_ring MUST use.
# geo_to_pixel is parity-frozen; replay_vertex_ring must implement its own helper.
# ---------------------------------------------------------------------------

def _lonlat_to_rasterio_xy(lon: float, lat: float, cfg: RegionConfig, W: int, H: int):
    """Convert WGS84 lon/lat to rasterio world (x, y) for from_bounds(0,0,W,H,W,H).

    CRITICAL: uses round() NOT int(). geo_to_pixel uses int() truncation which causes
    ~34px drift per barony ring. round() is the correct inverse and produces byte-equal
    rasterization. Plan 02's replay_vertex_ring MUST use this rounding convention.
    geo_to_pixel is parity-frozen and MUST NOT be changed.

    Coordinate convention:
    - geo_to_pixel returns py_row where row 0 = top (y grows DOWN).
    - from_bounds(0,0,W,H,W,H) uses rasterio world y where y=0 = bottom (y grows UP).
    - Conversion: rasterio_y = H - py_row.
    - Using round() instead of int() for py_row eliminates FP truncation drift.

    Returns (x, rasterio_y) where:
    - x = column index (0=left, W=right)
    - rasterio_y = H - row_index (0=bottom, H=top)
    """
    span = (cfg.lon_max - cfg.lon_min) * cfg.lon_scale
    x = round((lon - cfg.lon_min) * cfg.lon_scale / span * W)
    # py_row (0=top, grows DOWN) with round() instead of int():
    py_row = round((1.0 - (lat - cfg.lat_min) / (cfg.lat_max - cfg.lat_min)) * H)
    # Convert to rasterio world y (0=bottom, grows UP):
    rasterio_y = H - py_row
    return (x, rasterio_y)


# ---------------------------------------------------------------------------
# Session-scoped fixture: run Iberia 868 pipeline ONCE, persist arrays.
# Cost: ~30s on first run; the fixture is session-scoped to amortize.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def iberia_merge_and_sidecar(tmp_path_factory):
    """Run Iberia 868 pipeline, return (merge_int16_array, baronies_geojson_dict, cfg)."""
    from medieval_forge.services.pipeline import run_pipeline
    from medieval_forge.services.pipeline import cache as cache_mod
    from medieval_forge.services.pipeline.region_loader import load_region

    out = tmp_path_factory.mktemp("iberia_rt_test")
    project_id = "a1-roundtrip-session-00000000"
    cfg = replace(load_region("iberia_868"), output_dir=str(out))
    run_pipeline(cfg, project_id=project_id)

    entry = cache_mod.cache_get(project_id, "main", "merge")
    if entry is None:
        pytest.fail("Pipeline ran but 'merge' stage cache entry is absent — fixture broken.")
    merge_arr = entry.array.copy()

    bj_path = os.path.join(str(out), "baronies.geojson")
    with open(bj_path, encoding="utf-8") as f:
        bj = json.load(f)

    return merge_arr, bj, cfg


# ---------------------------------------------------------------------------
# GROUP A: round-trip identity (MUST PASS TODAY — A1 gate)
# ---------------------------------------------------------------------------

def test_round_trip_identity_unedited_real_iberia_barony_ring_is_byte_equal_to_raster_mask(
    iberia_merge_and_sidecar,
):
    """A1 gate: geo_to_pixel ring from baronies.geojson sidecar, rasterized back,
    must be byte-equal to the original result==bi mask.

    Uses COASTLINE barony 'Gijón' (lat ~43.54, north coast, no interior neighbours
    to gap per RESEARCH A3). The sidecar ring is the full pixel-staircase polygon
    from rasterio.features.shapes (not simplified/curve-fit) — verified 2026-05-30.

    Coordinate contract (Plan 02 replay_vertex_ring must follow):
    1. Ring lon/lat -> _lonlat_to_rasterio_xy() which uses round() (NOT int()).
    2. Build Shapely Polygon from rasterio world (x, y) coords.
    3. Rasterize with from_bounds(0,0,W,H,W,H), all_touched=False.
    4. Assert np.array_equal(rerasterised == bi, original_mask).

    If this test FAILS: DO NOT relax the assertion. DO NOT substitute a synthetic
    rectangle. Escalation required — ring re-rasterisation is the wrong mechanism
    for Plan 02 and the phase is blocked. Investigate truncation / staircase drift.
    """
    merge_arr, bj, cfg = iberia_merge_and_sidecar
    H, W = merge_arr.shape

    # COASTLINE barony: Gijón (north coast, lat ~43.54 — open boundary, RESEARCH A3)
    barony_name = "Gijón"
    target = next((f for f in bj["features"] if f["id"] == barony_name), None)
    if target is None:
        available = [f["id"] for f in bj["features"][:10]]
        pytest.fail(
            f"Barony '{barony_name}' not found in baronies.geojson. "
            f"Available (first 10): {available}"
        )

    # Determine barony raster index bi from centroid pixel
    centroid = target["properties"]["centroid"]
    lon_c, lat_c = centroid
    px_c, py_c = geo_to_pixel(lon_c, lat_c, cfg)
    bi = int(merge_arr[py_c, px_c])

    if bi < 0:
        pytest.fail(
            f"Centroid of '{barony_name}' at pixel ({px_c},{py_c}) is ocean (bi={bi}). "
            "Fixture or centroid coordinate bug."
        )

    original_mask = merge_arr == bi
    original_pixel_count = int(np.sum(original_mask))

    # Source the sidecar ring (full staircase polygon in lon/lat)
    geom = target["geometry"]
    if geom["type"] == "Polygon":
        ring = geom["coordinates"][0]
    elif geom["type"] == "MultiPolygon":
        # Pick the largest polygon ring for coastline barony
        rings = [p[0] for p in geom["coordinates"]]
        ring = max(rings, key=len)
    else:
        pytest.fail(f"Unexpected geometry type: {geom['type']}")

    # Note: this ring IS the full pixel staircase polygon from rasterio.features.shapes,
    # converted to lon/lat via _ring_to_lonlat (canvas_sidecars.py line 56-63).
    # NOT simplified/curve-fit. The distinction matters: geo_to_pixel on simplified
    # coords would give larger drift than on the pixel-staircase.

    # Convert ring lon/lat to rasterio world coords (x, rasterio_y)
    # CRITICAL: must use round(), not int() — see module docstring + _lonlat_to_rasterio_xy.
    rasterio_coords = [
        _lonlat_to_rasterio_xy(coord[0], coord[1], cfg, W, H)
        for coord in ring
    ]
    poly = Polygon(rasterio_coords)

    if not poly.is_valid:
        pytest.fail(
            f"Reconstructed polygon for '{barony_name}' is invalid (shapely is_valid=False). "
            "Geometry integrity issue in sidecar or conversion."
        )

    # Rasterise using the same transform as compute()
    transform = from_bounds(0, 0, W, H, W, H)
    rerasterised = rasterio.features.rasterize(
        [(poly, bi)],
        out_shape=(H, W),
        transform=transform,
        fill=-1,
        dtype=np.int16,
        all_touched=False,
    )
    rerasterised_mask = rerasterised == bi
    rerasterised_pixel_count = int(np.sum(rerasterised_mask))

    # Compute diff for diagnostic message
    diff_count = int(np.sum(rerasterised_mask != original_mask))
    diff_pct = 100.0 * diff_count / original_mask.size

    if diff_count > 0:
        # Determine if diff is a coordinate-convention error (whole flip / constant offset)
        # or true truncation drift (sparse boundary pixels).
        false_pos = int(np.sum(rerasterised_mask & ~original_mask))
        false_neg = int(np.sum(~rerasterised_mask & original_mask))

        pytest.fail(
            f"A1 GATE FAILED: '{barony_name}' round-trip rasterisation is NOT byte-equal.\n"
            f"  original  = {original_pixel_count} pixels\n"
            f"  rerasterised = {rerasterised_pixel_count} pixels\n"
            f"  diff = {diff_count} pixels ({diff_pct:.4f}% of raster)\n"
            f"  false_pos (rerasterised extra) = {false_pos}\n"
            f"  false_neg (original missing)   = {false_neg}\n"
            f"\n"
            f"ESCALATION REQUIRED — DO NOT relax this assertion.\n"
            f"If diff is large (>>10px) and spatially structured: likely a coordinate-\n"
            f"convention mismatch in the test setup — check _lonlat_to_rasterio_xy.\n"
            f"If diff is sparse (scattered boundary pixels): truncation drift in round() —\n"
            f"ring re-rasterisation from lon/lat is the wrong mechanism for Plan 02.\n"
            f"In either case: Plan 02 is blocked until A1 is resolved.\n"
            f"See .planning/phases/08.2-bezier-edit-to-map-convergence-backend-replay/"
            f"08.2-RESEARCH.md §A1."
        )

    # Byte-equal assertion
    assert np.array_equal(rerasterised_mask, original_mask), (
        f"A1 GATE: '{barony_name}' round-trip rasterisation must be byte-equal. "
        f"diff={diff_count} pixels. See test docstring for escalation path."
    )


# ---------------------------------------------------------------------------
# GROUP B: vertex-replay behaviour (skip-marked until Plan 02 lands)
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Wave 1: replay not yet implemented in compute()")
def test_move_op_re_rasterises_edited_barony_ring_pixels_differ_from_identity():
    """BEZ-CONV-01: move op triggers ring re-rasterisation; mask differs from identity.

    Plan 02 mechanism: compute() receives barony_name_to_idx param + snapshot with
    edit_log (snake_case) containing move ops; looks up vertex ring from vertices dict,
    converts to rasterio coords via round(), rasterizes, replaces polygons_by_id entry.

    END-TO-END criterion: the ==3 mask DIFFERS from input, not merely 'ran'.

    Snapshot shape (real wire format):
    - edit_log: [{"op": "move", "ts": 1, "vertexIds": ["B#2"]}]  (snake_case key)
    - vertices: {"B#0": {lat, lon}, "B#1": {lat, lon}, "B#2": {lat: moved_lat, lon: moved_lon}, ...}
    barony_name_to_idx = {"B": 3} (passed as compute() param, NOT in snapshot)
    """
    # NOTE: When this skip is removed (Plan 02), implement as follows:
    # 1. Build a 50x50 int16 raster with barony 3 occupying a 10x10 block at rows 10-19, cols 10-19.
    # 2. Build cfg with iberia_868 bounds (real geo_to_pixel needed for rasterio compatibility).
    # 3. Construct snapshot: edit_log with move op on vertex "B#2"; vertices dict with all ring
    #    points of barony B's ring, one of them moved by ~2 pixels.
    # 4. Set cfg.manual_edit_log_hash = "deadbeef12345678", manual_edit_log_count = 1.
    # 5. cfg.snapshot_loader = lambda _bid, _d=snapshot: _d  (by-value capture, Pitfall 1).
    # 6. Call compute(arr, cfg, barony_name_to_idx={"B": 3}).
    # 7. Assert np.any(out[barony_rows, barony_cols] != arr[barony_rows, barony_cols]).
    from medieval_forge.services.pipeline.manual_edit import compute
    from medieval_forge.services.pipeline.contracts import RegionConfig

    arr = np.full((50, 50), -1, dtype=np.int16)
    arr[10:20, 10:20] = 3  # barony 3
    cfg = RegionConfig(
        manual_edit_log_hash="deadbeef12345678",
        manual_edit_log_count=1,
    )
    snapshot = {
        "edit_log": [{"op": "move", "ts": 1, "vertexIds": ["B#2"]}],
        "vertices": {
            "B#0": {"lat": 42.0, "lon": -8.0},
            "B#1": {"lat": 42.5, "lon": -8.0},
            "B#2": {"lat": 43.0, "lon": -7.5},  # moved: original was 42.5, -7.5
            "B#3": {"lat": 42.0, "lon": -7.5},
        },
    }
    cfg.snapshot_loader = lambda _bid, _d=snapshot: _d
    barony_name_to_idx = {"B": 3}

    out = compute(arr, cfg, barony_name_to_idx=barony_name_to_idx)

    assert not np.array_equal(out == 3, arr == 3), (
        "move op must produce a DIFFERENT mask (not identity). "
        "If identical: replay_vertex_ring was not called or is a no-op."
    )


@pytest.mark.skip(reason="Wave 1: replay not yet implemented in compute()")
def test_add_op_grows_barony_ring():
    """BEZ-CONV-02: add op appends vertex to ring; mask area grows or shifts."""
    from medieval_forge.services.pipeline.manual_edit import compute
    from medieval_forge.services.pipeline.contracts import RegionConfig

    arr = np.full((50, 50), -1, dtype=np.int16)
    arr[10:20, 10:20] = 5
    cfg = RegionConfig(
        manual_edit_log_hash="add000000000abcd",
        manual_edit_log_count=1,
    )
    # add op: new vertex B#4 inserted into ring
    snapshot = {
        "edit_log": [{"op": "add", "ts": 1, "vertexIds": ["B#4"], "lat": 43.2, "lon": -7.3}],
        "vertices": {
            "B#0": {"lat": 42.0, "lon": -8.0},
            "B#1": {"lat": 42.5, "lon": -8.0},
            "B#2": {"lat": 42.5, "lon": -7.5},
            "B#3": {"lat": 42.0, "lon": -7.5},
            "B#4": {"lat": 43.2, "lon": -7.3},  # new vertex
        },
    }
    cfg.snapshot_loader = lambda _bid, _d=snapshot: _d
    out = compute(arr, cfg, barony_name_to_idx={"B": 5})
    assert not np.array_equal(out == 5, arr == 5), (
        "add op must change the barony mask (vertices dict extended)."
    )


@pytest.mark.skip(reason="Wave 1: replay not yet implemented in compute()")
def test_multi_delete_op_shrinks_barony_ring():
    """BEZ-CONV-02: multi_delete op removes vertex from ring; mask changes."""
    from medieval_forge.services.pipeline.manual_edit import compute
    from medieval_forge.services.pipeline.contracts import RegionConfig

    arr = np.full((50, 50), -1, dtype=np.int16)
    arr[10:20, 10:20] = 7
    cfg = RegionConfig(
        manual_edit_log_hash="del000000000abcd",
        manual_edit_log_count=1,
    )
    # multi_delete op: vertex B#2 removed; vertices dict has only 3 remaining
    snapshot = {
        "edit_log": [{"op": "multi_delete", "ts": 1, "vertexIds": ["B#2"]}],
        "vertices": {
            "B#0": {"lat": 42.0, "lon": -8.0},
            "B#1": {"lat": 42.5, "lon": -8.0},
            "B#3": {"lat": 42.0, "lon": -7.5},  # B#2 absent
        },
    }
    cfg.snapshot_loader = lambda _bid, _d=snapshot: _d
    out = compute(arr, cfg, barony_name_to_idx={"B": 7})
    assert not np.array_equal(out == 7, arr == 7), (
        "multi_delete op must change the barony mask (vertices dict shrunk)."
    )


@pytest.mark.skip(reason="Wave 1: replay not yet implemented in compute()")
def test_barony_name_to_idx_built_from_bars_not_frontend():
    """BEZ-CONV-01: compute() uses the passed barony_name_to_idx param (NOT a snapshot field).

    Proves Plan 02's design: backend builds {b['name']: i for i,b in enumerate(bars)}
    and passes it as param — no frontend ordering assumption (A2/A4 eliminated).
    The snapshot blob has NO barony_name_to_idx key; replay must still work.
    """
    from medieval_forge.services.pipeline.manual_edit import compute
    from medieval_forge.services.pipeline.contracts import RegionConfig

    arr = np.full((50, 50), -1, dtype=np.int16)
    arr[10:20, 10:20] = 9
    cfg = RegionConfig(
        manual_edit_log_hash="idx000000000abcd",
        manual_edit_log_count=1,
    )
    snapshot = {
        # Deliberately NO "barony_name_to_idx" key in snapshot — compute() must NOT look for it.
        "edit_log": [{"op": "move", "ts": 1, "vertexIds": ["MyBarony#1"]}],
        "vertices": {
            "MyBarony#0": {"lat": 42.0, "lon": -8.0},
            "MyBarony#1": {"lat": 43.0, "lon": -7.5},  # moved
            "MyBarony#2": {"lat": 42.0, "lon": -7.5},
        },
    }
    cfg.snapshot_loader = lambda _bid, _d=snapshot: _d

    # barony_name_to_idx supplied as param (backend-built from bars[])
    barony_name_to_idx = {"MyBarony": 9}
    out = compute(arr, cfg, barony_name_to_idx=barony_name_to_idx)

    assert not np.array_equal(out == 9, arr == 9), (
        "compute() must use the barony_name_to_idx PARAM (not a snapshot key). "
        "If identical to identity: the param was ignored and replay used wrong lookup."
    )


# ---------------------------------------------------------------------------
# GROUP C: landmask-only parity guard (BEZ-CONV-04 discriminating test)
# skip-marked until Wave 1 lands
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Wave 1: BEZ-CONV-04 guard not yet implemented in compute()")
def test_landmask_only_branch_with_nonempty_hash_returns_byte_identical():
    """BEZ-CONV-04 discriminator: a branch with a non-empty manual_edit_log_hash
    but ZERO vertex ops (only landmask_replace ops) must return byte-identical output.

    Distinct from the zero-edit Iberia parity run (which uses empty hash).
    This test catches Pitfall 4: if ring re-rasterisation enters on a landmask-only
    branch, the roundtrip degrades barony boundaries (not byte-equal) — parity breaks
    on landmask-only branches. Plan 02's compute() must guard:
    'if not vertex_ops: skip ring re-rasterisation' BEFORE entering the polygon loop.

    Comment: This fails if Pitfall 4 is live (ring re-rasterisation entered on a
    landmask-only branch). The existing split/merge/translate path may still run
    if those ops are present — this test uses ONLY landmask_replace.
    """
    from medieval_forge.services.pipeline.manual_edit import compute
    from medieval_forge.services.pipeline.contracts import RegionConfig

    arr = np.full((50, 50), -1, dtype=np.int16)
    arr[5:25, 5:25] = 1   # barony 1
    arr[5:25, 25:45] = 2  # barony 2

    cfg = RegionConfig(
        manual_edit_log_hash="landmask_only_abc",  # non-empty hash
        manual_edit_log_count=1,
    )
    # Snapshot contains ONLY landmask_replace op (zero vertex ops)
    snapshot = {
        "edit_log": [
            {
                "op": "landmask_replace",
                "ts": 1,
                "coords": [[-9.0, 43.0], [-8.0, 43.0], [-8.0, 42.0], [-9.0, 42.0]],
            }
        ],
        "vertices": {},  # empty vertices dict — no vertex ops
    }
    cfg.snapshot_loader = lambda _bid, _d=snapshot: _d

    barony_name_to_idx = {"A": 1, "B": 2}
    out = compute(arr, cfg, barony_name_to_idx=barony_name_to_idx)

    assert np.array_equal(out, arr), (
        "BEZ-CONV-04: landmask-only branch with non-empty hash must return byte-identical "
        "output (no vertex ops present). "
        "If this fails: Pitfall 4 is live — ring re-rasterisation is entering on "
        "landmask-only branches and degrading parity. Fix: check for vertex ops BEFORE "
        "entering the ring re-rasterisation path in compute()."
    )


# ---------------------------------------------------------------------------
# Coordinate contract guard (always runs — not skip-marked)
# Locks the rounding convention so Plan 02 cannot accidentally use int()
# ---------------------------------------------------------------------------

def test_lonlat_to_rasterio_xy_round_convention_byte_exact_for_integer_source_coords(
    iberia_merge_and_sidecar,
):
    """Coordinate contract: _lonlat_to_rasterio_xy with round() must exactly recover
    integer source coordinates that rasterio.features.shapes emits.

    Verifies: given a rasterio source ring coord (integer x, integer rasterio_y),
    _ring_to_lonlat(x, y) -> lon/lat -> _lonlat_to_rasterio_xy -> (x, y) exactly.

    This is the mechanical contract Plan 02 must satisfy. If this fails:
    a future change to geo_to_pixel, lon_scale, or map dimensions broke the
    coordinate round-trip. The int() vs round() distinction is LOAD-BEARING.
    Using int() instead of round() here would cause ~34px drift on a real barony.
    """
    merge_arr, bj, cfg = iberia_merge_and_sidecar
    H, W = merge_arr.shape

    # Get source rasterio coords for Gijón (integer pixel boundary staircase)
    from shapely.geometry import shape as shapely_shape

    transform = from_bounds(0, 0, W, H, W, H)
    barony_name = "Gijón"
    target_feat = next((f for f in bj["features"] if f["id"] == barony_name), None)
    if target_feat is None:
        pytest.skip(f"Barony '{barony_name}' not in baronies.geojson — fixture issue")

    centroid = target_feat["properties"]["centroid"]
    lon_c, lat_c = centroid
    px_c, py_c = geo_to_pixel(lon_c, lat_c, cfg)
    bi = int(merge_arr[py_c, px_c])

    source_poly = None
    for geom_dict, value in rasterio.features.shapes(merge_arr.astype(np.int16), transform=transform):
        if int(value) == bi:
            source_poly = shapely_shape(geom_dict)
            break

    if source_poly is None:
        pytest.fail(f"No rasterio shape found for bi={bi}")

    source_ring = list(source_poly.exterior.coords)

    # Get the sidecar ring (lon/lat), which came from _ring_to_lonlat of the same source
    sidecar_ring = target_feat["geometry"]["coordinates"][0]

    # For each sidecar lon/lat, reconstruct rasterio coords and compare to source
    mismatches: list[tuple] = []
    for i, (coord, src_pt) in enumerate(zip(sidecar_ring, source_ring)):
        lon, lat = coord[0], coord[1]
        x_recon, y_recon = _lonlat_to_rasterio_xy(lon, lat, cfg, W, H)
        x_src, y_src = int(src_pt[0]), int(src_pt[1])
        if x_recon != x_src or y_recon != y_src:
            mismatches.append((i, (x_src, y_src), (x_recon, y_recon)))

    assert not mismatches, (
        f"_lonlat_to_rasterio_xy failed to exactly recover {len(mismatches)} of "
        f"{len(source_ring)} source coords for '{barony_name}'.\n"
        f"First 5 mismatches (idx, src, recon): {mismatches[:5]}\n"
        f"CRITICAL: Plan 02's replay_vertex_ring MUST use round() NOT int() in "
        f"the lon/lat -> pixel conversion. See test module docstring."
    )
