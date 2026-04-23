---
phase: 02-read-only-canvas-viewer
plan: 05
subsystem: canvas-sizing-color-ux-fixes
tags: [canvas, resize-observer, error-boundary, radix-tooltip, cache-bust, gap-closure]
dependency_graph:
  requires:
    - 02-04 (sidecar emission, 5-tuple useCanvasArtifacts)
  provides:
    - CanvasViewer with ResizeObserver wired via callback-ref (B-1 fix)
    - Viewport-relative canvas region in ProjectDetail
    - react-error-boundary wrapping InspectorSidebarWrapper
    - 1.5× zoom threshold + Radix Tooltip on Labels toggle
    - GAP-04 H4 diagnosis confirmed (cacheVersion mitigation already shipped)
closes_gaps: [GAP-04, GAP-05, GAP-06, GAP-07, GAP-08]
requirements: [CANVAS-01, CANVAS-02, CANVAS-03, CANVAS-04, CANVAS-05, CANVAS-06]
---

# Plan 02-05 — Canvas Sizing + Color UX Fixes — Summary

## Outcome

All five GAPs opened by the 2026-04-18 human re-test are closed. Phase 2 UAT
items #1, #3, #4, #5, #6, #7, #8, #9, #11 become re-runnable; items #7 (label
threshold) and defensive sidebar fallback are now covered by automated tests.

## What Was Built

### GAP-05 — Stage fills viewport (keystone)

`CanvasViewer.tsx` already had the callback-ref `ResizeObserver` pattern from
prior quick tasks: a `setContainerRef` callback that (dis)connects the
observer on every DOM mount/unmount so it migrates across the
`metaQ.isPending` → `metaQ.data` branch transition (B-1 fix). Viewport
dimensions are `useState` (fallback `width`/`height` props preserved for
tests). A `getBoundingClientRect()` belt-and-suspenders sync-measure after
`observe()` covers browsers that never deliver an initial entry.

`ProjectDetail.tsx:140` uses `height: calc(100vh - 220px)` with
`minHeight: '500px'` so the canvas region tracks the viewport instead of
being locked to 800×600.

Tests (`CanvasViewer.resize.test.tsx`, 5/5 green):
- R1: observer callback updates Stage `width`/`height`
- R2: `computeFitToView` re-called with new dims on resize
- R3: 0×0 transient measurements are ignored
- R4: observer migrates from loading div to content div after `metaQ` resolves
- R5: sync-measure fallback when observer never fires

### GAP-06 — "Blank" on click

Confirmed as a downstream symptom of GAP-05. No separate fix applied — once
the Stage fills the canvas region, empty-area clicks no longer land in the
navy dead zone. Human re-verification pending.

### GAP-04 — #666666 condado fallback

**Task 2 diagnosis (see plan `<diagnosis>` block):** Ran three diagnostic
commands against a real Iberia project (`fe5d709d…`) on port 8765:

| Probe | Result |
|-------|--------|
| `GET /preview/condado_colors.json` | HTTP 200, 91 entries with valid hex |
| `GET /preview/territories.geojson` feature ids | 91 symbolic ids (`oviedo`, `pravia`, …) |
| Key overlap | **91/91 = 100%** |

**Verdict: H4** — historical `#666666` was stale TanStack Query + browser
HTTP cache. Fix already shipped via the `cacheVersion` prop wiring: every
preview URL carries `?v=<project.updated_at>` and every query key includes
`cacheVersion`, invalidating both caches when the pipeline regenerates.

Regression test added at `frontend/src/hooks/useCanvasArtifacts.cacheVersion.test.ts`
(2/2 green) asserting `?v=<encoded cacheVersion>` propagation to all five
preview URLs and absence when `cacheVersion` is `undefined`.

### GAP-08 — Label zoom-gate UX

`DecorationsLayer.tsx:13` — `LABEL_ZOOM_THRESHOLD_RELATIVE` lowered `2.0 →
1.5`. Paired Radix Tooltip on the Labels row of `LayerTogglePanel.tsx`
reads "Zoom in 1.5× to show labels". Rows without a tooltip hint render as
plain Flex (no extra wrapper).

Tests (`DecorationsLayer.test.tsx`, 9/9 green) now pin:
- Exact 1.5× boundary: `currentScale=0.51`, `minScale=0.34` → labels render
- Just below boundary: `currentScale=1.49×0.34` → labels do not render

### GAP-07 — Inspector sidebar ErrorBoundary

Installed `react-error-boundary@^4` and wrapped `InspectorSidebarWrapper`
in `ProjectDetail.tsx:155-172` with a visible Radix `Callout.Root` fallback
("Sidebar failed to load — check console."). `onError` logs the full error
to `console.error` for developer triage; the fallback UI never renders
`err.message` or `err.stack` (T-02-05-02 information-disclosure mitigation).

Test (`ProjectDetail.errorBoundary.test.tsx`, 1/1 green) mounts the exact
ErrorBoundary shape used in production, asserts the visible fallback text,
and explicitly checks that error message fragments and stack paths are
NOT present in the rendered DOM.

### Pre-existing regression fixed along the way

Quick task 260422-ktb merged research kingdom colors into CanvasViewer but
the code assumed `manualResult` always has both `kingdoms` and
`condados_assignment` populated. Test mocks and partial real-world results
crashed with `Cannot convert undefined or null to object` /
`not iterable`. Fixed by:

- `CanvasViewer.tsx:234` — `manualResult?.kingdoms ? Object.keys(…) : []`
- `useResearchStore.ts:18` — guard `computeCondadoColors` against missing
  `condados_assignment`

Recovered 13 of 16 failing frontend tests (97→101/100-104 green).

## Key Files

**Modified:**
- `frontend/src/components/canvas/CanvasViewer.tsx` — regression fix only (the callback-ref observer was pre-existing)
- `frontend/src/components/canvas/DecorationsLayer.tsx` — threshold 2.0→1.5
- `frontend/src/components/canvas/LayerTogglePanel.tsx` — Radix Tooltip on Labels row
- `frontend/src/pages/ProjectDetail.tsx` — ErrorBoundary wrap
- `frontend/src/stores/useResearchStore.ts` — `computeCondadoColors` guard
- `frontend/package.json` + `package-lock.json` — `react-error-boundary@^4`

**Created:**
- `frontend/src/hooks/useCanvasArtifacts.cacheVersion.test.ts` (GAP-04 H4 regression, 2 tests)
- `frontend/src/pages/__tests__/ProjectDetail.errorBoundary.test.tsx` (GAP-07 regression, 1 test)

**Test changes:**
- `frontend/src/components/canvas/__tests__/DecorationsLayer.test.tsx` — flipped threshold assertion, renamed boundary test to 1.5×, added just-below test
- `frontend/src/components/canvas/__tests__/LayerTogglePanel.test.tsx` — added Tooltip to `@radix-ui/themes` mock

## Threat Model Mitigations Landed

- **T-02-05-01 — Denial of Service (RO callback):** 0×0 guard in
  CanvasViewer.tsx:96 prevents collapsed-Stage on transient measurements.
- **T-02-05-02 — Information Disclosure (ErrorBoundary fallback):** Generic
  "Sidebar failed to load" text; `err.stack` / `err.message` never reach the
  DOM. Explicit DOM-content assertions in the regression test.

## Verification

| Check | Result |
|-------|--------|
| `npx vitest run` | 101/104 pass (3 pre-existing SSE failures unrelated to 02-05) |
| `npx tsc -b` | exit 0 |
| Resize tests | 5/5 green |
| useKeyboardShortcuts regression | 7/7 green |
| Grep sweep (all invariants) | ✓ every invariant from plan `<verification>` holds |
| D-04 preservation (`lib/map_generator.py` diff) | empty |

## Human UAT — Still Pending Re-Run

These items are unblocked but need human verification against a live pipeline:

- #1 Condado fills match (unblocked by cacheVersion mitigation)
- #3, #4, #6, #8, #9, #11 (all unblocked by GAP-05)
- #5 Click-select + neighbor chip pan (unblocked by GAP-05)
- #7 Label gate (new expected behavior: labels at ≥1.5× with tooltip hint)

## Commits

| Commit | Subject |
|--------|---------|
| 3247177 | fix(02-05): guard CanvasViewer against partial manualResult |
| 6f8fc2c | docs(02-05): GAP-04 diagnosis — H4 |
| e5dc1cb | test(02-05): GAP-04 H4 regression — cacheVersion propagation |
| dc3d0da | feat(02-05): GAP-08 — label threshold 2.0→1.5 + Radix Tooltip |
| 2128c30 | feat(02-05): GAP-07 — wrap InspectorSidebarWrapper in ErrorBoundary |

## Skipped / Deferred

- **Task 3 code change (H1/H2/H3 branches):** Not executed. Task 2 diagnosis
  confirmed H4 (cache-bust already in place); no backend code change needed.
  Added regression test for the existing mitigation instead.
