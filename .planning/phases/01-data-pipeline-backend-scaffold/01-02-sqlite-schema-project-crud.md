---
phase: 01
plan: 02
type: execute
wave: 2
depends_on:
  - 01-01
files_modified:
  - backend/medieval_forge/models.py
  - backend/medieval_forge/schemas.py
  - backend/medieval_forge/api/__init__.py
  - backend/medieval_forge/api/projects.py
  - backend/medieval_forge/services/__init__.py
  - backend/medieval_forge/services/paths.py
  - backend/medieval_forge/main.py
  - alembic/versions/0001_create_projects.py
  - backend/tests/test_projects.py
  - frontend/package.json
  - frontend/vite.config.ts
  - frontend/tsconfig.json
  - frontend/tsconfig.node.json
  - frontend/index.html
  - frontend/src/main.tsx
  - frontend/src/App.tsx
  - frontend/src/index.css
  - frontend/src/api/client.ts
  - frontend/src/pages/ProjectList.tsx
  - frontend/src/pages/ProjectNew.tsx
  - frontend/src/pages/ProjectDetail.tsx
autonomous: true
requirements:
  - PROJ-01
  - PROJ-02
  - PROJ-03
  - PROJ-04
  - PROJ-05

must_haves:
  truths:
    - "Project model has id (UUID string PK), name, country_qid, period_start/end, bbox_*, generator_config (JSON), status, created_at, updated_at (D-06)"
    - "POST /api/projects creates a row and ALSO creates ~/.medieval-forge/projects/{uuid}/{raw,generated,exports}/ folders (D-07)"
    - "GET /api/projects returns a list of project DTOs"
    - "GET /api/projects/{id} returns a single project; 404 on unknown UUID; 400 on malformed UUID (T-PATH mitigation)"
    - "PATCH /api/projects/{id} updates name, period, bbox, generator_config; returns 200 with updated DTO"
    - "DELETE /api/projects/{id} removes the row AND the project folder; idempotent (404 on second call is acceptable, but folder removal MUST not fail if folder absent)"
    - "Vite config uses base: \"./\" and outDir: \"../backend/medieval_forge/static\" (D-02)"
    - "frontend/src/index.css imports @radix-ui/themes/styles.css BEFORE tailwindcss (RESEARCH Pitfall 7)"
    - "Three React pages render: /projects (list+create button), /projects/new (form), /projects/:id (detail with placeholder Ingest/Generate/Export buttons that Plans 03/04/05 will wire)"
  artifacts:
    - path: "backend/medieval_forge/models.py"
      provides: "Project SQLAlchemy model with full column set"
      contains: "class Project(Base)"
    - path: "backend/medieval_forge/schemas.py"
      provides: "Pydantic v2 ProjectCreate, ProjectUpdate, ProjectResponse"
      exports: ["ProjectCreate", "ProjectUpdate", "ProjectResponse"]
    - path: "backend/medieval_forge/api/projects.py"
      provides: "5 CRUD routes mounted at /api/projects"
      exports: ["router"]
    - path: "backend/medieval_forge/services/paths.py"
      provides: "validated project_dir(uuid) helper enforcing T-PATH boundary"
      exports: ["project_dir", "ensure_project_dirs", "is_valid_uuid"]
    - path: "alembic/versions/0001_create_projects.py"
      provides: "initial migration creating projects table"
      contains: "op.create_table('projects'"
    - path: "frontend/vite.config.ts"
      provides: "Vite 6 config with base './' and outDir into backend/medieval_forge/static"
      contains: "base: './'"
    - path: "frontend/src/index.css"
      provides: "Tailwind v4 + Radix Themes CSS in correct import order"
      contains: "@import \"@radix-ui/themes/styles.css\""
    - path: "frontend/src/pages/ProjectList.tsx"
      provides: "list view backed by TanStack Query"
      exports: ["ProjectList"]
    - path: "frontend/src/pages/ProjectNew.tsx"
      provides: "create form posting to /api/projects"
      exports: ["ProjectNew"]
    - path: "frontend/src/pages/ProjectDetail.tsx"
      provides: "detail view + placeholder action buttons"
      exports: ["ProjectDetail"]
  key_links:
    - from: "backend/medieval_forge/api/projects.py"
      to: "backend/medieval_forge/services/paths.py"
      via: "is_valid_uuid + project_dir for T-PATH mitigation"
      pattern: "is_valid_uuid\\(.*project_id.*\\)"
    - from: "backend/medieval_forge/main.py"
      to: "backend/medieval_forge/api/projects.py"
      via: "app.include_router(projects_router, prefix=\"/api\")"
      pattern: "include_router\\(projects.*prefix=\"/api\""
    - from: "frontend/src/api/client.ts"
      to: "/api/projects"
      via: "TanStack Query useQuery + useMutation hooks"
      pattern: "fetch\\(.*api/projects"
    - from: "frontend/vite.config.ts outDir"
      to: "backend/medieval_forge/static/"
      via: "Vite build pipeline"
      pattern: "outDir:.*backend/medieval_forge/static"
---

<objective>
Build the Project domain end-to-end: SQLAlchemy model → Alembic migration → Pydantic schemas → 5 CRUD FastAPI routes → minimal React SPA (3 pages: list, new, detail) wired with TanStack Query. After this plan, a Game Designer can create, list, open, update, and delete projects via the UI in the browser. Per-project folders (`raw/`, `generated/`, `exports/`) are created on POST and removed on DELETE.

Purpose: PROJ-01..05 are the foundation every other Phase 1 capability builds on (Plans 03, 04, 05 all act on a project_id). The frontend SPA scaffold also lands here so the user-facing surface exists from Wave 2 onward; later plans only ADD components/buttons rather than bootstrapping React.

Output: backend/medieval_forge/{models.py expanded, schemas.py, api/projects.py, services/paths.py, main.py wires router}, alembic/versions/0001_create_projects.py, backend/tests/test_projects.py (real tests, not stubs), full frontend/ directory with Vite 6 + React 19 + Tailwind v4 + Radix Themes + TanStack Query + react-router-dom 7, three pages, npm-installable.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md
@.planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md
@.planning/phases/01-data-pipeline-backend-scaffold/01-VALIDATION.md
@.planning/phases/01-data-pipeline-backend-scaffold/01-01-project-scaffold-packaging.md
@CLAUDE.md
@backend/medieval_forge/database.py
@backend/medieval_forge/main.py
@backend/medieval_forge/models.py

<interfaces>
<!-- Contracts THIS plan defines and downstream plans (03, 04, 05) consume -->

backend/medieval_forge/models.py:
```python
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str]                  # UUID4 string, primary key (D-06)
    name: Mapped[str]
    country_qid: Mapped[str]         # e.g. "Q29" (Spain)
    period_start: Mapped[int]        # year, e.g. 868
    period_end: Mapped[int]          # year, e.g. 1492
    bbox_lon_min: Mapped[float | None]
    bbox_lon_max: Mapped[float | None]
    bbox_lat_min: Mapped[float | None]
    bbox_lat_max: Mapped[float | None]
    generator_config: Mapped[dict | None]   # JSON
    status: Mapped[str]              # "created" | "ingested" | "generated" | "exported" (Plans 03/04/05 update)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

backend/medieval_forge/services/paths.py:
```python
import re, uuid
from pathlib import Path
from medieval_forge.database import DATA_DIR

UUID_RE: re.Pattern  # validates v4-shaped UUIDs

def is_valid_uuid(value: str) -> bool: ...                # T-PATH guard
def project_dir(project_id: str) -> Path: ...             # raises ValueError on bad UUID; resolved path WITHIN DATA_DIR/projects/
def ensure_project_dirs(project_id: str) -> dict[str, Path]: ...  # returns {"root":..., "raw":..., "generated":..., "exports":...}
```

backend/medieval_forge/schemas.py (Pydantic v2):
```python
class ProjectCreate(BaseModel):
    name: str
    country_qid: str       # validator: matches r"^Q\d+$"
    period_start: int
    period_end: int
    bbox_lon_min: float | None = None
    bbox_lon_max: float | None = None
    bbox_lat_min: float | None = None
    bbox_lat_max: float | None = None
    generator_config: dict | None = None

class ProjectUpdate(BaseModel):    # all fields Optional
    ...

class ProjectResponse(BaseModel):
    id: str
    name: str
    country_qid: str
    period_start: int
    period_end: int
    bbox_lon_min: float | None
    bbox_lon_max: float | None
    bbox_lat_min: float | None
    bbox_lat_max: float | None
    generator_config: dict | None
    status: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
```

backend/medieval_forge/api/projects.py:
```python
router = APIRouter(prefix="/projects", tags=["projects"])

@router.post("", status_code=201, response_model=ProjectResponse)
@router.get("", response_model=list[ProjectResponse])
@router.get("/{project_id}", response_model=ProjectResponse)
@router.patch("/{project_id}", response_model=ProjectResponse)
@router.delete("/{project_id}", status_code=204)
```

frontend/src/api/client.ts: TanStack Query hooks consumed by all pages and by Plans 03/04/05:
- `useProjects()` → list
- `useProject(id)` → detail
- `useCreateProject()` → mutation
- `useUpdateProject()` → mutation
- `useDeleteProject()` → mutation
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Wave 0 — test_projects.py stubs (PROJ-01..05) using existing conftest fixtures</name>
  <files>backend/tests/test_projects.py</files>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-VALIDATION.md
    - backend/tests/conftest.py
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md (Validation Architecture)
  </read_first>
  <action>
    Create `backend/tests/test_projects.py` with passing-stub form. These will be filled in by Task 4. The point of this Wave 0 task is to register the test names so the per-task verify commands in this plan have something to call against without "test not found" errors.

    ```python
    """Tests for PROJ-01..05 — project CRUD endpoints.

    Stubs created in Wave 0 of Plan 01-02. Implemented in Task 4.
    """
    import pytest


    @pytest.mark.skip(reason="Implemented by Plan 01-02 Task 4")
    async def test_create_project(client):
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-02 Task 4")
    async def test_list_projects(client):
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-02 Task 4")
    async def test_get_project(client):
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-02 Task 4")
    async def test_get_project_invalid_uuid_returns_400(client):
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-02 Task 4")
    async def test_get_project_not_found_returns_404(client):
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-02 Task 4")
    async def test_update_project(client):
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-02 Task 4")
    async def test_delete_project(client):
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-02 Task 4")
    async def test_create_project_creates_folders(client, tmp_path):
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-02 Task 4")
    async def test_country_qid_validation_rejects_bad_format(client):
        pass
    ```
  </action>
  <verify>
    <automated>py -m pytest backend/tests/test_projects.py -q</automated>
  </verify>
  <done>9 tests collected, all skipped, 0 errors.</done>
  <acceptance_criteria>
    - backend/tests/test_projects.py exists
    - Contains exactly 9 test functions (test_create_project, test_list_projects, test_get_project, test_get_project_invalid_uuid_returns_400, test_get_project_not_found_returns_404, test_update_project, test_delete_project, test_create_project_creates_folders, test_country_qid_validation_rejects_bad_format)
    - py -m pytest backend/tests/test_projects.py -q exits 0 with "9 skipped" in output
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Project model + Alembic initial migration + paths.py (T-PATH guard) + schemas</name>
  <files>
    backend/medieval_forge/models.py,
    backend/medieval_forge/schemas.py,
    backend/medieval_forge/services/__init__.py,
    backend/medieval_forge/services/paths.py,
    alembic/versions/0001_create_projects.py
  </files>
  <behavior>
    - `from medieval_forge.models import Project, Base` works; Project has all 13 columns from <interfaces>
    - `from medieval_forge.schemas import ProjectCreate, ProjectUpdate, ProjectResponse` works
    - `ProjectCreate(country_qid="Q29", ...)` validates; `country_qid="spain"` raises ValidationError
    - `is_valid_uuid("550e8400-e29b-41d4-a716-446655440000")` returns True; `is_valid_uuid("../etc/passwd")` returns False (T-PATH mitigation)
    - `project_dir(uuid)` returns `DATA_DIR / "projects" / uuid` and verifies `.resolve().is_relative_to(DATA_DIR / "projects")`; raises ValueError on traversal attempt
    - `ensure_project_dirs(uuid)` creates `root/raw`, `root/generated`, `root/exports` (mkdir parents=True, exist_ok=True) and returns dict of paths
    - `py -m alembic upgrade head` applies migration `0001_create_projects` and creates the `projects` table in `~/.medieval-forge/medieval_forge.db`
  </behavior>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md (SQLAlchemy Project Model code example, lines ~640-665; Pattern 2 — Alembic; Security Domain — T-PATH)
    - .planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md (D-06, D-07)
    - backend/medieval_forge/models.py (current empty Base from Plan 01-01)
    - backend/medieval_forge/database.py
    - alembic/env.py
  </read_first>
  <action>
    1. REPLACE `backend/medieval_forge/models.py` with the full Project model:
       ```python
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
       ```

    2. CREATE `backend/medieval_forge/schemas.py`:
       ```python
       """Pydantic v2 request/response schemas for the projects API."""
       from __future__ import annotations

       import re
       from datetime import datetime
       from typing import Any

       from pydantic import BaseModel, ConfigDict, Field, field_validator

       _QID_RE = re.compile(r"^Q\d+$")


       class _CountryQidValidator:
           @field_validator("country_qid")
           @classmethod
           def _validate_qid(cls, v: str) -> str:
               if not _QID_RE.match(v):
                   raise ValueError("country_qid must match pattern ^Q\\d+$")
               return v


       class ProjectCreate(_CountryQidValidator, BaseModel):
           name: str = Field(..., min_length=1, max_length=255)
           country_qid: str
           period_start: int
           period_end: int
           bbox_lon_min: float | None = None
           bbox_lon_max: float | None = None
           bbox_lat_min: float | None = None
           bbox_lat_max: float | None = None
           generator_config: dict[str, Any] | None = None


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
           def _validate_qid_optional(cls, v: str | None) -> str | None:
               if v is not None and not _QID_RE.match(v):
                   raise ValueError("country_qid must match pattern ^Q\\d+$")
               return v


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
       ```

    3. CREATE `backend/medieval_forge/services/__init__.py` (empty: `"""Medieval Forge service layer."""`).

    4. CREATE `backend/medieval_forge/services/paths.py` (T-PATH boundary enforcement):
       ```python
       """Filesystem path helpers + T-PATH boundary enforcement.

       All filesystem access for project data goes through these helpers.
       Per RESEARCH.md Security Domain: validate UUID format AND verify the
       resolved path is within DATA_DIR/projects/.
       """
       from __future__ import annotations

       import re
       import uuid as _uuid_mod
       from pathlib import Path

       from medieval_forge.database import DATA_DIR

       PROJECTS_ROOT: Path = DATA_DIR / "projects"

       # Strict UUID v4 lowercase pattern (matches uuid.UUID(version=4) string form).
       _UUID_RE = re.compile(
           r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
       )


       def is_valid_uuid(value: str) -> bool:
           """Return True iff `value` is a syntactically valid UUID string."""
           if not isinstance(value, str) or not _UUID_RE.match(value):
               return False
           try:
               _uuid_mod.UUID(value)
           except (ValueError, TypeError):
               return False
           return True


       def project_dir(project_id: str) -> Path:
           """Return the project's root directory after T-PATH validation.

           Raises:
               ValueError: if project_id is not a valid UUID OR if the resolved
                           path escapes PROJECTS_ROOT.
           """
           if not is_valid_uuid(project_id):
               raise ValueError(f"invalid project_id: {project_id!r}")

           PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
           candidate = (PROJECTS_ROOT / project_id).resolve()
           root = PROJECTS_ROOT.resolve()
           # Python 3.9+: is_relative_to handles edge cases like trailing separators.
           if not candidate.is_relative_to(root):
               raise ValueError(f"project_id resolves outside PROJECTS_ROOT: {project_id!r}")
           return candidate


       def ensure_project_dirs(project_id: str) -> dict[str, Path]:
           """Create raw/, generated/, exports/ subfolders for the project."""
           root = project_dir(project_id)
           subdirs = {
               "root": root,
               "raw": root / "raw",
               "generated": root / "generated",
               "exports": root / "exports",
           }
           for p in subdirs.values():
               p.mkdir(parents=True, exist_ok=True)
           return subdirs
       ```

    5. CREATE `alembic/versions/0001_create_projects.py` (hand-write rather than autogenerate so the migration is deterministic):
       ```python
       """create projects table

       Revision ID: 0001
       Revises:
       Create Date: 2026-04-16
       """
       from __future__ import annotations

       import sqlalchemy as sa
       from alembic import op

       revision: str = "0001"
       down_revision: str | None = None
       branch_labels = None
       depends_on = None


       def upgrade() -> None:
           op.create_table(
               "projects",
               sa.Column("id", sa.String(length=36), primary_key=True),
               sa.Column("name", sa.String(length=255), nullable=False),
               sa.Column("country_qid", sa.String(length=20), nullable=False),
               sa.Column("period_start", sa.Integer(), nullable=False),
               sa.Column("period_end", sa.Integer(), nullable=False),
               sa.Column("bbox_lon_min", sa.Float(), nullable=True),
               sa.Column("bbox_lon_max", sa.Float(), nullable=True),
               sa.Column("bbox_lat_min", sa.Float(), nullable=True),
               sa.Column("bbox_lat_max", sa.Float(), nullable=True),
               sa.Column("generator_config", sa.JSON(), nullable=True),
               sa.Column("status", sa.String(length=50), nullable=False, server_default="created"),
               sa.Column("created_at", sa.DateTime(), nullable=False),
               sa.Column("updated_at", sa.DateTime(), nullable=False),
           )


       def downgrade() -> None:
           op.drop_table("projects")
       ```

    6. Apply the migration:
       ```bash
       py -m alembic upgrade head
       ```

       Verify the table exists:
       ```bash
       py -c "import sqlite3, pathlib; db = pathlib.Path.home()/'.medieval-forge'/'medieval_forge.db'; conn=sqlite3.connect(db); cur=conn.execute('SELECT name FROM sqlite_master WHERE type=\"table\" AND name=\"projects\"'); print(cur.fetchall())"
       ```
       Expected: `[('projects',)]`.

    7. Smoke-test schemas + paths:
       ```bash
       py -c "from medieval_forge.schemas import ProjectCreate; p=ProjectCreate(name='t',country_qid='Q29',period_start=800,period_end=1000); print(p.model_dump_json())"
       py -c "from medieval_forge.services.paths import is_valid_uuid; print(is_valid_uuid('550e8400-e29b-41d4-a716-446655440000')); print(is_valid_uuid('../etc/passwd'))"
       ```
  </action>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md
    - .planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md
    - backend/medieval_forge/models.py
    - backend/medieval_forge/database.py
    - alembic/env.py
  </read_first>
  <verify>
    <automated>py -m alembic upgrade head && py -c "from medieval_forge.schemas import ProjectCreate, ProjectUpdate, ProjectResponse; from medieval_forge.services.paths import is_valid_uuid, project_dir, ensure_project_dirs; assert is_valid_uuid('550e8400-e29b-41d4-a716-446655440000'); assert not is_valid_uuid('../etc/passwd'); print('OK')"</automated>
  </verify>
  <done>Migration applied; `projects` table exists; schemas import and validate; paths.is_valid_uuid correctly rejects traversal strings.</done>
  <acceptance_criteria>
    - backend/medieval_forge/models.py contains "class Project(Base)"
    - backend/medieval_forge/models.py contains "country_qid"
    - backend/medieval_forge/models.py contains "generator_config"
    - backend/medieval_forge/schemas.py contains "class ProjectCreate"
    - backend/medieval_forge/schemas.py contains "class ProjectUpdate"
    - backend/medieval_forge/schemas.py contains "class ProjectResponse"
    - backend/medieval_forge/schemas.py contains "from_attributes=True"
    - backend/medieval_forge/schemas.py contains "Q\\d+"
    - backend/medieval_forge/services/paths.py contains "is_relative_to"
    - backend/medieval_forge/services/paths.py contains "ensure_project_dirs"
    - alembic/versions/0001_create_projects.py contains "op.create_table('projects'" OR "op.create_table(\"projects\""
    - py -m alembic upgrade head exits 0
    - sqlite_master query for table 'projects' returns 1 row
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 3: api/projects.py — 5 CRUD routes; main.py wires router</name>
  <files>
    backend/medieval_forge/api/__init__.py,
    backend/medieval_forge/api/projects.py,
    backend/medieval_forge/main.py
  </files>
  <behavior>
    - Router exposes 5 endpoints under prefix `/projects` (which is mounted under `/api` by main.py — final paths: POST/GET /api/projects, GET/PATCH/DELETE /api/projects/{project_id})
    - POST: validates body via ProjectCreate; creates Project row + ensure_project_dirs; returns 201 + ProjectResponse
    - GET (list): returns list[ProjectResponse], ordered by created_at DESC
    - GET (single): T-PATH guard — 400 if project_id is not a valid UUID; 404 if not found
    - PATCH: T-PATH guard; updates only fields present in ProjectUpdate; returns 200 + ProjectResponse
    - DELETE: T-PATH guard; deletes row + shutil.rmtree(project_dir, ignore_errors=True); returns 204
    - main.py: `from .api.projects import router as projects_router; app.include_router(projects_router, prefix="/api")` — registered BEFORE the SPA catch-all (RESEARCH Pitfall 8)
  </behavior>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md (Pattern 5 — SPA fallback ordering)
    - .planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md (D-07 — folder structure)
    - backend/medieval_forge/main.py (current state from Plan 01-01)
    - backend/medieval_forge/database.py
    - backend/medieval_forge/models.py
    - backend/medieval_forge/schemas.py
    - backend/medieval_forge/services/paths.py
  </read_first>
  <action>
    1. CREATE `backend/medieval_forge/api/__init__.py` (empty: `"""Medieval Forge HTTP API routers."""`).

    2. CREATE `backend/medieval_forge/api/projects.py`:
       ```python
       """PROJ-01..05: project CRUD endpoints.

       T-PATH mitigation: every route that accepts a path-bound project_id
       validates it via services.paths.is_valid_uuid before any DB or fs access.
       """
       from __future__ import annotations

       import shutil

       from fastapi import APIRouter, Depends, HTTPException, status
       from sqlalchemy import select
       from sqlalchemy.ext.asyncio import AsyncSession

       from ..database import get_db
       from ..models import Project
       from ..schemas import ProjectCreate, ProjectResponse, ProjectUpdate
       from ..services.paths import ensure_project_dirs, is_valid_uuid, project_dir

       router = APIRouter(prefix="/projects", tags=["projects"])


       def _validate_project_id(project_id: str) -> None:
           if not is_valid_uuid(project_id):
               raise HTTPException(
                   status_code=status.HTTP_400_BAD_REQUEST,
                   detail="project_id must be a valid UUID",
               )


       @router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectResponse)
       async def create_project(
           payload: ProjectCreate, db: AsyncSession = Depends(get_db)
       ) -> Project:
           project = Project(**payload.model_dump())
           db.add(project)
           await db.commit()
           await db.refresh(project)
           # D-07: per-project folder structure.
           ensure_project_dirs(project.id)
           return project


       @router.get("", response_model=list[ProjectResponse])
       async def list_projects(db: AsyncSession = Depends(get_db)) -> list[Project]:
           result = await db.execute(select(Project).order_by(Project.created_at.desc()))
           return list(result.scalars().all())


       @router.get("/{project_id}", response_model=ProjectResponse)
       async def get_project(
           project_id: str, db: AsyncSession = Depends(get_db)
       ) -> Project:
           _validate_project_id(project_id)
           project = await db.get(Project, project_id)
           if project is None:
               raise HTTPException(status_code=404, detail="project not found")
           return project


       @router.patch("/{project_id}", response_model=ProjectResponse)
       async def update_project(
           project_id: str,
           payload: ProjectUpdate,
           db: AsyncSession = Depends(get_db),
       ) -> Project:
           _validate_project_id(project_id)
           project = await db.get(Project, project_id)
           if project is None:
               raise HTTPException(status_code=404, detail="project not found")
           updates = payload.model_dump(exclude_unset=True)
           for k, v in updates.items():
               setattr(project, k, v)
           await db.commit()
           await db.refresh(project)
           return project


       @router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
       async def delete_project(
           project_id: str, db: AsyncSession = Depends(get_db)
       ) -> None:
           _validate_project_id(project_id)
           project = await db.get(Project, project_id)
           if project is None:
               raise HTTPException(status_code=404, detail="project not found")
           # Capture the project root BEFORE delete (path validation re-runs).
           proj_root = project_dir(project_id)
           await db.delete(project)
           await db.commit()
           shutil.rmtree(proj_root, ignore_errors=True)
       ```

    3. EDIT `backend/medieval_forge/main.py`. Locate the comment block "API routers will be registered here by plans 02..05" (added in Plan 01-01 Task 6) and replace it with the actual import + include_router. The order MUST be:
       - imports at top
       - app = FastAPI(...)
       - app.include_router(projects_router, prefix="/api")   ← new
       - if ASSETS_DIR.exists(): app.mount("/assets", ...)
       - @app.get("/{full_path:path}") spa_catch_all          ← still last

       The new lines to add immediately after `app = FastAPI(...)`:
       ```python
       from .api.projects import router as projects_router

       app.include_router(projects_router, prefix="/api")
       ```

       Verify final route order with:
       ```bash
       py -c "from medieval_forge.main import app; [print(r.methods, r.path) for r in app.routes]"
       ```
       Expected: `/api/projects` paths appear BEFORE `/{full_path:path}`.
  </action>
  <read_first>
    - backend/medieval_forge/main.py
    - backend/medieval_forge/database.py
    - backend/medieval_forge/models.py
    - backend/medieval_forge/schemas.py
    - backend/medieval_forge/services/paths.py
  </read_first>
  <verify>
    <automated>py -c "from medieval_forge.main import app; paths=[r.path for r in app.routes]; assert '/api/projects' in paths or '/api/projects/' in paths or any('/api/projects' in p for p in paths), paths; catchall_idx=[i for i,p in enumerate(paths) if 'full_path' in p]; api_idxs=[i for i,p in enumerate(paths) if '/api/projects' in p]; assert all(i < catchall_idx[0] for i in api_idxs), 'catch-all must be after API routes'; print('OK')"</automated>
  </verify>
  <done>FastAPI app loads; 5 /api/projects routes registered; SPA catch-all is the last route.</done>
  <acceptance_criteria>
    - backend/medieval_forge/api/projects.py contains "router = APIRouter(prefix=\"/projects\""
    - backend/medieval_forge/api/projects.py contains "@router.post(\"\""
    - backend/medieval_forge/api/projects.py contains "@router.get(\"\""
    - backend/medieval_forge/api/projects.py contains "@router.get(\"/{project_id}\""
    - backend/medieval_forge/api/projects.py contains "@router.patch(\"/{project_id}\""
    - backend/medieval_forge/api/projects.py contains "@router.delete(\"/{project_id}\""
    - backend/medieval_forge/api/projects.py contains "is_valid_uuid"
    - backend/medieval_forge/api/projects.py contains "shutil.rmtree"
    - backend/medieval_forge/api/projects.py contains "ensure_project_dirs"
    - backend/medieval_forge/main.py contains "from .api.projects import router as projects_router"
    - backend/medieval_forge/main.py contains "app.include_router(projects_router, prefix=\"/api\")"
    - py -c "from medieval_forge.main import app" exits 0
    - The route ordering check (catch-all is last) in <verify> exits 0
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 4: test_projects.py — implement all 9 CRUD/security tests against AsyncClient</name>
  <files>backend/tests/test_projects.py</files>
  <behavior>
    - Replace all `@pytest.mark.skip` stubs with real async tests using the `client` fixture from conftest.py
    - Use a `tmp_path` monkeypatch trick to redirect `medieval_forge.services.paths.PROJECTS_ROOT` so file-creating tests don't leak into `~/.medieval-forge/projects/`
    - All 9 tests pass against the in-memory SQLite from conftest.py
  </behavior>
  <read_first>
    - backend/tests/conftest.py
    - backend/tests/test_projects.py (current stubs)
    - backend/medieval_forge/api/projects.py
    - backend/medieval_forge/services/paths.py
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md (conftest pattern)
  </read_first>
  <action>
    Replace `backend/tests/test_projects.py` with full implementations:

    ```python
    """Tests for PROJ-01..05 — project CRUD endpoints."""
    from __future__ import annotations

    from pathlib import Path

    import pytest


    @pytest.fixture(autouse=True)
    def _isolated_projects_root(tmp_path, monkeypatch):
        """Redirect PROJECTS_ROOT to a tmp dir so tests don't pollute ~/.medieval-forge/."""
        from medieval_forge.services import paths as paths_mod

        fake_root = tmp_path / "projects"
        monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", fake_root)


    def _payload(**overrides):
        base = {
            "name": "Test Project",
            "country_qid": "Q29",
            "period_start": 868,
            "period_end": 1492,
        }
        base.update(overrides)
        return base


    async def test_create_project(client):
        resp = await client.post("/api/projects", json=_payload())
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["name"] == "Test Project"
        assert data["country_qid"] == "Q29"
        assert data["status"] == "created"
        assert "id" in data and len(data["id"]) == 36


    async def test_list_projects(client):
        # Empty initially.
        resp = await client.get("/api/projects")
        assert resp.status_code == 200
        assert resp.json() == []
        # Create two.
        await client.post("/api/projects", json=_payload(name="A"))
        await client.post("/api/projects", json=_payload(name="B"))
        resp = await client.get("/api/projects")
        names = [p["name"] for p in resp.json()]
        assert set(names) == {"A", "B"}


    async def test_get_project(client):
        created = (await client.post("/api/projects", json=_payload())).json()
        pid = created["id"]
        resp = await client.get(f"/api/projects/{pid}")
        assert resp.status_code == 200
        assert resp.json()["id"] == pid


    async def test_get_project_invalid_uuid_returns_400(client):
        resp = await client.get("/api/projects/not-a-uuid")
        assert resp.status_code == 400
        assert "uuid" in resp.json()["detail"].lower()


    async def test_get_project_not_found_returns_404(client):
        # Valid UUID format but no row.
        resp = await client.get("/api/projects/550e8400-e29b-41d4-a716-446655440000")
        assert resp.status_code == 404


    async def test_update_project(client):
        created = (await client.post("/api/projects", json=_payload())).json()
        pid = created["id"]
        resp = await client.patch(
            f"/api/projects/{pid}",
            json={"name": "Renamed", "period_end": 1500},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["name"] == "Renamed"
        assert body["period_end"] == 1500
        assert body["country_qid"] == "Q29"  # unchanged


    async def test_delete_project(client):
        from medieval_forge.services.paths import PROJECTS_ROOT

        created = (await client.post("/api/projects", json=_payload())).json()
        pid = created["id"]
        # Folder exists post-create.
        assert (PROJECTS_ROOT / pid).exists()

        resp = await client.delete(f"/api/projects/{pid}")
        assert resp.status_code == 204

        # Row gone.
        resp = await client.get(f"/api/projects/{pid}")
        assert resp.status_code == 404
        # Folder gone.
        assert not (PROJECTS_ROOT / pid).exists()


    async def test_create_project_creates_folders(client, tmp_path):
        from medieval_forge.services.paths import PROJECTS_ROOT

        created = (await client.post("/api/projects", json=_payload())).json()
        pid = created["id"]
        root = PROJECTS_ROOT / pid
        assert (root / "raw").is_dir()
        assert (root / "generated").is_dir()
        assert (root / "exports").is_dir()


    async def test_country_qid_validation_rejects_bad_format(client):
        resp = await client.post("/api/projects", json=_payload(country_qid="spain"))
        assert resp.status_code == 422
        body = resp.json()
        assert any("country_qid" in str(err) for err in body["detail"])
    ```

    Run: `py -m pytest backend/tests/test_projects.py -x -q`. Expected: 9 passed.
  </action>
  <read_first>
    - backend/tests/conftest.py
    - backend/tests/test_projects.py
    - backend/medieval_forge/api/projects.py
    - backend/medieval_forge/services/paths.py
  </read_first>
  <verify>
    <automated>py -m pytest backend/tests/test_projects.py -x -q</automated>
  </verify>
  <done>9 passed, 0 failed.</done>
  <acceptance_criteria>
    - backend/tests/test_projects.py contains "client.post(\"/api/projects\""
    - backend/tests/test_projects.py contains "client.delete(f\"/api/projects/{pid}\")"
    - backend/tests/test_projects.py contains "monkeypatch.setattr(paths_mod, \"PROJECTS_ROOT\""
    - backend/tests/test_projects.py contains "test_get_project_invalid_uuid_returns_400"
    - backend/tests/test_projects.py contains "test_create_project_creates_folders"
    - py -m pytest backend/tests/test_projects.py -x -q exits 0 with "9 passed"
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 5: Frontend bootstrap — Vite 6 + React 19 + Tailwind v4 + Radix Themes + TanStack Query + react-router-dom 7</name>
  <files>
    frontend/package.json,
    frontend/vite.config.ts,
    frontend/tsconfig.json,
    frontend/tsconfig.node.json,
    frontend/index.html,
    frontend/src/main.tsx,
    frontend/src/App.tsx,
    frontend/src/index.css
  </files>
  <behavior>
    - `cd frontend && npm install` resolves all deps without errors
    - `cd frontend && npm run build` outputs files into `../backend/medieval_forge/static/` (D-02), with `index.html` and `assets/*.js` + `assets/*.css`
    - `vite.config.ts` sets `base: "./"` (CRITICAL — RESEARCH.md Pitfall 4)
    - `frontend/src/index.css` imports `@radix-ui/themes/styles.css` BEFORE `@import "tailwindcss"` (RESEARCH.md Pitfall 7)
    - `App.tsx` wraps the route tree in `<Theme>` (Radix) and `<QueryClientProvider>` (TanStack)
    - `App.tsx` defines three routes: `/projects`, `/projects/new`, `/projects/:id` (D-08, D-10 — no other routes, no canvas placeholder)
  </behavior>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md (Pattern 4 — Vite Config; Pitfall 4 — base "./"; Pitfall 7 — Radix CSS order; Standard Stack — exact frontend versions)
    - .planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md (D-02, D-08, D-10)
    - CLAUDE.md (Frontend stack table)
  </read_first>
  <action>
    1. CREATE `frontend/package.json`:
       ```json
       {
         "name": "medieval-forge-frontend",
         "version": "0.1.0",
         "private": true,
         "type": "module",
         "scripts": {
           "dev": "vite",
           "build": "tsc -b && vite build",
           "preview": "vite preview"
         },
         "dependencies": {
           "react": "^19.2.0",
           "react-dom": "^19.2.0",
           "react-router-dom": "^7.14.0",
           "@tanstack/react-query": "^5.99.0",
           "zustand": "^5.0.12",
           "zundo": "^2.3.0",
           "@radix-ui/themes": "^3.3.0"
         },
         "devDependencies": {
           "@types/react": "^19.2.0",
           "@types/react-dom": "^19.2.0",
           "@vitejs/plugin-react": "^4.4.0",
           "typescript": "~5.8.0",
           "vite": "^6.4.0",
           "tailwindcss": "^4.2.0",
           "@tailwindcss/vite": "^4.2.0"
         }
       }
       ```

    2. CREATE `frontend/vite.config.ts` (Pattern 4 from RESEARCH.md):
       ```typescript
       import { defineConfig } from 'vite'
       import react from '@vitejs/plugin-react'
       import tailwindcss from '@tailwindcss/vite'

       export default defineConfig({
         plugins: [react(), tailwindcss()],
         base: './',
         build: {
           outDir: '../backend/medieval_forge/static',
           emptyOutDir: true,
         },
         server: {
           port: 5173,
           proxy: {
             '/api': 'http://127.0.0.1:8765',
           },
         },
       })
       ```

    3. CREATE `frontend/tsconfig.json`:
       ```json
       {
         "compilerOptions": {
           "target": "ES2022",
           "useDefineForClassFields": true,
           "lib": ["ES2022", "DOM", "DOM.Iterable"],
           "module": "ESNext",
           "skipLibCheck": true,
           "moduleResolution": "bundler",
           "allowImportingTsExtensions": true,
           "resolveJsonModule": true,
           "isolatedModules": true,
           "noEmit": true,
           "jsx": "react-jsx",
           "strict": true,
           "noUnusedLocals": true,
           "noUnusedParameters": true,
           "noFallthroughCasesInSwitch": true
         },
         "include": ["src"],
         "references": [{ "path": "./tsconfig.node.json" }]
       }
       ```

    4. CREATE `frontend/tsconfig.node.json`:
       ```json
       {
         "compilerOptions": {
           "composite": true,
           "skipLibCheck": true,
           "module": "ESNext",
           "moduleResolution": "bundler",
           "allowSyntheticDefaultImports": true,
           "strict": true
         },
         "include": ["vite.config.ts"]
       }
       ```

    5. CREATE `frontend/index.html`:
       ```html
       <!DOCTYPE html>
       <html lang="en">
         <head>
           <meta charset="UTF-8" />
           <meta name="viewport" content="width=device-width, initial-scale=1.0" />
           <title>Medieval Forge</title>
         </head>
         <body>
           <div id="root"></div>
           <script type="module" src="/src/main.tsx"></script>
         </body>
       </html>
       ```

    6. CREATE `frontend/src/index.css` (CRITICAL ORDER — Pitfall 7):
       ```css
       /* Radix Themes CSS MUST come before Tailwind (RESEARCH.md Pitfall 7). */
       @import "@radix-ui/themes/styles.css";
       @import "tailwindcss";

       html, body, #root {
         height: 100%;
         margin: 0;
       }
       ```

    7. CREATE `frontend/src/main.tsx`:
       ```typescript
       import React from 'react'
       import ReactDOM from 'react-dom/client'
       import { BrowserRouter } from 'react-router-dom'
       import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
       import { Theme } from '@radix-ui/themes'
       import App from './App'
       import './index.css'

       const queryClient = new QueryClient({
         defaultOptions: {
           queries: { staleTime: 1000 * 30 },
         },
       })

       ReactDOM.createRoot(document.getElementById('root')!).render(
         <React.StrictMode>
           <Theme appearance="light" accentColor="iris" radius="medium">
             <QueryClientProvider client={queryClient}>
               <BrowserRouter>
                 <App />
               </BrowserRouter>
             </QueryClientProvider>
           </Theme>
         </React.StrictMode>,
       )
       ```

    8. CREATE `frontend/src/App.tsx` (D-10: only Phase 1 routes):
       ```typescript
       import { Navigate, Route, Routes } from 'react-router-dom'
       import { ProjectList } from './pages/ProjectList'
       import { ProjectNew } from './pages/ProjectNew'
       import { ProjectDetail } from './pages/ProjectDetail'

       export default function App() {
         return (
           <Routes>
             <Route path="/" element={<Navigate to="/projects" replace />} />
             <Route path="/projects" element={<ProjectList />} />
             <Route path="/projects/new" element={<ProjectNew />} />
             <Route path="/projects/:id" element={<ProjectDetail />} />
           </Routes>
         )
       }
       ```

    9. The three pages are stubs created in Task 6. To allow `npm install` and `npm run build` to succeed in this task BEFORE Task 6 lands them, create empty placeholder files:
       ```bash
       mkdir -p frontend/src/pages frontend/src/api
       ```
       Then write minimal placeholder files (Task 6 will replace them):
       - `frontend/src/pages/ProjectList.tsx`: `export function ProjectList() { return <div>list</div>; }`
       - `frontend/src/pages/ProjectNew.tsx`: `export function ProjectNew() { return <div>new</div>; }`
       - `frontend/src/pages/ProjectDetail.tsx`: `export function ProjectDetail() { return <div>detail</div>; }`
       - `frontend/src/api/client.ts`: `export {}`

    10. Install + build:
        ```bash
        cd frontend && npm install
        cd frontend && npm run build
        ```

        After build, verify outputs exist:
        ```bash
        ls backend/medieval_forge/static/index.html
        ls backend/medieval_forge/static/assets/*.js
        ```
  </action>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md
    - .planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md
    - CLAUDE.md
  </read_first>
  <verify>
    <automated>cd frontend && npm install && npm run build && ls ../backend/medieval_forge/static/index.html</automated>
  </verify>
  <done>npm install completes; npm run build produces backend/medieval_forge/static/index.html and at least one JS asset under static/assets/.</done>
  <acceptance_criteria>
    - frontend/package.json contains "react": "^19.2.0" OR "^19" semver
    - frontend/package.json contains "vite": "^6"
    - frontend/package.json contains "@radix-ui/themes"
    - frontend/package.json contains "@tailwindcss/vite"
    - frontend/package.json contains "@tanstack/react-query"
    - frontend/package.json contains "zundo": "^2.3.0"
    - frontend/vite.config.ts contains "base: './'"
    - frontend/vite.config.ts contains "outDir: '../backend/medieval_forge/static'"
    - frontend/vite.config.ts contains "tailwindcss()"
    - frontend/src/index.css line containing "@radix-ui/themes/styles.css" appears BEFORE line containing "@import \"tailwindcss\""
    - frontend/src/main.tsx contains "QueryClientProvider"
    - frontend/src/main.tsx contains "<Theme"
    - frontend/src/App.tsx contains exactly 3 Route elements with paths /projects, /projects/new, /projects/:id (no other routes per D-10)
    - backend/medieval_forge/static/index.html exists after build
    - backend/medieval_forge/static/assets/ contains at least one .js file
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 6: Frontend pages — TanStack Query client + ProjectList + ProjectNew + ProjectDetail (with placeholder action buttons for Plans 03/04/05)</name>
  <files>
    frontend/src/api/client.ts,
    frontend/src/pages/ProjectList.tsx,
    frontend/src/pages/ProjectNew.tsx,
    frontend/src/pages/ProjectDetail.tsx
  </files>
  <behavior>
    - `client.ts` exports typed `Project` interface matching ProjectResponse shape AND TanStack Query hooks: useProjects, useProject(id), useCreateProject, useUpdateProject, useDeleteProject
    - All API calls use relative paths (`/api/projects`) so they work both in dev (Vite proxy) and in production (FastAPI same origin)
    - `ProjectList`: renders a card/grid for each project with name, country_qid, period range, status, created_at; "New project" button → `/projects/new`; per-row "Open" link → `/projects/:id`; "Delete" button with `window.confirm` (PROJ-04 confirmation requirement)
    - `ProjectNew`: form with name, country_qid (text input — Wikidata QID), period_start, period_end, optional bbox 4 fields; on submit calls useCreateProject and navigates to `/projects/:newId`
    - `ProjectDetail`: shows project fields; PATCH-via-edit form for name/period; THREE placeholder buttons clearly labeled "Ingest (Plan 1.3)", "Generate (Plan 1.4)", "Export ZIP (Plan 1.5)" — disabled with `title="Will be wired in upcoming plan"`. These are SCAFFOLDS for plans 03/04/05 to wire later, not features delivered here.
    - Per D-09: a placeholder `<pre id="ingest-log">` element exists, empty for now, ready for Plan 03 to append SSE events
  </behavior>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md (D-08, D-09, D-10, specifics — page list)
    - frontend/src/App.tsx
    - backend/medieval_forge/schemas.py (ProjectResponse shape)
    - backend/medieval_forge/api/projects.py (endpoint shapes)
  </read_first>
  <action>
    1. REPLACE `frontend/src/api/client.ts`:
       ```typescript
       import {
         useQuery,
         useMutation,
         useQueryClient,
         type UseQueryResult,
       } from '@tanstack/react-query'

       export interface Project {
         id: string
         name: string
         country_qid: string
         period_start: number
         period_end: number
         bbox_lon_min: number | null
         bbox_lon_max: number | null
         bbox_lat_min: number | null
         bbox_lat_max: number | null
         generator_config: Record<string, unknown> | null
         status: string
         created_at: string
         updated_at: string
       }

       export interface ProjectCreatePayload {
         name: string
         country_qid: string
         period_start: number
         period_end: number
         bbox_lon_min?: number | null
         bbox_lon_max?: number | null
         bbox_lat_min?: number | null
         bbox_lat_max?: number | null
         generator_config?: Record<string, unknown> | null
       }

       export type ProjectUpdatePayload = Partial<ProjectCreatePayload> & {
         status?: string
       }

       async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
         const res = await fetch(path, {
           ...init,
           headers: {
             'Content-Type': 'application/json',
             ...(init?.headers || {}),
           },
         })
         if (!res.ok) {
           const text = await res.text()
           throw new Error(`${res.status} ${res.statusText}: ${text}`)
         }
         if (res.status === 204) return undefined as T
         return res.json() as Promise<T>
       }

       export function useProjects(): UseQueryResult<Project[]> {
         return useQuery({
           queryKey: ['projects'],
           queryFn: () => jsonFetch<Project[]>('/api/projects'),
         })
       }

       export function useProject(id: string | undefined) {
         return useQuery({
           queryKey: ['projects', id],
           queryFn: () => jsonFetch<Project>(`/api/projects/${id}`),
           enabled: Boolean(id),
         })
       }

       export function useCreateProject() {
         const qc = useQueryClient()
         return useMutation({
           mutationFn: (payload: ProjectCreatePayload) =>
             jsonFetch<Project>('/api/projects', {
               method: 'POST',
               body: JSON.stringify(payload),
             }),
           onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
         })
       }

       export function useUpdateProject(id: string) {
         const qc = useQueryClient()
         return useMutation({
           mutationFn: (payload: ProjectUpdatePayload) =>
             jsonFetch<Project>(`/api/projects/${id}`, {
               method: 'PATCH',
               body: JSON.stringify(payload),
             }),
           onSuccess: () => {
             qc.invalidateQueries({ queryKey: ['projects'] })
             qc.invalidateQueries({ queryKey: ['projects', id] })
           },
         })
       }

       export function useDeleteProject() {
         const qc = useQueryClient()
         return useMutation({
           mutationFn: (id: string) =>
             jsonFetch<void>(`/api/projects/${id}`, { method: 'DELETE' }),
           onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
         })
       }
       ```

    2. REPLACE `frontend/src/pages/ProjectList.tsx`:
       ```typescript
       import { Link } from 'react-router-dom'
       import { Box, Button, Card, Flex, Heading, Text } from '@radix-ui/themes'
       import { useDeleteProject, useProjects } from '../api/client'

       export function ProjectList() {
         const { data, isLoading, error } = useProjects()
         const del = useDeleteProject()

         return (
           <Box p="6">
             <Flex justify="between" align="center" mb="4">
               <Heading>Projects</Heading>
               <Link to="/projects/new">
                 <Button>New project</Button>
               </Link>
             </Flex>
             {isLoading && <Text>Loading…</Text>}
             {error && <Text color="red">{(error as Error).message}</Text>}
             {data && data.length === 0 && <Text color="gray">No projects yet.</Text>}
             <Flex direction="column" gap="3">
               {data?.map((p) => (
                 <Card key={p.id}>
                   <Flex justify="between" align="center">
                     <Box>
                       <Heading size="3">{p.name}</Heading>
                       <Text size="2" color="gray">
                         {p.country_qid} · {p.period_start}–{p.period_end} · {p.status}
                       </Text>
                     </Box>
                     <Flex gap="2">
                       <Link to={`/projects/${p.id}`}>
                         <Button variant="soft">Open</Button>
                       </Link>
                       <Button
                         color="red"
                         variant="soft"
                         onClick={() => {
                           if (window.confirm(`Delete project "${p.name}"?`)) {
                             del.mutate(p.id)
                           }
                         }}
                       >
                         Delete
                       </Button>
                     </Flex>
                   </Flex>
                 </Card>
               ))}
             </Flex>
           </Box>
         )
       }
       ```

    3. REPLACE `frontend/src/pages/ProjectNew.tsx`:
       ```typescript
       import { useState } from 'react'
       import { useNavigate } from 'react-router-dom'
       import { Box, Button, Flex, Heading, Text, TextField } from '@radix-ui/themes'
       import { useCreateProject } from '../api/client'

       export function ProjectNew() {
         const navigate = useNavigate()
         const create = useCreateProject()
         const [form, setForm] = useState({
           name: '',
           country_qid: 'Q29',
           period_start: 868,
           period_end: 1492,
           bbox_lon_min: '',
           bbox_lon_max: '',
           bbox_lat_min: '',
           bbox_lat_max: '',
         })

         const update = (k: keyof typeof form, v: string) =>
           setForm((s) => ({ ...s, [k]: v }))

         const submit = async (e: React.FormEvent) => {
           e.preventDefault()
           const toFloat = (v: string) => (v === '' ? null : Number(v))
           const created = await create.mutateAsync({
             name: form.name,
             country_qid: form.country_qid,
             period_start: Number(form.period_start),
             period_end: Number(form.period_end),
             bbox_lon_min: toFloat(form.bbox_lon_min),
             bbox_lon_max: toFloat(form.bbox_lon_max),
             bbox_lat_min: toFloat(form.bbox_lat_min),
             bbox_lat_max: toFloat(form.bbox_lat_max),
           })
           navigate(`/projects/${created.id}`)
         }

         return (
           <Box p="6" style={{ maxWidth: 640 }}>
             <Heading mb="4">New project</Heading>
             <form onSubmit={submit}>
               <Flex direction="column" gap="3">
                 <Box>
                   <Text as="label" size="2" weight="medium">Name</Text>
                   <TextField.Root
                     value={form.name}
                     onChange={(e) => update('name', e.target.value)}
                     required
                   />
                 </Box>
                 <Box>
                   <Text as="label" size="2" weight="medium">
                     Country (Wikidata QID, e.g. Q29 = Spain, Q142 = France)
                   </Text>
                   <TextField.Root
                     value={form.country_qid}
                     onChange={(e) => update('country_qid', e.target.value)}
                     required
                   />
                 </Box>
                 <Flex gap="3">
                   <Box style={{ flex: 1 }}>
                     <Text as="label" size="2" weight="medium">Period start (year)</Text>
                     <TextField.Root
                       type="number"
                       value={form.period_start}
                       onChange={(e) => update('period_start', e.target.value)}
                       required
                     />
                   </Box>
                   <Box style={{ flex: 1 }}>
                     <Text as="label" size="2" weight="medium">Period end (year)</Text>
                     <TextField.Root
                       type="number"
                       value={form.period_end}
                       onChange={(e) => update('period_end', e.target.value)}
                       required
                     />
                   </Box>
                 </Flex>
                 <Heading size="2" mt="2">Bounding box (optional)</Heading>
                 <Flex gap="3">
                   <TextField.Root placeholder="lon_min" value={form.bbox_lon_min} onChange={(e) => update('bbox_lon_min', e.target.value)} />
                   <TextField.Root placeholder="lon_max" value={form.bbox_lon_max} onChange={(e) => update('bbox_lon_max', e.target.value)} />
                   <TextField.Root placeholder="lat_min" value={form.bbox_lat_min} onChange={(e) => update('bbox_lat_min', e.target.value)} />
                   <TextField.Root placeholder="lat_max" value={form.bbox_lat_max} onChange={(e) => update('bbox_lat_max', e.target.value)} />
                 </Flex>
                 {create.error && (
                   <Text color="red">{(create.error as Error).message}</Text>
                 )}
                 <Flex gap="2" mt="2">
                   <Button type="submit" disabled={create.isPending}>
                     {create.isPending ? 'Creating…' : 'Create project'}
                   </Button>
                 </Flex>
               </Flex>
             </form>
           </Box>
         )
       }
       ```

    4. REPLACE `frontend/src/pages/ProjectDetail.tsx`:
       ```typescript
       import { useState } from 'react'
       import { Link, useParams } from 'react-router-dom'
       import { Box, Button, Card, Flex, Heading, Text, TextField } from '@radix-ui/themes'
       import { useProject, useUpdateProject } from '../api/client'

       export function ProjectDetail() {
         const { id } = useParams<{ id: string }>()
         const { data: project, isLoading, error } = useProject(id)
         const update = useUpdateProject(id || '')
         const [editing, setEditing] = useState(false)
         const [draft, setDraft] = useState({ name: '', period_start: 0, period_end: 0 })

         if (isLoading) return <Box p="6"><Text>Loading…</Text></Box>
         if (error) return <Box p="6"><Text color="red">{(error as Error).message}</Text></Box>
         if (!project) return null

         const startEdit = () => {
           setDraft({
             name: project.name,
             period_start: project.period_start,
             period_end: project.period_end,
           })
           setEditing(true)
         }

         const save = async () => {
           await update.mutateAsync({
             name: draft.name,
             period_start: Number(draft.period_start),
             period_end: Number(draft.period_end),
           })
           setEditing(false)
         }

         return (
           <Box p="6">
             <Flex justify="between" align="center" mb="4">
               <Heading>{project.name}</Heading>
               <Link to="/projects"><Button variant="soft">← All projects</Button></Link>
             </Flex>

             <Card mb="4">
               <Flex direction="column" gap="2">
                 <Text><strong>ID:</strong> {project.id}</Text>
                 <Text><strong>Country QID:</strong> {project.country_qid}</Text>
                 <Text><strong>Period:</strong> {project.period_start}–{project.period_end}</Text>
                 <Text><strong>Status:</strong> {project.status}</Text>
                 <Text size="2" color="gray">Created {project.created_at}</Text>
                 <Flex gap="2" mt="2">
                   {!editing && <Button variant="soft" onClick={startEdit}>Edit</Button>}
                 </Flex>
               </Flex>
             </Card>

             {editing && (
               <Card mb="4">
                 <Heading size="3" mb="2">Edit project</Heading>
                 <Flex direction="column" gap="2">
                   <TextField.Root
                     value={draft.name}
                     onChange={(e) => setDraft((s) => ({ ...s, name: e.target.value }))}
                   />
                   <Flex gap="2">
                     <TextField.Root
                       type="number"
                       value={draft.period_start}
                       onChange={(e) => setDraft((s) => ({ ...s, period_start: Number(e.target.value) }))}
                     />
                     <TextField.Root
                       type="number"
                       value={draft.period_end}
                       onChange={(e) => setDraft((s) => ({ ...s, period_end: Number(e.target.value) }))}
                     />
                   </Flex>
                   <Flex gap="2">
                     <Button onClick={save} disabled={update.isPending}>
                       {update.isPending ? 'Saving…' : 'Save'}
                     </Button>
                     <Button variant="soft" onClick={() => setEditing(false)}>Cancel</Button>
                   </Flex>
                 </Flex>
               </Card>
             )}

             {/* Placeholder action surface for Plans 03/04/05 (D-09 SSE log lives here too). */}
             <Card>
               <Heading size="3" mb="2">Pipeline actions</Heading>
               <Flex gap="2" mb="3">
                 <Button disabled title="Will be wired by Plan 1.3 (data ingestion)">Ingest (Plan 1.3)</Button>
                 <Button disabled title="Will be wired by Plan 1.4 (map generation)">Generate (Plan 1.4)</Button>
                 <Button disabled title="Will be wired by Plan 1.5 (Unity export)">Export ZIP (Plan 1.5)</Button>
               </Flex>
               <Box>
                 <Text size="2" color="gray">Ingestion log (populated by Plan 1.3):</Text>
                 <pre
                   id="ingest-log"
                   style={{
                     marginTop: 4,
                     padding: 8,
                     background: '#f5f5f5',
                     borderRadius: 4,
                     maxHeight: 240,
                     overflow: 'auto',
                     fontSize: 12,
                   }}
                 />
               </Box>
             </Card>
           </Box>
         )
       }
       ```

    5. Rebuild:
       ```bash
       cd frontend && npm run build
       ```

       Verify final bundle:
       ```bash
       ls backend/medieval_forge/static/index.html
       grep -E "src=\".*\.js\"" backend/medieval_forge/static/index.html
       ```
       Expected: index.html exists; the script src starts with `./assets/` (relative — confirms `base: './'` worked).
  </action>
  <read_first>
    - frontend/src/App.tsx
    - frontend/src/main.tsx
    - backend/medieval_forge/schemas.py
    - backend/medieval_forge/api/projects.py
    - .planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md
  </read_first>
  <verify>
    <automated>cd frontend && npm run build && grep -E "src=\"\\./assets/.*\\.js\"" ../backend/medieval_forge/static/index.html</automated>
  </verify>
  <done>npm run build succeeds. index.html script tag uses relative `./assets/...` path (confirms base: './'). Three pages exist with the required components and the placeholder action surface.</done>
  <acceptance_criteria>
    - frontend/src/api/client.ts contains "useProjects", "useProject", "useCreateProject", "useUpdateProject", "useDeleteProject"
    - frontend/src/api/client.ts contains "interface Project"
    - frontend/src/api/client.ts contains "/api/projects"
    - frontend/src/pages/ProjectList.tsx contains "useProjects"
    - frontend/src/pages/ProjectList.tsx contains "window.confirm"
    - frontend/src/pages/ProjectList.tsx contains "Link to=\"/projects/new\""
    - frontend/src/pages/ProjectNew.tsx contains "useCreateProject"
    - frontend/src/pages/ProjectNew.tsx contains "country_qid"
    - frontend/src/pages/ProjectDetail.tsx contains "useProject"
    - frontend/src/pages/ProjectDetail.tsx contains "useUpdateProject"
    - frontend/src/pages/ProjectDetail.tsx contains "id=\"ingest-log\"" (D-09 placeholder)
    - frontend/src/pages/ProjectDetail.tsx contains "Plan 1.3" AND "Plan 1.4" AND "Plan 1.5" (placeholder buttons labelled per their owning plan)
    - backend/medieval_forge/static/index.html exists
    - backend/medieval_forge/static/index.html contains src="./assets/" (relative path, confirms base: './')
  </acceptance_criteria>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Browser → POST /api/projects | Untrusted JSON body; Pydantic ProjectCreate validates name length, integer types, and country_qid pattern |
| Browser → /api/projects/{project_id} | project_id is path-bound user input; T-PATH guard via is_valid_uuid before DB lookup or filesystem operation |
| FastAPI → filesystem (~/.medieval-forge/projects/{uuid}/) | Per-project directory; project_dir() validates UUID AND verifies resolved path is within PROJECTS_ROOT |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-PATH | Tampering | All routes accepting project_id (GET/PATCH/DELETE single) | mitigate | `_validate_project_id` raises HTTPException 400 if `is_valid_uuid` returns False. `project_dir()` re-validates AND checks `.resolve().is_relative_to(PROJECTS_ROOT)`. Test `test_get_project_invalid_uuid_returns_400` covers HTTP layer. |
| T-02-01 | Tampering | shutil.rmtree on DELETE | mitigate | Path comes from `project_dir(project_id)` which has already been validated; `ignore_errors=True` so a missing folder doesn't raise (idempotency vs partial-state recovery). |
| T-02-02 | Spoofing/SSRF | country_qid input | mitigate | Pydantic field_validator enforces `^Q\d+$`; the QID is later passed to ingest service (Plan 03) which itself validates AGAIN before composing the SPARQL query. Defence in depth. |
| T-02-03 | Information Disclosure | Pydantic ValidationError surfacing in 422 response | accept | FastAPI's default 422 response includes field paths and error type but no stack trace. Acceptable for a local-only tool (ASVS V7 not violated — no PII, no internal paths). |
| T-02-04 | Denial of Service | Unbounded project list growth | accept | Single-user local tool; no realistic scenario for unbounded growth. |
| T-02-05 | Tampering | Frontend SPA accepts any JSON from /api/projects | mitigate | TypeScript Project interface enforces shape at compile time; runtime calls `res.ok` check. Server is single source of truth. |
</threat_model>

<verification>
After all 6 tasks complete, run the per-wave verification command from VALIDATION.md:

```bash
py -m pytest backend/tests/ -v --tb=short --ignore=backend/tests/test_generate.py
```

Expected: 14 passing tests (5 cli + 1 packaging-pyproject + 9 projects). The other plan stubs (test_ingest, test_generate, test_export) don't exist yet — they land in Plans 03/04/05.

Manual smoke (one-off):
```bash
# Terminal A
medieval-forge start --no-browser
# Terminal B
curl -X POST http://localhost:8765/api/projects -H "Content-Type: application/json" -d '{"name":"smoke","country_qid":"Q29","period_start":800,"period_end":1000}'
curl http://localhost:8765/api/projects
# Browser: http://localhost:8765/projects — should show one card "smoke"
medieval-forge stop
```
</verification>

<success_criteria>
- `py -m pytest backend/tests/test_projects.py -x -q` passes 9/9.
- `py -m pytest backend/tests/ -x -q --ignore=backend/tests/test_generate.py` passes 14/14 (cumulative with Plan 01-01 tests).
- `medieval-forge start --no-browser` + `curl POST /api/projects` succeeds; the project row exists in `~/.medieval-forge/medieval_forge.db` AND the folder `~/.medieval-forge/projects/{uuid}/{raw,generated,exports}/` exists.
- `cd frontend && npm run build` produces `backend/medieval_forge/static/index.html` whose script src is RELATIVE (`./assets/...`).
- `~/.medieval-forge/medieval_forge.db` has the `projects` table created by migration `0001_create_projects`.
- All 5 ROADMAP success criteria #1 (PKG install + browser) and #2 (full CRUD via UI) are now exercisable end-to-end.
</success_criteria>

<output>
After completion, create `.planning/phases/01-data-pipeline-backend-scaffold/01-02-SUMMARY.md` per the standard summary template. Note: (a) which Tailwind+Radix component library decisions were made (e.g. used Card vs Box+border), (b) any TanStack Query stale time tuning, (c) any deviations from the placeholder button labels (Plans 03/04/05 will need to find the right buttons to wire).
</output>
