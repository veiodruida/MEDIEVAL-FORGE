---
phase: "04"
plan: "03"
subsystem: "frontend/parameter-studio"
tags: ["slider", "debounce", "sse", "cancel", "zustand", "radix-ui"]
dependency_graph:
  requires: ["04-00", "04-02"]
  provides: ["slider-state", "render-api-helpers", "render-stream-consumer", "cancel-button", "parameter-sidebar"]
  affects: ["04-04", "04-05", "04-06"]
tech_stack:
  added: ["use-debounce@10.1.1"]
  patterns: ["useDebouncedCallback+flush for skip-debounce", "latest-wins SSE cancel sequence", "Zustand setState in beforeEach for test isolation", "FakeEventSource shim for jsdom EventSource gap"]
key_files:
  created:
    - frontend/src/api/render.ts
    - frontend/src/api/useRenderStream.ts
    - frontend/src/stores/usePipelineParams.ts
    - frontend/src/hooks/useParameterStudioDispatch.ts
    - frontend/src/components/canvas/SliderCard.tsx
    - frontend/src/components/canvas/StageViewToggle.tsx
    - frontend/src/components/canvas/ParameterSidebar.tsx
    - frontend/src/api/__tests__/useRenderStream.test.ts
    - frontend/src/stores/__tests__/usePipelineParams.test.ts
    - frontend/src/components/canvas/__tests__/SliderCard.test.tsx
    - frontend/src/components/canvas/__tests__/StageViewToggle.test.tsx
    - frontend/src/components/canvas/__tests__/ParameterSidebar.test.tsx
    - frontend/src/components/workspace/__tests__/WorkspaceToolbar.cancel.test.tsx
  modified:
    - frontend/src/stores/useRunStore.ts
    - frontend/src/components/workspace/WorkspaceToolbar.tsx
    - frontend/package.json
    - frontend/package-lock.json
  deleted:
    - frontend/src/stores/useRenderStore.ts
decisions:
  - "useParameterStudioDispatch extracted to hooks/ (not inlined in store) to isolate projectId dependency and enable direct debounce testing without rendering a full component"
  - "showCancel = runState === 'rendering' only — NOT 'generating' (per UI-SPEC §State Machine: cancel visible only during incremental re-render, not during full generate SSE which has no cancel endpoint)"
  - "useRenderStore absorbed into useRunStore in Task 4 (not a separate plan) to keep 04-03/04-04/04-05 parallel-safe in Wave 3"
  - "vi.clearAllMocks() replaced by per-mock mockReset()+mockResolvedValue() in beforeEach — clearAllMocks nukes return values set in vi.mock() factory, causing .catch() TypeError"
  - "FakeEventSource shim pattern (class with emit()/emitRaw()/triggerError()/close()) matches ProjectDetail.workspace.test.tsx precedent — jsdom has no EventSource"
metrics:
  duration_minutes: 95
  completed_date: "2026-05-10"
  tasks_completed: 4
  tasks_total: 4
  files_created: 13
  files_modified: 4
  files_deleted: 1
  tests_added: 26
---

# Phase 04 Plan 03: Parameter Studio UI Shell Summary

**One-liner:** 250ms-debounced slider-to-render pipeline with latest-wins SSE cancel, 320px collapsible sidebar, and WorkspaceToolbar cancel-button swap — 26 new tests, all green.

## What Was Built

### Task 1 — Render API + Stream Consumer + Pipeline Params Store

- `frontend/src/api/render.ts`: `postRender`, `postRenderCancel` (404=success), `getStageRasterUrl`, types `CfgOverrides`/`StageView`/`RenderResponse`
- `frontend/src/api/useRenderStream.ts`: EventSource subscriber for `/render/stream`; dispatches `stage_start/stage_done/stage_cancel/done/error` to `useRunStore`; `stage_cancel` sets `cancelled=true` + calls `revertStage`; `done` branches on `cancelled` → `cancelRender()` vs `finish('generated')`
- `frontend/src/stores/usePipelineParams.ts`: Zustand store with `PARAM_DEFAULTS` (`smooth_sigma=3.0, median_passes=8, fragment_min_px=600, blob_merge_px=200`), `PARAM_BOUNDS`, `stageView` (client-only, not in render diff), `sidebarOpen`, `diffOverrides()` pure function
- `frontend/src/hooks/useParameterStudioDispatch.ts`: `useDebouncedCallback(async, 250)` with `.flush()` for bypass; sequence: `postRenderCancel` → `postRender` → `startRender(run_id)` → `markRendered(values)`
- 9 tests: 4 `usePipelineParams` + 5 `useRenderStream`

### Task 2 — Slider Components + Sidebar

- `frontend/src/components/canvas/SliderCard.tsx`: Radix `Slider.Root` + `<input type="number">` + `ResetIcon` IconButton + default-tick div at `((def-min)/(max-min)*100)%`; `data-flash` attribute + 600ms red border on out-of-bounds clamp; `resetSlider` + `onResetCommit()` bypasses debounce
- `frontend/src/components/canvas/StageViewToggle.tsx`: Radix `RadioGroup` with 5 items (landmask/voronoi-raw/cleanup/smooth/render-final); default `render-final`; `data-testid="stage-view-toggle"`
- `frontend/src/components/canvas/ParameterSidebar.tsx`: `SIDEBAR_W=320`; `borderRight: '1px solid var(--gray-6)'`; returns `null` when `sidebarOpen===false`; `StageViewToggle` + 4 `SliderCard` instances stacked
- 13 tests: 5 `SliderCard` + 4 `StageViewToggle` + 4 `ParameterSidebar`

### Task 3 — WorkspaceToolbar Cancel Button

- `WorkspaceToolbar.tsx`: added `MixerHorizontalIcon` toggle (`aria-pressed`, toggles `usePipelineParams.sidebarOpen`) in left zone; `showCancel = runState === 'rendering'` (not `'generating'`); red `color="red" variant="solid"` Cancelar button replaces `GenerateStatusBadge` during rendering; `isRunning` gates Gerar Mapa button
- 4 tests in `WorkspaceToolbar.cancel.test.tsx`

### Task 4 — Absorb useRenderStore into useRunStore

- `useRunStore.ts` extended: `'rendering'` added to `RunState` union; `priorTokens: Record<string, string>`, `affectedStages: PipelineStage[]` fields; `startRender(runId, affectedStages?)`, `revertStage(stage, priorToken)`, `cancelRender()` actions
- `useRenderStore.ts` deleted
- All 4 consumers migrated: `useRenderStream`, `WorkspaceToolbar`, `ParameterSidebar`, `useParameterStudioDispatch`
- WorkspaceToolbar changed to `import type { PipelineStage, RunState }` (no runtime value import) — fixes TS6133

## Test Results

- **182 tests pass, 8 skipped** (8 skipped = Wave 0 stubs in `useCanvasArtifacts.cacheVersion.test.ts` + `BaronyLabels` — owned by 04-04/04-05)
- `tsc -b` exits 0
- `use-debounce@10.1.1` installed

## Commits

| Task | Hash | Message |
|------|------|---------|
| 1 | b534f56 | feat(04-03): install use-debounce + create api/render + render stream + pipeline params stores |
| 2 | 9d35bcd | feat(04-03): build SliderCard + StageViewToggle + ParameterSidebar components |
| 3 | a246467 | feat(04-03): WorkspaceToolbar sidebar toggle + Cancel button swap (D-16) |
| 4 | e297acc | feat(04-03): absorb useRenderStore into useRunStore + migrate all consumers (Task 4) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] showCancel included 'generating' state — hid badge during generate flow**
- Found during: Task 3 + Task 4 regression
- Issue: `showCancel = runState === 'generating' || runState === 'rendering'` caused `ProjectDetail.workspace.test.tsx` test "badge color is amber + copy is 'Gerando: voronoi' during generating state" to fail; UI-SPEC §State Machine explicitly states cancel is NOT shown during `generating` (generate SSE has no cancel endpoint)
- Fix: `showCancel = runState === 'rendering'` only; all cancel tests updated to use `runState='rendering'`
- Files modified: `WorkspaceToolbar.tsx`, `WorkspaceToolbar.cancel.test.tsx`
- Commit: a246467

**2. [Rule 1 - Bug] vi.clearAllMocks() nuked mock return values → .catch() TypeError**
- Found during: Task 1 test authoring
- Issue: `vi.clearAllMocks()` in `beforeEach` reset `postRenderCancel` to return `undefined`, breaking `.catch()` chain
- Fix: Replaced `vi.clearAllMocks()` with per-mock `mockReset()` + `mockResolvedValue()` in `beforeEach`; used factory pattern (`const mockX = vi.fn()` + `vi.mock(() => ({...}))`)
- Files modified: `usePipelineParams.test.ts`, `useRenderStream.test.ts`
- Commit: b534f56

**3. [Rule 1 - Bug] mock.invocationCallOrder undefined — wrong API for call-order assertion**
- Found during: Task 1 (latest-wins test)
- Issue: Used `mock.invocationCallOrder[0]` (Jasmine API) — not available in Vitest
- Fix: Replaced with shared `callOrder: string[]` array pushed by mock implementations; asserted `expect(callOrder).toEqual(['cancel', 'render'])`
- Files modified: `usePipelineParams.test.ts`
- Commit: b534f56

**4. [Rule 2 - Missing critical] useParameterStudioDispatch extracted to separate hooks/ file**
- Found during: Task 1 planning (advisor call)
- Issue: Plan implied dispatch logic inside `usePipelineParams` store — mixing `projectId` (component concern) with pure store state
- Fix: Created `frontend/src/hooks/useParameterStudioDispatch.ts` as separate hook with `projectId` param; `usePipelineParams` stays a pure Zustand store with no `projectId` dependency
- Files modified: New file `useParameterStudioDispatch.ts`; `ParameterSidebar.tsx` uses the hook
- Commit: b534f56

**5. [Rule 3 - Blocking] TypeScript TS6133 — useRunStore runtime import unused in WorkspaceToolbar**
- Found during: Task 4 migration
- Issue: `import { useRunStore } from '../../stores/useRunStore'` — only types needed, value import caused TS6133
- Fix: Changed to `import type { PipelineStage, RunState } from '../../stores/useRunStore'`
- Files modified: `WorkspaceToolbar.tsx`
- Commit: e297acc

## Known Stubs

None — all slider values flow to real `postRender` calls; no placeholder text or hardcoded empty arrays in the rendering path.

## Self-Check: PASSED

Files verified to exist:
- `frontend/src/api/render.ts` FOUND
- `frontend/src/api/useRenderStream.ts` FOUND
- `frontend/src/stores/usePipelineParams.ts` FOUND
- `frontend/src/hooks/useParameterStudioDispatch.ts` FOUND
- `frontend/src/components/canvas/SliderCard.tsx` FOUND
- `frontend/src/components/canvas/StageViewToggle.tsx` FOUND
- `frontend/src/components/canvas/ParameterSidebar.tsx` FOUND

Commits verified:
- b534f56 FOUND
- 9d35bcd FOUND
- a246467 FOUND
- e297acc FOUND

useRenderStore.ts deleted: CONFIRMED (0 runtime references remain)
