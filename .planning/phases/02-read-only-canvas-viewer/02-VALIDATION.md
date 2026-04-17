---
phase: 2
slug: read-only-canvas-viewer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-17
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `02-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest (unit/integration) + Playwright (E2E/visual smoke). Install in Wave 0 if absent. |
| **Config file** | `frontend/vite.config.ts` (existing) + `frontend/vitest.config.ts` (Wave 0) + `frontend/playwright.config.ts` (Wave 0 if Playwright absent) |
| **Quick run command** | `cd frontend && npm run test -- --run` |
| **Full suite command** | `cd frontend && npm run test -- --run && npm run test:e2e` |
| **Estimated runtime** | ~10–15 s unit + ~30 s E2E |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npm run test -- --run`
- **After every plan wave:** Run `cd frontend && npm run test -- --run && npm run test:e2e`
- **Before `/gsd-verify-work`:** Full suite must be green; Playwright Tailwind+Radix visual smoke must pass.
- **Max feedback latency:** ≤15 s for per-task sampling.

---

## Per-Task Verification Map

> Populated by the planner. Each row maps a task (`{phase}-{plan}-{task}`) to its requirement, test type, and automated command. The list below is the research-derived seed set; the planner must add one row per task and set `File Exists` to ❌ W0 when the test file is a Wave-0 dependency.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD-2.1-W0 | 2.1 | 0 | infra | — | N/A | setup | `cd frontend && npm i -D vitest @testing-library/react @testing-library/jest-dom jsdom @playwright/test && npx playwright install chromium` | ❌ W0 | ⬜ pending |
| TBD-2.1-projection | 2.1 | 1 | CANVAS-01 | — | N/A | unit | `npm run test -- projection.test.ts -- --run` | ❌ W0 | ⬜ pending |
| TBD-2.1-stage-scaffold | 2.1 | 1 | CANVAS-01 | — | N/A | integration | `npm run test -- CanvasViewer.test.tsx -- --run` | ❌ W0 | ⬜ pending |
| TBD-2.2-territory-layer | 2.2 | 2 | CANVAS-01 | — | N/A | integration | `npm run test -- TerritoryLayer.test.tsx -- --run` | ❌ W0 | ⬜ pending |
| TBD-2.2-layer-panel | 2.2 | 2 | CANVAS-04 | — | N/A | integration | `npm run test -- LayerTogglePanel.test.tsx -- --run` | ❌ W0 | ⬜ pending |
| TBD-2.2-radix-smoke | 2.2 | 0 | CANVAS-04 (visual) | — | V14 config | Playwright visual | `npm run test:e2e -- smoke-tailwind-radix.spec.ts` | ❌ W0 | ⬜ pending |
| TBD-2.3-zoom-pan | 2.3 | 3 | CANVAS-02 | — | N/A | unit | `npm run test -- useZoomPan.test.ts -- --run` | ❌ W0 | ⬜ pending |
| TBD-2.3-selection | 2.3 | 3 | CANVAS-03 | — | N/A | integration | `npm run test -- selection.test.tsx -- --run` | ❌ W0 | ⬜ pending |
| TBD-2.3-inspector | 2.3 | 3 | CANVAS-03 | — | N/A | integration | `npm run test -- InspectorSidebar.test.tsx -- --run` | ❌ W0 | ⬜ pending |
| TBD-2.3-labels | 2.3 | 3 | CANVAS-05 | — | N/A | unit | `npm run test -- DecorationsLayer.test.tsx -- --run` | ❌ W0 | ⬜ pending |
| TBD-2.3-fit-to-view | 2.3 | 3 | CANVAS-06 | — | N/A | integration | `npm run test -- FitToViewButton.test.tsx -- --run` | ❌ W0 | ⬜ pending |
| TBD-2.3-perf-probe | 2.3 | 3 | (non-req A5) | — | N/A | Playwright perf | `npm run test:e2e -- perf-panzoom.spec.ts` | ❌ W0 | ⬜ pending |
| TBD-backend-geojson | 2.1 | 1 | CANVAS-01 (data dep) | — | V5 input validation | unit (pytest) | `cd backend && pytest tests/test_territories_geojson.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/vitest.config.ts` — jsdom env + tsconfig paths
- [ ] `frontend/playwright.config.ts` — chromium only (install if absent)
- [ ] `frontend/src/lib/projection.test.ts` — projection round-trip + vertex preservation stubs
- [ ] `frontend/src/hooks/useZoomPan.test.ts` — wheel/pan stubs
- [ ] `frontend/src/hooks/useKeyboardShortcuts.test.ts` — Esc + Ctrl+0 + input-focus guard stubs
- [ ] `frontend/src/stores/uiStore.test.ts` — selection + layer toggle stubs
- [ ] `frontend/src/components/canvas/__tests__/TerritoryLayer.test.tsx` — RTL + react-konva test util
- [ ] `frontend/src/components/canvas/__tests__/InspectorSidebar.test.tsx`
- [ ] `frontend/src/components/canvas/__tests__/LayerTogglePanel.test.tsx`
- [ ] `frontend/e2e/smoke-tailwind-radix.spec.ts` — Pitfall 2 transparency smoke
- [ ] `frontend/e2e/perf-panzoom.spec.ts` — A5 frame-rate probe
- [ ] Frameworks install: `npm i -D vitest @testing-library/react @testing-library/jest-dom jsdom @playwright/test` + `npx playwright install chromium`
- [ ] Backend: `backend/tests/test_territories_geojson.py` — asserts generator emits `territories.geojson` with per-feature `id`, `properties.neighbors`, valid GeoJSON `Polygon`/`MultiPolygon` geometry

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Pixel-parity of Konva territory fill vs `terrain.png` background at 1× | CANVAS-01 | Automated pixel-diff is fragile across GPUs; a visual side-by-side is the most reliable gate | 1. Open Iberia project in app; 2. Disable Terrain layer, enable Territories layer; 3. Compare condado colors against `lookup_condado_colors.json` hex values for 5 sample territories; 4. Re-enable Terrain and verify polygon edges coincide with PNG boundaries at 1× zoom. |
| Selection UX flow end-to-end | CANVAS-03 | User-journey validation covers click + inspector fill + neighbor chip + Esc sequence | 1. Click condado; 2. verify gold border appears; 3. verify inspector shows 4 property groups; 4. click a neighbor chip; 5. verify selection moved and inspector updated; 6. press Esc; 7. verify selection clears and inspector shows project summary. |
| Label readability at threshold | CANVAS-05 | Visual legibility is subjective; derive the exact threshold value during UAT on Iberia | Pan/zoom around Iberia; confirm labels appear only after crossing ~1.5× scale; confirm labels are readable (not overlapping polygon edges catastrophically) for 10+ sampled condados. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references above
- [ ] No watch-mode flags in any command
- [ ] Feedback latency < 15 s per-task, < 45 s per-wave
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
