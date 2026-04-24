"""
Wave 0 RED test scaffolds for backend/medieval_forge/services/voronoi.py.

These tests FAIL at collection time because the voronoi module does not
exist yet. That is the expected RED state. Implementations come in P02.

All geometric fixtures use simple shapes (unit squares, triangles) so the
tests are deterministic and fast (<100ms each when green).
"""
import json
import pathlib
import time

import pytest

# This import will raise ModuleNotFoundError (RED) until P02 creates voronoi.py
from medieval_forge.services.voronoi import (  # noqa: E402
    build_adjacency,
    find_affected_neighbors,
    recalc_neighbors,
    merge_territories,
    split_territory,
    decimate_polygon,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _repo_root() -> pathlib.Path:
    p = pathlib.Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "backend").is_dir() and (parent / "frontend").is_dir():
            return parent
    raise RuntimeError("Cannot locate repo root")


def _iberia_json() -> dict:
    """Load the real Iberia territory fixture for performance tests."""
    json_path = _repo_root() / "backend" / "medieval_forge" / "services" / "territory_iberia.json"
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


# 3 seed points forming a triangle in a bounded box
TRIANGLE_SEEDS = [
    (0.5, 0.9),   # top-center
    (0.1, 0.1),   # bottom-left
    (0.9, 0.1),   # bottom-right
]

# Two adjacent unit squares sharing edge x=1
SQUARE_A = {
    "type": "Polygon",
    "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
}
SQUARE_B = {
    "type": "Polygon",
    "coordinates": [[[1.0, 0.0], [2.0, 0.0], [2.0, 1.0], [1.0, 1.0], [1.0, 0.0]]],
}

# Two non-adjacent squares (gap between them)
SQUARE_C = {
    "type": "Polygon",
    "coordinates": [[[5.0, 0.0], [6.0, 0.0], [6.0, 1.0], [5.0, 1.0], [5.0, 0.0]]],
}

# Unit square for split tests
UNIT_SQUARE = {
    "type": "Polygon",
    "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
}


# ---------------------------------------------------------------------------
# build_adjacency tests
# ---------------------------------------------------------------------------

def test_build_adjacency_returns_symmetric_neighbor_map():
    """
    Given 3 seed points in a triangle, build_adjacency returns a symmetric map:
    {0: {1, 2}, 1: {0, 2}, 2: {0, 1}}
    """
    adjacency = build_adjacency(TRIANGLE_SEEDS)

    assert 0 in adjacency
    assert 1 in adjacency
    assert 2 in adjacency

    # Symmetric: if A neighbors B then B neighbors A
    for idx, neighbors in adjacency.items():
        for n in neighbors:
            assert idx in adjacency[n], f"Adjacency not symmetric: {idx} -> {n} but not {n} -> {idx}"

    # Triangle: each vertex neighbors both others
    assert adjacency[0] == {1, 2}
    assert adjacency[1] == {0, 2}
    assert adjacency[2] == {0, 1}


def test_adjacency_rebuilt_after_merge():
    """
    After removing a seed (simulating a merge), build_adjacency on the
    remaining seeds produces a map with different indices than pre-merge.
    Confirms Pitfall 3: adjacency must be rebuilt, not reused.
    """
    seeds_before = TRIANGLE_SEEDS[:]
    adj_before = build_adjacency(seeds_before)

    # Simulate merge: remove seed at index 0 (top-center)
    seeds_after = seeds_before[1:]
    adj_after = build_adjacency(seeds_after)

    # Remaining 2 seeds should be adjacent to each other (single edge)
    assert len(adj_after) == 2
    assert 0 in adj_after
    assert 1 in adj_after
    assert adj_after[0] == {1}
    assert adj_after[1] == {0}

    # The index set changed — confirms indices cannot be reused from pre-merge map
    assert set(adj_after.keys()) != set(adj_before.keys()) or adj_before != adj_after


# ---------------------------------------------------------------------------
# find_affected_neighbors tests
# ---------------------------------------------------------------------------

def test_find_affected_neighbors_returns_moved_plus_ridge_neighbors():
    """
    find_affected_neighbors(moved_idx, adjacency) returns the moved condado's
    own index PLUS all its Voronoi neighbors from the adjacency map.
    """
    adjacency = {0: {1, 2}, 1: {0, 2}, 2: {0, 1}}
    affected = find_affected_neighbors(0, adjacency)

    # Must include the moved condado itself
    assert 0 in affected
    # Must include all ridge-sharing neighbors
    assert 1 in affected
    assert 2 in affected
    assert len(affected) == 3


# ---------------------------------------------------------------------------
# recalc_neighbors tests
# ---------------------------------------------------------------------------

def test_recalc_neighbors_returns_updated_geometries_within_500ms():
    """
    Performance contract (EDIT-01): recalc for a moved capital on the real
    Iberia fixture must complete in <500ms.

    Loads territory_iberia.json (real data), picks the first condado,
    moves its capital 0.1° east, and asserts:
    1. Result contains updated_territories dict with at least 1 entry
    2. affected_ids is a non-empty list
    3. Elapsed time < 500ms
    """
    iberia = _iberia_json()
    condados = iberia["condados"]
    first_condado = condados[0]
    condado_id = first_condado["id"]
    original_lon = first_condado["lon"]
    original_lat = first_condado["lat"]

    start = time.perf_counter()
    result = recalc_neighbors(
        condado_id=condado_id,
        new_lon=original_lon + 0.1,
        new_lat=original_lat,
        territory_data=iberia,
    )
    elapsed = time.perf_counter() - start

    assert "updated_territories" in result, "Result must contain updated_territories"
    assert "affected_ids" in result, "Result must contain affected_ids"
    assert len(result["updated_territories"]) >= 1, "At least the moved condado must be updated"
    assert len(result["affected_ids"]) >= 1, "At least the moved condado must be in affected_ids"
    assert elapsed < 0.5, f"recalc_neighbors took {elapsed:.3f}s — must be <500ms (EDIT-01)"


# ---------------------------------------------------------------------------
# merge tests
# ---------------------------------------------------------------------------

def test_merge_unary_union_produces_valid_polygon_from_2_adjacent():
    """
    Merging 2 adjacent unit squares produces a single valid polygon with
    combined area ≈ 2.0.
    """
    result = merge_territories(
        geometries=[SQUARE_A, SQUARE_B],
        primary_id="a",
        condado_ids=["a", "b"],
    )

    assert result["warning"] is None, "Adjacent merge should not trigger warning"
    merged = result["merged_territory"]
    assert merged["type"] == "Polygon", f"Expected Polygon, got {merged['type']}"

    # Verify combined area using shapely
    from shapely.geometry import shape
    geom = shape(merged)
    assert geom.is_valid, "Merged polygon must be valid"
    assert abs(geom.area - 2.0) < 1e-6, f"Expected area ≈ 2.0, got {geom.area}"


def test_merge_non_adjacent_returns_multipolygon_flagged_warning():
    """
    Merging non-adjacent polygons produces a MultiPolygon and sets
    warning='non_adjacent_multipolygon' (D-03: non-adjacent merge allowed but flagged).
    """
    result = merge_territories(
        geometries=[SQUARE_A, SQUARE_C],
        primary_id="a",
        condado_ids=["a", "c"],
    )

    assert result["warning"] == "non_adjacent_multipolygon", (
        f"Expected non_adjacent_multipolygon warning, got {result['warning']!r}"
    )
    merged = result["merged_territory"]
    assert merged["type"] == "MultiPolygon", (
        f"Non-adjacent merge must produce MultiPolygon, got {merged['type']}"
    )


# ---------------------------------------------------------------------------
# split tests
# ---------------------------------------------------------------------------

def test_split_valid_line_returns_two_polygons():
    """
    Splitting a unit square by horizontal line y=0.5 returns 2 polygons
    with combined area ≈ 1.0.
    """
    cut_line = [[-0.1, 0.5], [1.1, 0.5]]  # extends slightly outside to ensure 2 crossings

    result = split_territory(
        geometry=UNIT_SQUARE,
        cut_line=cut_line,
        original_id="unit",
    )

    assert result["original_id"] == "unit"
    poly_a = result["new_territory_a"]
    poly_b = result["new_territory_b"]

    from shapely.geometry import shape
    geom_a = shape(poly_a["geometry"])
    geom_b = shape(poly_b["geometry"])

    assert geom_a.is_valid, "Territory A must be a valid polygon"
    assert geom_b.is_valid, "Territory B must be a valid polygon"
    assert abs(geom_a.area + geom_b.area - 1.0) < 1e-6, (
        f"Combined area should be 1.0, got {geom_a.area + geom_b.area}"
    )


def test_split_non_bisecting_line_raises_valueerror():
    """
    CRITICAL — Pitfall 4: a cut line that does not cross the polygon
    boundary at exactly 2 points must raise ValueError, NOT silently succeed.

    Uses a line that only touches one corner (0 interior crossings).
    """
    non_bisecting_line = [[0.5, 1.5], [1.5, 0.5]]  # outside the unit square entirely

    with pytest.raises(ValueError, match=r"(?i)bisect|cross|intersect|split"):
        split_territory(
            geometry=UNIT_SQUARE,
            cut_line=non_bisecting_line,
            original_id="unit",
        )


# ---------------------------------------------------------------------------
# decimate tests
# ---------------------------------------------------------------------------

def test_decimate_polygon_returns_at_most_15_vertices():
    """
    Given a 50-vertex circle approximation, decimate_polygon(poly, target_vertices=12)
    returns a polygon with ≤ 15 exterior ring coordinates (12 ± 3 tolerance).

    Uses a regular 50-gon as a proxy for a Voronoi cell.
    """
    import math

    coords = [
        (0.5 + 0.4 * math.cos(2 * math.pi * i / 50),
         0.5 + 0.4 * math.sin(2 * math.pi * i / 50))
        for i in range(50)
    ]
    coords.append(coords[0])  # close ring

    polygon_50 = {
        "type": "Polygon",
        "coordinates": [coords],
    }

    result = decimate_polygon(polygon_50, target_vertices=12)

    exterior_coords = result["coordinates"][0]
    # Last coord repeats first (closed ring); count unique vertices
    unique_vertices = len(exterior_coords) - 1
    assert unique_vertices <= 15, (
        f"Expected ≤15 vertices after decimation, got {unique_vertices}"
    )
    assert unique_vertices >= 3, "Polygon must have at least 3 vertices"

    # Result must still be a valid polygon
    from shapely.geometry import shape
    geom = shape(result)
    assert geom.is_valid, "Decimated polygon must be valid"
