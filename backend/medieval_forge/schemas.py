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
    country_qid: str
    period_start: int
    period_end: int
    bbox_lon_min: float | None
    bbox_lon_max: float | None
    bbox_lat_min: float | None
    bbox_lat_max: float | None
    generator_config: dict[str, Any] | None
    status: str
    created_at: datetime
    updated_at: datetime
