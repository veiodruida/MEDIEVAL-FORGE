"""Pydantic v2 request/response schemas for the projects API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .services.countries import resolve_to_qid


def _resolve_country_list(v: str) -> str:
    """Accept 'Q29', 'Espanha', or 'Q29,Q45' / 'Espanha,Portugal'.

    Returns the canonical comma-separated QID string (no spaces).
    Raises ValueError if ANY token fails to resolve or if the string is empty.
    """
    tokens = [t.strip() for t in v.split(",") if t.strip()]
    if not tokens:
        raise ValueError("country_qid não pode ser vazio")
    qids = [resolve_to_qid(t) for t in tokens]
    # Deduplicate while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for q in qids:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return ",".join(out)


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    country_qid: str  # aceita nome, ISO, QID ou lista separada por vírgula — resolvido pelo validator
    period_start: int
    period_end: int
    bbox_lon_min: float | None = None
    bbox_lon_max: float | None = None
    bbox_lat_min: float | None = None
    bbox_lat_max: float | None = None
    generator_config: dict[str, Any] | None = None

    @field_validator("country_qid")
    @classmethod
    def _resolve_country(cls, v: str) -> str:
        try:
            return _resolve_country_list(v)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    country_qid: str | None = None
    period_start: int | None = None
    period_end: int | None = None
    bbox_lon_min: float | None = None
    bbox_lon_max: float | None = None
    bbox_lat_min: float | None = None
    bbox_lat_max: float | None = None
    generator_config: dict[str, Any] | None = None
    status: str | None = None

    @field_validator("country_qid")
    @classmethod
    def _resolve_country_optional(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            return _resolve_country_list(v)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    @model_validator(mode="after")
    def _check_period_ordering(self) -> "ProjectUpdate":
        """Enforce period_start < period_end only when both are explicitly provided."""
        if self.period_start is not None and self.period_end is not None:
            if self.period_start >= self.period_end:
                raise ValueError("period_start must be less than period_end")
        return self


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    country_qid: str | None
    period_start: int | None
    period_end: int | None
    bbox_lon_min: float | None
    bbox_lon_max: float | None
    bbox_lat_min: float | None
    bbox_lat_max: float | None
    generator_config: dict[str, Any] | None
    status: str
    created_at: datetime
    updated_at: datetime


# ==================== Phase 4: Edit API schemas ====================

from typing import Literal  # noqa: E402 — appended after existing imports


class MoveCapitalRequest(BaseModel):
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude in degrees")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude in degrees")


class MoveCapitalResponse(BaseModel):
    updated_territories: dict[str, dict]   # id -> GeoJSON Polygon/MultiPolygon
    affected_ids: list[str]


class MergeRequest(BaseModel):
    condado_ids: list[str] = Field(..., min_length=2, description="IDs to merge; primary_id MUST be in this list")
    primary_id: str = Field(..., description="ID whose name and key the merged result inherits")

    @field_validator("condado_ids")
    @classmethod
    def _unique_ids(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("condado_ids must be unique")
        return v


class MergeResponse(BaseModel):
    merged_id: str
    merged_territory: dict                   # GeoJSON (Polygon or MultiPolygon)
    removed_ids: list[str]
    warning: Literal["non_adjacent_multipolygon"] | None = None


class SplitRequest(BaseModel):
    cut_line: list[tuple[float, float]] = Field(..., min_length=2, max_length=1000)
    mode: Literal["snap", "polyline", "freehand"]

    @field_validator("cut_line")
    @classmethod
    def _coord_bounds(cls, v: list[tuple[float, float]]) -> list[tuple[float, float]]:
        for lon, lat in v:
            if not (-180.0 <= lon <= 180.0) or not (-90.0 <= lat <= 90.0):
                raise ValueError(f"cut_line coordinate out of range: ({lon}, {lat})")
        return v


class SplitResponse(BaseModel):
    original_id: str
    new_territory_a: dict                    # {id, geometry}
    new_territory_b: dict


class ReshapeGeometryRequest(BaseModel):
    geometry: dict                           # GeoJSON Polygon

    @field_validator("geometry")
    @classmethod
    def _polygon_size_bound(cls, v: dict) -> dict:
        # DoS bound per Research §Security Domain
        if v.get("type") != "Polygon":
            raise ValueError("geometry.type must be 'Polygon'")
        coords = v.get("coordinates") or []
        if not coords or not coords[0]:
            raise ValueError("geometry.coordinates[0] (exterior ring) required")
        if len(coords[0]) > 10_000:
            raise ValueError("polygon exterior has >10,000 coordinates — rejected (DoS bound)")
        return v


class SaveSnapshotRequest(BaseModel):
    territories: dict[str, dict]  # id -> feature dict (geometry + lon + lat + name...)
    capitals: dict[str, tuple[float, float]]  # id -> (lon, lat)


class VertexHandle(BaseModel):
    lon: float
    lat: float
    source_index: int  # index into the original exterior ring


class VertexHandlesResponse(BaseModel):
    handles: list[VertexHandle]


# ==================== Phase 5: Terrain Paint schemas ====================

TerrainType = Literal['mountain', 'forest', 'plains', 'river', 'arid']


class PaintTerrainRequest(BaseModel):
    territory_ids: list[str]
    terrain_type: TerrainType


class PaintTerrainResponse(BaseModel):
    painted_ids: list[str]
    skipped_ids: list[str]


# ==================== Etapa 8 (quick-260428-h1t): PATCH research/assignments ====================


class CondadoRename(BaseModel):
    """Rename / reparent a condado, OR (if cid is new) create one.

    Both fields optional: at the handler level, an existing condado is patched
    only on the fields that are not None. For a NEW condado_id, ``duchy_id``
    is required so the handler can derive ``kingdom_id`` from the duchies map.
    """
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    duchy_id: str | None = None


class EditAssignmentsRequest(BaseModel):
    """Body of PATCH /api/projects/{id}/research/assignments.

    At least one of ``barony_assignments`` / ``condado_renames`` must be set.
    """
    model_config = ConfigDict(extra="forbid")
    barony_assignments: dict[str, str] | None = None
    condado_renames: dict[str, CondadoRename] | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "EditAssignmentsRequest":
        if not self.barony_assignments and not self.condado_renames:
            raise ValueError(
                "at least one of 'barony_assignments' or 'condado_renames' must be provided"
            )
        return self
