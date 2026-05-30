"""Unit tests for canvas_sidecars.py barony hierarchy fields (Plan 08.3-02 Task 1).

Verifies that the barony emitter extends Feature properties with:
  - condado_idx (int)
  - duchy_id (str)
  - kingdom_id (str)

And that existing fields (condado_id, centroid, pixel_count, id, name) are
still present (regression guard).

Fixture: 2 baronies in 1 condado in 1 duchy in 1 kingdom, explicit numeric idx.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict

import numpy as np
import pytest

from medieval_forge.services.canvas_sidecars import build_baronies_geojson_sidecar
from medieval_forge.services.pipeline.contracts import RegionConfig


# ---------------------------------------------------------------------------
# Minimal RegionConfig fixture
# ---------------------------------------------------------------------------

def _make_cfg(tmp_path: str) -> RegionConfig:
    """Build a minimal RegionConfig with 2 condados, 1 duchy, 1 kingdom.

    Territory layout:
      kingdoms  = {"K1": ("K1", "Reino de Test")}
      duchies   = {"D1": ("D1", "Ducado de Test", "K1")}
      condados  = [
          ("C0", "Condado Zero", -7.0, 38.0, "D1", ...),   # idx 0
          ("C1", "Condado Um",   -6.0, 38.5, "D1", ...),   # idx 1
      ]

    Tuple structure mirrors inicio territory_data_v3.py:
      (condado_id, condado_name, lon, lat, duchy_id, ...)
    """
    cfg = RegionConfig(
        name="test",
        map_w=10,
        map_h=10,
        lon_min=-10.0,
        lon_max=0.0,
        lat_min=36.0,
        lat_max=44.0,
        output_dir=tmp_path,
        kingdoms={"K1": ("K1", "Reino de Test")},
        duchies={"D1": ("K1", "Ducado de Test")},
        condados=[
            ("C0", "Condado Zero", -7.0, 38.0, "D1"),
            ("C1", "Condado Um",   -6.0, 38.5, "D1"),
        ],
    )
    # lon_scale is derived in __post_init__; ensure it is set
    if cfg.lon_scale is None:
        import math
        cfg.lon_scale = math.cos(math.radians((cfg.lat_min + cfg.lat_max) / 2))
    return cfg


def _make_raster_and_bars(n_baronies: int = 2) -> tuple[np.ndarray, list[dict]]:
    """Make a 10x10 raster with n_baronies square patches + bars list.

    Barony 0 occupies top-left 5x5, barony 1 occupies top-right 5x5.
    Each barony belongs to condado_idx 0.
    """
    raster = np.full((10, 10), -1, dtype=np.int64)
    raster[:5, :5] = 0   # barony 0
    raster[:5, 5:] = 1   # barony 1
    bars = [
        {"name": "B0", "condado_idx": 0},
        {"name": "B1", "condado_idx": 0},
    ]
    return raster, bars


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_barony_features_have_condado_idx(tmp_path):
    """barony Feature.properties must contain condado_idx (int)."""
    cfg = _make_cfg(str(tmp_path))
    raster, bars = _make_raster_and_bars()
    # Empty cmap — we only care about geojson, not color file
    barony_cmap: dict[str, int] = {}
    build_baronies_geojson_sidecar(
        result=raster, bars=bars, cfg=cfg,
        barony_cmap=barony_cmap, out_dir=str(tmp_path),
    )
    with open(os.path.join(str(tmp_path), "baronies.geojson"), encoding="utf-8") as f:
        fc = json.load(f)

    assert len(fc["features"]) == 2
    for feat in fc["features"]:
        assert "condado_idx" in feat["properties"], (
            f"condado_idx missing from {feat['id']} properties"
        )
        assert isinstance(feat["properties"]["condado_idx"], int)


def test_barony_features_have_duchy_id(tmp_path):
    """barony Feature.properties must contain duchy_id (str), matching condado tuple[4]."""
    cfg = _make_cfg(str(tmp_path))
    raster, bars = _make_raster_and_bars()
    build_baronies_geojson_sidecar(
        result=raster, bars=bars, cfg=cfg,
        barony_cmap={}, out_dir=str(tmp_path),
    )
    with open(os.path.join(str(tmp_path), "baronies.geojson"), encoding="utf-8") as f:
        fc = json.load(f)

    for feat in fc["features"]:
        assert "duchy_id" in feat["properties"]
        assert feat["properties"]["duchy_id"] == "D1", (
            f"Expected duchy_id='D1', got {feat['properties']['duchy_id']!r}"
        )


def test_barony_features_have_kingdom_id(tmp_path):
    """barony Feature.properties must contain kingdom_id (str)."""
    cfg = _make_cfg(str(tmp_path))
    raster, bars = _make_raster_and_bars()
    build_baronies_geojson_sidecar(
        result=raster, bars=bars, cfg=cfg,
        barony_cmap={}, out_dir=str(tmp_path),
    )
    with open(os.path.join(str(tmp_path), "baronies.geojson"), encoding="utf-8") as f:
        fc = json.load(f)

    for feat in fc["features"]:
        assert "kingdom_id" in feat["properties"]
        assert feat["properties"]["kingdom_id"] == "K1", (
            f"Expected kingdom_id='K1', got {feat['properties']['kingdom_id']!r}"
        )


def test_existing_fields_not_regressed(tmp_path):
    """condado_id and centroid must still be present (regression guard)."""
    cfg = _make_cfg(str(tmp_path))
    raster, bars = _make_raster_and_bars()
    build_baronies_geojson_sidecar(
        result=raster, bars=bars, cfg=cfg,
        barony_cmap={}, out_dir=str(tmp_path),
    )
    with open(os.path.join(str(tmp_path), "baronies.geojson"), encoding="utf-8") as f:
        fc = json.load(f)

    for feat in fc["features"]:
        props = feat["properties"]
        assert "condado_id" in props, "condado_id regressed"
        assert "centroid" in props, "centroid regressed"
        assert "id" in props, "id regressed"
        assert "name" in props, "name regressed"
        assert "pixel_count" in props, "pixel_count regressed"
        # condado_id must resolve to "C0" (condados[0][0])
        assert props["condado_id"] == "C0"


def test_condado_idx_value_matches_bars_entry(tmp_path):
    """condado_idx in properties must match the value from bars[bi]['condado_idx']."""
    cfg = _make_cfg(str(tmp_path))
    raster, bars = _make_raster_and_bars()
    build_baronies_geojson_sidecar(
        result=raster, bars=bars, cfg=cfg,
        barony_cmap={}, out_dir=str(tmp_path),
    )
    with open(os.path.join(str(tmp_path), "baronies.geojson"), encoding="utf-8") as f:
        fc = json.load(f)

    feat_map = {f["id"]: f for f in fc["features"]}
    assert feat_map["B0"]["properties"]["condado_idx"] == 0
    assert feat_map["B1"]["properties"]["condado_idx"] == 0


def test_duchy_empty_when_condado_idx_out_of_range(tmp_path):
    """duchy_id and kingdom_id must be empty string when condado_idx is invalid."""
    cfg = _make_cfg(str(tmp_path))
    raster = np.full((10, 10), -1, dtype=np.int64)
    raster[:5, :5] = 0
    bars_bad = [{"name": "BOGUS", "condado_idx": 999}]  # out of range
    build_baronies_geojson_sidecar(
        result=raster, bars=bars_bad, cfg=cfg,
        barony_cmap={}, out_dir=str(tmp_path),
    )
    with open(os.path.join(str(tmp_path), "baronies.geojson"), encoding="utf-8") as f:
        fc = json.load(f)

    assert len(fc["features"]) == 1
    props = fc["features"][0]["properties"]
    assert props["duchy_id"] == ""
    assert props["kingdom_id"] == ""
    assert props["condado_id"] == ""
    # condado_idx is still emitted (the raw value from bars)
    assert props["condado_idx"] == 999
