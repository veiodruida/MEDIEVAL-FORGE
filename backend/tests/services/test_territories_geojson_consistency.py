"""Regression tests for quick-260426-pcy: metadata.condados.id ⊆ geojson.features.id.

These tests reproduce the historical orphan bug (12 condados in
territory_metadata.json missing from territories.geojson on project
2d402c81-0b72-4cbb-8b61-21d72eff2a44 — alcacer, beja, braga, braganca,
chaves, evora, lamego, porto, salamanca, santarem, tui, viana) and assert
the post-fix invariants:

1. set(metadata.condados.id) == set(geojson.features.id) when the FULL
   original_condados list is passed to emit_territories_from_disk (the
   contract that production call site services/generator.py:361 honours).
2. The legacy fallback path (original_condados=None) raises ValueError
   instead of silently dropping out-of-range orig_idx — the previous
   silent skip is the antipattern that hid the bug for an entire UAT round.
3. build_territories_geojson logs an ERROR when set(metadata ids) -
   set(feature ids) is non-empty (soft-assertion belt + suspenders so any
   future regression surfaces in logs).

Tests use small handcrafted numpy arrays + PNGs (no real project data
required).  Each test would FAIL on the pre-fix code (commit prior to
21e6614) and PASSES post-fix.
"""
from __future__ import annotations

import json
import logging
import uuid

import numpy as np
import pytest
from PIL import Image

from medieval_forge.services.territories_geojson import (
    _ProjCfg,
    build_territories_geojson,
    emit_territories_from_disk,
)


# ---------------------------------------------------------------------------
# Fixture helpers — descriptive, explicit numeric values (per project
# convention from feedback-tests-descriptive.md).
# ---------------------------------------------------------------------------

# Three handcrafted RGBs that DO NOT collide with the default RegionConfig
# ocean_far (70, 130, 180), so any failure here is unambiguously the
# index-space mismatch and not a colour collision.
COLOR_TUI       = (50,  60,  70)   # bug-equivalent: orig_idx 27 (out of meta range)
COLOR_PORTO     = (80,  90,  100)  # bug-equivalent: orig_idx 28 (out of meta range)
COLOR_BADAJOZ   = (110, 120, 130)  # bug-equivalent: orig_idx 12 (within meta range)


def _paint_three_horizontal_bands(path, color_top, color_mid, color_bot, w=30, h=30):
    """Write a 30x30 RGB PNG split into three horizontal bands."""
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[:10, :]   = color_top
    arr[10:20, :] = color_mid
    arr[20:, :]   = color_bot
    Image.fromarray(arr, mode="RGB").save(path)


def _write_metadata(gen_dir, condados_tuples):
    """Write territory_metadata.json with explicit pixel_center per condado."""
    payload = {
        "region": "test",
        "map_size": [30, 30],
        "bounds": {"lon_min": -10.0, "lon_max": 0.0,
                   "lat_min":  36.0, "lat_max": 44.0},
        "kingdoms": {},
        "duchies":  {},
        "condados": [
            {
                "id": cid, "name": name,
                "lon": lon, "lat": lat,
                "duchy": duchy,
                "kingdom": "K1",
                "pixel_center": pc_xy,
                "pixel_count": pc_count,
                "baronies": [],
            }
            for (cid, name, lon, lat, duchy, pc_xy, pc_count) in condados_tuples
        ],
        "baronies": [],
    }
    (gen_dir / "territory_metadata.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8",
    )


def _project_dirs(tmp_path, monkeypatch):
    """Create a fake project directory tree under tmp_path and return the
    generated/ subdir.  Patches PROJECTS_ROOT so emit_*_from_disk resolves
    via paths.project_dir().
    """
    pid = str(uuid.uuid4())
    from medieval_forge.services import paths as _paths
    monkeypatch.setattr(_paths, "PROJECTS_ROOT", tmp_path / "projects")
    gen = _paths.PROJECTS_ROOT / pid / "generated"
    gen.mkdir(parents=True)
    return pid, gen


# ---------------------------------------------------------------------------
# Test 1 — the historical bug fixture: original_condados is REQUIRED for the
# orig_idx → meta_ci remap.  Passing it produces full id-set equality.
# ---------------------------------------------------------------------------


def test_metadata_and_geojson_have_matching_condado_ids_when_original_condados_passed(
    tmp_path, monkeypatch,
):
    """Reproduces the bug-trigger: 3 surviving condados, two of whose
    orig_idx values (27, 28) exceed len(condados_meta)==3.  With the
    Problem B remap (original_condados passed), all three features must
    appear in territories.geojson — id-set equality with metadata.
    """
    pid, gen = _project_dirs(tmp_path, monkeypatch)

    _paint_three_horizontal_bands(
        gen / "lookup_condado.png",
        COLOR_TUI, COLOR_PORTO, COLOR_BADAJOZ,
    )
    # colors.json with TWO out-of-range orig_idx values (27, 28) and one
    # in-range (12).  This is the exact pattern from the bug repro.
    (gen / "lookup_condado_colors.json").write_text(json.dumps({
        f"{COLOR_TUI[0]},{COLOR_TUI[1]},{COLOR_TUI[2]}":         27,
        f"{COLOR_PORTO[0]},{COLOR_PORTO[1]},{COLOR_PORTO[2]}":   28,
        f"{COLOR_BADAJOZ[0]},{COLOR_BADAJOZ[1]},{COLOR_BADAJOZ[2]}": 12,
    }))
    _write_metadata(gen, [
        ("tui",     "Tui",     -8.0, 42.0, "D1", [15, 5],  300),
        ("porto",   "Porto",   -8.0, 41.0, "D1", [15, 15], 300),
        ("badajoz", "Badajoz", -7.0, 38.0, "D2", [15, 25], 300),
    ])

    # original_condados must include positions 12, 27, 28 with the right ids.
    original = [["__dropped", "x", -99.0, -99.0, "", []] for _ in range(30)]
    original[12] = ["badajoz", "Badajoz", -7.0, 38.0, "D2", []]
    original[27] = ["tui",     "Tui",     -8.0, 42.0, "D1", []]
    original[28] = ["porto",   "Porto",   -8.0, 41.0, "D1", []]

    cfg = _ProjCfg(-10.0, 0.0, 36.0, 44.0, 30, 30, 1, 0.78)
    out = emit_territories_from_disk(
        pid, gen, cfg, original_condados=original,
    )
    data = json.loads(out.read_text())

    metadata_ids = {"tui", "porto", "badajoz"}
    feature_ids  = {f["id"] for f in data["features"]}
    assert feature_ids == metadata_ids, (
        f"id-set equality broken: metadata={sorted(metadata_ids)}, "
        f"geojson={sorted(feature_ids)}, missing="
        f"{sorted(metadata_ids - feature_ids)}.  Pre-fix, the 12 orphans "
        "from project 2d402c81 had identical structure (orig_idx >= "
        "n_meta) and were silently dropped."
    )


def test_metadata_and_geojson_have_matching_condado_ids_via_build_geojson_directly(
    tmp_path, monkeypatch,
):
    """Direct check on build_territories_geojson: every condado that has
    pixels in pc must appear as a feature.  No PNG roundtrip — eliminates
    PIL/format variables.
    """
    pid, gen = _project_dirs(tmp_path, monkeypatch)

    W, H = 30, 30
    pc = np.full((H, W), -1, dtype=np.int32)
    pc[:10, :]   = 0  # tui      — meta_ci 0
    pc[10:20, :] = 1  # porto    — meta_ci 1
    pc[20:, :]   = 2  # badajoz  — meta_ci 2

    condados = [
        ["tui",     "Tui",     -8.0, 42.0, "D1", []],
        ["porto",   "Porto",   -8.0, 41.0, "D1", []],
        ["badajoz", "Badajoz", -7.0, 38.0, "D2", []],
    ]
    cfg = _ProjCfg(-10.0, 0.0, 36.0, 44.0, W, H, 1, 0.78)
    out = build_territories_geojson(pid, pc, condados, cfg)
    data = json.loads(out.read_text())

    assert {f["id"] for f in data["features"]} == {"tui", "porto", "badajoz"}


# ---------------------------------------------------------------------------
# Test 2 — fail-loud contract: the legacy fallback path now raises rather
# than silently dropping.  This is the core deviation from the previous
# silent-skip behaviour that hid the bug.
# ---------------------------------------------------------------------------


def test_legacy_fallback_raises_on_out_of_range_orig_idx(tmp_path, monkeypatch):
    """Without original_condados, an out-of-range orig_idx in colors.json
    must raise ValueError mentioning 'out of range'.  Pre-fix this was a
    logger.warning + continue — the silent skip that dropped 12 condados.
    """
    pid, gen = _project_dirs(tmp_path, monkeypatch)

    _paint_three_horizontal_bands(
        gen / "lookup_condado.png",
        COLOR_TUI, COLOR_PORTO, COLOR_BADAJOZ,
    )
    (gen / "lookup_condado_colors.json").write_text(json.dumps({
        f"{COLOR_TUI[0]},{COLOR_TUI[1]},{COLOR_TUI[2]}":         27,
        f"{COLOR_PORTO[0]},{COLOR_PORTO[1]},{COLOR_PORTO[2]}":   28,
        f"{COLOR_BADAJOZ[0]},{COLOR_BADAJOZ[1]},{COLOR_BADAJOZ[2]}": 12,
    }))
    _write_metadata(gen, [
        ("tui",     "Tui",     -8.0, 42.0, "D1", [15, 5],  300),
        ("porto",   "Porto",   -8.0, 41.0, "D1", [15, 15], 300),
        ("badajoz", "Badajoz", -7.0, 38.0, "D2", [15, 25], 300),
    ])

    cfg = _ProjCfg(-10.0, 0.0, 36.0, 44.0, 30, 30, 1, 0.78)
    with pytest.raises(ValueError, match="out of range"):
        emit_territories_from_disk(pid, gen, cfg)  # original_condados omitted


# ---------------------------------------------------------------------------
# Test 3 — soft-assertion log: any condado in metadata that produces no
# feature must emit an ERROR-level log line (without raising).
# ---------------------------------------------------------------------------


def test_orphan_invariant_logs_when_metadata_condado_has_no_pixels(
    tmp_path, monkeypatch, caplog,
):
    """build_territories_geojson logs ERROR listing every metadata id that
    failed to produce a feature.  Soft-assertion contract: future
    regressions surface in logs even if the file is still written.
    """
    pid, gen = _project_dirs(tmp_path, monkeypatch)

    W, H = 20, 20
    pc = np.full((H, W), -1, dtype=np.int32)
    pc[:10, :] = 0  # only meta_ci 0 has pixels — meta_ci 1 will orphan

    condados = [
        ["c_with_pixels", "Has Pixels",     -7.5, 42.0, "D1", []],
        ["c_orphaned",    "Has No Pixels",  -7.5, 38.0, "D1", []],
    ]
    cfg = _ProjCfg(-10.0, 0.0, 36.0, 44.0, W, H, 1, 0.78)

    with caplog.at_level(
        logging.ERROR, logger="medieval_forge.services.territories_geojson",
    ):
        out = build_territories_geojson(pid, pc, condados, cfg)

    # File still produced (soft assertion, not raise).
    data = json.loads(out.read_text())
    assert {f["id"] for f in data["features"]} == {"c_with_pixels"}

    # Error log mentions the missing count and the orphan id.
    assert any(
        "MISSING" in record.message and "c_orphaned" in record.message
        for record in caplog.records
        if record.levelno == logging.ERROR
    ), (
        f"expected ERROR log mentioning missing condado 'c_orphaned'; got: "
        f"{[r.message for r in caplog.records]}"
    )
