---
phase: 01-data-pipeline-backend-scaffold
reviewed: 2026-04-16T00:00:00Z
depth: standard
files_reviewed: 33
files_reviewed_list:
  - alembic/env.py
  - alembic/versions/0001_create_projects.py
  - backend/medieval_forge/__init__.py
  - backend/medieval_forge/api/__init__.py
  - backend/medieval_forge/api/export.py
  - backend/medieval_forge/api/generate.py
  - backend/medieval_forge/api/ingest.py
  - backend/medieval_forge/api/projects.py
  - backend/medieval_forge/cli.py
  - backend/medieval_forge/database.py
  - backend/medieval_forge/lib/map_generator.py
  - backend/medieval_forge/main.py
  - backend/medieval_forge/models.py
  - backend/medieval_forge/schemas.py
  - backend/medieval_forge/services/__init__.py
  - backend/medieval_forge/services/export.py
  - backend/medieval_forge/services/generator.py
  - backend/medieval_forge/services/ingest_osm.py
  - backend/medieval_forge/services/ingest_runner.py
  - backend/medieval_forge/services/ingest_wikidata.py
  - backend/medieval_forge/services/paths.py
  - backend/tests/conftest.py
  - backend/tests/test_cli.py
  - backend/tests/test_export.py
  - backend/tests/test_generate.py
  - backend/tests/test_ingest.py
  - backend/tests/test_packaging.py
  - backend/tests/test_projects.py
  - frontend/src/api/client.ts
  - frontend/src/App.tsx
  - frontend/src/main.tsx
  - frontend/src/pages/ProjectDetail.tsx
  - frontend/src/pages/ProjectList.tsx
  - frontend/src/pages/ProjectNew.tsx
findings:
  critical: 1
  warning: 5
  info: 5
  total: 11
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-04-16
**Depth:** standard
**Files Reviewed:** 33
**Status:** issues_found

## Summary

Phase 1 delivers a well-structured FastAPI backend scaffold with async SQLAlchemy, a clean project CRUD API, two ingest adapters (Wikidata SPARQL and OSM Overpass), a map generation wrapper, a Unity ZIP export service, and a React/TypeScript frontend. Security mitigations (T-PATH UUID validation, T-SSRF input guards) are consistently applied. The overall code quality is high for a scaffold phase.

The single Critical issue is a **global `importlib.reload` monkey-patch** in `generator.py` that mutates the shared `importlib` module object for the duration of every generation run — creating a race condition in any concurrent execution scenario. There are also five Warnings covering logic errors, a missing sentinel-flush in the SSE consumer, and a schema gap that permits clients to set arbitrary statuses.

---

## Critical Issues

### CR-01: Global `importlib.reload` monkey-patch creates a race condition

**File:** `backend/medieval_forge/services/generator.py:96`

**Issue:** `_patch_reload_for_synthetic` replaces `importlib.reload` on the actual `importlib` module object (`_importlib_mod.reload = _safe_reload`) for the entire duration of `generate_maps`. Because `importlib` is a singleton in Python's module cache, any other code in the same process that calls `importlib.reload()` concurrently — including other background generation tasks triggered by parallel API requests — will execute the patched function instead of the real one. If a second project's generation starts while the first is running, the patch installed for project A may silently suppress the reload that project B's pipeline expects, or vice versa. The patch is also applied to the module's `__dict__` directly, bypassing Python's descriptor protocol and any import hooks.

**Fix:** Keep the patch scoped to `map_generator`'s own namespace only (not the shared module):

```python
@contextmanager
def _patch_reload_for_synthetic(synthetic_module_name: str):
    _real_reload = importlib.reload

    def _safe_reload(module: types.ModuleType) -> types.ModuleType:
        if getattr(module, "__name__", None) == synthetic_module_name:
            return module
        return _real_reload(module)

    # Patch only in map_generator's local namespace, not the global importlib object.
    map_generator.importlib.reload = _safe_reload  # type: ignore[attr-defined]
    try:
        yield
    finally:
        map_generator.importlib.reload = _real_reload  # type: ignore[attr-defined]
```

This confines the patch to `map_generator`'s own reference to `importlib.reload`, leaving the global `importlib` module untouched and making concurrent generation tasks safe.

---

## Warnings

### WR-01: Duplicate `_cleanup_territory_module` definition silently shadows the first

**File:** `backend/medieval_forge/services/generator.py:68` and `backend/medieval_forge/services/generator.py:103`

**Issue:** `_cleanup_territory_module` is defined twice — once at line 68 and again at line 103 (identical body: `sys.modules.pop(name, None)`). Python silently replaces the first definition with the second. While the result is identical here, this is dead code that indicates a copy-paste error during refactoring and will confuse future readers who may modify one definition and miss the other.

**Fix:** Remove the first definition at line 68; keep only the one at line 103, which is closer to its callers.

---

### WR-02: SSE consumer never drains the queue sentinel on task cancellation

**File:** `backend/medieval_forge/api/ingest.py:43-48`

**Issue:** In `_sse_generator`, when the client disconnects, the `finally` block cancels the producer task and awaits it. However, the `asyncio.Queue` may still hold unconsumed messages — including the mandatory `None` sentinel that `run_ingest` always puts before returning. If the producer is cancelled after putting `None` into the queue but before the consumer reads it, the queue holds the sentinel permanently. For this endpoint the queue is ephemeral (one per request), so there is no resource leak. The real risk is a subtle ordering issue: the `finally` block calls `await task` which raises `CancelledError` (or swallows it), but does not drain the queue. If future changes make the queue bounded, this could deadlock because the producer may block on `queue.put()` while the consumer is stuck in `await task`.

Additionally, the `finally` block catches both `asyncio.CancelledError` and `Exception` in a single broad clause. `CancelledError` should be re-raised in most asyncio patterns to allow proper task cancellation propagation; swallowing it here is intentional (the generator is a consumer, not a task), but this should be explicit.

**Fix:**

```python
finally:
    if not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass  # expected — we cancelled it
        except Exception:  # noqa: BLE001
            pass
    # Drain any remaining messages so the queue does not hold references.
    while not queue.empty():
        queue.get_nowait()
```

---

### WR-03: `ProjectUpdate` schema exposes `status` as a free-form string field

**File:** `backend/medieval_forge/schemas.py:44`

**Issue:** `ProjectUpdate` includes `status: str | None = None` with no validation. The PATCH endpoint (`api/projects.py:70`) directly writes whatever value the client sends to `project.status`. This means any client can set a project to `status="generated"` or `status="exported"` without actually running the pipeline — which the test suite itself exploits (`test_export.py:102`). This bypasses the business logic guards in `api/export.py` that rely on `project.status` being trustworthy. While this is a local tool (not multi-user), it is an internal invariant violation that makes the status field unreliable as a gate.

**Fix:** Add a validator to whitelist allowed status transitions via PATCH, or remove `status` from `ProjectUpdate` entirely and only allow it to be set through the pipeline endpoints:

```python
_ALLOWED_STATUSES: frozenset[str] = frozenset({
    "created", "ingested", "generating", "generated",
    "error_ingesting", "error_generating", "exported",
})

@field_validator("status")
@classmethod
def _validate_status(cls, v: str | None) -> str | None:
    if v is not None and v not in _ALLOWED_STATUSES:
        raise ValueError(f"status must be one of {sorted(_ALLOWED_STATUSES)}")
    return v
```

---

### WR-04: `database.py` runs `mkdir` at module import time

**File:** `backend/medieval_forge/database.py:15`

**Issue:** `DATA_DIR.mkdir(parents=True, exist_ok=True)` executes when the module is imported — which happens during every test run, during alembic invocations, and during `from medieval_forge.database import DB_URL` in `alembic/env.py`. This creates the real `~/.medieval-forge` directory on disk even when tests are using an in-memory SQLite database. The test fixtures correctly redirect `PROJECTS_ROOT` (in `paths.py`), but `DATA_DIR` is never redirected, so the real home directory directory is always created. On CI systems this may fail with permission errors or pollute the runner's home directory.

**Fix:** Move the `mkdir` call into a function that is called explicitly during startup (e.g., in the `lifespan` function in `main.py` and in the `start` CLI command), rather than at import time:

```python
# database.py — remove side-effectful call at module level
DATA_DIR: Path = Path.home() / ".medieval-forge"
DB_URL: str = f"sqlite+aiosqlite:///{DATA_DIR}/medieval_forge.db"

def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
```

---

### WR-05: `load_territory_data` uses dynamic `importlib.import_module` on an attacker-controlled string

**File:** `backend/medieval_forge/lib/map_generator.py:193-197`

**Issue:** `load_territory_data(module_name)` calls `importlib.import_module(module_name)` where `module_name` is passed in from the caller. In the normal pipeline flow (`generator.py`), this is a synthetic module name constructed deterministically from a validated UUID (`_mf_territory_{uuid}`), so the attack surface is limited. However, the function is public in the lib module. If any future code path calls `load_territory_data` directly with unvalidated input, an attacker could supply a module name like `os` or `subprocess` and gain arbitrary code execution through subsequent attribute access on the returned values. The `importlib.reload(mod)` call that immediately follows further widens the window.

**Fix:** The generator service's approach (injecting a synthetic module and patching reload) already mitigates this for the API path. Add a guard in `load_territory_data` to enforce the naming convention:

```python
_ALLOWED_MODULE_PATTERN = re.compile(r'^_mf_territory_[0-9a-f_]+$|^territory_data')

def load_territory_data(module_name: str = "territory_data_v3"):
    if not _ALLOWED_MODULE_PATTERN.match(module_name):
        raise ValueError(f"module_name {module_name!r} does not match allowed pattern")
    import importlib
    mod = importlib.import_module(module_name)
    importlib.reload(mod)
    return mod.KINGDOMS, mod.DUCHIES, mod.CONDADOS
```

---

## Info

### IN-01: `map_generator.py` uses hardcoded absolute font path (Linux-only)

**File:** `backend/medieval_forge/lib/map_generator.py:608-609`

**Issue:** The font is loaded from `/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf` — an absolute path that does not exist on Windows or macOS. The code correctly falls back to `ImageFont.load_default()` in the `except` clause, but the bare `except:` at line 610 silently catches all exceptions including `KeyboardInterrupt` and `SystemExit`. The tool is described as cross-platform (the CLI targets Windows in the comment at generator.py:140).

**Fix:** Narrow the exception and use a cross-platform font search:

```python
try:
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", 11)
except (OSError, IOError):
    font = ImageFont.load_default()
```

---

### IN-02: `generate.py` imports `json`, `math`, `os`, `sys` on a single comma-separated line

**File:** `backend/medieval_forge/lib/map_generator.py:37`

**Issue:** `import json, math, os, sys` is a PEP 8 violation (E401 — multiple imports on one line). While not a bug, it reduces readability and will trigger linters that run in CI.

**Fix:** Split into one import per line.

---

### IN-03: `conftest.py` db_session fixture leaks a session if test throws before `yield`

**File:** `backend/tests/conftest.py:11-17`

**Issue:** The `db_session` fixture creates the engine, runs `create_all`, creates a session with `async with session_factory() as session:`, then yields. If a test itself raises an exception before the fixture's teardown can run, the `async with` context manager will close the session, but `engine.dispose()` at line 17 is in the same `async with` block scope — it only runs after the `async with session_factory()` block exits. The fixture pattern should place `engine.dispose()` in a `try/finally` or after the session context, regardless of test outcome. Currently `engine.dispose()` is inside the session block; if the session fails to close (e.g., due to a coroutine error), `dispose` will not run.

**Fix:**

```python
@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            yield session
    finally:
        await engine.dispose()
```

---

### IN-04: `useGenerate` hook does not guard against undefined `projectId`

**File:** `frontend/src/api/client.ts:122`

**Issue:** `useGenerate(projectId: string | undefined)` uses `projectId` directly in the `mutationFn` URL without a null check. If `mutate()` is called when `projectId` is `undefined`, the request will go to `/api/projects/undefined/generate`, which will return a 400 (UUID validation fails server-side), but the error message shown to the user will be confusing. The `useProject` hook already guards against this with `enabled: Boolean(id)`, but mutation hooks have no equivalent built-in guard.

**Fix:**

```typescript
mutationFn: async (territoryData?: Record<string, unknown>) => {
  if (!projectId) throw new Error('projectId is required')
  // ...
}
```

---

### IN-05: `useIngestStream` source parameter is not URL-encoded

**File:** `frontend/src/api/client.ts:158`

**Issue:** The `source` parameter is interpolated directly into the URL string: `` `/api/projects/${projectId}/ingest?source=${source}` ``. The TypeScript type constrains `source` to `'wikidata' | 'osm'` which are both safe ASCII, so there is no immediate injection risk. However, the pattern of raw string interpolation into URLs is fragile and should use `URLSearchParams` for correctness and future-proofing.

**Fix:**

```typescript
const params = new URLSearchParams({ source })
const res = await fetch(
  `/api/projects/${projectId}/ingest?${params}`,
  { method: 'POST' },
)
```

---

_Reviewed: 2026-04-16_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
