"""Verbatim port of inicio/map_generator.py §5 (BORDER MASK / PT-ES separation).

P-10: the inner loop strides every 3 pixels (`range(0, cfg.map_w, 3)`) — copy
verbatim. Stride 1 is 9× slower; stride 5+ misses curvature on the 38/40-point
border polygon.
"""

from __future__ import annotations

import numpy as np

from .contracts import RegionConfig, pixel_to_geo, point_in_polygon


def build_border_mask(cfg: RegionConfig) -> np.ndarray:
    """Build boolean mask for the 'PT side' of the border.

    Verbatim port of inicio/map_generator.py:317-328 (D-01).
    """
    mask = np.zeros((cfg.map_h, cfg.map_w), dtype=bool)
    if not cfg.border_polygon:
        return mask

    for y in range(cfg.map_h):
        for x in range(0, cfg.map_w, 3):
            lon, lat = pixel_to_geo(x, y, cfg)
            if point_in_polygon(lon, lat, cfg.border_polygon):
                mask[y, x:min(x+3, cfg.map_w)] = True
    return mask


__all__ = ["build_border_mask"]
