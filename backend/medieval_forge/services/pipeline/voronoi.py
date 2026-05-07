"""Verbatim port of inicio/map_generator.py §6 (BARONY ASSIGNMENT) + §8 (HIERARCHY MAPS).

Three functions, all carrying inicio bodies 1:1 per D-01:
  - setup_baronies        (§6, inicio:335-367) — TWO KD-trees per CLAUDE.md rule #3 + P-6
  - rasterize_baronies    (§6, inicio:370-429)
  - build_hierarchy_maps  (§8, inicio:504-516)

Signature substitutions per D-14: territory data is read from cfg
(`cfg.condados`, `cfg.duchies`, `cfg.kingdoms`) instead of inicio's separate
positional arguments. The 38/40-point border polygon (`cfg.border_polygon`)
routes municipalities via `point_in_polygon` ray-cast (CLAUDE.md rule #3).
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree

from .contracts import RegionConfig, geo_to_pixel, point_in_polygon  # point_in_polygon imported for routing reference (cfg.border_polygon ray-cast lives in border.py)


def setup_baronies(cfg: RegionConfig):
    """Build barony data arrays and KD-trees for assignment.

    Verbatim port of inicio/map_generator.py:335-367 (D-01) with D-14 substitution:
    territory data read from cfg.condados/cfg.duchies/cfg.kingdoms (instead of
    being passed as positional arguments).

    Critical (CLAUDE.md rule #3 + P-6): builds TWO KD-trees:
      - tp = cKDTree of PT baronies
      - te = cKDTree of ES baronies
    NOT a single global tree. Routing happens via cfg.pt_duchies membership.
    """
    condados = cfg.condados
    duchies = cfg.duchies
    kingdoms = cfg.kingdoms

    bars = []
    bpt = []  # is this barony on the PT side?
    dl = list(duchies.keys())
    d2i = {d: i for i, d in enumerate(dl)}
    kl = list(kingdoms.keys())
    k2i = {k: i for i, k in enumerate(kl)}

    for ci, c in enumerate(condados):
        did = c[4]
        for bn, blo, bla in c[5]:
            px, py = geo_to_pixel(blo, bla, cfg)
            bars.append({
                'name': bn, 'px': px, 'py': py,
                'condado_idx': ci, 'duchy_id': did,
                'kingdom_id': duchies[did][0],
            })
            bpt.append(did in cfg.pt_duchies)

    nb = len(bars)
    bpx = np.array([(b['px'], b['py']) for b in bars], dtype=np.float32)
    bc = np.array([b['condado_idx'] for b in bars], dtype=np.int32)
    bd = np.array([d2i[b['duchy_id']] for b in bars], dtype=np.int32)
    bk = np.array([k2i[b['kingdom_id']] for b in bars], dtype=np.int32)

    # Separate PT and ES barony indices for border-aware assignment
    # CLAUDE.md rule #3 + P-6: TWO KD-trees, never global.
    pi = [i for i in range(nb) if bpt[i]]
    ei = [i for i in range(nb) if not bpt[i]]
    tp = cKDTree(bpx[pi]) if pi else None
    te = cKDTree(bpx[ei]) if ei else None

    return bars, bpx, bc, bd, bk, pi, ei, tp, te


def rasterize_baronies(pt_data, es_municipalities, bars, pi, ei, tp, te,
                       land, border_mask, cfg: RegionConfig) -> np.ndarray:
    """Assign each land pixel to a barony via municipality polygons + KD-tree fallback.

    Verbatim port of inicio/map_generator.py:370-429 (D-01).

    The 38/40-point border polygon is consulted indirectly via the precomputed
    border_mask (built by border.build_border_mask, which uses point_in_polygon
    against cfg.border_polygon) to route unassigned land pixels to the correct
    per-country KD-tree (CLAUDE.md rule #3).
    """
    nb = len(bars)
    ci_img = Image.new("I", (cfg.map_w, cfg.map_h), -1)
    draw = ImageDraw.Draw(ci_img)

    # Rasterize PT municipalities → assign to nearest PT barony
    if pt_data and tp:
        for feat in pt_data.get('features', []):
            geom = feat['geometry']
            gt = geom['type']
            coords = geom['coordinates']
            rings = [coords[0]] if gt == 'Polygon' else \
                    [p[0] for p in coords] if gt == 'MultiPolygon' else []
            if not rings or len(rings[0]) < 40:
                continue
            mr = rings[0]
            cl = sum(c[0] for c in mr) / len(mr)
            cla = sum(c[1] for c in mr) / len(mr)
            px, py = geo_to_pixel(cl, cla, cfg)
            _, li = tp.query([px, py])
            bi = pi[li]
            for ring in rings:
                pts = [geo_to_pixel(lo, la, cfg) for lo, la in ring
                       if cfg.lon_min-1 <= lo <= cfg.lon_max+1 and
                          cfg.lat_min-1 <= la <= cfg.lat_max+1]
                if len(pts) >= 3:
                    draw.polygon(pts, fill=int(bi))

    # Rasterize ES municipalities → assign to nearest ES barony
    if te:
        for m in es_municipalities:
            px, py = geo_to_pixel(m['lon'], m['lat'], cfg)
            _, li = te.query([px, py])
            bi = ei[li]
            for ring in m['rings']:
                pts = [geo_to_pixel(lo, la, cfg) for lo, la in ring
                       if cfg.lon_min-1 <= lo <= cfg.lon_max+1 and
                          cfg.lat_min-1 <= la <= cfg.lat_max+1]
                if len(pts) >= 3:
                    draw.polygon(pts, fill=int(bi))

    raw = np.array(ci_img, dtype=np.int16)
    raw[~land] = -1

    # Fallback: land pixels without municipality → nearest barony (border-aware)
    unassigned = land & (raw < 0)
    if np.any(unassigned):
        ys, xs = np.where(unassigned)
        coords = np.column_stack([xs.astype(np.float32), ys.astype(np.float32)])
        ipt = border_mask[ys, xs]
        if tp and np.any(ipt):
            _, idx = tp.query(coords[ipt])
            raw[ys[ipt], xs[ipt]] = np.array(pi)[idx].astype(np.int16)
        if te and np.any(~ipt):
            _, idx = te.query(coords[~ipt])
            raw[ys[~ipt], xs[~ipt]] = np.array(ei)[idx].astype(np.int16)

    return raw


def build_hierarchy_maps(result: np.ndarray, bc, bd, bk, nb):
    """Build condado/duchy/kingdom pixel maps from barony result.

    Verbatim port of inicio/map_generator.py:504-516 (D-01).
    Lives in voronoi.py per RESEARCH §1 tie-break (operates on the same
    index arrays produced by setup_baronies).
    """
    h, w = result.shape
    pc = np.full((h, w), -1, dtype=np.int16)
    pd = np.full_like(pc, -1)
    pk = np.full_like(pc, -1)
    for bi in range(nb):
        m = result == bi
        if np.any(m):
            pc[m] = bc[bi]
            pd[m] = bd[bi]
            pk[m] = bk[bi]
    return pc, pd, pk


__all__ = [
    "setup_baronies",
    "rasterize_baronies",
    "build_hierarchy_maps",
]
