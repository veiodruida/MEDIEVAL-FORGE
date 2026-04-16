---
phase: 01
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
  - .gitignore
  - backend/medieval_forge/__init__.py
  - backend/medieval_forge/main.py
  - backend/medieval_forge/database.py
  - backend/medieval_forge/cli.py
  - backend/medieval_forge/models.py
  - backend/medieval_forge/static/.gitkeep
  - backend/tests/__init__.py
  - backend/tests/conftest.py
  - backend/tests/test_cli.py
  - backend/tests/test_packaging.py
  - alembic.ini
  - alembic/env.py
  - alembic/script.py.mako
  - alembic/versions/.gitkeep
autonomous: true
requirements:
  - PKG-01
  - PKG-02
  - PKG-03
  - PKG-04
  - PKG-05

must_haves:
  truths:
    - "py -m pip install -e .[dev] succeeds from repo root"
    - "medieval-forge --help prints click usage"
    - "medieval-forge start --no-browser starts uvicorn on port 8765 and writes PID file"
    - "medieval-forge stop reads PID file and terminates the process cross-platform (Windows + POSIX)"
    - "Alembic env.py uses asyncio.run + run_sync; alembic upgrade head runs against sqlite+aiosqlite URL without errors"
    - "pyproject.toml package-data glob includes static/**/* so wheel ships frontend bundle"
  artifacts:
    - path: "pyproject.toml"
      provides: "package metadata, deps, scripts entry point, package-data glob"
      contains: "medieval-forge = \"medieval_forge.cli:cli\""
    - path: "backend/medieval_forge/cli.py"
      provides: "click group with start/stop commands"
      exports: ["cli", "start", "stop"]
    - path: "backend/medieval_forge/main.py"
      provides: "FastAPI app factory with lifespan, CORS-free, SPA catch-all"
      exports: ["app"]
    - path: "backend/medieval_forge/database.py"
      provides: "async engine + AsyncSessionLocal + get_db dependency"
      exports: ["engine", "AsyncSessionLocal", "get_db", "DATA_DIR"]
    - path: "alembic/env.py"
      provides: "async migration runner using asyncio.run + run_sync"
      contains: "asyncio.run"
    - path: "backend/tests/conftest.py"
      provides: "async test fixtures (in-memory engine + AsyncClient)"
      exports: ["db_session", "client"]
  key_links:
    - from: "pyproject.toml [project.scripts]"
      to: "backend/medieval_forge/cli.py:cli"
      via: "entry point"
      pattern: "medieval-forge\\s*=\\s*\"medieval_forge\\.cli:cli\""
    - from: "backend/medieval_forge/main.py"
      to: "backend/medieval_forge/static/index.html"
      via: "FileResponse SPA catch-all"
      pattern: "FileResponse.*index\\.html"
    - from: "alembic/env.py"
      to: "backend/medieval_forge/models.py"
      via: "Base.metadata import"
      pattern: "from medieval_forge.models import Base"
---

<objective>
Bootstrap the flat monorepo (D-01), the pip-installable Python package, the async FastAPI app shell, the Alembic async migration scaffold, the `medieval-forge` Click CLI (PKG-02..04), and the `static/` package-data glob (PKG-05). After this plan, `py -m pip install -e .[dev]` succeeds and `medieval-forge --help` prints usage. No domain models, no API routes, no frontend yet — those come in plans 02 and 03.

Purpose: Every other plan depends on this scaffold (async engine, lifespan, CLI, package layout, Alembic). Per RESEARCH.md, three details MUST be right from day one or the whole stack fails: aiosqlite pinned `>=0.20,<0.22`, Alembic `env.py` async pattern, Vite `base: "./"` (Vite config is created in Plan 02 alongside the SPA pages, but the `static/` mount + SPA catch-all are wired here so the FastAPI side is ready).

Output: pyproject.toml (root), backend/medieval_forge/{__init__.py, main.py, database.py, cli.py, models.py with empty Base, static/.gitkeep}, alembic/{env.py, script.py.mako, versions/}, alembic.ini, backend/tests/{__init__.py, conftest.py, test_cli.py, test_packaging.py} as Wave 0 stubs.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md
@.planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md
@.planning/phases/01-data-pipeline-backend-scaffold/01-VALIDATION.md
@CLAUDE.md
@inicio/map_generator.py

<interfaces>
<!-- Contracts this plan defines and downstream plans (02, 03, 04, 05) consume -->

backend/medieval_forge/database.py:
```python
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATA_DIR: Path  # = Path.home() / ".medieval-forge"
DB_URL: str     # = f"sqlite+aiosqlite:///{DATA_DIR}/medieval_forge.db"

engine               # AsyncEngine
AsyncSessionLocal    # async_sessionmaker[AsyncSession]

async def get_db() -> AsyncSession:  # FastAPI dependency
    ...
```

backend/medieval_forge/main.py:
```python
from fastapi import FastAPI
app: FastAPI                        # exported, used by uvicorn.run("medieval_forge.main:app", ...)
                                    # Has lifespan that awaits engine connect/dispose.
                                    # Mounts /assets static, registers SPA catch-all.
                                    # API routers are added by plans 02..05 via app.include_router.
```

backend/medieval_forge/models.py (skeleton in this plan; populated in Plan 02):
```python
from sqlalchemy.orm import DeclarativeBase
class Base(DeclarativeBase): ...
```

backend/medieval_forge/cli.py:
```python
import click
@click.group()
def cli(): ...

@cli.command()
@click.option("--port", default=8765)
@click.option("--no-browser", is_flag=True)
def start(port: int, no_browser: bool): ...

@cli.command()
def stop(): ...
```

pyproject.toml [project.scripts]:
  medieval-forge = "medieval_forge.cli:cli"
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Wave 0 — pytest scaffold + conftest + CLI/packaging test stubs</name>
  <files>
    backend/tests/__init__.py,
    backend/tests/conftest.py,
    backend/tests/test_cli.py,
    backend/tests/test_packaging.py
  </files>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-VALIDATION.md
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md (Validation Architecture and conftest.py pattern, lines ~787-870)
    - CLAUDE.md (Backend stack section)
  </read_first>
  <action>
    Create the test directory and Wave 0 stubs that subsequent tasks/plans will fill in.

    1. Create `backend/tests/__init__.py` as an empty file.

    2. Create `backend/tests/conftest.py` with the EXACT async fixture pattern from RESEARCH.md (do not deviate — downstream plans rely on these fixture names):
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
           async def _override():
               yield db_session
           app.dependency_overrides[get_db] = _override
           async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
               yield c
           app.dependency_overrides.clear()
       ```

    3. Create `backend/tests/test_cli.py` with passing stubs (skip-marker pattern so they're discoverable but don't fail before implementation lands in Tasks 4 and 5):
       ```python
       import pytest

       @pytest.mark.skip(reason="Implemented by Plan 01-01 Task 5 (CLI start/stop)")
       def test_start_no_browser():
           pass

       @pytest.mark.skip(reason="Implemented by Plan 01-01 Task 5 (CLI start/stop)")
       def test_pid_file():
           pass

       @pytest.mark.skip(reason="Implemented by Plan 01-01 Task 5 (CLI start/stop)")
       def test_stop_command():
           pass
       ```

    4. Create `backend/tests/test_packaging.py` with passing stub for PKG-05 (filled in by Task 6):
       ```python
       import pytest

       @pytest.mark.skip(reason="Implemented by Plan 01-01 Task 6 (package-data glob)")
       def test_static_in_wheel():
           pass
       ```

    Note: do NOT add pytest config here — that goes in pyproject.toml in Task 2. Do NOT install pytest here — pip install happens after Task 2 writes the dev deps.
  </action>
  <verify>
    <automated>ls backend/tests/__init__.py backend/tests/conftest.py backend/tests/test_cli.py backend/tests/test_packaging.py</automated>
  </verify>
  <done>All four files exist; conftest.py contains the literal strings `pytest_asyncio.fixture`, `ASGITransport(app=app)`, `app.dependency_overrides[get_db]`.</done>
  <acceptance_criteria>
    - backend/tests/__init__.py exists (empty)
    - backend/tests/conftest.py contains "pytest_asyncio.fixture"
    - backend/tests/conftest.py contains "ASGITransport(app=app)"
    - backend/tests/conftest.py contains "app.dependency_overrides[get_db]"
    - backend/tests/conftest.py contains "create_async_engine(\"sqlite+aiosqlite:///:memory:\")"
    - backend/tests/test_cli.py contains exactly three test functions: test_start_no_browser, test_pid_file, test_stop_command
    - backend/tests/test_packaging.py contains test_static_in_wheel
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: pyproject.toml — project metadata, deps, scripts, pytest config, package-data glob</name>
  <files>pyproject.toml, .gitignore</files>
  <behavior>
    - `py -m pip install -e .[dev]` from repo root installs the package and dev tools without resolver errors
    - `medieval-forge` shell command exists on PATH after install
    - aiosqlite is constrained to `>=0.20,<0.22` (RESEARCH.md Pitfall 2 — v0.22 thread-hanging regression)
    - `pytest` discovers `backend/tests/` and runs successfully (zero failures, all skipped is OK at this stage)
    - `static/**/*` glob is registered as package data so the wheel ships frontend bundle
  </behavior>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md (Standard Stack table — exact versions; Pattern 7 — package-data; Pitfall 2 — aiosqlite pin)
    - CLAUDE.md (Technology Stack — version pins)
  </read_first>
  <action>
    Create `pyproject.toml` at repo root (D:/Projetos_Jogo/Medieval_Forge/pyproject.toml). This is the SINGLE source of truth — no setup.py, no setup.cfg.

    Use this exact content (verified versions from RESEARCH.md Standard Stack):

    ```toml
    [build-system]
    requires = ["setuptools>=68", "wheel"]
    build-backend = "setuptools.build_meta"

    [project]
    name = "medieval-forge"
    version = "0.1.0"
    description = "Local web tool for Game Designers that automates creation of historically-accurate medieval maps."
    readme = "README.md"
    requires-python = ">=3.11"
    license = { text = "MIT" }
    authors = [{ name = "Medieval Forge" }]
    dependencies = [
        "fastapi>=0.115,<0.140",
        "uvicorn[standard]>=0.30,<0.50",
        "sqlalchemy>=2.0,<2.1",
        "aiosqlite>=0.20,<0.22",
        "alembic>=1.13,<2.0",
        "pydantic>=2.7,<3.0",
        "httpx>=0.27,<0.30",
        "click>=8.1,<9.0",
        "psutil>=5.9,<7.0",
        "scipy>=1.13,<2.0",
        "shapely>=2.0,<3.0",
        "numpy>=1.26,<3.0",
        "Pillow>=10.0,<13.0",
    ]

    [project.optional-dependencies]
    dev = [
        "pytest>=8.0,<9.0",
        "pytest-asyncio>=0.23,<1.0",
        "build>=1.2,<2.0",
    ]

    [project.scripts]
    medieval-forge = "medieval_forge.cli:cli"

    [tool.setuptools]
    package-dir = { "" = "backend" }

    [tool.setuptools.packages.find]
    where = ["backend"]
    include = ["medieval_forge*"]

    [tool.setuptools.package-data]
    medieval_forge = ["static/**/*", "static/index.html", "lib/*.py"]

    [tool.pytest.ini_options]
    asyncio_mode = "auto"
    testpaths = ["backend/tests"]
    pythonpath = ["backend"]
    markers = [
        "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    ]
    ```

    Notes:
    - `package-dir = { "" = "backend" }` makes setuptools treat `backend/` as the package root; the actual Python package directory is `backend/medieval_forge/`.
    - `psutil` is included for the cross-platform `stop` command (RESEARCH.md Assumption A5 — Windows SIGTERM unreliable).
    - `httpx` is in main deps (used by both ingestion services AND test client).
    - `asyncio_mode = "auto"` so test functions don't need `@pytest.mark.asyncio` decorators.

    Then create / update `.gitignore` (append if exists, create if not):
    ```
    # Python
    __pycache__/
    *.py[cod]
    *.egg-info/
    .pytest_cache/
    build/
    dist/
    *.whl

    # Virtualenv
    .venv/
    venv/

    # Frontend build output (generated by Plan 02; tracked via package data, not git)
    backend/medieval_forge/static/*
    !backend/medieval_forge/static/.gitkeep

    # Frontend deps
    frontend/node_modules/
    frontend/dist/

    # Editor
    .idea/
    .vscode/
    ```

    After writing, install:
    ```bash
    py -m pip install -e .[dev]
    ```

    Verify the install resolved correctly by running `py -m pytest backend/tests/ -q`. Expected: 4 skipped (test_start_no_browser, test_pid_file, test_stop_command, test_static_in_wheel), 0 failed, 0 errors.
  </behavior>
  <action>
    Same as <behavior> spec above — create pyproject.toml exactly as specified, create .gitignore, then run `py -m pip install -e .[dev]` and `py -m pytest backend/tests/ -q`.
  </action>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md
    - CLAUDE.md
  </read_first>
  <verify>
    <automated>py -m pip install -e .[dev] && py -m pytest backend/tests/ -q</automated>
  </verify>
  <done>pip install completes without resolver conflicts; pytest reports "4 skipped" with 0 failed/errors; `medieval-forge --help` prints click usage (this validates the entry point is registered even though the cli module doesn't fully exist yet — at minimum, click reports an error mentioning "cli" if the import works).</done>
  <acceptance_criteria>
    - pyproject.toml exists at repo root
    - pyproject.toml contains "medieval-forge = \"medieval_forge.cli:cli\""
    - pyproject.toml contains "aiosqlite>=0.20,<0.22"
    - pyproject.toml contains "static/**/*"
    - pyproject.toml contains "asyncio_mode = \"auto\""
    - pyproject.toml contains "psutil"
    - .gitignore contains "__pycache__/"
    - .gitignore contains "frontend/node_modules/"
    - .gitignore contains "backend/medieval_forge/static/*"
    - py -m pip install -e .[dev] exits 0
    - py -m pytest backend/tests/ -q exits 0 with output containing "4 skipped"
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Async SQLAlchemy engine + session factory + empty Base + DATA_DIR helper</name>
  <files>
    backend/medieval_forge/__init__.py,
    backend/medieval_forge/database.py,
    backend/medieval_forge/models.py
  </files>
  <behavior>
    - Importing `medieval_forge.database` creates the `~/.medieval-forge/` directory if missing
    - `engine` is an AsyncEngine with URL `sqlite+aiosqlite:///{DATA_DIR}/medieval_forge.db`
    - `get_db` is an async generator yielding an AsyncSession with `expire_on_commit=False`
    - `Base` is a `DeclarativeBase` subclass exported from models.py (empty for now — Plan 02 adds Project)
    - `from medieval_forge.database import engine, AsyncSessionLocal, get_db, DATA_DIR` works
  </behavior>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md (Pattern 1 — FastAPI Async Session)
    - .planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md (D-03 — runtime data location)
  </read_first>
  <action>
    Create `backend/medieval_forge/__init__.py` (empty file with one line: `"""Medieval Forge backend package."""`).

    Create `backend/medieval_forge/database.py` with the exact Pattern 1 from RESEARCH.md:
    ```python
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
    ```

    Create `backend/medieval_forge/models.py` with the empty Base (Plan 02 adds the Project model — keep this file ready):
    ```python
    """SQLAlchemy declarative base. Models added in Plan 01-02."""
    from sqlalchemy.orm import DeclarativeBase


    class Base(DeclarativeBase):
        """Declarative base for all Medieval Forge ORM models."""
        pass
    ```

    Verify by running:
    ```bash
    py -c "from medieval_forge.database import engine, AsyncSessionLocal, get_db, DATA_DIR; print(DATA_DIR); print(engine.url)"
    ```
    Expected output: prints the Path to ~/.medieval-forge and `sqlite+aiosqlite:///...`.
  </behavior>
  <action>
    Implement as specified in <behavior>. After writing, run the import smoke test command listed.
  </action>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md
    - .planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md
  </read_first>
  <verify>
    <automated>py -c "from medieval_forge.database import engine, AsyncSessionLocal, get_db, DATA_DIR; assert str(engine.url).startswith('sqlite+aiosqlite:///'); assert DATA_DIR.name == '.medieval-forge'; print('OK')"</automated>
  </verify>
  <done>Smoke import prints `OK`; ~/.medieval-forge/ directory now exists on disk; engine URL begins with `sqlite+aiosqlite:///`.</done>
  <acceptance_criteria>
    - backend/medieval_forge/__init__.py exists
    - backend/medieval_forge/database.py contains "sqlite+aiosqlite:///"
    - backend/medieval_forge/database.py contains "expire_on_commit=False"
    - backend/medieval_forge/database.py contains "DATA_DIR.mkdir(parents=True, exist_ok=True)"
    - backend/medieval_forge/database.py exports DATA_DIR, engine, AsyncSessionLocal, get_db
    - backend/medieval_forge/models.py contains "class Base(DeclarativeBase)"
    - py -c "from medieval_forge.database import engine, AsyncSessionLocal, get_db, DATA_DIR" exits 0
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 4: Alembic async scaffold (init -t async, env.py wired to Base, alembic.ini DB URL)</name>
  <files>
    alembic.ini,
    alembic/env.py,
    alembic/script.py.mako,
    alembic/versions/.gitkeep
  </files>
  <behavior>
    - `alembic init -t async alembic` creates the async template (DO NOT use the default sync template — RESEARCH.md Pitfall 1 produces empty migrations)
    - `alembic.ini` `sqlalchemy.url` matches `sqlite+aiosqlite:///{HOME}/.medieval-forge/medieval_forge.db`
    - `env.py` imports `medieval_forge.models.Base` and sets `target_metadata = Base.metadata`
    - `alembic upgrade head` runs without error (no migrations exist yet — Plan 02 creates the first one — but the runner must execute cleanly)
    - `alembic revision --autogenerate -m "noop"` succeeds (will produce an empty migration since no models exist yet — that's expected; delete that probe migration after the test)
  </behavior>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md (Pattern 2 — Alembic Async env.py; Pitfall 1 — empty migrations)
  </read_first>
  <action>
    From repo root:

    1. Run: `py -m alembic init -t async alembic`

       This creates `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/`. The `-t async` flag is critical — without it, autogenerate produces empty migrations (Pitfall 1).

    2. Edit `alembic.ini`. Find the line `sqlalchemy.url = driver://user:pass@localhost/dbname` (around line 63) and replace with the literal string (Alembic resolves `~` itself if you use `Path.home()` in env.py, but ini files don't expand `~`; we'll use a relative path here and override programmatically in env.py to use DATA_DIR):
       ```
       sqlalchemy.url = sqlite+aiosqlite:///medieval_forge_alembic.db
       ```
       This default URL will be OVERRIDDEN at runtime by env.py to point at `DATA_DIR / medieval_forge.db`.

    3. Replace `alembic/env.py` with the async pattern wired to our models:
       ```python
       """Async Alembic env for Medieval Forge.

       Critical: uses asyncio.run + run_sync per RESEARCH.md Pitfall 1.
       URL is overridden at runtime to point at DATA_DIR / medieval_forge.db.
       """
       import asyncio
       from logging.config import fileConfig

       from alembic import context
       from sqlalchemy.ext.asyncio import async_engine_from_config
       from sqlalchemy import pool

       from medieval_forge.database import DB_URL
       from medieval_forge.models import Base

       config = context.config
       config.set_main_option("sqlalchemy.url", DB_URL)

       if config.config_file_name is not None:
           fileConfig(config.config_file_name)

       target_metadata = Base.metadata


       def run_migrations_offline() -> None:
           url = config.get_main_option("sqlalchemy.url")
           context.configure(
               url=url,
               target_metadata=target_metadata,
               literal_binds=True,
               dialect_opts={"paramstyle": "named"},
           )
           with context.begin_transaction():
               context.run_migrations()


       def do_run_migrations(connection) -> None:
           context.configure(connection=connection, target_metadata=target_metadata)
           with context.begin_transaction():
               context.run_migrations()


       async def run_migrations_online() -> None:
           connectable = async_engine_from_config(
               config.get_section(config.config_ini_section, {}),
               prefix="sqlalchemy.",
               poolclass=pool.NullPool,
           )
           async with connectable.connect() as connection:
               await connection.run_sync(do_run_migrations)
           await connectable.dispose()


       if context.is_offline_mode():
           run_migrations_offline()
       else:
           asyncio.run(run_migrations_online())
       ```

    4. Create `alembic/versions/.gitkeep` (empty) so git tracks the empty directory.

    5. Verify by running:
       ```bash
       py -m alembic upgrade head
       py -m alembic revision --autogenerate -m "noop_probe"
       ```

       The first command should print "Running upgrade  -> ..." or "Context impl SQLite". The second should create a versions/<hash>_noop_probe.py file. Read that file: if its `upgrade()` body contains only `pass`, the empty-migration scenario is correct (no models defined yet — Plan 02 will create the real first migration). DELETE the noop_probe file after verifying.

       ```bash
       rm alembic/versions/*_noop_probe.py
       ```
  </behavior>
  <action>
    Same as <behavior>. Run the alembic init command from repo root, edit env.py and alembic.ini, then run the verification commands. Delete the noop probe migration before finishing.
  </action>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md
  </read_first>
  <verify>
    <automated>py -m alembic upgrade head 2>&1 | grep -E "(Context impl|Running upgrade|will assume non-transactional)" && ls alembic/env.py alembic/script.py.mako alembic.ini</automated>
  </verify>
  <done>alembic upgrade head runs without traceback; env.py contains `asyncio.run` and `run_sync`; alembic.ini and script.py.mako exist; alembic/versions/ exists (empty save for .gitkeep); no probe migration left behind.</done>
  <acceptance_criteria>
    - alembic.ini exists at repo root
    - alembic/env.py contains "asyncio.run"
    - alembic/env.py contains "run_sync"
    - alembic/env.py contains "from medieval_forge.models import Base"
    - alembic/env.py contains "target_metadata = Base.metadata"
    - alembic/env.py contains "config.set_main_option(\"sqlalchemy.url\", DB_URL)"
    - alembic/script.py.mako exists
    - alembic/versions/.gitkeep exists
    - py -m alembic upgrade head exits 0
    - No file matching alembic/versions/*_noop_probe.py exists after task completes
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 5: Click CLI (start/stop) with cross-platform PID-file termination via psutil</name>
  <files>
    backend/medieval_forge/cli.py,
    backend/tests/test_cli.py
  </files>
  <behavior>
    - `medieval-forge --help` prints click usage with `start` and `stop` subcommands
    - `medieval-forge start --no-browser --port 8765` writes `~/.medieval-forge/medieval_forge.pid` and starts uvicorn on 127.0.0.1:8765
    - `medieval-forge start` (without --no-browser) opens a browser tab to http://localhost:8765 (after a short delay)
    - `medieval-forge stop` reads the PID file, terminates the process via `psutil.Process(pid).terminate()` (cross-platform; addresses RESEARCH.md Assumption A5 Windows SIGTERM concern), and removes the PID file
    - If the PID file is missing, `medieval-forge stop` prints "No running server found." and exits 0
    - Tests in `test_cli.py` exercise PID file write, start command argument plumbing (without actually launching uvicorn), and stop command behavior
  </behavior>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md (Pattern 8 — CLI Entry Point; Assumption A5 — Windows SIGTERM)
    - .planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md (specifics — port 8765, PID file location)
    - backend/tests/conftest.py
    - backend/tests/test_cli.py (current stubs from Task 1)
  </read_first>
  <action>
    Create `backend/medieval_forge/cli.py`:
    ```python
    """Medieval Forge command-line interface.

    Per PKG-02..04: start/stop the FastAPI server with optional browser open.
    Uses psutil for cross-platform process termination (RESEARCH.md Assumption A5).
    """
    from __future__ import annotations

    import os
    import threading
    import webbrowser
    from pathlib import Path

    import click
    import psutil
    import uvicorn

    from .database import DATA_DIR

    PID_FILE: Path = DATA_DIR / "medieval_forge.pid"


    @click.group()
    def cli() -> None:
        """Medieval Forge — local map authoring tool."""


    @cli.command()
    @click.option("--port", default=8765, show_default=True, help="Port to listen on.")
    @click.option("--no-browser", is_flag=True, help="Skip opening browser tab.")
    def start(port: int, no_browser: bool) -> None:
        """Start the Medieval Forge FastAPI server."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()))

        if not no_browser:
            threading.Timer(
                1.5, lambda: webbrowser.open(f"http://localhost:{port}")
            ).start()

        try:
            uvicorn.run(
                "medieval_forge.main:app",
                host="127.0.0.1",
                port=port,
                log_level="info",
            )
        finally:
            if PID_FILE.exists():
                PID_FILE.unlink(missing_ok=True)


    @cli.command()
    def stop() -> None:
        """Stop the running Medieval Forge server (reads PID file)."""
        if not PID_FILE.exists():
            click.echo("No running server found.")
            return
        try:
            pid = int(PID_FILE.read_text().strip())
        except ValueError:
            click.echo("PID file corrupt; removing.")
            PID_FILE.unlink(missing_ok=True)
            return

        try:
            proc = psutil.Process(pid)
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                proc.kill()
            click.echo(f"Stopped process {pid}")
        except psutil.NoSuchProcess:
            click.echo(f"Process {pid} not running; cleaning PID file.")
        finally:
            PID_FILE.unlink(missing_ok=True)


    if __name__ == "__main__":
        cli()
    ```

    Replace `backend/tests/test_cli.py` (remove all `@pytest.mark.skip` decorators from Task 1's stubs and implement real tests):
    ```python
    """Tests for medieval_forge.cli."""
    from __future__ import annotations

    import os
    from pathlib import Path
    from unittest.mock import patch

    import pytest
    from click.testing import CliRunner

    from medieval_forge.cli import PID_FILE, cli


    def test_help_lists_start_and_stop():
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "start" in result.output
        assert "stop" in result.output


    def test_start_no_browser(tmp_path, monkeypatch):
        """`start --no-browser --port N`: webbrowser.open MUST NOT be called; uvicorn.run MUST be called."""
        # Redirect PID_FILE to tmp_path so the test doesn't pollute ~/.medieval-forge
        fake_pid = tmp_path / "medieval_forge.pid"
        monkeypatch.setattr("medieval_forge.cli.PID_FILE", fake_pid)
        with patch("medieval_forge.cli.uvicorn.run") as mock_run, patch(
            "medieval_forge.cli.webbrowser.open"
        ) as mock_browser:
            runner = CliRunner()
            result = runner.invoke(cli, ["start", "--no-browser", "--port", "9999"])
            assert result.exit_code == 0, result.output
            mock_run.assert_called_once()
            kwargs = mock_run.call_args.kwargs
            assert kwargs["host"] == "127.0.0.1"
            assert kwargs["port"] == 9999
            mock_browser.assert_not_called()


    def test_pid_file(tmp_path, monkeypatch):
        """`start` writes the current PID to PID_FILE before invoking uvicorn."""
        fake_pid = tmp_path / "medieval_forge.pid"
        monkeypatch.setattr("medieval_forge.cli.PID_FILE", fake_pid)
        with patch("medieval_forge.cli.uvicorn.run"):
            runner = CliRunner()
            result = runner.invoke(cli, ["start", "--no-browser"])
            assert result.exit_code == 0, result.output
        # After uvicorn.run is mocked (returns immediately), the finally clause
        # unlinks the PID file. To assert the write happened, capture it from
        # the mock context. Simpler: re-invoke with a capturing patch.
        captured = {}

        def fake_run(*args, **kwargs):
            captured["pid"] = fake_pid.read_text().strip()

        with patch("medieval_forge.cli.uvicorn.run", side_effect=fake_run):
            runner = CliRunner()
            result = runner.invoke(cli, ["start", "--no-browser"])
            assert result.exit_code == 0
        assert captured["pid"] == str(os.getpid())


    def test_stop_command_no_pid_file(tmp_path, monkeypatch):
        """`stop` with no PID file prints helpful message and exits 0."""
        fake_pid = tmp_path / "medieval_forge.pid"
        monkeypatch.setattr("medieval_forge.cli.PID_FILE", fake_pid)
        runner = CliRunner()
        result = runner.invoke(cli, ["stop"])
        assert result.exit_code == 0
        assert "No running server found" in result.output


    def test_stop_command_terminates_process(tmp_path, monkeypatch):
        """`stop` calls psutil.Process(pid).terminate() and unlinks PID file."""
        fake_pid = tmp_path / "medieval_forge.pid"
        fake_pid.write_text("12345")
        monkeypatch.setattr("medieval_forge.cli.PID_FILE", fake_pid)

        with patch("medieval_forge.cli.psutil.Process") as mock_proc_cls:
            mock_proc = mock_proc_cls.return_value
            runner = CliRunner()
            result = runner.invoke(cli, ["stop"])
            assert result.exit_code == 0
            mock_proc_cls.assert_called_once_with(12345)
            mock_proc.terminate.assert_called_once()
        assert not fake_pid.exists()
    ```

    Note: the original `test_stop_command` stub from Task 1 must be removed and replaced with `test_stop_command_no_pid_file` and `test_stop_command_terminates_process`.

    Run: `py -m pytest backend/tests/test_cli.py -x -q`

    Expected: 5 passed, 0 failed. Then run `medieval-forge --help` from a shell to confirm the CLI entry point resolves and prints usage.
  </action>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md
    - .planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md
    - backend/tests/conftest.py
    - backend/tests/test_cli.py
  </read_first>
  <verify>
    <automated>py -m pytest backend/tests/test_cli.py -x -q && medieval-forge --help</automated>
  </verify>
  <done>5 cli tests pass; `medieval-forge --help` prints click usage listing both `start` and `stop` subcommands; PID_FILE constant resolves to `~/.medieval-forge/medieval_forge.pid`.</done>
  <acceptance_criteria>
    - backend/medieval_forge/cli.py contains "@click.group()"
    - backend/medieval_forge/cli.py contains "psutil.Process(pid).terminate" OR "proc.terminate()"
    - backend/medieval_forge/cli.py contains "PID_FILE.write_text(str(os.getpid()))"
    - backend/medieval_forge/cli.py contains "uvicorn.run("
    - backend/medieval_forge/cli.py contains "webbrowser.open"
    - backend/tests/test_cli.py contains test_help_lists_start_and_stop, test_start_no_browser, test_pid_file, test_stop_command_no_pid_file, test_stop_command_terminates_process
    - py -m pytest backend/tests/test_cli.py -x -q exits 0 with "5 passed"
    - `medieval-forge --help` prints output containing both "start" and "stop"
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 6: FastAPI app shell (lifespan, /assets mount, SPA catch-all) + static/.gitkeep + packaging test</name>
  <files>
    backend/medieval_forge/main.py,
    backend/medieval_forge/static/.gitkeep,
    backend/tests/test_packaging.py
  </files>
  <behavior>
    - `medieval_forge.main.app` is a FastAPI instance with a lifespan that opens/disposes the engine
    - `app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"))` is registered (handles JS/CSS bundles)
    - A catch-all route `@app.get("/{full_path:path}")` returns `FileResponse(STATIC_DIR / "index.html")` IF the file exists, otherwise returns a placeholder JSON `{"detail": "Frontend not built yet. Run `npm run build` from frontend/."}` with 503 status
    - API routers are registered in plans 02..05 BEFORE the catch-all (catch-all must be the LAST registration — RESEARCH.md Pitfall 8)
    - `backend/medieval_forge/static/.gitkeep` exists so the directory is tracked even before frontend build
    - `test_packaging.py::test_static_in_wheel` builds a wheel with `py -m build` and verifies `static/` directory was included as package data
  </behavior>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md (Pattern 1 — lifespan; Pattern 5 — SPA fallback; Pitfall 3 — deep links 404; Pitfall 8 — mount order)
    - backend/medieval_forge/database.py
    - backend/tests/test_packaging.py (current stub from Task 1)
  </read_first>
  <action>
    1. Create `backend/medieval_forge/static/.gitkeep` (empty file).

    2. Create `backend/medieval_forge/main.py`:
       ```python
       """FastAPI application factory for Medieval Forge.

       Lifespan opens the async engine; SPA catch-all handles React Router deep links.
       Per RESEARCH.md Pitfall 8: API routers MUST be registered before the catch-all.
       Routers are added by plans 01-02 (projects), 01-03 (ingest), 01-04 (generate),
       and 01-05 (export) via app.include_router(...).
       """
       from __future__ import annotations

       from contextlib import asynccontextmanager
       from pathlib import Path

       from fastapi import FastAPI
       from fastapi.responses import FileResponse, JSONResponse
       from fastapi.staticfiles import StaticFiles

       from .database import engine

       STATIC_DIR: Path = Path(__file__).parent / "static"
       INDEX_HTML: Path = STATIC_DIR / "index.html"
       ASSETS_DIR: Path = STATIC_DIR / "assets"


       @asynccontextmanager
       async def lifespan(app: FastAPI):
           # Startup: validate DB connectivity (tables come from Alembic).
           async with engine.begin() as conn:
               # No-op: just exercises the connection so a broken URL fails fast.
               pass
           yield
           # Shutdown: close pool.
           await engine.dispose()


       app = FastAPI(
           title="Medieval Forge",
           version="0.1.0",
           lifespan=lifespan,
       )

       # API routers will be registered here by plans 02..05:
       #   from .api.projects import router as projects_router
       #   app.include_router(projects_router, prefix="/api")
       #   ... etc.
       # IMPORTANT: register them BEFORE the SPA catch-all below.

       # /assets/* — JS/CSS bundles. Only mount if directory exists (frontend may
       # not be built yet during early development).
       if ASSETS_DIR.exists():
           app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


       @app.get("/{full_path:path}")
       async def spa_catch_all(full_path: str):
           """Serve React SPA index.html for all unmatched paths.

           Per Pitfall 3: required for React Router deep-link refresh to work.
           Returns a 503 placeholder if frontend has not been built yet.
           """
           if INDEX_HTML.exists():
               return FileResponse(INDEX_HTML)
           return JSONResponse(
               status_code=503,
               content={
                   "detail": "Frontend not built yet. Run `npm run build` from frontend/."
               },
           )
       ```

    3. Replace `backend/tests/test_packaging.py` (remove `@pytest.mark.skip`):
       ```python
       """Tests for PKG-05: frontend bundle is included as package data."""
       from __future__ import annotations

       import subprocess
       import sys
       import zipfile
       from pathlib import Path

       import pytest

       REPO_ROOT = Path(__file__).resolve().parents[2]


       def test_pyproject_declares_static_glob():
           """pyproject.toml must declare static/**/* in tool.setuptools.package-data."""
           pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
           assert "static/**/*" in pyproject
           assert "[tool.setuptools.package-data]" in pyproject


       @pytest.mark.slow
       def test_static_in_wheel(tmp_path):
           """Building the wheel produces an artifact whose RECORD includes static/."""
           # Seed a marker file so static/ has at least one entry to ship.
           static_marker = REPO_ROOT / "backend" / "medieval_forge" / "static" / "WHEEL_TEST_MARKER"
           static_marker.write_text("ok", encoding="utf-8")
           try:
               subprocess.run(
                   [sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path)],
                   cwd=REPO_ROOT,
                   check=True,
                   capture_output=True,
               )
               wheels = list(tmp_path.glob("*.whl"))
               assert wheels, "no wheel produced"
               with zipfile.ZipFile(wheels[0]) as zf:
                   names = zf.namelist()
               assert any(
                   "medieval_forge/static/WHEEL_TEST_MARKER" in n for n in names
               ), f"static/ not packaged. wheel contents: {names[:30]}"
           finally:
               static_marker.unlink(missing_ok=True)
       ```

    4. Run:
       ```bash
       py -m pytest backend/tests/test_packaging.py::test_pyproject_declares_static_glob -x -q
       py -m pytest backend/tests/test_packaging.py::test_static_in_wheel -x -q -m slow
       ```

       The slow test builds a wheel and inspects it; takes ~10-20s.

    5. Smoke-test the FastAPI app:
       ```bash
       py -c "from medieval_forge.main import app; print(type(app).__name__); print([r.path for r in app.routes])"
       ```
       Expected output: `FastAPI` and a list containing `/{full_path:path}`.
  </action>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md
    - backend/medieval_forge/database.py
    - backend/tests/test_packaging.py
  </read_first>
  <verify>
    <automated>py -m pytest backend/tests/test_packaging.py -x -q && py -c "from medieval_forge.main import app; assert any(r.path == '/{full_path:path}' for r in app.routes), 'spa catch-all missing'"</automated>
  </verify>
  <done>
    test_pyproject_declares_static_glob passes. test_static_in_wheel (slow) passes when run with -m slow. FastAPI smoke import succeeds and lists the SPA catch-all route. backend/medieval_forge/static/.gitkeep is committed.
  </done>
  <acceptance_criteria>
    - backend/medieval_forge/main.py contains "lifespan="
    - backend/medieval_forge/main.py contains "app = FastAPI("
    - backend/medieval_forge/main.py contains "FileResponse(INDEX_HTML)"
    - backend/medieval_forge/main.py contains "@app.get(\"/{full_path:path}\")"
    - backend/medieval_forge/main.py contains "ASSETS_DIR.exists()" (conditional mount)
    - backend/medieval_forge/static/.gitkeep exists
    - backend/tests/test_packaging.py contains test_pyproject_declares_static_glob and test_static_in_wheel
    - py -m pytest backend/tests/test_packaging.py::test_pyproject_declares_static_glob -x -q exits 0
    - py -c "from medieval_forge.main import app" exits 0
  </acceptance_criteria>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| OS shell → CLI | `medieval-forge start/stop` accepts CLI flags; trusted (user-controlled local invocation) |
| Browser → FastAPI catch-all | All non-API paths fall through to the SPA; the catch-all only serves a static file or a 503 JSON; no path traversal possible because FileResponse is bound to INDEX_HTML constant |
| Filesystem → DATA_DIR | `~/.medieval-forge/` is created at module import; only writes within the user's home directory |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-01 | Tampering | spa_catch_all route | mitigate | `full_path` argument is IGNORED by the handler — it always returns FileResponse(INDEX_HTML) (a constant Path). No path traversal vector. |
| T-01-02 | Tampering | PID file (`~/.medieval-forge/medieval_forge.pid`) | mitigate | `stop` validates PID is a valid integer before passing to psutil.Process; psutil.Process raises NoSuchProcess on bogus PID — caught and PID file removed |
| T-01-03 | Denial of Service | `start` command (no port reuse check) | accept | Local single-user tool; if port is in use, uvicorn fails fast with a clear error. Acceptable. |
| T-01-04 | Information Disclosure | FastAPI default exception handlers (stack traces) | mitigate | FastAPI default in production mode returns 500 JSON without traceback. No `debug=True` flag set on app constructor. ASVS V7. |
| T-01-05 | Tampering | `static/**/*` package-data glob (could include unintended files) | mitigate | Glob is scoped to `medieval_forge/static/` — Vite build is the only writer. `.gitignore` excludes `static/*` (only .gitkeep tracked) so dev artifacts never sneak in. |
</threat_model>

<verification>
After all 6 tasks complete, run the per-wave verification command from VALIDATION.md:

```bash
py -m pytest backend/tests/ -v --tb=short
```

Expected: 9 passing tests (5 cli + 1 packaging-pyproject + ~3 from skipped stubs that remain skipped because Plan 02 hasn't run yet — the Plan 02..05 stubs from later plans don't exist yet, so this number reflects ONLY this plan's tests). Slow-marked test_static_in_wheel passes when explicitly run with `-m slow`.

Smoke checks (manual but trivial):
- `medieval-forge --help` — prints click usage with start + stop
- `py -c "from medieval_forge.main import app"` — no traceback
- `py -m alembic upgrade head` — runs without error (no migrations to apply yet)
- `ls ~/.medieval-forge/` — directory exists (created on first import of database.py)
</verification>

<success_criteria>
- `py -m pip install -e .[dev]` succeeds from clean repo (idempotent on rerun).
- `medieval-forge --help` prints `Usage: medieval-forge [OPTIONS] COMMAND [ARGS]...` and lists `start` and `stop`.
- `py -m pytest backend/tests/test_cli.py backend/tests/test_packaging.py -x -q` exits 0 with 6 passed (5 cli + 1 packaging non-slow).
- `py -m alembic upgrade head` runs cleanly.
- `~/.medieval-forge/` directory exists on disk after any package import.
- pyproject.toml declares all stack-correction pins from CLAUDE.md (aiosqlite >=0.20,<0.22).
- FastAPI app is importable; SPA catch-all route is registered; lifespan is wired.
- backend/medieval_forge/static/.gitkeep tracked so the package directory is preserved before any frontend build.
</success_criteria>

<output>
After completion, create `.planning/phases/01-data-pipeline-backend-scaffold/01-01-SUMMARY.md` per the standard summary template. Note any deviations (e.g., if Windows psutil behaved differently than expected).
</output>
