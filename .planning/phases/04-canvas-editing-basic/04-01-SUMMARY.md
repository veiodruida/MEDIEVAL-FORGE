---
phase: 04-canvas-editing-basic
plan: 01
subsystem: frontend-types, frontend-tests, backend-tests, frontend-deps
tags: [wave-0, red-tests, types, scaffold, toast, tdd]
dependency_graph:
  requires: []
  provides:
    - frontend/src/types/editing.ts (all Phase 4 TypeScript contracts)
    - frontend/src/stores/__tests__/useProjectStore.test.ts (RED)
    - frontend/src/stores/__tests__/useEditorStore.test.ts (RED)
    - frontend/src/hooks/__tests__/useUndoShortcut.test.ts (RED)
    - frontend/src/components/canvas/__tests__/CapitalDrag.test.tsx (RED)
    - backend/tests/services/test_voronoi.py (RED)
    - backend/tests/api/test_edit_api.py (RED)
    - Toast.Provider mounted in main.tsx
  affects:
    - P03 (imports useProjectStore, useEditorStore from stores/)
    - P03 (imports useUndoShortcut from hooks/)
    - P02..P08 (all import from frontend/src/types/editing.ts)
    - P04 (backend edit.py must satisfy test_edit_api.py contracts)
tech_stack:
  added:
    - "@radix-ui/react-toast ^1.2.15"
    - "@radix-ui/react-icons ^1.3.2"
  patterns:
    - "Toast.Provider wrapping entire app tree in main.tsx"
    - "Wave 0 RED test pattern: import fails at collection = valid RED signal"
key_files:
  created:
    - frontend/src/types/editing.ts
    - frontend/src/stores/__tests__/useProjectStore.test.ts
    - frontend/src/stores/__tests__/useEditorStore.test.ts
    - frontend/src/hooks/__tests__/useUndoShortcut.test.ts
    - frontend/src/components/canvas/__tests__/CapitalDrag.test.tsx
    - backend/tests/services/test_voronoi.py
    - backend/tests/api/test_edit_api.py
  modified:
    - frontend/package.json
    - frontend/package-lock.json
    - frontend/src/main.tsx
decisions:
  - "Toast.Provider wraps Theme (not inside it) so Viewport can be at document root per UI-SPEC"
  - "RED tests use top-level module imports (not dynamic) so vitest/pytest fail at collection — valid RED signal per plan spec"
  - "test_edit_api.py uses inline db_session + client fixtures (mirrors conftest pattern) rather than depending on project_id fixture that does not exist yet"
  - "Pre-existing test failures (test_llm_retry.py pydantic error, @testing-library/dom missing) confirmed as pre-existing via git stash verification — not caused by this plan"
metrics:
  duration: "~30 minutes"
  completed: "2026-04-24"
  tasks: 4
  files: 11
---

# Phase 04 Plan 01: Wave 0 Scaffold Summary

**One-liner:** Test scaffolds (7 RED files) + shared TypeScript editing contracts + Toast.Provider mount + @radix-ui deps installed.

## What Was Done

Wave 0 for Phase 4 canvas-editing-basic. This plan establishes the foundations that all downstream plans (P02-P08) depend on:

1. **npm deps installed** — `@radix-ui/react-toast ^1.2.15` and `@radix-ui/react-icons ^1.3.2` added to `frontend/package.json`.
2. **Toast.Provider mounted** — `frontend/src/main.tsx` wraps `<App />` with `Toast.Provider swipeDirection="right"` and mounts `Toast.Viewport` at document root (fixed bottom-4 right-4).
3. **Shared TypeScript contracts** — `frontend/src/types/editing.ts` exports all 13 named types consumed by P03-P08.
4. **Frontend RED tests** — 4 test files created, all failing at collection time because `useProjectStore`, `useEditorStore`, `useUndoShortcut` do not exist yet.
5. **Backend RED tests** — 2 test files created; `test_voronoi.py` fails at collection (ModuleNotFoundError on `medieval_forge.services.voronoi`); `test_edit_api.py` collects 7 tests that will fail when `edit.py` is built.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| a4a7f7f | feat | Install @radix-ui/react-toast + react-icons, mount Toast.Provider |
| 3420768 | feat | Add shared TypeScript contracts (editing.ts) |
| 0c2a924 | test | Frontend Wave 0 RED scaffolds (4 files) |
| 323a97c | test | Backend Wave 0 RED scaffolds (2 files) |

## Test File Paths + RED Failure Summary

| File | Tests | RED State |
|------|-------|-----------|
| `frontend/src/stores/__tests__/useProjectStore.test.ts` | 5 | Cannot find module '../useProjectStore' |
| `frontend/src/stores/__tests__/useEditorStore.test.ts` | 4 | Cannot find module '../useEditorStore' |
| `frontend/src/hooks/__tests__/useUndoShortcut.test.ts` | 3 | Cannot find module '../useUndoShortcut' |
| `frontend/src/components/canvas/__tests__/CapitalDrag.test.tsx` | 2 | Cannot find module '../../../stores/useEditorStore' |
| `backend/tests/services/test_voronoi.py` | 9 | ModuleNotFoundError: medieval_forge.services.voronoi |
| `backend/tests/api/test_edit_api.py` | 7 | Collects successfully; fails at run (edit.py not built) |

**Total: 30 RED test anchors across 6 files.**

## Complete Export List: `frontend/src/types/editing.ts`

Downstream plans P03-P08 should import from this module. Do NOT redefine these types.

```typescript
// Backend payload contracts
export interface MoveCapitalRequest       // lon: number, lat: number
export interface MoveCapitalResponse      // updated_territories, affected_ids
export interface MergeRequest             // condado_ids, primary_id
export interface MergeResponse            // merged_id, merged_territory, removed_ids, warning
export interface SplitRequest             // cut_line, mode
export interface SplitResponse            // original_id, new_territory_a, new_territory_b
export interface ReshapeGeometryRequest   // geometry: GeoJSONPolygon

// GeoJSON primitives
export type Position = [number, number]
export interface GeoJSONPolygon           // type: 'Polygon', coordinates
export interface GeoJSONMultiPolygon      // type: 'MultiPolygon', coordinates

// Zustand store shapes
export interface ProjectGeometryState     // territories, capitals
export type ToolMode = 'none' | 'select' | 'capital' | 'vertex' | 'split'
export type SplitSubMode = 'snap' | 'polyline' | 'freehand'
export interface EditorState              // editMode, activeTool, splitSubMode, vertexEditCondadoId, rubberBandSelectionIds, undoLabels, redoLabels

// Labels / validation / save
export type UndoLabel = string
export interface ValidationIssue         // condado_id, severity, rule, message
export type SaveStrategy = 'auto' | 'per_op' | 'explicit'
export type SaveStatus = 'saved' | 'saving' | 'unsaved'
```

## Toast.Provider in main.tsx

```tsx
import * as Toast from '@radix-ui/react-toast'

<Toast.Provider swipeDirection="right">
  <Theme appearance="light" accentColor="iris" radius="medium">
    <QueryClientProvider ...>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </Theme>
  <Toast.Viewport className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 outline-none" />
</Toast.Provider>
```

Theme config (`appearance="light" accentColor="iris" radius="medium"`) unchanged — LOCKED per UI-SPEC.

## Deviations from Plan

None — plan executed exactly as written.

Pre-existing failures found (not caused by this plan):
- `tests/unit/test_llm_retry.py`: Pydantic validation error in fixture (pre-existing, confirmed via git stash)
- Multiple `@testing-library/dom` missing errors across frontend tests (pre-existing, same 15/18 failure count before and after)

## Known Stubs

None. This plan is types + test scaffolds only; no UI rendering or data wiring.

## Threat Flags

None. This plan adds no new runtime endpoints, auth paths, file access patterns, or schema changes.

## Self-Check: PASSED

Files verified to exist:
- frontend/src/types/editing.ts: FOUND
- frontend/src/stores/__tests__/useProjectStore.test.ts: FOUND
- frontend/src/stores/__tests__/useEditorStore.test.ts: FOUND
- frontend/src/hooks/__tests__/useUndoShortcut.test.ts: FOUND
- frontend/src/components/canvas/__tests__/CapitalDrag.test.tsx: FOUND
- backend/tests/services/test_voronoi.py: FOUND
- backend/tests/api/test_edit_api.py: FOUND

Commits verified:
- a4a7f7f: FOUND
- 3420768: FOUND
- 0c2a924: FOUND
- 323a97c: FOUND
