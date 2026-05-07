"""Verbatim port of inicio/map_generator.py §10 (LOOKUP MAPS for Unity hit detection).

Single function `generate_lookup_map(result, level_map, n_items, cfg, label)`
emitting (lookup_image_array, color_map_dict).

Critical (P-13 — deterministic RGB hash):
    r = (i * 37 + 50) % 256
    g = (i * 73 + 80) % 256
    b = (i * 113 + 30) % 256

Two runs over the same n_items produce identical (r,g,b) triples.

Per P-16, this function does NOT skip empty condados — it preserves indices
(unlike `export_metadata` in export.py which compacts).
"""

from __future__ import annotations

import numpy as np

from .contracts import RegionConfig


def generate_lookup_map(result: np.ndarray, level_map: np.ndarray, n_items: int,
                        cfg: RegionConfig, label: str = "barony"):
    """Generate a color-coded lookup map and color→ID mapping.

    Verbatim port of inicio/map_generator.py:656-673 (D-01).
    """
    h, w = result.shape
    lk = np.full((h, w, 3), list(cfg.ocean_far), dtype=np.uint8)
    color_map = {}

    for i in range(n_items):
        m = level_map == i if label != "barony" else result == i
        if not np.any(m):
            continue
        # Generate unique deterministic color (P-13)
        r = (i * 37 + 50) % 256
        g = (i * 73 + 80) % 256
        b = (i * 113 + 30) % 256
        lk[m] = [r, g, b]
        color_map[f"{r},{g},{b}"] = i

    return lk, color_map


__all__ = ["generate_lookup_map"]
