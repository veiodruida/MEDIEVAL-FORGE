"""Wave 0 stub for Phase 08 — implemented in plan 08-07c.

Covers REQ-IDs: EDIT-POLYGON-01, EDIT-POLYGON-02, EDIT-POLYGON-03, DAG-01, DAG-02
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md

BLOCKER-1 closure (08-07c): compute() replay path.
Replay loads the branch snapshot, vectorises edit events, replays them
in order, then rasterises the resulting polygon geometry.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 0 stub — implementation lands in plan 08-07c")


def test_compute_loads_snapshot_and_vectorises_edit_events():
    """Test will be filled by plan 08-07c per VALIDATION.md per-task table.

    DAG-01 + BLOCKER-1: compute() reads the branch snapshot GeoJSON and
    converts the stored edit_events list into vectorised geometry ops.
    """
    pass


def test_compute_replay_applies_all_edit_events_in_order():
    """Test will be filled by plan 08-07c per VALIDATION.md per-task table.

    EDIT-POLYGON-01 + BLOCKER-1: compute() applies move/split/merge ops in
    the same order they were recorded — reversing order produces different
    polygon geometry.
    """
    pass


def test_compute_rasterise_produces_lookup_barony_pixels():
    """Test will be filled by plan 08-07c per VALIDATION.md per-task table.

    DAG-02 + BLOCKER-1: after replay, compute() rasterises the edited
    polygons to a 1920x1080 numpy array matching lookup_barony.png format.
    """
    pass


def test_rasterize_uses_all_touched_false():
    """Test will be filled by plan 08-07c per VALIDATION.md per-task table.

    BLOCKER-1 closure (Gemini review LOW): rasterize() call uses
    all_touched=False to prevent raster-vector roundtrip artifacts that
    would corrupt Unity byOriginalIdx shader lookups.
    """
    pass
