---
phase: "04"
plan: "04"
subsystem: "frontend/canvas-hydration"
tags: ["wave-3", "konva", "clearcache", "stage-view", "prior-token", "tanstack-query"]
dependency_graph:
  requires:
    - frontend/src/api/render.ts (StageView type — from 04-03)
    - frontend/src/stores/useRunStore.ts (priorTokens + revertStage — from 04-03 Task 4)
    - frontend/src/stores/usePipelineParams.ts (stageView — from 04-03)
    - backend/medieval_forge/api/v3/render.py (GET /stage/{name}.png endpoint — from 04-02)
  provides:
    - frontend/src/hooks/useCanvasArtifacts.ts (6-tuple return with stageRasterUrl + stageView-keyed queries)
    - frontend/src/components/canvas/CanvasViewer.tsx (clearCache discipline + isStageOverlay gating + priorToken swap)
    - frontend/src/components/canvas/__tests__/CanvasViewer.clearCache.test.tsx (3 wired clearCache tests)
  affects:
    - 04-05 (BaronyLabels — reads useCanvasArtifacts 6-tuple; [5] is now stageRasterUrl string)
    - 04-06 (e2e: parameter-studio-cancel spec exercises priorToken swap path)
tech_stack:
  added: []
  patterns:
    - "useCanvasArtifacts 6-tuple: [territoriesQ, baroniesQ, condadoColorsQ, baronyColorsQ, metaQ, stageRasterUrl]"
    - "stageView in all 5 TanStack queryKeys — stage-view switch invalidates in-memory cache"
    - "effectiveCacheVersion = priorTokens.render ?? cacheVersion (D-13 cancel revert)"
    - "Konva.Stage.getLayers() iteration for clearCache — typed alternative to findAll('Layer')"
    - "React.forwardRef + useImperativeHandle fake stage for clearCache unit tests"
    - "isStageOverlay = stageView !== 'render-final' gates TerritoryLayer/BaronyLayer/DecorationsLayer"
key_files:
  created:
    - frontend/src/components/canvas/__tests__/CanvasViewer.clearCache.test.tsx
  modified:
    - frontend/src/hooks/useCanvasArtifacts.ts
    - frontend/src/components/canvas/CanvasViewer.tsx
    - frontend/src/components/canvas/__tests__/CanvasViewer.resize.test.tsx
decisions:
  - "getLayers() used instead of findAll('Layer') — findAll is not in Konva TypeScript type definitions; getLayers() is the typed Stage method returning Layer[] directly (Rule 1 deviation from plan implementation detail, same behavior)"
  - "useCanvasArtifacts 6-tuple backward-compatible at indices [0]..[4]; index [5] is new stageRasterUrl string"
  - "CanvasViewer.resize.test.tsx mock updated to 6-tuple (Rule 3 - blocking: would have broken destructure)"
metrics:
  duration: "~7 minutes"
  completed: "2026-05-10"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 3
  tests_added: 3
---

# Phase 04 Plan 04: Canvas Hydration — clearCache + stageView + priorToken Summary

**One-liner:** stageView-keyed 6-tuple from useCanvasArtifacts + Pitfall-6-compliant Konva.clearCache per layer + D-13 priorToken cacheVersion swap + isStageOverlay layer-visibility gate, proven by 3 new clearCache unit tests.

## What Was Built

### Task 1 — useCanvasArtifacts re-key on stageView + stageRasterUrl (6th return)

**New signature:**
```typescript
export function useCanvasArtifacts(
  projectId: string | undefined,
  projection: ProjectionConfig | null,
  cacheVersion?: string,
  stageView: StageView = 'render-final',  // NEW — defaults to existing behavior
)
```

**New return shape (6-tuple):**
```typescript
return [
  results[0],          // territoriesQ  → TerritoryRender[]
  results[1],          // baroniesQ     → BaronyRender[]
  results[2],          // condadoColorsQ → Record<string, string>
  results[3],          // baronyColorsQ → Record<string, string>
  { ...results[4], data: mergedMeta },  // metaQ with hoisted neighbors
  stageRasterUrl,      // NEW: string URL — not a query result
] as const
```

**stageRasterUrl logic:**
```typescript
const stageRasterUrl =
  stageView === 'render-final'
    ? `/api/v3/projects/${projectId}/artifacts/visual_condado.png${v}`
    : `/api/v3/projects/${projectId}/stage/${stageView}.png${v}`
```

All 5 queryKeys re-keyed on stageView:
```typescript
queryKey: ['territories-geojson', projectId, cacheVersion, stageView] as const
queryKey: ['baronies-geojson', projectId, cacheVersion, stageView] as const
queryKey: ['condado-colors', projectId, cacheVersion, stageView] as const
queryKey: ['barony-colors', projectId, cacheVersion, stageView] as const
queryKey: ['territory-metadata', projectId, cacheVersion, stageView] as const
```

### Task 2 — CanvasViewer wiring

**New imports:**
```typescript
import Konva from 'konva'  // default import (was `type Konva`)
import { usePipelineParams } from '../../stores/usePipelineParams'
import { useRunStore } from '../../stores/useRunStore'
```

**D-13 effectiveCacheVersion:**
```typescript
const stageView = usePipelineParams((s) => s.stageView)
const priorTokens = useRunStore((s) => s.priorTokens)
const effectiveCacheVersion =
  priorTokens.render !== undefined ? priorTokens.render : cacheVersion
```

**6-tuple destructure:**
```typescript
const [territoriesQ, baroniesQ, condadoColorsQ, baronyColorsQ, metaQ, stageRasterUrl] =
  useCanvasArtifacts(projectId, projection, effectiveCacheVersion, stageView)
```

**Pitfall-6-compliant clearCache useEffect:**
```typescript
useEffect(() => {
  const stage = stageRef.current
  if (!stage) return
  if (!territoriesQ.data || !baroniesQ.data || !metaQ.data) return
  stage.getLayers().forEach((layer) => {
    layer.clearCache()
    layer.batchDraw()
  })
}, [effectiveCacheVersion, stageView])
```

**isStageOverlay layer-visibility gating (UI-SPEC §StageViewToggle):**
```typescript
const isStageOverlay = stageView !== 'render-final'

<BackgroundLayer src={stageRasterUrl} ... />   // always shows, uses stageRasterUrl
<TerritoryLayer visible={!isStageOverlay && layerVisibility.condados} ... />
<BaronyLayer visible={!isStageOverlay && layerVisibility.baronies} ... />
<DecorationsLayer layerVisibility={{
  capitals: !isStageOverlay && layerVisibility.capitals,
  labels: !isStageOverlay && layerVisibility.labels,
}} ... />
```

### clearCache Test Design

The 3 unit tests use `React.forwardRef` + `useImperativeHandle` to assign a fake Konva-like object (with `getLayers()` spy) to `stageRef.current`. This allows the production `getLayers().forEach(clearCache)` path to execute in jsdom without a real Konva canvas:

```typescript
const fakeStage = { getLayers: vi.fn(() => [fakeLayer]), ... }
vi.mock('react-konva', () => ({
  Stage: React.forwardRef((props, ref) => {
    React.useImperativeHandle(ref, () => fakeStage, [])
    return <div>{props.children}</div>
  }),
  ...
}))
```

| Test | Behavior Verified |
|------|------------------|
| `test_clearCache_called_on_token_change` | clearCache fires when cacheVersion changes |
| `test_clearCache_called_on_stage_view_change` | clearCache fires when stageView changes |
| `test_clearCache_NOT_called_when_token_unchanged` | No spurious clearCache on same deps |

## Test Results

- **3 new clearCache tests: all passing**
- **185 total tests passing, 5 skipped** (Wave 0 BaronyLabels stubs — owned by 04-05)
- **`tsc -b` exits 0** — TypeScript clean
- Pre-existing `act()` warning in `selection.test.tsx` is out of scope (pre-existing, not in modified files)

## Commits

| Hash | Message | Files |
|------|---------|-------|
| de2b401 | feat(04-04): useCanvasArtifacts re-key on stageView + expose stageRasterUrl as 6th return | useCanvasArtifacts.ts, CanvasViewer.resize.test.tsx |
| 2b14173 | feat(04-04): CanvasViewer clearCache discipline + stageView gating + priorToken swap | CanvasViewer.tsx, CanvasViewer.clearCache.test.tsx |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `findAll('Layer')` not in Konva TypeScript types**
- **Found during:** Task 2 TypeScript check (`tsc -b`)
- **Issue:** Plan specified `stage.findAll('Layer').forEach(...)` — `findAll` does not exist in `konva` TypeScript definitions (`Container.d.ts`, `Stage.d.ts`). TypeScript errors TS2339 + TS7006 blocked compilation.
- **Fix:** Used `stage.getLayers()` instead — the typed method on `Konva.Stage` returning `Layer[]` directly. Behavior is identical: iterates all layers in the stage in z-order.
- **Files modified:** `frontend/src/components/canvas/CanvasViewer.tsx`
- **Commit:** 2b14173

**2. [Rule 3 - Blocking] CanvasViewer.resize.test.tsx mock returned 5-tuple**
- **Found during:** Task 1 implementation (after extending return to 6-tuple)
- **Issue:** `CanvasViewer.resize.test.tsx` mocked `useCanvasArtifacts` returning a 5-tuple. CanvasViewer now destructures 6 elements — the 6th (`stageRasterUrl`) would be `undefined`, causing `BackgroundLayer src` to receive `undefined`.
- **Fix:** Added `stageRasterUrl` string as 6th element in the mock return. No behavior change in the test assertions.
- **Files modified:** `frontend/src/components/canvas/__tests__/CanvasViewer.resize.test.tsx`
- **Commit:** de2b401

## Known Stubs

None. All 3 clearCache tests are fully implemented. The `stageRasterUrl` and `isStageOverlay` logic is fully wired to real store state. No placeholder data in any rendering path.

## Threat Flags

None. This plan extends client-side hydration only — no new HTTP surfaces, no untrusted input parsing. The plan's threat register (T-04-04-01 priorTokens cancel race, T-04-04-02 clearCache thrash) are addressed by:
- T-04-04-01: `priorTokens.render` functional update via Zustand `revertStage` (owned by 04-03 Task 4)
- T-04-04-02: clearCache is O(layer-count = constant 5); debounced 250ms upstream by slider

## Note on useRenderStore Migration

Per plan checker B1 and 04-03 SUMMARY: the useRenderStore → useRunStore migration was completed in 04-03 Task 4. This plan only READS `useRunStore.priorTokens` — it does NOT modify `useRunStore.ts`. File ownership is exclusive vs 04-03 and 04-05.

## Self-Check: PASSED
