"""Tests for Plan 04-01 D-01: 4 separately cacheable cleanup stages.

Verifies:
  - Each split function does NOT mutate its input array (.copy() guard)
  - smooth_per_territory returns a new array with correct dtype/shape
  - The 4 split functions in sequence produce byte-identical output to
    the Phase 01 monolith `cleanup_and_smooth` (D-17 parity)
"""
from __future__ import annotations

import numpy as np
import pytest

from medieval_forge.services.pipeline.cleanup import (
    apply_median,
    remove_fragments,
    smooth_per_territory,
    merge_small_blobs,
)
from medieval_forge.services.pipeline.contracts import RegionConfig
from tests.unit._cleanup_monolith_snapshot import cleanup_and_smooth as monolith

pytestmark = pytest.mark.unit

RNG = np.random.default_rng(42)


def _make_synthetic(h: int = 100, w: int = 100, nb: int = 5):
    """Return (raw, land, nb) for a small deterministic test map."""
    land = np.ones((h, w), dtype=bool)
    # 10-px border is ocean
    land[:5, :] = False
    land[-5:, :] = False
    land[:, :5] = False
    land[:, -5:] = False
    raw = RNG.integers(0, nb, (h, w), dtype=np.int16)
    raw[~land] = -1
    return raw, land, nb


def _default_cfg() -> RegionConfig:
    """Minimal RegionConfig with defaults; stop_event=None (Phase 01 path)."""
    return RegionConfig()


def test_apply_median_does_not_mutate_input() -> None:
    raw, land, nb = _make_synthetic()
    cfg = _default_cfg()
    raw_before = raw.copy()
    apply_median(raw, land, nb, cfg)
    assert np.array_equal(raw, raw_before), "apply_median must NOT mutate its input"


def test_apply_median_default_cfg_matches_monolith() -> None:
    """apply_median + identity for other stages vs monolith median-only phase."""
    raw, land, nb = _make_synthetic(200, 200, 5)
    cfg = _default_cfg()

    # Split result after only the median stage
    med_split = apply_median(raw.copy(), land, nb, cfg)

    # Monolith result after ONLY the median passes (no fragment/smooth/merge).
    # We run the monolith on a fresh copy that has land already zeroed,
    # and compare by running just the median loop inline (same logic).
    raw_mono = raw.copy()
    for i in range(cfg.median_passes):
        from scipy.ndimage import median_filter
        ri = raw_mono.astype(np.int32)
        ri[~land] = 9999
        sz = 11 if i < 2 else 9 if i < 4 else 7 if i < 6 else 5
        cl = median_filter(ri, size=sz).astype(np.int16)
        cl[~land] = -1
        v = (raw_mono >= 0) & (cl >= 0) & (cl < nb)
        raw_mono[v] = cl[v]
        raw_mono[~land] = -1

    assert np.array_equal(med_split, raw_mono), (
        "apply_median output must be byte-identical to the monolith median passes"
    )


def test_remove_fragments_does_not_mutate_input() -> None:
    raw, land, nb = _make_synthetic()
    cfg = _default_cfg()
    med = apply_median(raw, land, nb, cfg)
    med_before = med.copy()
    remove_fragments(med, land, nb, cfg)
    assert np.array_equal(med, med_before), "remove_fragments must NOT mutate its input"


def test_smooth_per_territory_returns_new_array() -> None:
    raw, land, nb = _make_synthetic()
    cfg = _default_cfg()
    med = apply_median(raw, land, nb, cfg)
    frag = remove_fragments(med, land, nb, cfg)
    result = smooth_per_territory(frag, land, cfg)
    assert result is not frag, "smooth_per_territory must return a NEW array"
    assert result.dtype == np.int16, f"expected int16, got {result.dtype}"
    assert result.shape == frag.shape, "shape must be preserved"


def test_merge_small_blobs_does_not_mutate_input() -> None:
    raw, land, nb = _make_synthetic()
    cfg = _default_cfg()
    med = apply_median(raw, land, nb, cfg)
    frag = remove_fragments(med, land, nb, cfg)
    sm = smooth_per_territory(frag, land, cfg)
    sm_before = sm.copy()
    merge_small_blobs(sm, land, nb, cfg)
    assert np.array_equal(sm, sm_before), "merge_small_blobs must NOT mutate its input"


def test_split_chain_default_cfg_matches_cleanup_and_smooth() -> None:
    """D-17: 4 split functions in sequence produce byte-identical output to monolith."""
    raw, land, nb = _make_synthetic(200, 200, 5)
    cfg = _default_cfg()

    # Run monolith (mutates raw_mono in place, which is expected)
    raw_mono = raw.copy()
    monolith_out = monolith(raw_mono, land, nb, cfg)

    # Run split chain on the ORIGINAL raw (must not mutate it)
    raw_split = raw.copy()
    med = apply_median(raw_split, land, nb, cfg)
    frag = remove_fragments(med, land, nb, cfg)
    sm = smooth_per_territory(frag, land, cfg)
    result = merge_small_blobs(sm, land, nb, cfg)

    assert np.array_equal(result, monolith_out), (
        "split chain output must be byte-identical to cleanup_and_smooth monolith (D-17)"
    )
