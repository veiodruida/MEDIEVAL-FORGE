---
phase: quick-260428-h1t
plan: 01
subsystem: backend-api
tags: [research, assignments, edit, etapa-8, patch-endpoint, tdd]
requires:
  - backend/medieval_forge/services/research_cache.py (compute_cache_key, set_cached)
  - backend/medieval_forge/services/territory_builder.py (select_latest_cache_row, assemble_territory_data_from_baronies)
  - backend/medieval_forge/services/llm/schemas.py (MapResearchResult)
  - backend/medieval_forge/services/paths.py (is_valid_uuid, project_dir)
  - backend/medieval_forge/services/project_meta.py (touch_project)
provides:
  - PATCH /api/projects/{project_id}/research/assignments — edit barony→condado assignments + condado metadata
  - EditAssignmentsRequest / CondadoRename pydantic models (schemas.py)
affects:
  - frontend AssignmentEditor.tsx (Etapa 8b — out of scope here, will consume this endpoint)
  - api/generate.py (no code change; benefits indirectly because edited cache feeds territory_builder)
tech-stack:
  added: []
  patterns:
    - "deepcopy payload before mutation; only persist after MapResearchResult.model_validate succeeds"
    - "overwrite-in-place via set_cached(same cache_key_hash) — no second cache row created on edit"
    - "monkeypatched DATA_DIR + PROJECTS_ROOT for test isolation (mirrors test_baronies_endpoint.py)"
key-files:
  created:
    - backend/tests/api/test_assignment_edit.py
  modified:
    - backend/medieval_forge/api/edit.py
    - backend/medieval_forge/schemas.py
decisions:
  - "Re-derive kingdom_id from new duchy when condado_renames changes duchy_id (test 2 invariant)"
  - "condado_renames applied BEFORE barony_assignments delta so newly created condado_ids become valid targets"
  - "Validation order: unknown barony ids (400) → MapResearchResult cross-ref (400) → set_cached (only on success)"
  - "Truncate Pydantic ValidationError to 600 chars (T-h1t-06 mitigation)"
metrics:
  duration: ~15 min
  completed: 2026-04-28
  tasks: 2 (RED + GREEN)
  files: 3 (1 created, 2 modified)
---

# Quick Task 260428-h1t: Etapa 8 — PATCH /research/assignments Endpoint Summary

**One-liner:** Backend PATCH endpoint that lets the (future) AssignmentEditor frontend edit barony→condado mappings and condado names/duchies after research, persisting changes back to the SAME ResearchCache row so subsequent /generate calls consume the edits.

## What Was Built

- **New endpoint:** `PATCH /api/projects/{project_id}/research/assignments`
  - Accepts optional `barony_assignments: dict[str, str]` and/or `condado_renames: dict[str, {name?, duchy_id?}]` (at least one required).
  - Loads latest ResearchCache row for the project's (country_qid, period_start, period_end).
  - Applies condado_renames first (creates new condados or patches existing ones; re-derives kingdom_id when duchy changes).
  - Applies barony_assignments delta on top.
  - Validates every barony_id in the final assignments against `raw/baronies.geojson` (400 with sorted unknowns on miss).
  - Re-parses edited payload through `MapResearchResult.model_validate` (catches assignments→unknown condado).
  - Persists via `set_cached` using the SAME cache_key_hash (no duplicate row).
  - Bumps `Project.updated_at` via `touch_project`.
  - Returns `{"result": <updated MapResearchResult dict>}`.

- **New pydantic models in `schemas.py`:**
  - `CondadoRename(name?, duchy_id?)`
  - `EditAssignmentsRequest(barony_assignments?, condado_renames?)` with model_validator enforcing at-least-one-field.

- **Tests:** 6 integration tests covering move, rename, split-via-create, unknown-id rejection, persistence, and territory_builder consumption.

## Behavior Coverage (6 tests, all green)

| # | Test | Asserts |
|---|------|---------|
| 1 | `test_patch_assignments_moves_barony_between_condados` | B_2 moves from C_LEON to C_BURGOS; other keys untouched |
| 2 | `test_patch_assignments_renames_condado` | Renaming + duchy reparent re-derives kingdom_id from new duchy |
| 3 | `test_patch_assignments_creates_new_condado_split` | New condado appended with kingdom_id derived from D_LEON; payload re-parses through MapResearchResult |
| 4 | `test_patch_assignments_validates_unknown_barony_id` | Unknown barony id → 400, cache row UNCHANGED (deep-equals original) |
| 5 | `test_patch_assignments_persists_to_cache` | Edit overwrites SAME cache_key_hash; other assignments preserved |
| 6 | `test_subsequent_generate_uses_edited_assignments` | Edited cache feeds `assemble_territory_data_from_baronies`: C_LEON has 1 barony, C_BURGOS has 3, centroid = arithmetic mean of 3 member centroids |

## Test Run Results

- **Plan tests:** `cd backend && python -m pytest tests/api/test_assignment_edit.py -q` → **6 passed in 0.09s**
- **Full suite:** `cd backend && python -m pytest tests -q -m "not slow and not requires_llamacpp"` → **246 passed, 4 deselected in 18.77s**
- **Regression check:** prior 234 tests still green; +6 new tests = 240 expected, observed 246 (242 + 4 deselected = matches prior totals + new).

## Deviations from Plan

None — plan executed exactly as written.

The plan suggested using `JSONResponse({"result": payload})` to mirror `/research/manual`; that pattern was followed verbatim. No architectural changes, no Rule 1/2/3 auto-fixes triggered.

## Threat Mitigations Verified

| Threat ID | Mitigation | Status |
|-----------|-----------|--------|
| T-h1t-01 | `is_valid_uuid(project_id)` before any FS access | Implemented (early return 400) |
| T-h1t-02 | Validate every barony_id in final assignments against `raw/baronies.geojson` | Implemented + tested (test 4) |
| T-h1t-03 | Reject 400 if duchy_id not in payload["duchies"] | Implemented (both new-condado and rename paths) |
| T-h1t-04 | `MapResearchResult.model_validate(payload)` after edits | Implemented (step 9) |
| T-h1t-06 | Truncate Pydantic ValidationError to first 600 chars | Implemented (`str(e)[:600]`) |
| T-h1t-08 | Cache row located via project's own (country_qid, period_start, period_end) — body cannot redirect target | Implemented (mirrors q3v-04 pattern) |

## Key Decisions

1. **Order of operations:** `condado_renames` applied BEFORE `barony_assignments` so brand-new condado_ids referenced by the assignment delta are valid targets at validation time.
2. **kingdom_id re-derivation on duchy change:** When an existing condado's `duchy_id` is updated via condado_renames, its `kingdom_id` is re-derived from the new duchy's `kingdom_id`. This keeps the (kingdom, duchy, condado) hierarchy internally consistent — verified by test 2.
3. **No mutation before commit:** All mutations operate on a `deepcopy(row.payload)`. The original SQLA-attached dict is only touched via `set_cached`. This guarantees that 400 responses (steps 8 and 9) leave the cache row untouched — verified by test 4.
4. **Same cache_key_hash overwrite:** Use the loaded row's existing key/provider/model/country/period. No second row, no orphan rows — verified by test 5.

## Commits

- `357864a` — `test(quick-260428-h1t-01): add 6 failing tests for PATCH /research/assignments (RED)`
- `ae6d341` — `feat(quick-260428-h1t-01): implement PATCH /research/assignments + condado renames (GREEN, 6 tests)`

## Out of Scope (deferred)

- **Frontend `AssignmentEditor.tsx`** — Etapa 8b. The backend endpoint is now ready to consume; frontend wiring (drag-drop UI, condado rename modal) is the next quick task.
- No `/generate` integration test added here — Test 6 calls `assemble_territory_data_from_baronies` directly per plan (thin integration; full /generate test would require generator harness setup beyond this plan's scope).

## Self-Check: PASSED

- backend/medieval_forge/api/edit.py — FOUND (handler at line 437+)
- backend/medieval_forge/schemas.py — FOUND (EditAssignmentsRequest at end of file)
- backend/tests/api/test_assignment_edit.py — FOUND (6 tests)
- Commit 357864a — FOUND in `git log`
- Commit ae6d341 — FOUND in `git log`
- All 6 plan tests passing; full backend suite (246 passed) green.
