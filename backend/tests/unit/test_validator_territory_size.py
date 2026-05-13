"""Unit tests for _check_territory_size (D-12 + D-08 TERRITORY_TOO_SMALL).

Threshold = cfg.blob_merge_px (default 200). Both condados and baronies.
Half-open: pixel_count < threshold fails; pixel_count == threshold passes.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from medieval_forge.services.export.validator import (
    _ValidationContext,
    _check_territory_size,
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


def _meta(condados, baronies) -> dict:
    return {
        "territory_metadata.json": {
            "region": "test",
            "map_size": [3840, 2160],
            "bounds": {"lon_min": 0.0, "lon_max": 1.0, "lat_min": 0.0, "lat_max": 1.0},
            "kingdoms": {},
            "duchies": {},
            "condados": condados,
            "baronies": baronies,
        }
    }


def _condado(cid: str, pixel_count: int) -> dict:
    return {
        "id": cid,
        "name": cid.upper(),
        "lon": 0.0,
        "lat": 0.0,
        "duchy": "d",
        "kingdom": "k",
        "pixel_center": [0, 0],
        "pixel_count": pixel_count,
        "baronies": [],
    }


def test_all_condados_above_threshold_no_errors(iberia_cfg) -> None:
    payloads = _meta(
        condados=[_condado("c1", 500)],
        baronies=[{"name": "b1", "condado_idx": 0, "duchy": "d", "pixel_count": 300}],
    )
    ctx = _ValidationContext()
    _check_territory_size(ctx, generated_dir=None, payloads=payloads, cfg=iberia_cfg)
    assert ctx.errors == []


def test_condado_with_150px_records_exactly_one_too_small_error(iberia_cfg) -> None:
    payloads = _meta(condados=[_condado("c1", 150)], baronies=[])
    ctx = _ValidationContext()
    _check_territory_size(ctx, generated_dir=None, payloads=payloads, cfg=iberia_cfg)
    assert len(ctx.errors) == 1
    assert ctx.errors[0].code == "TERRITORY_TOO_SMALL"
    assert ctx.errors[0].context["id"] == "c1"
    assert ctx.errors[0].context["kind"] == "condado"
    assert ctx.errors[0].context["pixel_count"] == 150
    assert ctx.errors[0].context["threshold"] == 200


def test_condado_with_199px_at_boundary_below_threshold_fails(iberia_cfg) -> None:
    """D-12: strict `<` comparator — 199 < 200 fails."""
    payloads = _meta(condados=[_condado("c1", 199)], baronies=[])
    ctx = _ValidationContext()
    _check_territory_size(ctx, generated_dir=None, payloads=payloads, cfg=iberia_cfg)
    assert len(ctx.errors) == 1


def test_condado_with_200px_at_boundary_AT_threshold_passes(iberia_cfg) -> None:
    """D-12: <200 fails, =200 passes (cfg.blob_merge_px boundary)."""
    payloads = _meta(condados=[_condado("c1", 200)], baronies=[])
    ctx = _ValidationContext()
    _check_territory_size(ctx, generated_dir=None, payloads=payloads, cfg=iberia_cfg)
    assert ctx.errors == []


def test_barony_below_threshold_records_one_error(iberia_cfg) -> None:
    payloads = _meta(
        condados=[],
        baronies=[{"name": "b1", "condado_idx": 0, "duchy": "d", "pixel_count": 100}],
    )
    ctx = _ValidationContext()
    _check_territory_size(ctx, generated_dir=None, payloads=payloads, cfg=iberia_cfg)
    assert len(ctx.errors) == 1
    assert ctx.errors[0].context["kind"] == "barony"
    assert ctx.errors[0].context["id"] == "b1"
    assert ctx.errors[0].context["pixel_count"] == 100


def test_five_small_territories_record_five_distinct_errors(iberia_cfg) -> None:
    """D-18: collect ALL errors, no fail-fast."""
    payloads = _meta(
        condados=[_condado(f"c{i}", 100) for i in range(3)],
        baronies=[
            {"name": f"b{i}", "condado_idx": 0, "duchy": "d", "pixel_count": 100}
            for i in range(2)
        ],
    )
    ctx = _ValidationContext()
    _check_territory_size(ctx, generated_dir=None, payloads=payloads, cfg=iberia_cfg)
    assert len(ctx.errors) == 5
    assert all(e.code == "TERRITORY_TOO_SMALL" for e in ctx.errors)
    kinds = [e.context["kind"] for e in ctx.errors]
    assert kinds.count("condado") == 3
    assert kinds.count("barony") == 2


def test_custom_threshold_300_with_condado_250_fails(iberia_cfg) -> None:
    """Validator must read cfg.blob_merge_px, not hard-coded 200."""
    cfg = replace(iberia_cfg, blob_merge_px=300)
    payloads = _meta(condados=[_condado("c1", 250)], baronies=[])
    ctx = _ValidationContext()
    _check_territory_size(ctx, generated_dir=None, payloads=payloads, cfg=cfg)
    assert len(ctx.errors) == 1
    assert ctx.errors[0].context["threshold"] == 300
