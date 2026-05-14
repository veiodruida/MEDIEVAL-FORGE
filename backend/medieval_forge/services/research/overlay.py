"""services/research/overlay.py — pure merge function for D-03/D-04 overlay layer.

Contract:
    1. Input metadata dict is NEVER mutated (deepcopy at top).
    2. Every condado.original_idx survives unchanged (CLAUDE.md rule 4).
    3. Unknown condado_id in overlay is silently ignored (overlay may target
       condados that no longer exist after region re-curation).
    4. Only fields present in `allowed_fields` are emitted into the merged
       output; the schema (CondadoOverlayEntry) accepts a SUPERSET of fields
       so cache hits + reloads validate cleanly across verdict changes.
    5. Pydantic validation (load_overlay_if_exists) happens BEFORE merge —
       a malformed sidecar raises ValidationError at load time, never silently
       corrupts the merge.
    6. Overlay fields with None value are NOT written to the merged condado
       (treated as "no information" — leaves any existing field untouched).

Consumer boundaries (D-04):
    - build_unity_zip (Plan 08): passes allowed_fields=_ZIP_BOUND_FIELDS.
    - api/v3/artifacts.py overlay endpoint (Plan 08): passes default
      _ALL_OVERLAY_FIELDS — UI sees all three fields regardless of zip verdict.

Plan 00 Q2 verdict drives the literal value of _ZIP_BOUND_FIELDS. Drift between
this constant and the verdict file is caught by
tests/unit/test_overlay_merge_strict_bound.py::test_zip_bound_fields_matches_q2_verdict_file_value.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel, ValidationError


class CondadoOverlayEntry(BaseModel):
    """Per-condado overlay payload — sidecar `research_overlay.json` value type.

    extra='forbid' so a typo in user-edited overlay JSON fails loudly at load
    time (RESEARCH §Pitfall 8). The Unity loader is JObject-tolerant (Q2 verdict)
    so unknown keys at the Unity boundary are silently dropped; we keep the
    pydantic boundary STRICT to catch authoring errors early.
    """

    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    kingdom_owner: str | None = None
    # REVIEWS fix #1 (T-07-05-05): cap historical_notes at 2KB to bound overlay file size.
    # Enforced at the pydantic boundary — load_overlay_if_exists() validates before merge.
    historical_notes: str | None = Field(default=None, max_length=2048)


class ResearchOverlay(RootModel[dict[str, CondadoOverlayEntry]]):
    """Top-level overlay file shape: `{condado_id: CondadoOverlayEntry, ...}`.

    Validation is via pydantic; load_overlay_if_exists() returns the validated
    dict-shaped root (NOT the model instance) so merge_overlay() can stay
    dict-typed and avoid pydantic-aware code paths.
    """


# ----------------------------------------------------------------------------
# CONTRACT (REVIEWS fix #1, 2026-05-14): schema-acceptance vs zip-emission
# ----------------------------------------------------------------------------
# CondadoOverlayEntry (pydantic schema) accepts THREE optional fields:
#     {name, kingdom_owner, historical_notes}
#
# _ZIP_BOUND_FIELDS controls which of those fields are emitted into the Unity
# export zip's territory_metadata.json (Plan 08 build_unity_zip).
#
# The two sets are deliberately ASYMMETRIC:
#   - Strict  (Q2 verdict): _ZIP_BOUND_FIELDS == frozenset({"name"})
#                           -> zip emits ONLY name; kingdom_owner + historical_notes
#                             stay in research_overlay.json sidecar but never enter zip.
#   - Tolerant (Q2 verdict): _ZIP_BOUND_FIELDS == frozenset({"name","kingdom_owner",
#                                                            "historical_notes"})
#                           -> zip emits all three.
#
# In BOTH verdicts the schema still tolerates all three (so cache hits + reloads
# validate cleanly). The artifact endpoint (Plan 08 api/v3/artifacts.py) ALWAYS
# passes the default _ALL_OVERLAY_FIELDS — UI consumers see all three regardless
# of zip-bound verdict. Only build_unity_zip applies _ZIP_BOUND_FIELDS.
#
# Drift between this constant and the Q2 verdict file is enforced by
# test_overlay_merge_strict_bound.py::test_zip_bound_fields_matches_q2_verdict_file_value.
# ----------------------------------------------------------------------------
# Phase 07 Plan 00 Q2 verdict: Tolerant (see 07-Q2-UNITY-LOADER-VERDICT.md).
# Reconquista MapLoader.cs uses JObject with `?.Value<T>() ?? default` per-key
# reads (line 196 + 212-218); unknown JSON keys are silently ignored. Safe to
# emit all three overlay fields into territory_metadata.json.
_ZIP_BOUND_FIELDS: frozenset[str] = frozenset({"name", "kingdom_owner", "historical_notes"})
_ALL_OVERLAY_FIELDS: frozenset[str] = frozenset({"name", "kingdom_owner", "historical_notes"})


def merge_overlay(
    metadata: dict[str, Any],
    overlay: dict[str, Any],
    allowed_fields: frozenset[str] = _ALL_OVERLAY_FIELDS,
) -> dict[str, Any]:
    """Return a new metadata dict with overlay fields merged into matching condados.

    Args:
        metadata: territory_metadata.json shape — must contain `condados: list[dict]`,
            each with `id: str`. Other keys (kingdoms, duchies, baronies, region, ...)
            are passed through deep-copied but unchanged.
        overlay: `{condado_id: {name?, kingdom_owner?, historical_notes?}}`. May
            contain condado_ids NOT in metadata — those are silently ignored
            (invariant 3: overlay may target condados that no longer exist after
            region re-curation).
        allowed_fields: subset of `_ALL_OVERLAY_FIELDS`. Fields outside this set
            are dropped from the merged output even when present in the overlay
            entry. build_unity_zip (Plan 08) passes `_ZIP_BOUND_FIELDS`; the
            artifact endpoint passes the default `_ALL_OVERLAY_FIELDS`.

    Returns:
        A NEW dict (deep copy of metadata) with overlay fields applied. Input
        metadata is byte-identical to its pre-call state.

    Invariants (all enforced by tests/unit/test_overlay_merge.py):
        1. Input metadata is NOT mutated.
        2. Every condado.original_idx survives unchanged.
        3. Unknown condado_id in overlay is silently ignored.
        4. Overlay fields with None value are NOT written.
        5. Only fields in `allowed_fields` are emitted.
        6. CondadoOverlayEntry schema is enforced before this function is called
           (load_overlay_if_exists raises ValidationError on malformed input).
    """
    # Plan 07-08 Task 3 (REVIEWS fix #10): explicit type contract.
    # merge_overlay() is INTERNAL — its caller (build_unity_zip / artifact
    # endpoint) calls load_overlay_if_exists() first, which validates and
    # returns a dict. If a string (e.g. truncated JSON literal) reaches us,
    # that is a programmer error and we fail loudly with TypeError. Without
    # this guard the function would raise AttributeError deep inside the
    # condado loop, obscuring the contract violation.
    if not isinstance(metadata, dict):
        raise TypeError(
            f"merge_overlay: metadata must be a dict, got {type(metadata).__name__}"
        )
    if not isinstance(overlay, dict):
        raise TypeError(
            f"merge_overlay: overlay must be a dict, got {type(overlay).__name__} — "
            f"did you forget to call load_overlay_if_exists() first?"
        )

    # Invariant 1: deepcopy at top — input metadata is never mutated.
    merged = copy.deepcopy(metadata)

    condados = merged.get("condados", [])
    for condado in condados:
        condado_id = condado.get("id")
        if condado_id is None:
            continue
        entry = overlay.get(condado_id)
        if entry is None:
            # Invariant 3: condado has no overlay entry — pass through unchanged.
            continue
        for field in allowed_fields:
            if field not in entry:
                continue
            value = entry[field]
            if value is None:
                # Invariant 4: None means "no information"; do NOT overwrite.
                continue
            condado[field] = value
        # Invariant 2 is implicit: we only assign whitelisted fields; original_idx
        # is not in _ALL_OVERLAY_FIELDS so it can never be overwritten.

    return merged


def load_overlay_if_exists(overlay_path: Path) -> dict[str, Any] | None:
    """Load `research_overlay.json` if it exists, validating shape via pydantic.

    Returns:
        - None if the file does not exist (D-12 zero-LLM parity guard).
        - The validated dict (RootModel root) ready to pass to merge_overlay()
          when the file exists and validates cleanly.

    Raises:
        json.JSONDecodeError: malformed JSON.
        pydantic.ValidationError: schema-invalid (extra fields, oversized
            historical_notes per T-07-05-05, type errors).

    Both error classes propagate intentionally — the runner (Plan 07) decides
    how to surface them; this function is pure I/O + validation.
    """
    if not overlay_path.exists():
        return None
    raw = overlay_path.read_text(encoding="utf-8")
    parsed = json.loads(raw)  # may raise JSONDecodeError on malformed JSON
    # pydantic validation — raises ValidationError on schema/length violations.
    model = ResearchOverlay.model_validate(parsed)
    # Return the dict-shaped root so merge_overlay stays dict-typed.
    return {cid: entry.model_dump() for cid, entry in model.root.items()}


__all__ = [
    "CondadoOverlayEntry",
    "ResearchOverlay",
    "_ALL_OVERLAY_FIELDS",
    "_ZIP_BOUND_FIELDS",
    "load_overlay_if_exists",
    "merge_overlay",
    "ValidationError",
]
