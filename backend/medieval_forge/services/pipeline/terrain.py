"""Terrain lookup raster + RGB→stats JSON for the 12-file Unity contract.

Closes Phase 05 SC-3 Gap 1 (VERIFICATION) by emitting the two missing files
listed in CLAUDE.md §"v3 Pipeline Contract" rows 5 + 6:

    terrain_lookup.png   (1920×1080, native 1x — NOT NEAREST-upscaled)
    terrain_types.json   (RGB → {name, movement, defense, attack})

Phase 05 contract placeholder — flat plains-everywhere-on-land emitter.
Real terrain (DEM-derived, biome-aware) is Phase 06/07.

Phase 05 ships a single-terrain palette ("plains" on every land pixel,
"ocean" sentinel for water). Phase 06's validation gate is where richer
terrain types will arrive if/when DEM ingestion lands. The single-terrain
choice keeps the file contract honest (12/12) without inventing biome data
the toy datasets do not yet carry.

Palette collisions are blocked at write-time by `assert_palette_no_collision`,
called from `build_terrain_types_json`. The palette tuple values were chosen
to NOT equal any existing RegionConfig color field or any committed
`kingdom_colors` entry in `data/regions/*.yaml` (verified via grep).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:  # pragma: no cover
    from .contracts import RegionConfig


# Phase 05 palette — locked. Changing these values requires a coordinated
# update to terrain_types.json schema + every Unity terrain loader.
PLAINS_RGB: tuple[int, int, int] = (124, 179, 66)  # Material Light Green 600
OCEAN_RGB: tuple[int, int, int] = (0, 0, 0)        # Sentinel: ocean pixels


# Single source of truth for the terrain_types.json shape. Keys are
# comma-separated "R,G,B" strings (no spaces) per CLAUDE.md row 6.
TERRAIN_TYPES_JSON: dict[str, dict] = {
    "124,179,66": {"name": "plains", "movement": 1.0, "defense": 0.0, "attack": 0.0},
    "0,0,0":     {"name": "ocean",  "movement": 0.0, "defense": 0.0, "attack": 0.0},
}


def assert_palette_no_collision(cfg: "RegionConfig") -> None:
    """Raise ValueError if PLAINS_RGB or OCEAN_RGB collides with any cfg color.

    Guards the terrain palette against silent corruption: a region YAML that
    happens to declare a `kingdom_colors` value equal to PLAINS_RGB would
    break Unity's terrain lookup (two distinct semantic layers, same RGB).
    """
    protected: dict[tuple[int, int, int], str] = {
        tuple(PLAINS_RGB): "PLAINS_RGB",
        tuple(OCEAN_RGB): "OCEAN_RGB",
    }
    cfg_colors: list[tuple[str, tuple]] = [
        ("mountain_color_visual", tuple(cfg.mountain_color_visual)),
        ("mountain_color_lookup", tuple(cfg.mountain_color_lookup)),
        ("river_color", tuple(cfg.river_color)),
        ("coast_inner_color", tuple(cfg.coast_inner_color)),
        ("ocean_near", tuple(cfg.ocean_near)),
        ("ocean_far", tuple(cfg.ocean_far)),
    ]
    for kid, rgb in cfg.kingdom_colors.items():
        cfg_colors.append((f"kingdom_colors[{kid!r}]", tuple(rgb)))

    for name, rgb in cfg_colors:
        if rgb in protected:
            raise ValueError(
                f"terrain palette collision: {protected[rgb]} {rgb} "
                f"== cfg.{name} {rgb}. Pick a different PLAINS_RGB / "
                f"OCEAN_RGB or recolor the conflicting cfg field."
            )


def render_terrain_lookup(land: np.ndarray, cfg: "RegionConfig") -> np.ndarray:
    """Return uint8 RGB array of shape (cfg.map_h, cfg.map_w, 3).

    Every land pixel → PLAINS_RGB; every ocean pixel → OCEAN_RGB sentinel.

    The output is NATIVE 1x (1920×1080 for default cfg) — terrain_lookup.png
    is NOT NEAREST-upscaled from a smaller raster (CLAUDE.md row 5 is
    explicit on the 1920×1080 dimension). Rule #1 (NEAREST only, never
    BICUBIC/BILINEAR) applies to upscale operations; a 1x-native file
    is simply not upscaled at all.
    """
    # WR-03 fix (Plan 05 review): use runtime exceptions instead of `assert`.
    # `python -O` strips asserts, so input validation must not depend on them —
    # a wrong dtype/shape under -O would silently corrupt the terrain raster
    # (e.g. integer land[] indexing would broadcast unexpectedly into arr[]).
    if land.dtype != np.bool_:
        raise TypeError(f"land must be bool[H,W], got dtype={land.dtype}")
    if land.shape != (cfg.map_h, cfg.map_w):
        raise ValueError(
            f"land shape mismatch: expected ({cfg.map_h}, {cfg.map_w}), "
            f"got {land.shape}"
        )
    arr = np.zeros((cfg.map_h, cfg.map_w, 3), dtype=np.uint8)
    arr[land] = PLAINS_RGB
    arr[~land] = OCEAN_RGB
    return arr


def build_terrain_types_json(cfg: "RegionConfig") -> dict[str, dict]:
    """Return a fresh deep-copy of TERRAIN_TYPES_JSON after asserting no collision.

    Returning a fresh dict (deep-copied via dict comprehension) prevents a
    misbehaving caller from mutating the module-level constant and silently
    poisoning subsequent callers.
    """
    assert_palette_no_collision(cfg)
    # Deep copy: outer dict + each inner payload dict.
    return {key: dict(payload) for key, payload in TERRAIN_TYPES_JSON.items()}


__all__ = [
    "PLAINS_RGB",
    "OCEAN_RGB",
    "TERRAIN_TYPES_JSON",
    "render_terrain_lookup",
    "build_terrain_types_json",
    "assert_palette_no_collision",
]
