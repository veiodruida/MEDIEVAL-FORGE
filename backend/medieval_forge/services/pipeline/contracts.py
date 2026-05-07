"""RegionConfig dataclass + shared coordinate transforms.

Verbatim port of inicio/map_generator.py §1 (lines 52-112) plus §2 transform
signatures. Bodies for the §2 transforms (geo_to_pixel, pixel_to_geo,
point_in_polygon) are filled by Plan 02 from inicio lines 152-185.

Per RESEARCH §2.b and Open Q1, RegionConfig is a stdlib `@dataclass` to
minimise drift from inicio (which also uses `@dataclass`). Phase 04 may
revisit if slider validation needs emerge.

The 5 NEW fields the port adds (per RESEARCH §2.a "New fields"):
  - kingdoms / duchies / condados (D-14: territory data lives on cfg)
  - rng_seed (CLAUDE.md: np.random.default_rng(cfg.rng_seed) replaces inicio's
    hardcoded 42 at lines 537 + 904)
  - draw_names (D-03: generate_maps(draw_names=) becomes cfg.draw_names;
    default False per PREFLIGHT.md Q10 verdict)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class RegionConfig:
    """Configuration for a map region. Change these to map a different area."""

    name: str = "iberia"

    # Map dimensions (1x render resolution)
    map_w: int = 1920
    map_h: int = 1080
    upscale: int = 2  # final output = map_w*upscale x map_h*upscale

    # Geographic bounds (WGS84)
    lon_min: float = -13.2
    lon_max: float = 8.2
    lat_min: float = 35.4
    lat_max: float = 44.6

    # Projection correction (cos of center latitude); derived in __post_init__
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
    island_min_px: int = 300       # remove islands smaller than this
    fragment_min_px: int = 600     # merge barony fragments smaller than this
    blob_merge_px: int = 200       # merge final baronies smaller than this
    median_passes: int = 8         # number of median filter passes
    smooth_sigma: float = 3.0      # Gaussian smoothing sigma (valid range [3.0, 4.5])

    # Mountain config
    mountain_threshold: int = 1500
    mountain_color_visual: tuple = (118, 100, 80)
    mountain_color_lookup: tuple = (50, 45, 40)
    mountain_noise: int = 20

    # River config
    river_color: tuple = (74, 144, 217)
    river_width: int = 2

    # ---- New fields the port introduces (not in inicio) ------------------

    # D-14: territory data lives directly on cfg
    kingdoms: dict = field(default_factory=dict)
    duchies: dict = field(default_factory=dict)
    condados: list = field(default_factory=list)

    # CLAUDE.md determinism: np.random.default_rng(cfg.rng_seed) replaces
    # inicio's hardcoded 42 at lines 537 + 904
    rng_seed: int = 42

    # D-03 + PREFLIGHT.md Q10: deployed visual_condado.png has no labels.
    draw_names: bool = False

    def __post_init__(self):
        if self.lon_scale is None:
            center_lat = (self.lat_min + self.lat_max) / 2
            self.lon_scale = math.cos(math.radians(center_lat))


# ═══════════════════════════════════════════════════════════════
# SECTION 2 transform signatures — bodies filled by Plan 02 (inicio:149-185)
# ═══════════════════════════════════════════════════════════════


def geo_to_pixel(lon: float, lat: float, cfg: RegionConfig,
                 w: int = None, h: int = None) -> Tuple[int, int]:
    """Convert WGS84 lon/lat to pixel coordinates.

    Verbatim port of inicio/map_generator.py:152-167 (D-01).
    """
    w = w or cfg.map_w
    h = h or cfg.map_h
    span = (cfg.lon_max - cfg.lon_min) * cfg.lon_scale
    px = int((lon - cfg.lon_min) * cfg.lon_scale / span * w)
    py = int((1.0 - (lat - cfg.lat_min) / (cfg.lat_max - cfg.lat_min)) * h)
    return (px, py)


def pixel_to_geo(px: int, py: int, cfg: RegionConfig,
                 w: int = None, h: int = None) -> Tuple[float, float]:
    """Convert pixel coordinates to WGS84 lon/lat.

    Verbatim port of inicio/map_generator.py:170-178 (D-01).
    """
    w = w or cfg.map_w
    h = h or cfg.map_h
    span = (cfg.lon_max - cfg.lon_min) * cfg.lon_scale
    lon = px / w * span / cfg.lon_scale + cfg.lon_min
    lat = cfg.lat_max - py / h * (cfg.lat_max - cfg.lat_min)
    return (lon, lat)


def point_in_polygon(x: float, y: float, polygon: list) -> bool:
    """Ray-casting point-in-polygon test.

    Verbatim port of inicio/map_generator.py:181-185 (D-01).
    """
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


__all__ = [
    "RegionConfig",
    "geo_to_pixel",
    "pixel_to_geo",
    "point_in_polygon",
]
