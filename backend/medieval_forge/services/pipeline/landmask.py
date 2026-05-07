"""Verbatim port of inicio/map_generator.py §3 (DATA LOADING) + §4 (LAND MASK).

Three functions, all carrying inicio bodies 1:1 per D-01:
  - decode_topojson_municipalities (§3, inicio:200-242)
  - load_municipalities             (§3, inicio:245-260)
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


def load_municipalities(cfg: RegionConfig):
    """Load PT GeoJSON and ES TopoJSON municipality data.

    Verbatim port of inicio/map_generator.py:245-260 (D-01).
    Returns (pt_data, es_municipalities) tuple.
    """
    pt_data = None
    es_municipalities = []

    if cfg.municipality_pt_geojson and os.path.exists(cfg.municipality_pt_geojson):
        with open(cfg.municipality_pt_geojson, 'r', encoding='utf-8') as f:
            pt_data = json.load(f)
        print(f"  Loaded PT municipalities: {len(pt_data.get('features', []))} features")

    if cfg.municipality_es_topojson and os.path.exists(cfg.municipality_es_topojson):
        # Windows-port deviation (Rule 3): inicio:256 omits encoding='utf-8',
        # relying on POSIX UTF-8 default. On Windows cp1252 raises
        # UnicodeDecodeError on byte 0x8d. PT load already uses utf-8 (inicio:251);
        # adding it here keeps cross-platform behaviour identical to inicio's intent.
        with open(cfg.municipality_es_topojson, 'r', encoding='utf-8') as f:
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
    """
    w = target_w or cfg.map_w
    h = target_h or cfg.map_h

    land_img = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(land_img)

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
    labeled, n = nd_label(land)
    sizes = np.bincount(labeled.ravel())
    main_lbl = np.argmax(sizes[1:]) + 1
    for lbl in range(1, n + 1):
        if lbl != main_lbl and sizes[lbl] < cfg.island_min_px * (w / cfg.map_w):
            land[labeled == lbl] = False

    return land


__all__ = [
    "decode_topojson_municipalities",
    "load_municipalities",
    "build_land_mask",
]
