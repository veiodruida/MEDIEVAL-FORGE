---
phase: 03
plan: 03
subsystem: backend/research-api
tags: [llm, research, sse, cache, sqlite, fastapi]
dependency_graph:
  requires: [03-01, 03-02]
  provides: [research-sse-endpoint, provider-discovery-endpoint, research-cache-table]
  affects: [backend/medieval_forge/api/, backend/medieval_forge/services/, backend/medieval_forge/models.py]
tech_stack:
  added: []
  patterns:
    - SSE asyncio.Queue producer pattern (mirrored from api/ingest.py)
    - SHA-256 cache key with 5-tuple (country_qid, period_start, period_end, provider, model)
    - app.state._test_session_factory injection for runner testability
    - validate_assignment_against_condados wraps provider before retry loop (T-3-08)
key_files:
  created:
    - backend/medieval_forge/services/research_cache.py
    - backend/medieval_forge/services/llm/prompt.py
    - backend/medieval_forge/services/research_runner.py
    - backend/medieval_forge/api/research.py
    - backend/medieval_forge/api/llm.py
    - backend/tests/unit/test_research_cache.py
    - backend/tests/unit/test_condado_assignment.py
    - backend/tests/integration/__init__.py
    - backend/tests/integration/test_research_sse.py
    - backend/tests/integration/test_providers_endpoint.py
  modified:
    - backend/medieval_forge/models.py (added ResearchCache)
    - backend/medieval_forge/main.py (lifespan creates all tables; research_router + llm_router registered)
decisions:
  - "app.state._test_session_factory injection: runner db_session_factory resolved via getattr(request.app.state, '_test_session_factory', AsyncSessionLocal) — allows integration tests to inject in-memory DB without patching the module-level global"
  - "Dependency injection for project existence check: trigger_research uses get_db dependency (not AsyncSessionLocal directly) so test overrides work for 404 checks"
  - "test_providers_endpoint: monkeypatches read_claude_cli_token to None to prevent live CLI credential file from making claude appear configured in test environments"
metrics:
  duration: "~40 minutes"
  completed: "2026-04-21"
  tasks: 3
  files: 12
---

# Phase 03 Plan 03: Research API + Cache + Provider Discovery Summary

Research orchestration layer built end-to-end: SQLite cache table, condado-aware prompt builder, SSE research runner wiring providers (Plan 01) + auth (Plan 02) + 3-retry loop + cache, and four endpoints exposed to the UI (Plan 04).

## What Was Built

### Endpoints Added

| Method | Path | Behavior |
|--------|------|----------|
| `POST` | `/api/projects/{id}/research?provider=X&force_refresh=bool` | Starts research run; streams `text/event-stream` SSE progress; validates UUID/provider/project before streaming; cancels task on client disconnect |
| `GET` | `/api/projects/{id}/research/cached?provider=X&model=Y` | Returns persisted cache payload as JSON; 404 if not cached |
| `GET` | `/api/llm/providers` | Returns machine-readable list of all registered providers (auto-discovered from PROVIDERS registry); each entry: `{provider_id, display_name, auth_methods, configured, healthy, default_model}` |
| `GET` | `/api/llm/health` | Returns `{provider_id: {healthy, message}}` for all providers |

### Cache Key Formula (verbatim)

```
SHA-256(f"{country_qid}:{period_start}:{period_end}:{provider}:{model}")
```

Example: `SHA-256("Q29:868:900:claude:claude-sonnet-4-6")` → 64-char hex string used as `research_cache.cache_key_hash` PRIMARY KEY.

### Table Schema

```sql
CREATE TABLE research_cache (
    cache_key_hash  TEXT(64) PRIMARY KEY,   -- SHA-256 hex
    payload         JSON     NOT NULL,       -- ResearchResult.model_dump()
    provider        TEXT(50) NOT NULL,
    model           TEXT(100) NOT NULL,
    country_qid     TEXT(20) NOT NULL,
    period_start    INTEGER  NOT NULL,
    period_end      INTEGER  NOT NULL,
    created_at      DATETIME NOT NULL
);
```

Table is created on app startup via `Base.metadata.create_all` (idempotent; no Alembic).

### SSE Message Shape (for Plan 04 UI)

```
data: starting claude (claude-sonnet-4-6)\n\n     ← run started
data: Tentativa 1/3: ...\n\n                       ← retry attempt (from run_with_retry)
data: cached\n\n                                   ← cache hit (force_refresh=False)
data: RESULT: {json...}\n\n                        ← final payload
data: DONE\n\n                                     ← stream end
data: ERROR: ExceptionType: message[:200]\n\n      ← on failure (T-3-12: truncated)
```

### Cache Hit Condition (for Plan 04 "cached" badge)

`GET /api/projects/{id}/research/cached?provider=X` returns 200 → show badge.
`GET /api/projects/{id}/research` stream emits `data: cached\n\n` as first event → also indicates hit.

### force_refresh URL Semantics (for Plan 04 button)

`POST /api/projects/{id}/research?provider=X&force_refresh=true` — bypasses cache, calls LLM, then updates cache with new result.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed `app.state` dict access pattern in research.py**
- **Found during:** Task 3 — SSE integration tests showed `run_research` always used real `AsyncSessionLocal` despite test override
- **Issue:** Endpoint used `request.app.state.__dict__.get(...)` but Starlette `State` stores in `_state` sub-dict, not top-level dict
- **Fix:** Changed to `getattr(request.app.state, "_test_session_factory", AsyncSessionLocal)`
- **Files modified:** `backend/medieval_forge/api/research.py`
- **Commit:** 680305f

**2. [Rule 1 - Bug] Fixed test_providers_endpoint: CLI credential interference**
- **Found during:** Task 3 — `test_get_providers_marks_unconfigured_when_no_credentials` failed because `~/.claude/.credentials.json` exists on the dev machine with a valid token
- **Fix:** Added `monkeypatch.setattr(auth_mod, "read_claude_cli_token", lambda: None)` to the test
- **Files modified:** `backend/tests/integration/test_providers_endpoint.py`
- **Commit:** 680305f

## Patterns Established for Plan 04

1. **SSE consumption**: Stream `POST /api/projects/{id}/research?provider=X`; collect `data:` lines; `data: DONE\n\n` signals completion; `data: ERROR:` signals failure; `data: cached\n\n` signals cache hit.
2. **Provider dropdown**: `GET /api/llm/providers` → render `display_name` for each entry; use `configured` + `healthy` booleans for status badges; `auth_methods[0].type` tells UI which setup flow to show.
3. **force_refresh**: Add `?force_refresh=true` query param to the research POST to bypass cache.
4. **Cached badge**: Check `GET /projects/{id}/research/cached?provider=X` at dialog open — 200 means cached, 404 means not cached.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `backend/medieval_forge/services/research_cache.py` | FOUND |
| `backend/medieval_forge/services/llm/prompt.py` | FOUND |
| `backend/medieval_forge/services/research_runner.py` | FOUND |
| `backend/medieval_forge/api/research.py` | FOUND |
| `backend/medieval_forge/api/llm.py` | FOUND |
| Commit 61d7eb3 (test scaffold) | FOUND |
| Commit 6fbe34e (model + cache + runner) | FOUND |
| Commit 680305f (api endpoints + main.py) | FOUND |
| 17 tests pass | VERIFIED |
