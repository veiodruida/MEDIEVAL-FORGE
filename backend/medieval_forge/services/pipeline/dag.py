"""Phase 04 D-02: version_token derivation + STAGE_READS map + DAG_ORDER tuple.

A stage's token = sha256(stage_name + sorted (field, cfg[field]) pairs for its declared
reads + sorted upstream tokens) truncated to 16 hex chars. Sorting + json.dumps with
sort_keys=True guarantees determinism across Python runs (Pitfall 2: dict iteration
order). RegionConfig is @dataclass — use getattr(cfg, name), not .model_dump().

Phase 08: STAGE_TOKEN_OVERRIDES map added for stages whose token cannot derive from
cfg fields alone (manual_edit uses edit-op log stored out-of-band in snapshots table).
Walker checks this map FIRST; falls back to compute_version_token if absent.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Iterable

from .contracts import RegionConfig


def _serialize_cfg_field(value: Any) -> str:
    """Stable string serialization of a single cfg field value.

    Lists, dicts, tuples, sets, frozensets -> json.dumps(sort_keys=True, default=str)
    so dict ordering doesn't drift across CPython versions. Scalars -> str(value).
    """
    if isinstance(value, (list, dict, tuple, set, frozenset)):
        # frozenset/set need conversion to a sortable list first
        if isinstance(value, (set, frozenset)):
            value = sorted(value, key=str)
        return json.dumps(value, sort_keys=True, default=str)
    return str(value)


def compute_version_token(stage_name: str, reads: frozenset[str],
                          cfg: RegionConfig, upstream_tokens: Iterable[str]) -> str:
    """Return the 16-char hex token for a stage given its inputs.

    Determinism: sorted(reads) + sorted(upstream_tokens) means call ordering of
    the producer doesn't matter. Token isolation: a slider on smooth_sigma does
    NOT change apply_median's token because 'smooth_sigma' is not in reads for median.
    """
    parts: list[str] = [stage_name]
    for field_name in sorted(reads):
        value = getattr(cfg, field_name, None)
        parts.append(f"{field_name}={_serialize_cfg_field(value)}")
    for tok in sorted(upstream_tokens):
        parts.append(tok)
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


# D-02 reads declarations — single source of truth for which cfg fields each
# stage consumes. Phase 04 sliders touch only median, fragment, smooth, merge.
STAGE_READS: dict[str, frozenset[str]] = {
    # Phase 08 Plan 08 (DAG-04 / WARNING-4 fix): landmask_override added so
    # version_token changes when user replaces the landmask polygon via editor.
    "landmask":    frozenset({"map_w", "map_h", "lon_min", "lon_max",
                              "lat_min", "lat_max", "upscale",
                              "landmask_override"}),
    "border":      frozenset({"border_polygon", "pt_duchies"}),
    "voronoi":     frozenset({"condados", "rng_seed"}),
    "median":      frozenset({"median_passes"}),
    "fragment":    frozenset({"fragment_min_px"}),
    "smooth":      frozenset({"smooth_sigma"}),
    "merge":       frozenset({"blob_merge_px"}),
    # Phase 08 D-17/D-18: manual_edit reads NOTHING from cfg directly — its
    # inputs are out-of-band (snapshot blob in DB). Token derived via override.
    "manual_edit": frozenset(),
    "hierarchy":   frozenset(),  # reads upstream array only
    "render":      frozenset({"kingdom_colors", "ocean_near", "ocean_far",
                              "draw_names", "coast_inner_width",
                              "coast_inner_color", "ocean_gradient_dist"}),
    "lookup":      frozenset(),
    "metadata":    frozenset({"condados", "duchies", "kingdoms"}),
    "export":      frozenset({"output_dir"}),
}

# D-01: 13-stage canonical DAG order (Phase 08 inserts manual_edit).
# Phase 03's 11-entry list expanded by Phase 04 ('cleanup' → 'median'+'fragment').
# Phase 08 inserts 'manual_edit' between 'merge' and 'hierarchy' per D-17.
DAG_ORDER: tuple[str, ...] = (
    "landmask", "border", "voronoi", "median", "fragment",
    "smooth", "merge", "manual_edit", "hierarchy",
    "render", "lookup", "metadata", "export",
)


# Upstream-edge map: which stage(s) feed each stage's `upstream_tokens` list.
# A stage's input array is the previous stage's output array, but lookup +
# metadata + export depend on render's output array. Hierarchy depends on
# manual_edit (Phase 08 D-17: manual_edit slotted between merge and hierarchy).
DAG_PARENTS: dict[str, tuple[str, ...]] = {
    "landmask":    (),
    "border":      ("landmask",),
    "voronoi":     ("border",),
    "median":      ("voronoi",),
    "fragment":    ("median",),
    "smooth":      ("fragment",),
    "merge":       ("smooth",),
    "manual_edit": ("merge",),          # Phase 08 D-17: new stage
    "hierarchy":   ("manual_edit",),    # Phase 08: was ("merge",)
    "render":      ("hierarchy",),
    "lookup":      ("render",),
    "metadata":    ("hierarchy",),
    "export":      ("render", "lookup", "metadata"),
}


# Phase 08: override map for stages whose token cannot derive from cfg fields alone.
# Walker checks this map FIRST; falls back to compute_version_token if absent.
# Pattern reserved for any future out-of-band input stage (e.g. research-overlay sidecar).
from . import manual_edit as _manual_edit_module  # noqa: E402

STAGE_TOKEN_OVERRIDES: dict[str, Callable[[RegionConfig, Iterable[str]], str]] = {
    "manual_edit": _manual_edit_module.manual_edit_token,
}


__all__ = [
    "compute_version_token",
    "STAGE_READS",
    "DAG_ORDER",
    "DAG_PARENTS",
    "STAGE_TOKEN_OVERRIDES",
]
