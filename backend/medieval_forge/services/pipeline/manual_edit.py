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

Plan 08-07: replay helpers replay_split / replay_merge / replay_translate.
These are PURE FUNCTIONS — no DB access, no HTTP. They are invoked from compute()
in plan 08-07c (DAG stage replay), NOT from the HTTP handler /editor/apply.
The HTTP handler only persists the op and bumps hash+count (BLOCKER-1 contract / D-17).
"""
from __future__ import annotations

import hashlib
from typing import Iterable

import numpy as np
from shapely.geometry import LineString, Polygon
from shapely.ops import split as shapely_split
from shapely.ops import unary_union

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


# ---------------------------------------------------------------------------
# Plan 08-07: Replay helpers — PURE FUNCTIONS (no DB, no HTTP).
# Invoked by compute() in plan 08-07c DAG replay. NOT called from /editor/apply.
# ---------------------------------------------------------------------------

def replay_split(parent: Polygon, cut: LineString) -> list[Polygon]:
    """D-02 / EDIT-POLYGON-01: split parent polygon along cut line.

    Returns exactly 2 non-empty Polygon pieces whose union equals parent area.
    Raises ValueError("SPLIT_INVALID: ...") if cut does not bisect the polygon
    into exactly 2 pieces (e.g. cut misses polygon, tangent-only cut).

    This is a PURE FUNCTION — no DB access, no side effects.
    Invoked from compute() in plan 08-07c, NOT from HTTP handler.
    """
    result = shapely_split(parent, cut)
    pieces = [g for g in result.geoms if isinstance(g, Polygon) and g.area > 0]
    if len(pieces) != 2:
        raise ValueError(
            f"SPLIT_INVALID: cut produced {len(pieces)} piece(s); expected 2. "
            "Ensure the line crosses the polygon interior at two distinct boundary points."
        )
    return pieces


def replay_merge(a: Polygon, b: Polygon) -> Polygon:
    """D-02 / EDIT-POLYGON-02: merge two adjacent baronies into one polygon.

    D-08: winner = first-selected (caller decides which is 'a').
    D-09: cross-condado merge allowed — adjacency is the ONLY constraint.
    Pitfall 2: raises ValueError("NOT_ADJACENT") if a.touches(b) is False.

    Returns a single Polygon (never MultiPolygon).
    Raises ValueError("NOT_ADJACENT") if polygons are not adjacent (touches == False).
    Raises ValueError("MERGE_INVALID: ...") if union produces non-Polygon geometry.

    This is a PURE FUNCTION — no DB access, no side effects.
    Invoked from compute() in plan 08-07c, NOT from HTTP handler.
    """
    if not a.touches(b):
        raise ValueError("NOT_ADJACENT")
    union = unary_union([a, b])
    if isinstance(union, Polygon):
        return union
    raise ValueError(
        f"MERGE_INVALID: union of adjacent polygons produced {type(union).__name__}; "
        "expected Polygon. This may indicate a topology issue (sliver gap or overlap)."
    )


def replay_translate(polygon: Polygon, d_lat: float, d_lon: float) -> Polygon:
    """D-02 / EDIT-POLYGON-03: translate a polygon by (d_lat, d_lon) delta.

    Applies uniform offset to all vertices. Shared-vertex coupling is handled
    by the HTTP handler / frontend before calling this; replay_translate operates
    on one polygon at a time.

    Returns a new Polygon with all vertices shifted by (d_lat, d_lon).

    This is a PURE FUNCTION — no DB access, no side effects.
    Invoked from compute() in plan 08-07c, NOT from HTTP handler.
    """
    from shapely.affinity import translate as shapely_translate
    # d_lon = xoff (longitude = x-axis), d_lat = yoff (latitude = y-axis)
    return shapely_translate(polygon, xoff=d_lon, yoff=d_lat)


__all__ = ["compute", "manual_edit_token", "replay_split", "replay_merge", "replay_translate"]
