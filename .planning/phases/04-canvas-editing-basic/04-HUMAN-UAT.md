---
status: diagnosed
phase: 04-canvas-editing-basic
source: [04-VERIFICATION.md]
started: 2026-04-24T15:45:00Z
updated: 2026-04-25T00:45:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Capital drag re-renders in under 500ms (auto/per_op mode)
expected: Dragging a capital marker causes the affected neighbor Voronoi polygons to visually update on the Konva canvas within 500ms — no page reload required
result: issue
reported: "Eu arrasto o ponto fica um buraco e nada acontece"
severity: major

### 2. Vertex drag immediately reflected on canvas (auto/per_op mode)
expected: Dragging a border vertex reshapes the polygon outline on canvas without reload
result: issue
reported: "Não consigo arrastar nada"
severity: major

### 3. Merge result immediately visible (auto/per_op mode)
expected: After clicking Fundir on 2+ selected territories, a single merged polygon replaces the selected set on canvas without reload
result: issue
reported: "Não consigo selecionar mais do que um territorio, tentei usar shift nao funcionou, teteni arrastar com o mouse tbm nao, botão de merge nao existe"
severity: major

### 4. Ctrl+Z undoes capital drag as single compound step (visual)
expected: Pressing Ctrl+Z after a capital drag restores both the capital marker position and all affected neighbor polygon shapes in one step — no partial revert
result: issue
reported: "Ctrl+z nao funciona."
severity: major

### 5. Ctrl+S in explicit save mode flushes and visually updates canvas (no reload)
expected: Pressing Ctrl+S with unsaved edits in explicit mode flips SaveStatusIndicator to 'Salvo' AND the canvas re-renders with post-edit geometry within 500ms
result: issue
reported: "Tbm não funciona. Alias tou a testar tudo clicando em Editar para se fazer alterações."
severity: major
context: "Usuário está entrando em modo de edição clicando no botão Editar, mas nenhuma interação de edição funciona (drag capital, drag vertex, multi-select, Ctrl+Z, Ctrl+S)."

## Summary

total: 5
passed: 0
issues: 5
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "Dragging a capital marker causes the affected neighbor Voronoi polygons to visually update on the Konva canvas within 500ms — no page reload required"
  status: failed
  reason: "User reported: Eu arrasto o ponto fica um buraco e nada acontece — the capital marker leaves a hole where it was and nothing happens to the Voronoi polygons. User is clicking 'Editar' button to enter edit mode."
  severity: major
  test: 1
  artifacts: []
  missing: []

- truth: "Dragging a border vertex reshapes the polygon outline on canvas without reload"
  status: failed
  reason: "User reported: Não consigo arrastar nada — cannot drag any vertex even after clicking Editar to enter edit mode."
  severity: major
  test: 2
  artifacts: []
  missing: []

- truth: "After clicking Fundir on 2+ selected territories, a single merged polygon replaces the selected set on canvas without reload"
  status: failed
  reason: "User reported: Não consigo selecionar mais do que um territorio — shift-click doesn't add to selection, drag-to-box-select doesn't work, and the Fundir (merge) button is not visible/present in the UI."
  severity: major
  test: 3
  artifacts: []
  missing: ["multi-select affordance", "Fundir button in toolbar"]

- truth: "Pressing Ctrl+Z after a capital drag restores both the capital marker position and all affected neighbor polygon shapes in one step — no partial revert"
  status: failed
  reason: "User reported: Ctrl+z nao funciona — keyboard shortcut not firing undo."
  severity: major
  test: 4
  artifacts: []
  missing: []

- truth: "Pressing Ctrl+S with unsaved edits in explicit mode flips SaveStatusIndicator to 'Salvo' AND the canvas re-renders with post-edit geometry within 500ms"
  status: failed
  reason: "User reported: Tbm não funciona — Ctrl+S keyboard shortcut not working either."
  severity: major
  test: 5
  artifacts: []
  missing: []

## Cross-cutting observation

User entered edit mode by clicking the "Editar" button but NO edit interaction worked — capital drag, vertex drag, multi-select, Ctrl+Z, Ctrl+S all failed. This pattern strongly suggests a single systemic root cause (e.g., edit-mode state not actually activating downstream handlers, pointer-events disabled, Konva draggable prop not wired to mode, or keyboard listeners scoped wrong) rather than 5 independent bugs.

## Root Cause (diagnosed 2026-04-25, confidence: HIGH)

**`useProjectStore.hydrate(projectId, territories, capitals)` is never invoked in production code** — defined in `frontend/src/stores/useProjectStore.ts:24,47` with zero call sites outside tests. The edit-side geometry store stays at initial empty values (`territories: {}`, `capitals: {}`, `projectId: null`) for the entire session.

### Evidence

- `useProjectStore.ts:44` — initial state `projectId: null, territories: {}, capitals: {}`.
- Global grep for `hydrate` in `frontend/src` finds the method definition and a comment in `CanvasViewer.tsx:177` ("may differ from the projectId prop until hydrate() is called") — but no component/hook/page ever calls it. `ProjectDetail.tsx` mounts `CanvasViewer` without hydrating.
- `SelectionFloatingToolbar.tsx:83` — `if (!projectId) return` short-circuits the Fundir (merge) button before the API call.
- `VertexHandlesLayer.tsx:42,65` — early-returns unless `projectId && vertexEditId`; later reads `territories[vertexEditId]` which is always `undefined` → no handles render → nothing to drag.
- `CanvasViewer.tsx:354,382,422` — rollback/validation/vertex-commit all read from empty store; commit block never issues the PATCH for geometry.
- `useUndoShortcut.ts:49` and `persistence.ts:94` — both read `projectId` from the empty store → cache-invalidation skipped, Ctrl+S has no snapshot to POST.

### Why all 5 symptoms follow

- **Capital drag (T1)**: POST uses prop `projectId` so backend call succeeds, but `applyBatchUpdate` mutates an empty store, and rollback path `capitals[condadoId]` yields `undefined`. Canvas only re-renders via `invalidateCanvasArtifacts()` — which itself reads store state.
- **Vertex drag (T2)**: `VertexHandlesLayer` requires store `projectId` (is `null`) → handles never render.
- **Merge (T3)**: Rubber-band selection works, but `handleMerge` guards on `if (!projectId) return`. (Shift-click multi-select is a **separately missing feature** — out of scope for this fix.)
- **Ctrl+Z (T4)**: `temporal.undo()` fires on an empty history (mutations never landed in the store because compound transactions wrap mutations that never hydrated).
- **Ctrl+S (T5)**: `manualSave()` destructures `{ projectId, territories, capitals }` from the empty store → no snapshot to POST.

### Why unit tests passed

Every automated test calls `useProjectStore.getState().applyBatchUpdate(...)` or seeds the store imperatively (e.g., `CapitalDrag.test.tsx:201,250`), bypassing the missing `hydrate` wiring. Classic blind spot of imperative test setup.

### Fix scope

- **Primary fix**: add a `useEffect` in `CanvasViewer.tsx` (or `ProjectDetail.tsx`) that calls `useProjectStore.getState().hydrate(projectId, territoriesAsRecord, capitalsAsRecord)` once both `territoriesQ` and `metaQ` resolve. Re-hydrate when `projectId` or `cacheVersion` changes.
- **Data adapter**: transform `territoriesQ.data` (array of `TerritoryRender`) → `Record<id, GeoJSONPolygon|MultiPolygon>`; transform `metaQ.data.condados` → `Record<id, [lon, lat]>`. See shape types in `frontend/src/hooks/useCanvasArtifacts.ts`.
- **Secondary** (separate gap, not caused by hydration bug): shift-click multi-select affordance in the territory click handler — this is a genuinely missing feature, promised by SC3 but only rubber-band was implemented.

**Estimated fix size**: ~15–30 lines for hydration wiring + adapter; shift-click is a separate ~10-line feature addition.

**Files that will change**: `frontend/src/components/canvas/CanvasViewer.tsx`, possibly `frontend/src/pages/ProjectDetail.tsx`, and a click-handler file for shift-click (e.g., `TerritoryLayer` or `SelectionManager`).

**Regression risk**: low for the hydration fix (adds wiring that everything already expects); medium for shift-click (new interaction path, must not break rubber-band).
