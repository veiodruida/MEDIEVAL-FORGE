"""[BLOCKING] Real-pipeline integration test closing verification gap G-03.

Runs the real emit_*_from_disk codepath end-to-end against an on-disk fixture
that matches map_generator.py SECTION 10's output format exactly. Fails loudly
if either territories.geojson or baronies.geojson is missing or un-parseable.

Also covers G-02 (silent swallow removal) by corrupting the lookup file and
asserting the exception propagates out of run_generation instead of being
hidden by a try/except inside generator.py.
"""
import json
import uuid
from pathlib import Path

import numpy as np
import pytest
from PIL import Image


def _paint_rgb(
    path: Path,
    rgb_by_region: dict[tuple[int, int, int], tuple[int, int, int, int]],
) -> None:
    """Write a small RGB PNG where each (r,g,b) fills the given (x0,y0,x1,y1) rect."""
    arr = np.zeros((20, 20, 3), dtype=np.uint8)
    for (r, g, b), (x0, y0, x1, y1) in rgb_by_region.items():
        arr[y0:y1, x0:x1] = (r, g, b)
    Image.fromarray(arr, mode="RGB").save(path)


@pytest.fixture
def fake_generated_dir(tmp_path, monkeypatch):
    from medieval_forge.services import paths as _paths
    monkeypatch.setattr(_paths, "PROJECTS_ROOT", tmp_path / "projects")
    pid = str(uuid.uuid4())
    (_paths.PROJECTS_ROOT / pid / "raw").mkdir(parents=True)
    (_paths.PROJECTS_ROOT / pid / "raw" / "municipalities.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "Polygon",
             "coordinates": [[[-10, 36], [-10, 44], [0, 44], [0, 36], [-10, 36]]]},
             "properties": {}}
        ]})
    )
    gen = _paths.PROJECTS_ROOT / pid / "generated"
    gen.mkdir()
    # lookup_condado.png with two colors
    _paint_rgb(gen / "lookup_condado.png", {
        (10, 20, 30): (0, 0, 10, 20),
        (40, 50, 60): (10, 0, 20, 20),
    })
    # lookup_condado_colors.json in REAL format
    (gen / "lookup_condado_colors.json").write_text(
        json.dumps({"10,20,30": 0, "40,50,60": 1})
    )
    # lookup_barony.png with two colors
    _paint_rgb(gen / "lookup_barony.png", {
        (200, 10, 30): (0, 0, 10, 20),
        (15, 80, 240): (10, 0, 20, 20),
    })
    (gen / "lookup_barony_colors.json").write_text(
        json.dumps({"200,10,30": 0, "15,80,240": 1})
    )
    (gen / "territory_metadata.json").write_text(json.dumps({
        "region": "test",
        "map_size": [20, 20],
        "bounds": {"lon_min": -10.0, "lon_max": 0.0, "lat_min": 36.0, "lat_max": 44.0},
        "kingdoms": {"K1": "K1"},
        "duchies": {"D1": {"kingdom": "K1", "name": "D1"}},
        "condados": [
            {"id": "C_A", "name": "Alpha", "lon": -7.5, "lat": 42.0, "duchy": "D1",
             "kingdom": "K1", "pixel_center": [5, 10], "pixel_count": 200,
             "baronies": ["B_A1"]},
            {"id": "C_B", "name": "Beta",  "lon": -2.5, "lat": 42.0, "duchy": "D1",
             "kingdom": "K1", "pixel_center": [15, 10], "pixel_count": 200,
             "baronies": ["B_B1"]},
        ],
        "baronies": [
            {"name": "B_A1", "condado_idx": 0, "duchy": "D1", "pixel_count": 200},
            {"name": "B_B1", "condado_idx": 1, "duchy": "D1", "pixel_count": 200},
        ],
    }))
    return pid, gen


def test_run_generation_emits_both_geojson_artifacts(fake_generated_dir, monkeypatch):
    """[BLOCKING] closes G-03. Runs the real emitter orchestration end-to-end."""
    pid, gen = fake_generated_dir
    from medieval_forge.services import generator as gen_mod

    # Stub map_generator.generate_maps: fixture files already on disk, no-op.
    def _fake_generate_maps(region_cfg, territory_module, draw_names):
        # Ensure the generator's output_dir matches our fixture dir.
        assert Path(region_cfg.output_dir) == gen
    monkeypatch.setattr(gen_mod.map_generator, "generate_maps", _fake_generate_maps)

    config = {
        "territory_data": {
            "kingdoms": {"K1": "K1"},
            "duchies": {"D1": ("K1", "D1")},
            "condados": [
                ("C_A", "Alpha", -7.5, 42.0, "D1", [("B_A1", -7.5, 42.0)]),
                ("C_B", "Beta", -2.5, 42.0, "D1", [("B_B1", -2.5, 42.0)]),
            ],
        },
        "lon_min": -10.0, "lon_max": 0.0, "lat_min": 36.0, "lat_max": 44.0,
        "map_w": 20, "map_h": 20, "upscale": 1,
    }

    manifest = gen_mod._run_pipeline_sync(pid, gen, config)

    # [BLOCKING] assertions — fail loudly
    tpath = gen / "territories.geojson"
    bpath = gen / "baronies.geojson"
    assert tpath.exists(), f"BLOCKING: territories.geojson missing at {tpath}"
    assert bpath.exists(), f"BLOCKING: baronies.geojson missing at {bpath}"
    assert (gen / "condado_colors.json").exists(), (
        "BLOCKING: condado_colors.json sidecar missing"
    )
    assert (gen / "barony_colors.json").exists(), (
        "BLOCKING: barony_colors.json sidecar missing"
    )

    tdata = json.loads(tpath.read_text())
    bdata = json.loads(bpath.read_text())
    assert tdata["type"] == "FeatureCollection"
    assert bdata["type"] == "FeatureCollection"
    assert len(tdata["features"]) == 2
    assert len(bdata["features"]) == 2
    assert {f["id"] for f in tdata["features"]} == {"C_A", "C_B"}
    assert {f["id"] for f in bdata["features"]} == {"B_A1", "B_B1"}

    # Manifest surfaces all emitted files via the whitelist
    assert "territories.geojson" in manifest
    assert "baronies.geojson" in manifest
    assert "condado_colors.json" in manifest
    assert "barony_colors.json" in manifest


def test_emitter_error_propagates_to_caller(fake_generated_dir, monkeypatch):
    """G-02: malformed lookup colors must raise — no silent swallow."""
    pid, gen = fake_generated_dir
    # Corrupt the file so emit_territories_from_disk raises ValueError
    (gen / "lookup_condado_colors.json").write_text(
        json.dumps({"not-a-triple": 0})
    )

    from medieval_forge.services import generator as gen_mod

    def _fake_generate_maps(region_cfg, territory_module, draw_names):
        pass
    monkeypatch.setattr(gen_mod.map_generator, "generate_maps", _fake_generate_maps)

    config = {
        "territory_data": {
            "kingdoms": {"K1": "K1"},
            "duchies": {"D1": ("K1", "D1")},
            "condados": [("C_A", "Alpha", -7.5, 42.0, "D1", [("B_A1", -7.5, 42.0)])],
        },
        "lon_min": -10.0, "lon_max": 0.0, "lat_min": 36.0, "lat_max": 44.0,
        "map_w": 20, "map_h": 20, "upscale": 1,
    }

    with pytest.raises(ValueError, match="malformed key"):
        gen_mod._run_pipeline_sync(pid, gen, config)
