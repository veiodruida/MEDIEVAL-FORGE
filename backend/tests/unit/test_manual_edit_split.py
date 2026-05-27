"""Wave 0 stub for Phase 08 — implemented in plan 08-07.

Covers REQ-IDs: EDIT-POLYGON-01, EDIT-POLYGON-02, DAG-01
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 0 stub — implementation lands in plan 08-07")


def test_split_territory_produces_two_non_overlapping_polygons():
    """Test will be filled by plan 08-07 per VALIDATION.md per-task table.

    EDIT-POLYGON-01: split_territory() cuts a barony along a user-drawn
    line and returns two non-overlapping polygons whose union equals the
    original area (Shapely symmetric_difference == empty).
    """
    pass


def test_split_territory_assigns_unique_ids_to_both_halves():
    """Test will be filled by plan 08-07 per VALIDATION.md per-task table.

    EDIT-POLYGON-01: both output territories receive distinct IDs; neither
    ID collides with existing barony IDs in the project.
    """
    pass


def test_split_emits_dag_manual_edit_version_token():
    """Test will be filled by plan 08-07 per VALIDATION.md per-task table.

    DAG-01: split_territory() increments the manual_edit stage version_token
    so the DAG cache invalidates downstream stages (render, lookup, export).
    """
    pass
