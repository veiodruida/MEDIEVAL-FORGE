"""Unit tests for _check_color_collision (D-13 + D-08 COLOR_COLLISION).

D-17 enforcement: each test asserts EXACTLY the expected error codes.
User preference: descriptive test names + explicit numeric fixtures.

NOTE on within-file collision (D-13 Scope 1): JSON dict semantics collapse
duplicate keys at parse time, so within-file dup is hard to induce at the
unit-layer payload level. Coverage for that scope is provided by the e2e
broken-fixture test in tests/e2e/test_export_gate_broken.py — see
test_broken_duplicate_lookup_color_triggers_color_collision_only. This unit
file covers the cross-layer terrain scope (Scope 2) and the no-error happy
paths, since those ARE expressible as hand-built payload dicts.
"""
from __future__ import annotations

import pytest

from medieval_forge.services.export.validator import (
    _ValidationContext,
    _check_color_collision,
)
from medieval_forge.services.pipeline.region_loader import (
    clear_region_cache,
    load_region,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def iberia_cfg():
    clear_region_cache()
    return load_region("iberia_868")


def test_clean_lookup_colors_no_collisions(iberia_cfg) -> None:
    ctx = _ValidationContext()
    payloads = {
        "lookup_barony_colors.json": {"50,80,30": 0, "127,255,0": 1},
        "lookup_condado_colors.json": {"60,90,40": 0, "200,100,50": 1},
    }
    _check_color_collision(ctx, payloads, iberia_cfg)
    assert ctx.errors == []


def test_cross_layer_collision_with_plains_rgb_records_one_error(iberia_cfg) -> None:
    ctx = _ValidationContext()
    payloads = {
        "lookup_barony_colors.json": {"124,179,66": 0},  # PLAINS_RGB
        "lookup_condado_colors.json": {},
    }
    _check_color_collision(ctx, payloads, iberia_cfg)
    assert len(ctx.errors) == 1
    assert ctx.errors[0].code == "COLOR_COLLISION"
    assert ctx.errors[0].context["conflicts_with"] == "PLAINS_RGB"
    assert ctx.errors[0].context["scope"] == "cross_layer_terrain"
    assert ctx.errors[0].file == "lookup_barony_colors.json"


def test_cross_layer_collision_with_ocean_rgb_records_one_error(iberia_cfg) -> None:
    """OCEAN_RGB = (0, 0, 0), the terrain_lookup.png ocean sentinel."""
    ctx = _ValidationContext()
    payloads = {
        "lookup_barony_colors.json": {},
        "lookup_condado_colors.json": {"0,0,0": 5},  # OCEAN_RGB
    }
    _check_color_collision(ctx, payloads, iberia_cfg)
    assert len(ctx.errors) == 1
    assert ctx.errors[0].code == "COLOR_COLLISION"
    assert ctx.errors[0].context["conflicts_with"] == "OCEAN_RGB"
    assert ctx.errors[0].file == "lookup_condado_colors.json"


def test_cross_layer_collision_with_ocean_far_records_one_error(iberia_cfg) -> None:
    """cfg.ocean_far = (70, 130, 180), the lookup PNG ocean fill color (lookup.py:31)."""
    rgb_key = f"{iberia_cfg.ocean_far[0]},{iberia_cfg.ocean_far[1]},{iberia_cfg.ocean_far[2]}"
    ctx = _ValidationContext()
    payloads = {
        "lookup_barony_colors.json": {},
        "lookup_condado_colors.json": {rgb_key: 0},
    }
    _check_color_collision(ctx, payloads, iberia_cfg)
    assert len(ctx.errors) == 1
    assert ctx.errors[0].code == "COLOR_COLLISION"
    assert ctx.errors[0].context["conflicts_with"] == "cfg.ocean_far"


def test_cross_file_same_rgb_in_barony_and_condado_is_allowed(iberia_cfg) -> None:
    """D-13: cross-FILE lookup collision is intentional — different layers."""
    ctx = _ValidationContext()
    payloads = {
        "lookup_barony_colors.json": {"50,80,30": 0},
        "lookup_condado_colors.json": {"50,80,30": 3},  # same RGB, different layer
    }
    _check_color_collision(ctx, payloads, iberia_cfg)
    assert ctx.errors == []


def test_aggregate_two_distinct_collisions_records_two_errors(iberia_cfg) -> None:
    """D-18: collect ALL errors, no fail-fast."""
    ctx = _ValidationContext()
    payloads = {
        "lookup_barony_colors.json": {"124,179,66": 0},  # PLAINS_RGB collision
        "lookup_condado_colors.json": {"0,0,0": 5},      # OCEAN_RGB collision
    }
    _check_color_collision(ctx, payloads, iberia_cfg)
    assert len(ctx.errors) == 2
    assert all(e.code == "COLOR_COLLISION" for e in ctx.errors)
    conflict_sources = {e.context["conflicts_with"] for e in ctx.errors}
    assert conflict_sources == {"PLAINS_RGB", "OCEAN_RGB"}
