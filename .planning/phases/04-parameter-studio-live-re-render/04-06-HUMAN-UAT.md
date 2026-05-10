---
status: partial
phase: 04-parameter-studio-live-re-render
source:
  - 04-00-SUMMARY.md
  - 04-01-SUMMARY.md
  - 04-02-SUMMARY.md
  - 04-03-SUMMARY.md
  - 04-04-SUMMARY.md
  - 04-05-SUMMARY.md
  - 04-06-SUMMARY.md (in progress — Task 4 awaiting these UAT results)
started: 2026-05-10T20:23:48Z
updated: 2026-05-10T20:23:48Z
---

## Current Test

[testing paused — 12 items outstanding, scheduled for 2026-05-11]

## Pre-flight (run once before testing)

```
# Terminal 1 — backend (port 8000)
cd C:\Users\veio_\Documents\Unity_Projects\MEDIEVAL-FORGE
medieval-forge start
# fallback: cd backend && uvicorn medieval_forge.main:app --reload --port 8000

# Terminal 2 — frontend (port 5173)
cd C:\Users\veio_\Documents\Unity_Projects\MEDIEVAL-FORGE\frontend
npm run dev
```

Open http://localhost:5173/projects in browser. Open DevTools console (F12) and keep it visible — Test 12 audits console for errors throughout.

For Tests 1–11 you need an existing generated project. If none exists, click **"Gerar Mapa"** on a fresh project first and wait for completion before starting Test 1.

## Tests

### 1. Existing project loads with parameter studio shell
expected: Navigate to a generated project. ParameterSidebar appears on left at 320px width with heading "Parâmetros". Canvas fills remaining viewport.
result: [pending]

### 2. Stage view radios visible
expected: Top of ParameterSidebar shows 5 stage-view radios: "Mapa final" (selected by default), "Suavização", "Limpeza", "Voronoi bruto", "Máscara terrestre".
result: [pending]

### 3. Slider cards render
expected: 4 SliderCards visible below the radios: "Suavização (σ)", "Passes Mediana", "Fragmento mín. (px)", "Fusão de blobs (px)". Each card shows slider + numeric input + reset (↻) icon.
result: [pending]

### 4. Sigma drag triggers re-render
expected: Drag σ slider from 3.0 to 4.5. Canvas re-renders showing visibly different territory smoothing. Wall-clock ~17–30s on this machine — this is expected; D-19 500ms target deferred to Phase 05.
result: [pending]

### 5. Stage view: Suavização
expected: Click "Suavização" radio. Canvas swaps to colorized smooth-stage raster (per-territory blur output). Barony/condado labels are hidden. No flicker.
result: [pending]

### 6. Stage view restore
expected: Click "Mapa final" radio. Canvas restores to the final composite render. Labels re-appear if their layer toggles are on.
result: [pending]

### 7. Sidebar collapse toggle
expected: Click the Mixer icon in the WorkspaceToolbar (left zone). ParameterSidebar collapses to 0 width; canvas grows to fill space. Click again — sidebar restores.
result: [pending]

### 8. Barony name labels (D-12)
expected: Toggle Baronies layer on (LayerTogglePanel). Each barony shows its name as 10px white text with thin black halo (shadowBlur=1) at the polygon centroid. Long names truncated at 12 chars with `…`.
result: [pending]

### 9. Cancel reverts slider + canvas (D-13/D-16)
expected: Drag a slider; while render in progress, click "Cancelar" in the toolbar. Slider snaps back to its prior value. Canvas restores to prior render without flicker. Cancel completes <500ms (D-14 cooperative cancel).
result: [pending]

### 10. Reset slider via icon
expected: Click the reset (↻) icon on a single SliderCard. That slider snaps to its default value. Canvas re-renders if the value changed.
result: [pending]

### 11. SC-3 pixel diff visible
expected: σ 3.0→4.5 produces visibly different pixels in the rendered map (territory edges differ). Functional contract — even though wall-clock is 17–30s, the change must be observable.
result: [pending]

### 12. Console error audit
expected: No console errors throughout Tests 1–11. Warnings about React DevTools or Vite HMR are acceptable. Any other warning/error → record in this test result.
result: [pending]

## Summary

total: 12
passed: 0
issues: 0
pending: 12
skipped: 0
blocked: 0

## Gaps
