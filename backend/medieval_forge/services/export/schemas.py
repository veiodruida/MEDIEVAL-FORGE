"""services/export/schemas.py — pydantic v2 schemas for the 5 contract JSONs + MANIFEST.

Reuses RegionConfigSchema's idioms (region_loader.py:79-149): BaseModel,
ConfigDict(extra='forbid'), Field(...) constraints. No cross-field validators
(D-19 deferral; v3.1 territory).

MANIFEST_SCHEMA_VERSION bump from 1 → 2 per D-07.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator

# v3 (Phase 07 D-CONTEXT canonical_refs): added research_overlay_applied to MANIFEST
# bump 2 → 3 alongside CondadoEntrySchema gaining `kingdom_owner` + `historical_notes`
# (D-03 + RESEARCH §Pitfall 8 — extend schema additively so extra='forbid' still rejects
# truly-unknown fields while overlay merge can write the two optional fields).
MANIFEST_SCHEMA_VERSION: int = 3

_RGB_KEY_RE = re.compile(r"^(\d{1,3}),(\d{1,3}),(\d{1,3})$")


def _validate_rgb_keys(v: dict) -> dict:
    for key in v:
        m = _RGB_KEY_RE.match(key)
        if not m or any(int(g) > 255 for g in m.groups()):
            raise ValueError(
                f"invalid RGB key: {key!r} (must match 0-255,0-255,0-255)"
            )
    return v


class LookupBaronyColorsSchema(RootModel[dict[str, int]]):
    """RGB-string-key → barony index. Mirrors lookup.py:51 (`f'{r},{g},{b}': i`)."""

    @field_validator("root")
    @classmethod
    def _keys(cls, v: dict[str, int]) -> dict[str, int]:
        return _validate_rgb_keys(v)


class LookupCondadoColorsSchema(RootModel[dict[str, int]]):
    """RGB-string-key → condado index. Same shape as barony."""

    @field_validator("root")
    @classmethod
    def _keys(cls, v: dict[str, int]) -> dict[str, int]:
        return _validate_rgb_keys(v)


class TerrainTypePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    movement: float = Field(ge=0.0)
    defense: float = Field(ge=0.0)
    attack: float = Field(ge=0.0)


class TerrainTypesSchema(RootModel[dict[str, TerrainTypePayload]]):
    """RGB-string-key → terrain payload. terrain.py:41-44."""

    @field_validator("root")
    @classmethod
    def _keys(cls, v: dict[str, TerrainTypePayload]) -> dict[str, TerrainTypePayload]:
        return _validate_rgb_keys(v)


class CondadoEntrySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    lon: float
    lat: float
    duchy: str
    kingdom: str
    pixel_center: tuple[int, int]    # [col, row] Y-DOWN — D-10 (numpy convention; Unity flips on load)
    pixel_count: int = Field(ge=1)
    baronies: list[str]
    original_idx: int | None = None  # OPTIONAL — emitted when condado tuple len > 6 (export.py:69)
    # Phase 07 (D-03 + Pitfall 8): overlay-mergeable fields. Optional so raw pipeline
    # output (no overlay) still validates; merged metadata (with overlay) also validates.
    # Schema acceptance is BROADER than zip emission — see services/research/overlay.py
    # `_ZIP_BOUND_FIELDS` doc-comment for the contract.
    kingdom_owner: str | None = None
    historical_notes: str | None = None


class BaronyEntrySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    condado_idx: int
    duchy: str
    pixel_count: int = Field(ge=1)
    # NO original_idx — baronies exempt per D-11 (golden territory_metadata.json:1838+)


class DuchyEntrySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kingdom: str
    name: str


class TerritoryMetadataSchema(BaseModel):
    """Mirrors services/pipeline/export.py:37-82 writer verbatim.
    ConfigDict(extra='forbid') catches silent drift on every CI run."""
    model_config = ConfigDict(extra="forbid")
    region: str
    map_size: tuple[int, int]
    bounds: dict[str, float]
    kingdoms: dict[str, str]
    duchies: dict[str, DuchyEntrySchema]
    condados: list[CondadoEntrySchema]
    baronies: list[BaronyEntrySchema]


class MountainRiverDataSchema(BaseModel):
    """Permissive — toy datasets ship {}; real Iberia ships rich nested data."""
    model_config = ConfigDict(extra="allow")  # external file, looser contract
    mountains: dict = Field(default_factory=dict)
    rivers: dict = Field(default_factory=dict)


class ManifestFileEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    source: str  # "generated" | "placeholder"
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ValidationErrorEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str  # SCHEMA_INVALID | COLOR_COLLISION | OCEAN_LEAK | MISSING_ORIGINAL_IDX | TERRITORY_TOO_SMALL | PIXEL_CENTER_OUT_OF_RANGE
    severity: str  # "error" | "warning"
    file: str | None = None
    context: dict
    message: str


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passed: bool
    errors: list[ValidationErrorEntry] = Field(default_factory=list)
    warnings: list[ValidationErrorEntry] = Field(default_factory=list)


class ManifestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = MANIFEST_SCHEMA_VERSION
    region_key: str
    project_id: str
    generated_at_utc: str
    exported_at_utc: str
    spec_version: int = 1
    phase: int = 6
    validation_report: ValidationReport
    files: list[ManifestFileEntry]
    # Phase 07 D-04: True when Plan 08's build_unity_zip merged a research overlay
    # into territory_metadata.json. False (default) for zero-LLM exports — D-12 parity.
    research_overlay_applied: bool = False
