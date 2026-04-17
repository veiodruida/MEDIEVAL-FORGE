"""Tests for territories_geojson — CANVAS-01 data dependency."""
import json
import uuid

import numpy as np
import pytest

from medieval_forge.services.territories_geojson import build_territories_geojson, _ProjCfg


def _cfg(mw=100, mh=80):
    return _ProjCfg(
        lon_min=-10.0, lon_max=0.0, lat_min=36.0, lat_max=44.0,
        map_w=mw, map_h=mh, upscale=1, lon_scale=0.78,
    )


def test_emits_geojson_with_id_polygon_neighbors(tmp_path, monkeypatch):
    pid = str(uuid.uuid4())
    from medieval_forge.services import paths as _paths
    monkeypatch.setattr(_paths, "PROJECTS_ROOT", tmp_path / "projects")

    W, H = 100, 80
    pc = np.full((H, W), -1, dtype=np.int32)
    # A: top-left quadrant, B: top-right, C: bottom-left
    pc[:40, :50] = 0
    pc[:40, 50:] = 1
    pc[40:, :50] = 2

    condados = [
        ["C_A", "AlphaLand", -7.5, 42.0, "D1", []],
        ["C_B", "BetaLand",  -2.5, 42.0, "D1", []],
        ["C_C", "GammaLand", -7.5, 38.0, "D1", []],
    ]
    out = build_territories_geojson(pid, pc, condados, _cfg())
    data = json.loads(out.read_text())
    assert data["type"] == "FeatureCollection"
    ids = {f["id"] for f in data["features"]}
    assert ids == {"C_A", "C_B", "C_C"}
    for f in data["features"]:
        assert f["geometry"]["type"] in ("Polygon", "MultiPolygon")
        assert isinstance(f["properties"]["neighbors"], list)
    by_id = {f["id"]: f for f in data["features"]}
    # C_A shares a full edge with both C_B (right side) and C_C (bottom side)
    assert set(by_id["C_A"]["properties"]["neighbors"]) == {"C_B", "C_C"}
    # C_B and C_C share at least one neighbor (C_A); they may also touch at a
    # corner point (pixel (50,40)) which shapely.touches() counts as adjacency.
    assert "C_A" in by_id["C_B"]["properties"]["neighbors"]
    assert "C_A" in by_id["C_C"]["properties"]["neighbors"]
    # No self-loops
    for f in data["features"]:
        assert f["id"] not in f["properties"]["neighbors"]


def test_invalid_uuid_rejected():
    with pytest.raises(ValueError):
        build_territories_geojson(
            "not-a-uuid", np.zeros((1, 1), dtype=np.int32), [], _cfg()
        )


def test_whitelist_contains_territories_and_baronies_geojson():
    from medieval_forge.services.generator import GENERATED_FILE_WHITELIST
    assert "territories.geojson" in GENERATED_FILE_WHITELIST
    assert "baronies.geojson" in GENERATED_FILE_WHITELIST


def test_empty_condados_produces_empty_feature_collection(tmp_path, monkeypatch):
    pid = str(uuid.uuid4())
    from medieval_forge.services import paths as _paths
    monkeypatch.setattr(_paths, "PROJECTS_ROOT", tmp_path / "projects")
    pc = np.full((10, 10), -1, dtype=np.int32)
    out = build_territories_geojson(pid, pc, [], _cfg())
    data = json.loads(out.read_text())
    assert data["features"] == []


def test_neighbors_no_self_loops(tmp_path, monkeypatch):
    """Condado must not list itself as a neighbor."""
    pid = str(uuid.uuid4())
    from medieval_forge.services import paths as _paths
    monkeypatch.setattr(_paths, "PROJECTS_ROOT", tmp_path / "projects")
    W, H = 50, 50
    pc = np.full((H, W), -1, dtype=np.int32)
    pc[:25, :] = 0
    pc[25:, :] = 1
    condados = [
        ["C_TOP", "Top", -7.5, 42.0, "D1", []],
        ["C_BOT", "Bottom", -7.5, 38.0, "D1", []],
    ]
    out = build_territories_geojson(pid, pc, condados, _cfg())
    data = json.loads(out.read_text())
    by_id = {f["id"]: f for f in data["features"]}
    assert "C_TOP" not in by_id["C_TOP"]["properties"]["neighbors"]
    assert "C_BOT" not in by_id["C_BOT"]["properties"]["neighbors"]
