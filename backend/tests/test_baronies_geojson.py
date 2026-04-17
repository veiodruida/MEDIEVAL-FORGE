"""Tests for baronies_geojson — D-02 data dependency."""
import json
import uuid

import numpy as np
import pytest

from medieval_forge.services.baronies_geojson import build_baronies_geojson
from medieval_forge.services.territories_geojson import _ProjCfg


def _cfg():
    return _ProjCfg(-10.0, 0.0, 36.0, 44.0, 100, 80, 1, 0.78)


def test_emits_baronies_with_condado_id_and_fill(tmp_path, monkeypatch):
    pid = str(uuid.uuid4())
    from medieval_forge.services import paths as _paths
    monkeypatch.setattr(_paths, "PROJECTS_ROOT", tmp_path / "projects")
    W, H = 100, 80
    pb = np.full((H, W), -1, dtype=np.int32)
    pb[:40, :50] = 0
    pb[:40, 50:] = 1
    baronies = [
        {"name": "B_A1", "condado_idx": 0, "duchy": "D1", "pixel_count": 2000},
        {"name": "B_B1", "condado_idx": 1, "duchy": "D1", "pixel_count": 2000},
    ]
    condados = [
        ["C_A", "Alpha", -7.5, 42.0, "D1", ["B_A1"]],
        ["C_B", "Beta",  -2.5, 42.0, "D1", ["B_B1"]],
    ]
    colors = {"B_A1": "#ff0000", "B_B1": "#00ff00"}
    out = build_baronies_geojson(pid, pb, baronies, condados, _cfg(), colors)
    data = json.loads(out.read_text())
    assert data["type"] == "FeatureCollection"
    by_id = {f["id"]: f for f in data["features"]}
    assert by_id["B_A1"]["properties"]["condado_id"] == "C_A"
    assert by_id["B_A1"]["properties"]["fill"] == "#ff0000"
    assert by_id["B_B1"]["properties"]["condado_id"] == "C_B"
    assert by_id["B_B1"]["properties"]["fill"] == "#00ff00"


def test_barony_invalid_uuid_rejected():
    with pytest.raises(ValueError):
        build_baronies_geojson(
            "not-a-uuid",
            np.zeros((1, 1), dtype=np.int32),
            [],
            [],
            _cfg(),
            {},
        )


def test_barony_geometry_types(tmp_path, monkeypatch):
    pid = str(uuid.uuid4())
    from medieval_forge.services import paths as _paths
    monkeypatch.setattr(_paths, "PROJECTS_ROOT", tmp_path / "projects")
    W, H = 60, 60
    pb = np.full((H, W), 0, dtype=np.int32)
    baronies = [{"name": "B_X", "condado_idx": 0, "duchy": "D1", "pixel_count": 3600}]
    condados = [["C_X", "X", -5.0, 40.0, "D1", ["B_X"]]]
    colors = {"B_X": "#aabbcc"}
    out = build_baronies_geojson(pid, pb, baronies, condados, _cfg(), colors)
    data = json.loads(out.read_text())
    for f in data["features"]:
        assert f["geometry"]["type"] in ("Polygon", "MultiPolygon")


def test_barony_missing_color_uses_fallback(tmp_path, monkeypatch):
    pid = str(uuid.uuid4())
    from medieval_forge.services import paths as _paths
    monkeypatch.setattr(_paths, "PROJECTS_ROOT", tmp_path / "projects")
    W, H = 60, 60
    pb = np.full((H, W), 0, dtype=np.int32)
    baronies = [{"name": "B_NOCLR", "condado_idx": 0, "duchy": "D1", "pixel_count": 3600}]
    condados = [["C_X", "X", -5.0, 40.0, "D1", []]]
    out = build_baronies_geojson(pid, pb, baronies, condados, _cfg(), {})
    data = json.loads(out.read_text())
    assert data["features"][0]["properties"]["fill"] == "#888888"
