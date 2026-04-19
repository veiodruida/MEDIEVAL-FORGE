"""D-02 data dependency: emit baronies.geojson.

Read-back approach (same vendored-black-box constraint as territories_geojson).
Inputs from disk: lookup_barony.png, lookup_barony_colors.json, territory_metadata.json.
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

from .paths import project_dir
from .territories_geojson import _ProjCfg, _pixel_polygon_to_lonlat

logger = logging.getLogger(__name__)


def build_baronies_geojson(
    project_id: str,
    pb: np.ndarray,
    baronies: list[dict],   # [{ "name": "B_X", "condado_idx": int, "duchy": ..., "pixel_count": int }]
    condados: list[list[Any]],
    cfg: _ProjCfg,
    barony_colors: dict[str, str],   # name -> "#rrggbb"
) -> Path:
    """Write baronies.geojson with per-barony polygon + condado_id + fill."""
    out_dir = project_dir(project_id) / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)

    pb32 = pb.astype(np.int32)
    pb_H, pb_W = pb32.shape  # actual raster dims — lookup PNG is map_w × map_h (NOT upscaled)
    shapes_per_idx: dict[int, list] = {}
    for geom, idx in rasterio.features.shapes(pb32, mask=(pb32 >= 0)):
        i = int(idx)
        shapes_per_idx.setdefault(i, []).append(shape(geom))

    features: list[dict] = []
    for bi, b in enumerate(baronies):
        geoms = shapes_per_idx.get(bi, [])
        if not geoms:
            continue
        u = unary_union(geoms)
        lonlat = _pixel_polygon_to_lonlat(mapping(u), cfg, pb_W, pb_H)
        condado_id = condados[b["condado_idx"]][0] if 0 <= b["condado_idx"] < len(condados) else ""
        features.append({
            "type": "Feature",
            "id": b["name"],
            "geometry": lonlat,
            "properties": {
                "id": b["name"],
                "name": b["name"],
                "condado_id": condado_id,
                "fill": barony_colors.get(b["name"], "#888888"),
            },
        })

    out_path = out_dir / "baronies.geojson"
    out_path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return out_path


def emit_baronies_from_disk(project_id: str, generated_dir: Path, cfg: _ProjCfg) -> Path:
    """Read-back orchestrator. Parses the REAL map_generator lookup format
    ``{"r,g,b": idx}`` (see lib/map_generator.py SECTION 10). DO NOT change to
    hex parsing — that schema does not exist on disk.

    Emits two artifacts:
      * ``baronies.geojson`` (existing contract, via build_baronies_geojson)
      * ``barony_colors.json`` sidecar — ``{barony_name: "#rrggbb"}`` for the
        frontend. The Unity-consumed ``lookup_barony_colors.json`` stays
        untouched (D-04 black-box preserved).
    """
    from PIL import Image
    meta = json.loads((generated_dir / "territory_metadata.json").read_text())
    baronies = meta.get("baronies", [])
    condados = [
        [c["id"], c["name"], c["lon"], c["lat"], c.get("duchy", ""), c.get("baronies", [])]
        for c in meta["condados"]
    ]
    colors_raw = json.loads((generated_dir / "lookup_barony_colors.json").read_text())

    img = np.array(Image.open(generated_dir / "lookup_barony.png").convert("RGB"))
    H, W, _ = img.shape
    pb = np.full((H, W), -1, dtype=np.int32)

    sidecar: dict[str, str] = {}
    barony_colors_hex: dict[str, str] = {}
    for rgb_key, idx_val in colors_raw.items():
        parts = rgb_key.split(",")
        if len(parts) != 3:
            raise ValueError(
                f"lookup_barony_colors.json malformed key {rgb_key!r}; expected 'r,g,b'"
            )
        r, g, blue = (int(p) for p in parts)
        idx = int(idx_val)
        if idx < 0 or idx >= len(baronies):
            logger.warning(
                "lookup_barony_colors.json idx %d out of range (len=%d) — skipping",
                idx, len(baronies),
            )
            continue
        mask = (img[:, :, 0] == r) & (img[:, :, 1] == g) & (img[:, :, 2] == blue)
        pb[mask] = idx
        hex_str = f"#{r:02x}{g:02x}{blue:02x}"
        sidecar[baronies[idx]["name"]] = hex_str
        barony_colors_hex[baronies[idx]["name"]] = hex_str

    (generated_dir / "barony_colors.json").write_text(json.dumps(sidecar))
    # Pass the hex map to build_baronies_geojson (it expects name -> "#hex")
    return build_baronies_geojson(project_id, pb, baronies, condados, cfg, barony_colors_hex)
