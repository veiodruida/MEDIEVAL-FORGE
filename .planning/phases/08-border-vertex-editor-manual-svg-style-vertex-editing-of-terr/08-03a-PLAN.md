---
phase: 08
plan: 03a
type: execute
wave: 1
depends_on: [08-00]
autonomous: true
requirements: [PERSIST-01, BRANCH-01]
files_modified:
  - backend/medieval_forge/models.py
  - backend/medieval_forge/services/branches/__init__.py
  - backend/medieval_forge/services/branches/service.py
  - backend/medieval_forge/api/v3/branches.py
  - backend/medieval_forge/main.py
  - backend/tests/unit/test_models_branches.py
  - backend/tests/integration/test_branches_endpoint.py

must_haves:
  truths:
    - "Branch table created on FastAPI startup via Base.metadata.create_all"
    - "POST /api/v3/projects/{id}/branches creates a branch with unique (project_id, name)"
    - "GET /api/v3/projects/{id}/branches returns branch list sorted by updated_at desc"
    - "PATCH /api/v3/projects/{id}/branches/{branch_id} renames (rename allowed on main per D-15)"
    - "DELETE returns 409 when branch.is_main=True (D-15 protection)"
    - "Existing projects lazy-create 'main' branch on first endpoint hit"
    - "original_idx_high_water inherited from parent branch on creation (D-22)"
  artifacts:
    - path: "backend/medieval_forge/models.py"
      provides: "Branch ORM model"
      contains: "class Branch(Base)"
    - path: "backend/medieval_forge/services/branches/service.py"
      provides: "create_branch / list_branches / rename_branch / delete_branch / ensure_main_branch"
      min_lines: 80
    - path: "backend/medieval_forge/api/v3/branches.py"
      provides: "5 endpoints (POST, GET, PATCH, DELETE, GET single)"
      min_lines: 60
  key_links:
    - from: "main.py lifespan"
      to: "Base.metadata.create_all"
      via: "Branch class registered on Base → table auto-created"
      pattern: "Base.metadata.create_all"
    - from: "api/v3/branches.py"
      to: "services/branches/service.py"
      via: "thin FastAPI router delegates to service layer"
      pattern: "await create_branch\\|list_branches\\|rename_branch\\|delete_branch"
---

<objective>
Wave 1 backend foundation #3 (parallel-safe with 08-01 — disjoint file set). Add the `branches` SQLAlchemy model + service layer + 5 FastAPI endpoints. `main` branch is delete-protected per D-15; rename allowed. Lazy-create `main` for pre-Phase-8 projects on first read (Pattern 2 convention).

D-22 inheritance: new branch inherits `original_idx_high_water` from parent so split operations on the child branch get unique ids relative to the parent's max.

Purpose: provide the persistence + API surface plan 08-03b (snapshots + edit_events) depends on, and plan 08-04 (frontend store) consumes.
Output: 1 ORM model + 1 service module + 1 router + DDL via create_all + 2 test files filled.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/REQUIREMENTS.md
@.planning/phases/08-.../08-CONTEXT.md
@.planning/phases/08-.../08-RESEARCH.md §"Pattern 3: SQLAlchemy 2.0 mapped models" + §"Pattern 1.5: SQLAlchemy 2.0 Branch CRUD"
@backend/medieval_forge/models.py
@backend/medieval_forge/main.py
@backend/medieval_forge/database.py
@backend/medieval_forge/api/v3/projects.py

<interfaces>
From models.py (verified pattern): Base = DeclarativeBase; Project / LLMCredential use `Mapped[..]` + `mapped_column`. Helpers `_new_uuid()` (uuid4 hex) and `_utcnow()` (datetime.utcnow) already exist.

From main.py:31 (verified): lifespan calls `Base.metadata.create_all(bind=...)` — new models auto-create.

From RESEARCH Pattern 3 (verbatim):
```python
class Branch(Base):
    __tablename__ = "branches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_main: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    original_idx_high_water: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    edits_since_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_branch_project_name"),)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Branch ORM model + services/branches/ package + unit tests</name>
  <files>backend/medieval_forge/models.py, backend/medieval_forge/services/branches/__init__.py, backend/medieval_forge/services/branches/service.py, backend/tests/unit/test_models_branches.py</files>
  <read_first>
    - backend/medieval_forge/models.py (full file — _new_uuid, _utcnow, Mapped pattern, existing imports)
    - backend/medieval_forge/database.py (AsyncSessionLocal pattern)
    - backend/tests/unit/test_models_branches.py (Wave 0 stub)
    - .planning/phases/08-.../08-RESEARCH.md §"Pattern 3" + §"SQLAlchemy 2.0 Branch CRUD"
  </read_first>
  <behavior>
    - Test: Branch(project_id='p1', name='main', is_main=True) round-trips via AsyncSession
    - Test: UniqueConstraint('project_id', 'name') rejects duplicate via IntegrityError
    - Test: original_idx_high_water defaults to 0
    - Test: create_branch('p1', 'experiment', parent_branch_id='<main_id>') inherits parent's original_idx_high_water
    - Test: ensure_main_branch('p1') returns existing main if present, else creates one with is_main=True
    - Test: delete_branch raises BranchProtectedError when is_main=True (D-15)
  </behavior>
  <action>
**Step 1 — `models.py`:** Append Branch class verbatim from RESEARCH Pattern 3 (above). Ensure imports include `Boolean, Integer, UniqueConstraint, ForeignKey, DateTime, String` from `sqlalchemy` and `Mapped, mapped_column` from `sqlalchemy.orm`.

**Step 2 — `services/branches/__init__.py`:** Empty file (package marker).

**Step 3 — `services/branches/service.py`:** New module with these functions:

```python
"""Phase 08 D-10/D-11/D-15/D-22: Branch CRUD + lazy main creation + idx inheritance."""
from __future__ import annotations
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import Branch


class BranchProtectedError(Exception):
    """D-15: main branch cannot be deleted via UI."""

class BranchNameTakenError(Exception):
    """D-13: unique constraint on (project_id, name)."""


async def ensure_main_branch(db: AsyncSession, project_id: str) -> Branch:
    """D-10 lazy-create: every project must have a 'main' branch on first touch.

    Idempotent — returns existing main if present.
    """
    existing = (await db.execute(
        select(Branch).where(Branch.project_id == project_id, Branch.is_main == True)
    )).scalar_one_or_none()
    if existing is not None:
        return existing
    branch = Branch(project_id=project_id, name="main", is_main=True)
    db.add(branch)
    await db.commit()
    await db.refresh(branch)
    return branch


async def create_branch(db: AsyncSession, project_id: str, name: str,
                        parent_branch_id: str | None) -> Branch:
    """D-11: explicit create. D-22: inherits original_idx_high_water from parent."""
    if not name or len(name) > 255 or not name.replace("-", "").replace("_", "").isalnum():
        raise ValueError("branch name must be 1-255 alphanumeric/-/_ characters")
    if name == "main":
        raise BranchNameTakenError("'main' is reserved; created lazily by ensure_main_branch")
    branch = Branch(project_id=project_id, name=name, is_main=False)
    if parent_branch_id:
        parent = (await db.execute(
            select(Branch).where(Branch.id == parent_branch_id)
        )).scalar_one()
        branch.original_idx_high_water = parent.original_idx_high_water
    db.add(branch)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise BranchNameTakenError(f"branch name '{name}' already exists") from exc
    await db.refresh(branch)
    return branch


async def list_branches(db: AsyncSession, project_id: str) -> list[Branch]:
    """D-13: sorted by updated_at desc (most-recent-edit first)."""
    return list((await db.execute(
        select(Branch).where(Branch.project_id == project_id)
                      .order_by(Branch.updated_at.desc())
    )).scalars())


async def rename_branch(db: AsyncSession, branch_id: str, new_name: str) -> Branch:
    """D-15: rename allowed on main."""
    if not new_name or len(new_name) > 255:
        raise ValueError("name length 1-255")
    branch = (await db.execute(select(Branch).where(Branch.id == branch_id))).scalar_one()
    branch.name = new_name
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise BranchNameTakenError(f"branch name '{new_name}' already exists") from exc
    await db.refresh(branch)
    return branch


async def delete_branch(db: AsyncSession, branch_id: str) -> None:
    """D-15: main is delete-protected."""
    branch = (await db.execute(select(Branch).where(Branch.id == branch_id))).scalar_one()
    if branch.is_main:
        raise BranchProtectedError("main branch cannot be deleted")
    await db.execute(delete(Branch).where(Branch.id == branch_id))
    await db.commit()
```

**Step 4 — `test_models_branches.py`:** Remove skip marker; implement 6 tests above using existing pytest-asyncio `db_session` fixture (check `backend/tests/conftest.py` — likely already exists; if not, create a minimal in-memory aiosqlite session fixture).
  </action>
  <verify>
    <automated>cd backend && python -m pytest tests/unit/test_models_branches.py -v -x</automated>
  </verify>
  <acceptance_criteria>
    - 6 unit tests pass
    - `python -c "from medieval_forge.models import Branch; from medieval_forge.services.branches.service import ensure_main_branch, create_branch, list_branches, rename_branch, delete_branch, BranchProtectedError, BranchNameTakenError; print('ok')"` prints ok
    - `grep -c "class Branch" backend/medieval_forge/models.py` returns 1
  </acceptance_criteria>
  <done>Branch model + service + unit tests committed.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: api/v3/branches.py router + main.py mount + integration tests</name>
  <files>backend/medieval_forge/api/v3/branches.py, backend/medieval_forge/main.py, backend/tests/integration/test_branches_endpoint.py</files>
  <read_first>
    - backend/medieval_forge/api/v3/projects.py (existing router pattern + pydantic body shape)
    - backend/medieval_forge/main.py (router mount pattern)
    - backend/medieval_forge/services/paths.py (is_valid_uuid helper)
    - backend/tests/integration/test_branches_endpoint.py (Wave 0 stub)
  </read_first>
  <behavior>
    - Test: POST /api/v3/projects/{pid}/branches with {"name":"experiment"} → 201 + branch JSON
    - Test: POST with name="main" → 400 (reserved name)
    - Test: POST with invalid name "exp lab" → 400 (invalid chars)
    - Test: POST duplicate name → 409
    - Test: GET /api/v3/projects/{pid}/branches → 200 + list ordered by updated_at desc; ensure_main_branch creates main if absent
    - Test: PATCH /api/v3/projects/{pid}/branches/{bid} with {"name":"renamed"} → 200
    - Test: DELETE main branch → 409 + error code BRANCH_PROTECTED
    - Test: DELETE non-main branch → 204
    - Test: invalid project_id (not UUID) → 400 via is_valid_uuid guard
  </behavior>
  <action>
**Step 1 — `api/v3/branches.py`:** Thin router delegating to service layer. Use prefix `/v3/projects/{project_id}/branches` (note: main.py adds `/api` prefix at mount → effective path `/api/v3/...`).

```python
"""Phase 08 D-10..D-15: Branch CRUD endpoints. Local-only — no auth (RESEARCH §Security Domain V13)."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from ..deps import get_db  # or wherever the AsyncSession dep lives
from ..services.paths import is_valid_uuid
from ..services.branches.service import (
    ensure_main_branch, create_branch, list_branches, rename_branch, delete_branch,
    BranchProtectedError, BranchNameTakenError,
)

router = APIRouter(prefix="/v3/projects/{project_id}/branches", tags=["v3-branches"])


class BranchCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_-]+$")
    parent_branch_id: str | None = None


class BranchRenameBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_-]+$")


def _guard_pid(project_id: str) -> None:
    if not is_valid_uuid(project_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "project_id must be UUID")


@router.get("")
async def list_endpoint(project_id: str, db: AsyncSession = Depends(get_db)):
    _guard_pid(project_id)
    await ensure_main_branch(db, project_id)  # lazy main
    return [{"id": b.id, "name": b.name, "is_main": b.is_main,
             "original_idx_high_water": b.original_idx_high_water,
             "edits_since_snapshot": b.edits_since_snapshot,
             "created_at": b.created_at.isoformat(),
             "updated_at": b.updated_at.isoformat()}
            for b in await list_branches(db, project_id)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_endpoint(project_id: str, body: BranchCreateBody,
                          db: AsyncSession = Depends(get_db)):
    _guard_pid(project_id)
    try:
        branch = await create_branch(db, project_id, body.name, body.parent_branch_id)
    except BranchNameTakenError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return {"id": branch.id, "name": branch.name, "is_main": branch.is_main}


@router.patch("/{branch_id}")
async def rename_endpoint(project_id: str, branch_id: str, body: BranchRenameBody,
                          db: AsyncSession = Depends(get_db)):
    _guard_pid(project_id)
    try:
        branch = await rename_branch(db, branch_id, body.name)
    except BranchNameTakenError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return {"id": branch.id, "name": branch.name}


@router.delete("/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endpoint(project_id: str, branch_id: str,
                          db: AsyncSession = Depends(get_db)):
    _guard_pid(project_id)
    try:
        await delete_branch(db, branch_id)
    except BranchProtectedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "BRANCH_PROTECTED", "message": "main branch cannot be deleted"}
        )
    return None
```

If the project doesn't have a `deps.py` with `get_db`, find the existing dependency pattern in another v3 router (likely `api/v3/projects.py` or `database.py` exports `get_db`).

**Step 2 — `main.py`:** Register router. Find the block where v3 routers are included (e.g., `app.include_router(projects.router, prefix='/api')`); add `from .api.v3 import branches; app.include_router(branches.router, prefix='/api')`.

**Step 3 — `test_branches_endpoint.py`:** Remove skip marker; implement 9 integration tests above using TestClient or httpx AsyncClient (whatever Phase 06/07 patterns use — read one existing integration test as template).
  </action>
  <verify>
    <automated>cd backend && python -m pytest tests/integration/test_branches_endpoint.py -v -x && python -c "from medieval_forge.main import app; routes=[r.path for r in app.routes]; assert any('/branches' in r for r in routes); print('ok')"</automated>
  </verify>
  <acceptance_criteria>
    - 9 integration tests pass
    - `curl -X GET http://localhost:8000/api/v3/projects/{uuid}/branches` returns 200 + list with main present
    - `grep -c "branches.router" backend/medieval_forge/main.py` returns 1
    - All 5 endpoints (GET list, POST create, PATCH rename, DELETE) responding correctly
  </acceptance_criteria>
  <done>Branches API mounted; integration suite green.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| HTTP → backend | Branch CRUD endpoints accept project_id (path), branch_id (path), name (body) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-08-03a-01 | Tampering | branch name SQL injection | mitigate | SQLAlchemy 2.0 ORM parameterized queries (verified — no raw SQL). Pydantic `pattern=r"^[a-zA-Z0-9_-]+$"` rejects any chars that could break templating in future logs. |
| T-08-03a-02 | Tampering | path traversal via project_id | mitigate | `is_valid_uuid` guard (existing Phase 05 helper) reused at every endpoint. |
| T-08-03a-03 | Information Disclosure | XSS via branch name in inspector | accept | React auto-escapes text; never use dangerouslySetInnerHTML for branch names (frontend plan 08-09 follows). |
| T-08-03a-04 | DoS | unbounded branches per project | accept | RESEARCH §Open Q4: no hard cap in Phase 8; surface count in picker. LRU deferred per D-23. |
</threat_model>

<verification>
- 1 ORM class + 1 service + 1 router + main.py mount
- 6 unit + 9 integration tests green
- Pre-existing Iberia parity unaffected (no cfg or pipeline changes here)
- 2 atomic commits
</verification>

<success_criteria>
Branch CRUD persistence + API live. Plans 08-03b (snapshots), 08-04 (frontend store), and 08-09 (BranchPicker UI) can consume `/api/v3/projects/{pid}/branches`.
</success_criteria>

<output>
After completion, create `.planning/phases/08-.../08-03a-SUMMARY.md`.
</output>
