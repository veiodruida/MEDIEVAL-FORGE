"""Unit tests for terrain.py — palette uniqueness, JSON schema, raster shape."""
from __future__ import annotations

import numpy as np
import pytest

from medieval_forge.services.pipeline.contracts import RegionConfig
from medieval_forge.services.pipeline.region_loader import (
    clear_region_cache,
    load_region,
)
from medieval_forge.services.pipeline.terrain import (
    OCEAN_RGB,
    PLAINS_RGB,
    TERRAIN_TYPES_JSON,
    assert_palette_no_collision,
    build_terrain_types_json,
    render_terrain_lookup,
)

pytestmark = pytest.mark.unit


def test_plains_rgb_value() -> None:
    """Locked palette value (124, 179, 66) — DO NOT change without coordinated update."""
    assert PLAINS_RGB == (124, 179, 66)


def test_ocean_rgb_value() -> None:
    """Ocean sentinel locked at pure black."""
    assert OCEAN_RGB == (0, 0, 0)


def test_terrain_types_json_schema() -> None:
    """RGB-keyed dict with {name, movement, defense, attack} per CLAUDE.md row 6."""
    assert set(TERRAIN_TYPES_JSON.keys()) == {"124,179,66", "0,0,0"}
    for key, payload in TERRAIN_TYPES_JSON.items():
        assert set(payload.keys()) == {"name", "movement", "defense", "attack"}
        assert isinstance(payload["name"], str)
        for field in ("movement", "defense", "attack"):
            assert isinstance(payload[field], float)


def test_render_terrain_lookup_shape() -> None:
    """Returns uint8 array of shape (map_h, map_w, 3)."""
    cfg = RegionConfig()  # defaults: 1920 × 1080
    land = np.ones((cfg.map_h, cfg.map_w), dtype=bool)
    arr = render_terrain_lookup(land, cfg)
    assert arr.shape == (1080, 1920, 3)
    assert arr.dtype == np.uint8


def test_render_terrain_lookup_land_vs_ocean() -> None:
    """Land pixels get PLAINS_RGB, ocean pixels get OCEAN_RGB."""
    cfg = RegionConfig()
    land = np.zeros((cfg.map_h, cfg.map_w), dtype=bool)
    land[0:540, :] = True  # top half = land
    arr = render_terrain_lookup(land, cfg)
    assert tuple(arr[0, 0]) == PLAINS_RGB
    assert tuple(arr[1079, 0]) == OCEAN_RGB


def test_assert_no_collision_iberia() -> None:
    """Real Iberia cfg must NOT trip the collision guard (palette pre-verified)."""
    clear_region_cache()
    cfg = load_region("iberia_868")
    assert_palette_no_collision(cfg)  # raises if collision; passes otherwise


def test_assert_no_collision_france() -> None:
    """France cfg (autogen kingdom_colors) must NOT trip the collision guard."""
    clear_region_cache()
    cfg = load_region("france_1066")
    assert_palette_no_collision(cfg)


def test_assert_collision_raises() -> None:
    """Manually inject a colliding kingdom_color and expect ValueError."""
    cfg = RegionConfig(kingdom_colors={"0": list(PLAINS_RGB)})
    with pytest.raises(ValueError, match=r"PLAINS_RGB"):
        assert_palette_no_collision(cfg)


def test_build_terrain_types_json_returns_copy() -> None:
    """Mutating the returned dict must not affect the module constant."""
    cfg = RegionConfig()
    a = build_terrain_types_json(cfg)
    a["sentinel"] = {"name": "x", "movement": 0.0, "defense": 0.0, "attack": 0.0}
    b = build_terrain_types_json(cfg)
    assert "sentinel" not in b
