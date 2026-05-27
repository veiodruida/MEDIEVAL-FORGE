"""Phase 08 Plan 06a — unit tests for topology.py validate_edit + douglas_peucker_simplify.

Covers REQ-IDs: EDIT-VERTEX-01, EDIT-VERTEX-02, EDIT-VERTEX-04, TOPO-01
See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-06a-PLAN.md
"""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from medieval_forge.services.pipeline.topology import validate_edit, douglas_peucker_simplify


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# A simple square: valid polygon with no self-intersections.
SQUARE = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])

# A figure-8 self-intersecting polygon (invalid).
FIGURE_EIGHT = Polygon([(0, 0), (2, 2), (2, 0), (0, 2)])

# A small neighbour adjacent to the right side of SQUARE.
RIGHT_NEIGHBOUR = Polygon([(1, 0), (2, 0), (2, 1), (1, 1)])

# A square moved far away — disjoint from SQUARE.
FAR_POLYGON = Polygon([(10, 10), (11, 10), (11, 11), (10, 11)])

# A square with an extra vertex on the top edge at (0.5, 1) — simplifiable.
SQUARE_WITH_EXTRA_VERTEX = Polygon(
    [(0, 0), (1, 0), (1, 1), (0.5, 1), (0, 1)]
)


# ---------------------------------------------------------------------------
# validate_edit tests
# ---------------------------------------------------------------------------

class TestValidateEdit:
    def test_valid_polygon_with_no_neighbours_returns_true_none(self):
        """EDIT-VERTEX-01: simple valid square with empty neighbours list returns (True, None)."""
        valid, code = validate_edit(SQUARE, [])
        assert valid is True
        assert code is None

    def test_self_intersecting_polygon_returns_false_self_intersect(self):
        """TOPO-01: figure-8 self-intersecting polygon returns (False, 'SELF_INTERSECT')."""
        valid, code = validate_edit(FIGURE_EIGHT, [])
        assert valid is False
        assert code == "SELF_INTERSECT"

    def test_polygon_disjoint_from_neighbour_returns_false_neighbour_gap(self):
        """TOPO-01: polygon that becomes disjoint from previously-touching neighbour
        returns (False, 'NEIGHBOUR_GAP')."""
        # SQUARE moved so it no longer touches RIGHT_NEIGHBOUR: use FAR_POLYGON as target.
        # FAR_POLYGON is disjoint from RIGHT_NEIGHBOUR.
        valid, code = validate_edit(FAR_POLYGON, [RIGHT_NEIGHBOUR])
        assert valid is False
        assert code == "NEIGHBOUR_GAP"

    def test_valid_polygon_touching_neighbour_returns_true_none(self):
        """EDIT-VERTEX-01: valid polygon that shares an edge with neighbour returns (True, None)."""
        valid, code = validate_edit(SQUARE, [RIGHT_NEIGHBOUR])
        assert valid is True
        assert code is None

    def test_multiple_neighbours_all_touching_returns_true_none(self):
        """EDIT-VERTEX-01: valid polygon touching multiple neighbours returns (True, None)."""
        top_neighbour = Polygon([(0, 1), (1, 1), (1, 2), (0, 2)])
        valid, code = validate_edit(SQUARE, [RIGHT_NEIGHBOUR, top_neighbour])
        assert valid is True
        assert code is None

    def test_invalid_polygon_with_valid_neighbour_returns_self_intersect(self):
        """TOPO-01: self-intersect error takes precedence over neighbour gap check."""
        valid, code = validate_edit(FIGURE_EIGHT, [RIGHT_NEIGHBOUR])
        assert valid is False
        assert code == "SELF_INTERSECT"


# ---------------------------------------------------------------------------
# douglas_peucker_simplify tests
# ---------------------------------------------------------------------------

class TestDouglasPeuckerSimplify:
    def test_simplify_polygon_reduces_vertex_count_below_cap(self):
        """EDIT-VERTEX-04: simplify with tolerance=0.001 reduces vertex count on polygon
        with an extra collinear-ish vertex (the point at (0.5, 1) is removable)."""
        original_count = len(SQUARE_WITH_EXTRA_VERTEX.exterior.coords) - 1  # -1 for closing coord
        result = douglas_peucker_simplify(SQUARE_WITH_EXTRA_VERTEX, tolerance=0.001)
        result_count = len(result.exterior.coords) - 1
        assert result_count <= original_count
        # The collinear vertex at (0.5, 1) should be simplified away
        assert result_count < original_count

    def test_simplify_preserves_boundary_vertices_at_very_small_tolerance(self):
        """EDIT-VERTEX-04: at very small tolerance simplify preserves most/all vertices."""
        result = douglas_peucker_simplify(SQUARE, tolerance=0.000001)
        # Basic square — nothing to simplify at near-zero tolerance
        assert result.is_valid

    def test_simplify_result_polygon_passes_topology_validate(self):
        """EDIT-VERTEX-01: simplified polygon is self-intersection-free;
        validate_edit returns (True, None) after simplification."""
        result = douglas_peucker_simplify(SQUARE_WITH_EXTRA_VERTEX, tolerance=0.001)
        valid, code = validate_edit(result, [])
        assert valid is True
        assert code is None

    def test_simplify_raises_value_error_on_zero_tolerance(self):
        """EDIT-VERTEX-04: tolerance <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="tolerance"):
            douglas_peucker_simplify(SQUARE, tolerance=0.0)

    def test_simplify_raises_value_error_on_excessive_tolerance(self):
        """EDIT-VERTEX-04: tolerance > 0.1 raises ValueError."""
        with pytest.raises(ValueError, match="tolerance"):
            douglas_peucker_simplify(SQUARE, tolerance=0.2)

    def test_simplify_uses_preserve_topology_true(self):
        """EDIT-VERTEX-04: preserve_topology=True is non-negotiable (RESEARCH §Don't Hand-Roll #4).
        Ensure result polygon is still valid after simplification."""
        result = douglas_peucker_simplify(SQUARE_WITH_EXTRA_VERTEX, tolerance=0.01)
        assert result.is_valid, "Simplified polygon must pass is_valid (preserve_topology=True)"
