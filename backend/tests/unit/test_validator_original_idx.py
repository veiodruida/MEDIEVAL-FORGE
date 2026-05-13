"""Unit tests for _check_original_idx (D-11 REVISED + D-08 MISSING_ORIGINAL_IDX).

D-11 REVISED: condados-only check; baronies exempt by canonical shape
(tests/fixtures/iberia_868/golden/territory_metadata.json:1838+).
NO RegionConfig flag, NO YAML flag.
"""
from __future__ import annotations

import pytest

from medieval_forge.services.export.validator import (
    _ValidationContext,
    _check_original_idx,
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


def _condado(cid: str, original_idx) -> dict:
    out = {
        "id": cid,
        "name": cid.upper(),
        "lon": 0.0,
        "lat": 0.0,
        "duchy": "d",
        "kingdom": "k",
        "pixel_center": [0, 0],
        "pixel_count": 500,
        "baronies": [],
    }
    if original_idx is not None:
        out["original_idx"] = original_idx
    return out


def _meta(condados, baronies=None) -> dict:
    return {
        "territory_metadata.json": {
            "region": "test",
            "map_size": [3840, 2160],
            "bounds": {"lon_min": 0.0, "lon_max": 1.0, "lat_min": 0.0, "lat_max": 1.0},
            "kingdoms": {},
            "duchies": {},
            "condados": condados,
            "baronies": baronies or [],
        }
    }


def test_all_condados_with_original_idx_no_errors(iberia_cfg) -> None:
    payloads = _meta([_condado("c1", 1), _condado("c2", 2)])
    ctx = _ValidationContext()
    _check_original_idx(ctx, payloads, iberia_cfg)
    assert ctx.errors == []


def test_condado_missing_original_idx_records_one_error(iberia_cfg) -> None:
    payloads = _meta([_condado("c1", None)])
    ctx = _ValidationContext()
    _check_original_idx(ctx, payloads, iberia_cfg)
    assert len(ctx.errors) == 1
    assert ctx.errors[0].code == "MISSING_ORIGINAL_IDX"
    assert ctx.errors[0].context["id"] == "c1"
    assert ctx.errors[0].context["kind"] == "condado"
    assert ctx.errors[0].file == "territory_metadata.json"


def test_baronies_without_original_idx_are_exempt_no_errors(iberia_cfg) -> None:
    """D-11 REVISED: baronies are EXEMPT by canonical shape."""
    payloads = _meta(
        condados=[_condado("c1", 1)],
        baronies=[
            {"name": "b1", "condado_idx": 0, "duchy": "d", "pixel_count": 500},
            {"name": "b2", "condado_idx": 0, "duchy": "d", "pixel_count": 400},
        ],
    )
    ctx = _ValidationContext()
    _check_original_idx(ctx, payloads, iberia_cfg)
    assert ctx.errors == []


def test_three_condados_missing_original_idx_record_three_errors(iberia_cfg) -> None:
    """D-18: collect ALL, no fail-fast."""
    payloads = _meta([_condado(f"c{i}", None) for i in range(3)])
    ctx = _ValidationContext()
    _check_original_idx(ctx, payloads, iberia_cfg)
    assert len(ctx.errors) == 3
    assert all(e.code == "MISSING_ORIGINAL_IDX" for e in ctx.errors)
    ids = {e.context["id"] for e in ctx.errors}
    assert ids == {"c0", "c1", "c2"}


def test_condado_with_explicit_null_original_idx_records_error(iberia_cfg) -> None:
    """Null is missing for D-11 purposes (entry.get returns None for both)."""
    payloads = _meta([{
        "id": "c1",
        "name": "C1",
        "lon": 0.0,
        "lat": 0.0,
        "duchy": "d",
        "kingdom": "k",
        "pixel_center": [0, 0],
        "pixel_count": 500,
        "baronies": [],
        "original_idx": None,
    }])
    ctx = _ValidationContext()
    _check_original_idx(ctx, payloads, iberia_cfg)
    assert len(ctx.errors) == 1


def test_condado_with_valid_int_original_idx_no_errors(iberia_cfg) -> None:
    payloads = _meta([_condado("c1", 92)])
    ctx = _ValidationContext()
    _check_original_idx(ctx, payloads, iberia_cfg)
    assert ctx.errors == []
