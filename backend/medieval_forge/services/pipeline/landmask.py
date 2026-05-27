"""Verbatim port of inicio/map_generator.py §3 (DATA LOADING) + §4 (LAND MASK).

Functions, all carrying inicio bodies 1:1 per D-01 except for the
Phase 02 D-06 GeoJSON ES branch + D-04 fail-fast input assert in
`load_municipalities`:
  - decode_topojson_municipalities (§3, inicio:200-242)
  - decode_geojson_municipalities  (Phase 02 D-06; output shape matches
                                    decode_topojson_municipalities)
  - load_municipalities             (§3, inicio:245-260; D-04 + D-06)
  - build_land_mask                 (§4, inicio:267-310) — P-11 island scaling
                                    `cfg.island_min_px * (w / cfg.map_w)` preserved
                                    so the 2x mask uses 4× the island threshold
                                    (CLAUDE.md rule #6 — 2x is independent render).

NOTE: inicio's `load_territory_data` (lines 192-197) is intentionally OMITTED
per D-13 — territory data lives on cfg now (kingdoms/duchies/condados fields).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import label as nd_label

from .contracts import RegionConfig, geo_to_pixel


def decode_topojson_municipalities(topo: dict, cfg: RegionConfig) -> list:
    """Decode TopoJSON municipalities into list of {lon, lat, rings}.

    Verbatim port of inicio/map_generator.py:200-242 (D-01).
    """
    tr = topo.get('transform', {})
    sx, sy = tr.get('scale', [1, 1])
    tx, ty = tr.get('translate', [0, 0])
    arcs_decoded = []
    for arc in topo.get('arcs', []):
        cx, cy = 0, 0
        pts = []
        for d in arc:
            cx += d[0]; cy += d[1]
            pts.append((cx * sx + tx, cy * sy + ty))
        arcs_decoded.append(pts)

    def decode_ring(refs):
        coords = []
        for idx in refs:
            a = arcs_decoded[idx] if idx >= 0 else arcs_decoded[~idx][::-1]
            coords.extend(a[1:] if coords else a)
        return coords

    obj = topo.get('objects', {}).get('municipalities', {})
    result = []
    for g in obj.get('geometries', []):
        gt = g.get('type', '')
        ga = g.get('arcs', [])
        rings = []
        if gt == 'Polygon':
            for ra in ga:
                r = decode_ring(ra)
                if len(r) >= 3: rings.append(r)
        elif gt == 'MultiPolygon':
            for p in ga:
                for ra in p:
                    r = decode_ring(ra)
                    if len(r) >= 3: rings.append(r)
        if rings:
            mr = rings[0]
            cl = sum(p[0] for p in mr) / len(mr)
            cla = sum(p[1] for p in mr) / len(mr)
            if cfg.lon_min <= cl <= cfg.lon_max and cfg.lat_min <= cla <= cfg.lat_max:
                result.append({'lon': cl, 'lat': cla, 'rings': rings})
    return result


def decode_geojson_municipalities(fc: dict, cfg: RegionConfig) -> list:
    """Decode GeoJSON FeatureCollection into list of {lon, lat, rings}.

    Phase 02 D-06: live OSM ES output emits GeoJSON (not TopoJSON). Output
    shape MUST match decode_topojson_municipalities byte-for-byte (verbatim
    parity with inicio:215-219). Each item:

        {"lon": float, "lat": float, "rings": list[list[tuple[float, float]]]}

    lon/lat = arithmetic mean of the FIRST ring's points (mirrors inicio:215-217).
    Bbox-filtered to cfg.lon_min..lon_max / cfg.lat_min..lat_max (mirrors
    inicio:218-219). Rings shorter than 3 points are dropped (matches inicio:208-211).

    Polygon → exterior ring only. MultiPolygon → list of exterior rings.
    Anything else (Point, LineString, etc.) → skipped.
    """
    result = []
    for feature in fc.get("features", []):
        geom = feature.get("geometry") or {}
        gt = geom.get("type", "")
        coords = geom.get("coordinates", [])
        rings = []
        if gt == "Polygon" and coords:
            r = coords[0]  # exterior ring only — matches TopoJSON branch
            if len(r) >= 3:
                rings.append([tuple(p) for p in r])
        elif gt == "MultiPolygon":
            for poly in coords:
                if poly:
                    r = poly[0]
                    if len(r) >= 3:
                        rings.append([tuple(p) for p in r])
        else:
            continue
        if not rings:
            continue
        mr = rings[0]
        cl = sum(p[0] for p in mr) / len(mr)
        cla = sum(p[1] for p in mr) / len(mr)
        if cfg.lon_min <= cl <= cfg.lon_max and cfg.lat_min <= cla <= cfg.lat_max:
            result.append({"lon": cl, "lat": cla, "rings": rings})
    return result


def load_municipalities(cfg: RegionConfig):
    """Load PT GeoJSON and ES TopoJSON/GeoJSON municipality data.

    Verbatim port of inicio/map_generator.py:245-260 (D-01) extended in
    Phase 02 with:
      - D-04 fail-fast input assert: cfg.dataset and the three required
        Path attributes (pt_geojson, es_input, mountain_river_json) MUST
        exist on disk. Missing → FileNotFoundError naming the missing
        attribute.
      - D-06 ES extension discriminator: `.geojson` → GeoJSON branch
        (decode_geojson_municipalities); ANY OTHER extension (including
        the vendored `.json` TopoJSON) → existing TopoJSON branch.

    Returns (pt_data, es_municipalities) tuple.
    """
    # D-04: required ProjectDataset paths must exist; fail fast on missing input.
    # Phase 02 ProjectDataset is the single port through which file inputs flow;
    # the legacy three flat path fields on RegionConfig are gone.
    if cfg.dataset is None:
        raise FileNotFoundError(
            "RegionConfig.dataset is None — Phase 02 ProjectDataset is required."
        )
    for attr in ("pt_geojson", "es_input", "mountain_river_json"):
        p = getattr(cfg.dataset, attr, None)
        if p is None or not Path(p).exists():
            raise FileNotFoundError(
                f"ProjectDataset.{attr} missing or not found: {p!r}"
            )

    pt_data = None
    es_municipalities = []

    pt_path = cfg.dataset.pt_geojson
    if pt_path and os.path.exists(pt_path):
        with open(pt_path, 'r', encoding='utf-8') as f:
            pt_data = json.load(f)
        print(f"  Loaded PT municipalities: {len(pt_data.get('features', []))} features")

    es_path = cfg.dataset.es_input
    if es_path and os.path.exists(es_path):
        # D-06: extension discriminator. `.geojson` → GeoJSON branch;
        # anything else (including the vendored `.json` TopoJSON) → existing
        # TopoJSON branch. DO NOT INVERT — the vendored npm package
        # `es-atlas@0.6.0` ships municipalities as `.json` (TopoJSON despite
        # the extension); only live adapter output uses `.geojson`.
        if str(es_path).endswith(".geojson"):
            with open(es_path, 'r', encoding='utf-8') as f:
                es_municipalities = decode_geojson_municipalities(json.load(f), cfg)
        else:
            # Windows-port deviation (Rule 3): inicio:256 omits encoding='utf-8',
            # relying on POSIX UTF-8 default. On Windows cp1252 raises
            # UnicodeDecodeError on byte 0x8d. PT load already uses utf-8 (inicio:251);
            # adding it here keeps cross-platform behaviour identical to inicio's intent.
            with open(es_path, 'r', encoding='utf-8') as f:
                es_municipalities = decode_topojson_municipalities(json.load(f), cfg)
        print(f"  Loaded ES municipalities: {len(es_municipalities)} features")

    return pt_data, es_municipalities


def build_land_mask(pt_data, es_municipalities, cfg: RegionConfig,
                    target_w: int = None, target_h: int = None) -> np.ndarray:
    """Build binary land mask from municipality polygons at specified resolution.

    Verbatim port of inicio/map_generator.py:267-310 (D-01).

    Critical (P-11 + CLAUDE.md rule #6): the island filter scales with
    resolution via `cfg.island_min_px * (w / cfg.map_w)` so the 2x mask is
    an INDEPENDENT render with 4× the island threshold (not an upscale).

    Phase 08 Plan 08 (LANDMASK-01, DAG-04): when cfg.landmask_override is set,
    rasterize directly from the override polygon instead of PT/ES municipality
    inputs. This is the editor replace path — pt_data and es_municipalities are
    ignored. When override is None (default), behavior is unchanged from pre-
    Phase-08 (D-17 parity carry-forward).

    T-08-08-01: landmask_override does NOT touch cfg.border_polygon. The PT/ES
    border stays a separate read-only surface (Pitfall 3 / CLAUDE.md Rule #3).
    """
    w = target_w or cfg.map_w
    h = target_h or cfg.map_h

    land_img = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(land_img)

    # Phase 08 Plan 08: landmask_override fast-path — skip municipality data.
    if cfg.landmask_override is not None:
        pts = [geo_to_pixel(lo, la, cfg, w, h) for lo, la in cfg.landmask_override
               if cfg.lon_min - 1 <= lo <= cfg.lon_max + 1 and
               cfg.lat_min - 1 <= la <= cfg.lat_max + 1]
        if len(pts) >= 3:
            draw.polygon(pts, fill=255)
        land = np.array(land_img) > 0
        # Apply island filter (same as default path — CLAUDE.md rule #6 preserved)
        labeled, n = nd_label(land)
        if n > 0:
            sizes = np.bincount(labeled.ravel())
            if len(sizes) > 1:
                main_lbl = np.argmax(sizes[1:]) + 1
                threshold = cfg.island_min_px * (w / cfg.map_w)
                for lbl in range(1, n + 1):
                    if lbl != main_lbl and sizes[lbl] < threshold:
                        land[labeled == lbl] = False
        return land

    # Default path: rasterize from PT/ES municipality data (D-01 verbatim port).
    # Draw PT concelhos
    if pt_data:
        for feat in pt_data.get('features', []):
            geom = feat['geometry']
            gt = geom['type']
            coords = geom['coordinates']
            rings = [coords[0]] if gt == 'Polygon' else \
                    [p[0] for p in coords] if gt == 'MultiPolygon' else []
            for ring in rings:
                pts = [geo_to_pixel(lo, la, cfg, w, h) for lo, la in ring
                       if cfg.lon_min-1 <= lo <= cfg.lon_max+1 and
                          cfg.lat_min-1 <= la <= cfg.lat_max+1]
                if len(pts) >= 3:
                    draw.polygon(pts, fill=255)

    # Draw ES municipalities
    for m in es_municipalities:
        for ring in m['rings']:
            pts = [geo_to_pixel(lo, la, cfg, w, h) for lo, la in ring
                   if cfg.lon_min-1 <= lo <= cfg.lon_max+1 and
                      cfg.lat_min-1 <= la <= cfg.lat_max+1]
            if len(pts) >= 3:
                draw.polygon(pts, fill=255)

    land = np.array(land_img) > 0

    # Remove tiny disconnected islands (P-11: scales with target_w / cfg.map_w)
    # Rule 1 bug-fix: n==0 means all-ocean result; skip island removal entirely
    # to avoid np.argmax on empty array (ValueError).
    labeled, n = nd_label(land)
    if n > 0:
        sizes = np.bincount(labeled.ravel())
        if len(sizes) > 1:
            main_lbl = np.argmax(sizes[1:]) + 1
            for lbl in range(1, n + 1):
                if lbl != main_lbl and sizes[lbl] < cfg.island_min_px * (w / cfg.map_w):
                    land[labeled == lbl] = False

    return land


__all__ = [
    "decode_topojson_municipalities",
    "decode_geojson_municipalities",
    "load_municipalities",
    "build_land_mask",
]
