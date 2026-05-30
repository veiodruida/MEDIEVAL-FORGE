"""Phase 08.2 Wave 0: E2E integration test — REAL wire format convergence gate.

REQ-IDs: BEZ-CONV-01, BEZ-CONV-02

xfail NOW, the Plan 02 red->green gate. NOT skip-marked — xfail is correct because:
- test infrastructure is complete (compute() is callable)
- test RUNS today and produces a predictable result (identity)
- Plan 02 flips it to xpass->pass by adding replay_vertex_ring to compute()

This test does NOT call _render_producer and does NOT touch the DB.
The _render_producer DB-fetch -> branch-hash -> loader join is covered by:
- Plan 02 Task 3: test_render_producer_loader_injection.py mock-DB tests
- Plan 04: Playwright UAT (BEZ-CONV-05)

This gate scopes itself to the compute()-replay contract:
  snapshot_loader injected directly (cfg.snapshot_loader = lambda _bid, _d=snap: _d)
  edit_log snake_case (real wire format — Pitfall 0)
  barony_name_to_idx built backend-side from bars[] (Pitfall 5 eliminated)

Pitfall coverage:
  - Pitfall 0 (edit_log snake_case): uses 'edit_log' key (NOT 'editLog')
  - Pitfall 1 (by-value capture): lambda _bid, _d=snapshot: _d
  - Pitfall 5 (barony_name_to_idx): passed as compute() param from bars[]
  - G8 criterion: rerasterised barony mask DIFFERS from baseline (not merely 'ran')

COASTLINE barony note (RESEARCH A3): the test builds a synthetic 2-barony raster
where barony_idx=1 occupies a coastal-like area. Interior shared-edge gaps are a
known design constraint (RESEARCH A3) and are out of scope for this gate.
"""
from __future__ import annotations

import pytest
import numpy as np
import rasterio.features
from rasterio.transform import from_bounds
from shapely.geometry import Polygon
from dataclasses import replace

from medieval_forge.services.pipeline.contracts import RegionConfig, geo_to_pixel


# ---------------------------------------------------------------------------
# Shared: build a minimal 2-barony raster using real Iberia cfg bounds.
# Must use real cfg so geo_to_pixel + from_bounds round-trip is meaningful.
# ---------------------------------------------------------------------------

def _make_iberia_cfg() -> RegionConfig:
    """Real Iberia 868 config for coordinate-space consistency."""
    from medieval_forge.services.pipeline.region_loader import load_region
    return load_region("iberia_868")


def _build_test_raster_and_snapshot(cfg: RegionConfig):
    """Build a minimal test raster (two baronies) + snapshot in REAL wire format.

    Barony 'Coastal' (bi=1): a small rectangle in the northwest (near the coast).
    Barony 'Inland'  (bi=2): a small rectangle in the center.

    The snapshot's edit_log moves one vertex of 'Coastal' so the ring changes.
    The snapshot is in the EXACT frontend wire format:
    - edit_log (snake_case, NOT editLog)
    - vertices: {"<baronyName>#<i>": {"lat": ..., "lon": ...}}
    - NO barony_name_to_idx in snapshot (it's passed as compute() param)

    Returns (arr, snapshot, barony_name_to_idx, bars_list)
    """
    H, W = cfg.map_h, cfg.map_w

    # Build a raster: two baronies in northwest Iberia (coastline region)
    # Coastal barony near Coruña (lon=-8.4, lat=43.4) — row ~100..115, col ~190..230
    arr = np.full((H, W), -1, dtype=np.int16)

    # Define small rectangles in geo space for predictable pixel coverage
    # Coastal barony: lon [-8.5, -8.2] x lat [43.3, 43.5] -> pixels
    coastal_px0, coastal_py0 = geo_to_pixel(-8.5, 43.5, cfg)  # top-left (high lat = low row)
    coastal_px1, coastal_py1 = geo_to_pixel(-8.2, 43.3, cfg)  # bottom-right

    # Inland barony: lon [-7.0, -6.7] x lat [42.8, 43.0]
    inland_px0, inland_py0 = geo_to_pixel(-7.0, 43.0, cfg)
    inland_px1, inland_py1 = geo_to_pixel(-6.7, 42.8, cfg)

    COASTAL_BI = 1
    INLAND_BI = 2
    arr[coastal_py0:coastal_py1, coastal_px0:coastal_px1] = COASTAL_BI
    arr[inland_py0:inland_py1, inland_px0:inland_px1] = INLAND_BI

    # Build the vertices dict for 'Coastal' ring (the 4-corner rectangle in geo coords)
    # These are the SAME coords the sidecar would store, so geo_to_pixel round-trip holds
    coastal_ring_lonlat = [
        (-8.5, 43.5),  # top-left
        (-8.5, 43.3),  # bottom-left
        (-8.2, 43.3),  # bottom-right
        (-8.2, 43.5),  # top-right
        (-8.5, 43.5),  # close ring
    ]
    vertices: dict[str, dict] = {}
    for i, (lon, lat) in enumerate(coastal_ring_lonlat[:-1]):  # exclude closing vertex
        vertices[f"Coastal#{i}"] = {"lat": lat, "lon": lon}

    # Move vertex #2 (bottom-right corner) outward — larger rectangle
    # Original: lon=-8.2, lat=43.3 -> moved: lon=-8.1, lat=43.2
    vertices["Coastal#2"] = {"lat": 43.2, "lon": -8.1}

    # Snapshot in EXACT frontend wire format (Pitfall 0: snake_case edit_log)
    snapshot = {
        "edit_log": [
            {
                "op": "move",
                "ts": 1000,
                "vertexIds": ["Coastal#2"],
            }
        ],
        "vertices": vertices,
        # NO barony_name_to_idx key — it's passed as compute() param (Pitfall 5 fix)
    }

    bars_list = [
        {"name": "Coastal", "condado_idx": 0},
        {"name": "Inland", "condado_idx": 0},
    ]
    barony_name_to_idx = {b["name"]: i for i, b in enumerate(bars_list)}

    return arr, snapshot, barony_name_to_idx, bars_list


# ---------------------------------------------------------------------------
# End-to-end convergence test (xfail until Plan 02 lands)
# ---------------------------------------------------------------------------

def test_bezier_convergence_e2e_edited_barony_mask_differs_from_baseline():
    """G8 closure gate: after vertex-op replay, the edited barony pixel mask DIFFERS
    from the zero-edit baseline.

    REAL wire format — uses edit_log (snake_case), vertices dict, no DB.
    Snapshot loader injected directly via by-value lambda (Pitfall 1 fix).
    barony_name_to_idx built from bars[] backend-side (Pitfall 5 fix).

    Catches simultaneously:
    - Pitfall 0 (edit_log key mismatch): uses snake_case edit_log
    - Pitfall 5 (barony_name_to_idx): passed as compute() param
    - G8 criterion: rerasterised mask != baseline (not just 'ran')

    xfail(strict=True): suite stays green now; Plan 02 flips to xpass->pass by
    implementing replay_vertex_ring in compute() and removing this xfail.
    """
    from medieval_forge.services.pipeline.manual_edit import compute

    cfg = _make_iberia_cfg()
    arr, snapshot, barony_name_to_idx, _ = _build_test_raster_and_snapshot(cfg)

    # BASELINE: zero-edit run (empty hash -> identity path)
    cfg_baseline = replace(cfg, manual_edit_log_hash="", manual_edit_log_count=0)
    # Phase 08.3 Plan 01 (Rule 1 fix): compute() returns (ndarray, list) tuple since Plan 01.
    # Unpack to get the array; empty new_barony_entries for baseline (zero-edit path).
    baseline, _ = compute(arr.copy(), cfg_baseline)
    assert np.array_equal(baseline, arr), "Baseline must be identity (empty hash)"

    # EDITED: inject snapshot directly (mimics _render_producer by-value pattern)
    cfg_edited = replace(
        cfg,
        manual_edit_log_hash="bezier_move_a1b2c3d4",
        manual_edit_log_count=1,
    )
    # By-value capture (Pitfall 1 fix): loader captured before scope exit
    cfg_edited.snapshot_loader = lambda _bid, _d=snapshot: _d

    # Plan 02 wave: compute() gains barony_name_to_idx param
    # Phase 08.3 Plan 01 (Rule 1 fix): unpack tuple return from compute()
    result, _ = compute(arr.copy(), cfg_edited, barony_name_to_idx=barony_name_to_idx)

    COASTAL_BI = 1
    baseline_mask = baseline == COASTAL_BI
    result_mask = result == COASTAL_BI

    # G8 criterion: edited barony mask DIFFERS from baseline
    # Not merely 'ran' — must show pixel-level geometry change
    masks_differ = not np.array_equal(result_mask, baseline_mask)
    assert masks_differ, (
        "G8 GATE: edited barony mask is IDENTICAL to baseline after vertex-op replay. "
        "The move op (vertex #2 shifted from lon=-8.2 to lon=-8.1) must produce a "
        "DIFFERENT pixel mask. "
        "Likely cause: replay_vertex_ring not yet implemented in compute(). "
        "Plan 02 must add replay_vertex_ring() and call it for move/add/delete ops."
    )

    # Additional: the diff should be significant (not just 1-2 noise pixels)
    diff_pixels = int(np.sum(result_mask != baseline_mask))
    assert diff_pixels >= 5, (
        f"Only {diff_pixels} pixels differ — too few for a real vertex move. "
        "Expected at least 5 pixel difference for a meaningful geometry change."
    )
