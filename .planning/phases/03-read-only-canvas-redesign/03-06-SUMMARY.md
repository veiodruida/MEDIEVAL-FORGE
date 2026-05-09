---
phase: 03-read-only-canvas-redesign
plan: 06
subsystem: frontend
tags: [deletion, v1-purge, edit-graph, stepper, llm-frontend]

# Dependency graph
requires:
  - phase: 03-read-only-canvas-redesign
    plan: 04
    provides: ProjectDetail workspace shell (no longer references v1 modules)
  - phase: 03-read-only-canvas-redesign
    plan: 05
    provides: CanvasViewer + TerritoryLayer + LayerTogglePanel stripped of v1 imports
provides:
  - "Frontend graph free of v1 edit/stepper/LLM dependencies"
  - "InspectorSidebar.tsx stripped of useResearchStore + useValidationStore (Plan 05 deferred consumer cleanup)"
  - "api/client.ts trimmed to 8 hooks (Project CRUD + Presets + StatusManifest + useExport + buildBaronies)"
  - "main.tsx persistence bootstrap removed"
affects:
  - "03-07 (backend D-12+D-13 purge — frontend half done; backend api/{ingest,research,codex,llm}.py + services/{ingest_runner,ingest_wikidata,research_runner,research_cache,llm/} deletion now unblocked)"
  - "03-08 (Playwright UAT — surface area finalized; only the canvas workspace + ProjectList + ProjectNew remain to test)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pitfall-1 grep gate excluding intentional test denylist literals (ProjectDetail.workspace.test.tsx forbidden-symbols array) — single non-matching grep over source files only"
    - "Atomic combined deletion (D-10+D-11+D-13 in one commit) — Task 1 alone left the build broken because ResearchDialog imports api/edit + AssignmentEditor (Task 1 deletions); separation cannot satisfy `npm run build` between commits"

key-files:
  modified:
    - frontend/src/components/canvas/InspectorSidebar.tsx (stripped useResearchStore + useValidationStore + research badges + validation issues block)
    - frontend/src/main.tsx (removed initPersistence bootstrap)
    - frontend/src/api/client.ts (rewrote — kept 8 hooks, dropped 5 v1 hooks)
    - frontend/src/components/workspace/RunLogPanel.tsx (Radix Card invalid `p` prop replaced with style.padding — pre-existing typecheck blocker unblocked)
    - frontend/src/stores/uiStore.ts (docstring scrubbed of TerrainBadgesLayer reference for grep cleanliness)
  deleted:
    # D-10 — edit-only graph
    - frontend/src/pages/TerritoryEditor.tsx
    - frontend/src/components/canvas/EditToolbar.tsx
    - frontend/src/components/canvas/SplitTool.tsx
    - frontend/src/components/canvas/VertexHandlesLayer.tsx
    - frontend/src/components/canvas/SelectionFloatingToolbar.tsx
    - frontend/src/components/canvas/ValidationBadgesLayer.tsx
    - frontend/src/components/canvas/TerrainBadgesLayer.tsx
    - frontend/src/components/canvas/SaveStatusIndicator.tsx
    - frontend/src/components/canvas/SettingsPanel.tsx
    - frontend/src/components/canvas/__tests__/SplitTool.test.tsx
    - frontend/src/components/canvas/__tests__/TerrainBadgesLayer.test.tsx
    - frontend/src/components/canvas/__tests__/CapitalDrag.test.tsx
    - frontend/src/components/canvas/__tests__/TerritoryLayer.shiftClick.test.tsx
    - frontend/src/stores/useEditorStore.ts
    - frontend/src/stores/useValidationStore.ts
    - frontend/src/stores/useProjectStore.ts
    - frontend/src/stores/__tests__/useEditorStore.test.ts
    - frontend/src/stores/__tests__/useProjectStore.test.ts
    - frontend/src/hooks/useUndoShortcut.ts
    - frontend/src/hooks/useBeforeUnloadGuard.ts
    - frontend/src/hooks/useEditKeyboardMap.ts
    - frontend/src/hooks/useRubberBandSelection.ts
    - frontend/src/hooks/__tests__/useUndoShortcut.test.ts
    - frontend/src/hooks/__tests__/useRubberBandSelection.test.ts
    - frontend/src/api/edit.ts
    - frontend/src/services/persistence.ts
    - frontend/src/services/validation.ts
    - frontend/src/services/__tests__/persistence.test.ts
    - frontend/src/services/__tests__/validation.test.ts
    - frontend/src/components/research/AssignmentEditor.tsx
    - frontend/src/components/research/AssignmentEditor.test.tsx
    # D-11 — v1 stepper UI
    - frontend/src/components/pipeline/Stepper.tsx
    - frontend/src/components/pipeline/Stepper.test.tsx
    - frontend/src/components/pipeline/StepCard.tsx
    - frontend/src/components/pipeline/StepCard.test.tsx
    - frontend/src/components/pipeline/ProviderEffortPicker.tsx
    - frontend/src/components/pipeline/ProviderEffortPicker.test.tsx
    - frontend/src/components/pipeline/TerrainDataSection.tsx
    - frontend/src/components/pipeline/__tests__/TerrainDataSection.test.tsx
    - frontend/src/components/ingest/BaronyGranularitySlider.tsx
    - frontend/src/stores/usePipelineStore.ts
    - frontend/src/stores/__tests__/usePipelineStore.test.ts
    - frontend/src/api/useTerrainStepStream.ts
    - frontend/src/api/__tests__/useIngestStream.test.tsx
    # D-13 — frontend LLM purge
    - frontend/src/components/research/ResearchDialog.tsx
    - frontend/src/components/research/ResearchDialog.test.tsx
    - frontend/src/components/research/AuthSetupSheet.tsx
    - frontend/src/components/research/ManualResearchPanel.tsx
    - frontend/src/components/research/ProviderSelector.tsx
    - frontend/src/components/codex/CodexViewer.tsx
    - frontend/src/components/codex/CodexViewer.test.tsx
    - frontend/src/stores/useResearchStore.ts
    - frontend/src/hooks/useResearchStream.ts
    - frontend/src/hooks/useResearchStream.test.ts
    - frontend/src/hooks/useCodexStream.ts
    - frontend/src/hooks/useCodexStream.test.ts
    - frontend/src/api/research.ts
    - frontend/src/api/codex.ts

key-decisions:
  - "Combined D-10 + D-11 + D-13 deletions into one atomic commit. Reason: ResearchDialog.tsx (D-13 target) imports api/edit (D-10 target) and AssignmentEditor (D-10 target). Splitting would leave the build broken between Task 1 and Task 2 commits, violating the plan's `npm run build green` acceptance gate. The plan structured them as 2 tasks for didactic clarity; the build constraint forces unification."
  - "InspectorSidebar.tsx stripped of useResearchStore + useValidationStore in this plan (Rule 3 — blocking). Plan 05 SUMMARY explicitly punted this consumer cleanup to Wave 3 (handoff note). Strip removes: research-derived Reino/Ducado solid badges (lines 181-187 pre-strip) and validation issues block (lines 232-251 pre-strip). Single-select detail view + English COPY constants intact; PT-BR placeholder + multi-select dispatcher unchanged."
  - "api/client.ts rewritten as a fresh minimal file (8 surviving hooks) instead of surgical edits. Cleaner diff, no dead helper utilities. Surviving hooks: useStatusManifest, usePresets, useProjects, useProject, useCreateProject, useUpdateProject, useDeleteProject, useExport, plus buildBaronies + Project/Preset/StatusManifest/ProjectCreatePayload/ProjectUpdatePayload/ExportResponse interfaces."
  - "main.tsx initPersistence bootstrap removed (services/persistence.ts deleted in D-10). One import + one call site stripped; no replacement (read-only canvas needs no localStorage strategy gate)."
  - "RunLogPanel.tsx Radix Themes Card `p='3'` prop replaced with style.padding (Rule 1 — bug). Pre-existing TS2322 error blocked the post-deletion typecheck gate; minimum-impact fix is a single line. Recorded as deviation since it's outside the deletion scope. Reproduced via `git stash + tsc -b` confirming pre-existence."
  - "Pitfall-1 grep filter pragma: ProjectDetail.workspace.test.tsx forbidden-symbol array (lines 327-346) contains intentional string literals like 'useEditorStore', 'useResearchStore' as a regression denylist. These are NOT broken imports. The verification grep excludes that one test file; matches in source files (.ts/.tsx) outside tests is the gate."
  - "Plan Task 1 step 2 (`App.tsx remove /projects/:id/edit route + lazy import`) was a no-op. Plan 04's ProjectDetail rewrite did not register that route in the first place; current App.tsx only routes /projects, /projects/new, /projects/:id, /canvas-smoke. Documented as advisor-confirmed already-clean state."
  - "useExport kept (consumed by ProjectDetail Exportar ZIP, advisor-confirmed in Plan 04 SUMMARY decision #1). Plan 06 step 3 explicitly permits this exception. The remaining v1 hooks (useIngestStream, useGenerate, useTerritoryTemplate, useRenderModern, useIngestStatus) were grep-confirmed zero consumers and dropped."

requirements-completed: [SC-3]

# Metrics
duration: ~12min
completed: 2026-05-09
---

# Phase 03 Plan 06: Mechanical deletion sweep (D-10 + D-11 + D-13) Summary

**63 v1 frontend files purged (8764 LOC deleted, 3 added) in one atomic commit covering D-10 (edit-only graph), D-11 (v1 stepper UI), and D-13 (frontend LLM stack). InspectorSidebar.tsx stripped of useResearchStore + useValidationStore (Plan 05's Wave 3 handoff). api/client.ts trimmed to 8 hooks. Pitfall-1 grep returns zero in source files. tsc + vitest + vite build all green; 154/154 specs passing.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-09T21:44:47Z
- **Completed:** 2026-05-09T21:56Z
- **Tasks:** Combined into 1 atomic commit (plan structured as 2)
- **Commits:** 1 atomic
- **Files deleted:** 63
- **Files modified:** 5
- **Net LOC:** −8761 (8764 deletions − 3 insertions)

## Accomplishments

- **D-10 — edit-only graph deletion:** 31 source + test files removed (TerritoryEditor page, 8 edit-only canvas components, 4 hooks, 4 stores, edit api, 2 services + 6 test files + AssignmentEditor + AssignmentEditor.test).
- **D-11 — v1 stepper UI deletion:** 13 files removed (entire pipeline/ subdir incl. 4 components + 4 tests, BaronyGranularitySlider + test, usePipelineStore + test, useTerrainStepStream + useIngestStream test).
- **D-13 — frontend LLM purge:** 14 files removed (ResearchDialog + test + 3 research support components, CodexViewer + test, useResearchStore, useResearchStream + test, useCodexStream + test, api/research.ts, api/codex.ts).
- **InspectorSidebar.tsx stripped:** Plan 05's documented Wave 3 handoff (`useResearchStore` + `useValidationStore` consumers) cleaned. Research solid badges + validation issues block removed. Single-select detail view + 13 English COPY constants intact; PT-BR placeholder + multi-select dispatcher unchanged.
- **api/client.ts trim:** Rewrote with 8 surviving hooks — useStatusManifest, usePresets, useProjects, useProject, useCreateProject, useUpdateProject, useDeleteProject, useExport, plus the buildBaronies helper. Dropped useIngestStream + IngestStreamHandle, useGenerate, useTerritoryTemplate, useRenderModern, useIngestStatus + IngestStatus interface.
- **main.tsx persistence bootstrap removed:** `import { initPersistence } from './services/persistence'` + `initPersistence()` deletion (services/persistence.ts purged in D-10).
- **RunLogPanel.tsx pre-existing typecheck error fixed:** Radix Themes `<Card p="3">` prop is invalid since v3; replaced with `style.padding: var(--space-3)`. Confirmed pre-existing via `git stash + tsc -b` reproduction.
- **App.tsx already clean:** Plan Task 1 step 2 ("remove /projects/:id/edit route") was a no-op — Plan 04's ProjectDetail rewrite never registered that route.
- **Vitest 154/154 green across 24 files** (was 268/268 across 45 files pre-purge — drop reflects deleted test files for deleted modules; zero regressions on surviving specs).

## Task Commits

| # | Task | Type | Commit |
|---|------|------|--------|
| 1+2 | Combined D-10 + D-11 + D-13 purge (63 files) | chore | `4ff5b64` |

## Files Created/Modified

See `key-files` block in frontmatter (63 deletions, 5 modifications).

## Decisions Made

See `key-decisions` block in frontmatter. Highlights:

- **Combined deletion commit (Rule 3 deviation).** ResearchDialog imports api/edit + AssignmentEditor (both D-10 targets). Two-commit split would leave Task 1 with broken build. Plan 06 verify gates demand `npm run build green` — only achievable with combined commit.
- **InspectorSidebar consumer strip (Rule 3 deviation).** Plan 05 SUMMARY explicitly handed this off to Wave 3. Producer deletion (useResearchStore + useValidationStore) forces consumer cleanup in same commit.
- **RunLogPanel `p` prop fix (Rule 1 deviation).** Pre-existing TS error blocks the gate. Minimum 1-line fix; out-of-scope-but-blocking is the textbook case for this rule.

## Deviations from Plan

**Total deviations:** 4 — all advisor-confirmed; all Rule 1/3.

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Combined Task 1 + Task 2 into single atomic commit**
- **Found during:** End-of-Task-1 typecheck after staging D-10 deletions.
- **Issue:** `frontend/src/components/research/ResearchDialog.tsx` imports `from "../../api/edit"` (D-10 deletion target) and `from "./AssignmentEditor"` (D-10 deletion target). Plan placed ResearchDialog in Task 2; deleting api/edit + AssignmentEditor in Task 1 alone left the typecheck broken.
- **Fix:** Pull all D-11 + D-13 deletions forward into the same commit. Records as one combined commit message preserving both task narratives.
- **Files modified:** All 63 deletion targets bundled together.
- **Commit:** `4ff5b64`.

**2. [Rule 3 — Blocking] InspectorSidebar.tsx stripped of useResearchStore + useValidationStore**
- **Found during:** Pre-Task 1 inventory grep.
- **Issue:** Survivor `InspectorSidebar.tsx` imports `useResearchStore` (research badges in single-select view) + `useValidationStore` (validation issues block). Plan 05 SUMMARY notes: "InspectorSidebar.tsx still imports useResearchStore + useValidationStore. Both will be removed by Wave 3 along with the stores themselves." Producer deletion in this plan forces consumer cleanup.
- **Fix:** Remove both imports; remove the `manualResult`/`researchAssignment`/`researchKingdomName`/`researchDuchyName` derivations + the research badges JSX (Reino/Ducado solid Badges); remove `allIssues`/`validationIssues` + the "Problemas de Validação" JSX block. Single-select detail view + 13 English COPY constants verbatim; PT-BR placeholder + multi-select dispatcher untouched.
- **Files modified:** `frontend/src/components/canvas/InspectorSidebar.tsx`.
- **Commit:** `4ff5b64`. Existing 10-spec InspectorSidebar.test.tsx still green (no specs covered the removed branches per Plan 05 contract rebaseline).

**3. [Rule 1 — Bug] RunLogPanel.tsx Radix Card invalid `p` prop**
- **Found during:** Post-Task-1 typecheck.
- **Issue:** `<Card p="3" ...>` triggers `error TS2322 Property 'p' does not exist on type 'CardProps'`. Reproduced as pre-existing via `git stash` + `tsc -b` on baseline. The plan does not target this file; however its typecheck error blocks the deletion gate.
- **Fix:** Replace `p="3"` with `style.padding: 'var(--space-3)'`. One line.
- **Files modified:** `frontend/src/components/workspace/RunLogPanel.tsx`.
- **Commit:** `4ff5b64`.

**4. [No-op] App.tsx route already clean — Plan Task 1 step 2 was redundant**
- **Found during:** Pre-Task 1 read of App.tsx.
- **Issue:** Plan asked to remove `/projects/:id/edit` route + lazy import of TerritoryEditor. App.tsx in current main only registers `/`, `/projects`, `/projects/new`, `/projects/:id`, `/canvas-smoke`. Plan 04's rewrite never wired the edit route.
- **Fix:** None required. Documented in commit body and deviations.

## Authentication Gates

None. Phase 03 is local-only by D-20.

## Issues Encountered

None outside the 4 deviations above.

## User Setup Required

None.

## Next Phase Readiness

- **Plan 03-07 (backend D-12 + D-13 purge) cleared.** Frontend LLM client surface is gone — no consumers of `/api/research/*`, `/api/codex/*`, `/api/llm/*`, or `/api/projects/{id}/ingest` (v1 GET-SSE) remain. Backend `api/{ingest,research,codex,llm}.py` + `services/{ingest_runner,ingest_wikidata,research_runner,research_cache,llm/}` deletion is mechanical.
- **Plan 03-08 (Playwright UAT) ready.** Surface area finalized to: ProjectList, ProjectNew, ProjectDetail (workspace shell + canvas), `/canvas-smoke` (DEV-only).
- **Phase 03 SC-3 (no console errors) prerequisite met for FE.** Pitfall-1 grep returns zero in source; build + tsc + vitest all green. Final SC-3 verification awaits Plan 03-08 Playwright smoke.

## Verification

- `cd frontend && npx tsc -b 2>&1 | tail -5` → **zero errors**
- `cd frontend && npm test -- --run` → **154 passed (24 files)**; expected drop from 268 due to deleted test files for deleted modules
- `cd frontend && npm run build 2>&1 | tail -10` → **green** (1.87s, 451 modules transformed, 718 KB JS / 693 KB CSS bundles)
- Pitfall-1 grep over `frontend/src/ --include='*.ts' --include='*.tsx' | grep -v ProjectDetail.workspace.test` → **zero hits**
- `grep -nE "useIngestStream|useGenerate|useTerritoryTemplate|useRenderModern|useIngestStatus" frontend/src/api/client.ts` → **zero hits**
- `grep -nE "TerritoryEditor|/projects/:id/edit" frontend/src/App.tsx` → **zero hits**
- `find frontend/src/components/pipeline frontend/src/components/research frontend/src/components/codex` → all 3 directories absent
- `git show --stat 4ff5b64 | tail -1` → `63 files changed, 3 insertions(+), 8764 deletions(-)`

## Self-Check: PASSED

- FOUND commit: 4ff5b64 (chore(03-06) — purge v1 frontend)
- DELETED: frontend/src/pages/TerritoryEditor.tsx
- DELETED: frontend/src/components/canvas/EditToolbar.tsx
- DELETED: frontend/src/components/canvas/SplitTool.tsx
- DELETED: frontend/src/components/canvas/VertexHandlesLayer.tsx
- DELETED: frontend/src/components/canvas/SelectionFloatingToolbar.tsx
- DELETED: frontend/src/components/canvas/ValidationBadgesLayer.tsx
- DELETED: frontend/src/components/canvas/TerrainBadgesLayer.tsx
- DELETED: frontend/src/components/canvas/SaveStatusIndicator.tsx
- DELETED: frontend/src/components/canvas/SettingsPanel.tsx
- DELETED: frontend/src/components/pipeline/ (dir)
- DELETED: frontend/src/components/research/ (dir)
- DELETED: frontend/src/components/codex/ (dir)
- DELETED: frontend/src/components/ingest/BaronyGranularitySlider.tsx
- DELETED: frontend/src/stores/{useEditorStore,useValidationStore,useProjectStore,usePipelineStore,useResearchStore}.ts
- DELETED: frontend/src/hooks/{useUndoShortcut,useBeforeUnloadGuard,useEditKeyboardMap,useRubberBandSelection,useResearchStream,useCodexStream}.ts
- DELETED: frontend/src/api/{edit,research,codex,useTerrainStepStream}.ts
- DELETED: frontend/src/services/{persistence,validation}.ts
- FOUND: frontend/src/components/canvas/InspectorSidebar.tsx (no useResearchStore/useValidationStore imports)
- FOUND: frontend/src/api/client.ts (8 hooks; no v1-only hooks)
- FOUND: frontend/src/main.tsx (no initPersistence)
- VITEST: 154/154 green
- TSC: zero errors
- VITE BUILD: green

---
*Phase: 03-read-only-canvas-redesign*
*Completed: 2026-05-09*
