"""Border-edit shrink → ocean-hole regression (2026-06-01 "carve-enclave-edit-leaves-hole").

GROUND TRUTH (captured from the real Apply payload, NOT hypothesised):
  Editing a barony's shared border emits `move` ops whose snapshot.vertices contains
  ONLY the edited barony's (shrunken) ring. manual_edit.compute() rebuilds ONLY that
  barony's polygon; the vacated land is rasterised with fill=-1 and is never reassigned
  to a neighbour. The D-27 contract (rule #5) says -1 == ocean ONLY — vacated LAND must
  never become -1.

These tests reproduce the user's exact repro class with two ADJACENT baronies and a
single shrink, WITHOUT any carve op (the prior carve fix does not touch this path).

Identity bounding box ⇒ _lonlat_to_rasterio_xy is a pass-through:
  lon = col ; lat = H - row  (rasterio y-flip)
"""
from __future__ import annotations

import numpy as np
import pytest

W, H = 40, 40

A_IDX = 0   # barony A — its shared border with B is dragged inward (shrunk)
B_IDX = 1   # barony B — the neighbour across the shared border

# Land block rows 10-29. A: cols 10-24. B: cols 25-39. Ocean (-1) elsewhere.
LAND_ROW_MIN, LAND_ROW_MAX = 10, 29
A_COL_MIN, A_COL_MAX = 10, 24
B_COL_MIN, B_COL_MAX = 25, 39

# Shrink A's right edge from col 24 inward to col 19 → vacated strip cols 20-24.
A_SHRUNK_COL_MAX = 19


def _pixel_to_lonlat(row: int, col: int) -> dict:
    """Inverse of _lonlat_to_rasterio_xy under the identity bbox."""
    return {"lon": float(col), "lat": float(H - row)}


def _make_raster() -> np.ndarray:
    raster = np.full((H, W), -1, dtype=np.int16)
    raster[LAND_ROW_MIN : LAND_ROW_MAX + 1, A_COL_MIN : A_COL_MAX + 1] = A_IDX
    raster[LAND_ROW_MIN : LAND_ROW_MAX + 1, B_COL_MIN : B_COL_MAX + 1] = B_IDX
    return raster


def _shrunk_a_ring() -> list[dict]:
    """A's new (shrunken) rectangle: rows 10-29, cols 10-19. 4 corners, closed loop."""
    return [
        _pixel_to_lonlat(LAND_ROW_MIN, A_COL_MIN),         # top-left
        _pixel_to_lonlat(LAND_ROW_MIN, A_SHRUNK_COL_MAX),  # top-right
        _pixel_to_lonlat(LAND_ROW_MAX, A_SHRUNK_COL_MAX),  # bottom-right
        _pixel_to_lonlat(LAND_ROW_MAX, A_COL_MIN),         # bottom-left
    ]


def _make_cfg(edit_log: list[dict], vertices: dict):
    from medieval_forge.services.pipeline.contracts import RegionConfig

    snapshot_data = {"edit_log": edit_log, "vertices": vertices}
    cfg = RegionConfig()
    cfg.map_w = W
    cfg.map_h = H
    cfg.lon_min = 0.0
    cfg.lon_max = float(W)
    cfg.lon_scale = 1.0
    cfg.lat_min = 0.0
    cfg.lat_max = float(H)
    cfg.manual_edit_log_hash = "border-shrink-test-hash"
    cfg.manual_edit_log_count = len(edit_log)
    cfg.branch_id = "border-shrink-test-branch"
    cfg.snapshot_loader = lambda bid: snapshot_data
    return cfg


def _build_shrink_inputs():
    """Return (raster, cfg, name_to_idx) for the shrink-A-border scenario."""
    ring = _shrunk_a_ring()
    vertices = {f"A#{i}": pt for i, pt in enumerate(ring)}
    # The real payload's move op carries only vertexIds + ts; coords live in vertices.
    move_op = {"op": "move", "ts": 0, "vertexIds": list(range(len(ring)))}
    cfg = _make_cfg([move_op], vertices)
    raster = _make_raster()
    name_to_idx = {"A": A_IDX, "B": B_IDX}
    return raster, cfg, name_to_idx


@pytest.mark.unit
class TestBorderShrinkLeavesNoOceanHole:
    """D-27 / rule #5: shrinking a shared border must NOT turn vacated land into ocean."""

    def test_vacated_land_is_never_ocean_sentinel(self):
        """RED: vacated strip (cols 20-24) becomes -1 today. It must become a real barony.

        Numeric fixtures:
          - A (idx=0): rows 10-29, cols 10-24 (input).
          - B (idx=1): rows 10-29, cols 25-39 (input).
          - A shrunk to cols 10-19 via a `move` op + A's new ring in vertices.
          - Vacated strip: rows 10-29, cols 20-24 (was A in input).

        Contract: every pixel that was LAND (A or B) in the input must remain a real
        barony idx (>=0, != 9999) in the output — never the ocean sentinel -1.
        """
        from medieval_forge.services.pipeline.manual_edit import compute

        raster, cfg, name_to_idx = _build_shrink_inputs()
        result, _ = compute(raster, cfg, name_to_idx)

        input_land = (raster >= 0) & (raster != 9999)
        orphaned = int(np.sum(input_land & (result == -1)))
        assert orphaned == 0, (
            f"{orphaned} land pixels became ocean (-1) after shrinking A's border. "
            f"Vacated land must be reassigned to a neighbour (D-27 / rule #5), not left ocean. "
            f"This is the user's 'buraco' — expected RED until the gap-fill lands."
        )

    def test_vacated_strip_extends_the_neighbour_not_the_shrunk_barony(self):
        """Default 'extend neighbour': the vacated strip should go to B, not back to A.

        A was deliberately shrunk to cols 10-19; refilling the strip back to A would
        silently undo the user's edit. The strip should extend the bordering neighbour B.
        """
        from medieval_forge.services.pipeline.manual_edit import compute

        raster, cfg, name_to_idx = _build_shrink_inputs()
        result, _ = compute(raster, cfg, name_to_idx)

        strip = result[LAND_ROW_MIN : LAND_ROW_MAX + 1, 20 : A_COL_MAX + 1]
        # No ocean in the strip, and it must not all revert to A (the shrunk barony).
        assert int(np.sum(strip == -1)) == 0, "vacated strip still has ocean pixels"
        assert int(np.sum(strip == B_IDX)) > 0, (
            "vacated strip should extend neighbour B (idx=1); found none — "
            "naive nearest-fill that pulls back to A undoes the user's shrink."
        )
