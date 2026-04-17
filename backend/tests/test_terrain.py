"""Unit tests for the geographic terrain classifier.

Tests validate the port from inicio/map_generator.py render_mountains / render_rivers
to the backend pipeline. All 5 tests must pass without any external data dependencies
(fixtures inject data directly).

Acceptance criteria covered:
  - test_mountain_data_loads        (AC 1)
  - test_render_mountains_produces_mask (AC 2, 3)
  - test_terrain_lookup_palette     (AC 4)
  - test_mountain_intersected_with_land (AC 4 + no ocean bleed)
  - test_terrain_types_json_matches_palette (AC 4)
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest
from PIL import Image


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cfg(w: int = 64, h: int = 64, upscale: int = 1):
    """Minimal RegionConfig for a small test canvas covering a known lon/lat box."""
    from medieval_forge.lib.map_generator import RegionConfig
    return RegionConfig(
        name="test",
        map_w=w,
        map_h=h,
        upscale=upscale,
        # Tight bounding box centred on Iberia for realistic coordinate mapping.
        lon_min=-10.0,
        lon_max=5.0,
        lat_min=36.0,
        lat_max=44.0,
    )


def _iberia_bundled_path() -> pathlib.Path:
    """Return the path to the bundled Iberia mountain/river JSON."""
    return (
        pathlib.Path(__file__).parent.parent
        / "medieval_forge"
        / "services"
        / "mountain_river_data_iberia.json"
    )


# ---------------------------------------------------------------------------
# Test 1: bundled data loads and validates polygon format
# ---------------------------------------------------------------------------

def test_mountain_data_loads():
    """mountain_river_data_iberia.json exists and has valid polygon structure.

    Validates acceptance criterion 1: the file is bundled and parseable,
    with at least 3 mountain ranges each having >= 3 [lon, lat] pairs.
    """
    path = _iberia_bundled_path()
    assert path.exists(), (
        f"Bundled data not found at {path}. "
        "Copy inicio/mountain_river_data.json to backend/medieval_forge/services/mountain_river_data_iberia.json"
    )

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    mountains = data.get("mountains", {})
    assert len(mountains) >= 3, (
        f"Expected >= 3 mountain ranges, got {len(mountains)}: {list(mountains.keys())}"
    )

    for key, mtn in mountains.items():
        polygon = mtn.get("polygon", [])
        assert isinstance(polygon, list) and len(polygon) >= 3, (
            f"Mountain {key!r}: polygon must have >= 3 points, got {len(polygon)}"
        )
        for i, pt in enumerate(polygon):
            assert (
                isinstance(pt, list) and len(pt) == 2
                and isinstance(pt[0], (int, float))
                and isinstance(pt[1], (int, float))
            ), f"Mountain {key!r} polygon[{i}] is not [lon, lat]: {pt}"

    rivers = data.get("rivers", {})
    # Rivers are optional but if present must have >= 2 coordinate pairs.
    for key, river in rivers.items():
        coords = river.get("coords", [])
        assert len(coords) >= 2, (
            f"River {key!r}: need >= 2 coords for a line, got {len(coords)}"
        )


# ---------------------------------------------------------------------------
# Test 2: render_mountains_from_data rasterizes a fixture polygon correctly
# ---------------------------------------------------------------------------

def test_render_mountains_produces_mask():
    """render_mountains_from_data paints mountain pixels inside a known polygon.

    Uses a small fixture polygon that covers the top-left quadrant of the
    test canvas and verifies pixels inside are True, pixels outside are False.
    """
    from medieval_forge.lib.map_generator import render_mountains_from_data

    cfg = _make_cfg(w=64, h=64)

    # Build an all-land mask.
    land = np.ones((64, 64), dtype=bool)

    # A polygon that covers the top-left quadrant in geographic coords.
    # cfg: lon -10..5, lat 36..44. Center of top-left quadrant:
    #   lon ~-8.75, lat ~42 (upper-left in screen coords = small y = top).
    # Polygon: rectangle lon [-10, -2.5], lat [40, 44].
    fixture_data = {
        "mountains": {
            "test_range": {
                "name": "Test Range",
                "polygon": [
                    [-10.0, 40.0],
                    [-2.5,  40.0],
                    [-2.5,  44.0],
                    [-10.0, 44.0],
                    [-10.0, 40.0],
                ],
            }
        }
    }

    mask = render_mountains_from_data(fixture_data, cfg, land, 64, 64)

    assert mask.dtype == bool, "render_mountains_from_data must return boolean mask"
    assert mask.shape == (64, 64), f"Expected (64,64), got {mask.shape}"

    # The polygon covers the northern half (lat 40..44 out of 36..44 = top 50%).
    # In pixel coords lat is inverted: lat_max is row 0, lat_min is row 63.
    # lat 40 → py = (1 - (40-36)/(44-36)) * 64 = (1 - 0.5) * 64 = 32
    # lat 44 → py = (1 - (44-36)/(44-36)) * 64 = 0
    # So rows 0..31 should be mountain, rows 33..63 should not.
    assert np.any(mask[0:30, :]), "Top rows should be mountain (inside polygon)"
    assert not np.any(mask[35:, :]), "Bottom rows should NOT be mountain (outside polygon)"


# ---------------------------------------------------------------------------
# Test 3: terrain_lookup has exactly 4 distinct RGB values on land
# ---------------------------------------------------------------------------

def test_terrain_lookup_palette():
    """generate_terrain_lookup produces exactly 4 distinct RGB values total.

    When mountain data covers part of the land area, the output must have
    exactly ocean + coast + plain + mountain — no synthetic 5th color.
    """
    from medieval_forge.lib.map_generator import generate_terrain_lookup, _TERRAIN_TYPES

    cfg = _make_cfg(w=128, h=128)

    # Land: left 100 columns, ocean: right 28 columns.
    land = np.zeros((128, 128), dtype=bool)
    land[:, :100] = True

    # Mountain: top-left 40x40 block (on land).
    mtn = np.zeros((128, 128), dtype=bool)
    mtn[:40, :40] = True

    lookup, terrain_types = generate_terrain_lookup(land, cfg, mtn_mask=mtn)

    all_pixels = lookup.reshape(-1, 3)
    unique_colors = {tuple(row) for row in all_pixels}

    expected_colors = {
        _TERRAIN_TYPES["ocean"]["rgb"],
        _TERRAIN_TYPES["coast"]["rgb"],
        _TERRAIN_TYPES["plain"]["rgb"],
        _TERRAIN_TYPES["mountain"]["rgb"],
    }

    assert unique_colors == expected_colors, (
        f"Expected exactly these 4 colors: {expected_colors}\n"
        f"Got {len(unique_colors)} colors: {unique_colors}\n"
        "Synthetic noise (hill/forest) must not appear in the output."
    )


# ---------------------------------------------------------------------------
# Test 4: mountain polygon extending into ocean is clipped to land
# ---------------------------------------------------------------------------

def test_mountain_intersected_with_land():
    """Mountain polygon extending over ocean is clipped — no ocean pixels become mountain.

    This verifies the land-intersection in render_mountains_from_data and the
    mtn_1x & land guard in generate_terrain_lookup.
    """
    from medieval_forge.lib.map_generator import render_mountains_from_data, _TERRAIN_TYPES

    cfg = _make_cfg(w=64, h=64)

    # Land: only left half. Ocean: right half.
    land = np.zeros((64, 64), dtype=bool)
    land[:, :32] = True

    # Mountain polygon covers the FULL canvas width (both land and ocean).
    fixture_data = {
        "mountains": {
            "wide_range": {
                "name": "Wide Range",
                "polygon": [
                    [-10.0, 36.0],
                    [5.0,   36.0],
                    [5.0,   44.0],
                    [-10.0, 44.0],
                    [-10.0, 36.0],
                ],
            }
        }
    }

    mask = render_mountains_from_data(fixture_data, cfg, land, 64, 64)

    # All mountain pixels must be on land (left half only).
    assert not np.any(mask[:, 32:]), (
        "Mountain mask must not bleed into ocean columns (right half). "
        "Land intersection failed."
    )
    # Left half should have mountain pixels (the polygon covers all land).
    assert np.any(mask[:, :32]), (
        "Mountain mask must paint pixels on the land side (left half)."
    )


# ---------------------------------------------------------------------------
# Test 5: terrain_types.json RGB keys match every color in the PNG
# ---------------------------------------------------------------------------

def test_terrain_types_json_matches_palette():
    """Every RGB value in terrain_lookup must have a matching entry in terrain_types.

    This ensures Unity can always look up a pixel color in the JSON dictionary.
    No pixel should be an unmapped color (not even (0,0,0) black).
    """
    from medieval_forge.lib.map_generator import generate_terrain_lookup

    cfg = _make_cfg(w=64, h=64)

    # Mixed canvas: partial land, partial ocean, partial mountain.
    land = np.zeros((64, 64), dtype=bool)
    land[:, :48] = True  # right 16 cols = ocean

    mtn = np.zeros((64, 64), dtype=bool)
    mtn[:20, :20] = True  # top-left block = mountain (on land)

    lookup, terrain_types = generate_terrain_lookup(land, cfg, mtn_mask=mtn)

    # Build the set of allowed RGB tuples from terrain_types keys.
    allowed_rgbs: set[tuple[int, int, int]] = set()
    for key in terrain_types:
        parts = key.split(",")
        allowed_rgbs.add((int(parts[0]), int(parts[1]), int(parts[2])))

    # Every pixel in the output must be one of the allowed colors.
    flat = lookup.reshape(-1, 3)
    unique_in_output = {tuple(row) for row in flat}

    unmapped = unique_in_output - allowed_rgbs
    assert not unmapped, (
        f"terrain_lookup.png contains RGB values not in terrain_types.json: {unmapped}\n"
        "Unity hit-detection would fail for these pixels."
    )
