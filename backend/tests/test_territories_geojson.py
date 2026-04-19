"""Tests for territories_geojson — CANVAS-01 data dependency."""
import json
import uuid

import numpy as np
import pytest
from PIL import Image

from medieval_forge.services.territories_geojson import (
    build_territories_geojson,
    emit_territories_from_disk,
    _ProjCfg,
)


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


# ---------------------------------------------------------------------------
# G-01 closure: tests for emit_territories_from_disk — real `{"r,g,b": idx}`
# format consumption + condado_colors.json sidecar emission.
# ---------------------------------------------------------------------------


def _write_metadata(gen_dir, condados_tuples, baronies=None):
    """Write territory_metadata.json with the structure emit_*_from_disk expects."""
    condados_meta = []
    for idx, c in enumerate(condados_tuples):
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
        "baronies": baronies or [],
    }))


def _paint_two_colors(path, color_a, color_b, W=20, H=20):
    """Write a small RGB PNG split into left half (color_a) and right half (color_b)."""
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    arr[:, :W // 2] = color_a
    arr[:, W // 2:] = color_b
    Image.fromarray(arr, mode="RGB").save(path)


def test_emit_territories_from_disk_parses_real_format_and_writes_sidecar(
    tmp_path, monkeypatch,
):
    """G-01: consume `{"r,g,b": idx}` — NOT `{condado_id: "#hex"}`."""
    pid = str(uuid.uuid4())
    from medieval_forge.services import paths as _paths
    monkeypatch.setattr(_paths, "PROJECTS_ROOT", tmp_path / "projects")
    gen = _paths.PROJECTS_ROOT / pid / "generated"
    gen.mkdir(parents=True)

    _paint_two_colors(gen / "lookup_condado.png", (10, 20, 30), (40, 50, 60))
    # Real format from map_generator.py SECTION 10:
    (gen / "lookup_condado_colors.json").write_text(
        json.dumps({"10,20,30": 0, "40,50,60": 1})
    )
    _write_metadata(gen, [
        ("C_A", "Alpha", -7.5, 42.0, "D1", []),
        ("C_B", "Beta",  -2.5, 42.0, "D1", []),
    ])

    cfg = _ProjCfg(-10.0, 0.0, 36.0, 44.0, 20, 20, 1, 0.78)
    out = emit_territories_from_disk(pid, gen, cfg)
    data = json.loads(out.read_text())
    ids = {f["id"] for f in data["features"]}
    assert ids == {"C_A", "C_B"}

    # condado_colors.json sidecar with {id: "#rrggbb"} — frontend consumable
    sidecar_path = gen / "condado_colors.json"
    assert sidecar_path.exists(), "condado_colors.json sidecar must be emitted"
    sidecar = json.loads(sidecar_path.read_text())
    # Zero-padded hex must come out as '#0a141e' (not '#a141e')
    assert sidecar == {"C_A": "#0a141e", "C_B": "#28323c"}, sidecar


def test_emit_territories_from_disk_malformed_key_raises_value_error(
    tmp_path, monkeypatch,
):
    """G-01 / G-02 invariant: malformed keys must raise, not silently mis-parse."""
    pid = str(uuid.uuid4())
    from medieval_forge.services import paths as _paths
    monkeypatch.setattr(_paths, "PROJECTS_ROOT", tmp_path / "projects")
    gen = _paths.PROJECTS_ROOT / pid / "generated"
    gen.mkdir(parents=True)

    _paint_two_colors(gen / "lookup_condado.png", (10, 20, 30), (40, 50, 60))
    (gen / "lookup_condado_colors.json").write_text(
        json.dumps({"not,a,triple,extra": 0})
    )
    _write_metadata(gen, [("C_A", "Alpha", -7.5, 42.0, "D1", [])])

    cfg = _ProjCfg(-10.0, 0.0, 36.0, 44.0, 20, 20, 1, 0.78)
    with pytest.raises(ValueError, match="malformed key"):
        emit_territories_from_disk(pid, gen, cfg)


def test_pixel_polygon_to_lonlat_uses_actual_pc_shape_not_upscaled_dims(
    tmp_path, monkeypatch,
):
    """Regression: BUG-1 — lookup PNG is at map_w×map_h (NOT map_w*upscale×map_h*upscale).

    With upscale=2, the buggy code used W=map_w*2, H=map_h*2 for the inverse
    projection, which compressed all lon/lat coords to ~50% of the valid range.
    The fix reads W/H from pc.shape (the actual raster dimensions).

    This test uses upscale=2 with a PNG painted at map_w×map_h (40×40, not 80×80)
    so that the shapes rasterio emits are in 0..40 pixel space.  After the fix
    the emitted polygon vertices must cover nearly the full geographic bounds.
    """
    pid = str(uuid.uuid4())
    from medieval_forge.services import paths as _paths
    monkeypatch.setattr(_paths, "PROJECTS_ROOT", tmp_path / "projects")
    gen = _paths.PROJECTS_ROOT / pid / "generated"
    gen.mkdir(parents=True)

    map_w, map_h = 40, 40
    # PNG is at map_w × map_h — NOT at map_w*upscale × map_h*upscale.
    # This matches what map_generator.generate_lookup_map actually writes.
    _paint_two_colors(gen / "lookup_condado.png", (10, 20, 30), (40, 50, 60),
                      W=map_w, H=map_h)
    (gen / "lookup_condado_colors.json").write_text(
        json.dumps({"10,20,30": 0, "40,50,60": 1})
    )

    lon_min, lon_max = -10.0, 0.0
    lat_min, lat_max = 36.0, 44.0
    _write_metadata(gen, [
        ("C_A", "Alpha", -7.5, 42.0, "D1", []),
        ("C_B", "Beta",  -2.5, 42.0, "D1", []),
    ])
    # Overwrite the map_size in metadata to match map_w*upscale (upscaled terrain dims).
    meta_path = gen / "territory_metadata.json"
    meta = json.loads(meta_path.read_text())
    meta["map_size"] = [map_w * 2, map_h * 2]  # upscaled terrain is 80×80
    meta["bounds"] = {"lon_min": lon_min, "lon_max": lon_max,
                      "lat_min": lat_min, "lat_max": lat_max}
    meta_path.write_text(json.dumps(meta))

    # upscale=2: the BUGGY code would divide by map_w*upscale=80 instead of 40.
    cfg = _ProjCfg(lon_min, lon_max, lat_min, lat_max,
                   map_w=map_w, map_h=map_h, upscale=2, lon_scale=0.78)
    out = emit_territories_from_disk(pid, gen, cfg)
    data = json.loads(out.read_text())

    all_lons: list[float] = []
    all_lats: list[float] = []
    for feat in data["features"]:
        geom = feat["geometry"]
        rings = (geom["coordinates"] if geom["type"] == "Polygon"
                 else [r for poly in geom["coordinates"] for r in poly])
        for ring in rings:
            for coord in ring:
                all_lons.append(coord[0])
                all_lats.append(coord[1])

    # With the fix, vertices from the RIGHT half of the PNG must reach near lon_max.
    # The right half starts at pixel x=20; in a 40-wide image that is x/40 = 0.5 of span.
    # The rightmost pixels are at x≈40, so lon ≈ lon_max.  Allow 5% tolerance.
    lon_range = max(all_lons) - min(all_lons)
    lat_range = max(all_lats) - min(all_lats)
    expected_lon_span = lon_max - lon_min  # 10.0
    expected_lat_span = lat_max - lat_min  # 8.0

    assert lon_range > expected_lon_span * 0.85, (
        f"lon range {lon_range:.3f} < 85% of expected {expected_lon_span}; "
        "territories still compressed — upscale mismatch not fixed"
    )
    assert lat_range > expected_lat_span * 0.85, (
        f"lat range {lat_range:.3f} < 85% of expected {expected_lat_span}; "
        "territories still compressed — upscale mismatch not fixed"
    )


def test_emit_territories_from_disk_out_of_range_idx_skipped_not_crashed(
    tmp_path, monkeypatch,
):
    """Out-of-range idx warns + is skipped; remaining features still emitted."""
    pid = str(uuid.uuid4())
    from medieval_forge.services import paths as _paths
    monkeypatch.setattr(_paths, "PROJECTS_ROOT", tmp_path / "projects")
    gen = _paths.PROJECTS_ROOT / pid / "generated"
    gen.mkdir(parents=True)

    _paint_two_colors(gen / "lookup_condado.png", (10, 20, 30), (40, 50, 60))
    # idx=9 is out of range (only 1 condado in metadata)
    (gen / "lookup_condado_colors.json").write_text(
        json.dumps({"10,20,30": 0, "40,50,60": 9})
    )
    _write_metadata(gen, [("C_A", "Alpha", -7.5, 42.0, "D1", [])])

    cfg = _ProjCfg(-10.0, 0.0, 36.0, 44.0, 20, 20, 1, 0.78)
    out = emit_territories_from_disk(pid, gen, cfg)
    data = json.loads(out.read_text())
    # Only C_A emitted; the out-of-range entry is silently skipped.
    assert {f["id"] for f in data["features"]} == {"C_A"}


# ---------------------------------------------------------------------------
# Problem B fix: orig_idx → meta_ci remapping via original_condados parameter
# ---------------------------------------------------------------------------


def _paint_three_regions(path, color_a, color_b, color_c, W=30, H=20):
    """Write a small RGB PNG split into three vertical thirds."""
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    third = W // 3
    arr[:, :third] = color_a
    arr[:, third:2 * third] = color_b
    arr[:, 2 * third:] = color_c
    Image.fromarray(arr, mode="RGB").save(path)


def test_emit_territories_orig_idx_remapped_to_meta_ci(tmp_path, monkeypatch):
    """Problem B regression: survivors with original index >= n_survivors must be emitted.

    Scenario: 100-entry original condados list. Only 3 survive (indices 5, 7, 99).
    generate_lookup_map writes colors_raw = {color_A: 5, color_B: 7, color_C: 99}.
    export_metadata writes 3 survivors re-indexed 0,1,2 in metadata.

    Without the fix, pc stores values 5, 7, 99 and build_territories_geojson
    loops ci in 0..2 — never matching 5, 7, or 99 → 0 features emitted.
    With the fix, pc stores values 0, 1, 2 (meta positions) → 3 features emitted.
    """
    pid = str(uuid.uuid4())
    from medieval_forge.services import paths as _paths
    monkeypatch.setattr(_paths, "PROJECTS_ROOT", tmp_path / "projects")
    gen = _paths.PROJECTS_ROOT / pid / "generated"
    gen.mkdir(parents=True)

    # Three survivors at original indices 5, 7, 99 in a 100-condado universe.
    # Colors chosen so they don't collide with map_generator's formula.
    color_a = (50, 60, 70)
    color_b = (80, 90, 100)
    color_c = (110, 120, 130)

    _paint_three_regions(gen / "lookup_condado.png", color_a, color_b, color_c)

    # colors_raw uses ORIGINAL indices as values (as generate_lookup_map writes them).
    (gen / "lookup_condado_colors.json").write_text(json.dumps({
        f"{color_a[0]},{color_a[1]},{color_a[2]}": 5,
        f"{color_b[0]},{color_b[1]},{color_b[2]}": 7,
        f"{color_c[0]},{color_c[1]},{color_c[2]}": 99,
    }))

    # Metadata has only the 3 survivors, re-indexed 0..2.
    _write_metadata(gen, [
        ("COND_5",  "Condado5",  -8.0, 42.0, "D1", []),
        ("COND_7",  "Condado7",  -5.0, 42.0, "D1", []),
        ("COND_99", "Condado99", -2.0, 42.0, "D1", []),
    ])

    # original_condados: 100-entry list; positions 5, 7, 99 are the survivors.
    original_condados = [
        [f"DROPPED_{i}", f"Dropped{i}", -10.0, 36.0, "D1", []]
        for i in range(100)
    ]
    original_condados[5]  = ["COND_5",  "Condado5",  -8.0, 42.0, "D1", []]
    original_condados[7]  = ["COND_7",  "Condado7",  -5.0, 42.0, "D1", []]
    original_condados[99] = ["COND_99", "Condado99", -2.0, 42.0, "D1", []]

    cfg = _ProjCfg(-10.0, 0.0, 36.0, 44.0, 30, 20, 1, 0.78)
    out = emit_territories_from_disk(pid, gen, cfg, original_condados=original_condados)
    data = json.loads(out.read_text())

    ids = {f["id"] for f in data["features"]}
    assert ids == {"COND_5", "COND_7", "COND_99"}, (
        f"Expected 3 features (COND_5, COND_7, COND_99) but got: {ids}. "
        "Survivors with orig_idx >= n_survivors must be emitted after remap."
    )
    assert len(data["features"]) == 3
