"""Unit tests for _check_ocean_leak (D-09 + D-08 OCEAN_LEAK).

D-17 enforcement: each test asserts EXACTLY the expected error codes.
Explicit numeric fixtures — tiny PIL images written to tmp_path per test.

Land/ocean predicate (terrain.py:35-36):
  ocean pixel in terrain_lookup.png == OCEAN_RGB (0, 0, 0)
  land  pixel in terrain_lookup.png == PLAINS_RGB (124, 179, 66)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from medieval_forge.services.export.validator import (
    _ValidationContext,
    _check_ocean_leak,
)
from medieval_forge.services.pipeline.region_loader import (
    clear_region_cache,
    load_region,
)

pytestmark = pytest.mark.unit

_OCEAN_RGB = (0, 0, 0)
_PLAINS_RGB = (124, 179, 66)


@pytest.fixture
def iberia_cfg():
    clear_region_cache()
    return load_region("iberia_868")


def _write_png(path: Path, arr: np.ndarray) -> None:
    Image.fromarray(arr.astype(np.uint8), mode="RGB").save(path)


def test_all_land_terrain_with_valid_condado_lookup_no_errors(
    iberia_cfg, tmp_path: Path
) -> None:
    """Entire image is land → no ocean to leak into."""
    h, w = 10, 10
    terrain = np.full((h, w, 3), _PLAINS_RGB, dtype=np.uint8)
    lk = np.full((h, w, 3), (50, 80, 30), dtype=np.uint8)  # valid condado RGB
    _write_png(tmp_path / "terrain_lookup.png", terrain)
    _write_png(tmp_path / "lookup_barony.png", lk)
    _write_png(tmp_path / "lookup_condado.png", lk)

    ctx = _ValidationContext()
    _check_ocean_leak(ctx, tmp_path, iberia_cfg)
    assert ctx.errors == []


def test_half_ocean_with_correct_ocean_far_no_errors(iberia_cfg, tmp_path: Path) -> None:
    """Left half ocean (OCEAN_RGB), right half land (PLAINS_RGB);
    lookup ocean filled with cfg.ocean_far (correct), land filled with condado RGB."""
    h, w = 10, 10
    terrain = np.full((h, w, 3), _OCEAN_RGB, dtype=np.uint8)
    terrain[:, w // 2 :] = _PLAINS_RGB
    lk = np.full((h, w, 3), tuple(iberia_cfg.ocean_far), dtype=np.uint8)
    lk[:, w // 2 :] = (50, 80, 30)
    _write_png(tmp_path / "terrain_lookup.png", terrain)
    _write_png(tmp_path / "lookup_barony.png", lk)
    _write_png(tmp_path / "lookup_condado.png", lk)

    ctx = _ValidationContext()
    _check_ocean_leak(ctx, tmp_path, iberia_cfg)
    assert ctx.errors == []


def test_one_leak_pixel_records_exact_count_and_sample(iberia_cfg, tmp_path: Path) -> None:
    h, w = 10, 10
    terrain = np.full((h, w, 3), _OCEAN_RGB, dtype=np.uint8)  # all ocean
    lk_barony = np.full((h, w, 3), tuple(iberia_cfg.ocean_far), dtype=np.uint8)
    lk_condado = lk_barony.copy()
    lk_condado[3, 5] = (50, 80, 30)  # 1 leak pixel at (col=5, row=3)
    _write_png(tmp_path / "terrain_lookup.png", terrain)
    _write_png(tmp_path / "lookup_barony.png", lk_barony)
    _write_png(tmp_path / "lookup_condado.png", lk_condado)

    ctx = _ValidationContext()
    _check_ocean_leak(ctx, tmp_path, iberia_cfg)
    assert len(ctx.errors) == 1
    assert ctx.errors[0].code == "OCEAN_LEAK"
    assert ctx.errors[0].file == "lookup_condado.png"
    assert ctx.errors[0].context["leak_count"] == 1
    assert len(ctx.errors[0].context["sample_pixels"]) == 1
    assert ctx.errors[0].context["sample_pixels"][0] == {
        "x": 5,
        "y": 3,
        "rgb": [50, 80, 30],
    }


def test_leaks_in_both_files_record_two_separate_errors(iberia_cfg, tmp_path: Path) -> None:
    h, w = 10, 10
    terrain = np.full((h, w, 3), _OCEAN_RGB, dtype=np.uint8)
    lk_barony = np.full((h, w, 3), tuple(iberia_cfg.ocean_far), dtype=np.uint8)
    lk_barony[1, 1] = (200, 100, 50)
    lk_condado = np.full((h, w, 3), tuple(iberia_cfg.ocean_far), dtype=np.uint8)
    lk_condado[2, 2] = (50, 80, 30)
    _write_png(tmp_path / "terrain_lookup.png", terrain)
    _write_png(tmp_path / "lookup_barony.png", lk_barony)
    _write_png(tmp_path / "lookup_condado.png", lk_condado)

    ctx = _ValidationContext()
    _check_ocean_leak(ctx, tmp_path, iberia_cfg)
    assert len(ctx.errors) == 2
    files = {e.file for e in ctx.errors}
    assert files == {"lookup_barony.png", "lookup_condado.png"}
    assert all(e.code == "OCEAN_LEAK" for e in ctx.errors)


def test_fifteen_leak_pixels_records_count_15_but_samples_truncated_to_10(
    iberia_cfg, tmp_path: Path
) -> None:
    h, w = 10, 10
    terrain = np.full((h, w, 3), _OCEAN_RGB, dtype=np.uint8)
    lk = np.full((h, w, 3), tuple(iberia_cfg.ocean_far), dtype=np.uint8)
    # paint 15 distinct pixels with a leaking RGB
    for i in range(15):
        lk[i // w, i % w] = (50, 80, 30)
    _write_png(tmp_path / "terrain_lookup.png", terrain)
    _write_png(tmp_path / "lookup_barony.png", lk)
    _write_png(
        tmp_path / "lookup_condado.png",
        np.full((h, w, 3), tuple(iberia_cfg.ocean_far), dtype=np.uint8),
    )

    ctx = _ValidationContext()
    _check_ocean_leak(ctx, tmp_path, iberia_cfg)
    assert len(ctx.errors) == 1
    assert ctx.errors[0].context["leak_count"] == 15
    assert len(ctx.errors[0].context["sample_pixels"]) == 10  # truncation cap
