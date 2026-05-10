---
phase: "04"
plan: "05"
subsystem: frontend-canvas
tags: [wave-3, d-12, barony-labels, konva, tdd]
dependency_graph:
  requires:
    - "04-00 (BaronyLabels.test.tsx stub)"
  provides:
    - "frontend/src/components/canvas/BaronyLayer.tsx (Text labels)"
    - "frontend/src/components/canvas/__tests__/BaronyLabels.test.tsx (5 tests)"
  affects:
    - "CanvasViewer (consumes BaronyLayer — labels render when Baronies toggle ON)"
tech_stack:
  added: []
  patterns:
    - "Konva Text with approximate offsetX centering (char-count × 6px heuristic)"
    - "vertexCentroid: arithmetic mean of flat points[] pairs"
    - "truncate: slice(0, 11) + U+2026 ellipsis at LABEL_MAX_CHARS=12"
    - "TDD: RED commit then GREEN commit pattern"
key_files:
  created: []
  modified:
    - frontend/src/components/canvas/BaronyLayer.tsx
    - frontend/src/components/canvas/__tests__/BaronyLabels.test.tsx
    - frontend/src/components/canvas/__tests__/BaronyLayer.test.tsx
decisions:
  - "Vertex-average centroid (not area-weighted) is sufficient for D-12 — baronies are roughly convex and 1-2px off-center is invisible at 10px font size"
  - "Approximate text width (text.length × 6px) rather than post-mount Konva ref measurement — avoids useEffect/useRef complexity for a 10px decorative label"
  - "Two separate .map() calls (polygons then labels) inside one Layer — keeps Konva z-order correct (all labels above all polygons) without an extra Layer node"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-10"
  tasks_completed: 1
  files_created: 0
  files_modified: 3
---

# Phase 04 Plan 05: BaronyLayer Text Labels (D-12) Summary

**One-liner:** Surgical addition of Konva Text labels at barony polygon centroids — 10px white halo text, truncated at 12 chars, conditional on `visible` prop — closing D-12 with 5 passing tests.

## What Was Built

### Task 1: Add Konva Text labels to BaronyLayer (TDD)

**RED commit (`567dad2`):** Filled `BaronyLabels.test.tsx` with 5 real assertions:
1. Labels render (`data-testid="barony-label-{id}"`) when `visible=true`
2. No labels rendered when `visible=false`
3. Long name truncated to `'BaroniaDeNo…'` (11 chars + U+2026 = 12 visible)
4. Label `x`/`y` match arithmetic centroid of polygon points
5. `fontSize=10`, `fill=#FFFFFF`, `shadowBlur=1`, `shadowColor=black`, `listening=false`

Result: 4 tests failed, 1 passed (the hide test — no Text nodes present in Phase 03 code).

**GREEN commit (`21e05ac`):** Modified `BaronyLayer.tsx`:

| Addition | Detail |
|----------|--------|
| `import { Layer, Line, Text }` | Added Text to the react-konva import |
| `LABEL_MAX_CHARS = 12` | Constant for truncation boundary |
| `LABEL_FONT_SIZE = 10` | Constant for font size |
| `vertexCentroid(points)` | Arithmetic mean of all (x,y) pairs in flat array |
| `truncate(name)` | `slice(0, 11) + '…'` when `name.length > 12` |
| Second `.map()` with `visible &&` guard | Renders Text nodes only when visible=true |
| Text visual contract | `fill="#FFFFFF"`, `shadowColor="black"`, `shadowBlur={1}`, `shadowOpacity={1}`, `shadowOffset={{x:0,y:0}}`, `fontStyle="normal"`, `listening={false}` |

**Visual contract proof:**
- Font: `fontSize={10}` (`LABEL_FONT_SIZE = 10`)
- Fill: `fill="#FFFFFF"` (white)
- Halo: `shadowBlur={1}`, `shadowColor="black"`, `shadowOpacity={1}`, `shadowOffset={{x:0,y:0}}`
- Anchor: `offsetX={approxTextWidth/2}`, `offsetY={LABEL_FONT_SIZE/2}` (center-center)
- Non-interactive: `listening={false}` (clicks pass through to Line polygons below)
- Truncation: Unicode ellipsis `…` (U+2026), not three ASCII dots

**Existing click-to-select preserved:** The first `.map()` for Line polygons is unchanged. `handleClick` still fires `selectBarony(id)` and `cancelBubble`. Labels in the second `.map()` have `listening={false}` so they never intercept these events.

## Verification Results

- `npx vitest run BaronyLabels.test.tsx BaronyLayer.test.tsx`: **11/11 passed** (5 new + 6 existing)
- `npx vitest run` (full suite): **190/190 passed**, 0 skipped
- `npx tsc -b`: **exit 0** (clean)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Issue] Extended `BaronyLayer.test.tsx` mock with Text stub**
- **Found during:** GREEN phase, before running tests
- **Issue:** The existing `BaronyLayer.test.tsx` mocked only `Layer` and `Line` from `react-konva`. Once `BaronyLayer.tsx` imported `Text`, the mock returned `undefined` for `Text`, causing React to throw "Element type is invalid" on all 6 existing tests when `visible=true` (which triggers the new label render branch).
- **Fix:** Added a minimal `Text` stub to the `vi.mock('react-konva', ...)` factory that renders a `<div>` with `data-testid`, `data-text`, and `data-listening` attributes. Existing 6 tests assert nothing about Text, so the stub is sufficient to unblock them.
- **Files modified:** `frontend/src/components/canvas/__tests__/BaronyLayer.test.tsx`
- **Commit:** `21e05ac` (bundled with GREEN feat commit per TDD convention)

## Commits

| Hash | Message | Files |
|------|---------|-------|
| `567dad2` | `test(04-05): add failing tests for BaronyLabels D-12` | `BaronyLabels.test.tsx` |
| `21e05ac` | `feat(04-05): add Konva Text labels to BaronyLayer (D-12)` | `BaronyLayer.tsx`, `BaronyLayer.test.tsx` |

## Known Stubs

None. All tests are fully implemented and passing.

## Threat Flags

None. Pure rendering addition — no new HTTP endpoints, no untrusted input, no new auth surface.

## Self-Check: PASSED
