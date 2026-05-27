"""Wave 0 stub for Phase 08 — implemented in plan 08-06b.

Covers REQ-IDs: TOPO-03, TOPO-04, EDIT-VERTEX-01
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 0 stub — implementation lands in plan 08-06b")


def test_move_shared_vertex_updates_both_neighbour_polygons():
    """Test will be filled by plan 08-06b per VALIDATION.md per-task table.

    TOPO-03: when a vertex is shared between two adjacent baronies,
    move_vertex() updates the same coordinate in both polygon rings so the
    shared edge remains topologically consistent.
    """
    pass


def test_shared_vertex_coupling_preserves_no_gap_between_neighbours():
    """Test will be filled by plan 08-06b per VALIDATION.md per-task table.

    TOPO-04: after moving a shared vertex, Shapely's distance() between the
    two updated polygons is 0.0 (no gap introduced).
    """
    pass


def test_non_shared_vertex_move_does_not_propagate_to_neighbours():
    """Test will be filled by plan 08-06b per VALIDATION.md per-task table.

    TOPO-03: a vertex that belongs to only one polygon does not trigger
    coupling propagation to adjacent territories.
    """
    pass
