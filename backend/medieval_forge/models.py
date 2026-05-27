"""SQLAlchemy ORM models for Medieval Forge."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, LargeBinary, String, UniqueConstraint
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


class Branch(Base):
    """Phase 08 D-10/D-11/D-15/D-22: Named branch for a project.

    main branch is delete-protected (D-15); rename allowed.
    original_idx_high_water tracks the highest original_idx allocated on this
    branch so splits always get a unique index (D-22).
    """
    __tablename__ = "branches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_main: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    original_idx_high_water: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )  # D-22: monotonically increasing per branch; freed idx never reused
    edits_since_snapshot: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )  # D-10 cadence counter for auto-snapshot at 25 edits
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_branch_project_name"),
    )


class Snapshot(Base):
    """Phase 08 D-12: per-branch snapshot blob (gzip+json of geojson+config+edit_log).

    Trigger values: "auto" | "manual" | "pre_slider_change" (D-19).
    seq is 1-based monotonic per branch (UniqueConstraint enforces no duplicate seq).
    """
    __tablename__ = "snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    branch_id: Mapped[str] = mapped_column(
        ForeignKey("branches.id"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    trigger: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # "auto" | "manual" | "pre_slider_change"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("branch_id", "seq", name="uq_snapshot_branch_seq"),
    )


class EditEvent(Base):
    """Phase 08 D-35: edit operation log for a branch.

    op_type examples: "vertex_move", "vertex_add", "vertex_delete", "split", "merge".
    payload is stored as JSON; op_type pattern guard is at the endpoint layer.
    """
    __tablename__ = "edit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    branch_id: Mapped[str] = mapped_column(
        ForeignKey("branches.id"), nullable=False, index=True
    )
    op_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
