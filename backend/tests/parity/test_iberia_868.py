"""Iberia 868 parity vs. Reconquista deployed maps (D-09 source of truth).

10 parametrised tests across 3 functions:
  - test_lookup_png_byte_equal (x2): lookup_barony.png, lookup_condado.png
  - test_visual_png_ssim (x4): visual_condado/visual_barony/mountains_mask/rivers_overlay
  - test_json_deep_equal (x4): lookup_*_colors, territory_metadata, mountain_river_data

Deferred per Pitfall P-2 (Phase 06 export-validation gate):
  - terrain_lookup.png, terrain_types.json (inicio doesn't generate them)

Comparison rules per CONTEXT.md D-12:
  - Lookup PNGs: byte-equal via numpy.array_equal
  - Visual PNGs + masks: SSIM >= 0.98 via skimage.metrics.structural_similarity
  - JSONs: deep-equal after recursive key-sort
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from skimage.metrics import structural_similarity as ssim

pytestmark = pytest.mark.parity


# --- Lookup PNGs: byte-equal (terrain_lookup.png deferred to Phase 06 per P-2) ---
@pytest.mark.parametrize("name", ["lookup_barony.png", "lookup_condado.png"])
def test_lookup_png_byte_equal(pipeline_output: Path, golden_dir: Path, name: str) -> None:
    actual = np.array(Image.open(pipeline_output / name))
    golden = np.array(Image.open(golden_dir / name))
    if not np.array_equal(actual, golden):
        diff_path = pipeline_output / f"DIFF_{name}"
        # Per-pixel mismatch mask: black = match, white = mismatch (any channel).
        if actual.shape == golden.shape:
            mismatch = np.any(actual != golden, axis=-1) if actual.ndim == 3 else (actual != golden)
            Image.fromarray((mismatch * 255).astype(np.uint8)).save(diff_path)
        pytest.fail(
            f"{name}: pixel-mismatch.\n"
            f"  golden: {golden_dir / name}\n"
            f"  actual: {pipeline_output / name}\n"
            f"  diff:   {diff_path}"
        )


# --- Visual PNGs + masks: SSIM >= 0.98 ---
@pytest.mark.parametrize(
    "name",
    ["visual_condado.png", "visual_barony.png", "mountains_mask.png", "rivers_overlay.png"],
)
def test_visual_png_ssim(pipeline_output: Path, golden_dir: Path, name: str) -> None:
    actual = np.array(Image.open(pipeline_output / name).convert("RGB"))
    golden = np.array(Image.open(golden_dir / name).convert("RGB"))
    score = ssim(actual, golden, channel_axis=2, data_range=255)
    assert score >= 0.98, (
        f"{name}: SSIM {score:.4f} < 0.98.\n"
        f"  golden: {golden_dir / name}\n"
        f"  actual: {pipeline_output / name}"
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
def test_json_deep_equal(pipeline_output: Path, golden_dir: Path, name: str) -> None:
    actual = _normalise(json.loads((pipeline_output / name).read_text(encoding="utf-8")))
    golden = _normalise(json.loads((golden_dir / name).read_text(encoding="utf-8")))
    assert actual == golden, (
        f"{name}: JSON mismatch.\n"
        f"  hint: diff <(jq -S . {golden_dir / name}) <(jq -S . {pipeline_output / name})"
    )
