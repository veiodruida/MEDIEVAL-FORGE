"""Wave 0 stub for Phase 08 — implemented in plan 08-03.

Covers REQ-IDs: PERSIST-01, PERSIST-02, BRANCH-03
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 0 stub — implementation lands in plan 08-03")


def test_snapshot_saved_on_branch_switch_and_reloaded_correctly():
    """Test will be filled by plan 08-03 per VALIDATION.md per-task table.

    PERSIST-01: switching branches triggers an auto-save snapshot; reloading
    that branch returns the same GeoJSON vertex coordinates.
    """
    pass


def test_snapshot_list_endpoint_returns_all_saved_states():
    """Test will be filled by plan 08-03 per VALIDATION.md per-task table.

    PERSIST-02: GET /api/v3/projects/{id}/branches/{branch_id}/snapshots
    returns all snapshot entries ordered by created_at.
    """
    pass


def test_restore_snapshot_replaces_active_geojson_in_stage_cache():
    """Test will be filled by plan 08-03 per VALIDATION.md per-task table.

    PERSIST-02: POST /api/v3/projects/{id}/snapshots/{snap_id}/restore
    overwrites the stage cache with the snapshot GeoJSON and invalidates
    downstream tokens.
    """
    pass
