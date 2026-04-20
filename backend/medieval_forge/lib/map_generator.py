#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  MAP GENERATOR — Modular Grand Strategy Map Pipeline           ║
║  Project: Reconquista: Swords, Faith & Legacy                  ║
║  Author: Jhonni Vieceli                                        ║
║  Version: 1.0 — April 2026                                     ║
║                                                                  ║
║  Region-agnostic: works for Iberia, England, or any region     ║
║  with municipality/parish GeoJSON data.                        ║
║                                                                  ║
║  INPUTS:                                                        ║
║    - RegionConfig (coordinates, resolution, colors)             ║
║    - territory_data module (KINGDOMS, DUCHIES, CONDADOS)        ║
║    - Municipality GeoJSON (PT) + TopoJSON (ES)                 ║
║    - mountain_river_data.json (optional)                        ║
║                                                                  ║
║  OUTPUTS (for Unity):                                           ║
║    - lookup_barony.png   → barony hit detection (unique colors)║
║    - lookup_condado.png  → condado hit detection               ║
║    - visual_barony.png   → barony visual (for dev/skinning)    ║
║    - visual_condado.png  → condado visual (for dev/skinning)   ║
║    - territory_colors.json → color→ID mapping for Unity        ║
║    - territory_metadata.json → full hierarchy for Unity        ║
║    - mountains_mask.png  → impassable terrain mask             ║
╚══════════════════════════════════════════════════════════════════╝

Unity Integration:
  - Lookup maps use unique RGB colors per territory
  - Unity reads pixel at click position → looks up color in territory_colors.json
  - Visual maps are placeholder — will be replaced by pergaminho skin
  - Mountains mask: white = impassable, black = passable
"""

import json, math, os, sys
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.spatial import cKDTree
from scipy.ndimage import (gaussian_filter, distance_transform_edt,
                           label as nd_label, median_filter,
                           binary_dilation, binary_erosion)


# ═══════════════════════════════════════════════════════════════
# SECTION 1: CONFIGURATION
# ═══════════════════════════════════════════════════════════════

@dataclass
class RegionConfig:
    """Configuration for a map region. Change these to map a different area."""
    name: str = "iberia"
    
    # Map dimensions (1x render resolution)
    map_w: int = 1920
    map_h: int = 1080
    upscale: int = 2  # final output = map_w*upscale × map_h*upscale
    
    # Geographic bounds (WGS84)
    lon_min: float = -13.2
    lon_max: float = 8.2
    lat_min: float = 35.4
    lat_max: float = 44.6
    
    # Projection correction (cos of center latitude)
    lon_scale: float = field(default=None)
    
    # Paths
    output_dir: str = "../Assets/StreamingAssets/Maps"
    municipality_pt_geojson: str = None  # path to PT concelhos GeoJSON
    municipality_es_topojson: str = None  # path to ES municipalities TopoJSON
    mountain_river_json: str = None  # path to mountain/river data
    
    # PT/ES border polygon (for assigning municipalities to correct baronies)
    # List of (lon, lat) points defining the border
    border_polygon: list = field(default_factory=list)
    
    # Which duchies are on the "PT side" of the border
    pt_duchies: set = field(default_factory=set)
    
    # Rendering
    kingdom_colors: dict = field(default_factory=dict)
    ocean_near: tuple = (45, 90, 140)   # deep ocean RGB
    ocean_far: tuple = (70, 130, 180)   # shallow ocean RGB
    ocean_gradient_dist: float = 150.0  # px distance for full gradient
    coast_inner_width: int = 2          # px of inner coast outline
    coast_inner_color: tuple = (15, 10, 5)
    
    # Cleanup thresholds
    island_min_px: int = 300        # remove islands smaller than this
    fragment_min_px: int = 600      # merge barony fragments smaller than this
    blob_merge_px: int = 200        # merge final baronies smaller than this
    median_passes: int = 8          # number of median filter passes
    smooth_sigma: float = 3.0       # Gaussian smoothing sigma
    
    # Mountain config
    mountain_threshold: int = 1500   # elevation threshold in meters
    mountain_color_visual: tuple = (118, 100, 80)
    mountain_color_lookup: tuple = (50, 45, 40)
    mountain_noise: int = 20
    
    # River config
    river_color: tuple = (74, 144, 217)
    river_width: int = 2
    
    def __post_init__(self):
        if self.lon_scale is None:
            center_lat = (self.lat_min + self.lat_max) / 2
            self.lon_scale = math.cos(math.radians(center_lat))


def iberia_config() -> RegionConfig:
    """Default configuration for the Iberian Peninsula (868 AD)."""
    cfg = RegionConfig(
        name="iberia",
        map_w=1920, map_h=1080, upscale=2,
        lon_min=-13.2, lon_max=8.2, lat_min=35.4, lat_max=44.6,
        output_dir="../Assets/StreamingAssets/Maps",
        municipality_pt_geojson="../Assets/StreamingAssets/Maps/pt_concelhos_wgs84.geojson",
        municipality_es_topojson="es-atlas-pkg/package/es/municipalities.json",
        mountain_river_json="mountain_river_data.json",
        pt_duchies={"d_portucale", "d_gharb", "d_fronteira"},
        kingdom_colors={
            0: (190, 158, 82),   # Astúrias — gold
            1: (148, 88, 168),   # Pamplona — purple
            2: (198, 108, 128),  # Marca Hispânica — pink
            3: (68, 158, 62),    # Emirato — green
        },
        border_polygon=[
            (-9.50,42.20),(-8.85,41.88),(-8.16,41.82),(-7.92,41.88),
            (-7.40,41.87),(-7.17,41.97),(-6.93,41.94),(-6.81,41.95),
            (-6.55,41.68),(-6.38,41.65),(-6.19,41.57),(-6.54,41.37),
            (-6.80,41.13),(-6.93,41.03),(-6.86,40.89),(-6.86,40.27),
            (-6.90,40.11),(-6.96,39.91),(-7.04,39.67),(-7.02,39.47),
            (-7.26,39.21),(-7.42,39.18),(-7.30,39.05),(-7.16,38.96),
            (-7.07,38.81),(-7.06,38.65),(-7.17,38.44),(-7.25,38.24),
            (-7.35,38.14),(-7.42,38.00),(-7.48,37.82),(-7.44,37.65),
            (-7.50,37.50),(-7.46,37.38),(-7.43,37.26),(-7.41,37.18),
            (-7.38,37.08),(-7.40,36.90),(-9.50,36.90),(-9.50,42.20),
        ],
    )
    return cfg


# ═══════════════════════════════════════════════════════════════
# SECTION 2: COORDINATE TRANSFORMS
# ═══════════════════════════════════════════════════════════════

def geo_to_pixel(lon: float, lat: float, cfg: RegionConfig,
                 w: int = None, h: int = None) -> Tuple[int, int]:
    """Convert WGS84 lon/lat to pixel coordinates."""
    w = w or cfg.map_w
    h = h or cfg.map_h
    span = (cfg.lon_max - cfg.lon_min) * cfg.lon_scale
    px = int((lon - cfg.lon_min) * cfg.lon_scale / span * w)
    py = int((1.0 - (lat - cfg.lat_min) / (cfg.lat_max - cfg.lat_min)) * h)
    return (px, py)


def pixel_to_geo(px: int, py: int, cfg: RegionConfig,
                 w: int = None, h: int = None) -> Tuple[float, float]:
    """Convert pixel coordinates to WGS84 lon/lat."""
    w = w or cfg.map_w
    h = h or cfg.map_h
    span = (cfg.lon_max - cfg.lon_min) * cfg.lon_scale
    lon = px / w * span / cfg.lon_scale + cfg.lon_min
    lat = cfg.lat_max - py / h * (cfg.lat_max - cfg.lat_min)
    return (lon, lat)


def point_in_polygon(x: float, y: float, polygon: list) -> bool:
    """Ray-casting point-in-polygon test."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


# ═══════════════════════════════════════════════════════════════
# SECTION 3: DATA LOADING
# ═══════════════════════════════════════════════════════════════

def load_territory_data(module_name: str = "territory_data_v3"):
    """Load territory definitions from Python module."""
    import importlib
    mod = importlib.import_module(module_name)
    importlib.reload(mod)
    return mod.KINGDOMS, mod.DUCHIES, mod.CONDADOS


def decode_topojson_municipalities(topo: dict, cfg: RegionConfig) -> list:
    """Decode TopoJSON municipalities into list of {lon, lat, rings}."""
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


def load_municipalities(cfg: RegionConfig) -> Tuple[dict, list]:
    """Load PT GeoJSON and ES TopoJSON municipality data."""
    pt_data = None
    es_municipalities = []
    
    if cfg.municipality_pt_geojson and os.path.exists(cfg.municipality_pt_geojson):
        with open(cfg.municipality_pt_geojson, 'r', encoding='utf-8') as f:
            pt_data = json.load(f)
        print(f"  Loaded PT municipalities: {len(pt_data.get('features', []))} features")
    
    if cfg.municipality_es_topojson and os.path.exists(cfg.municipality_es_topojson):
        with open(cfg.municipality_es_topojson, 'r', encoding='utf-8') as f:
            es_municipalities = decode_topojson_municipalities(json.load(f), cfg)
        print(f"  Loaded ES municipalities: {len(es_municipalities)} features")
    
    return pt_data, es_municipalities


# ═══════════════════════════════════════════════════════════════
# SECTION 4: LAND MASK GENERATION
# ═══════════════════════════════════════════════════════════════

def build_land_mask(pt_data, es_municipalities, cfg: RegionConfig,
                    target_w: int = None, target_h: int = None) -> np.ndarray:
    """Build binary land mask from municipality polygons at specified resolution."""
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

    # Remove tiny disconnected islands
    labeled, n = nd_label(land)
    sizes = np.bincount(labeled.ravel())
    if len(sizes) <= 1:
        # Nenhum pixel de terra encontrado — retorna máscara vazia
        return land
    main_lbl = np.argmax(sizes[1:]) + 1
    for lbl in range(1, n + 1):
        if lbl != main_lbl and sizes[lbl] < cfg.island_min_px * (w / cfg.map_w):
            land[labeled == lbl] = False

    return land


# ═══════════════════════════════════════════════════════════════
# SECTION 5: BORDER MASK (PT/ES separation)
# ═══════════════════════════════════════════════════════════════

def build_border_mask(cfg: RegionConfig) -> np.ndarray:
    """Build boolean mask for the 'PT side' of the border."""
    mask = np.zeros((cfg.map_h, cfg.map_w), dtype=bool)
    if not cfg.border_polygon:
        return mask
    
    for y in range(cfg.map_h):
        for x in range(0, cfg.map_w, 3):
            lon, lat = pixel_to_geo(x, y, cfg)
            if point_in_polygon(lon, lat, cfg.border_polygon):
                mask[y, x:min(x+3, cfg.map_w)] = True
    return mask


# ═══════════════════════════════════════════════════════════════
# SECTION 6: BARONY ASSIGNMENT (Voronoi from municipality centroids)
# ═══════════════════════════════════════════════════════════════

def setup_baronies(condados, duchies, kingdoms, cfg):
    """Build barony data arrays and KD-trees for assignment."""
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
    pi = [i for i in range(nb) if bpt[i]]
    ei = [i for i in range(nb) if not bpt[i]]
    tp = cKDTree(bpx[pi]) if pi else None
    te = cKDTree(bpx[ei]) if ei else None
    
    return bars, bpx, bc, bd, bk, pi, ei, tp, te


def rasterize_baronies(pt_data, es_municipalities, bars, pi, ei, tp, te,
                       land, border_mask, cfg) -> np.ndarray:
    """Assign each land pixel to a barony using municipality polygons + KD-tree fallback."""
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


# ═══════════════════════════════════════════════════════════════
# SECTION 7: CLEANUP & SMOOTHING
# ═══════════════════════════════════════════════════════════════

def cleanup_and_smooth(raw: np.ndarray, land: np.ndarray,
                       nb: int, cfg: RegionConfig) -> np.ndarray:
    """Apply median filter, fragment removal, and Gaussian smoothing."""
    # Median filter passes (progressively smaller kernel)
    for i in range(cfg.median_passes):
        ri = raw.astype(np.int32)
        ri[~land] = 9999
        sz = 11 if i < 2 else 9 if i < 4 else 7 if i < 6 else 5
        cl = median_filter(ri, size=sz).astype(np.int16)
        cl[~land] = -1
        v = (raw >= 0) & (cl >= 0) & (cl < nb)
        raw[v] = cl[v]
        raw[~land] = -1
    
    # Remove disconnected fragments per barony
    for bi in range(nb):
        mask = raw == bi
        if not np.any(mask):
            continue
        labeled, n = nd_label(mask)
        if n <= 1:
            continue
        sizes = np.bincount(labeled.ravel())
        ml = np.argmax(sizes[1:]) + 1
        for lbl in range(1, n + 1):
            if lbl != ml and sizes[lbl] < cfg.fragment_min_px:
                frag = labeled == lbl
                dil = binary_dilation(frag, iterations=5)
                bord = dil & ~frag & (raw >= 0) & (raw != bi)
                if np.any(bord):
                    nb_arr = raw[bord]
                    raw[frag] = np.bincount(nb_arr[nb_arr >= 0].astype(int)).argmax()
    
    # Gaussian smoothing
    h, w = raw.shape
    best = np.zeros((h, w), dtype=np.float32)
    result = np.full((h, w), -1, dtype=np.int16)
    for cid in np.unique(raw[raw >= 0]):
        mask = (raw == cid).astype(np.float32)
        mask[~land] = 0
        npx = mask.sum()
        s = cfg.smooth_sigma if npx > 400 else max(1.2, cfg.smooth_sigma * (npx / 400))
        blurred = gaussian_filter(mask, sigma=s)
        blurred[~land] = 0
        bt = blurred > best
        result[bt] = cid
        best[bt] = blurred[bt]
    result[~land] = -1
    
    # Merge tiny baronies
    for bi in range(nb):
        npx = np.sum(result == bi)
        if npx == 0 or npx >= cfg.blob_merge_px:
            continue
        mask = result == bi
        dil = binary_dilation(mask, iterations=5)
        bord = dil & ~mask & (result >= 0) & (result != bi)
        if np.any(bord):
            nb_arr = result[bord]
            result[mask] = np.bincount(nb_arr[nb_arr >= 0].astype(int)).argmax()
    
    return result


# ═══════════════════════════════════════════════════════════════
# SECTION 8: HIERARCHY MAPS
# ═══════════════════════════════════════════════════════════════

def build_hierarchy_maps(result: np.ndarray, bc, bd, bk, nb):
    """Build condado/duchy/kingdom pixel maps from barony result."""
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


# ═══════════════════════════════════════════════════════════════
# SECTION 9: RENDERING
# ═══════════════════════════════════════════════════════════════

def render_map(result, pc, pd, pk, bc, bd, bk, nb, nc, condados, duchies,
               kingdoms, land, cfg, map_type="condado",
               draw_names=True, land_2x=None):
    """Render a visual map at specified level (condado or barony)."""
    h, w = result.shape
    om = ~land
    cd = distance_transform_edt(om)
    dp = np.clip(cd / cfg.ocean_gradient_dist, 0, 1)
    
    # Kingdom color palettes with variation
    dl = list(duchies.keys())
    kl = list(kingdoms.keys())
    k2i = {k: i for i, k in enumerate(kl)}
    
    rng = np.random.default_rng(42)
    vis = np.full((h, w, 3), list(cfg.ocean_far), dtype=np.uint8)
    
    if map_type == "condado":
        for ci in range(nc):
            m = pc == ci
            if not np.any(m):
                continue
            ki = k2i[duchies[condados[ci][4]][0]]
            base = cfg.kingdom_colors.get(ki, (128, 128, 128))
            di_val = bd[np.where(bc == ci)[0][0]] if np.any(bc == ci) else 0
            vd = ((di_val * 23 + 7) % 25) - 12
            vc = ((ci * 17 + 5) % 20) - 10
            vis[m] = [int(np.clip(base[0]+vd+vc+rng.integers(-5,5), 30, 240)),
                      int(np.clip(base[1]+vd*0.6+vc*0.5+rng.integers(-5,5), 30, 240)),
                      int(np.clip(base[2]-vd*0.3+vc*0.3+rng.integers(-5,5), 30, 240))]
    else:  # barony
        for bi in range(nb):
            m = result == bi
            if not np.any(m):
                continue
            ki = bk[bi]; ci = bc[bi]; di = bd[bi]
            base = cfg.kingdom_colors.get(ki, (128, 128, 128))
            vd = ((di*23+7)%25)-12; vc = ((ci*17+5)%20)-10; vb = ((bi*11+3)%12)-6
            vis[m] = [int(np.clip(base[0]+vd+vc+vb, 35, 235)),
                      int(np.clip(base[1]+vd*0.6+vc*0.5+vb, 35, 235)),
                      int(np.clip(base[2]-vd*0.3+vc*0.3+vb, 35, 235))]
    
    # Ocean gradient
    for ch, (near, far) in enumerate(zip(cfg.ocean_near, cfg.ocean_far)):
        vis[:,:,ch][om] = (near + (far - near) * dp)[om].astype(np.uint8)
    
    # Territory borders (only on land pixels)
    iv = Image.fromarray(vis, "RGB")
    src = result if map_type == "barony" else pc
    for dy, dx in [(0,1), (1,0)]:
        a = src[:,:-1] if dy==0 else src[:-1,:]
        b = src[:,1:] if dy==0 else src[1:,:]
        ac = pc[:,:-1] if dy==0 else pc[:-1,:]
        bcc = pc[:,1:] if dy==0 else pc[1:,:]
        ad = pd[:,:-1] if dy==0 else pd[:-1,:]
        bdd = pd[:,1:] if dy==0 else pd[1:,:]
        ak = pk[:,:-1] if dy==0 else pk[:-1,:]
        bkk = pk[:,1:] if dy==0 else pk[1:,:]
        diff = (a != b) & (a >= 0) & (b >= 0)
        yb, xb = np.where(diff)
        for y, x in zip(yb, xb):
            if ak[y,x] != bkk[y,x]:
                co = (5,3,1); wb = 5 if map_type=="condado" else 4
            elif ad[y,x] != bdd[y,x]:
                co = (10,6,3); wb = 3
            elif map_type=="barony" and ac[y,x] != bcc[y,x]:
                co = (22,16,10); wb = 2
            else:
                co = (30,22,15); wb = 1
            if dy == 0:
                for o in range(-(wb//2), wb//2+1):
                    nx_ = x+1+o
                    if 0 <= nx_ < w and land[y, nx_]:
                        iv.putpixel((nx_, y), co)
            else:
                for o in range(-(wb//2), wb//2+1):
                    ny_ = y+1+o
                    if 0 <= ny_ < h and land[ny_, x]:
                        iv.putpixel((x, ny_), co)
    
    vn = np.array(iv)
    
    # Names (condado map only)
    if draw_names and map_type == "condado":
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11)
            font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
        except:
            font = font_sm = ImageFont.load_default()
        
        iv2 = Image.fromarray(vn, "RGB")
        dv = ImageDraw.Draw(iv2)
        for ci in range(nc):
            m = pc == ci
            if not np.any(m):
                continue
            ys, xs = np.where(m)
            cx, cy = int(xs.mean()), int(ys.mean())
            npx = len(ys)
            cname = condados[ci][1]
            ki = k2i[duchies[condados[ci][4]][0]]
            f = font if npx > 1500 else font_sm
            bbox = dv.textbbox((0, 0), cname, font=f)
            tw = bbox[2] - bbox[0]; th = bbox[3] - bbox[1]
            dv.rectangle([cx-tw//2-2, cy-th//2-1, cx+tw//2+2, cy+th//2+1],
                        fill=(0, 0, 0, 180))
            tcol = (255, 255, 230) if ki == 3 else (255, 255, 255)
            dv.text((cx-tw//2, cy-th//2), cname, fill=tcol, font=f)
        vn = np.array(iv2)
    
    # Upscale to 2x with NEAREST (no color bleeding)
    W2, H2 = w * cfg.upscale, h * cfg.upscale
    img_2x = np.array(Image.fromarray(vn).resize((W2, H2), Image.NEAREST))
    
    # Apply 2x land mask + inner coast outline
    if land_2x is not None:
        coast_inner_2x = land_2x & ~binary_erosion(land_2x, iterations=cfg.coast_inner_width)
        img_2x[coast_inner_2x] = list(cfg.coast_inner_color)
        
        # Force ocean outside land at 2x
        cd2 = distance_transform_edt(~land_2x)
        dp2 = np.clip(cd2 / (cfg.ocean_gradient_dist * cfg.upscale), 0, 1)
        not_land = ~land_2x
        for ch, (near, far) in enumerate(zip(cfg.ocean_near, cfg.ocean_far)):
            img_2x[:,:,ch][not_land] = (near + (far - near) * dp2)[not_land].astype(np.uint8)
    
    return img_2x


# ═══════════════════════════════════════════════════════════════
# SECTION 10: LOOKUP MAPS (for Unity hit detection)
# ═══════════════════════════════════════════════════════════════

def generate_lookup_map(result, level_map, n_items, cfg, label="barony"):
    """Generate a color-coded lookup map and color→ID mapping."""
    h, w = result.shape
    lk = np.full((h, w, 3), list(cfg.ocean_far), dtype=np.uint8)
    color_map = {}
    
    for i in range(n_items):
        m = level_map == i if label != "barony" else result == i
        if not np.any(m):
            continue
        # Generate unique deterministic color
        r = (i * 37 + 50) % 256
        g = (i * 73 + 80) % 256
        b = (i * 113 + 30) % 256
        lk[m] = [r, g, b]
        color_map[f"{r},{g},{b}"] = i
    
    return lk, color_map


# ═══════════════════════════════════════════════════════════════
# SECTION 11: METADATA EXPORT (for Unity)
# ═══════════════════════════════════════════════════════════════

def export_metadata(condados, duchies, kingdoms, bars, result, pc, cfg):
    """Export territory metadata as JSON for Unity consumption."""
    dl = list(duchies.keys())
    kl = list(kingdoms.keys())
    k2i = {k: i for i, k in enumerate(kl)}
    
    metadata = {
        "region": cfg.name,
        "map_size": [cfg.map_w * cfg.upscale, cfg.map_h * cfg.upscale],
        "bounds": {
            "lon_min": cfg.lon_min, "lon_max": cfg.lon_max,
            "lat_min": cfg.lat_min, "lat_max": cfg.lat_max,
        },
        "kingdoms": {k: v for k, v in kingdoms.items()},
        "duchies": {k: {"kingdom": v[0], "name": v[1]} for k, v in duchies.items()},
        "condados": [],
        "baronies": [],
    }
    
    for ci, c in enumerate(condados):
        npx = int(np.sum(pc == ci))
        if npx == 0:
            continue
        ys, xs = np.where(pc == ci)
        metadata["condados"].append({
            "id": c[0],
            "name": c[1],
            "lon": c[2], "lat": c[3],
            "duchy": c[4],
            "kingdom": duchies[c[4]][0],
            "pixel_center": [int(xs.mean()), int(ys.mean())],
            "pixel_count": npx,
            "baronies": [b[0] for b in c[5]],
        })
    
    for bi, b in enumerate(bars):
        npx = int(np.sum(result == bi))
        if npx == 0:
            continue
        metadata["baronies"].append({
            "name": b['name'],
            "condado_idx": b['condado_idx'],
            "duchy": b['duchy_id'],
            "pixel_count": npx,
        })
    
    return metadata


# ═══════════════════════════════════════════════════════════════
# SECTION 12: MOUNTAINS & RIVERS
# ═══════════════════════════════════════════════════════════════

def render_mountains(cfg, land_2x):
    """Render mountain mask from polygon data."""
    if not cfg.mountain_river_json or not os.path.exists(cfg.mountain_river_json):
        return None
    
    with open(cfg.mountain_river_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    mountains = data.get('mountains', {})
    if not mountains:
        return None
    
    W2 = cfg.map_w * cfg.upscale
    H2 = cfg.map_h * cfg.upscale
    mask = np.zeros((H2, W2), dtype=bool)
    
    for key, mtn in mountains.items():
        polygon = mtn.get('polygon', [])
        if not polygon:
            continue
        pts = [geo_to_pixel(lo, la, cfg, W2, H2) for lo, la in polygon]
        img = Image.new("L", (W2, H2), 0)
        ImageDraw.Draw(img).polygon(pts, fill=255)
        mask |= (np.array(img) > 0)
    
    # Only keep mountain pixels that are on land
    if land_2x is not None:
        mask &= land_2x
    
    return mask


def render_rivers(cfg):
    """Render river lines as transparent PNG overlay."""
    if not cfg.mountain_river_json or not os.path.exists(cfg.mountain_river_json):
        return None
    
    with open(cfg.mountain_river_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    rivers = data.get('rivers', {})
    if not rivers:
        return None
    
    W2 = cfg.map_w * cfg.upscale
    H2 = cfg.map_h * cfg.upscale
    img = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    rc = cfg.river_color
    for key, river in rivers.items():
        coords = river.get('coords', [])
        if len(coords) < 2:
            continue
        pts = [geo_to_pixel(lo, la, cfg, W2, H2) for lo, la in coords]
        draw.line(pts, fill=(rc[0], rc[1], rc[2], 200),
                 width=cfg.river_width * cfg.upscale)
    
    return img


# ═══════════════════════════════════════════════════════════════
# SECTION 13: TERRAIN LOOKUP (terrain_lookup.png + terrain_types.json)
# ═══════════════════════════════════════════════════════════════

# Terrain type definitions: name → (R, G, B) + game stats.
# Exactly 4 types derived from geographic polygon data — no synthetic noise.
# Forest and hill are NOT generated here; they require a separate data source
# (e.g. CORINE land cover) and are out of scope for the current pipeline.
_TERRAIN_TYPES: dict[str, dict] = {
    "ocean":    {"rgb": (45,  90,  140), "movement": 0,   "defense": 0,   "attack": 0},
    "coast":    {"rgb": (100, 160, 180), "movement": 0.9, "defense": 1.0, "attack": 1.0},
    "plain":    {"rgb": (180, 200, 120), "movement": 1.0, "defense": 1.0, "attack": 1.0},
    "mountain": {"rgb": (100,  85,  65), "movement": 0.4, "defense": 1.8, "attack": 0.6},
}


def render_mountains_from_data(
    data: dict,
    cfg: RegionConfig,
    land_mask: np.ndarray,
    target_w: int,
    target_h: int,
) -> np.ndarray:
    """Rasterize mountain polygons from pre-loaded JSON data into a boolean mask.

    This is the testable core of render_mountains() — it accepts data already
    loaded from JSON so tests can inject fixture data without touching the
    filesystem.

    Args:
        data: dict with key "mountains" → {key: {polygon: [[lon,lat], ...]}}
        cfg: RegionConfig for geo_to_pixel projection.
        land_mask: boolean (target_h, target_w) land mask — mountains are
                   clipped to land (no ocean bleed).
        target_w, target_h: pixel dimensions for the output mask.

    Returns:
        boolean (target_h, target_w) ndarray — True where mountain polygons fall
        on land. Returns all-False array if no mountain polygons found.
    """
    mask = np.zeros((target_h, target_w), dtype=bool)
    mountains = data.get("mountains", {})
    for key, mtn in mountains.items():
        polygon = mtn.get("polygon", [])
        if len(polygon) < 3:
            continue
        pts = [geo_to_pixel(lo, la, cfg, target_w, target_h) for lo, la in polygon]
        img = Image.new("L", (target_w, target_h), 0)
        ImageDraw.Draw(img).polygon(pts, fill=255)
        mask |= (np.array(img) > 0)
    # Clip to land — mountains must not bleed into ocean.
    if land_mask is not None:
        mask &= land_mask
    return mask


def generate_terrain_lookup(
    land: np.ndarray,
    cfg: RegionConfig,
    mtn_mask: np.ndarray | None = None,
    rivers_img=None,
) -> tuple[np.ndarray, dict]:
    """Generate terrain_lookup pixel map and terrain_types metadata.

    Classification uses hand-curated geographic polygon data (mountain ranges
    from mountain_river_data.json) rather than synthetic noise. The palette is
    exactly 4 types: ocean, coast, plain, mountain.

    Classification rules (applied in priority order, highest last = wins):
      1. ocean    — pixel not in land mask (baseline fill)
      2. plain    — all land pixels
      3. coast    — land pixel within 8px of ocean boundary (distance_transform)
      4. mountain — pixel in mtn_mask, intersected with land (highest priority)

    Forest and hill types are NOT generated here. They require a separate data
    source (e.g. CORINE land cover) and are planned as a future extension.

    Args:
        land: boolean (H, W) array — True = land pixel.
        cfg: RegionConfig (for dimensions).
        mtn_mask: optional boolean mountain mask. May be at 2x resolution
                  (shape H*upscale × W*upscale) — downscaled to 1x via NEAREST.
                  If None, no mountain pixels are painted.
        rivers_img: unused (rivers are a visual-only overlay in rivers_overlay.png,
                    not encoded in the terrain type lookup).

    Returns:
        (lookup_arr, terrain_types_dict)
        lookup_arr: uint8 (H, W, 3) RGB array — each pixel colored by terrain type.
        terrain_types_dict: JSON-serialisable dict mapping "R,G,B" →
                            {type, movement, defense, attack}.
    """
    H, W = land.shape
    lookup = np.zeros((H, W, 3), dtype=np.uint8)

    # Step 1 — Ocean baseline (pixels outside land mask).
    lookup[~land] = _TERRAIN_TYPES["ocean"]["rgb"]

    # Step 2 — Plain: all land pixels (overridden by coast and mountain below).
    lookup[land] = _TERRAIN_TYPES["plain"]["rgb"]

    # Step 3 — Coast mask: land pixels within 8px of ocean boundary.
    # distance_transform_edt returns 0 at ocean pixels and increases inland.
    # Land pixels with small EDT value are close to ocean → coast.
    from scipy.ndimage import distance_transform_edt as _dte
    dist_from_ocean = _dte(land)  # 0 at ocean, positive on land
    coast_mask = land & (dist_from_ocean <= 8)
    if np.any(coast_mask):
        lookup[coast_mask] = _TERRAIN_TYPES["coast"]["rgb"]

    # Step 4 — Mountain mask (downscale from 2x to 1x via NEAREST if necessary).
    # NEVER use BICUBIC or BILINEAR — they spread mountain pixels into ocean.
    mtn_1x: np.ndarray | None = None
    if mtn_mask is not None:
        mh, mw = mtn_mask.shape
        if mh == H and mw == W:
            mtn_1x = mtn_mask
        else:
            # Downscale via integer stride (NEAREST equivalent for boolean masks).
            scale_h = mh // H
            scale_w = mw // W
            if scale_h >= 1 and scale_w >= 1:
                mtn_1x = mtn_mask[::scale_h, ::scale_w][:H, :W]

    # Mountains override coast and plain — only where mountain is on land.
    if mtn_1x is not None:
        mtn_land = mtn_1x & land
        if np.any(mtn_land):
            lookup[mtn_land] = _TERRAIN_TYPES["mountain"]["rgb"]

    # Step 5 — Build terrain_types.json: emit only the 4 canonical types.
    # Each entry: "R,G,B" → {type, movement, defense, attack}.
    terrain_types: dict[str, dict] = {}
    for type_name, td in _TERRAIN_TYPES.items():
        r, g, b = td["rgb"]
        key = f"{r},{g},{b}"
        terrain_types[key] = {
            "type":     type_name,
            "movement": td["movement"],
            "defense":  td["defense"],
            "attack":   td["attack"],
        }

    return lookup, terrain_types


# ═══════════════════════════════════════════════════════════════
# SECTION 14: MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════

def generate_maps(cfg: RegionConfig = None, territory_module: str = "territory_data_v3",
                  draw_names: bool = True):
    """
    Main pipeline: generates all map files for Unity.
    
    Call this function to generate everything:
        generate_maps(iberia_config())
    
    For a different region (e.g., England):
        cfg = RegionConfig(name="england", lon_min=-6, lon_max=2, ...)
        generate_maps(cfg, territory_module="territory_data_england")
    """
    if cfg is None:
        cfg = iberia_config()
    
    os.makedirs(cfg.output_dir, exist_ok=True)
    
    print(f"{'='*60}")
    print(f"MAP GENERATOR — {cfg.name.upper()}")
    print(f"{'='*60}")
    
    # 1. Load data
    print("[1] Loading territory data...")
    kingdoms, duchies, condados = load_territory_data(territory_module)
    nc = len(condados)
    
    print("[2] Loading municipalities...")
    pt_data, es_municipalities = load_municipalities(cfg)
    
    # 2. Build land mask at 1x
    print("[3] Building land mask (1x)...")
    land = build_land_mask(pt_data, es_municipalities, cfg)
    print(f"    Land: {np.sum(land):,} px")
    
    # 3. Build land mask at 2x (for post-upscale masking)
    print("[4] Building land mask (2x)...")
    W2, H2 = cfg.map_w * cfg.upscale, cfg.map_h * cfg.upscale
    land_2x = build_land_mask(pt_data, es_municipalities, cfg, W2, H2)
    print(f"    Land 2x: {np.sum(land_2x):,} px")
    
    # 4. Border mask
    print("[5] Building border mask...")
    border_mask = build_border_mask(cfg)
    
    # 5. Setup baronies
    print("[6] Setting up baronies...")
    bars, bpx, bc, bd, bk, pi, ei, tp, te = setup_baronies(
        condados, duchies, kingdoms, cfg)
    nb = len(bars)
    
    # 6. Rasterize
    print("[7] Rasterizing baronies...")
    raw = rasterize_baronies(pt_data, es_municipalities, bars,
                             pi, ei, tp, te, land, border_mask, cfg)
    
    # 7. Cleanup & smooth
    print("[8] Cleanup & smoothing...")
    result = cleanup_and_smooth(raw, land, nb, cfg)
    
    # 8. Hierarchy
    print("[9] Building hierarchy...")
    pc, pd, pk = build_hierarchy_maps(result, bc, bd, bk, nb)
    land = result >= 0  # update land to match result
    
    na = sum(1 for i in range(nb) if np.sum(result == i) > 0)
    nc_active = sum(1 for i in range(nc) if np.sum(pc == i) > 0)
    print(f"    Active: {na} baronies, {nc_active} condados")
    
    # 9. Render visual maps
    print("[10] Rendering visual maps...")
    for mt in ["condado", "barony"]:
        print(f"     {mt}...")
        img = render_map(result, pc, pd, pk, bc, bd, bk, nb, nc,
                        condados, duchies, kingdoms, land, cfg,
                        map_type=mt, draw_names=(draw_names and mt == "condado"),
                        land_2x=land_2x)
        Image.fromarray(img).save(f"{cfg.output_dir}/visual_{mt}.png")
    
    # 10. Lookup maps
    print("[11] Generating lookup maps...")
    for label, level_map, n_items in [("barony", result, nb), ("condado", pc, nc)]:
        lk, cmap = generate_lookup_map(result, level_map, n_items, cfg, label)
        Image.fromarray(lk).save(f"{cfg.output_dir}/lookup_{label}.png")
        with open(f"{cfg.output_dir}/lookup_{label}_colors.json", 'w', encoding='utf-8') as f:
            json.dump(cmap, f, indent=2)
    
    # 11. Metadata
    print("[12] Exporting metadata...")
    metadata = export_metadata(condados, duchies, kingdoms, bars, result, pc, cfg)
    with open(f"{cfg.output_dir}/territory_metadata.json", 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    # 12. Mountains
    print("[13] Mountains...")
    mtn_mask = render_mountains(cfg, land_2x)
    if mtn_mask is not None:
        # Save as white-on-black mask (white = impassable)
        mtn_img = np.zeros((H2, W2), dtype=np.uint8)
        mtn_img[mtn_mask] = 255
        Image.fromarray(mtn_img).save(f"{cfg.output_dir}/mountains_mask.png")
        print(f"    Mountain pixels: {np.sum(mtn_mask):,}")
        
        # Also apply mountains to visual maps
        for mt in ["condado", "barony"]:
            vis = np.array(Image.open(f"{cfg.output_dir}/visual_{mt}.png"))
            mc = cfg.mountain_color_visual
            noise = np.random.default_rng(42).integers(
                -cfg.mountain_noise, cfg.mountain_noise, (H2, W2))
            for ch in range(3):
                vis[:,:,ch][mtn_mask] = np.clip(
                    mc[ch] + noise[mtn_mask], 30, 220).astype(np.uint8)
            Image.fromarray(vis).save(f"{cfg.output_dir}/visual_{mt}.png")
    
    # 13. Rivers — DISCONNECTED from pipeline on 2026-04-17.
    # render_rivers() remains available in this module for future reactivation.
    # See .planning/debug/resolved/terrain-real-geography.md (Rivers Disconnect addendum).
    rivers_img = None

    # 14. Terrain lookup (terrain_lookup.png + terrain_types.json)
    print("[15] Terrain lookup...")
    terrain_arr, terrain_types = generate_terrain_lookup(
        land, cfg, mtn_mask=mtn_mask, rivers_img=rivers_img
    )
    Image.fromarray(terrain_arr).save(f"{cfg.output_dir}/terrain_lookup.png")
    with open(f"{cfg.output_dir}/terrain_types.json", 'w', encoding='utf-8') as f:
        json.dump(terrain_types, f, indent=2)
    unique_types = len({tuple(terrain_arr[land][i]) for i in range(0, int(land.sum()), max(1, int(land.sum())//1000))})
    print(f"    Terrain types written: {len(terrain_types)} types, ~{unique_types} unique colors sampled")

    print(f"\n{'='*60}")
    print(f"DONE — {na} baronies, {nc_active} condados")
    print(f"Output: {cfg.output_dir}/")
    print(f"  visual_condado.png   — condado visual map")
    print(f"  visual_barony.png    — barony visual map")
    print(f"  lookup_condado.png   — condado hit detection")
    print(f"  lookup_barony.png    — barony hit detection")
    print(f"  lookup_*_colors.json — color→ID mapping")
    print(f"  territory_metadata.json — full hierarchy")
    print(f"  mountains_mask.png   — impassable terrain")
    print(f"{'='*60}")


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Default: generate Iberia maps
    cfg = iberia_config()
    generate_maps(cfg, territory_module="territory_data_v3", draw_names=True)
