"""Phase 08 BLOCKER-1 closure (plan 08-07c): unit tests for compute() replay path.

REQ-IDs: EDIT-POLYGON-01, EDIT-POLYGON-02, EDIT-POLYGON-03, DAG-01, DAG-02

Tests the following behaviours (per 08-07c Task 1 spec):
  1. Identity carry-forward: empty log_hash → byte-equal output (D-17)
  2. RuntimeError when log_hash set but snapshot_loader is None
  3. Single translate op mutates at least 1 pixel of a minimal raster
  4. Empty edit_log from loader → byte-equal output (identity)
  5. Determinism: same cfg + same input → identical output across 2 calls
  6. rasterio.features.rasterize is called with all_touched=False (Gemini LOW)

Fixture: 10×10 int16 raster
  - top-left  4×4 quadrant = barony_id 1
  - top-right 4×4 quadrant = barony_id 2
  - remainder = -1 (ocean sentinel per CLAUDE.md rule #5)
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from medieval_forge.services.pipeline.contracts import RegionConfig
from medieval_forge.services.pipeline.manual_edit import compute


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_raster() -> np.ndarray:
    """10×10 int16 raster with two baronies and ocean."""
    arr = np.full((10, 10), -1, dtype=np.int16)   # ocean
    arr[0:4, 0:4] = 1   # barony 1 — top-left 4×4 block
    arr[0:4, 6:10] = 2  # barony 2 — top-right 4×4 block
    return arr


def _cfg_identity() -> RegionConfig:
    """RegionConfig with empty hash → identity path."""
    return RegionConfig(
        manual_edit_log_hash="",
        manual_edit_log_count=0,
    )


def _cfg_with_loader(loader_func, *, log_hash: str = "abc0123456789abc") -> RegionConfig:
    """RegionConfig with hash set + loader injected for replay path."""
    cfg = RegionConfig(
        manual_edit_log_hash=log_hash,
        manual_edit_log_count=1,
    )
    cfg.snapshot_loader = loader_func
    return cfg


def _translate_one_op_log() -> dict:
    """Single translate op: move barony 1 down by 1 raster unit (dLat=1.0, dLon=0.0)."""
    return {
        "edit_log": [
            {
                "op": "translate",
                "polygonId": 1,
                "dLat": 1.0,
                "dLon": 0.0,
                "ts": 0,
            }
        ]
    }


# ---------------------------------------------------------------------------
# Test 1: identity carry-forward (empty log_hash)
# ---------------------------------------------------------------------------

def test_compute_empty_hash_returns_input_byte_equal():
    """D-17 carry-forward: empty log_hash → same array object returned."""
    arr = _make_raster()
    cfg = _cfg_identity()

    out = compute(arr, cfg)

    assert np.array_equal(out, arr), "identity path must return byte-equal array"
    assert out is arr, "identity path must return same object (no copy)"


# ---------------------------------------------------------------------------
# Test 2: RuntimeError when hash set but loader absent
# ---------------------------------------------------------------------------

def test_compute_raises_when_hash_set_but_loader_missing():
    """BLOCKER-1: non-empty hash without snapshot_loader → explicit RuntimeError."""
    arr = _make_raster()
    cfg = RegionConfig(
        manual_edit_log_hash="abc0123456789abc",
        manual_edit_log_count=1,
    )
    # snapshot_loader is None (default)

    with pytest.raises(RuntimeError, match="snapshot_loader required"):
        compute(arr, cfg)


# ---------------------------------------------------------------------------
# Test 3: single translate op mutates at least 1 pixel
# ---------------------------------------------------------------------------

def test_compute_single_translate_op_mutates_raster():
    """Translate barony 1 → at least 1 pixel must differ from input."""
    arr = _make_raster()
    loader = MagicMock(return_value=_translate_one_op_log())
    cfg = _cfg_with_loader(loader)

    out = compute(arr, cfg)

    assert out.shape == arr.shape, "output shape must match input"
    assert out.dtype == arr.dtype, "output dtype must remain int16"
    assert np.any(out != arr), (
        "A translate op must change at least 1 pixel. "
        "If no pixel changed, the replay path is identity (BLOCKER-1 regression)."
    )


# ---------------------------------------------------------------------------
# Test 4: empty edit_log from loader → identity
# ---------------------------------------------------------------------------

def test_compute_empty_edit_log_from_loader_returns_identity():
    """D-17: loader returns empty edit_log → output byte-equal to input."""
    arr = _make_raster()
    loader = MagicMock(return_value={"edit_log": []})
    cfg = _cfg_with_loader(loader)

    out = compute(arr, cfg)

    assert np.array_equal(out, arr), (
        "Empty edit_log from snapshot must produce identity output (D-17 carry-forward)"
    )


# ---------------------------------------------------------------------------
# Test 5: determinism — same cfg + same input → identical output
# ---------------------------------------------------------------------------

def test_compute_is_deterministic_same_result_across_two_calls():
    """D-18: identical cfg + input must produce identical output on two calls."""
    arr = _make_raster()
    loader = MagicMock(return_value=_translate_one_op_log())
    cfg = _cfg_with_loader(loader)

    out1 = compute(arr.copy(), cfg)
    out2 = compute(arr.copy(), cfg)

    assert np.array_equal(out1, out2), (
        "compute() must be deterministic: same cfg+input must produce same output"
    )


# ---------------------------------------------------------------------------
# Test 6: rasterize called with all_touched=False (Gemini LOW concern)
# ---------------------------------------------------------------------------

def test_compute_rasterize_invoked_with_all_touched_false():
    """Gemini review (LOW): rasterize must use all_touched=False to prevent
    sub-pixel border leakage that would break Unity byOriginalIdx shader.

    Verified via monkey-patch spy on rasterio.features.rasterize.
    """
    arr = _make_raster()
    loader = MagicMock(return_value=_translate_one_op_log())
    cfg = _cfg_with_loader(loader)

    rasterize_calls: list[dict[str, Any]] = []
    import rasterio.features as _rf

    original_rasterize = _rf.rasterize

    def _spy_rasterize(*args, **kwargs):
        rasterize_calls.append(kwargs)
        return original_rasterize(*args, **kwargs)

    with patch.object(_rf, "rasterize", side_effect=_spy_rasterize):
        compute(arr, cfg)

    assert rasterize_calls, "rasterio.features.rasterize should have been called"
    for call_kwargs in rasterize_calls:
        all_touched_val = call_kwargs.get("all_touched", False)
        assert all_touched_val is False, (
            f"rasterize must be called with all_touched=False (or omitted), "
            f"got all_touched={all_touched_val!r}. "
            "This prevents sub-pixel aliasing / orphan border pixels that would "
            "break Unity byOriginalIdx shader."
        )
