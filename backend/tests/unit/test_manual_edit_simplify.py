"""Wave 0 stub for Phase 08 — implemented in plan 08-06a.

Covers REQ-IDs: EDIT-VERTEX-01, EDIT-VERTEX-02, EDIT-VERTEX-04
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md
"""
import pytest

pytestmark = pytest.mark.skip(reason="Wave 0 stub — implementation lands in plan 08-06a")


def test_simplify_polygon_reduces_vertex_count_below_cap():
    """Test will be filled by plan 08-06a per VALIDATION.md per-task table.

    EDIT-VERTEX-04: simplify_polygon() reduces vertex count to <= cap using
    Ramer-Douglas-Peucker; result still passes topology validation.
    """
    pass


def test_simplify_preserves_boundary_vertices_at_tolerance_zero():
    """Test will be filled by plan 08-06a per VALIDATION.md per-task table.

    EDIT-VERTEX-04: at tolerance=0.0 simplify_polygon() returns the
    original vertex list unchanged.
    """
    pass


def test_simplify_result_polygon_passes_topology_validate():
    """Test will be filled by plan 08-06a per VALIDATION.md per-task table.

    EDIT-VERTEX-01: simplified polygon is self-intersection-free and
    topology_validate() returns (True, None) after simplification.
    """
    pass
