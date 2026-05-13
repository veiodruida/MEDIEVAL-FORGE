"""services/export/validator.py — Phase 06 export gate.

Pure function `validate_export(generated_dir, cfg)` runs:
  1. Per-file schema validation (D-05/D-06) — SCHEMA_INVALID short-circuits per D-18
  2. Five semantic checks (D-09..D-13) — collect ALL errors per D-18
     - COLOR_COLLISION (D-13): within-file + cross-layer terrain palette
     - OCEAN_LEAK (D-09): territory RGB in landmask-ocean pixel (one-way)
     - TERRITORY_TOO_SMALL (D-12): pixel count < cfg.blob_merge_px (200)
     - MISSING_ORIGINAL_IDX (D-11 REVISED): condados-only; baronies exempt
     - PIXEL_CENTER_OUT_OF_RANGE (D-10): bounds check; Y-down preserved

Returns (ValidationReport, sha256_by_file) — caller branches on report.passed.

Body implementations land in Plan 06-02. This file (Plan 06-01) only ships
signatures + ValidationFailedError + the orchestrator skeleton.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..pipeline.contracts import EXPORT_FILE_CONTRACT, RegionConfig
from .schemas import (
    LookupBaronyColorsSchema,
    LookupCondadoColorsSchema,
    MountainRiverDataSchema,
    TerrainTypesSchema,
    TerritoryMetadataSchema,
    ValidationErrorEntry,
    ValidationReport,
)


class ValidationFailedError(Exception):
    """Raised by build_unity_zip (Plan 06-03) when validate_export reports failure.

    The endpoint layer (api/v3/export.py) catches this and maps to HTTP 422 with
    the structured error envelope (D-08). The validator itself NEVER raises this —
    it returns ValidationReport with passed=False. Keeps validator pure (D-01).
    """

    def __init__(self, report: ValidationReport) -> None:
        super().__init__(f"export gate failed with {len(report.errors)} errors")
        self.report = report


@dataclass
class _ValidationContext:
    """Internal mutable accumulator. PUBLIC return is ValidationReport (pydantic)."""

    errors: list[ValidationErrorEntry] = field(default_factory=list)
    warnings: list[ValidationErrorEntry] = field(default_factory=list)
    sha256_by_file: dict[str, str] = field(default_factory=dict)

    def add_error(self, code: str, file: str | None, context: dict, message: str) -> None:
        self.errors.append(
            ValidationErrorEntry(
                code=code,
                severity="error",
                file=file,
                context=context,
                message=message,
            )
        )

    def add_warning(self, code: str, file: str | None, context: dict, message: str) -> None:
        self.warnings.append(
            ValidationErrorEntry(
                code=code,
                severity="warning",
                file=file,
                context=context,
                message=message,
            )
        )


# Conditional contract files — toy regions may legitimately omit these
# when render_mountains/render_rivers return None for empty data. The pipeline
# only writes the file when the render produces a non-None result; the
# validator must NOT flag the absence as SCHEMA_INVALID. See
# backend/tests/e2e/test_france_1066_export_contract.py:44-48 for the established
# precedent + EXPORT_FILE_CONTRACT_DEFERRED == () meaning the file set is
# canonical but two members are conditional.
_CONDITIONAL_FILES: frozenset[str] = frozenset({
    "mountains_mask.png",
    "rivers_overlay.png",
})


# Schema registry — maps contract filename to its pydantic schema.
_SCHEMA_MAP: dict[str, type] = {
    "lookup_barony_colors.json": LookupBaronyColorsSchema,
    "lookup_condado_colors.json": LookupCondadoColorsSchema,
    "terrain_types.json": TerrainTypesSchema,
    "territory_metadata.json": TerritoryMetadataSchema,
    "mountain_river_data.json": MountainRiverDataSchema,
}


def validate_export(
    generated_dir: Path,
    cfg: RegionConfig,
) -> tuple[ValidationReport, dict[str, str]]:
    """Pure function. Reads files in `generated_dir`, returns (report, sha256_map).

    No side effects, no HTTP coupling, no DB access. Safe to call from CLI,
    UI preview, dry-run endpoint, and the zip builder.

    Args:
        generated_dir: Pipeline output directory (e.g., project_dir/output).
        cfg: RegionConfig — `cfg.ocean_far`, `cfg.blob_merge_px`, `cfg.map_w`, `cfg.map_h`
             are read; cfg is NOT mutated (D-V3-05).

    Returns:
        (report, sha256_by_file). sha256_by_file maps every existing contract
        file to its hex-encoded sha256 (validator-time hashing per Per-Discretion #2).
    """
    ctx = _ValidationContext()
    payloads: dict[str, Any] = {}

    # Step 1: read each contract file once; compute sha256; parse JSON-shaped files.
    for fname in EXPORT_FILE_CONTRACT:
        path = generated_dir / fname
        if not path.exists():
            if fname in _CONDITIONAL_FILES:
                # Toy regions (e.g. France 1066) legitimately omit mountains_mask.png
                # and rivers_overlay.png when render_mountains/render_rivers return None
                # for empty mountain/river data. See
                # backend/tests/e2e/test_france_1066_export_contract.py:44-48 for the
                # canonical conditional set. Not a gate failure.
                continue
            ctx.add_error(
                "SCHEMA_INVALID",
                file=fname,
                context={"reason": "missing"},
                message=f"contract file missing: {fname}",
            )
            continue
        raw_bytes = path.read_bytes()
        ctx.sha256_by_file[fname] = hashlib.sha256(raw_bytes).hexdigest()
        if fname.endswith(".json"):
            try:
                payloads[fname] = json.loads(raw_bytes.decode("utf-8"))
            except json.JSONDecodeError as exc:
                ctx.add_error(
                    "SCHEMA_INVALID",
                    file=fname,
                    context={"reason": str(exc)},
                    message=f"invalid JSON: {fname}",
                )

    # Step 2: pydantic schema validation per JSON. SCHEMA_INVALID short-circuits
    # the semantic checks (D-18 exception — corrupt JSON cannot feed downstream).
    schema_ok = _run_schema_validation(ctx, payloads)
    if not schema_ok:
        return _build_report(ctx), ctx.sha256_by_file

    # Step 3: run all 5 semantic checks; collect ALL errors (D-18 main rule).
    _check_color_collision(ctx, payloads, cfg)
    _check_ocean_leak(ctx, generated_dir, cfg)
    _check_territory_size(ctx, generated_dir, payloads, cfg)
    _check_original_idx(ctx, payloads, cfg)
    _check_pixel_center(ctx, payloads, cfg)

    return _build_report(ctx), ctx.sha256_by_file


def _build_report(ctx: _ValidationContext) -> ValidationReport:
    return ValidationReport(
        passed=len(ctx.errors) == 0,
        errors=list(ctx.errors),
        warnings=list(ctx.warnings),
    )


def _run_schema_validation(ctx: _ValidationContext, payloads: dict[str, Any]) -> bool:
    """Return True iff every parseable JSON passes its schema. Records SCHEMA_INVALID on failure."""
    all_ok = True
    for fname, Schema in _SCHEMA_MAP.items():
        if fname not in payloads:
            continue  # already reported as missing in Step 1
        try:
            Schema.model_validate(payloads[fname])
        except ValidationError as exc:
            ctx.add_error(
                "SCHEMA_INVALID",
                file=fname,
                context={"errors": exc.errors()},
                message=f"schema validation failed for {fname}",
            )
            all_ok = False
    return all_ok


# ---------------------------------------------------------------------------
# Plan 06-02 fills these bodies. Stubs raise NotImplementedError so any
# accidental call surfaces immediately in test output rather than silently
# passing the gate.
# ---------------------------------------------------------------------------


def _check_color_collision(
    ctx: _ValidationContext, payloads: dict[str, Any], cfg: RegionConfig
) -> None:
    """COLOR_COLLISION (D-13): two collision scopes.

    Scope 1 (within-file): The lookup_*_colors.json files are written as
    {f"{r},{g},{b}": territory_idx}. JSON dict semantics enforce unique keys,
    so a literal duplicate key would have been silently collapsed at write
    time. We detect within-file collision by inverting the dict and checking
    for two distinct territory ids mapping to the same RGB. Achievable in
    practice when a broken fixture rewrites the file with duplicated RGB
    values across distinct ids.

    Scope 2 (cross-layer terrain): Any condado/barony RGB in lookup_*_colors.json
    that equals PLAINS_RGB, OCEAN_RGB (from terrain.py), or cfg.ocean_far
    (the lookup-PNG ocean sentinel) is a cross-layer collision. Mirrors
    services/pipeline/terrain.py:47-75 assert_palette_no_collision; we
    PROMOTE the ValueError into a structured error (D-13 + Phase 05 Plan
    05-11 callsite migration).

    D-13 explicitly allows cross-FILE (barony color == condado color) —
    different lookup layers, different consumers. Don't flag that.
    """
    from ..pipeline.terrain import OCEAN_RGB, PLAINS_RGB

    cross_layer_protected: dict[tuple[int, int, int], str] = {
        tuple(PLAINS_RGB): "PLAINS_RGB",
        tuple(OCEAN_RGB): "OCEAN_RGB",
        tuple(cfg.ocean_far): "cfg.ocean_far",
    }

    for fname in ("lookup_barony_colors.json", "lookup_condado_colors.json"):
        rgb_to_ids: dict[str, list[int]] = {}
        for rgb_key, tid in payloads.get(fname, {}).items():
            rgb_to_ids.setdefault(rgb_key, []).append(tid)

        # Scope 1: within-file dup RGB → multiple territory ids
        for rgb_key, ids in rgb_to_ids.items():
            if len(ids) > 1:
                ctx.add_error(
                    "COLOR_COLLISION",
                    file=fname,
                    context={
                        "rgb": rgb_key,
                        "territories": sorted(ids),
                        "scope": "within_file",
                    },
                    message=f"RGB {rgb_key} maps to {len(ids)} territories in {fname}",
                )

        # Scope 2: cross-layer terrain
        for rgb_key, ids in rgb_to_ids.items():
            try:
                rgb_tuple = tuple(int(c) for c in rgb_key.split(","))
            except ValueError:
                continue  # schema validation already caught malformed keys
            if rgb_tuple in cross_layer_protected:
                ctx.add_error(
                    "COLOR_COLLISION",
                    file=fname,
                    context={
                        "rgb": rgb_key,
                        "territories": sorted(ids),
                        "scope": "cross_layer_terrain",
                        "conflicts_with": cross_layer_protected[rgb_tuple],
                    },
                    message=(
                        f"RGB {rgb_key} in {fname} collides with "
                        f"{cross_layer_protected[rgb_tuple]} (cross-layer terrain palette)"
                    ),
                )


def _check_ocean_leak(
    ctx: _ValidationContext, generated_dir: Path, cfg: RegionConfig
) -> None:
    """OCEAN_LEAK (D-09): territory color appears in landmask-ocean pixel.

    One-way only (leak from territory into ocean). The bidirectional "ocean
    color inside a polygon" check would false-positive on legitimate enclosed
    lakes / lagoons — out of scope per CONTEXT.md deferred ideas.

    Landmask source: terrain_lookup.png (D-09 final + RESEARCH §Per-Discretion #18).
    Karpathy-simple: avoid re-deriving the landmask from GeoJSON; terrain_lookup.png
    is already on disk, schema-validated (corrupt PNG → SCHEMA_INVALID short-circuit
    in Step 2; we never reach here).

    The land-vs-ocean predicate is taken from terrain.py:35-36:
      ocean pixel in terrain_lookup.png == OCEAN_RGB (0, 0, 0)
      land  pixel in terrain_lookup.png == PLAINS_RGB (124, 179, 66)
      → `land = (terrain_arr != OCEAN_RGB).any(axis=-1)` returns True where ANY channel differs from black

    Sampling: up to 10 leak coordinates per file for the error context — enough
    for UI debugging, doesn't bloat the response.
    """
    import numpy as np
    from PIL import Image

    from ..pipeline.terrain import OCEAN_RGB

    ocean_rgb_uint8 = np.array(OCEAN_RGB, dtype=np.uint8)
    expected_ocean_rgb = np.array(cfg.ocean_far, dtype=np.uint8)

    terrain_path = generated_dir / "terrain_lookup.png"
    if not terrain_path.exists():
        return  # missing already reported in Step 1; nothing more we can do
    terrain_arr = np.array(Image.open(terrain_path).convert("RGB"))
    land = (terrain_arr != ocean_rgb_uint8).any(axis=-1)  # bool[H, W]
    ocean = ~land

    for lookup_name in ("lookup_barony.png", "lookup_condado.png"):
        path = generated_dir / lookup_name
        if not path.exists():
            continue  # missing already reported in Step 1
        lk = np.array(Image.open(path).convert("RGB"))
        if lk.shape[:2] != terrain_arr.shape[:2]:
            ctx.add_error(
                "OCEAN_LEAK",
                file=lookup_name,
                context={
                    "reason": "shape_mismatch",
                    "terrain_shape": list(terrain_arr.shape),
                    "lookup_shape": list(lk.shape),
                },
                message=(
                    f"{lookup_name} shape mismatch with terrain_lookup.png — "
                    f"cannot check ocean leak"
                ),
            )
            continue
        leaks = ocean & np.any(lk != expected_ocean_rgb, axis=-1)
        leak_count = int(leaks.sum())
        if leak_count > 0:
            ys, xs = np.where(leaks)
            sample = [
                {
                    "x": int(xs[i]),
                    "y": int(ys[i]),
                    "rgb": [int(c) for c in lk[ys[i], xs[i]]],
                }
                for i in range(min(10, len(ys)))
            ]
            ctx.add_error(
                "OCEAN_LEAK",
                file=lookup_name,
                context={
                    "leak_count": leak_count,
                    "sample_pixels": sample,
                    "expected_ocean_rgb": list(cfg.ocean_far),
                },
                message=(
                    f"{lookup_name}: {leak_count} pixel(s) in ocean region "
                    f"do not match cfg.ocean_far {tuple(cfg.ocean_far)}"
                ),
            )


def _check_territory_size(
    ctx: _ValidationContext,
    generated_dir: Path,
    payloads: dict[str, Any],
    cfg: RegionConfig,
) -> None:
    """TERRITORY_TOO_SMALL (D-12): pixel_count < cfg.blob_merge_px.

    Threshold = cfg.blob_merge_px (default 200) — no new config field per D-12.
    Reads pixel_count straight from territory_metadata.json (already populated
    by services/pipeline/export.py:37-82 and schema-validated in Step 2).
    Both condados and baronies share the same floor.

    Note on the export.py:52 `npx == 0` compaction: condados/baronies with
    pixel_count=0 are filtered out at write time, so the smallest count we'll
    see is 1. Schema (CondadoEntrySchema.pixel_count) already enforces ge=1
    — this check enforces the higher >= blob_merge_px floor.
    """
    threshold = cfg.blob_merge_px
    meta = payloads.get("territory_metadata.json", {})

    for kind, key, id_field in (
        ("condado", "condados", "id"),
        ("barony", "baronies", "name"),
    ):
        for entry in meta.get(key, []):
            pixel_count = entry.get("pixel_count", 0)
            if pixel_count < threshold:
                tid = entry.get(id_field, "<unknown>")
                ctx.add_error(
                    "TERRITORY_TOO_SMALL",
                    file="territory_metadata.json",
                    context={
                        "kind": kind,
                        "id": tid,
                        "pixel_count": pixel_count,
                        "threshold": threshold,
                    },
                    message=(
                        f"{kind} {tid!r}: pixel_count={pixel_count} < "
                        f"cfg.blob_merge_px={threshold}"
                    ),
                )


def _check_original_idx(
    ctx: _ValidationContext, payloads: dict[str, Any], cfg: RegionConfig
) -> None:
    """MISSING_ORIGINAL_IDX (D-11 REVISED): condados-only; baronies exempt.

    CLAUDE.md rule 4 (Nájera bug — indices > 44) + rule 7 (byOriginalIdx
    Unity-side) both apply to condados. The canonical barony shape in
    tests/fixtures/iberia_868/golden/territory_metadata.json:1838+ is
    {name, condado_idx, duchy, pixel_count} — NO original_idx. The Unity
    `byOriginalIdx` lookup is condado-keyed; baronies use positional
    `condado_idx`. NO YAML flag added, NO RegionConfig field added —
    Iberia passes the gate cleanly with all 92 condados carrying
    `original_idx: 1..92` (verified in golden 91/91 emitted after
    `npx == 0` compaction).

    Schema (CondadoEntrySchema.original_idx) is `int | None = None` because
    legacy data may have null; this check tightens to "must be a non-null int".
    """
    meta = payloads.get("territory_metadata.json", {})

    for entry in meta.get("condados", []):
        oidx = entry.get("original_idx")
        if oidx is None:
            tid = entry.get("id", "<unknown>")
            ctx.add_error(
                "MISSING_ORIGINAL_IDX",
                file="territory_metadata.json",
                context={"kind": "condado", "id": tid},
                message=(
                    f"condado {tid!r}: missing original_idx "
                    f"(condados-only check per D-11; CLAUDE.md rules 4+7)"
                ),
            )
    # NOTE: baronies are EXEMPT (D-11 REVISED). Do not iterate meta.get("baronies", []).


def _check_pixel_center(
    ctx: _ValidationContext, payloads: dict[str, Any], cfg: RegionConfig
) -> None:
    """PIXEL_CENTER_OUT_OF_RANGE (D-10): bounds check; numpy Y-down preserved.

    pixel_center ships as [col, row] in 1x lookup space (PREFLIGHT Q9 + v1
    archive ARCHITECTURE.md:252). The check is 0 <= col < cfg.map_w AND
    0 <= row < cfg.map_h. Half-open intervals — pixel at exactly map_w or
    map_h is OUT of range (would index past the last valid pixel).

    No Y-axis conversion. The v1-archive "convert on export" idea is REJECTED
    by D-10: Unity loader already inverts on load (Reconquista contract).
    Flipping at export would break byte-parity with Reconquista gold.

    Only condados carry pixel_center (canonical barony shape lacks it per
    territory_metadata.json:1838+); baronies are silently skipped.
    """
    meta = payloads.get("territory_metadata.json", {})
    map_w = cfg.map_w
    map_h = cfg.map_h

    for entry in meta.get("condados", []):
        pc = entry.get("pixel_center")
        if pc is None:
            continue  # schema enforces presence; if absent, SCHEMA_INVALID would have fired
        col, row = pc[0], pc[1]
        if not (0 <= col < map_w) or not (0 <= row < map_h):
            tid = entry.get("id", "<unknown>")
            ctx.add_error(
                "PIXEL_CENTER_OUT_OF_RANGE",
                file="territory_metadata.json",
                context={
                    "kind": "condado",
                    "id": tid,
                    "pixel_center": [col, row],
                    "bounds": {"map_w": map_w, "map_h": map_h},
                    "note": "Y-down numpy convention (D-10); Unity flips on load",
                },
                message=(
                    f"condado {tid!r}: pixel_center=[{col}, {row}] outside "
                    f"[0, {map_w}) × [0, {map_h})"
                ),
            )


__all__ = ["validate_export", "ValidationFailedError"]
