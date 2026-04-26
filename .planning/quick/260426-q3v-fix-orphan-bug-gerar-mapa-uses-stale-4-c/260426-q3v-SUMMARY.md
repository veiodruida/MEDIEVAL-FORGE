---
quick_task: 260426-q3v
title: "Fix orphan bug #4 — Gerar mapa uses stale 4-condado template instead of cached 91-condado research"
completed: 2026-04-26
duration_min: 18
tasks: 2
commits:
  - c8d1d0d  # feat: add territory_builder service
  - 29a31f1  # fix: /generate prefers DB-cached research over body
files_created:
  - backend/medieval_forge/services/territory_builder.py
  - backend/tests/services/test_territory_builder.py
  - backend/tests/api/test_generate_uses_cached_research.py
files_modified:
  - backend/medieval_forge/api/generate.py
tests_added: 11   # 7 builder + 4 endpoint regression
requirements: [QUICK-260426-q3v]
---

# Quick Task 260426-q3v: Fix orphan bug #4 — `/generate` uses stale body, not cached research

## One-liner

`/generate` now prefers the latest `ResearchCache` row over the request body, so a frontend posting a stale 4-condado template no longer overrides 91-condado manual research; cache miss returns 422 with a research-mention message; power-user override via `force_body_territory_data: true`.

## Root Cause

`backend/medieval_forge/api/generate.py:trigger_generate` merged `project.bbox → project.generator_config → request body` and accepted whatever `territory_data` the body contained. The frontend (`frontend/src/pages/ProjectDetail.tsx:359`) sources `territory` from either `DEFAULT_TERRITORY` (4 condados) or `useTerritoryTemplate('iberia')` (4 condados from `territory_iberia.json`). Neither path consults the per-project `research_cache` rows that `POST /projects/{id}/research/manual` writes (91 condados for Q29,Q45). Result: the body always won and the cache was effectively dead-code at generation time.

## Chosen Precedence Order

1. **Latest `ResearchCache` row** keyed on `(project.country_qid, project.period_start, project.period_end)` — cross-provider, newest `created_at` wins (deterministic, observable via the row's `provider`/`model` fields).
2. **Project bbox + `generator_config`** — flow into `merged` first.
3. **Request body** — IGNORED for `territory_data` unless `force_body_territory_data: true`.
4. **422 fail-fast** when neither cache nor body provides usable data.

The cache key is derived from the **project row**, never from the body — so a malicious client cannot redirect the lookup to another project's research (T-q3v-04 mitigation realized).

## Schema Change

None. `ResearchCache.created_at` already existed (`models.py:80`), so no migration was needed. `select_latest_cache_row` orders by `created_at DESC LIMIT 1`.

## What Was Built

### Task 1 — `services/territory_builder.py` (new)

Three exports:

- `select_latest_cache_row(session, country_qid, period_start, period_end) -> ResearchCache | None`
- `assemble_territory_data(payload, centroids) -> dict` — builds the `(id, name, lon, lat, duchy_id, baronies)` tuples consumed by `services.generator._inject_territory_module`. Centroids without an assignment emit `duchy_id=None` (no silent drops). Raises `ValueError` listing unknown ids if the payload references centroids absent from `territories.geojson`.
- `build_territory_data_from_cache(session, project, project_path) -> dict | None` — public entry point.

7 tests pass: cache-row selection (none / latest-wins-across-providers), assembly shape (91 condados), defensive `ValueError`, unassigned-centroid handling, full wire-up (none on miss / 91 on hit).

### Task 2 — `api/generate.py` rewired

Cache lookup added before the existing `territory_data` check. New 422 message mentions "research" so the user knows to run research first. `force_body_territory_data` is popped from `merged` so it never leaks into `RegionConfig`. INFO logs cover both cache-hit and force-body branches.

4 regression tests:

1. Empty body + 91-cache → captured config has 91 condados (the bug fix).
2. Stale 4-condado body + 91-cache → cache wins (91 condados).
3. Empty body + no cache → 422 with "research" in detail; project status remains `created`, background task NOT scheduled.
4. `force_body_territory_data: true` + 91-cache → body wins (4 condados); override flag stripped from pipeline config.

## Verification

```
backend $ pytest tests/services/test_territory_builder.py tests/api/test_generate_uses_cached_research.py tests/api/test_research_manual.py tests/api/test_edit_api.py
24 passed in 0.33s
```

## Deviations from Plan

None for the fix itself. Plan executed exactly as specified.

## Deferred Issues

The full backend suite has 16 pre-existing failures unrelated to this task (Duchy schema drift in `tests/unit/test_llm_*`, Wikidata SSE smoke tests, ingest-time fixtures, etc.). Per scope-boundary rule (only auto-fix issues directly caused by current task's changes), these were left untouched. None of the failures touch the cache-or-generate code paths affected here.

## Threat Flags

None. The change is additive: one indexed SELECT + an in-memory assembly. No new endpoints, no new file access, no new auth surface. T-q3v-04 (body redirecting cache lookup) is structurally prevented because the cache key is built from `project.*` columns only.

## Self-Check: PASSED

- `backend/medieval_forge/services/territory_builder.py` — FOUND
- `backend/tests/services/test_territory_builder.py` — FOUND
- `backend/tests/api/test_generate_uses_cached_research.py` — FOUND
- `backend/medieval_forge/api/generate.py` — modified (import + cache-first logic)
- Commits c8d1d0d, 29a31f1 — present in `git log`
- 11/11 task-specific tests green
