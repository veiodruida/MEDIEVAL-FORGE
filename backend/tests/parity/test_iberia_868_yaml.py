"""Iberia 868 YAML parity gate — Plan 05-03 (D-14).

Proves that loading via load_region('iberia_868') produces byte-equal lookup
PNGs, SSIM >= 0.98 visual PNGs, and deep-equal JSONs compared to the same
Phase 01 golden fixtures used by test_iberia_868.py.

This gate MUST stay green until Plan 05-05 deletes iberia_config() from
regions.py (D-17 step 3 invariant: both parity tests pass simultaneously).

10 parametrised tests across 3 functions (mirrors test_iberia_868.py exactly):
  - test_lookup_png_byte_equal_yaml (x2): lookup_barony.png, lookup_condado.png
  - test_visual_png_ssim_yaml (x4): visual_condado/visual_barony/mountains_mask/rivers_overlay
  - test_json_deep_equal_yaml (x4): lookup_*_colors, territory_metadata, mountain_river_data

Plus canvas sidecar existence test (mirrors test_canvas_sidecars_exist).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from skimage.metrics import structural_similarity as ssim

from medieval_forge.services.pipeline import run_pipeline
from medieval_forge.services.pipeline.region_loader import load_region, clear_region_cache

pytestmark = pytest.mark.parity


@pytest.fixture(scope="session")
def pipeline_output_yaml(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run the v3 pipeline once per session using load_region, return output dir.

    Session-scoped to match the cost profile of test_iberia_868.py — the full
    Iberia pipeline runs once and all 10 parity tests share the output.
    """
    out = tmp_path_factory.mktemp("iberia_868_yaml_actual")
    clear_region_cache()
    cfg = load_region("iberia_868")
    cfg.output_dir = str(out)
    run_pipeline(cfg)
    return out


# --- Lookup PNGs: byte-equal (terrain_lookup.png deferred to Phase 06 per P-2) ---
@pytest.mark.parametrize("name", ["lookup_barony.png", "lookup_condado.png"])
def test_lookup_png_byte_equal_yaml(
    pipeline_output_yaml: Path, golden_dir: Path, name: str
) -> None:
    actual = np.array(Image.open(pipeline_output_yaml / name))
    golden = np.array(Image.open(golden_dir / name))
    if not np.array_equal(actual, golden):
        diff_path = pipeline_output_yaml / f"DIFF_{name}"
        if actual.shape == golden.shape:
            mismatch = np.any(actual != golden, axis=-1) if actual.ndim == 3 else (actual != golden)
            Image.fromarray((mismatch * 255).astype(np.uint8)).save(diff_path)
        pytest.fail(
            f"{name}: pixel-mismatch (YAML-loaded cfg vs golden).\n"
            f"  golden: {golden_dir / name}\n"
            f"  actual: {pipeline_output_yaml / name}\n"
            f"  diff:   {diff_path}"
        )


# --- Visual PNGs + masks: SSIM >= 0.98 ---
@pytest.mark.parametrize(
    "name",
    ["visual_condado.png", "visual_barony.png", "mountains_mask.png", "rivers_overlay.png"],
)
def test_visual_png_ssim_yaml(
    pipeline_output_yaml: Path, golden_dir: Path, name: str
) -> None:
    actual = np.array(Image.open(pipeline_output_yaml / name).convert("RGB"))
    golden = np.array(Image.open(golden_dir / name).convert("RGB"))
    score = ssim(actual, golden, channel_axis=2, data_range=255)
    assert score >= 0.98, (
        f"{name}: SSIM {score:.4f} < 0.98 (YAML-loaded cfg vs golden).\n"
        f"  golden: {golden_dir / name}\n"
        f"  actual: {pipeline_output_yaml / name}"
    )


# --- JSONs: deep-equal after recursive key-sort (terrain_types.json deferred per P-2) ---
def _normalise(obj):
    if isinstance(obj, dict):
        return {k: _normalise(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return [_normalise(x) for x in obj]
    return obj


@pytest.mark.parametrize(
    "name",
    [
        "lookup_barony_colors.json",
        "lookup_condado_colors.json",
        "territory_metadata.json",
        "mountain_river_data.json",
    ],
)
def test_json_deep_equal_yaml(
    pipeline_output_yaml: Path, golden_dir: Path, name: str
) -> None:
    actual = _normalise(json.loads((pipeline_output_yaml / name).read_text(encoding="utf-8")))
    golden = _normalise(json.loads((golden_dir / name).read_text(encoding="utf-8")))
    assert actual == golden, (
        f"{name}: JSON mismatch (YAML-loaded cfg vs golden).\n"
        f"  hint: diff <(jq -S . {golden_dir / name}) <(jq -S . {pipeline_output_yaml / name})"
    )


# --- Canvas sidecars exist + non-empty (mirrors test_canvas_sidecars_exist) ---
def test_canvas_sidecars_exist_yaml(pipeline_output_yaml: Path) -> None:
    sidecars = (
        "territories.geojson",
        "baronies.geojson",
        "condado_colors.json",
        "barony_colors.json",
    )
    for name in sidecars:
        p = pipeline_output_yaml / name
        assert p.is_file(), f"missing canvas sidecar: {name}"
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data, f"empty canvas sidecar: {name}"

    tj = json.loads((pipeline_output_yaml / "territories.geojson").read_text(encoding="utf-8"))
    assert tj["type"] == "FeatureCollection"
    assert len(tj["features"]) > 0, "territories.geojson has zero features"

    bj = json.loads((pipeline_output_yaml / "baronies.geojson").read_text(encoding="utf-8"))
    assert bj["type"] == "FeatureCollection"
    assert len(bj["features"]) > 0, "baronies.geojson has zero features"

    colors = json.loads((pipeline_output_yaml / "condado_colors.json").read_text(encoding="utf-8"))
    territory_ids = {f["id"] for f in tj["features"]}
    missing_colors = territory_ids - set(colors.keys())
    assert not missing_colors, (
        f"condado_colors.json missing {len(missing_colors)} entries: "
        f"{sorted(missing_colors)[:5]}"
    )
