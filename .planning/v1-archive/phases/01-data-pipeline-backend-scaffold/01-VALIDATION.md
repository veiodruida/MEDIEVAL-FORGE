---
phase: 1
slug: data-pipeline-backend-scaffold
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-16
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio + httpx |
| **Config file** | `backend/pyproject.toml` `[tool.pytest.ini_options]` — Wave 0 installs |
| **Quick run command** | `py -m pytest backend/tests/ -x -q --ignore=backend/tests/test_generate.py` |
| **Full suite command** | `py -m pytest backend/tests/ -v --tb=short` |
| **Estimated runtime** | ~15 seconds (quick), ~90 seconds (full with slow marks) |

---

## Sampling Rate

- **After every task commit:** Run `py -m pytest backend/tests/ -x -q --ignore=backend/tests/test_generate.py`
- **After every plan wave:** Run `py -m pytest backend/tests/ -v --tb=short`
- **Before `/gsd-verify-work`:** Full suite must be green (including `@pytest.mark.slow`)
- **Max feedback latency:** 15 seconds (quick run)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | PKG-01 | — | N/A | smoke | `medieval-forge --help` exits 0 | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | PKG-02 | — | N/A | unit | `pytest tests/test_cli.py::test_start_no_browser -x` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 1 | PKG-03 | — | N/A | unit | `pytest tests/test_cli.py::test_pid_file -x` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 1 | PKG-05 | — | N/A | unit | `pytest tests/test_packaging.py::test_static_in_wheel -x` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 2 | PROJ-01 | T-PATH | UUID validated before path construction | integration | `pytest tests/test_projects.py::test_create_project -x` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 2 | PROJ-02 | — | N/A | integration | `pytest tests/test_projects.py::test_list_projects -x` | ❌ W0 | ⬜ pending |
| 1-02-03 | 02 | 2 | PROJ-03 | T-PATH | UUID validated before path construction | integration | `pytest tests/test_projects.py::test_get_project -x` | ❌ W0 | ⬜ pending |
| 1-02-04 | 02 | 2 | PROJ-04 | — | N/A | integration | `pytest tests/test_projects.py::test_delete_project -x` | ❌ W0 | ⬜ pending |
| 1-02-05 | 02 | 2 | PROJ-05 | — | N/A | integration | `pytest tests/test_projects.py::test_update_project -x` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 3 | INGEST-01 | T-SSRF | QID format validated as `Q\d+` before request | unit (mocked) | `pytest tests/test_ingest.py::test_wikidata_pagination -x` | ❌ W0 | ⬜ pending |
| 1-03-02 | 03 | 3 | INGEST-02 | T-SSRF | ISO country code validated before request | unit (mocked) | `pytest tests/test_ingest.py::test_osm_fallback -x` | ❌ W0 | ⬜ pending |
| 1-03-03 | 03 | 3 | INGEST-03 | T-PATH | project_id is validated UUID | integration | `pytest tests/test_ingest.py::test_geojson_written -x` | ❌ W0 | ⬜ pending |
| 1-03-04 | 03 | 3 | INGEST-04 | — | N/A | integration | `pytest tests/test_ingest.py::test_sse_stream -x` | ❌ W0 | ⬜ pending |
| 1-04-01 | 04 | 4 | GEN-01 | T-DOS | Status checked != "generating" before re-trigger | integration | `pytest tests/test_generate.py::test_trigger_generation -x` | ❌ W0 | ⬜ pending |
| 1-04-02 | 04 | 4 | GEN-02 | — | N/A | integration (slow) | `pytest tests/test_generate.py::test_png_outputs -x -m slow` | ❌ W0 | ⬜ pending |
| 1-04-03 | 04 | 4 | GEN-03 | T-PATH | project_id UUID validated before FileResponse | integration | `pytest tests/test_generate.py::test_png_fileresponse -x` | ❌ W0 | ⬜ pending |
| 1-04-04 | 04 | 4 | GEN-04 | — | N/A | performance (slow) | `pytest tests/test_generate.py::test_generation_time -x -m slow` | ❌ W0 | ⬜ pending |
| 1-05-01 | 05 | 5 | EXPORT-01 | T-PATH | project_id UUID validated; resolved path within base | integration | `pytest tests/test_export.py::test_zip_download -x` | ❌ W0 | ⬜ pending |
| 1-05-02 | 05 | 5 | EXPORT-02 | — | N/A | integration | `pytest tests/test_export.py::test_zip_contents -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/__init__.py` — marks test directory as package
- [ ] `backend/tests/conftest.py` — shared async fixtures: in-memory SQLite DB, AsyncClient (httpx ASGITransport), project factory helper
- [ ] `backend/tests/test_projects.py` — stubs for PROJ-01..05
- [ ] `backend/tests/test_ingest.py` — stubs for INGEST-01..04 (httpx mocked)
- [ ] `backend/tests/test_generate.py` — stubs for GEN-01..04 (GEN-02/04 marked `@pytest.mark.slow`)
- [ ] `backend/tests/test_export.py` — stubs for EXPORT-01..02
- [ ] `backend/tests/test_cli.py` — stubs for PKG-02..04
- [ ] `backend/tests/test_packaging.py` — stub for PKG-05
- [ ] Framework install: `pip install pytest pytest-asyncio httpx` added to `pyproject.toml` dev dependencies

**conftest.py pattern (from RESEARCH.md):**
```python
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from medieval_forge.main import app
from medieval_forge.database import get_db
from medieval_forge.models import Base

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
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `pip install medieval-forge` from clean virtualenv | PKG-01 | Requires wheel build + clean env | `python -m venv /tmp/test_env && /tmp/test_env/bin/pip install dist/*.whl && /tmp/test_env/bin/medieval-forge --help` |
| Browser opens at localhost:8765 on start | PKG-02 | Requires OS browser interaction | Run `medieval-forge start`, verify browser opens; Ctrl+C to stop |
| `medieval-forge stop` terminates server | PKG-04 | Requires two terminals | Terminal 1: `medieval-forge start --no-browser`; Terminal 2: `medieval-forge stop`; verify Terminal 1 exits |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING (❌ W0) references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s (quick run)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
