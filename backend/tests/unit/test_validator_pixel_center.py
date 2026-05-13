"""Unit tests for _check_pixel_center (D-10 + D-08 PIXEL_CENTER_OUT_OF_RANGE).

Bounds: 0 <= col < cfg.map_w AND 0 <= row < cfg.map_h (half-open).
Y-down numpy convention preserved — no orientation conversion at export.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from medieval_forge.services.export.validator import (
    _ValidationContext,
    _check_pixel_center,
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


def _condado(cid: str, pc: list[int]) -> dict:
    return {
        "id": cid,
        "name": cid.upper(),
        "lon": 0.0,
        "lat": 0.0,
        "duchy": "d",
        "kingdom": "k",
        "pixel_center": pc,
        "pixel_count": 500,
        "baronies": [],
        "original_idx": 1,
    }


def _meta(condados) -> dict:
    return {
        "territory_metadata.json": {
            "region": "test",
            "map_size": [3840, 2160],
            "bounds": {"lon_min": 0.0, "lon_max": 1.0, "lat_min": 0.0, "lat_max": 1.0},
            "kingdoms": {},
            "duchies": {},
            "condados": condados,
            "baronies": [],
        }
    }


def test_all_condados_in_range_no_errors(iberia_cfg) -> None:
    payloads = _meta([_condado("c1", [100, 100]), _condado("c2", [1000, 500])])
    ctx = _ValidationContext()
    _check_pixel_center(ctx, payloads, iberia_cfg)
    assert ctx.errors == []


def test_negative_column_out_of_range_records_one_error(iberia_cfg) -> None:
    payloads = _meta([_condado("c1", [-1, 0])])
    ctx = _ValidationContext()
    _check_pixel_center(ctx, payloads, iberia_cfg)
    assert len(ctx.errors) == 1
    assert ctx.errors[0].code == "PIXEL_CENTER_OUT_OF_RANGE"
    assert ctx.errors[0].context["id"] == "c1"
    assert ctx.errors[0].context["pixel_center"] == [-1, 0]


def test_negative_row_out_of_range_records_one_error(iberia_cfg) -> None:
    payloads = _meta([_condado("c1", [0, -1])])
    ctx = _ValidationContext()
    _check_pixel_center(ctx, payloads, iberia_cfg)
    assert len(ctx.errors) == 1


def test_column_at_map_w_is_out_of_range(iberia_cfg) -> None:
    """Half-open interval: col == map_w is past last valid pixel."""
    payloads = _meta([_condado("c1", [iberia_cfg.map_w, 100])])
    ctx = _ValidationContext()
    _check_pixel_center(ctx, payloads, iberia_cfg)
    assert len(ctx.errors) == 1


def test_row_at_map_h_is_out_of_range(iberia_cfg) -> None:
    payloads = _meta([_condado("c1", [100, iberia_cfg.map_h])])
    ctx = _ValidationContext()
    _check_pixel_center(ctx, payloads, iberia_cfg)
    assert len(ctx.errors) == 1


def test_corner_pixel_at_map_w_minus_1_in_range(iberia_cfg) -> None:
    """The pixel at the last valid coord is IN range."""
    payloads = _meta([_condado("c1", [iberia_cfg.map_w - 1, iberia_cfg.map_h - 1])])
    ctx = _ValidationContext()
    _check_pixel_center(ctx, payloads, iberia_cfg)
    assert ctx.errors == []


def test_four_out_of_range_condados_record_four_errors(iberia_cfg) -> None:
    """D-18: collect ALL, no fail-fast."""
    payloads = _meta([
        _condado("c1", [-1, 0]),
        _condado("c2", [0, -1]),
        _condado("c3", [iberia_cfg.map_w, 100]),
        _condado("c4", [100, iberia_cfg.map_h]),
    ])
    ctx = _ValidationContext()
    _check_pixel_center(ctx, payloads, iberia_cfg)
    assert len(ctx.errors) == 4
    assert all(e.code == "PIXEL_CENTER_OUT_OF_RANGE" for e in ctx.errors)


def test_custom_cfg_dims_use_cfg_not_hard_coded(iberia_cfg) -> None:
    """Validator reads cfg.map_w/map_h — not hard-coded 1920×1080."""
    cfg = replace(iberia_cfg, map_w=3840, map_h=2160)
    payloads = _meta([_condado("c1", [2000, 1500])])
    ctx = _ValidationContext()
    _check_pixel_center(ctx, payloads, cfg)
    assert ctx.errors == []
