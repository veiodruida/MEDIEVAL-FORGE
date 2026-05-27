"""Wave 0 stub for Phase 08 — implemented in plan 08-08.

Covers REQ-IDs: LANDMASK-01, LANDMASK-02, DAG-04
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md

WARNING-4 fix: contracts.py + dag.py listed as affected; per-country KD-tree
rebuild required after landmask edit.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 0 stub — implementation lands in plan 08-08")


def test_landmask_manual_edit_invalidates_voronoi_cache():
    """Test will be filled by plan 08-08 per VALIDATION.md per-task table.

    LANDMASK-01 + DAG-04: editing the land mask polygon triggers version_token
    increment on the 'landmask' stage, causing voronoi (downstream) to be
    recomputed on next generate call.
    """
    pass


def test_landmask_edit_endpoint_returns_updated_geojson():
    """Test will be filled by plan 08-08 per VALIDATION.md per-task table.

    LANDMASK-01: POST /api/v3/projects/{id}/landmask/edit accepts a GeoJSON
    polygon and returns the updated landmask GeoJSON in response.
    """
    pass


def test_landmask_edit_rebuilds_per_country_kd_tree():
    """Test will be filled by plan 08-08 per VALIDATION.md per-task table.

    LANDMASK-02: after a landmask edit, the PT and ES KD-trees are rebuilt
    from the updated land polygon — not the previous cached trees.
    """
    pass
