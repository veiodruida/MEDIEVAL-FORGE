---
phase: quick-260422-l7g
plan: 01
subsystem: backend-schemas, backend-services, frontend-research
tags: [bug-fix, multi-country, persistence, alembic, research-flow]
dependency_graph:
  requires: []
  provides: [multi-country-qid-storage, period-persistence, preset-multi-country]
  affects: [research-pipeline, territory-ingestion, llm-prompt-generation]
tech_stack:
  added: []
  patterns: [comma-separated-qid-list, pydantic-multi-token-validator, patch-before-research]
key_files:
  created:
    - alembic/versions/0002_widen_country_qid_multi_country.py
  modified:
    - backend/medieval_forge/models.py
    - backend/medieval_forge/schemas.py
    - backend/medieval_forge/services/countries.py
    - backend/tests/test_projects.py
    - frontend/src/components/research/ResearchDialog.tsx
    - frontend/src/components/research/ManualResearchPanel.tsx
decisions:
  - "ResearchCache.country_qid kept at String(20): cache keys derive from individual resolved QIDs per run, not the multi-country list stored on the project"
  - "Period ordering enforced only when both period_start and period_end present in same PATCH — single-bound updates still allowed"
  - "Médio Oriente preset left as Q43 single-country: label is geographic (Anatolia/Levant/Mesopotamia), not matching modern country entries in _TABLE"
metrics:
  duration: "~25 minutes"
  completed: "2026-04-22"
  tasks: 5
  files_modified: 6
  files_created: 1
---

# Phase quick-260422-l7g Plan 01: Fix Research Flow — Date/Country Persistence + Multi-Country Support Summary

**One-liner:** Widened `projects.country_qid` to VARCHAR(200) with Alembic batch migration, added comma-separated QID validator (`Q29,Q45`), fixed 6 multi-country presets, and wired ResearchDialog to PATCH `{country_qid, period_start, period_end}` to DB before every LLM/manual research call.

## Tasks Completed

| # | Task | Commit | Key Files |
|---|------|--------|-----------|
| 1 | Widen country_qid column + Alembic 0002 migration | 573cc54 | models.py, alembic/versions/0002_widen_country_qid_multi_country.py |
| 2 | Widen ProjectCreate/Update validator to accept comma-separated QIDs | ad5919d | schemas.py, tests/test_projects.py |
| 3 | Fix multi-country presets (Ibérica + 5 others) | 76157fc | services/countries.py |
| 4 | ResearchDialog PATCHes dates + country before every research call | 3faa0c7 | ResearchDialog.tsx, ManualResearchPanel.tsx |
| 5 | Apply migration + rebuild frontend + regression suite | (no new commit — migration + build verified) | dev DB, frontend/dist/ |

## Migration Details

- **Revision:** 0002
- **Down revision:** 0001
- **Change:** `projects.country_qid VARCHAR(20) → VARCHAR(200)` via `batch_alter_table` (SQLite-compatible)
- **Alembic current:** `0002 (head)` — verified against `~/.medieval-forge/medieval_forge.db`
- **Dev DB schema confirmed:** `country_qid VARCHAR(200) NOT NULL`

## Preset Changes

| Preset | Before | After | clip_iso_codes |
|--------|--------|-------|----------------|
| Península Ibérica | `Q29` | `Q29,Q45` | `["ES", "PT"]` (already present) |
| Ilhas Britânicas | `Q145` | `Q145,Q27` | `["GB", "IE"]` (added) |
| Escandinávia | `Q34` | `Q35,Q20,Q34` | `["DK", "NO", "SE"]` (added) |
| Balcãs | `Q403` | `Q403,Q224,Q225` | `["RS", "HR", "BA"]` (added) |
| Europa Central | `Q36` | `Q36,Q28,Q213` | `["PL", "HU", "CZ"]` (added) |
| Norte de África | `Q1028` | `Q1028,Q262,Q948` | `["MA", "DZ", "TN"]` (added) |
| Médio Oriente | `Q43` | unchanged | — |

## Tests Added (Task 2)

File: `backend/tests/test_projects.py`

- `test_project_create_country_qid_multi` — parametrized (5 cases): single QID, name, comma QIDs, whitespace tolerant, names resolved per token
- `test_project_create_country_qid_multi_rejects_bad` — parametrized (2 cases): `Q29,INVALID`, empty string
- `test_project_update_country_qid_multi_accepts_none` — None passes through
- `test_project_update_country_qid_multi_accepts_comma_list` — `Q29,Q45` accepted
- `test_project_update_period_ordering_enforced` — period_start >= period_end raises
- `test_project_update_period_ordering_single_bound_ok` — only period_end set, no error
- `test_patch_project_with_multi_country_qid` — end-to-end PATCH with `Q29,Q45` returns 200

All 21 tests in `test_projects.py` pass green.

## Existing Project Remediation (Ibérica — Q29 → Q29,Q45)

**The user must take one of the following actions manually.** Neither option was executed automatically.

**Option A (RECOMMENDED): Delete and recreate from the fixed preset.**
Create a new project using the "Península Ibérica" preset — it now ships with `country_qid="Q29,Q45"`. This ensures territories are ingested for both Spain and Portugal. The `clip_iso_codes: ["ES", "PT"]` was already correct before this fix, so the new project will clip correctly to both countries.

**Option B: PATCH the existing project and re-run ingestion.**
Open the existing Iberia project in the UI, open the Research Dialog, change the country input from `Q29` to `Q29,Q45`, and click "Iniciar pesquisa" or generate the manual prompt. This will PATCH `country_qid` to `"Q29,Q45"` in the DB. However, `territories.geojson` is frozen at ingestion time — only Spanish condados will be present until you re-trigger "OSM Ingest" and "Generate" explicitly. Option A avoids this re-ingestion step.

## Important Side Effects (User Must Know)

### 1. Research cache becomes orphaned when country_qid changes

`compute_cache_key` (in `services/research_cache.py`) hashes `country_qid:period_start:period_end:provider:model`. Changing the stored `country_qid` from `"Q29"` to `"Q29,Q45"` on an existing project makes all prior cached research unreachable — cache rows still exist in the DB but won't match the new key. The cache will simply be bypassed and a fresh research run will be required.

### 2. Territories are frozen at ingestion time

Patching an existing Iberia project's `country_qid` to `"Q29,Q45"` does **NOT** re-run OSM ingestion or territory rasterization. `territories.geojson` still contains only Spanish condados from the original ingest. For meaningful multi-country research, use Option A (delete + recreate) rather than Option B.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pre-existing test using "spain" (valid name) as invalid input**

- **Found during:** Task 2, RED phase
- **Issue:** `test_country_qid_validation_rejects_bad_format` used `country_qid="spain"` expecting 422, but "spain" is in `_TABLE` as a valid alias for Q29. The test passed before only because the validator called `resolve_to_qid` which returned Q29.  
  Wait — actually the test was FAILING even before this task (old validator returned Q29 for "spain" → 201 not 422). The test was broken before we touched anything. Confirmed by the first RED run.
- **Fix:** Changed to `"NOTACOUNTRY"` — a string that is neither a QID, ISO code, nor any recognized name.
- **Files modified:** `backend/tests/test_projects.py`

### Pre-existing Test Failures (Out of Scope — Not Fixed)

The following test failures existed before this task and are unrelated to its changes. They are deferred:

| File | Issue |
|------|-------|
| `tests/unit/test_llm_retry.py` | Duchy tuple payload shape (fixed in 260422-gts but test file not updated) |
| `tests/unit/test_condado_assignment.py` | Same Duchy tuple issue |
| `tests/unit/test_llm_schemas.py` | Same Duchy tuple issue |
| `tests/unit/test_llm_registry.py` | Provider count 4 vs 5 (manual provider added in 260422-h24) |
| `tests/unit/test_auth_session.py` | Credential source 'disk' vs 'session' |
| `tests/unit/test_oauth_flow.py` | Credential source 'disk' vs 'oauth' |
| `tests/integration/test_research_sse.py` | Same Duchy tuple issue |

## Threat Flags

None. No new network endpoints, auth paths, or trust boundary changes introduced.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| alembic/versions/0002_widen_country_qid_multi_country.py | FOUND |
| backend/medieval_forge/models.py | FOUND |
| backend/medieval_forge/schemas.py | FOUND |
| backend/medieval_forge/services/countries.py | FOUND |
| frontend/src/components/research/ResearchDialog.tsx | FOUND |
| frontend/src/components/research/ManualResearchPanel.tsx | FOUND |
| commit 573cc54 (Task 1) | FOUND |
| commit ad5919d (Task 2) | FOUND |
| commit 76157fc (Task 3) | FOUND |
| commit 3faa0c7 (Task 4) | FOUND |
