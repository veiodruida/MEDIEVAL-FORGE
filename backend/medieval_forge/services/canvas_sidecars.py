"""Canvas-sidecar emitters for the v3 pipeline (Plan 03-01, Pitfall 10 fix).

The 12-file Unity contract gives the canvas the lookup PNGs + metadata, but
the Phase 03 read-only canvas also needs four lightweight derived artefacts
to render territory polygons in lon/lat space:

  - territories.geojson   FeatureCollection of condado polygons
                          (id, name, neighbors, centroid, kingdom_id, duchy_id)
  - baronies.geojson      FeatureCollection of barony polygons
                          (id, name, condado_id, centroid, pixel_count)
  - condado_colors.json   {condado_id: "#rrggbb"} — matches lookup_condado.png
  - barony_colors.json    {barony_id:  "#rrggbb"} — matches lookup_barony.png

The four files are written into ``cfg.output_dir`` alongside the 10 Unity
contract files. They are emit-only and parity-safe — Phase 01 parity asserts
only on the 10 contract files.

Key constraints (verified against existing pipeline code):
  - Sidecar GeoJSONs are derived from the same `result` (barony raster) and
    `pc` (condado raster) arrays the metadata + lookup steps already used,
    so geometry never disagrees with the rendered PNGs (D-09 deployed-wins).
  - Polygon vertices are rasterio.features.shapes output (pixel space) then
    mapped to lon/lat via the inverse of pipeline.contracts.geo_to_pixel.
    pc/result resolution is ``cfg.map_w x cfg.map_h`` (1x), NOT the upscaled
    visual resolution — this matches the lookup PNG resolution.
  - Color maps emitted by ``generate_lookup_map`` use
    ``"r,g,b"``-string keys mapped to ORIGINAL indices (not compacted). We
    invert those into ``{id: "#rrggbb"}`` form via the original
    ``cfg.condados`` / ``bars`` lists.
  - Empty / dropped condados (npx == 0) are intentionally absent from
    territories.geojson — they have no polygon to draw. Their colors also
    don't appear in the cmap (generate_lookup_map skips them).
"""

from __future__ import annotations

import json
import os
from typing import Any

import numpy as np
import rasterio.features
from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

from .pipeline.contracts import RegionConfig


# ---------------------------------------------------------------------------
# Pixel → lon/lat helper (inverse of pipeline.contracts.geo_to_pixel).
# Duplicated here rather than imported from territories_geojson.py because
# that module is a Phase 03 deletion target (Wave 3); keeping this self-
# contained keeps the deletion graph clean.
# ---------------------------------------------------------------------------
def _ring_to_lonlat(coords, cfg: RegionConfig, raster_w: int, raster_h: int):
    span = (cfg.lon_max - cfg.lon_min) * cfg.lon_scale
    out = []
    for x, y in coords:
        lon = x / raster_w * span / cfg.lon_scale + cfg.lon_min
        lat = cfg.lat_max - y / raster_h * (cfg.lat_max - cfg.lat_min)
        out.append([lon, lat])
    return out


def _pixel_geom_to_lonlat(geom: dict, cfg: RegionConfig, raster_w: int, raster_h: int) -> dict:
    if geom["type"] == "Polygon":
        return {
            "type": "Polygon",
            "coordinates": [_ring_to_lonlat(r, cfg, raster_w, raster_h) for r in geom["coordinates"]],
        }
    if geom["type"] == "MultiPolygon":
        return {
            "type": "MultiPolygon",
            "coordinates": [
                [_ring_to_lonlat(r, cfg, raster_w, raster_h) for r in poly]
                for poly in geom["coordinates"]
            ],
        }
    raise ValueError(f"unsupported geometry type: {geom['type']}")


def _invert_cmap_to_hex(cmap: dict[str, int]) -> dict[int, str]:
    """``{"r,g,b": orig_idx}`` -> ``{orig_idx: "#rrggbb"}``."""
    out: dict[int, str] = {}
    for rgb_key, idx in cmap.items():
        r, g, b = (int(p) for p in rgb_key.split(","))
        out[int(idx)] = f"#{r:02x}{g:02x}{b:02x}"
    return out


# ---------------------------------------------------------------------------
# Public emitters — called from run_pipeline at the end of the export stage.
# ---------------------------------------------------------------------------
def build_territories_geojson_sidecar(
    *,
    pc: np.ndarray,
    condados: list,
    duchies: dict,
    cfg: RegionConfig,
    condado_cmap: dict[str, int],
    out_dir: str,
) -> tuple[str, str]:
    """Write territories.geojson + condado_colors.json.

    Returns the two paths written.
    """
    raster_h, raster_w = pc.shape

    # Group rasterio shapes by condado original index.
    pc32 = pc.astype(np.int32)
    shapes_per_idx: dict[int, list] = {}
    for geom, idx in rasterio.features.shapes(pc32, mask=(pc32 >= 0)):
        i = int(idx)
        shapes_per_idx.setdefault(i, []).append(shape(geom))

    # Build features in original-condado-index order; skip drops (empty).
    features: list[dict] = []
    unioned: dict[int, Any] = {}
    for ci, c in enumerate(condados):
        geoms = shapes_per_idx.get(ci, [])
        if not geoms:
            continue
        u = unary_union(geoms)
        unioned[ci] = u
        cid = c[0]
        cname = c[1]
        duchy_id = c[4]
        kingdom_id = duchies[duchy_id][0] if duchy_id in duchies else ""
        lonlat_geom = _pixel_geom_to_lonlat(mapping(u), cfg, raster_w, raster_h)
        features.append({
            "type": "Feature",
            "id": cid,
            "geometry": lonlat_geom,
            "properties": {
                "id": cid,
                "name": cname,
                "neighbors": [],   # filled below
                "centroid": [c[2], c[3]],   # (lon, lat) from territory_data
                "kingdom_id": kingdom_id,
                "duchy_id": duchy_id,
            },
        })

    # Neighbour topology via STRtree + .touches (matches v1 emitter behaviour).
    if unioned:
        idx_to_id = {ci: condados[ci][0] for ci in unioned}
        id_to_ci = {v: k for k, v in idx_to_id.items()}
        tree_geoms = list(unioned.values())
        tree = STRtree(tree_geoms)
        ci_by_geom_idx = list(unioned.keys())

        for feat in features:
            ci = id_to_ci[feat["id"]]
            g = unioned[ci]
            neigh_ids: set[str] = set()
            for qi in tree.query(g):
                other_ci = ci_by_geom_idx[qi]
                if other_ci == ci:
                    continue
                if g.touches(unioned[other_ci]):
                    neigh_ids.add(idx_to_id[other_ci])
            feat["properties"]["neighbors"] = sorted(neigh_ids)

    geojson_path = os.path.join(out_dir, "territories.geojson")
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(
            {"type": "FeatureCollection", "features": features},
            f, ensure_ascii=False,
        )

    # condado_colors.json: {condado_id: "#rrggbb"} via cmap inversion.
    idx_to_hex = _invert_cmap_to_hex(condado_cmap)
    colors: dict[str, str] = {}
    for ci, c in enumerate(condados):
        if ci in idx_to_hex:
            colors[c[0]] = idx_to_hex[ci]
    colors_path = os.path.join(out_dir, "condado_colors.json")
    with open(colors_path, "w", encoding="utf-8") as f:
        json.dump(colors, f, ensure_ascii=False)

    return geojson_path, colors_path


def build_baronies_geojson_sidecar(
    *,
    result: np.ndarray,
    bars: list[dict],
    cfg: RegionConfig,
    barony_cmap: dict[str, int],
    out_dir: str,
) -> tuple[str, str]:
    """Write baronies.geojson + barony_colors.json.

    Each surviving barony (npx > 0) emits one Feature. The barony id is its
    `name` (no separate id field exists in the bars dict — see voronoi.py).
    """
    raster_h, raster_w = result.shape

    res32 = result.astype(np.int32)
    shapes_per_idx: dict[int, list] = {}
    for geom, idx in rasterio.features.shapes(res32, mask=(res32 >= 0)):
        i = int(idx)
        shapes_per_idx.setdefault(i, []).append(shape(geom))

    features: list[dict] = []
    for bi, b in enumerate(bars):
        geoms = shapes_per_idx.get(bi, [])
        if not geoms:
            continue
        u = unary_union(geoms)
        bname = b["name"]
        condado_idx = b["condado_idx"]
        condado_id = cfg.condados[condado_idx][0] if 0 <= condado_idx < len(cfg.condados) else ""
        npx = int(np.sum(result == bi))
        # Centroid in lon/lat — derive from polygon to stay consistent with
        # the rendered raster (don't reuse the inicio bx/by which is the
        # geo seed point, not the post-cleanup mass-centroid).
        centroid_px = u.centroid
        cx, cy = centroid_px.x, centroid_px.y
        span = (cfg.lon_max - cfg.lon_min) * cfg.lon_scale
        lon = cx / raster_w * span / cfg.lon_scale + cfg.lon_min
        lat = cfg.lat_max - cy / raster_h * (cfg.lat_max - cfg.lat_min)
        lonlat_geom = _pixel_geom_to_lonlat(mapping(u), cfg, raster_w, raster_h)
        # Derive duchy_id and kingdom_id from the condado tuple (same derivation
        # as the condado emitter at ~128-129): condado tuple index 4 is duchy_id.
        duchy_id = ""
        kingdom_id = ""
        if 0 <= condado_idx < len(cfg.condados):
            condado_tuple = cfg.condados[condado_idx]
            duchy_id = condado_tuple[4] if len(condado_tuple) > 4 else ""
            kingdom_id = cfg.duchies[duchy_id][0] if duchy_id in cfg.duchies else ""
        features.append({
            "type": "Feature",
            "id": bname,
            "geometry": lonlat_geom,
            "properties": {
                "id": bname,
                "name": bname,
                "condado_id": condado_id,
                "condado_idx": condado_idx,
                "duchy_id": duchy_id,
                "kingdom_id": kingdom_id,
                "centroid": [lon, lat],
                "pixel_count": npx,
            },
        })

    geojson_path = os.path.join(out_dir, "baronies.geojson")
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(
            {"type": "FeatureCollection", "features": features},
            f, ensure_ascii=False,
        )

    idx_to_hex = _invert_cmap_to_hex(barony_cmap)
    colors: dict[str, str] = {}
    for bi, b in enumerate(bars):
        if bi in idx_to_hex:
            colors[b["name"]] = idx_to_hex[bi]
    colors_path = os.path.join(out_dir, "barony_colors.json")
    with open(colors_path, "w", encoding="utf-8") as f:
        json.dump(colors, f, ensure_ascii=False)

    return geojson_path, colors_path


__all__ = [
    "build_territories_geojson_sidecar",
    "build_baronies_geojson_sidecar",
]
