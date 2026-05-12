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
