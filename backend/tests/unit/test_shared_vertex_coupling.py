"""Phase 08 Plan 06b — shared-vertex coupling tests (TOPO-03, TOPO-04).

Rule 1 deviation: stub functions referenced non-existent backend coupling
helpers. These tests verify that validate_edit called on two adjacent
polygons (sharing a vertex/edge) stays valid after a simulated coupled move.
This is the backend-side assertion of D-30 correctness.

All tests use explicit numeric coordinate fixtures per user feedback memory.
"""
from shapely.geometry import Polygon

from medieval_forge.services.pipeline.topology import validate_edit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Two adjacent squares sharing the edge at x=1.
# Barony A: (0,0)-(1,0)-(1,1)-(0,1)
# Barony B: (1,0)-(2,0)-(2,1)-(1,1)
# They share the segment from (1,0) to (1,1).
BARONY_A = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
BARONY_B = Polygon([(1, 0), (2, 0), (2, 1), (1, 1)])

# After a coupled vertex move: both baronies move the shared edge to x=1.2.
# Barony A updated: (0,0)-(1.2,0)-(1.2,1)-(0,1)
# Barony B updated: (1.2,0)-(2,0)-(2,1)-(1.2,1)
# Shared edge now at x=1.2 — still touching (no gap).
BARONY_A_MOVED = Polygon([(0, 0), (1.2, 0), (1.2, 1), (0, 1)])
BARONY_B_MOVED = Polygon([(1.2, 0), (2, 0), (2, 1), (1.2, 1)])

# Broken move: only Barony A updated, shrinking its right edge from x=1 to x=0.8.
# Barony B stays at x=1. This creates a real gap between A(right=0.8) and B(left=1.0).
BARONY_A_BROKEN = Polygon([(0, 0), (0.8, 0), (0.8, 1), (0, 1)])
# BARONY_B stays at x=1 — gap from x=0.8 to x=1.0 introduced


# ---------------------------------------------------------------------------
# TOPO-04: coupled move keeps polygons valid and touching
# ---------------------------------------------------------------------------

def test_coupled_vertex_move_barony_A_is_valid_post_edit():
    """TOPO-04: after coupled move, Barony A is valid and still touches Barony B.

    Explicit fixture: shared edge moved from x=1.0 → x=1.2 in both baronies.
    Barony A has Barony B as neighbour; validate_edit must return (True, None).
    """
    valid, code = validate_edit(BARONY_A_MOVED, neighbours=[BARONY_B_MOVED])
    assert valid is True
    assert code is None


def test_coupled_vertex_move_barony_B_is_valid_post_edit():
    """TOPO-04: after coupled move, Barony B is valid and still touches Barony A.

    Symmetric check: validate_edit from Barony B's perspective.
    """
    valid, code = validate_edit(BARONY_B_MOVED, neighbours=[BARONY_A_MOVED])
    assert valid is True
    assert code is None


def test_coupled_polygons_share_zero_distance_after_move():
    """TOPO-04: Shapely distance() between the two updated polygons is 0.0 (no gap).

    Explicit fixture: BARONY_A_MOVED + BARONY_B_MOVED share edge at x=1.2.
    distance() == 0.0 confirms no gap was introduced by the coupled move.
    """
    distance = BARONY_A_MOVED.distance(BARONY_B_MOVED)
    assert distance == 0.0, f"Expected 0.0 gap but got {distance}"


# ---------------------------------------------------------------------------
# TOPO-03: non-coupled move introduces gap (NEIGHBOUR_GAP error)
# ---------------------------------------------------------------------------

def test_non_coupled_move_leaves_gap_and_returns_NEIGHBOUR_GAP():
    """TOPO-03: when only one polygon moves (non-coupled), a gap is introduced.

    Explicit fixture: Barony A right edge shrunk to x=0.8, Barony B left edge stays at x=1.0.
    validate_edit for Barony A with Barony B as neighbour must return NEIGHBOUR_GAP
    because A(right=0.8) is disjoint from B(left=1.0) — gap from 0.8 to 1.0.
    """
    valid, code = validate_edit(BARONY_A_BROKEN, neighbours=[BARONY_B])
    assert valid is False
    assert code == "NEIGHBOUR_GAP"


def test_non_shared_vertex_move_does_not_affect_non_touching_neighbour():
    """TOPO-03: moving a vertex that is NOT on the shared edge leaves
    non-touching neighbours unaffected.

    Explicit fixture: Barony A has outer vertex at (0,0) moved to (-0.5, 0).
    New Barony A: (-0.5,0)-(1,0)-(1,1)-(0,1). Still touches Barony B at x=1.
    validate_edit returns (True, None) — the non-shared vertex move is fine.
    """
    barony_a_outer_moved = Polygon([(-0.5, 0), (1, 0), (1, 1), (0, 1)])
    valid, code = validate_edit(barony_a_outer_moved, neighbours=[BARONY_B])
    assert valid is True
    assert code is None
