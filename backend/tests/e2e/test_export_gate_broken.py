"""SC-4-Broken + D-14 + D-17 + D-18: broken France output triggers exact D-08 codes.

D-14: no committed broken YAML -- fixtures mutate France's clean output in-place.
D-17: per-fixture assertions on the expected code(s) appearing in report.errors.
D-18: validator collects ALL errors (no fail-fast except SCHEMA_INVALID).
SC-4-Broken: broken is BLOCKED with the structured error list.

Fixture strategy: copy France's clean output into a per-test tmp dir, mutate the
copy, run validate_export, assert the expected code(s) appear in report.errors.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from medieval_forge.services.export import validate_export
from medieval_forge.services.pipeline import run_pipeline
from medieval_forge.services.pipeline.region_loader import (
    clear_region_cache,
    load_region,
)

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def clean_france_output(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run France pipeline once per module; per-test fixtures copy this."""
    out = tmp_path_factory.mktemp("france_broken_source")
    clear_region_cache()
    cfg = replace(load_region("france_1066"), output_dir=str(out))
    run_pipeline(cfg)
    return out


@pytest.fixture
def france_cfg():
    clear_region_cache()
    return load_region("france_1066")


def _copy_clean(clean_dir: Path, dst: Path) -> Path:
    """Copy clean France output into dst. Returns dst."""
    dst.mkdir(parents=True, exist_ok=True)
    for f in clean_dir.iterdir():
        if f.is_file():
            shutil.copy2(f, dst / f.name)
    return dst


def test_clean_copy_still_passes_gate(
    clean_france_output: Path, france_cfg, tmp_path: Path
) -> None:
    """Sanity: an unmutated copy of clean France passes the gate.

    If this fails, the copy procedure is broken -- diagnose before trusting
    broken-case results.
    """
    out = _copy_clean(clean_france_output, tmp_path / "clean")
    report, _sha = validate_export(out, france_cfg)
    assert report.passed, f"clean copy FAILED: {[e.code for e in report.errors]}"


def test_broken_drop_original_idx_triggers_missing_original_idx_only(
    clean_france_output: Path, france_cfg, tmp_path: Path
) -> None:
    """D-17: at least one MISSING_ORIGINAL_IDX error from the induced removal."""
    out = _copy_clean(clean_france_output, tmp_path / "drop_oidx")
    meta_path = out / "territory_metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["condados"], "France output has no condados -- fixture broken"
    # Hard precondition: France toy must carry original_idx on condados
    # (Phase 05 STATE.md: autogen emits original_idx). Without it, the
    # induced "del" is a no-op and the assertion downstream would mislead.
    assert "original_idx" in meta["condados"][0], (
        "France toy condado missing original_idx -- _autogen_territories regression"
    )
    del meta["condados"][0]["original_idx"]
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    report, _sha = validate_export(out, france_cfg)
    codes = [e.code for e in report.errors]
    assert "MISSING_ORIGINAL_IDX" in codes, f"expected MISSING_ORIGINAL_IDX, got {codes}"
    # D-17: exactly one MISSING_ORIGINAL_IDX (the one we induced)
    assert codes.count("MISSING_ORIGINAL_IDX") == 1


def test_broken_paint_ocean_leak_triggers_ocean_leak_only(
    clean_france_output: Path, france_cfg, tmp_path: Path
) -> None:
    """Paint 5 pixels with a non-ocean RGB in the ocean region of lookup_condado.png."""
    out = _copy_clean(clean_france_output, tmp_path / "ocean_leak")
    # Find an ocean pixel via terrain_lookup.png (OCEAN_RGB=(0,0,0)) then paint
    # in lookup_condado.png.
    terrain = np.array(Image.open(out / "terrain_lookup.png").convert("RGB"))
    ocean_mask = (terrain == [0, 0, 0]).all(axis=-1)
    ys, xs = np.where(ocean_mask)
    if len(ys) < 5:
        pytest.skip("France toy dataset has fewer than 5 ocean pixels -- cannot induce OCEAN_LEAK")

    lk_path = out / "lookup_condado.png"
    lk = np.array(Image.open(lk_path).convert("RGB"))
    for i in range(5):
        lk[ys[i], xs[i]] = [200, 100, 50]  # non-ocean condado-like RGB
    Image.fromarray(lk, mode="RGB").save(lk_path)

    report, _sha = validate_export(out, france_cfg)
    codes = [e.code for e in report.errors]
    assert "OCEAN_LEAK" in codes
    # D-17 EXACT: only one OCEAN_LEAK error (and only for lookup_condado.png)
    leak_errors = [e for e in report.errors if e.code == "OCEAN_LEAK"]
    assert len(leak_errors) == 1
    assert leak_errors[0].file == "lookup_condado.png"
    assert leak_errors[0].context["leak_count"] == 5


def test_broken_duplicate_lookup_color_triggers_color_collision(
    clean_france_output: Path, france_cfg, tmp_path: Path
) -> None:
    """Force a cross-layer PLAINS_RGB collision in lookup_condado_colors.json."""
    out = _copy_clean(clean_france_output, tmp_path / "color_collision")
    colors_path = out / "lookup_condado_colors.json"
    colors = json.loads(colors_path.read_text(encoding="utf-8"))
    if "124,179,66" in colors:
        pytest.skip("France output already has PLAINS_RGB in lookup -- pick a different broken pattern")
    # Rewrite: remove first entry, add a PLAINS_RGB entry pointing to the same id.
    first_rgb = next(iter(colors))
    first_id = colors[first_rgb]
    del colors[first_rgb]
    colors["124,179,66"] = first_id  # PLAINS_RGB collision (cross-layer)
    colors_path.write_text(json.dumps(colors), encoding="utf-8")

    report, _sha = validate_export(out, france_cfg)
    codes = [e.code for e in report.errors]
    assert "COLOR_COLLISION" in codes
    coll_errors = [e for e in report.errors if e.code == "COLOR_COLLISION"]
    assert len(coll_errors) >= 1
    assert any(e.context.get("conflicts_with") == "PLAINS_RGB" for e in coll_errors)


def test_broken_shrink_territory_to_150px_triggers_territory_too_small(
    clean_france_output: Path, france_cfg, tmp_path: Path
) -> None:
    out = _copy_clean(clean_france_output, tmp_path / "too_small")
    meta_path = out / "territory_metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["condados"], "France has no condados -- fixture broken"
    meta["condados"][0]["pixel_count"] = 150
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    report, _sha = validate_export(out, france_cfg)
    codes = [e.code for e in report.errors]
    assert "TERRITORY_TOO_SMALL" in codes
    too_small = [e for e in report.errors if e.code == "TERRITORY_TOO_SMALL"]
    assert len(too_small) == 1
    assert too_small[0].context["pixel_count"] == 150


def test_broken_pixel_center_out_of_range_triggers_pixel_center_code(
    clean_france_output: Path, france_cfg, tmp_path: Path
) -> None:
    out = _copy_clean(clean_france_output, tmp_path / "pixel_center")
    meta_path = out / "territory_metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["condados"][0]["pixel_center"] = [-1, 0]
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    report, _sha = validate_export(out, france_cfg)
    codes = [e.code for e in report.errors]
    assert "PIXEL_CENTER_OUT_OF_RANGE" in codes
    pc = [e for e in report.errors if e.code == "PIXEL_CENTER_OUT_OF_RANGE"]
    assert len(pc) == 1
    assert pc[0].context["pixel_center"] == [-1, 0]


def test_broken_corrupt_json_triggers_schema_invalid_and_short_circuits(
    clean_france_output: Path, france_cfg, tmp_path: Path
) -> None:
    """D-18: SCHEMA_INVALID short-circuits semantic checks."""
    out = _copy_clean(clean_france_output, tmp_path / "corrupt_json")
    (out / "territory_metadata.json").write_text("{ this is not valid json", encoding="utf-8")

    report, _sha = validate_export(out, france_cfg)
    codes = [e.code for e in report.errors]
    assert "SCHEMA_INVALID" in codes
    # D-18 short-circuit: when SCHEMA_INVALID fires on a JSON, semantic checks
    # that depend on that JSON do NOT run.
    assert "MISSING_ORIGINAL_IDX" not in codes
    assert "TERRITORY_TOO_SMALL" not in codes
    assert "PIXEL_CENTER_OUT_OF_RANGE" not in codes


def test_aggregate_five_failures_records_all_five_codes(
    clean_france_output: Path, france_cfg, tmp_path: Path
) -> None:
    """D-18: validator collects ALL errors. D-17 aggregate: all 5 code categories present.

    Skips SCHEMA_INVALID (would short-circuit). Combines:
    - MISSING_ORIGINAL_IDX (drop original_idx)
    - OCEAN_LEAK (paint condado RGB into ocean)
    - COLOR_COLLISION (PLAINS_RGB cross-layer)
    - TERRITORY_TOO_SMALL (pixel_count=150)
    - PIXEL_CENTER_OUT_OF_RANGE (pixel_center=[-1, 0])
    """
    out = _copy_clean(clean_france_output, tmp_path / "aggregate")

    # 1. Drop original_idx + 2. Shrink pixel_count + 3. Out-of-range pixel_center
    meta_path = out / "territory_metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if "original_idx" in meta["condados"][0]:
        del meta["condados"][0]["original_idx"]
    meta["condados"][0]["pixel_count"] = 150
    meta["condados"][0]["pixel_center"] = [-1, 0]
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    # 4. COLOR_COLLISION (PLAINS_RGB cross-layer)
    colors_path = out / "lookup_condado_colors.json"
    colors = json.loads(colors_path.read_text(encoding="utf-8"))
    if "124,179,66" not in colors:
        first_rgb = next(iter(colors))
        first_id = colors[first_rgb]
        del colors[first_rgb]
        colors["124,179,66"] = first_id
    colors_path.write_text(json.dumps(colors), encoding="utf-8")

    # 5. OCEAN_LEAK
    terrain = np.array(Image.open(out / "terrain_lookup.png").convert("RGB"))
    ocean_mask = (terrain == [0, 0, 0]).all(axis=-1)
    ys, xs = np.where(ocean_mask)
    if len(ys) >= 1:
        lk_path = out / "lookup_condado.png"
        lk = np.array(Image.open(lk_path).convert("RGB"))
        lk[ys[0], xs[0]] = [200, 100, 50]
        Image.fromarray(lk, mode="RGB").save(lk_path)
    else:
        pytest.skip("France has no ocean pixels -- cannot induce OCEAN_LEAK")

    report, _sha = validate_export(out, france_cfg)
    codes = set(e.code for e in report.errors)
    expected_codes = {
        "MISSING_ORIGINAL_IDX",
        "TERRITORY_TOO_SMALL",
        "PIXEL_CENTER_OUT_OF_RANGE",
        "COLOR_COLLISION",
        "OCEAN_LEAK",
    }
    missing = expected_codes - codes
    assert not missing, f"validator missed codes: {missing} (got {codes})"
    assert report.passed is False
