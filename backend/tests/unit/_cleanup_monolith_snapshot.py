"""Verbatim snapshot of the Phase 01 cleanup_and_smooth monolith.

Preserved here so test_cleanup_split.py can assert the 4 split functions
produce byte-identical output to the original. This file must NOT be changed
after Plan 04-01 — it is the gold standard for the parity assertion.

Copied verbatim from backend/medieval_forge/services/pipeline/cleanup.py
before the Phase 04-01 refactor replaced it with 4 separate functions.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import (
    gaussian_filter,
    median_filter,
    label as nd_label,
    binary_dilation,
)

from medieval_forge.services.pipeline.contracts import RegionConfig


def cleanup_and_smooth(raw: np.ndarray, land: np.ndarray,
                       nb: int, cfg: RegionConfig) -> np.ndarray:
    """Monolith from Phase 01 — verbatim copy for parity reference.

    Mutates `raw` in-place during median + fragment passes.
    """
    # Median filter passes (progressively smaller kernel)
    for i in range(cfg.median_passes):
        ri = raw.astype(np.int32)
        ri[~land] = 9999
        sz = 11 if i < 2 else 9 if i < 4 else 7 if i < 6 else 5
        cl = median_filter(ri, size=sz).astype(np.int16)
        cl[~land] = -1
        v = (raw >= 0) & (cl >= 0) & (cl < nb)
        raw[v] = cl[v]
        raw[~land] = -1

    # Remove disconnected fragments per barony
    for bi in range(nb):
        mask = raw == bi
        if not np.any(mask):
            continue
        labeled, n = nd_label(mask)
        if n <= 1:
            continue
        sizes = np.bincount(labeled.ravel())
        ml = np.argmax(sizes[1:]) + 1
        for lbl in range(1, n + 1):
            if lbl != ml and sizes[lbl] < cfg.fragment_min_px:
                frag = labeled == lbl
                dil = binary_dilation(frag, iterations=5)
                bord = dil & ~frag & (raw >= 0) & (raw != bi)
                if np.any(bord):
                    nb_arr = raw[bord]
                    raw[frag] = np.bincount(nb_arr[nb_arr >= 0].astype(int)).argmax()

    # Gaussian smoothing
    h, w = raw.shape
    best = np.zeros((h, w), dtype=np.float32)
    result = np.full((h, w), -1, dtype=np.int16)
    for cid in np.unique(raw[raw >= 0]):
        mask = (raw == cid).astype(np.float32)
        mask[~land] = 0
        npx = mask.sum()
        s = cfg.smooth_sigma if npx > 400 else max(1.2, cfg.smooth_sigma * (npx / 400))
        blurred = gaussian_filter(mask, sigma=s)
        blurred[~land] = 0
        bt = blurred > best
        result[bt] = cid
        best[bt] = blurred[bt]
    result[~land] = -1

    # Merge tiny baronies
    for bi in range(nb):
        npx = np.sum(result == bi)
        if npx == 0 or npx >= cfg.blob_merge_px:
            continue
        mask = result == bi
        dil = binary_dilation(mask, iterations=5)
        bord = dil & ~mask & (result >= 0) & (result != bi)
        if np.any(bord):
            nb_arr = result[bord]
            result[mask] = np.bincount(nb_arr[nb_arr >= 0].astype(int)).argmax()

    return result
