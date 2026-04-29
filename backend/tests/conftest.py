import json
import uuid as _uuid
from pathlib import Path

import pytest
import pytest_asyncio
import respx
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from medieval_forge.main import app
from medieval_forge.database import get_db
from medieval_forge.models import Base, Project
from medieval_forge.services import paths

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    """Read backend/tests/fixtures/responses_recorded/{name}.json and return parsed dict."""
    return json.loads((FIXTURES_DIR / "responses_recorded" / f"{name}.json").read_text())


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async def _override():
        yield db_session
    app.dependency_overrides[get_db] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def respx_mock():
    """Yield a respx mock context (assert_all_called=False)."""
    with respx.mock(assert_all_called=False) as mock:
        yield mock


@pytest.fixture
def tmp_raw_dir(monkeypatch, tmp_path):
    """Monkeypatch paths.PROJECTS_ROOT to tmp_path; return (project_id, raw_dir)."""
    monkeypatch.setattr(paths, "PROJECTS_ROOT", tmp_path / "projects")
    pid = str(_uuid.uuid4())
    dirs = paths.ensure_project_dirs(pid)
    return pid, dirs["raw"]


@pytest_asyncio.fixture
async def async_session():
    """Yield (session, session_factory) backed by in-memory SQLite."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s, Session
    await engine.dispose()


@pytest_asyncio.fixture
async def sample_project(async_session):
    """Create a Project row and return (project_id, session_factory)."""
    session, factory = async_session
    proj = Project(name="Test", country_qid="Q142", period_start=1000, period_end=1100)
    session.add(proj)
    await session.commit()
    await session.refresh(proj)
    return proj.id, factory
