---
phase: quick-260426-qvu
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/medieval_forge/api/edit.py
  - backend/medieval_forge/services/project_meta.py
  - backend/tests/api/test_edit_api.py
autonomous: true
requirements:
  - ORPHAN-BUG-5
must_haves:
  truths:
    - "Calling POST /projects/{id}/territories/{cid}/recalc bumps Project.updated_at"
    - "Calling POST /projects/{id}/territories/merge bumps Project.updated_at"
    - "Calling POST /projects/{id}/territories/{cid}/split bumps Project.updated_at"
    - "Calling PATCH /projects/{id}/territories/{cid}/geometry bumps Project.updated_at"
    - "Calling POST /projects/{id}/geometry/save bumps Project.updated_at"
    - "Each bump happens in the same async transaction as the mutation (single commit)"
    - "Bumping a non-existent project_id does NOT raise — it is a no-op (test path uses synthetic UUIDs without DB rows)"
  artifacts:
    - path: "backend/medieval_forge/services/project_meta.py"
      provides: "touch_project(session, project_id) shared helper"
      exports: ["touch_project"]
    - path: "backend/medieval_forge/api/edit.py"
      provides: "Edit endpoints calling touch_project + commit"
      contains: "touch_project"
    - path: "backend/tests/api/test_edit_api.py"
      provides: "Regression test asserting updated_at strictly advances"
      contains: "test_updated_at_bumps"
  key_links:
    - from: "backend/medieval_forge/api/edit.py"
      to: "backend/medieval_forge/services/project_meta.py"
      via: "import + await touch_project(session, project_id) before session.commit()"
      pattern: "touch_project\\(session"
    - from: "touch_project"
      to: "Project.updated_at"
      via: "UPDATE projects SET updated_at = :now WHERE id = :pid"
      pattern: "Project\\.updated_at|update\\(Project\\)"
---

<objective>
Bump `Project.updated_at` on every Phase 4 edit endpoint mutation (move_capital, reshape_geometry, merge, split, save_geometry_snapshot) inside the same DB transaction as the mutation. Closes orphan bug #5 from `.planning/phases/04-canvas-editing-basic/04-HUMAN-UAT.md` (line 179).

Purpose: Architecturally clean staleness signal — clients/UI/tests can rely on `updated_at` to detect post-edit state. Currently neutralized by no-cache headers but that masks the real bug.

Output:
- New shared helper `services/project_meta.py::touch_project(session, project_id)`
- All 5 edit endpoints call helper + `session.commit()` after their mutation in the same async transaction
- Regression test that asserts `updated_at` strictly advances after each endpoint call
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@backend/medieval_forge/api/edit.py
@backend/medieval_forge/models.py
@backend/medieval_forge/database.py
@backend/tests/api/test_edit_api.py

<interfaces>
<!-- From backend/medieval_forge/models.py -->
```python
class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    # ...
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )
```

Note: `onupdate=_utcnow` only fires when SQLAlchemy issues an UPDATE through the ORM
on a tracked Project instance. Disk-level `save_territories()` writes to GeoJSON
files — they do NOT touch the `projects` table — so `updated_at` is never bumped.
Fix: explicitly UPDATE the row.

<!-- From backend/medieval_forge/api/edit.py — all 5 endpoints accept session via Depends(get_db) but currently never use it -->
- POST `/projects/{project_id}/territories/{condado_id}/recalc` (move_capital)
- POST `/projects/{project_id}/territories/merge`
- POST `/projects/{project_id}/territories/{condado_id}/split`
- PATCH `/projects/{project_id}/territories/{condado_id}/geometry` (reshape_geometry)
- POST `/projects/{project_id}/geometry/save` (save_geometry_snapshot)

<!-- From backend/tests/api/test_edit_api.py -->
- Tests use synthetic UUID `aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee` with NO Project row inserted in DB
- `db_session` fixture uses in-memory SQLite + Base.metadata.create_all
- `territory_files` fixture seeds disk GeoJSON only
- Therefore: `touch_project` MUST handle missing Project row gracefully (no-op, no exception)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add touch_project helper + wire into 5 edit endpoints</name>
  <files>
    backend/medieval_forge/services/project_meta.py,
    backend/medieval_forge/api/edit.py
  </files>
  <behavior>
    - touch_project(session, project_id) issues UPDATE projects SET updated_at = :now WHERE id = :pid
    - If no row matches (rowcount == 0) → no-op, no exception (handles test fixtures with synthetic UUIDs)
    - Uses datetime.now(timezone.utc) for the timestamp (matches models._utcnow)
    - Does NOT call session.commit() — caller owns transaction boundary
    - Each of the 5 endpoints in api/edit.py calls `await touch_project(session, project_id)` AFTER the disk save_territories() call but BEFORE returning, then awaits `session.commit()` so the bump is persisted
    - Bump and disk write are wrapped in a try/except: if save_territories raises, no commit happens (no half-bumped state). If touch_project raises, the disk write has already happened so we log and proceed (disk is already authoritative for territories).
    - For endpoints with `persist=False` query param (move_capital, merge, split, reshape_geometry): skip the bump when persist is False (no mutation occurred)
  </behavior>
  <action>
1. Create `backend/medieval_forge/services/project_meta.py`:
   ```python
   """Shared helper for bumping Project.updated_at on edit endpoints."""
   from __future__ import annotations
   from datetime import datetime, timezone
   from sqlalchemy import update
   from sqlalchemy.ext.asyncio import AsyncSession
   from ..models import Project

   async def touch_project(session: AsyncSession, project_id: str) -> bool:
       """Bump Project.updated_at to now(UTC). No-op if project_id has no DB row.

       Returns True if a row was updated, False otherwise. Does NOT commit —
       caller owns the transaction so the bump can be batched with other writes.
       """
       result = await session.execute(
           update(Project)
           .where(Project.id == project_id)
           .values(updated_at=datetime.now(timezone.utc))
       )
       return result.rowcount > 0
   ```

2. In `backend/medieval_forge/api/edit.py`:
   - Add import at top: `from ..services.project_meta import touch_project`
   - In `move_capital`: after `await save_territories(...)` inside the `if persist:` block, add `await touch_project(session, project_id); await session.commit()`
   - In `merge_territories_endpoint`: same pattern after `save_territories` inside `if persist:`
   - In `split_territory_endpoint`: same pattern after `save_territories` inside `if persist:`
   - In `reshape_geometry`: same pattern after `save_territories` inside `if persist:`
   - In `save_geometry_snapshot`: after `await save_territories(project_id, merged)` (always persists), add `await touch_project(session, project_id); await session.commit()`

3. Use a single shared helper — do NOT duplicate `datetime.now(timezone.utc)` or `update(Project)` statements in the endpoints. The helper is the single source of truth for the bump SQL.

4. Do NOT remove the `Depends(get_db)` parameter from any endpoint — it is now actively used.
  </action>
  <verify>
    <automated>cd backend && python -m pytest tests/api/test_edit_api.py -x -q</automated>
  </verify>
  <done>
    - `services/project_meta.py` exists and exports `touch_project`
    - All 5 endpoints in `api/edit.py` import and call `touch_project` followed by `session.commit()` inside their persist branch
    - Existing `test_edit_api.py` tests still pass (the no-op behavior on missing Project row preserves backwards compat with the synthetic-UUID fixtures)
    - No duplicated `update(Project)` or `datetime.now(timezone.utc)` calls in `edit.py` — only the helper call
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Regression test — updated_at strictly advances after each edit endpoint</name>
  <files>backend/tests/api/test_edit_api.py</files>
  <behavior>
    - New test `test_updated_at_bumps_after_each_edit_endpoint` (or one test per endpoint, whichever stays under 60s):
      - Inserts a real `Project` row into the in-memory DB with a known initial `updated_at` (e.g. `datetime(2020, 1, 1, tzinfo=timezone.utc)`)
      - For each of the 5 endpoints (recalc, merge, split, reshape_geometry, geometry/save):
        - Records `before = project.updated_at` (re-fetch from DB to avoid stale ORM cache)
        - Calls the endpoint with a valid payload (reuse the existing fixture polygons)
        - Asserts response is 200
        - Re-fetches Project from DB (use `await session.refresh(project)` or fresh `session.get(Project, PROJECT_ID)`)
        - Asserts `project.updated_at > before` (STRICT inequality — proves the bump happened)
    - Uses `asyncio.sleep(0.001)` between consecutive endpoint calls only if datetime resolution on the host could otherwise produce equal timestamps; prefer `datetime.now(timezone.utc)` resolution which is microsecond-level on Windows/Linux so usually no sleep needed. If flakiness appears, add the sleep.
    - Test runs under existing `client` + `db_session` + `territory_files` fixtures; project row insertion happens inside the test body, not the fixture (keeps existing tests untouched)
  </behavior>
  <action>
1. Add a new async test to `backend/tests/api/test_edit_api.py` that:
   - Imports `from datetime import datetime, timezone` and `from medieval_forge.models import Project`
   - Inserts a `Project(id=PROJECT_ID, name="test", country_qid="Q29", period_start=1000, period_end=1100, updated_at=datetime(2020,1,1,tzinfo=timezone.utc))` via `db_session`
   - Commits, then for each endpoint:
     - Re-reads `Project.updated_at` from DB
     - POSTs/PATCHes the endpoint via `client`
     - Asserts 200
     - Uses a fresh session query to verify `updated_at > before`

2. Suggested payloads (reuse existing constants):
   - move_capital: `POST /projects/{PROJECT_ID}/territories/leon/recalc` with `{"lon": -5.6, "lat": 42.4}`
   - merge: `POST /projects/{PROJECT_ID}/territories/merge` with `{"primary_id": "leon", "condado_ids": ["leon", "castela"]}`
   - split: `POST /projects/{PROJECT_ID}/territories/leon/split` with `{"cut_line": BISECTING_CUT_LINE}`
   - reshape: `PATCH /projects/{PROJECT_ID}/territories/leon/geometry` with `{"geometry": LEON_POLYGON}`
   - save: `POST /projects/{PROJECT_ID}/geometry/save` with `{"territories": {"leon": LEON_POLYGON}, "capitals": {}}`

3. IMPORTANT — datetime comparison: SQLite via aiosqlite may return naive datetimes. Normalize both sides before comparing, e.g.:
   ```python
   def _aware(dt):
       return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
   assert _aware(after) > _aware(before)
   ```

4. If the merge/split mutate state in ways that break the next endpoint call (e.g., merge removes "castela", split renames "leon"), order the assertions per endpoint as INDEPENDENT sub-tests (each rebuilding a fresh Project + fresh territories), or run the bump-check on a single endpoint per test function with parameterization via `@pytest.mark.parametrize`. Pick whichever is simpler — preference: `parametrize` over endpoint name + payload builder, with fresh `territory_files` fixture per parameter.
  </action>
  <verify>
    <automated>cd backend && python -m pytest tests/api/test_edit_api.py -x -q -k updated_at</automated>
  </verify>
  <done>
    - At least one test (or 5 parameterized tests) exists that asserts `Project.updated_at` strictly advances after each of the 5 edit endpoints
    - Test passes against the implementation from Task 1
    - Test would FAIL against the pre-Task-1 code (no bump) — manually verifiable by reverting Task 1
    - Full `test_edit_api.py` suite still green
  </done>
</task>

</tasks>

<verification>
- `cd backend && python -m pytest tests/api/test_edit_api.py -x -q` → all green
- Grep `touch_project` in `api/edit.py` → 5 call sites (one per endpoint)
- Grep `update(Project)` in `api/edit.py` → 0 matches (logic lives only in the helper)
</verification>

<success_criteria>
- All 5 edit endpoints bump `Project.updated_at` after a successful mutation
- Bump uses a single shared helper (`services/project_meta.py::touch_project`)
- Bump + disk write share the same async transaction (single `session.commit()` per request)
- Regression test asserts strict advancement of `updated_at` after each endpoint
- Existing test suite remains green
</success_criteria>

<output>
After completion, create `.planning/quick/260426-qvu-fix-orphan-bug-project-updated-at-not-bu/260426-qvu-SUMMARY.md`
</output>
