---
status: diagnosed
phase: 04-parameter-studio-live-re-render
source:
  - 04-00-SUMMARY.md
  - 04-01-SUMMARY.md
  - 04-02-SUMMARY.md
  - 04-03-SUMMARY.md
  - 04-04-SUMMARY.md
  - 04-05-SUMMARY.md
  - 04-06-SUMMARY.md (pending — Task 4 done, will be written when orchestrator resumes)
started: 2026-05-10T20:23:48Z
updated: 2026-05-11T09:45:13Z
---

## Current Test

[testing complete — 12/12 passed; 3 polish gaps captured for follow-up phase]

## Pre-flight (run once before testing)

```
# Terminal 1 — backend (port 8765)
cd C:\Users\veio_\Documents\Unity_Projects\MEDIEVAL-FORGE
medieval-forge start
# fallback: cd backend && uvicorn medieval_forge.main:app --reload --port 8765

# Terminal 2 — frontend (port 5173)
cd C:\Users\veio_\Documents\Unity_Projects\MEDIEVAL-FORGE\frontend
npm run dev
```

Or use the helper: `uat-04.bat` (seeds project + starts both servers + opens checklist + browser).

Open http://localhost:5173/projects. Open DevTools console (F12).

## Tests

### 1. Existing project loads with parameter studio shell
expected: Navigate to a generated project. ParameterSidebar appears on left at 320px width with heading "Parâmetros". Canvas fills remaining viewport.
result: pass

### 2. Stage view radios visible
expected: Top of ParameterSidebar shows 5 stage-view radios: "Mapa final" (selected by default), "Suavização", "Limpeza", "Voronoi bruto", "Máscara terrestre".
result: pass

### 3. Slider cards render
expected: 4 SliderCards visible below the radios: "Suavização (σ)", "Passes Mediana", "Fragmento mín. (px)", "Fusão de blobs (px)" — each with slider + numeric input + reset (↻) icon.
result: pass

### 4. Sigma drag triggers re-render
expected: Drag σ slider from 3.0 to 4.5. Canvas re-renders showing visibly different territory smoothing. Wall-clock ~17–30s on this machine — this is expected; D-19 500ms target deferred to Phase 05.
result: pass

### 5. Stage view: Suavização
expected: Click "Suavização" radio. Canvas swaps to colorized smooth-stage raster (per-territory blur output). Barony/condado labels are hidden. No flicker.
result: pass

### 6. Stage view restore
expected: Click "Mapa final" radio. Canvas restores to the final composite render. Labels re-appear if their layer toggles are on.
result: pass

### 7. Sidebar collapse toggle
expected: Click the Mixer icon in the WorkspaceToolbar (left zone). ParameterSidebar collapses to 0 width; canvas grows to fill space. Click again — sidebar restores.
result: pass

### 8. Barony name labels (D-12)
expected: Toggle Baronies layer on (LayerTogglePanel). Each barony shows its name as 10px white text with thin black halo (shadowBlur=1) at the polygon centroid. Long names truncated at 12 chars with `…`.
result: pass

### 9. Cancel reverts slider + canvas (D-13/D-16)
expected: Drag a slider; while render in progress, click "Cancelar" in the toolbar. Slider snaps back to its prior value. Canvas restores to prior render without flicker. Cancel completes <500ms (D-14 cooperative cancel).
result: pass

### 10. Reset slider via icon
expected: Click the reset (↻) icon on a single SliderCard. That slider snaps to its default value. Canvas re-renders if the value changed.
result: pass

### 11. SC-3 pixel diff visible
expected: σ 3.0→4.5 produces visibly different pixels in the rendered map (territory edges differ). Functional contract — even though wall-clock is 17–30s, the change must be observable.
result: pass

### 12. Console error audit
expected: No console errors throughout Tests 1–11. Warnings about React DevTools or Vite HMR are acceptable. Any other warning/error → record in this test result.
result: pass

## Summary

total: 12
passed: 12
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

# Polish improvements surfaced during UAT. All 12 functional tests passed,
# but the user reported three follow-up observations that warrant a
# decimal phase (04.1) rather than blocking Phase 04 closure.
# All three are post-completion improvements, not test failures.

- truth: "Map canvas keeps current zoom/pan when slider triggers a re-render"
  status: failed
  reason: "User reported: zoom resets every time I edit a parameter — annoying when comparing details after a small slider change"
  severity: major
  test: 4
  root_cause: "CanvasViewer.tsx line 206-208 — useEffect re-runs fitToView() whenever the `projection` reference changes. Slider /render → metadata refetch → projection re-derived (same bounds, new reference) → effect fires → zoom resets. Pre-Phase 04 this never triggered because canvas did not rehydrate on parameter changes."
  artifacts:
    - path: "frontend/src/components/canvas/CanvasViewer.tsx"
      issue: "fitToView re-runs on every projection reference change (lines 206-208)"
  missing:
    - "Stable projection key comparison (e.g., `${mapW}x${mapH}:${lon_min},${lon_max}`) tracked via useRef so fitToView only runs when bounds actually change"
    - "Vitest coverage: zoom level persists across simulated /render hydration cycles"
  debug_session: ""

- truth: "User can preview the previous render alongside the new one to judge slider impact"
  status: failed
  reason: "User reported: deveria ter uma maneira de previsualizar se quiser o antes e o depois de uma modificação"
  severity: minor
  test: 4
  root_cause: "Feature gap — no before/after preview affordance exists. Current UX applies slider changes immediately with no comparison handle. useRunStore already retains a `priorToken` for cancel/D-13 purposes, so the raster for the previous state is available — just not surfaced in the UI."
  artifacts:
    - path: "frontend/src/components/canvas/CanvasViewer.tsx"
      issue: "no preview-previous affordance"
    - path: "frontend/src/stores/useRunStore.ts"
      issue: "priorToken already tracked but unused for comparison"
  missing:
    - "Toggle/hold gesture (suggested: hold spacebar OR press-and-hold a sidebar button) that swaps canvas raster to priorToken artifact while held"
    - "Alternative considered: split-view (2 stages side-by-side) or diff highlight overlay — heavier, choose during planning"
    - "Vitest coverage: hold gesture triggers priorToken raster swap; release restores current"
  debug_session: ""

- truth: "User can verify that a barony's size/extent matches the historical 868 AD dataset"
  status: failed
  reason: "User reported: notei baronias muito grandes e nao sei se elas sao realente assim como posso ter certeza? é pela idade? como a pesquisa eh feita?"
  severity: minor
  test: 8
  root_cause: "Discoverability gap — the canonical territory data lives in `inicio/territory_data_v3.py` (91 condados, ~250 baronias for Iberia 868 AD, coordinates are historical centroids not modern cities). The huge baronies in frontier/Andalusia regions are accurate to the dataset (sparse points → large Voronoi cells), but the user has no in-app way to (a) inspect a barony's source data, (b) compare against the historical period, or (c) understand the Voronoi-from-centroids mechanic. The data file itself is not surfaced in any UI affordance."
  artifacts:
    - path: "inicio/territory_data_v3.py"
      issue: "canonical data lives outside the app — no UI surface for verification"
  missing:
    - "Click-on-barony info panel showing: name, parent condado, parent duchy, source coordinate (lon/lat), source file reference"
    - "README / in-app help text explaining the Voronoi-from-centroids mechanic (sparse → large cells is by design)"
    - "Optional: link to canonical hierarchy doc per region (HIERARQUIA_868AD_V3.md exists outside repo — surface it or document the absence)"
  debug_session: ""
