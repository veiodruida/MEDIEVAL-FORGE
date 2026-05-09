---
phase: 03-read-only-canvas-redesign
plan: 07
subsystem: backend
tags: [deletion, v1-purge, ingest, llm, models]

requires:
  - phase: 03-read-only-canvas-redesign
    plan: 01
    provides: _write_geojson_atomic lifted to services/paths.py (allowed ingest_runner.py deletion)
  - phase: 03-read-only-canvas-redesign
    plan: 06
    provides: frontend purged of v1 LLM/ingest consumers (no surviving callers)
provides:
  - "Backend free of v1 ingest endpoints (api/ingest.py, services/ingest_runner.py, services/ingest_wikidata.py)"
  - "Backend free of LLM stack (api/{auth,research,codex,llm,edit}.py + services/{research_runner,research_cache,codex_runner,codex_cache,credential_store,territory_builder}.py + services/llm/)"
  - "models.py shrunk: only Project + Base survive"
  - "main.py shrunk: credential preload + oauth_states init removed; lifespan keeps only Base.metadata.create_all + engine.dispose"
affects:
  - "03-08 (Playwright UAT — backend surface area finalised: only projects/export/terrain/v3 routers)"
  - "Future Phase 07 (LLM rewrite from scratch — clean slate; no D-13 carry-over)"

tech-stack:
  added: []
  patterns:
    - "Atomic two-task commit split (D-12 → D-13) — no cross-domain imports forced a Plan 06-style combined commit; each task verified independently"
    - "Pre-flight grep audit (Plan acceptance step 1) caught api/edit.py as orphan via lazy imports of all D-13 services; advisor confirmed include in deletion sweep"

key-files:
  modified:
    - backend/medieval_forge/main.py (lifespan shrunk; 6 router imports + 6 include_routers stripped)
    - backend/medieval_forge/models.py (LLMCredential + ResearchCache + CodexCache classes deleted; Project + Base kept)
    - backend/tests/unit/test_paths_write_geojson_atomic.py (legacy re-export test case dropped — ingest_runner.py is gone)
  deleted:
    # D-12 — v1 ingest backend
    - backend/medieval_forge/api/ingest.py
    - backend/medieval_forge/services/ingest_runner.py
    - backend/medieval_forge/services/ingest_wikidata.py
    - backend/tests/test_ingest.py
    - backend/tests/test_bbox_backfill.py
    - backend/tests/api/test_baronies_endpoint.py
    # D-13 — LLM backend stack
    - backend/medieval_forge/api/auth.py
    - backend/medieval_forge/api/research.py
    - backend/medieval_forge/api/codex.py
    - backend/medieval_forge/api/llm.py
    - backend/medieval_forge/api/edit.py
    - backend/medieval_forge/services/research_runner.py
    - backend/medieval_forge/services/research_cache.py
    - backend/medieval_forge/services/codex_runner.py
    - backend/medieval_forge/services/codex_cache.py
    - backend/medieval_forge/services/credential_store.py
    - backend/medieval_forge/services/territory_builder.py
    - backend/medieval_forge/services/llm/ (15 files: __init__, auth, base, claude, gemini, llamacpp, manual, model_routing, ollama, openai, parse, prompt, registry, retry, schemas)
    # Orphan LLM tests
    - backend/tests/api/test_assignment_edit.py
    - backend/tests/api/test_codex_endpoints.py
    - backend/tests/api/test_edit_api.py
    - backend/tests/api/test_paint_terrain.py
    - backend/tests/api/test_research_manual.py
    - backend/tests/integration/test_providers_endpoint.py
    - backend/tests/integration/test_research_sse.py
    - backend/tests/services/test_codex_prompt.py
    - backend/tests/services/test_codex_runner.py
    - backend/tests/services/test_codex_schema.py
    - backend/tests/services/test_llamacpp_provider.py
    - backend/tests/services/test_llm_providers.py
    - backend/tests/services/test_research_runner_map_path.py
    - backend/tests/services/test_territory_builder.py
    - backend/tests/services/test_territory_builder_baronies_aggregation.py
    - backend/tests/services/test_territory_builder_cache_dispatch.py
    - backend/tests/unit/test_auth_session.py
    - backend/tests/unit/test_oauth_flow.py
    - backend/tests/unit/test_research_cache.py
    - backend/tests/unit/test_llm_registry.py
    - backend/tests/unit/test_llm_retry.py
    - backend/tests/unit/test_llm_routing.py
    - backend/tests/unit/test_llm_schemas.py
    - backend/tests/unit/test_map_research_prompt.py
    - backend/tests/unit/test_barony_assignments_validation.py
    - backend/tests/unit/test_cli_piggyback.py
    - backend/tests/unit/test_condado_assignment.py

key-decisions:
  - "api/edit.py added to deletion list (plan-permitted). Pre-flight grep showed it imports services/territories_geojson + services/research_cache + services/territory_builder + services/llm/schemas — all D-13 targets. Plan body line 146 explicitly authorises: 'If a backend api/edit.py exists, add it to deletion list.' Advisor confirmed."
  - "tests/test_ingest.py deleted whole-file. 15 tests mixed wikidata (delete) + osm (survives). tests/services/test_ingest_osm.py (5 tests) covers the surviving OSM module separately, so coverage is preserved."
  - "services/territories_geojson.py KEPT (not in plan deletion list). Voronoi.py lazy-imports it in load_land_mask_and_bbox (api/edit.py-only callsite, now orphan). Karpathy #3 — surgical changes; do not delete unrelated dead code. Recorded as deferred orphan; tests/test_territories_geojson.py + tests/services/test_territories_geojson_consistency.py still pass (module still imports cleanly)."
  - "services/voronoi.py KEPT (actively consumed by services/pipeline/__init__.py: setup_baronies, rasterize_baronies, build_hierarchy_maps). The load_land_mask_and_bbox function inside voronoi (consumed only by api/edit.py::move_capital) is now dead code; left untouched per Karpathy #3."
  - "api/terrain.py KEPT (Phase 02.1 stubs; no LLM imports). Imports services/ingest_terrain (survives). Plan does not list it for deletion."
  - "api/export.py audited and KEPT. No LLM imports; consumes Project model + services/paths + services/export. Plan 04 'Exportar ZIP' button still works."
  - "Two atomic commits (Task 1, Task 2). Unlike Plan 06, D-12 and D-13 had NO cross-domain imports forcing a combined commit — Task 1 verified standalone before starting Task 2."
  - "tests/unit/test_paths_write_geojson_atomic.py: dropped test_legacy_import_path_still_works_via_reexport (lines 21-25). The other 3 tests stay. Required because ingest_runner.py re-export stub is now deleted."

requirements-completed: [SC-3, SC-4]

duration: ~25min
completed: 2026-05-09
---

# Phase 03 Plan 07: Backend Deletion Sweep (D-12 + D-13) Summary

**14 backend source files + services/llm/ subdir (15 files) + 26 orphan tests deleted across 2 atomic commits. main.py lifespan shrunk (credential preload + oauth_states removed). models.py shrunk (LLMCredential + ResearchCache + CodexCache deleted; Project + Base kept). api/edit.py added to deletion (plan-permitted; orphan-via-LLM-imports). Phase 01 parity 11/11 still green; full backend suite 191 passed (2 pre-existing failures unrelated to this plan).**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-09 (post Plan 06)
- **Completed:** 2026-05-09
- **Tasks:** 2 (D-12 standalone, then D-13 standalone)
- **Commits:** 2 atomic
- **Files deleted:** 14 source + 15 services/llm/ + 26 tests = 55
- **Files modified:** 3 (main.py, models.py, test_paths_write_geojson_atomic.py)
- **Net LOC:** -10130 (1355 deletions Task 1 + 8775 deletions Task 2 - 2 insertions)

## Accomplishments

- **D-12 (Task 1) — v1 ingest backend deleted:** api/ingest.py + services/ingest_runner.py + services/ingest_wikidata.py removed; main.py ingest_router import + include stripped; 3 orphan tests deleted (test_ingest, test_bbox_backfill, test_baronies_endpoint).
- **D-13 (Task 2) — LLM backend stack deleted:** 5 api modules (auth, research, codex, llm, edit) + 6 services modules (research_runner, research_cache, codex_runner, codex_cache, credential_store, territory_builder) + services/llm/ (15 files) removed; 23 orphan LLM tests deleted.
- **main.py lifespan shrunk:** credential_store.load_all + app.state.credentials + app.state.oauth_states preload all removed. Lifespan now only opens engine, runs Base.metadata.create_all, yields, disposes engine. 6 router imports + 6 include_router lines stripped.
- **models.py shrunk:** LLMCredential, ResearchCache, CodexCache classes deleted. Project + Base + helpers (_new_uuid, _utcnow) survive. Orphan llm_credentials/research_cache/codex_cache SQLite tables in user DB are harmless (left untouched per RESEARCH §Runtime State Inventory).
- **Smoke import passes:** `python -c "from medieval_forge.main import app; print(len(app.routes))"` -> 25 routes.

## Task Commits

| # | Task | Type | Commit | Files | LOC |
|---|------|------|--------|-------|-----|
| 1 | D-12 — v1 ingest backend | chore | `a3561c2` | 8 changed | -1355 |
| 2 | D-13 — LLM backend stack | chore | `87f8aab` | 55 changed | -8775 +2 |

## Files Created/Modified

See `key-files` block in frontmatter (55 deletions, 3 modifications).

## Decisions Made

See `key-decisions` block. Highlights:

- **api/edit.py deletion (plan-permitted).** Pre-flight grep revealed it imports 4 D-13 service targets via lazy imports. Plan line 146 explicitly authorised inclusion.
- **services/territories_geojson.py KEPT.** Not in plan's deletion list. Voronoi lazy-imports it for an api/edit.py-only function — now orphan code, but Karpathy #3 says don't delete unrelated dead code. Tests still pass.
- **api/terrain.py + api/export.py KEPT.** Both surveyed: zero LLM imports, no orphan status. Plan 04 ZIP export button + Phase 02.1 terrain stubs continue to function.
- **Two atomic commits, NOT combined like Plan 06.** D-12 has zero cross-domain imports into D-13; Task 1 verified standalone (parity + v3 endpoints green) before Task 2 began.

## Deviations from Plan

**Total deviations:** 2 — both Karpathy/scope-driven, no architectural impact.

### Deferred Items (out-of-scope, Karpathy #3)

**1. [Out-of-scope] services/territories_geojson.py and dead branch in voronoi.py**
- **Found during:** Pre-flight grep audit.
- **Issue:** voronoi.py:336 lazy-imports territories_geojson inside load_land_mask_and_bbox (only api/edit.py consumer; now deleted). voronoi.py module-level docstring (line 3) still says "Consumed by api/edit.py".
- **Decision:** Leave both files untouched. territories_geojson.py is not in plan's deletion list. Karpathy #3 — surgical changes; don't delete unrelated dead code. The lazy import never executes after edit.py deletion.
- **Documented as:** Deferred orphan for a future cleanup plan if/when the sidecar architecture is reworked.

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Drop legacy re-export test from test_paths_write_geojson_atomic.py**
- **Found during:** Task 1 pre-test review.
- **Issue:** test_legacy_import_path_still_works_via_reexport imports `from medieval_forge.services.ingest_runner import _write_geojson_atomic` to verify the re-export stub from Plan 03-01. With ingest_runner.py deleted in this plan, that test would hard-fail.
- **Fix:** Delete the 1 test case (5 lines, lines 21-25). The other 3 tests in the file (canonical import, JSON roundtrip, no-auto-mkdir) stay.
- **Files modified:** backend/tests/unit/test_paths_write_geojson_atomic.py.
- **Commit:** `a3561c2`.

## Pre-existing Failures (NOT introduced by this plan)

Confirmed via `git stash` reproduction against pre-Plan-07 baseline:

1. `tests/unit/test_v3_artifacts.py::test_artifacts_rejects_path_traversal_attempt` — expects 400/404/503; gets 200. Pre-existing security gap; out of scope for D-12/D-13 deletion sweep.
2. `tests/services/test_ingest_osm.py::test_sse_generator_sets_stop_event_on_client_disconnect` — pre-existing failure; surviving osm test, not affected by deletions.

Both should be tracked as deferred items in the phase verification doc.

## Authentication Gates

None. Phase 03 is local-only by D-20.

## Issues Encountered

None outside the 1 fix above.

## User Setup Required

None.

## Next Phase Readiness

- **Plan 03-08 (Playwright UAT) cleared.** Backend surface area finalised: 25 routes across projects/export/terrain/v3 routers. No LLM endpoints remain; no v1 ingest endpoints remain.
- **Phase 03 SC-3 (no console errors at any layer) prerequisite met for backend.** Surviving routers + models compile and import; pre-existing test failures predate this plan.
- **Phase 03 SC-4 (Phase 01 parity stays green) verified.** test_iberia_868.py 11/11 (10 file outputs + sidecar) green at end of each task.
- **D-12 closed.** v1 ingest endpoints + ingest_runner + ingest_wikidata gone.
- **D-13 closed.** Full LLM stack purged including auth.py + credential_store.py + LLMCredential + ResearchCache + CodexCache models. Phase 07 (future) starts from clean slate.

## Verification

- `cd backend && py -3.14 -m pytest tests/parity/test_iberia_868.py` → **11 passed**
- `cd backend && py -3.14 -c "from medieval_forge.main import app; print(len(app.routes))"` → **25 routes**, no ImportError
- Full sweep: 191 passed, 2 pre-existing failures (proven via git stash). Phase 02 v3 ingest + Plan 02 v3 endpoints + Phase 02.1 terrain all green.
- `grep -rn "credential_store|LLMCredential|ResearchCache|CodexCache|app.state.credentials|app.state.oauth_states" medieval_forge/ --include="*.py"` → **zero hits**
- `find medieval_forge/services/llm 2>&1 | grep -v "No such"` → **nothing**
- `find medieval_forge/api -name "auth.py" -o -name "research.py" -o -name "codex.py" -o -name "llm.py" -o -name "edit.py" -o -name "ingest.py"` → **nothing**
- `grep -n "class LLMCredential|class ResearchCache|class CodexCache" medieval_forge/models.py` → **zero hits**
- `git log --oneline -3` → `87f8aab` (D-13), `a3561c2` (D-12), `68efcc6` (Plan 06 frontend purge)

## Self-Check: PASSED

- FOUND commit: a3561c2 (chore(03-07): delete v1 ingest backend (D-12))
- FOUND commit: 87f8aab (chore(03-07): delete LLM backend stack (D-13))
- DELETED: backend/medieval_forge/api/ingest.py
- DELETED: backend/medieval_forge/api/auth.py
- DELETED: backend/medieval_forge/api/research.py
- DELETED: backend/medieval_forge/api/codex.py
- DELETED: backend/medieval_forge/api/llm.py
- DELETED: backend/medieval_forge/api/edit.py
- DELETED: backend/medieval_forge/services/ingest_runner.py
- DELETED: backend/medieval_forge/services/ingest_wikidata.py
- DELETED: backend/medieval_forge/services/research_runner.py
- DELETED: backend/medieval_forge/services/research_cache.py
- DELETED: backend/medieval_forge/services/codex_runner.py
- DELETED: backend/medieval_forge/services/codex_cache.py
- DELETED: backend/medieval_forge/services/credential_store.py
- DELETED: backend/medieval_forge/services/territory_builder.py
- DELETED: backend/medieval_forge/services/llm/ (15 files)
- FOUND: backend/medieval_forge/main.py (no LLM imports; lifespan shrunk)
- FOUND: backend/medieval_forge/models.py (no LLMCredential/ResearchCache/CodexCache)
- SMOKE: from medieval_forge.main import app → 25 routes, no ImportError
- PARITY: 11/11 green (test_iberia_868.py + sidecar)
- FULL SUITE: 191 passed, 2 pre-existing failures (unrelated)

---
*Phase: 03-read-only-canvas-redesign*
*Completed: 2026-05-09*
