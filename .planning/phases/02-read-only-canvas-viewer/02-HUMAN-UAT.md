---
status: complete
phase: 02-read-only-canvas-viewer
source: [02-VERIFICATION.md, human re-test 2026-04-18, human re-UAT 2026-04-23]
started: 2026-04-18T00:00:00Z
updated: 2026-04-23T17:30:00Z
fixes_landed_in: 02-05
fixes_landed_date: 2026-04-23
reverified_date: 2026-04-23
---

## Current Test

[testing complete — all 11 tests pass after re-UAT]

## Tests

### 1. Condado fills match lookup_condado_colors.json
expected: Open a generated Iberia project at /projects/:id. Every condado polygon renders with the exact hex color from `lookup_condado_colors.json` — pixel-parity with `terrain.png` (no color drift from the Unity palette).
result: pass
reverified: 2026-04-23 (human re-UAT; cacheVersion fix from 02-05 confirmed)

### 2. Barony overlay toggle
expected: Borders layer toggle flips barony overlay on/off. When ON, baronies render at 85% opacity with a subtle internal stroke (rgba(0,0,0,0.25), 0.5px). Baronies are NOT clickable (listening=false).
result: pass
reverified: 2026-04-23 (human re-UAT)

### 3. Drag-pan smoothness + edge clamp
expected: Click-and-drag the Stage pans the canvas. At edges, `dragBoundFunc` clamps so the map cannot be dragged beyond its bounds. Movement feels smooth (no stutter or snap-back).
result: pass
reverified: 2026-04-23 (human re-UAT)

### 4. Cursor-anchored wheel zoom + scale clamp
expected: Mouse wheel zooms in/out anchored to cursor position (not canvas center). Min scale = fit-to-view; max scale = 4× min. Wheel stops zooming at the clamps.
result: pass
reverified: 2026-04-23 (human re-UAT)

### 5. Click-select + neighbor chip pan-on-select
expected: Click any condado → gold selection outline appears. Click a neighbor chip in the InspectorSidebar → selection moves to that condado AND canvas pans to center the new selection.
result: pass
reverified: 2026-04-23 (human re-UAT; downstream of GAP-05 fix)

### 6. Esc + empty-Stage click deselect
expected: Pressing Esc clears the selection. Clicking empty Stage area also clears selection. InspectorSidebar returns to its empty/default state.
result: pass
reverified: 2026-04-23 (human re-UAT)
observation: User noted baronies are not selectable — confirmed by design (BaronyLayer listening=false in Phase 02; barony selection deferred to Phase 04/05 editing).

### 7. Label gate at 2× minScale threshold (now 1.5×)
expected: Labels layer ON + zoom below 1.5× minScale → no labels visible. Zoom ≥ 1.5× minScale → condado labels become visible with the D-04 dual-ring capital markers. Tooltip on Labels checkbox explains the gate.
result: pass
reverified: 2026-04-23 (human re-UAT; threshold 1.5 + tooltip from 02-05 confirmed)
follow_up: User reports labels are hard to read on dark territory fills (always-black text). New gap GAP-09 logged for dynamic contrast (luminance-based black/white text).

### 8. Fit-to-view button + Ctrl/Cmd+0 shortcut
expected: Clicking FitToViewButton OR pressing Ctrl+0 (Cmd+0 on Mac) resets the view: scale → minScale, position → centered with 5% padding.
result: pass
reverified: 2026-04-23 (human re-UAT after SPA-routing fix)
diagnostic: Initial UAT showed button absent; root cause was vite `base: './'` causing deep-link hard-refresh to fetch JS from `/projects/assets/...` (404 → SPA catchall → text/html → React never mounts). Fixed by switching to `base: '/'` (commit 082be0a). Verified via Playwright spec frontend/e2e/uat-fittoview.spec.ts.

### 9. D-06.3 capital sentinel end-to-end
expected: Select a condado with a defined `capital_name` → InspectorSidebar shows the capital name. Select a condado with empty/whitespace `capital_name` → InspectorSidebar shows the "No capital assigned" sentinel text.
result: pass
reverified: 2026-04-23 (human re-UAT)

### 10. G-02 error propagation through FastAPI status machine
expected: Trigger a deliberate emitter failure. Run generation. The FastAPI background task should set project status to `error_generating` with `last_error` populated.
result: pass
reverified: 2026-04-23 (covered by automated test backend/tests/test_generator_e2e.py::test_emitter_error_propagates_to_caller; manual reproduction skipped per user choice)

### 11. Stage canvas fills full viewport (NEW — discovered in re-test)
expected: The Konva Stage fills the entire central viewport between the left LayerTogglePanel and the right InspectorSidebar — no dead/empty area.
result: pass
reverified: 2026-04-23 (human re-UAT; ResizeObserver + calc(100vh-220px) fix from 02-05 confirmed)

## Summary

total: 11
passed: 11
issues: 0 (all four original failures fixed in 02-05; verified in re-UAT 2026-04-23)
pending: 0
skipped: 0
blocked: 0
new_gaps_discovered_during_re_uat: 2 (GAP-09 label contrast — minor; GAP-10 SPA deep-link refresh — already fixed)

## Gaps

### GAP-04 — TerritoryLayer renders #666666 (cores cinza)
severity: blocker
status: fix_landed_pending_reverify
truth: TerritoryLayer falls back to `#666666` for every condado; Unity palette colors from `condado_colors.json` are not applied.
evidence: User screenshots (Borders OFF → all gray); frontend code is correct end-to-end. Suspected backend defect: `condado_colors.json` not produced, returns empty, or has IDs that don't match `territory_metadata.json`.
affects: [CANVAS-01, CANVAS-04]
fix_hint: First, live-verify endpoint with `curl /api/projects/{id}/preview/condado_colors.json`. If empty or 404 → fix `emit_territories_from_disk` sidecar emission. If populated but mismatched → fix ID join logic. Add a backend integration assertion that `condado_colors.json` keys ⊆ `territory_metadata.json` condado IDs.
fix_landed: Task 2 diagnosis (2026-04-23) confirmed H4 — backend 100% correct (91/91 keys match). Historical #666666 was TanStack Query + HTTP cache staleness. Mitigation already shipped via `cacheVersion` prop. Regression test added at `frontend/src/hooks/useCanvasArtifacts.cacheVersion.test.ts`. Commits: 6f8fc2c (diagnosis), e5dc1cb (regression test).

### GAP-05 — Stage hardcoded to 800×600 (keystone bug)
severity: blocker
status: fix_landed_pending_reverify
truth: `CanvasViewer.tsx` accepts `width`/`height` props with defaults (800, 600); `ProjectDetail.tsx:136` mounts it without passing dimensions; no `ResizeObserver` measures the actual container. Stage stays 800×600 regardless of viewport.
evidence: `CanvasViewer.tsx:58` (defaults), `CanvasViewer.tsx:219-220` (uses props directly as `viewportW`/`viewportH`), `CanvasViewer.tsx:235-236` (Stage created with `width={viewportW}`), `ProjectDetail.tsx:136` (no dimension props passed).
affects: [CANVAS-02, CANVAS-03, CANVAS-04, CANVAS-05, CANVAS-06]
fix_hint: Wire a `ResizeObserver` (or `useResizeObserver` hook) in `CanvasViewer` to measure its parent container. Update `viewportW`/`viewportH` from measured values. Re-call `setMinScale` and re-fit when dimensions change. Add a `useZoomPan` test for "stage resize triggers minScale recompute".
fix_landed: Callback-ref ResizeObserver pattern (B-1 fix) in CanvasViewer.tsx + `calc(100vh - 220px)` viewport-relative canvas region in ProjectDetail.tsx. 5 resize tests green (R1/R2/R3/R4/R5). Shipped via prior quick tasks; validated in 02-05.

### GAP-06 — Click-select returns "blank" (likely consequence of GAP-05)
severity: blocker
status: fix_landed_pending_reverify
truth: User clicks a condado → InspectorSidebar shows project-overview/empty state instead of selected condado details.
evidence: `CanvasViewer.tsx:186-193` deselects on `e.target === e.target.getStage()`. Because Stage only fills left ~800px (GAP-05), clicks in the right half (dead area) match this condition and clear the selection.
affects: [CANVAS-03, CANVAS-05]
fix_hint: Fixing GAP-05 should resolve GAP-06 directly (clicks will land on actual polygons). Verify after GAP-05 fix.
fix_landed: Downstream of GAP-05. No separate fix; once Stage fills the canvas region, empty-area clicks no longer land in the dead navy zone. Pending human re-verification.

### GAP-07 — InspectorSidebar lacks ErrorBoundary (defensive)
severity: warning
status: fix_landed_pending_reverify
truth: `ProjectDetail.tsx:142` mounts `InspectorSidebarWrapper` without a `<Suspense>` or `<ErrorBoundary>`. If `metaQ`/`territoriesQ` throws or suspends, the entire sidebar can vanish silently — appearing "blank" to the user.
evidence: `ProjectDetail.tsx:142` (no boundary), TanStack Query queries can throw on network/parse errors.
affects: [CANVAS-03]
fix_hint: Wrap `InspectorSidebarWrapper` in a `<react-error-boundary>` `<ErrorBoundary>` with a visible fallback ("Sidebar failed to load — see console") so silent failures become visible.
fix_landed: react-error-boundary@^4 installed; InspectorSidebarWrapper wrapped in ErrorBoundary with visible Radix Callout fallback ("Sidebar failed to load — check console."). Full error goes to console.error only (T-02-05-02 no-leak). Regression test in ProjectDetail.errorBoundary.test.tsx. Commit: 2128c30.

### GAP-08 — Labels zoom-gate UX mismatch
severity: warning
status: fix_landed_pending_reverify
truth: Labels checkbox toggles state correctly, but `DecorationsLayer` only renders labels at `currentScale >= 2.0 * minScale`. At default zoom (= minScale), labels never appear even when toggle is ON. User perceives the toggle as broken.
evidence: `DecorationsLayer.tsx:13` (`LABEL_ZOOM_THRESHOLD_RELATIVE = 2.0`), `:78-80` (gate logic). Working as designed but UX is opaque.
affects: [CANVAS-04]
fix_hint: Two options: (a) add a tooltip on the Labels checkbox: "Zoom in 2× to show labels" (preserves current threshold); (b) lower threshold to `1.5` or `1.0` so labels appear closer to default zoom. Decision: UX preference — recommend (a) plus a slight reduction to 1.5× as a compromise.
fix_landed: Both (a) and (b) applied per recommendation — threshold lowered 2.0→1.5 in DecorationsLayer.tsx, Radix Tooltip "Zoom in 1.5× to show labels" added to Labels row in LayerTogglePanel.tsx. Boundary tests pin 1.5×0.34 (on) and 1.49×0.34 (off). Commit: dc3d0da.

### GAP-09 — Label text contrast against dark territory fills (NEW)
severity: minor (UX)
status: open
truth: Condado labels are rendered with a fixed dark text color. On territories with dark fill colors (e.g., dark blue/purple kingdoms from research palette), the text is illegible.
evidence: User report 2026-04-23 during Test 7 re-UAT. Reproducible by enabling Labels and zooming on any dark-filled condado.
affects: [CANVAS-04]
fix_hint: Compute relative luminance of the condado fill color and pick black or white text accordingly (WCAG-style). Implementation: helper in `frontend/src/lib/contrast.ts` returning `'#000' | '#fff'` from a hex; consume it in `DecorationsLayer.tsx` per-label. Optional: add a thin contrasting halo/stroke for additional readability across all backgrounds.

### GAP-10 — SPA deep-link refresh broke all JS loading (NEW, ALREADY FIXED)
severity: blocker
status: fixed
truth: Hard refresh on any deep route (e.g., `/projects/{id}`) caused the browser to fetch JS modules from the wrong path (`/projects/assets/...`), which fell through to the SPA catchall and returned `text/html`. Browsers refused to execute the module script with that MIME type → React never mounted, so on re-UAT the FitToView (and effectively the entire freshly-built bundle) appeared missing.
evidence: Surfaced during Test 8 ("FitToView button missing"). Diagnosed via `frontend/e2e/uat-fittoview.spec.ts` — Playwright captured the browser console error `Failed to load module script: Expected a JavaScript-or-Wasm module script but the server responded with a MIME type of "text/html"`. Confirmed by direct `curl /projects/assets/index-D7ly9i8C.js` returning `text/html` (the SPA index).
affects: All routes other than `/`. Tests #1–#7 passed only because the user reached the project view via client-side navigation from `/`; once they hard-refreshed for Test 8 the bug bit. Effectively masked the entire freshly-built bundle.
fix_landed: `frontend/vite.config.ts` switched from `base: './'` to `base: '/'` so the built `index.html` references absolute `/assets/*` paths that hit the StaticFiles mount regardless of the current route. Rebuilt; Playwright spec confirms FitToView present and visible. Commit: 082be0a.

## Cross-cutting note

GAP-05 (Stage sizing) is the keystone. Fixing it likely resolves GAP-06 directly and unblocks human re-verification of items #2, #3, #4, #6, #8, #9. Recommended fix order: GAP-05 → GAP-04 → GAP-08 → GAP-07.

GAP-10 (SPA deep-link refresh) was discovered during this re-UAT and is already fixed. It is the actual reason Test 8 failed initially; FitToView itself was always correct in the source.
