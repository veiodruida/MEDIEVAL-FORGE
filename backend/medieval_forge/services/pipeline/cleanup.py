"""Phase 04 D-01: 4 separately cacheable cleanup stages.

Replaces the monolith `cleanup_and_smooth` from Phase 01. The 4 functions, called
in order with the previous output as input, produce byte-equal output to the
monolith at default cfg (D-17 parity guarantee).

Each function:
  - Takes its predecessor's array as `input_array` and never mutates it (.copy() at top)
  - Checks cfg.stop_event between heavy work blocks for cooperative cancel (D-14)
  - Returns a fresh np.ndarray for the next stage

Stage reads declarations (D-02) live in dag.py.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import (
    gaussian_filter,
    median_filter,
    label as nd_label,
    binary_dilation,
)

from .contracts import RegionConfig


class StageCancelled(Exception):
    """Raised by a split cleanup function when cfg.stop_event is set.

    Plan 04-02's render producer catches this and emits stage_cancel SSE events.
    """
    def __init__(self, stage_name: str):
        super().__init__(f"stage cancelled: {stage_name}")
        self.stage_name = stage_name


def _check_cancel(cfg: RegionConfig, stage_name: str) -> None:
    if cfg.stop_event is not None and cfg.stop_event.is_set():
        raise StageCancelled(stage_name)


def apply_median(raw: np.ndarray, land: np.ndarray,
                 nb: int, cfg: RegionConfig) -> np.ndarray:
    """Stage 1: 8 median filter passes (kernels 11/11/9/9/7/7/5/5).

    Verbatim semantics from Phase 01 cleanup.py:40-48.
    Returns a copy — does NOT mutate `raw`.
    """
    _check_cancel(cfg, "median")
    med = raw.copy()  # CRITICAL: copy to preserve cached prior_array (Pitfall 1)
    for i in range(cfg.median_passes):
        _check_cancel(cfg, "median")  # cancel between passes (D-14 < 2 s)
        ri = med.astype(np.int32)
        ri[~land] = 9999
        sz = 11 if i < 2 else 9 if i < 4 else 7 if i < 6 else 5
        cl = median_filter(ri, size=sz).astype(np.int16)
        cl[~land] = -1
        v = (med >= 0) & (cl >= 0) & (cl < nb)
        med[v] = cl[v]
        med[~land] = -1
    return med


def remove_fragments(med: np.ndarray, land: np.ndarray,
                     nb: int, cfg: RegionConfig) -> np.ndarray:
    """Stage 2: drop barony fragments < cfg.fragment_min_px.

    Verbatim semantics from Phase 01 cleanup.py:51-67.
    Returns a copy — does NOT mutate `med`.
    """
    _check_cancel(cfg, "fragment")
    frag = med.copy()  # CRITICAL: copy
    for bi in range(nb):
        mask = frag == bi
        if not np.any(mask):
            continue
        labeled, n = nd_label(mask)
        if n <= 1:
            continue
        sizes = np.bincount(labeled.ravel())
        ml = np.argmax(sizes[1:]) + 1
        for lbl in range(1, n + 1):
            if lbl != ml and sizes[lbl] < cfg.fragment_min_px:
                fr = labeled == lbl
                dil = binary_dilation(fr, iterations=5)
                bord = dil & ~fr & (frag >= 0) & (frag != bi)
                if np.any(bord):
                    nb_arr = frag[bord]
                    frag[fr] = np.bincount(nb_arr[nb_arr >= 0].astype(int)).argmax()
    return frag


def smooth_per_territory(frag: np.ndarray, land: np.ndarray,
                         cfg: RegionConfig) -> np.ndarray:
    """Stage 3: per-territory Gaussian smoothing, winner-takes-all.

    Verbatim semantics from Phase 01 cleanup.py:70-83. P-5 sigma-attenuation
    for tiny territories (npx <= 400) preserved verbatim.
    Allocates fresh result; does NOT need .copy() of `frag`.
    """
    _check_cancel(cfg, "smooth")
    h, w = frag.shape
    best = np.zeros((h, w), dtype=np.float32)
    result = np.full((h, w), -1, dtype=np.int16)
    for cid in np.unique(frag[frag >= 0]):
        mask = (frag == cid).astype(np.float32)
        mask[~land] = 0
        npx = mask.sum()
        s = cfg.smooth_sigma if npx > 400 else max(1.2, cfg.smooth_sigma * (npx / 400))
        blurred = gaussian_filter(mask, sigma=s)
        blurred[~land] = 0
        bt = blurred > best
        result[bt] = cid
        best[bt] = blurred[bt]
    result[~land] = -1
    return result


def merge_small_blobs(sm: np.ndarray, land: np.ndarray,
                      nb: int, cfg: RegionConfig) -> np.ndarray:
    """Stage 4: merge final baronies < cfg.blob_merge_px into the largest neighbor.

    Verbatim semantics from Phase 01 cleanup.py:86-95.
    Returns a copy — does NOT mutate `sm`.
    """
    _check_cancel(cfg, "merge")
    merged = sm.copy()  # CRITICAL: copy to preserve sm as cached 'smooth' stage output
    for bi in range(nb):
        npx = np.sum(merged == bi)
        if npx == 0 or npx >= cfg.blob_merge_px:
            continue
        mask = merged == bi
        dil = binary_dilation(mask, iterations=5)
        bord = dil & ~mask & (merged >= 0) & (merged != bi)
        if np.any(bord):
            nb_arr = merged[bord]
            merged[mask] = np.bincount(nb_arr[nb_arr >= 0].astype(int)).argmax()
    return merged


__all__ = [
    "apply_median",
    "remove_fragments",
    "smooth_per_territory",
    "merge_small_blobs",
    "StageCancelled",
]
