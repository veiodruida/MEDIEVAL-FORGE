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
        except Exception as exc:  # pydantic.ValidationError or json shape mismatch
            ctx.add_error(
                "SCHEMA_INVALID",
                file=fname,
                context={"errors": str(exc)},
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
    """COLOR_COLLISION (D-13): within-file dup RGB + cross-layer terrain palette."""
    raise NotImplementedError("06-02: fill body — see 06-RESEARCH.md §validator orchestration")


def _check_ocean_leak(
    ctx: _ValidationContext, generated_dir: Path, cfg: RegionConfig
) -> None:
    """OCEAN_LEAK (D-09): territory RGB in landmask-ocean pixel. One-way only."""
    raise NotImplementedError("06-02: fill body — see 06-RESEARCH.md §Per-Discretion #18 pseudocode")


def _check_territory_size(
    ctx: _ValidationContext,
    generated_dir: Path,
    payloads: dict[str, Any],
    cfg: RegionConfig,
) -> None:
    """TERRITORY_TOO_SMALL (D-12): pixel count < cfg.blob_merge_px (200)."""
    raise NotImplementedError("06-02: fill body")


def _check_original_idx(
    ctx: _ValidationContext, payloads: dict[str, Any], cfg: RegionConfig
) -> None:
    """MISSING_ORIGINAL_IDX (D-11 REVISED): condados-only; baronies exempt by canonical shape."""
    raise NotImplementedError("06-02: fill body")


def _check_pixel_center(
    ctx: _ValidationContext, payloads: dict[str, Any], cfg: RegionConfig
) -> None:
    """PIXEL_CENTER_OUT_OF_RANGE (D-10): bounds check. Y-down preserved per D-10."""
    raise NotImplementedError("06-02: fill body")


__all__ = ["validate_export", "ValidationFailedError"]
