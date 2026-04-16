"""Async SQLAlchemy engine + session factory for Medieval Forge.

Per D-03 (CONTEXT.md): all runtime data lives in ~/.medieval-forge/.
"""
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DATA_DIR: Path = Path.home() / ".medieval-forge"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_URL: str = f"sqlite+aiosqlite:///{DATA_DIR}/medieval_forge.db"

engine = create_async_engine(DB_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an async session, closes on exit."""
    async with AsyncSessionLocal() as session:
        yield session
