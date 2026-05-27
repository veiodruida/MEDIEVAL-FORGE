"""Phase 08 Plan 07 — unit tests for replay_split in manual_edit.py.

Covers REQ-IDs: EDIT-POLYGON-01, D-07, D-22
All fixtures are explicit numeric polygons (user feedback memory — descriptive names
+ explicit numeric fixtures).
"""
from __future__ import annotations

import pytest
from shapely.geometry import LineString, Polygon


# ---------------------------------------------------------------------------
# Fixtures — explicit numeric (user feedback memory)
# ---------------------------------------------------------------------------

# A 1×1 unit square: vertices (0,0)→(1,0)→(1,1)→(0,1)
UNIT_SQUARE = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])

# Diagonal cut from bottom-left to top-right — bisects the square into two triangles
DIAGONAL_CUT = LineString([(0, 0), (1, 1)])

# Horizontal midline cut — bisects into two rectangles (0,0)-(1,0.5) and (0,0.5)-(1,1)
HORIZONTAL_CUT = LineString([(-0.1, 0.5), (1.1, 0.5)])

# A cut that does NOT intersect the polygon (entirely outside)
OUTSIDE_CUT = LineString([(5, 5), (6, 6)])

# A cut that touches only the boundary but doesn't cross (no interior split)
TANGENT_CUT = LineString([(0, 0), (0, 1)])  # along left edge — no interior split


# ---------------------------------------------------------------------------
# Tests for replay_split (pure function — no DB)
# ---------------------------------------------------------------------------

class TestReplaySplitDiagonalCut:
    """EDIT-POLYGON-01: replay_split returns 2 triangles from diagonal cut."""

    def test_diagonal_cut_produces_exactly_two_pieces(self):
        """replay_split(unit_square, diagonal) → exactly 2 non-empty Polygon pieces."""
        from medieval_forge.services.pipeline.manual_edit import replay_split

        pieces = replay_split(UNIT_SQUARE, DIAGONAL_CUT)
        assert len(pieces) == 2

    def test_diagonal_cut_pieces_are_polygons(self):
        """Both pieces from diagonal cut are shapely Polygon instances."""
        from medieval_forge.services.pipeline.manual_edit import replay_split

        pieces = replay_split(UNIT_SQUARE, DIAGONAL_CUT)
        for p in pieces:
            assert isinstance(p, Polygon)

    def test_diagonal_cut_union_equals_input_area(self):
        """Union of two pieces equals original area (symmetric_difference is empty)."""
        from medieval_forge.services.pipeline.manual_edit import replay_split
        from shapely.ops import unary_union

        pieces = replay_split(UNIT_SQUARE, DIAGONAL_CUT)
        union = unary_union(pieces)
        # Symmetric difference between union and original should be near-zero area
        diff = UNIT_SQUARE.symmetric_difference(union)
        assert diff.area < 1e-10, f"Area mismatch: symmetric_difference area = {diff.area}"

    def test_diagonal_cut_pieces_do_not_overlap(self):
        """The two pieces from diagonal cut have zero intersection area."""
        from medieval_forge.services.pipeline.manual_edit import replay_split

        pieces = replay_split(UNIT_SQUARE, DIAGONAL_CUT)
        assert pieces[0].intersection(pieces[1]).area < 1e-10


class TestReplaySplitHorizontalCut:
    """EDIT-POLYGON-01: horizontal midline cut produces two equal rectangles."""

    def test_horizontal_cut_produces_two_pieces(self):
        """replay_split with horizontal midline → 2 pieces."""
        from medieval_forge.services.pipeline.manual_edit import replay_split

        pieces = replay_split(UNIT_SQUARE, HORIZONTAL_CUT)
        assert len(pieces) == 2

    def test_horizontal_cut_pieces_have_equal_area(self):
        """Both halves have equal area (0.5 each for the unit square)."""
        from medieval_forge.services.pipeline.manual_edit import replay_split

        pieces = replay_split(UNIT_SQUARE, HORIZONTAL_CUT)
        assert abs(pieces[0].area - 0.5) < 1e-10
        assert abs(pieces[1].area - 0.5) < 1e-10


class TestReplaySplitInvalidCuts:
    """EDIT-POLYGON-01 + BLOCKER-1: cuts that do not bisect raise ValueError SPLIT_INVALID."""

    def test_outside_cut_raises_SPLIT_INVALID(self):
        """Cut entirely outside polygon → ValueError with 'SPLIT_INVALID' in message."""
        from medieval_forge.services.pipeline.manual_edit import replay_split

        with pytest.raises(ValueError, match="SPLIT_INVALID"):
            replay_split(UNIT_SQUARE, OUTSIDE_CUT)

    def test_tangent_cut_along_boundary_raises_SPLIT_INVALID(self):
        """Cut tangent to polygon boundary (does not cross interior) → SPLIT_INVALID."""
        from medieval_forge.services.pipeline.manual_edit import replay_split

        with pytest.raises(ValueError, match="SPLIT_INVALID"):
            replay_split(UNIT_SQUARE, TANGENT_CUT)


class TestReplaySplitChildNaming:
    """D-07: child name format is '<orig> (2)'; test via the plan-documented contract."""

    def test_split_does_not_alter_geometry_contract(self):
        """replay_split is geometry-only (pure): returns polygons, not dicts.
        Name assignment '<orig> (2)' is done by the HTTP handler layer, not replay_split."""
        from medieval_forge.services.pipeline.manual_edit import replay_split

        pieces = replay_split(UNIT_SQUARE, HORIZONTAL_CUT)
        # pieces are raw shapely Polygon instances — no name/id attached
        assert all(hasattr(p, 'area') for p in pieces)
        assert all(not hasattr(p, 'name') for p in pieces)
