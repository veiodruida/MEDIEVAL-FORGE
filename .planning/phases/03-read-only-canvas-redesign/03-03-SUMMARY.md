---
phase: 03-read-only-canvas-redesign
plan: 03
subsystem: frontend
tags: [zustand, sse, run-state-machine, multi-select, v3-artifacts, vitest]

# Dependency graph
requires:
  - phase: 03-read-only-canvas-redesign
    plan: 01
    provides: 4 canvas-sidecar files emitted by run_pipeline (territories.geojson, baronies.geojson, condado_colors.json, barony_colors.json)
  - phase: 03-read-only-canvas-redesign
    plan: 02
    provides: GET /api/v3/projects/{id}/artifacts/* FileResponse endpoint + cfg.on_stage SSE bridge
provides:
  - "useRunStore (frontend/src/stores/useRunStore.ts) — 5-state machine + 11-stage canonical PIPELINE_STAGES tuple + LOG_CAP=500 logLines accumulator"
  - "selectedTerritoryIds: string[] + selectIds(ids[]) action on uiStore (D-17 multi-select primitive)"
  - "selectSelectedTerritoryId selector — exported migration target for consumers"
  - "useCanvasArtifacts.ts hits /api/v3/projects/{id}/artifacts/* (was /preview/*)"
affects:
  - "03-04 (ProjectDetail rewrite consumes useRunStore for SSE-driven UI states)"
  - "03-05 (canvas surface consumes selectedTerritoryIds + selectSelectedTerritoryId)"
  - "03-06 / 03-07 (Wave 3 deletes the legacy selectedTerritoryId mirror once consumers migrate to the selector)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Zustand v5 store with immutable .slice(-LOG_CAP) accumulator pattern"
    - "Mirror-field for backward-compat: selectedTerritoryId stays as a real state field synced with selectedTerritoryIds[0] ?? null until consumers migrate"
    - "Selector export (selectSelectedTerritoryId) as the migration vector — Plan 05 flips consumers to it, then drops the mirror"
    - "Substring-matcher fetch mocks (urlStr.includes('territory_metadata')) are URL-prefix agnostic by design — minimised lock-step churn during the v3 switch"

key-files:
  created:
    - frontend/src/stores/useRunStore.ts
    - frontend/src/stores/__tests__/useRunStore.test.ts
  modified:
    - frontend/src/stores/uiStore.ts
    - frontend/src/stores/uiStore.test.ts
    - frontend/src/hooks/useCanvasArtifacts.ts
    - frontend/src/hooks/useCanvasArtifacts.cacheVersion.test.ts
    - frontend/src/components/canvas/__tests__/CanvasViewer.hydrate.test.tsx
    - frontend/src/components/canvas/CanvasViewer.tsx
  deleted:
    - frontend/src/stores/__tests__/uiStore.test.ts (orphaned test for removed overlay fields)

key-decisions:
  - "Mirrored selectedTerritoryId field instead of pure-getter or selector-only: Zustand v5 + getter has known friction AND the plan's 'do not modify consumers' constraint demands CanvasViewer's `useUIStore((s) => s.selectedTerritoryId)` keep working — mirror writes resolve the three-way conflict (Rule 3 deviation, advisor-confirmed)"
  - "Deleted orphaned __tests__/uiStore.test.ts: it exclusively covered overlayImageUrl + overlayOpacity + setOverlayImageUrl + setOverlayOpacity + 'terrain' layer behavior, ALL of which Task 2 removes. Plan author missed the duplicate test file (only listed the next-to-code one in <files_modified>). Documented as Rule 3 — orphan would have been a TS+runtime regression at the Task 2 commit"
  - "Updated CanvasViewer.tsx line 262 fetch URL prefix in lock-step with the hook: a SECOND fetch in CanvasViewer (used by the hydrate effect) is independent from useCanvasArtifacts but goes to the same backend file. Hydrate test (which plan demands stay green) only passes when both fetches use v3. Documented as Rule 3 — strict reading of 'no UI files modified' ignored the actual data flow"
  - "3 of 5 CanvasViewer test files use substring matchers — no edit needed despite being listed in plan <files>. Verified green; deviation noted, no churn introduced"
  - "Mirror selectedTerritoryId is technical debt scheduled for deletion in Plan 05 once consumers migrate to selectSelectedTerritoryId — explicitly typed as legacy in the JSDoc"

requirements-completed: [SC-1, SC-2]

# Metrics
duration: ~10min
completed: 2026-05-09
---

# Phase 03 Plan 03: Frontend foundation — useRunStore + uiStore evolution + v3 URL switch Summary

**One new Zustand store (useRunStore) with the 11-stage SSE state machine, an evolved uiStore with selectedTerritoryIds[] multi-select primitive (mirror field kept for backward-compat), and a 5-URL prefix swap in useCanvasArtifacts from v1 /preview/* to v3 /api/v3/projects/{id}/artifacts/*. All 34 target vitest specs green; full suite 238/238 green; 4 atomic commits delivered.**

## Performance

- **Duration:** ~10 min (including the deviation pivots)
- **Started:** 2026-05-09T22:05Z
- **Completed:** 2026-05-09T22:13Z
- **Tasks:** 3 (+ 1 fix commit)
- **Commits:** 4
- **Files created:** 2
- **Files modified:** 6
- **Files deleted:** 1

## Accomplishments

- **useRunStore implemented (Truth #1).** 5-state machine (idle | ingesting | generating | generated | error), 11-stage PIPELINE_STAGES tuple matching the Plan 03-01 cfg.on_stage canonical order (landmask → border → voronoi → cleanup → smooth → merge → hierarchy → render → lookup → metadata → export), logLines capped at LOG_CAP=500 (mitigates T-03-FE-PLUMB-01 unbounded-accumulator threat), finishStage idempotent on duplicate calls. 12 vitest specs cover initial state, start, appendLog cap, stage tracking, finish, reset.
- **uiStore evolved for D-17 multi-select (Truths #2, #3).** Added `selectedTerritoryIds: string[]` + `selectIds(ids[])` action; LayerName cleansed of `'terrain'`; `overlayImageUrl` + `overlayOpacity` + their setters removed. Selector `selectSelectedTerritoryId` exported as the migration target for Plan 05 consumers. Legacy `select(id|null)` preserved as a thin convenience writer.
- **selectedTerritoryId backward-compat mirror.** Kept as a real state field synced on every `selectIds` / `select` write, so unmigrated consumers (CanvasViewer line 153 `useUIStore((s) => s.selectedTerritoryId)`) keep firing. Plan 05 will migrate them to the selector and drop the mirror.
- **useCanvasArtifacts v3 URL switch (Truth #4).** 5 fetch templates updated; query keys + select transforms + cacheVersion encoding (`?v=…`) all preserved verbatim. Hydrate-effect fetch in CanvasViewer.tsx updated in lock-step.
- **Test lock-step (Truth #5).** 34 specs green across the 5 target test files; 238/238 across the full suite — zero regressions.

## Task Commits

| # | Task | Type | Commit |
|---|------|------|--------|
| 1 | Create useRunStore Zustand store | feat | `561f999` |
| 2 | Promote uiStore.selectedTerritoryId → selectedTerritoryIds[] | refactor | `fcb2ebf` |
| 2.1 | Mirror selectedTerritoryId for backward-compat (deviation fix) | fix | `f7a0576` |
| 3 | Switch useCanvasArtifacts URL prefix /preview/* → /api/v3/projects/{id}/artifacts/* | feat | `f9e8a55` |

## Files Created/Modified

### Created

- `frontend/src/stores/useRunStore.ts` — 109 lines. PIPELINE_STAGES tuple, RunState type, useRunStore hook with start / appendLog / startStage / finishStage / finish / reset actions. LOG_CAP=500 enforced via `slice(-LOG_CAP)`.
- `frontend/src/stores/__tests__/useRunStore.test.ts` — 12 specs. Initial state, 11-stage tuple shape, start (generating + ingesting), appendLog cap (push 600 → length 500, oldest dropped), startStage, finishStage (push + idempotent), finish (generated + error variants), reset.

### Modified

- `frontend/src/stores/uiStore.ts` — replaced single-id selection with `selectedTerritoryIds: string[]` + `selectIds(ids[])` action; kept legacy `select(id|null)`; mirrored `selectedTerritoryId` field for backward-compat; dropped `'terrain'` from LayerName; removed overlay fields + setters; exported `selectSelectedTerritoryId` selector.
- `frontend/src/stores/uiStore.test.ts` — 9 specs. Initial empty ids + null selector, selectIds-with-two-ids, legacy select(string)/select(null), selectedTerritoryId mirror tracks first id (NEW), no `'terrain'` key, overlay fields absent at runtime, toggleLayer carry-over.
- `frontend/src/hooks/useCanvasArtifacts.ts` — 5 URL templates flipped from `/api/projects/${pid}/preview/*` → `/api/v3/projects/${pid}/artifacts/*`. Query keys + select transforms + cacheVersion encoding unchanged.
- `frontend/src/hooks/useCanvasArtifacts.cacheVersion.test.ts` — assertion text + explicit v3-prefix regex matcher + added baronies.geojson presence check (it was missing from the original assertion list).
- `frontend/src/components/canvas/__tests__/CanvasViewer.hydrate.test.tsx` — `installFetchMock` regex updated from `/\/api\/projects\/([^/?]+)\/preview\/territories\.geojson/` → `/\/api\/v3\/projects\/([^/?]+)\/artifacts\/territories\.geojson/`.
- `frontend/src/components/canvas/CanvasViewer.tsx` — line 262 hydrate-effect fetch URL updated in lock-step. Single-line surgical change; no behavior change.

### Deleted

- `frontend/src/stores/__tests__/uiStore.test.ts` — orphaned test exclusively covering removed overlay/terrain fields.

## Decisions Made

- **selectedTerritoryId mirror over pure selector (key).** The plan's `<interfaces>` block offered two options: a Zustand-v5 getter or a selector export. Initial implementation went with the selector (advisor's first guidance). After Task 2 commit the panOnSelect tests broke because CanvasViewer.tsx line 153 reads `s.selectedTerritoryId` directly via `useUIStore` subscription — the selector route doesn't satisfy that subscription. The plan also says "do not modify consumers" (Plan 05 territory). Resolution: mirror `selectedTerritoryId` as a real state field that's written on every `selectIds` / `select` call. This satisfies all three plan constraints simultaneously: new ids[] primitive, no consumer modification, panOnSelect tests green. Mirror is documented as Plan 05 deletion candidate.
- **Deletion of `__tests__/uiStore.test.ts`.** The plan listed only `frontend/src/stores/uiStore.test.ts` (next-to-code) in `<files_modified>`. A duplicate test file existed at `frontend/src/stores/__tests__/uiStore.test.ts` covering exclusively the removed fields. Leaving it would have been a TS-error + runtime-fail regression at the Task 2 commit. Deleted as a Rule 3 fix.
- **CanvasViewer.tsx 1-line URL update.** The hydrate effect inside `CanvasViewer.tsx` (line 262) does its OWN fetch independently from `useCanvasArtifacts`. The plan's "no UI files modified" rule conflicts with the plan's "hydrate test stays green" demand. The 1-line surgical URL swap is the only resolution; CanvasViewer behavior is otherwise untouched.
- **3 of 5 listed test files needed no edit.** `CanvasViewer.test.tsx`, `CanvasViewer.resize.test.tsx`, `CanvasViewer.panOnSelect.test.tsx` use substring matchers (`urlStr.includes('territory_metadata')`) that are URL-prefix agnostic. They appear in the plan's `<files>` list (anticipated lock-step churn) but no actual edit was needed. Verified green.

## Deviations from Plan

**Total deviations:** 3 — all Rule 3 (auto-fix blocking issues), all advisor-confirmed.

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Selector-only approach broke panOnSelect tests; switched to mirror field**
- **Found during:** Task 3 baseline test run (panOnSelect tests failed: `expected "spy" to be called` and `expected 'C_LUGO' to be null`).
- **Issue:** `CanvasViewer.tsx:153` reads `s.selectedTerritoryId` via `useUIStore` subscription. Removing the field — even with a `selectSelectedTerritoryId` selector exported — means the subscription never fires on selection change, so the pan-on-select effect doesn't run.
- **Fix:** Reintroduced `selectedTerritoryId: string | null` as a real state field that mirrors `selectedTerritoryIds[0] ?? null`. Both `selectIds(ids[])` and `select(id|null)` write both fields atomically. Selector export retained for migration; mirror documented as Plan 05 deletion candidate.
- **Files modified:** `frontend/src/stores/uiStore.ts`, `frontend/src/stores/uiStore.test.ts` (+ new mirror-tracking test).
- **Verification:** panOnSelect 7/7 green; uiStore 9/9 green.
- **Committed in:** `f7a0576` (fix(03-03): mirror selectedTerritoryId for backward-compat).

**2. [Rule 3 — Blocking] Deleted orphaned `__tests__/uiStore.test.ts`**
- **Found during:** Pre-Task 2 (advisor flagged the duplicate during the conflict-resolution call).
- **Issue:** Two `uiStore.test.ts` files existed: `frontend/src/stores/uiStore.test.ts` (next-to-code, listed by the plan) and `frontend/src/stores/__tests__/uiStore.test.ts` (duplicate, exclusively covering `overlayImageUrl`, `overlayOpacity`, `setOverlayImageUrl`, `setOverlayOpacity`, `'terrain'` layer behavior — ALL fields Task 2 removes). Leaving it would have been a TS-error + runtime-fail at the Task 2 commit. Plan author missed it.
- **Fix:** `rm` the orphan; the next-to-code suite (rewritten in Task 2) is the canonical surface.
- **Files modified:** deleted `frontend/src/stores/__tests__/uiStore.test.ts`.
- **Committed in:** `fcb2ebf` (Task 2 commit).

**3. [Rule 3 — Blocking] Updated CanvasViewer.tsx line 262 fetch URL in lock-step**
- **Found during:** Task 3 second test run (hydrate.test.tsx failed: 6 tests timed out waiting for `useProjectStore.getState().projectId === 'p1'`).
- **Issue:** `CanvasViewer.tsx` contains a SECOND fetch (at line 262, inside the hydrate effect) that targets the same backend URL family — but it's in the component file, not in `useCanvasArtifacts`. After updating the hook + the test mock regex to v3, this second fetch still hit the v1 path → 404 → hydrate never ran → `setProjectId` never fired → `expect(projectId).toBe('p1')` timed out. Plan said "no UI files modified" but the plan also demands the hydrate test stay green. Conflict resolved in favor of green tests.
- **Fix:** 1-line URL swap on `CanvasViewer.tsx:262`. No behavior change; identical request shape on the new prefix.
- **Files modified:** `frontend/src/components/canvas/CanvasViewer.tsx`.
- **Verification:** hydrate.test.tsx 7/7 green; full suite 238/238.
- **Committed in:** `f9e8a55` (Task 3).

### Adapted to Code Reality

**4. [Adapted] 3 of 5 listed CanvasViewer test files needed no edit.** Plan listed `CanvasViewer.test.tsx`, `CanvasViewer.resize.test.tsx`, `CanvasViewer.panOnSelect.test.tsx` as needing fetch-mock URL updates. Reality: those files use substring matchers (`urlStr.includes('territory_metadata')`) which are URL-prefix agnostic by design. Verified green without edit. Documented for traceability — no change introduced.

## Authentication Gates

None — this plan is pure frontend state plumbing; no network surface introduced.

## Issues Encountered

None outside the 3 deviations above.

## User Setup Required

None.

## Next Phase Readiness

- **Plan 03-04 ready (ProjectDetail rewrite).** SSE consumer can subscribe to `/generate/stream` (Plan 03-02) and dispatch `useRunStore.start / startStage / finishStage / appendLog / finish / reset` directly. The 11-stage canonical order in PIPELINE_STAGES matches the cfg.on_stage emit order exactly.
- **Plan 03-05 ready (canvas surface).** Multi-select consumers can read `useUIStore((s) => s.selectedTerritoryIds)` for the gold outline (D-17), the existing single-select consumers can keep reading `selectedTerritoryId` until migrated to `selectSelectedTerritoryId`. InteractionLayer's new `selectedTerritoryIds: string[]` prop (per UI-SPEC §4) maps cleanly.
- **Plan 03-06 / 03-07 (Wave 3 deletion) cleared.** No new orphaned modules introduced; v1 LayerName 'terrain' + overlay fields removed already; selectedTerritoryId mirror documented as deletion candidate.

## Verification

- `cd frontend && npm run test -- --run src/stores/__tests__/useRunStore.test.ts` → **12/12 green**
- `cd frontend && npm run test -- --run src/stores/uiStore.test.ts` → **9/9 green**
- `cd frontend && npm run test -- --run src/hooks/useCanvasArtifacts.cacheVersion.test.ts src/components/canvas/__tests__/CanvasViewer.{,hydrate,resize,panOnSelect}.test.tsx` → **34/34 green**
- `cd frontend && npm run test -- --run` (full suite) → **238/238 green across 39 files**
- `grep -rn "/preview/" frontend/src/hooks/ frontend/src/components/canvas/__tests__/` → **zero matches**
- `grep -c "/api/v3/projects/" frontend/src/hooks/useCanvasArtifacts.ts` → **5**
- `grep -n "PIPELINE_STAGES" frontend/src/stores/useRunStore.ts` → **3 hits (export const + type alias + tests reference)**
- `grep -nE "logLines.*slice\(-500\)|LOG_CAP" frontend/src/stores/useRunStore.ts` → **2 hits (cap definition + slice usage)**
- `grep -n "selectedTerritoryIds" frontend/src/stores/uiStore.ts` → **6 hits**
- `grep -n "'terrain'" frontend/src/stores/uiStore.ts` → **3 hits, all in doc comment** (no live code uses 'terrain' as a LayerName key after the rewrite — verified by `Object.keys(layerVisibility)` test)
- `grep -nE "overlayImageUrl|overlayOpacity" frontend/src/stores/uiStore.ts` → **1 hit, in doc comment only** (no live code references)

## Self-Check: PASSED

- FOUND: frontend/src/stores/useRunStore.ts (PIPELINE_STAGES, RunState, LOG_CAP, useRunStore)
- FOUND: frontend/src/stores/__tests__/useRunStore.test.ts (12 tests passing)
- FOUND: frontend/src/stores/uiStore.ts (selectedTerritoryIds, selectedTerritoryId mirror, selectIds, selectSelectedTerritoryId selector)
- FOUND: frontend/src/stores/uiStore.test.ts (9 tests passing)
- FOUND: frontend/src/hooks/useCanvasArtifacts.ts (5 v3 URLs, no /preview/ refs)
- FOUND: frontend/src/hooks/useCanvasArtifacts.cacheVersion.test.ts (2 tests passing)
- FOUND: frontend/src/components/canvas/__tests__/CanvasViewer.hydrate.test.tsx (7 tests passing, regex updated)
- FOUND: frontend/src/components/canvas/CanvasViewer.tsx (line 262 v3 URL)
- DELETED: frontend/src/stores/__tests__/uiStore.test.ts (orphan removed)
- FOUND commit: 561f999 (Task 1 — feat useRunStore)
- FOUND commit: fcb2ebf (Task 2 — refactor uiStore + delete orphan)
- FOUND commit: f7a0576 (fix — mirror selectedTerritoryId)
- FOUND commit: f9e8a55 (Task 3 — feat v3 URL switch)
- VITEST: full suite 238/238 green across 39 files; no regressions

---
*Phase: 03-read-only-canvas-redesign*
*Completed: 2026-05-09*
