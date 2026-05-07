"""Verbatim port of inicio/map_generator.py §11 (METADATA EXPORT for Unity).

Single function `export_metadata(condados, duchies, kingdoms, bars, result, pc, cfg)`
returning the territory_metadata.json contents as a dict.

Per PREFLIGHT.md Q8 verdict: `original_idx` ABSENT in deployed
territory_metadata.json (0/92 condados, 0/251 baronies). Per D-09 (deployed
wins) the port reproduces inicio verbatim — no `original_idx` emitted.
CLAUDE.md rule #4 (Nájera-bug fix) is deferred to whichever later phase
aligns the schema with the rule.

P-14: `pixel_center` stays in numpy Y-down coords. DO NOT flip Y for Unity.
P-16: condados are compacted (skip when npx == 0) — preserved verbatim
(unlike lookup.py's generate_lookup_map which preserves index gaps).
"""

from __future__ import annotations

import numpy as np

from .contracts import RegionConfig


def export_metadata(condados, duchies, kingdoms, bars, result: np.ndarray,
                    pc: np.ndarray, cfg: RegionConfig) -> dict:
    """Export territory metadata as JSON for Unity consumption.

    Verbatim port of inicio/map_generator.py:680-726 (D-01).

    Per PREFLIGHT.md Q8 verdict (D-09 deployed-wins): `original_idx` ABSENT —
    no per-condado/per-barony original_idx field emitted (verbatim inicio).
    """
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
            # P-14: numpy Y-down coords; DO NOT flip Y for Unity.
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


__all__ = ["export_metadata"]
