"""Phase 08 D-26 + D-01: topology validation + Douglas-Peucker simplify.

D-26: validate_edit — blocking errors: self-intersect + neighbour gap.
D-01: douglas_peucker_simplify — preserve_topology=True is non-negotiable
      (RESEARCH §Don't Hand-Roll #4).
"""
from __future__ import annotations

from shapely.geometry import Polygon


def validate_edit(
    target: Polygon,
    neighbours: list[Polygon],
) -> tuple[bool, str | None]:
    """D-26: returns (valid, error_code) for a single barony post-edit.

    Blocking errors (checked in priority order):
      - target is invalid (self-intersection): 'SELF_INTERSECT'
      - target is disjoint from a previously-touching neighbour: 'NEIGHBOUR_GAP'

    Args:
        target: The edited polygon to validate.
        neighbours: Adjacent polygons that the target should still touch after the edit.

    Returns:
        Tuple of (is_valid, error_code). error_code is None when valid.
    """
    if not target.is_valid:
        return False, "SELF_INTERSECT"
    for n in neighbours:
        # Neighbour must still share an edge (touches) or overlap — disjoint = gap
        if target.disjoint(n):
            return False, "NEIGHBOUR_GAP"
    return True, None


def douglas_peucker_simplify(target: Polygon, tolerance: float) -> Polygon:
    """D-01: Douglas-Peucker simplify with preserve_topology=True.

    Uses shapely.simplify(preserve_topology=True) — preserve_topology=True is
    non-negotiable to avoid breaking shared edges with neighbours
    (RESEARCH §Don't Hand-Roll #4).

    Args:
        target: The polygon to simplify.
        tolerance: Simplification tolerance in coordinate units. Must be in (0, 0.1].
                   UI slider range is 0.00001–0.01; backend accepts up to 0.1 as buffer.

    Returns:
        Simplified Polygon.

    Raises:
        ValueError: If tolerance is out of valid range.
    """
    if tolerance <= 0 or tolerance > 0.1:
        raise ValueError(
            f"tolerance must be in (0, 0.1]; got {tolerance!r}. "
            "UI slider range is 0.00001–0.01."
        )
    return target.simplify(tolerance, preserve_topology=True)
