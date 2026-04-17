"""D-02 data dependency: emit baronies.geojson.

Read-back approach (same vendored-black-box constraint as territories_geojson).
Inputs from disk: lookup_barony.png, lookup_barony_colors.json, territory_metadata.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import rasterio.features
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from .paths import project_dir
from .territories_geojson import _ProjCfg, _pixel_polygon_to_lonlat


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
        lonlat = _pixel_polygon_to_lonlat(mapping(u), cfg)
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
    """Read-back orchestrator. Resolves pb + baronies from disk, calls builder."""
    from PIL import Image
    meta = json.loads((generated_dir / "territory_metadata.json").read_text())
    baronies = meta.get("baronies", [])
    condados = [
        [c["id"], c["name"], c["lon"], c["lat"], c.get("duchy", ""), c.get("baronies", [])]
        for c in meta["condados"]
    ]
    barony_colors = json.loads((generated_dir / "lookup_barony_colors.json").read_text())
    name_to_bi = {b["name"]: i for i, b in enumerate(baronies)}
    img = np.array(Image.open(generated_dir / "lookup_barony.png").convert("RGB"))
    H, W, _ = img.shape
    pb = np.full((H, W), -1, dtype=np.int32)
    for bname, hexstr in barony_colors.items():
        r = int(hexstr[1:3], 16)
        g = int(hexstr[3:5], 16)
        b = int(hexstr[5:7], 16)
        mask = (img[:, :, 0] == r) & (img[:, :, 1] == g) & (img[:, :, 2] == b)
        bi = name_to_bi.get(bname)
        if bi is not None:
            pb[mask] = bi
    return build_baronies_geojson(project_id, pb, baronies, condados, cfg, barony_colors)
