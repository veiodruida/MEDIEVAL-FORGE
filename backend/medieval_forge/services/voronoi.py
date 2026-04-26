"""
Phase 4 geometry service: Voronoi adjacency + neighbor-only recalc + Shapely ops.
Consumed by api/edit.py. Centralizes all scipy + Shapely dependencies.

All public functions accept and return GeoJSON-dict representations so that
callers (FastAPI endpoints) can work directly with JSON-serialisable data.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np
from scipy.spatial import Voronoi
from shapely import is_valid
from shapely.geometry import (
    LineString,
    MultiPolygon,
    Point,
    Polygon,
    mapping,
    shape,
)
from shapely.ops import orient, split, unary_union

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_shapely(geojson: dict) -> Polygon | MultiPolygon:
    """Convert a GeoJSON geometry dict to a Shapely geometry."""
    return shape(geojson)


def _to_geojson(geom: Polygon | MultiPolygon) -> dict:
    """Convert a Shapely geometry to a GeoJSON geometry dict."""
    return dict(mapping(geom))


# ---------------------------------------------------------------------------
# Voronoi adjacency + neighbor-only recalc
# ---------------------------------------------------------------------------

def build_adjacency(
    points: np.ndarray | list[tuple[float, float]],
) -> dict[int, set[int]]:
    """Build index→neighbor-indices adjacency from Voronoi ridge_points.

    MUST rebuild from scratch after every merge — scipy ridge_points indices
    shift when the seed list shrinks (Pitfall 3; Research §Pattern 5).
    """
    pts = np.asarray(points, dtype=float)
    if len(pts) < 4:
        # scipy needs ≥ 4 points for a valid Voronoi diagram; for fewer, use
        # all-pairs adjacency as a safe fallback.
        return {i: {j for j in range(len(pts)) if j != i} for i in range(len(pts))}
    vor = Voronoi(pts)
    adj: dict[int, set[int]] = {i: set() for i in range(len(pts))}
    for p1, p2 in vor.ridge_points:
        if p1 >= 0 and p2 >= 0:
            adj[int(p1)].add(int(p2))
            adj[int(p2)].add(int(p1))
    return adj


def find_affected_neighbors(
    moved_idx: int,
    adj: dict[int, set[int]],
) -> set[int]:
    """Return {moved_idx} ∪ direct ridge-sharing neighbors. Per D-08 scope."""
    return {moved_idx} | adj.get(moved_idx, set())


def recalc_neighbors(
    condado_id: str,
    new_lon: float,
    new_lat: float,
    territory_data: dict,
) -> dict[str, Any]:
    """Recompute Voronoi for the moved capital and its ridge-sharing neighbors.

    :param condado_id: id string of the condado whose capital was moved.
    :param new_lon: new longitude for the capital.
    :param new_lat: new latitude for the capital.
    :param territory_data: full Iberia fixture dict with "condados" list.
                           Each condado is a list: [id, name, lon, lat, duchy_id, baronies].
    :return: {"updated_territories": {id: geojson_polygon}, "affected_ids": [str, ...]}

    Perf target: <500ms on ~800-seed Iberia dataset. The Voronoi call itself
    is ~50ms; clipping is skipped here (pass land_mask via a future parameter if
    needed). Callers in api/edit.py may apply land-mask clipping on top.
    """
    t0 = time.perf_counter()

    condados = territory_data["condados"]

    # Build seed list and find the moved condado's index.
    # Each condado is [id, name, lon, lat, duchy_id, baronies]
    seeds: list[tuple[float, float]] = []
    id_to_idx: dict[str, int] = {}
    moved_idx: int | None = None

    for i, c in enumerate(condados):
        cid = c[0]
        lon = c[2]
        lat = c[3]
        if cid == condado_id:
            # Use the new position for the moved condado.
            seeds.append((new_lon, new_lat))
            moved_idx = i
        else:
            seeds.append((lon, lat))
        id_to_idx[cid] = i

    if moved_idx is None:
        raise ValueError(f"condado_id {condado_id!r} not found in territory_data")

    pts = np.asarray(seeds, dtype=float)
    adj = build_adjacency(pts)
    affected_indices = find_affected_neighbors(moved_idx, adj)

    # Build a mapping of index → condado_id for the affected subset.
    idx_to_id: dict[int, str] = {v: k for k, v in id_to_idx.items()}

    # Compute Voronoi regions for affected seeds.
    vor = Voronoi(pts)

    updated_territories: dict[str, dict] = {}
    for idx in affected_indices:
        region_idx = vor.point_region[idx]
        region = vor.regions[region_idx]
        if not region or -1 in region:
            # Unbounded cell — skip (real app clips against land mask / bbox).
            continue
        vertices = [vor.vertices[v] for v in region]
        poly = Polygon(vertices)
        if not is_valid(poly):
            poly = poly.buffer(0)  # standard GEOS self-intersection repair
        poly = orient(poly, sign=1.0)  # counter-clockwise exterior
        cid = idx_to_id.get(idx)
        if cid is not None:
            updated_territories[cid] = _to_geojson(poly)

    affected_ids = [idx_to_id[i] for i in affected_indices if i in idx_to_id]

    elapsed = time.perf_counter() - t0
    if elapsed > 0.5:
        logger.warning(
            "recalc_neighbors exceeded 500ms budget: %.3fs for %d seeds, %d affected",
            elapsed,
            len(pts),
            len(affected_indices),
        )

    return {
        "updated_territories": updated_territories,
        "affected_ids": affected_ids,
    }


# ---------------------------------------------------------------------------
# Merge (unary_union)
# ---------------------------------------------------------------------------

def merge_territories(
    geometries: list[dict],
    primary_id: str,
    condado_ids: list[str],
) -> dict[str, Any]:
    """Merge polygons via unary_union. D-03.

    :param geometries: list of GeoJSON geometry dicts (Polygon or MultiPolygon).
    :param primary_id: id of the condado that the merged result inherits.
    :param condado_ids: ordered list matching geometries (first = primary).
    :return: {
        "merged_territory": GeoJSON geometry dict,
        "warning": "non_adjacent_multipolygon" | None,
    }

    Per research §Pattern 6: always call orient(sign=1.0) after union.
    is_valid + buffer(0) repair applied post-union (threat T-04-02-04).
    """
    if len(geometries) < 2:
        raise ValueError("merge_territories requires at least 2 polygons")

    shapely_geoms = [_to_shapely(g) for g in geometries]
    merged = unary_union(shapely_geoms)

    warning: str | None = None
    if isinstance(merged, MultiPolygon):
        warning = "non_adjacent_multipolygon"

    merged = orient(merged, sign=1.0)

    if not is_valid(merged):
        merged = merged.buffer(0)
        if not is_valid(merged):
            raise ValueError("merge produced invalid geometry that could not be repaired")

    return {
        "merged_territory": _to_geojson(merged),
        "warning": warning,
    }


# ---------------------------------------------------------------------------
# Split (shapely.ops.split)
# ---------------------------------------------------------------------------

def split_territory(
    geometry: dict,
    cut_line: list[list[float]],
    original_id: str,
) -> dict[str, Any]:
    """Split polygon by cut_line. D-04 + EDIT-04.

    PITFALL 4 (Shapely issue #1951, wontfix):
        `ops.split` silently returns a single-geometry collection if the cut line
        does not bisect the polygon. We pre-validate with `exterior.intersection`
        AND post-validate `len(result.geoms) >= 2`.

    :param geometry: GeoJSON Polygon geometry dict.
    :param cut_line: list of [lon, lat] coordinate pairs for the cut line.
    :param original_id: id of the territory being split.
    :return: {
        "original_id": str,
        "new_territory_a": {"id": str, "geometry": GeoJSON},
        "new_territory_b": {"id": str, "geometry": GeoJSON},
    }
    :raises ValueError: if cut line does not produce 2+ polygons.
    """
    polygon = _to_shapely(geometry)
    if not isinstance(polygon, Polygon):
        raise ValueError("split_territory requires a Polygon geometry, not MultiPolygon")

    cut_line_geom = LineString(cut_line)

    # Pre-validation (Pitfall 4): cut line MUST cross the exterior at ≥ 2 distinct
    # points. If not, ops.split silently returns [original_polygon].
    intersection = polygon.exterior.intersection(cut_line_geom)
    n_crossings = 0
    if isinstance(intersection, Point):
        n_crossings = 1
    elif hasattr(intersection, "geoms"):
        n_crossings = sum(1 for g in intersection.geoms if isinstance(g, Point))

    if n_crossings < 2:
        raise ValueError(
            f"Cut line does not bisect the territory (only {n_crossings} boundary "
            f"crossing(s); need >=2). Ensure the line enters and exits the polygon."
        )

    # Actual split
    result = split(polygon, cut_line_geom)
    polys = [g for g in result.geoms if isinstance(g, Polygon)]
    if len(polys) < 2:
        raise ValueError(
            "Split produced fewer than 2 polygons despite valid crossings; "
            "check cut_line validity and polygon complexity."
        )

    oriented = [orient(p, sign=1.0) for p in polys]

    return {
        "original_id": original_id,
        "new_territory_a": {
            "id": f"{original_id}_a",
            "geometry": _to_geojson(oriented[0]),
        },
        "new_territory_b": {
            "id": f"{original_id}_b",
            "geometry": _to_geojson(oriented[1]),
        },
    }


# ---------------------------------------------------------------------------
# Decimate (curvature-weighted uniform-stride sampler)
# ---------------------------------------------------------------------------

def decimate_polygon(
    geometry: dict,
    target_vertices: int = 12,
    **_ignored: Any,
) -> dict:
    """Reduce polygon to ~target_vertices, preserving high-curvature corners. D-02 + EDIT-02.

    Scale-independent: operates on vertex INDICES, not metric tolerances, so
    it produces consistent results for unit-square, lon/lat-degree, and pixel
    coordinate systems alike. Replaces the previous Douglas-Peucker
    binary-search implementation, which was effectively a no-op for real
    Galician condado polygons (~0.5° span, ~287 vertices) because
    `tolerance_range=(0.0, 1.0)` was wildly mis-scaled and Shapely #2165
    invalidations caused the search to never converge (orphan bug
    260426-qc0).

    Algorithm:
      1. Score every original vertex by local turning-angle magnitude
         (cross product of incoming/outgoing edges, normalized by segment
         lengths). Higher = sharper corner.
      2. Always keep the top-K highest-curvature vertices (K = max(2, target/2)).
      3. Fill remaining slots by uniform float-stride over the full ring,
         skipping indices already kept.
      4. Sort selected indices ascending to preserve ring orientation;
         close ring by repeating first coord.

    Backwards-compat: previous kwargs `tolerance_range` and `max_iterations`
    are accepted via **_ignored for any stale callers.

    :param geometry: GeoJSON Polygon geometry dict.
    :param target_vertices: approximate handle count (±3 tolerance).
    :return: GeoJSON Polygon geometry dict with reduced vertex count.
    """
    polygon = _to_shapely(geometry)
    if not isinstance(polygon, Polygon):
        raise ValueError("decimate_polygon requires a Polygon geometry")

    coords = list(polygon.exterior.coords)[:-1]  # drop closing duplicate
    n = len(coords)
    if n <= target_vertices:
        return _to_geojson(polygon)

    # 1. Curvature score per vertex.
    scores: list[float] = []
    for i in range(n):
        ax, ay = coords[(i - 1) % n]
        bx, by = coords[i]
        cx, cy = coords[(i + 1) % n]
        v1x, v1y = bx - ax, by - ay
        v2x, v2y = cx - bx, cy - by
        cross = abs(v1x * v2y - v1y * v2x)
        l1 = (v1x * v1x + v1y * v1y) ** 0.5
        l2 = (v2x * v2x + v2y * v2y) ** 0.5
        denom = l1 * l2
        scores.append(cross / denom if denom > 0 else 0.0)

    # 2. Always keep top-K highest-curvature vertices.
    k_corners = max(2, target_vertices // 2)
    corner_indices = sorted(
        range(n), key=lambda i: scores[i], reverse=True
    )[:k_corners]
    keep: set[int] = set(corner_indices)

    # 3. Fill remaining slots by uniform float-stride over the ring.
    if len(keep) < target_vertices:
        stride = n / target_vertices
        for j in range(target_vertices):
            idx = int(round(j * stride)) % n
            if idx not in keep:
                keep.add(idx)
                if len(keep) >= target_vertices:
                    break

    # 4. Sort by original index to preserve ring orientation; close ring.
    ordered = sorted(keep)
    new_coords = [coords[i] for i in ordered]
    new_coords.append(new_coords[0])

    new_poly = Polygon(new_coords)
    # Topology safeguard — if curvature sampling produces self-intersection
    # (rare for convex-ish Voronoi cells), fall back to plain stride.
    if not is_valid(new_poly):
        stride_int = max(1, n // target_vertices)
        fallback = [coords[i] for i in range(0, n, stride_int)][:target_vertices]
        fallback.append(fallback[0])
        new_poly = Polygon(fallback)
    return _to_geojson(new_poly)
