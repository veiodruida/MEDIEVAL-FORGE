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
    country_qid: Mapped[str] = mapped_column(String(20), nullable=False)
    period_start: Mapped[int] = mapped_column(nullable=False)
    period_end: Mapped[int] = mapped_column(nullable=False)
    bbox_lon_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_lon_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_lat_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_lat_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    generator_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )


class LLMCredential(Base):
    """Persistent LLM credential store (per-user, local tool).

    Each provider has exactly one row (provider_id is PK). Deliberate tradeoff
    against D-14 (original "never on disk" rule): users asked for persistence
    across restarts. The DB file lives in the user's home directory and is not
    shared, so this is equivalent to tools like gh/git that persist tokens locally.
    """
    __tablename__ = "llm_credentials"

    provider_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    # "api_key" | "oauth" | "none" (Ollama; value stores the selected model)
    credential_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # For api_key: the raw key. For oauth: access_token. For Ollama none: empty.
    credential_value: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    # Optional refresh token for OAuth flows.
    refresh_token: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # Ollama: user-selected local model (e.g. "qwen2.5:7b"). Null for other providers.
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )


class ResearchCache(Base):
    """Per-research cache (RESEARCH-04, D-25). Key: SHA-256 of (country_qid:period_start:period_end:provider:model)."""
    __tablename__ = "research_cache"

    cache_key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    country_qid: Mapped[str] = mapped_column(String(20), nullable=False)
    period_start: Mapped[int] = mapped_column(nullable=False)
    period_end: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
