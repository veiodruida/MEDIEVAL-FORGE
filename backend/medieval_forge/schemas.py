"""Pydantic v2 request/response schemas for the projects API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .services.countries import resolve_to_qid


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    country_qid: str  # aceita nome, ISO ou QID — resolvido pelo validator
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
            return resolve_to_qid(v)
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
            return resolve_to_qid(v)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


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
