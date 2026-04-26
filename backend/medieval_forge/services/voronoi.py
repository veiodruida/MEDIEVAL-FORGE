"""
Phase 4 geometry service: Voronoi adjacency + neighbor-only recalc + Shapely ops.
Consumed by api/edit.py. Centralizes all scipy + Shapely dependencies.

All public functions accept and return GeoJSON-dict representations so that
callers (FastAPI endpoints) can work directly with JSON-serialisable data.
"""
from __future__ import annotations

import json
import logging
import math
import pathlib
import time
from typing import Any

import numpy as np
from scipy.spatial import Voronoi
from shapely import is_valid
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiPolygon,
    Point,
    Polygon,
    box as _shapely_box,
    mapping,
    shape,
)
from shapely.geometry.base import BaseGeometry
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


def _select_largest_polygon(geom: BaseGeometry) -> Polygon | None:
    """Reduce a clipped geometry to a single Polygon (largest by area).

    Clipping with shapely.intersection can return Polygon, MultiPolygon, or
    GeometryCollection (the latter when boundary touches drop point/line
    fragments alongside polygonal area).  We always want a single Polygon
    per cell, so we keep the largest polygon component and discard
    lower-dimensional debris.  Returns None when no polygonal area survives.
    """
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, Polygon):
        return geom if geom.area > 0 else None
    polys: list[Polygon] = []
    if isinstance(geom, MultiPolygon):
        polys = [p for p in geom.geoms if not p.is_empty and p.area > 0]
    elif isinstance(geom, GeometryCollection):
        for g in geom.geoms:
            if isinstance(g, Polygon) and not g.is_empty and g.area > 0:
                polys.append(g)
            elif isinstance(g, MultiPolygon):
                polys.extend(p for p in g.geoms if not p.is_empty and p.area > 0)
    if not polys:
        return None
    return max(polys, key=lambda p: p.area)


def recalc_neighbors(
    condado_id: str,
    new_lon: float,
    new_lat: float,
    territory_data: dict,
    *,
    land_mask: BaseGeometry | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> dict[str, Any]:
    """Recompute Voronoi for the moved capital and its ridge-sharing neighbors.

    :param condado_id: id string of the condado whose capital was moved.
    :param new_lon: new longitude for the capital.
    :param new_lat: new latitude for the capital.
    :param territory_data: full Iberia fixture dict with "condados" list.
                           Each condado is a list: [id, name, lon, lat, duchy_id, baronies].
    :param land_mask: optional Shapely geometry in lon/lat — when supplied,
                     each computed Voronoi cell is intersected with this
                     geometry so cells never extend into ocean / outside the
                     project's land area.  Takes precedence over bbox when
                     both are provided (bbox is then implicit in the mask).
    :param bbox: optional (lon_min, lat_min, lon_max, lat_max) — when
                supplied (and land_mask is None), each cell is intersected
                with this bounding box.  Also used to bound previously-
                unbounded edge cells via sentinel seeds before clipping
                (qlo-01 fix: previously such cells were silently dropped).
    :return: {"updated_territories": {id: geojson_polygon}, "affected_ids": [str, ...]}

    Behavior contract:
        - When NEITHER land_mask NOR bbox is supplied, behavior is unchanged:
          unbounded edge cells are skipped, affected_ids reflects the full
          set of affected indices regardless of clip outcome (legacy
          backwards-compat for unit tests + early callers).
        - When land_mask or bbox is supplied, sentinel seeds are added to the
          Voronoi computation so every real cell becomes bounded, then each
          cell is clipped to (land_mask if set else bbox).  Cells whose
          clip result is empty are omitted from BOTH updated_territories
          AND affected_ids — no zero-area polygons leak out.

    Perf target: <500ms on ~800-seed Iberia dataset. The Voronoi call itself
    is ~50ms.
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

    # Resolve clip geometry. land_mask wins when both supplied.
    clip_geom: BaseGeometry | None = None
    if land_mask is not None:
        clip_geom = land_mask
    elif bbox is not None:
        lon_min, lat_min, lon_max, lat_max = bbox
        clip_geom = _shapely_box(lon_min, lat_min, lon_max, lat_max)

    # When clipping is requested, add 4 far-away sentinel seeds so every
    # real seed gets a bounded Voronoi cell.  Sentinels live well outside
    # any reasonable clip extent, so the intersection step always strips
    # any sentinel-derived polygon area from real-cell results.
    n_real = len(pts)
    if clip_geom is not None:
        # Compute a sentinel radius from the union of pts + clip extent.
        cx_min, cy_min, cx_max, cy_max = clip_geom.bounds
        all_x = np.concatenate([pts[:, 0], np.array([cx_min, cx_max])])
        all_y = np.concatenate([pts[:, 1], np.array([cy_min, cy_max])])
        x_lo, x_hi = float(all_x.min()), float(all_x.max())
        y_lo, y_hi = float(all_y.min()), float(all_y.max())
        cx = (x_lo + x_hi) * 0.5
        cy = (y_lo + y_hi) * 0.5
        r = max(x_hi - x_lo, y_hi - y_lo, 1.0) * 100.0
        sentinels = np.array([
            [cx - r, cy - r],
            [cx + r, cy - r],
            [cx - r, cy + r],
            [cx + r, cy + r],
        ], dtype=float)
        vor_pts = np.vstack([pts, sentinels])
    else:
        vor_pts = pts

    vor = Voronoi(vor_pts)

    updated_territories: dict[str, dict] = {}
    surviving_indices: set[int] = set()

    for idx in affected_indices:
        region_idx = vor.point_region[idx]
        region = vor.regions[region_idx]
        if not region or -1 in region:
            # Unbounded cell.
            if clip_geom is None:
                # Legacy path: skip entirely.
                continue
            # With clip_geom in effect, sentinel seeds should have made every
            # real cell bounded.  If it is still unbounded, log + skip
            # (defense-in-depth — should not happen in practice).
            logger.warning(
                "recalc_neighbors: cell %d still unbounded after sentinel "
                "augmentation — skipping.", idx,
            )
            continue
        vertices = [vor.vertices[v] for v in region]
        poly = Polygon(vertices)
        if not is_valid(poly):
            poly = poly.buffer(0)  # standard GEOS self-intersection repair

        if clip_geom is not None:
            try:
                clipped = poly.intersection(clip_geom)
            except Exception:
                logger.exception(
                    "recalc_neighbors: intersection failed for cell %d", idx,
                )
                continue
            poly = _select_largest_polygon(clipped)
            if poly is None:
                # Cell lies entirely outside the clip geometry — drop it
                # from both updated_territories AND affected_ids.
                continue
            if not is_valid(poly):
                poly = poly.buffer(0)
                if not isinstance(poly, Polygon) or poly.is_empty:
                    continue

        poly = orient(poly, sign=1.0)  # counter-clockwise exterior
        cid = idx_to_id.get(idx)
        if cid is not None:
            updated_territories[cid] = _to_geojson(poly)
            surviving_indices.add(idx)

    # Compute affected_ids per behavior contract:
    #   - clip in effect → only survivors
    #   - no clip → preserve legacy "all affected_indices" semantics
    if clip_geom is not None:
        affected_ids = [idx_to_id[i] for i in surviving_indices if i in idx_to_id]
    else:
        affected_ids = [idx_to_id[i] for i in affected_indices if i in idx_to_id]

    elapsed = time.perf_counter() - t0
    if elapsed > 0.5:
        logger.warning(
            "recalc_neighbors exceeded 500ms budget: %.3fs for %d seeds, %d affected",
            elapsed,
            n_real,
            len(affected_indices),
        )

    return {
        "updated_territories": updated_territories,
        "affected_ids": affected_ids,
    }


# ---------------------------------------------------------------------------
# Land-mask + bbox loader (consumed by api/edit.py::move_capital)
# ---------------------------------------------------------------------------

def load_land_mask_and_bbox(
    generated_dir: pathlib.Path,
) -> tuple[BaseGeometry | None, tuple[float, float, float, float] | None]:
    """Build the (land_mask, bbox) pair from a project's generated/ artifacts.

    Inputs (read from `generated_dir`):
      * ``territory_metadata.json`` → ``bounds`` block → bbox tuple
      * ``lookup_condado.png`` → binary land mask via rasterio.features.shapes
        → unary_union → projected pixel→lon/lat using the SAME inversion as
        territories_geojson.pixel_polygon_to_lonlat (DRY reuse).

    Returns ``(land_mask, bbox)`` where either may be None when the
    corresponding source file is missing or malformed.  Never raises —
    callers always get a safe pair (worst case (None, None)) so the
    move_capital endpoint can still run unclipped.
    """
    bbox: tuple[float, float, float, float] | None = None
    land_mask: BaseGeometry | None = None

    # 1. bbox from metadata.
    meta_path = generated_dir / "territory_metadata.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            b = meta.get("bounds") or {}
            lon_min = float(b["lon_min"]); lon_max = float(b["lon_max"])
            lat_min = float(b["lat_min"]); lat_max = float(b["lat_max"])
            bbox = (lon_min, lat_min, lon_max, lat_max)
        except (KeyError, ValueError, TypeError, OSError) as e:
            logger.warning(
                "load_land_mask_and_bbox: failed to parse bounds from %s: %s",
                meta_path, e,
            )
            bbox = None

    # 2. land mask from lookup raster.  Requires bbox to project pixels.
    lookup_path = generated_dir / "lookup_condado.png"
    if bbox is not None and lookup_path.exists():
        try:
            import rasterio.features
            from PIL import Image
            from .territories_geojson import (
                pixel_polygon_to_lonlat,
                _ProjCfg,
            )

            img = np.array(Image.open(lookup_path).convert("RGB"))
            H, W, _ = img.shape
            # Background = pure black per generate_lookup_map; everything
            # else is land.
            mask = (img.sum(axis=-1) > 0).astype(np.uint8)
            geoms_px: list = []
            for geom_px, val in rasterio.features.shapes(mask, mask=mask.astype(bool)):
                if int(val) != 1:
                    continue
                geoms_px.append(shape(geom_px))
            if geoms_px:
                land_px = unary_union(geoms_px)
                # Project pixel-space polygon(s) → lon/lat using the same
                # inversion math as territories_geojson.
                lon_min, lat_min, lon_max, lat_max = bbox
                mid_lat = (lat_min + lat_max) * 0.5
                lon_scale = math.cos(math.radians(mid_lat))
                cfg = _ProjCfg(
                    lon_min=lon_min, lon_max=lon_max,
                    lat_min=lat_min, lat_max=lat_max,
                    map_w=W, map_h=H, upscale=1, lon_scale=lon_scale,
                )
                land_mask_geojson = pixel_polygon_to_lonlat(
                    mapping(land_px), cfg, W, H,
                )
                land_mask = shape(land_mask_geojson)
                if not is_valid(land_mask):
                    land_mask = land_mask.buffer(0)
        except Exception as e:
            logger.warning(
                "load_land_mask_and_bbox: failed to build land mask from %s: %s",
                lookup_path, e,
            )
            land_mask = None

    return land_mask, bbox


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
