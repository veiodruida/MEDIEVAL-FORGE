"""Phase 08 Plan 06b — topology validation tests (TOPO-01, TOPO-02).

Rule 1 deviation: stub had 'DEGENERATE' blocking code which contradicts D-27
(duplicate vertex is a non-blocking warning, not a blocking error). Replaced
entirely with plan-spec tests per 08-06a precedent (Deviation #3).

Uses validate_edit from topology.py — same function exercised by
test_editor_validate_endpoint.py integration tests, but tested here at unit
level with explicit geometric fixtures (Shapely Polygon objects).
"""
from shapely.geometry import Polygon

from medieval_forge.services.pipeline.topology import validate_edit


# ---------------------------------------------------------------------------
# Fixtures (explicit coordinates per user feedback memory)
# ---------------------------------------------------------------------------

# A simple valid square: (0,0)-(1,0)-(1,1)-(0,1)-(0,0)
SQUARE = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])

# A figure-8 self-intersecting polygon: two triangles crossing at origin
# Ring: (0,0) → (2,1) → (2,-1) → (0,0) → (-1,1) → (-1,-1) → (0,0)
# Using classic bowtie shape: outer ring crosses itself
FIGURE_EIGHT = Polygon([(0, 0), (2, 1), (2, -1), (-2, 1), (-2, -1)])

# Neighbour square: (1,0)-(2,0)-(2,1)-(1,1)-(1,0) — shares right edge with SQUARE
SQUARE_NEIGHBOUR = Polygon([(1, 0), (2, 0), (2, 1), (1, 1)])

# Disjoint square: (5,5)-(6,5)-(6,6)-(5,6) — no shared edge with SQUARE
DISJOINT_SQUARE = Polygon([(5, 5), (6, 5), (6, 6), (5, 6)])


# ---------------------------------------------------------------------------
# TOPO-01: self-intersect blocks (SELF_INTERSECT error code)
# ---------------------------------------------------------------------------

def test_self_intersecting_figure8_polygon_returns_SELF_INTERSECT_code():
    """TOPO-01: figure-8 (bowtie) polygon is not valid in Shapely → SELF_INTERSECT.

    Explicit fixture: bowtie with vertices (0,0),(2,1),(2,-1),(-2,1),(-2,-1)
    produces self-intersection at the crossing point near origin.
    """
    valid, code = validate_edit(FIGURE_EIGHT, neighbours=[])
    assert valid is False
    assert code == "SELF_INTERSECT"


def test_valid_square_with_no_neighbours_returns_True_None():
    """TOPO-01: a well-formed square with no neighbours is valid.

    Explicit fixture: unit square (0,0)-(1,0)-(1,1)-(0,1).
    Expected: (True, None).
    """
    valid, code = validate_edit(SQUARE, neighbours=[])
    assert valid is True
    assert code is None


# ---------------------------------------------------------------------------
# TOPO-01 + TOPO-02: neighbour gap blocks (NEIGHBOUR_GAP error code)
# ---------------------------------------------------------------------------

def test_disjoint_neighbour_after_edit_returns_NEIGHBOUR_GAP_code():
    """TOPO-01/TOPO-02: when a moved polygon is disjoint from a previously-touching
    neighbour, validate_edit returns NEIGHBOUR_GAP.

    Explicit fixture: SQUARE neighbour passed is DISJOINT_SQUARE (5,5)-(6,6)
    — no shared edge or touch → gap introduced.
    """
    valid, code = validate_edit(SQUARE, neighbours=[DISJOINT_SQUARE])
    assert valid is False
    assert code == "NEIGHBOUR_GAP"


def test_touching_neighbour_after_edit_returns_True_None():
    """TOPO-01: square with an adjacent touching neighbour is valid post-edit.

    Explicit fixture: SQUARE + SQUARE_NEIGHBOUR share edge at x=1.
    Shapely: two polygons sharing an edge → NOT disjoint → no NEIGHBOUR_GAP.
    Expected: (True, None).
    """
    valid, code = validate_edit(SQUARE, neighbours=[SQUARE_NEIGHBOUR])
    assert valid is True
    assert code is None


def test_self_intersect_checked_before_neighbour_gap():
    """TOPO-01 priority: self-intersect is checked before neighbour gap.

    When target is invalid (figure-8) AND has a disjoint neighbour, the
    returned code is SELF_INTERSECT (not NEIGHBOUR_GAP). Priority matters
    for frontend error message clarity.
    """
    valid, code = validate_edit(FIGURE_EIGHT, neighbours=[DISJOINT_SQUARE])
    assert valid is False
    assert code == "SELF_INTERSECT"


# ---------------------------------------------------------------------------
# D-27: duplicate vertex / degenerate polygon is NON-BLOCKING (not validate_edit)
# ---------------------------------------------------------------------------

def test_degenerate_near_zero_area_polygon_is_still_valid_in_validate_edit():
    """D-27: duplicate vertex / sliver polygon is a WARNING (amber badge), NOT
    a blocking error in validate_edit. D-27 explicitly states: 'non-blocking'.

    validate_edit only checks SELF_INTERSECT + NEIGHBOUR_GAP.
    A thin sliver polygon with very small area that is still geometrically
    valid (not self-intersecting) should return (True, None).

    Explicit fixture: a very thin rectangle 1e-5 wide × 1.0 tall, area=1e-5.
    """
    sliver = Polygon([(0, 0), (1e-5, 0), (1e-5, 1), (0, 1)])
    # Shapely reports sliver as valid (no self-intersection)
    assert sliver.is_valid
    valid, code = validate_edit(sliver, neighbours=[])
    assert valid is True
    assert code is None
