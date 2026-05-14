"""SQLAlchemy ORM models for Medieval Forge."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Project(Base):
    """A Medieval Forge project (PROJ-01..05)."""
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country_qid: Mapped[str | None] = mapped_column(String(200), nullable=True)
    period_start: Mapped[int | None] = mapped_column(nullable=True)
    period_end: Mapped[int | None] = mapped_column(nullable=True)
    bbox_lon_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_lon_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_lat_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_lat_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    generator_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    region_key: Mapped[str] = mapped_column(String(64), nullable=False, default="iberia_868")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )


class LLMCredential(Base):
    """SQLite-backed credential store for LLM providers.

    Phase 07 D-06: payload column stores plaintext JSON per Discretion #1
    (OS-keyring escrow is v3.1 hardening per RESEARCH Don't Hand-Roll).

    REVIEWS fix #8 (2026-05-14): provider_id is an enum-string PK, NOT a FK
    from a `providers` table. Deletion path is exclusively
    services/credential_store.delete_credentials(provider). Rotation does NOT
    cascade to ResearchCache rows (cache is content-addressable, outlives keys).
    """
    __tablename__ = "llm_credentials"
    provider_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    credential_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )


class ResearchCache(Base):
    """SQLite cache for LLM research payloads.

    REVIEWS fix #8 (2026-05-14): this table is intentionally INDEPENDENT of
    llm_credentials. Cache keys are content-addressable
    (sha256(country|period|provider|model|...)), so credential rotation does NOT
    invalidate cached payloads. The only deletion path is the (currently
    unimplemented) force-clear admin action.

    Lifecycle:
    - LLMCredential row -> may come and go as user rotates keys.
    - ResearchCache row -> outlives credential rows; cache hits succeed even
      without any LLMCredential present (the cached payload is the answer).
    """
    __tablename__ = "research_cache"
    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)  # SHA-256 hex
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    # REVIEWS fix #2 (2026-05-14): renamed from `created_at` to `generated_at` to
    # disambiguate from research_overlay.meta.json::applied_at (Plan 07b).
    # generated_at == when the LLM originally produced this cached payload.
    # applied_at  == when the runner wrote this overlay to a project (lives in
    #                meta sidecar, NOT in DB).
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
