---
phase: 04-canvas-editing-basic
plan: 11
status: complete
completed: 2026-04-25
---

# 04-11 Summary — Wire useProjectStore.hydrate()

## What was implemented

Added a `useEffect` in `CanvasViewer.tsx` that calls `useProjectStore.getState().hydrate()` once `metaQ.data` resolves, closing the root cause of all 5 UAT failures (T1–T5): the `hydrate()` action existed in the store but had zero production call sites.

## Hydration adapter approach used

**Option B — direct `fetch()` call inside the effect** (per checker WARNING 3).

`territoriesQ.data` returned by `useCanvasArtifacts` is post-`select` (Konva projection-transformed points, not reversible to lon/lat). Rather than relying on TanStack's internal pre-`select` cache key (which is an implementation detail that could silently return `undefined`), the effect fetches `/api/projects/:id/territories.geojson[?v=cacheVersion]` directly and parses the raw FeatureCollection. A try/catch wraps the fetch so that test environments without a base URL don't produce unhandled rejections.

## History safety (checker BLOCKER 1)

The hydrate call is wrapped in:
```
temporal.getState().pause()
→ hydrate()
→ temporal.getState().clear()
→ temporal.setState({ isTracking: true })
```
This avoids the patched `resume()` (which flushes one undo entry — intended for user edits via `beginTransaction`/`endTransaction`). After hydration, `pastStates.length === 0` confirmed by Test 5.

## Auto-save race guard (checker BLOCKER 2)

A `hydratedKeyRef = useRef<string | null>(null)` tracks the last hydrated `"${projectId}|${cacheVersion}"` key. The effect early-exits when the key matches, so post-auto-save query invalidation (which changes `territoriesQ.data` reference but not `projectId` or `cacheVersion`) cannot re-run the effect and overwrite in-memory edits. Confirmed by Test 7.

## Test setup surprises

- The test environment (Node.js/jsdom) rejects relative URLs in `fetch()` with `TypeError: Failed to parse URL` rather than returning a non-ok Response. The initial implementation only guarded `if (!resp.ok) return`, causing an unhandled rejection that broke `CanvasViewer.resize.test.tsx`. Fixed by wrapping the `fetch()` call in a try/catch.
- The hydrate test file mocks `useCanvasArtifacts` via mutable module-level variables (`currentTerritories`, `currentMeta`) that tests can swap before each render — mirrors the pattern in `CanvasViewer.resize.test.tsx`.

## Test results

All 7 new integration tests pass:

| Test | Status |
|------|--------|
| T1: hydrates on mount once queries resolve | ✓ |
| T2: project switch replaces territories (with absence checks) | ✓ |
| T3: cacheVersion change re-hydrates | ✓ |
| T4: metaQ pending → no hydrate | ✓ |
| T5 (BLOCKER 1): hydrate pushes no undo entry | ✓ |
| T6 (BLOCKER 1): user edit → undo restores edit, not hydration | ✓ |
| T7 (BLOCKER 2): auto-save invalidation does not re-hydrate | ✓ |

Full suite: 151/154 tests pass. The 3 pre-existing failures are in `useResearchStream.test.ts` and `ResearchDialog.test.tsx` (research module, unrelated to this plan).

## UAT status after this plan

- **T1 (capital drag)**: store now populated → Voronoi recalc targets correct geometry ✓
- **T2 (vertex handles)**: store populated → VertexHandlesLayer render gate passes ✓
- **T3 (Fundir button)**: SelectionFloatingToolbar `!projectId` guard now unblocked ✓ (partial — shift-click deferred to 04-12)
- **T4 (Ctrl+Z)**: undo history clean after hydrate; first user edit creates exactly one entry ✓
- **T5 (Ctrl+S)**: `manualSave` reads populated store → snapshot non-empty ✓

## Remaining gap

T3 shift-click affordance deferred to plan 04-12.
