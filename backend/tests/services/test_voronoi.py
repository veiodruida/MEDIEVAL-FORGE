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

def _grid_territory_data(seeds: list[tuple[float, float]]) -> dict:
    """Wrap seed tuples into the territory_data shape recalc_neighbors expects.

    Each condado list = [id, name, lon, lat, duchy_id, baronies] — matches
    the on-disk territory_iberia.json format.  IDs are deterministic strings
    so tests can reference them.
    """
    return {
        "condados": [
            [f"c{i}", f"name{i}", lon, lat, "d0", []]
            for i, (lon, lat) in enumerate(seeds)
        ]
    }


def test_recalc_neighbors_no_clip_backwards_compat():
    """Test A (qlo): without land_mask/bbox, behavior matches the legacy
    code path — unbounded edge cells are silently skipped, only bounded cells
    appear in the result.  Guards backwards compatibility for any caller
    that still invokes recalc_neighbors with the original 4-arg signature.
    """
    seeds = [(2.0, 2.0), (8.0, 2.0), (2.0, 8.0), (8.0, 8.0)]
    td = _grid_territory_data(seeds)
    result = recalc_neighbors("c0", 2.0, 2.0, td)
    # All 4 cells of a 2x2 grid are unbounded (corner seeds) — the legacy
    # code path skips them all.  This is the documented historic behavior.
    assert result["updated_territories"] == {}, (
        "Without clip geom, all-corner seeds yield only unbounded cells which "
        "the legacy path skips."
    )
    # Legacy behavior: affected_ids reflects affected_indices (NOT survivors)
    # when no clipping is in effect — preserves backwards-compat with callers
    # that relied on this for highlighting / progress UI.
    assert set(result["affected_ids"]) == {"c0", "c1", "c2"}


def test_recalc_neighbors_clips_to_bbox():
    """Test B (qlo): with bbox supplied, every returned polygon's exterior
    coordinates lie within the bbox, AND previously-unbounded edge cells are
    now bounded (and present in the result).
    """
    from shapely.geometry import shape as _shape
    # 4 seeds near the corners of a (0,0)-(10,10) bbox — all are normally
    # unbounded but clipping by the bbox makes them all finite squares.
    seeds = [(2.0, 2.0), (8.0, 2.0), (2.0, 8.0), (8.0, 8.0)]
    td = _grid_territory_data(seeds)
    result = recalc_neighbors(
        "c0", 2.0, 2.0, td,
        bbox=(0.0, 0.0, 10.0, 10.0),
    )
    assert len(result["updated_territories"]) >= 1, (
        "Bbox clip must rescue at least one previously-unbounded cell."
    )
    # The moved cell c0 must specifically appear (it is in affected_indices).
    assert "c0" in result["updated_territories"], (
        "Moved cell must be in updated_territories after bbox clip."
    )
    for cid, geom in result["updated_territories"].items():
        poly = _shape(geom)
        for x, y in poly.exterior.coords:
            assert -1e-9 <= x <= 10.0 + 1e-9, f"{cid}: lon {x} outside bbox"
            assert -1e-9 <= y <= 10.0 + 1e-9, f"{cid}: lat {y} outside bbox"


def test_recalc_neighbors_clips_to_land_mask():
    """Test C (qlo): land_mask = left half of a 10x10 bbox (a vertical
    coastline at x=5).  A seed near x=4.5 produces a polygon entirely
    contained within the land mask.
    """
    from shapely.geometry import Polygon as _Polygon, shape as _shape
    from shapely import contains as _contains
    land_mask = _Polygon([(0, 0), (5, 0), (5, 10), (0, 10), (0, 0)])
    # Place the moved seed deep inside the left half so its Voronoi cell
    # naturally extends across x=5 and gets clipped.
    seeds = [(4.5, 5.0), (8.0, 2.0), (8.0, 8.0), (1.0, 1.0), (1.0, 9.0)]
    td = _grid_territory_data(seeds)
    result = recalc_neighbors(
        "c0", 4.5, 5.0, td,
        land_mask=land_mask,
    )
    assert "c0" in result["updated_territories"], (
        "Moved cell c0 must be in updated_territories after land mask clip."
    )
    moved_geom = _shape(result["updated_territories"]["c0"])
    # Tight contains tolerance via tiny buffer (numerical noise from clipping).
    assert _contains(land_mask.buffer(1e-6), moved_geom), (
        f"Moved cell must be contained within land mask; got coords with "
        f"max x={max(x for x, _ in moved_geom.exterior.coords):.6f}"
    )
    # And every coord should be at x <= 5 + 1e-6.
    for x, _y in moved_geom.exterior.coords:
        assert x <= 5.0 + 1e-6, f"coord lon={x} extends past coastline x=5"


def test_recalc_neighbors_drops_cells_fully_outside_land_mask():
    """Test D (qlo): cells whose Voronoi region falls entirely outside the
    land mask must be omitted from BOTH updated_territories AND affected_ids.
    No empty/zero-area geometries returned.
    """
    from shapely.geometry import Polygon as _Polygon
    # Land mask = left half only.  Seeds c1 & c2 sit on the right side
    # (x=8) — their Voronoi cells will be entirely in the ocean half and
    # must be dropped after clipping.
    # Land mask = strictly x <= 4.  c1/c2 sit at x=9 → midpoint with c0
    # is at x ≈ 5.75, so their entire Voronoi cells lie at x >= 5.75 (well
    # outside the land mask) and clipping must drop them.
    land_mask = _Polygon([(0, 0), (4, 0), (4, 10), (0, 10), (0, 0)])
    seeds = [(2.5, 5.0), (9.0, 2.5), (9.0, 7.5), (2.5, 1.0), (2.5, 9.0)]
    td = _grid_territory_data(seeds)
    result = recalc_neighbors(
        "c0", 2.5, 5.0, td,
        land_mask=land_mask,
        bbox=(0.0, 0.0, 10.0, 10.0),  # bbox helps bound c1/c2 before clip
    )
    # c1 and c2 cells live entirely in x > 5 → must be dropped post-clip.
    assert "c1" not in result["updated_territories"], (
        "c1 lives in ocean half — must be dropped."
    )
    assert "c2" not in result["updated_territories"], (
        "c2 lives in ocean half — must be dropped."
    )
    assert "c1" not in result["affected_ids"], (
        "Dropped cells must NOT appear in affected_ids."
    )
    assert "c2" not in result["affected_ids"], (
        "Dropped cells must NOT appear in affected_ids."
    )
    # Sanity: no empty geometries leaked into result.
    from shapely.geometry import shape as _shape
    for cid, geom in result["updated_territories"].items():
        s = _shape(geom)
        assert not s.is_empty, f"{cid} returned an empty geometry"
        assert s.area > 0, f"{cid} returned a zero-area geometry"


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
    # territory_iberia.json stores condados as lists: [id, name, lon, lat, duchy_id, baronies]
    condado_id = first_condado[0]
    original_lon = first_condado[2]
    original_lat = first_condado[3]

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


def test_decimate_polygon_degree_scale_high_vertex_count():
    """
    Contract test for must_haves.truths (260426-qc0): a 287-vertex polygon at
    lon/lat degree scale (Galician condado-sized: center ~(-7.5, 43.0),
    radius ~0.25°) must decimate to approximately the requested 12 handles.

    Note on RED reproduction: the real-world bug on lugo (286/287 vertices
    returned) requires Shapely #2165 to fire across every binary-search probe,
    which is a topology accident specific to the actual coastline coords.
    Synthetic regular/jittered/star/coastal fixtures explored during
    development all converge correctly under the current (buggy) DP search,
    so this test does NOT fail on the pre-fix code. It locks in the
    post-fix behavioral contract from the plan's must_haves.truths instead.
    """
    import math
    from shapely.geometry import shape as _shape

    cx, cy, r = -7.5, 43.0, 0.25
    n_input = 287
    coords = [
        (cx + r * math.cos(2 * math.pi * i / n_input),
         cy + r * math.sin(2 * math.pi * i / n_input))
        for i in range(n_input)
    ]
    coords.append(coords[0])  # close ring

    polygon_287 = {"type": "Polygon", "coordinates": [coords]}

    result = decimate_polygon(polygon_287, target_vertices=12)
    exterior = result["coordinates"][0]
    unique_vertices = len(exterior) - 1

    assert unique_vertices <= 15, (
        f"Expected ≤15 vertices for target=12 on degree-scale polygon, "
        f"got {unique_vertices} (orphan bug #1: DP no-op on lon/lat scale)"
    )
    assert unique_vertices >= 4, (
        f"Decimated polygon must keep ≥4 vertices (endpoint min), got {unique_vertices}"
    )
    assert _shape(result).is_valid, "Decimated polygon must be a valid shapely Polygon"


def test_decimate_polygon_preserves_sharp_corners():
    """
    A "house" polygon (square base + sharp triangular peak on top edge) decimated
    to 10 vertices must keep both the four square corners AND the peak vertex —
    these five points carry the highest turning angles in the ring and are the
    most visually salient handles for an editor.

    Target=10 → k_corners = max(2, 10//2) = 5, exactly matching the five
    high-curvature vertices in the fixture (4 right-angle square corners + 1
    sharp triangular peak). Asserts that the curvature-weighted sampler picks
    all five before falling back to uniform stride for the remaining slots.
    """
    import math
    from shapely.geometry import shape as _shape

    # Square base with extra collinear points on each edge, plus a sharp
    # triangular peak protruding from the top edge.
    base_coords: list[tuple[float, float]] = []
    # bottom edge: (0,0) -> (1,0), 8 pts (corner at (0,0) is index 0)
    for i in range(8):
        base_coords.append((i / 8.0, 0.0))
    # right edge: (1,0) -> (1,1), 8 pts (corner at (1,0) is index 8)
    for i in range(8):
        base_coords.append((1.0, i / 8.0))
    # top edge first half: (1,1) -> (0.5,1) (corner at (1,1) is index 16)
    for i in range(4):
        base_coords.append((1.0 - i * 0.125, 1.0))
    peak = (0.5, 1.5)  # narrow triangular spike
    base_coords.append(peak)  # index 20
    # top edge second half: (0.5,1) -> (0,1)
    for i in range(4):
        base_coords.append((0.5 - i * 0.125, 1.0))
    # left edge: (0,1) -> (0,0), 8 pts (corner at (0,1) is index 25)
    for i in range(8):
        base_coords.append((0.0, 1.0 - i / 8.0))
    base_coords.append(base_coords[0])  # close

    house = {"type": "Polygon", "coordinates": [base_coords]}

    result = decimate_polygon(house, target_vertices=10)
    out_coords = result["coordinates"][0]

    # Peak (highest-y point) must be present in result within tight tolerance.
    min_dist = min(
        math.hypot(x - peak[0], y - peak[1]) for (x, y) in out_coords
    )
    assert min_dist < 1e-6, (
        f"Sharp peak {peak} must be preserved in decimated output; "
        f"closest result vertex was {min_dist:.6f} away. Output: {out_coords}"
    )

    # All four square corners must also survive (they are the highest-
    # curvature vertices in the ring).
    for corner in [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]:
        d = min(math.hypot(x - corner[0], y - corner[1]) for (x, y) in out_coords)
        assert d < 1e-6, (
            f"Square corner {corner} must be preserved; closest was {d:.6f}. "
            f"Output: {out_coords}"
        )
    assert _shape(result).is_valid, "House decimation must produce valid polygon"
