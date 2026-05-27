"""Wave 0 stub for Phase 08 — implemented in plan 08-06b.

Covers REQ-IDs: EDIT-VERTEX-01, TOPO-01, TOPO-02
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 0 stub — implementation lands in plan 08-06b")


def test_self_intersection_polygon_returns_SELF_INTERSECT_code():
    """Test will be filled by plan 08-06b per VALIDATION.md per-task table.

    TOPO-01: topology_validate() returns ('SELF_INTERSECT', detail) for a
    figure-8 polygon where the ring crosses itself.
    """
    pass


def test_disjoint_neighbour_returns_NEIGHBOUR_GAP_code():
    """Test will be filled by plan 08-06b per VALIDATION.md per-task table.

    TOPO-02: topology_validate() returns ('NEIGHBOUR_GAP', detail) when a
    moved vertex leaves a gap between two previously-touching territories.
    """
    pass


def test_valid_post_edit_polygon_returns_True_None():
    """Test will be filled by plan 08-06b per VALIDATION.md per-task table.

    TOPO-01: topology_validate() returns (True, None) for a well-formed,
    non-self-intersecting polygon with no gap to neighbours.
    """
    pass


def test_duplicate_vertex_coordinates_returns_DEGENERATE_code():
    """Test will be filled by plan 08-06b per VALIDATION.md per-task table.

    TOPO-01: topology_validate() catches degenerate (zero-area) polygons
    produced by duplicate consecutive vertices and returns DEGENERATE code.
    """
    pass
