---
phase: 07-llm-research-as-opt-in-metadata-layer
plan: 01
subsystem: backend/db+services
tags: [llm, credentials, alembic, cache, sqlalchemy]
requires:
  - alembic migration 0005 head
  - medieval_forge.models.Base + _utcnow
  - sqlalchemy 2.x async session pattern (database.py)
provides:
  - models.LLMCredential (provider_id PK)
  - models.ResearchCache (cache_key SHA-256 PK, generated_at column)
  - services.credential_store.{get,store,delete}_credentials async CRUD
  - alembic migration 0006 (idempotent upgrade/downgrade)
  - pytest marker `anthropic` for Plan 04/11 integration tests
affects:
  - backend/medieval_forge/models.py (+49 lines, 2 new classes)
  - pyproject.toml (+1 marker)
tech-stack:
  added: []
  patterns:
    - "SQLAlchemy 2.x Mapped/mapped_column"
    - "Async session via aiosqlite (matches database.py)"
    - "Alembic offline-mode round-trip (sql-only verification)"
    - "Content-addressable cache decoupled from credential lifecycle (REVIEWS fix #8)"
key-files:
  created:
    - alembic/versions/0006_create_llm_credentials_and_research_cache.py
    - backend/medieval_forge/services/credential_store.py
    - backend/tests/unit/test_credential_store.py
  modified:
    - backend/medieval_forge/models.py
    - pyproject.toml
decisions:
  - "REVIEWS fix #2: ResearchCache uses `generated_at` (not `created_at`) to disambiguate from research_overlay.meta.json::applied_at (Plan 07b)"
  - "REVIEWS fix #8: provider_id is enum-string PK; no FK; delete_credentials does NOT cascade to research_cache (cache is content-addressable, outlives keys)"
  - "Discretion #1: payload stored as plaintext JSON; OS-keyring escrow deferred to v3.1"
  - "Discretion #6: Alembic migration over inline CREATE TABLE"
  - "clear_credentials kept as back-compat alias; new code must use delete_credentials"
metrics:
  duration: "~30 min"
  tasks_completed: 3
  files_created: 3
  files_modified: 2
  tests_added: 5
  completed: 2026-05-14
---

# Phase 07 Plan 01: LLM credential store + research cache DB foundation Summary

DB foundation for Phase 07 LLM research: SQLAlchemy `LLMCredential` + `ResearchCache` models, Alembic migration 0006, and async CRUD in `services/credential_store.py` — all downstream Wave 1-3 plans (04 Claude provider, 07a cache, 07b runner) can now import freely.

## What was built

### Models (`backend/medieval_forge/models.py`)

- **`LLMCredential`** — `__tablename__ = "llm_credentials"`, columns: `provider_id` (`String(50)` PK), `credential_type`, `payload` (JSON), `created_at`, `updated_at`. Class docstring documents Discretion #1 plaintext payload + REVIEWS fix #8 cascade boundary.
- **`ResearchCache`** — `__tablename__ = "research_cache"`, columns: `cache_key` (`String(64)` SHA-256 hex PK), `payload` (JSON), `provider`, `model`, **`generated_at`** (REVIEWS fix #2 — renamed from `created_at`). Class docstring documents the independent lifecycle from `LLMCredential`.

### Migration (`alembic/versions/0006_create_llm_credentials_and_research_cache.py`)

- `revision = "0006"`, `down_revision = "0005"`.
- `upgrade()` calls `op.create_table` for both tables (DDL matches model column types exactly).
- `downgrade()` drops both tables in reverse order.
- Verified: offline `alembic upgrade 0005:0006 --sql` produces expected `CREATE TABLE` statements; full `upgrade head` + `downgrade -1` + `upgrade head` round-trip runs cleanly against the user's real DB.

### Credential store (`backend/medieval_forge/services/credential_store.py`)

Three async functions backed by the `LLMCredential` table:

- `get_credentials(session, provider_id) -> dict | None`
- `store_credentials(session, provider_id, payload)` — upsert
- `delete_credentials(session, provider_id)` — does NOT cascade to `ResearchCache` (REVIEWS fix #8)
- `clear_credentials = delete_credentials` — back-compat alias for legacy callers

Module header documents REVIEWS fix #8 cascade behavior in two places (header comment + `delete_credentials` docstring).

### Tests (`backend/tests/unit/test_credential_store.py`)

5 async unit tests using the in-memory aiosqlite `db_session` fixture from `backend/tests/conftest.py`:

1. `test_store_then_get_round_trips_payload_for_claude`
2. `test_get_credentials_returns_none_when_provider_absent`
3. `test_delete_credentials_deletes_row`
4. `test_store_credentials_upserts_existing_row`
5. `test_delete_credentials_does_not_cascade_to_research_cache` — REVIEWS fix #8 contract enforcement

All 5 pass: `pytest backend/tests/unit/test_credential_store.py -q` → `5 passed, 46 warnings in 0.05s` (warnings are unrelated Python 3.14 asyncio policy deprecations).

### pytest marker

`pyproject.toml` `[tool.pytest.ini_options].markers` gains `"anthropic: integration tests that require Anthropic SDK + live or mocked claude credentials"` — verified via `pytest --markers | grep '^@pytest.mark.anthropic'`.

## Commits

| Task | Hash    | Subject                                                                  |
|------|---------|--------------------------------------------------------------------------|
| 1    | 7eb2f33 | feat(07-01): add LLMCredential + ResearchCache models + anthropic marker |
| 2    | 00debfd | feat(07-01): add Alembic migration 0006 — llm_credentials + research_cache |
| 3    | cc4697c | feat(07-01): add credential_store CRUD + REVIEWS fix #8 cascade tests    |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Repo layout: `alembic/` and `pyproject.toml` are at root, not in `backend/`**
- **Found during:** Task 2 (writing migration 0006) and Task 1 (marker registration).
- **Issue:** Plan repeatedly referenced `backend/alembic/versions/...`, `backend/pyproject.toml`, and `cd backend && pytest` / `cd backend && alembic ...`. The actual repo layout puts `alembic/versions/` and `pyproject.toml` at the repo root (verified against migrations 0001–0005 + the existing `pyproject.toml` which configures `pythonpath = ["backend"]` and `testpaths = ["backend/tests"]`).
- **Fix:** Created migration at `alembic/versions/0006_create_llm_credentials_and_research_cache.py` (consistent with 0001-0005). Marker added to root `pyproject.toml`. Verification commands run from repo root with `PYTHONPATH=backend`.
- **Files modified:** As above — paths reflected in commit messages and frontmatter.
- **Commits:** 7eb2f33, 00debfd.

**2. [Rule 3 — Blocking] `alembic env.py` hardcodes `DB_URL` from `database.py`, ignoring `-x sqlalchemy.url=...`**
- **Found during:** Task 2 verification.
- **Issue:** The plan's <behavior> Test 3 implies the migration should be testable against an isolated DB. `alembic/env.py` does `config.set_main_option("sqlalchemy.url", DB_URL)` unconditionally, so neither `-x sqlalchemy.url=...` nor `MEDIEVAL_FORGE_DB_URL` env override took effect — every `alembic upgrade head` invocation hits the user's real `~/.medieval-forge/medieval_forge.db`.
- **Fix:** (a) Offline `--sql` mode (`alembic upgrade 0005:0006 --sql`) was used to verify the generated DDL matches the model spec without touching the live DB. (b) Once verified safe, the live DB was used for `upgrade head` / `downgrade -1` / `upgrade head` round-trip — only DDL on new tables, no risk to existing rows.
- **Note:** The env.py limitation is pre-existing (not in this plan's scope). Logged for future hardening; offline SQL verification covered the migration acceptance criteria. Test 3 ("Base.metadata.create_all() ALSO creates the tables") is covered implicitly by the conftest `db_session` fixture, which does exactly that and is the substrate of all 5 unit tests.

### Auth gates

None. No human action required.

## Verification

| Check                                                                                | Status |
|--------------------------------------------------------------------------------------|--------|
| `python -c "from medieval_forge.models import LLMCredential, ResearchCache"` exits 0 | PASS   |
| `alembic upgrade head` applies migration 0006 cleanly (with `PYTHONPATH=backend`)    | PASS   |
| `alembic downgrade -1 && alembic upgrade head` round-trip                            | PASS   |
| `pytest backend/tests/unit/test_credential_store.py -q` → 5 passed                   | PASS   |
| `pytest --markers \| grep '^@pytest.mark.anthropic'` returns 1 match                 | PASS   |
| `grep "print\\(.*payload\\|logger.*payload" credential_store.py` returns 0 matches   | PASS (T-07-01-03) |
| `grep "REVIEWS fix #8" credential_store.py` returns ≥2 matches                       | PASS (T-07-01-05) |
| `grep "REVIEWS fix #8" models.py` returns ≥1 match (ResearchCache docstring)         | PASS   |

## Handoff to next waves

- **Plan 04 (Claude provider)** can `from medieval_forge.services.credential_store import get_credentials` for D-07 step 2 of the auth resolution chain.
- **Plan 07a (research cache)** can `from medieval_forge.models import ResearchCache` and write rows with `generated_at = datetime.now(timezone.utc)`.
- **Plan 07b (runner + overlay merge)** can read `ResearchCache.generated_at` and copy it into `research_overlay.meta.json::generated_at` on cache-hit paths.
- **Plans 04 + 11** can use `@pytest.mark.anthropic` without `PytestUnknownMarkWarning`.

## Self-Check: PASSED

- `alembic/versions/0006_create_llm_credentials_and_research_cache.py` — FOUND
- `backend/medieval_forge/services/credential_store.py` — FOUND
- `backend/tests/unit/test_credential_store.py` — FOUND
- Commit 7eb2f33 — FOUND
- Commit 00debfd — FOUND
- Commit cc4697c — FOUND
