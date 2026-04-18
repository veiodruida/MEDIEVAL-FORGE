"""Tests for baronies_geojson — D-02 data dependency."""
import json
import uuid

import numpy as np
import pytest
from PIL import Image

from medieval_forge.services.baronies_geojson import (
    build_baronies_geojson,
    emit_baronies_from_disk,
)
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


# ---------------------------------------------------------------------------
# G-01 closure: tests for emit_baronies_from_disk — real `{"r,g,b": idx}`
# format consumption + barony_colors.json sidecar emission.
# ---------------------------------------------------------------------------


def _write_metadata(gen_dir, condados_tuples, baronies_dicts):
    condados_meta = []
    for c in condados_tuples:
        condados_meta.append({
            "id": c[0], "name": c[1], "lon": c[2], "lat": c[3],
            "duchy": c[4] if len(c) > 4 else "",
            "kingdom": "K1",
            "pixel_center": [5, 5],
            "pixel_count": 200,
            "baronies": c[5] if len(c) > 5 else [],
        })
    (gen_dir / "territory_metadata.json").write_text(json.dumps({
        "region": "test",
        "map_size": [20, 20],
        "bounds": {"lon_min": -10.0, "lon_max": 0.0, "lat_min": 36.0, "lat_max": 44.0},
        "kingdoms": {"K1": "K1"},
        "duchies": {"D1": {"kingdom": "K1", "name": "D1"}},
        "condados": condados_meta,
        "baronies": baronies_dicts,
    }))


def _paint_two_colors(path, color_a, color_b, W=20, H=20):
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    arr[:, :W // 2] = color_a
    arr[:, W // 2:] = color_b
    Image.fromarray(arr, mode="RGB").save(path)


def test_emit_baronies_from_disk_parses_real_format_and_writes_sidecar(
    tmp_path, monkeypatch,
):
    """G-01: parse `{"r,g,b": idx}` and emit barony_colors.json sidecar."""
    pid = str(uuid.uuid4())
    from medieval_forge.services import paths as _paths
    monkeypatch.setattr(_paths, "PROJECTS_ROOT", tmp_path / "projects")
    gen = _paths.PROJECTS_ROOT / pid / "generated"
    gen.mkdir(parents=True)

    _paint_two_colors(gen / "lookup_barony.png", (200, 10, 30), (15, 80, 240))
    (gen / "lookup_barony_colors.json").write_text(
        json.dumps({"200,10,30": 0, "15,80,240": 1})
    )
    _write_metadata(
        gen,
        condados_tuples=[
            ("C_A", "Alpha", -7.5, 42.0, "D1", ["B_A1"]),
            ("C_B", "Beta",  -2.5, 42.0, "D1", ["B_B1"]),
        ],
        baronies_dicts=[
            {"name": "B_A1", "condado_idx": 0, "duchy": "D1", "pixel_count": 200},
            {"name": "B_B1", "condado_idx": 1, "duchy": "D1", "pixel_count": 200},
        ],
    )

    cfg = _ProjCfg(-10.0, 0.0, 36.0, 44.0, 20, 20, 1, 0.78)
    out = emit_baronies_from_disk(pid, gen, cfg)
    data = json.loads(out.read_text())
    by_id = {f["id"]: f for f in data["features"]}
    assert set(by_id) == {"B_A1", "B_B1"}
    # Fill comes from the server-resolved hex string derived from the raw rgb
    assert by_id["B_A1"]["properties"]["fill"] == "#c80a1e"
    assert by_id["B_B1"]["properties"]["fill"] == "#0f50f0"
    assert by_id["B_A1"]["properties"]["condado_id"] == "C_A"
    assert by_id["B_B1"]["properties"]["condado_id"] == "C_B"

    sidecar_path = gen / "barony_colors.json"
    assert sidecar_path.exists(), "barony_colors.json sidecar must be emitted"
    sidecar = json.loads(sidecar_path.read_text())
    assert sidecar == {"B_A1": "#c80a1e", "B_B1": "#0f50f0"}, sidecar


def test_emit_baronies_from_disk_malformed_key_raises_value_error(
    tmp_path, monkeypatch,
):
    """G-01 / G-02 invariant: malformed keys must raise, not silently mis-parse."""
    pid = str(uuid.uuid4())
    from medieval_forge.services import paths as _paths
    monkeypatch.setattr(_paths, "PROJECTS_ROOT", tmp_path / "projects")
    gen = _paths.PROJECTS_ROOT / pid / "generated"
    gen.mkdir(parents=True)

    _paint_two_colors(gen / "lookup_barony.png", (200, 10, 30), (15, 80, 240))
    (gen / "lookup_barony_colors.json").write_text(
        json.dumps({"not,a,triple,extra": 0})
    )
    _write_metadata(
        gen,
        condados_tuples=[("C_A", "Alpha", -7.5, 42.0, "D1", ["B_A1"])],
        baronies_dicts=[
            {"name": "B_A1", "condado_idx": 0, "duchy": "D1", "pixel_count": 200},
        ],
    )

    cfg = _ProjCfg(-10.0, 0.0, 36.0, 44.0, 20, 20, 1, 0.78)
    with pytest.raises(ValueError, match="malformed key"):
        emit_baronies_from_disk(pid, gen, cfg)
