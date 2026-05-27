"""Phase 08 D-17 + D-18: manual_edit stage — identity pass-through when log empty.

Slotted between 'merge' and 'hierarchy' in DAG_ORDER. When manual_edit_log_hash == ""
(no user edits), compute() returns the input array unchanged (byte-equal) so parity
tests stay green (Phase 01 D-09 + Phase 04 D-17 carry-forward).

When non-empty, the actual edit replay happens HERE in a follow-up plan (08-06a/b/07).
This plan establishes the contract + identity path; replay logic comes later.

D-18 token formula (BLOCKER-2 fix):
  sha256("manual_edit" + f"count={edit_op_count}" + f"loghash={log_hash}" + sorted(upstream))[:16]

The count term is a SEPARATE explicit term in the formula, not derived from the hash,
so two different edit sequences that happen to produce the same hash but have different
lengths still yield distinct tokens.
"""
from __future__ import annotations

import hashlib
from typing import Iterable

import numpy as np

from .contracts import RegionConfig


def compute(input_array: np.ndarray, cfg: RegionConfig) -> np.ndarray:
    """D-17 identity contract: empty log_hash → input unchanged (byte-equal).

    Non-empty log replay is implemented in a follow-up plan (08-06+/07); this plan
    ships the identity path so the DAG can be wired and parity stays green.

    Args:
        input_array: The barony raster array from the 'merge' stage.
        cfg: RegionConfig with manual_edit_log_hash and manual_edit_log_count fields.

    Returns:
        The same array (identity) when log_hash is empty, otherwise the array with
        edits replayed (identity in Wave 1; full replay in later plans).
    """
    if not cfg.manual_edit_log_hash:
        # Empty hash → identity pass-through. No copy; same object is returned
        # so downstream numpy views are unaffected and parity tests stay byte-equal.
        return input_array
    # Non-empty log: replay path lands in plans 08-06+/07 (vertex/polygon op replay).
    # Wave 1 accepts identity behaviour — the DAG contract is established here.
    return input_array


def manual_edit_token(cfg: RegionConfig, upstream_tokens: Iterable[str]) -> str:
    """D-18 token formula including count as a separate term (BLOCKER-2 fix).

    Formula: sha256("manual_edit" | f"count={N}" | f"loghash={hash}" | sorted(upstream))[:16]

    Empty log_hash + count=0 produces a stable identity token that still depends on
    upstream tokens, so any upstream change (e.g. smooth-σ slider) cascades correctly
    through manual_edit to hierarchy and beyond.

    The count term is explicit and separate from loghash so that two edit sequences
    with the same hash but different op counts produce different tokens (D-18 contract).

    Args:
        cfg: RegionConfig carrying manual_edit_log_hash and manual_edit_log_count.
        upstream_tokens: Tokens from parent stages (typically just 'merge' token).

    Returns:
        16-char hex digest (matching the Phase 04 pattern from compute_version_token).
    """
    parts: list[str] = [
        "manual_edit",
        f"count={cfg.manual_edit_log_count}",
        f"loghash={cfg.manual_edit_log_hash}",
    ]
    for tok in sorted(upstream_tokens):
        parts.append(tok)
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


__all__ = ["compute", "manual_edit_token"]
