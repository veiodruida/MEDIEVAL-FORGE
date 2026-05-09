"""Unit tests for /api/v3/projects/{id}/status manifest endpoint (Plan 03-02 D-21)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from medieval_forge.database import get_db
from medieval_forge.main import app
from medieval_forge.models import Base, Project
from medieval_forge.services import paths as paths_mod


@pytest_asyncio.fixture
async def in_memory_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(in_memory_db, monkeypatch, tmp_path):
    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")

    async def _override_get_db():
        async with in_memory_db() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _make_project(
    factory: async_sessionmaker,
    *,
    project_id: str | None = None,
    status: str = "draft",
) -> str:
    pid = project_id or str(uuid.uuid4())
    async with factory() as s:
        s.add(
            Project(
                id=pid,
                name="test",
                country_qid="Q29,Q45",
                period_start=868,
                period_end=1492,
                status=status,
            )
        )
        await s.commit()
    return pid


# ---- 1. 404 when project absent ----
async def test_status_returns_404_when_project_does_not_exist(client):
    r = await client.get(f"/api/v3/projects/{uuid.uuid4()}/status")
    assert r.status_code == 404


# ---- 2. Project present, no artifacts → has_artifacts all False ----
async def test_status_returns_all_false_has_artifacts_when_nothing_generated(
    client, in_memory_db
):
    pid = await _make_project(in_memory_db, status="draft")
    r = await client.get(f"/api/v3/projects/{pid}/status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "draft"
    assert isinstance(body["has_artifacts"], dict)
    assert len(body["has_artifacts"]) == 14
    assert all(v is False for v in body["has_artifacts"].values())
    assert body["last_generated_at"] is None


# ---- 3. Project + 14 artifacts present → all True + last_generated_at set ----
async def test_status_returns_all_true_when_all_14_artifacts_present(
    client, in_memory_db, tmp_path
):
    from medieval_forge.api.v3.artifacts import ARTIFACT_FILES

    pid = await _make_project(in_memory_db, status="generated")
    out_dir = tmp_path / "projects" / pid / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in ARTIFACT_FILES:
        (out_dir / f).write_bytes(b"x")

    r = await client.get(f"/api/v3/projects/{pid}/status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "generated"
    assert all(v is True for v in body["has_artifacts"].values())
    # last_generated_at should be present (project.updated_at.isoformat()).
    assert body["last_generated_at"] is not None
    # Round-trip parse to confirm ISO format.
    parsed = datetime.fromisoformat(body["last_generated_at"])
    assert isinstance(parsed, datetime)


# ---- 4. UUID guard ----
async def test_status_returns_400_when_project_id_is_not_uuid(client):
    r = await client.get("/api/v3/projects/not-a-uuid/status")
    assert r.status_code == 400
