"""Phase 08 Plan 07 — unit tests for replay_merge in manual_edit.py.

Covers REQ-IDs: EDIT-POLYGON-02, D-08, D-09
All fixtures are explicit numeric polygons (user feedback memory — descriptive names
+ explicit numeric fixtures).
"""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon


# ---------------------------------------------------------------------------
# Fixtures — explicit numeric (user feedback memory)
# ---------------------------------------------------------------------------

# Left unit square: (0,0)→(1,0)→(1,1)→(0,1)
LEFT_SQUARE = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])

# Right unit square: shares edge x=1 with LEFT_SQUARE
RIGHT_SQUARE = Polygon([(1, 0), (2, 0), (2, 1), (1, 1)])

# Top square: shares edge y=1 with LEFT_SQUARE
TOP_SQUARE = Polygon([(0, 1), (1, 1), (1, 2), (0, 2)])

# Far-away square: NOT adjacent to LEFT_SQUARE (gap between them)
FAR_SQUARE = Polygon([(5, 5), (6, 5), (6, 6), (5, 6)])

# Square in a different "condado" region — same geometry as RIGHT_SQUARE
# (D-09: cross-condado merge is allowed — adjacency is the only constraint)
CROSS_CONDADO_SQUARE = Polygon([(1, 0), (2, 0), (2, 1), (1, 1)])


# ---------------------------------------------------------------------------
# Tests for replay_merge (pure function — no DB)
# ---------------------------------------------------------------------------

class TestReplayMergeAdjacentSquares:
    """EDIT-POLYGON-02: replay_merge(adjacent_a, adjacent_b) → single rectangle."""

    def test_adjacent_squares_produce_single_polygon(self):
        """replay_merge(left_square, right_square) → 1 Polygon (not MultiPolygon)."""
        from medieval_forge.services.pipeline.manual_edit import replay_merge

        result = replay_merge(LEFT_SQUARE, RIGHT_SQUARE)
        assert isinstance(result, Polygon)

    def test_merged_area_equals_sum_of_inputs(self):
        """Merged area = 1.0 + 1.0 = 2.0 for two unit squares."""
        from medieval_forge.services.pipeline.manual_edit import replay_merge

        result = replay_merge(LEFT_SQUARE, RIGHT_SQUARE)
        assert abs(result.area - 2.0) < 1e-10

    def test_merged_result_is_rectangle_two_by_one(self):
        """Union of two 1×1 squares side-by-side = 2×1 rectangle; bounds check."""
        from medieval_forge.services.pipeline.manual_edit import replay_merge

        result = replay_merge(LEFT_SQUARE, RIGHT_SQUARE)
        minx, miny, maxx, maxy = result.bounds
        assert abs(minx - 0.0) < 1e-10
        assert abs(maxx - 2.0) < 1e-10
        assert abs(miny - 0.0) < 1e-10
        assert abs(maxy - 1.0) < 1e-10

    def test_merged_result_has_no_holes(self):
        """Merged rectangle has no interior rings."""
        from medieval_forge.services.pipeline.manual_edit import replay_merge

        result = replay_merge(LEFT_SQUARE, RIGHT_SQUARE)
        assert len(result.interiors) == 0

    def test_merge_is_commutative(self):
        """replay_merge(a, b) area equals replay_merge(b, a) area."""
        from medieval_forge.services.pipeline.manual_edit import replay_merge

        result_ab = replay_merge(LEFT_SQUARE, RIGHT_SQUARE)
        result_ba = replay_merge(RIGHT_SQUARE, LEFT_SQUARE)
        assert abs(result_ab.area - result_ba.area) < 1e-10

    def test_top_adjacent_square_merges_to_two_by_one_tall(self):
        """LEFT_SQUARE + TOP_SQUARE (shared edge y=1) → 1×2 tall rectangle."""
        from medieval_forge.services.pipeline.manual_edit import replay_merge

        result = replay_merge(LEFT_SQUARE, TOP_SQUARE)
        assert isinstance(result, Polygon)
        assert abs(result.area - 2.0) < 1e-10


class TestReplayMergeNonAdjacent:
    """EDIT-POLYGON-02 Pitfall 2: non-adjacent merge raises ValueError NOT_ADJACENT."""

    def test_non_adjacent_squares_raise_NOT_ADJACENT(self):
        """replay_merge(left_square, far_square) → ValueError with 'NOT_ADJACENT'."""
        from medieval_forge.services.pipeline.manual_edit import replay_merge

        with pytest.raises(ValueError, match="NOT_ADJACENT"):
            replay_merge(LEFT_SQUARE, FAR_SQUARE)

    def test_non_adjacent_merge_error_message_includes_NOT_ADJACENT_code(self):
        """Exact error code 'NOT_ADJACENT' present in exception message for easy HTTP mapping."""
        from medieval_forge.services.pipeline.manual_edit import replay_merge

        try:
            replay_merge(LEFT_SQUARE, FAR_SQUARE)
            pytest.fail("Expected ValueError was not raised")
        except ValueError as exc:
            assert "NOT_ADJACENT" in str(exc)


class TestReplayMergeCrossCondado:
    """D-09: cross-condado merge is allowed — only adjacency matters."""

    def test_cross_condado_adjacent_merge_is_allowed(self):
        """D-09: two adjacent polygons from different condados merge successfully.
        LEFT_SQUARE and CROSS_CONDADO_SQUARE share edge x=1 — merge must succeed."""
        from medieval_forge.services.pipeline.manual_edit import replay_merge

        # CROSS_CONDADO_SQUARE is geometrically identical to RIGHT_SQUARE
        # (would be from a different condado in the territory hierarchy)
        result = replay_merge(LEFT_SQUARE, CROSS_CONDADO_SQUARE)
        assert isinstance(result, Polygon)
        assert abs(result.area - 2.0) < 1e-10
