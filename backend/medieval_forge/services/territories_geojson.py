"""CANVAS-01 data dependency: emit territories.geojson with per-condado
polygon + neighbors adjacency.

VENDORED BLACK BOX CONSTRAINT: inicio/map_generator.py is not modified.
This module runs AFTER generate_maps() has written its files to disk and
reconstructs the condado raster from lookup_condado.png + lookup_condado_colors.json.

T-PATH: project_id is validated via paths.project_dir() (ValueError on bad UUID).
V5 input validation: filename 'territories.geojson' is appended to
GENERATED_FILE_WHITELIST in generator.py; the existing /preview/{filename}
route handles the actual serving — no new route is introduced.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import rasterio.features
from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

from .paths import project_dir

logger = logging.getLogger(__name__)


class _ProjCfg:
    """Minimal cfg-like shim holding the fields we need for lon/lat inversion.
    Populated from territory_metadata.json + lookup_condado.png shape.
    """
    __slots__ = ("lon_min", "lon_max", "lat_min", "lat_max", "map_w", "map_h", "upscale", "lon_scale")

    def __init__(self, lon_min, lon_max, lat_min, lat_max, map_w, map_h, upscale, lon_scale):
        self.lon_min = lon_min
        self.lon_max = lon_max
        self.lat_min = lat_min
        self.lat_max = lat_max
        self.map_w = map_w
        self.map_h = map_h
        self.upscale = upscale
        self.lon_scale = lon_scale


def _pixel_polygon_to_lonlat(geom: dict, cfg: _ProjCfg, W: int, H: int) -> dict:
    """Apply the inverse of map_generator.geo_to_pixel to every vertex.

    W and H must be the actual pixel dimensions of the raster array that
    rasterio.features.shapes was run on (i.e. pc.shape[1] and pc.shape[0]).
    These come from lookup_condado.png / lookup_barony.png which are written at
    map_w × map_h (NOT map_w*upscale × map_h*upscale) by map_generator.py.
    Do NOT substitute cfg.map_w * cfg.upscale here — that is the upscaled
    terrain resolution, not the lookup raster resolution.
    """
    span = (cfg.lon_max - cfg.lon_min) * cfg.lon_scale

    def px_to_lonlat(px: float, py: float) -> tuple[float, float]:
        lon = px / W * span / cfg.lon_scale + cfg.lon_min
        lat = cfg.lat_max - py / H * (cfg.lat_max - cfg.lat_min)
        return (lon, lat)

    def ring(coords):
        return [list(px_to_lonlat(x, y)) for x, y in coords]

    if geom["type"] == "Polygon":
        return {"type": "Polygon", "coordinates": [ring(r) for r in geom["coordinates"]]}
    if geom["type"] == "MultiPolygon":
        return {
            "type": "MultiPolygon",
            "coordinates": [[ring(r) for r in poly] for poly in geom["coordinates"]],
        }
    raise ValueError(f"unsupported geometry type: {geom['type']}")


def build_territories_geojson(
    project_id: str,
    pc: np.ndarray,
    condados: list[list[Any]],
    cfg: _ProjCfg,
) -> Path:
    """Write territories.geojson with per-condado polygon + neighbors."""
    out_dir = project_dir(project_id) / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)

    pc32 = pc.astype(np.int32)
    pc_H, pc_W = pc32.shape  # actual raster dims — lookup PNG is map_w × map_h (NOT upscaled)
    shapes_per_idx: dict[int, list] = {}
    for geom, idx in rasterio.features.shapes(pc32, mask=(pc32 >= 0)):
        i = int(idx)
        shapes_per_idx.setdefault(i, []).append(shape(geom))

    features: list[dict] = []
    unioned: dict[int, Any] = {}
    for ci, c in enumerate(condados):
        geoms = shapes_per_idx.get(ci, [])
        if not geoms:
            continue
        u = unary_union(geoms)
        unioned[ci] = u
        lonlat_geojson = _pixel_polygon_to_lonlat(mapping(u), cfg, pc_W, pc_H)
        features.append({
            "type": "Feature",
            "id": c[0],
            "geometry": lonlat_geojson,
            "properties": {"id": c[0], "name": c[1], "neighbors": []},
        })

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

    out_path = out_dir / "territories.geojson"
    out_path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return out_path


def emit_territories_from_disk(
    project_id: str,
    generated_dir: Path,
    cfg: _ProjCfg,
) -> Path:
    """Read-back orchestrator. Parses the REAL map_generator lookup format
    ``{"r,g,b": idx}`` (see lib/map_generator.py SECTION 10, generate_lookup_map).
    DO NOT change to hex parsing — that schema does not exist on disk.

    Emits two artifacts:
      * ``territories.geojson`` (existing contract, via build_territories_geojson)
      * ``condado_colors.json`` sidecar — ``{condado_id: "#rrggbb"}`` for the
        frontend. The Unity-consumed ``lookup_condado_colors.json`` stays
        untouched (D-04 black-box preserved).
    """
    meta = json.loads((generated_dir / "territory_metadata.json").read_text())
    condados_meta = meta["condados"]  # list of dicts per export_metadata
    # Rehydrate the tuple/list shape build_territories_geojson expects:
    # [id, name, lon, lat, duchy, baronies]
    condados = [
        [c["id"], c["name"], c["lon"], c["lat"], c.get("duchy", ""), c.get("baronies", [])]
        for c in condados_meta
    ]
    colors_raw = json.loads((generated_dir / "lookup_condado_colors.json").read_text())

    from PIL import Image
    img = np.array(Image.open(generated_dir / "lookup_condado.png").convert("RGB"))
    H, W, _ = img.shape
    pc = np.full((H, W), -1, dtype=np.int32)

    sidecar: dict[str, str] = {}
    for rgb_key, idx_val in colors_raw.items():
        parts = rgb_key.split(",")
        if len(parts) != 3:
            raise ValueError(
                f"lookup_condado_colors.json malformed key {rgb_key!r}; expected 'r,g,b'"
            )
        r, g, b = (int(p) for p in parts)
        idx = int(idx_val)
        if idx < 0 or idx >= len(condados):
            logger.warning(
                "lookup_condado_colors.json idx %d out of range (len=%d) — skipping",
                idx, len(condados),
            )
            continue
        mask = (img[:, :, 0] == r) & (img[:, :, 1] == g) & (img[:, :, 2] == b)
        pc[mask] = idx
        # Build sidecar: condado id -> #rrggbb (for frontend fills)
        sidecar[condados[idx][0]] = f"#{r:02x}{g:02x}{b:02x}"

    (generated_dir / "condado_colors.json").write_text(json.dumps(sidecar))
    return build_territories_geojson(project_id, pc, condados, cfg)
