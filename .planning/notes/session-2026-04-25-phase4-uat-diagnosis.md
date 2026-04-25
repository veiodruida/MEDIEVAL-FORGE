---
type: session-notes
date: 2026-04-25
phases: [04-canvas-editing-basic]
status: gaps-planned
next: Execute 04-11 + 04-12 (gap closure) — likely on Paperclip
---

# Session 2026-04-25 — Phase 04 Human UAT, systemic diagnosis, gap-closure plans

## Goal

Run the 5 pending human UAT tests from `04-HUMAN-UAT.md` (left at `status: partial` on 2026-04-24), record results, diagnose any failures, and prepare fix plans for execution. Outcome would determine whether Phase 04 is truly closed or needs gap-closure work.

## Outcomes

### Human UAT (commit pending)

All 5 tests **failed** with the same symptom pattern: user clicks the "Editar" button to enter edit mode, then no edit interaction works.

| # | Test | Reported |
|---|------|----------|
| 1 | Capital drag re-render | "arrasto o ponto, fica um buraco e nada acontece" |
| 2 | Vertex drag | "não consigo arrastar nada" |
| 3 | Multi-select + Fundir | "shift não funciona, drag não seleciona, botão Fundir não existe" |
| 4 | Ctrl+Z | "não funciona" |
| 5 | Ctrl+S (explicit) | "não funciona" |

UAT.md status updated to `diagnosed`. All 5 gaps recorded in YAML structure.

### Root cause (single, high confidence)

`useProjectStore.hydrate(projectId, territories, capitals)` is **never called in production code**. Defined at `frontend/src/stores/useProjectStore.ts:24,47` with zero call sites outside test files.

The edit-side Zustand store stays at initial empty values (`projectId: null`, `territories: {}`, `capitals: {}`) for the entire session. Downstream consumers all short-circuit:

- Capital drag: `applyBatchUpdate` mutates an empty store; rollback path reads `capitals[id]` → `undefined`.
- Vertex handles: `VertexHandlesLayer` early-returns unless `projectId && vertexEditId`.
- Merge UI: `SelectionFloatingToolbar.handleMerge` guards on `if (!projectId) return`.
- Ctrl+Z: zundo `temporal.undo()` runs against empty history (no mutations ever landed because they all gated on `projectId`).
- Ctrl+S: `manualSave()` destructures `{ projectId, territories, capitals }` from the empty store → no snapshot to POST.

**Why automated tests passed:** every unit/integration test seeds the store imperatively via `useProjectStore.getState().applyBatchUpdate(...)` (e.g., `CapitalDrag.test.tsx:201,250`), bypassing the missing real-mount hydration path. Classic blind spot of imperative test setup.

**Code authors anticipated the dependency** but never wired it: `CanvasViewer.tsx:177` has the comment *"storeProjectId may differ from the projectId prop until hydrate() is called"*.

**Secondary gap (separate from hydration bug):** shift-click multi-select is genuinely missing. Only rubber-band was implemented. SC3 (merge) promised shift-click affordance.

### Gap-closure plans (created, verified 2/3 iterations)

**04-11 — Wire useProjectStore.hydrate() in CanvasViewer**
- Effect mounts hydrate once per `(projectId, cacheVersion)` tuple via `hydratedKeyRef = useRef<string|null>(null)`.
- Wraps hydrate with `temporal.pause() → hydrate() → temporal.clear() → temporal.setState({ isTracking: true })` so hydration does NOT pollute zundo undo history.
- Data adapter: direct `fetch('/api/projects/:id/territories.geojson?v=...')` (Option B — chosen over `queryClient.getQueryData` to avoid TanStack v5 select-cache assumptions).
- 7 unit tests including assertions that `pastStates.length === 0` after hydrate and that mid-session edits survive cache invalidation refetch.

**04-12 — Shift-click multi-select on TerritoryLayer**
- Adds shift-modifier handling to `handleClick` (append/toggle to `useEditorStore.rubberBandSelectionIds`).
- `handleClick` is `useCallback(..., [])` with all store reads via `getState()` inside body — keeps reference stable across mutations so `React.memo` on `TerritoryPolygon` does not invalidate on every shift-click (would have caused a re-render storm on 800-territory maps).
- Only engages in edit mode; outside edit mode, shift-click falls through to plain single-select.
- 6 tests including reference-stability assertion.

### Plan-checker iterations

Iteration 1 found 2 blockers + 3 warnings:
- BLOCKER 1: hydrate would push entries into zundo history → broken Ctrl+Z UX.
- BLOCKER 2: `territoriesQ.data` in dep array → invalidation refetches would race-overwrite in-memory edits.
- WARNING 3: Option-A `getQueryData` fragile.
- WARNING 5: test 2 needed explicit absence assertion.
- MINOR 6: `handleClick` reference instability → re-render storm risk.

Iteration 2: all 5 fixes confirmed in place. **VERIFICATION PASSED.**

## Files changed

- `M .planning/ROADMAP.md` — plan list updated (10 → 12 plans for phase 04, progress row).
- `M .planning/phases/04-canvas-editing-basic/04-HUMAN-UAT.md` — `partial` → `diagnosed`, all 5 tests as `result: issue`, full root cause + fix scope appended.
- `?? .planning/phases/04-canvas-editing-basic/04-11-PLAN.md` — gap closure plan 1.
- `?? .planning/phases/04-canvas-editing-basic/04-12-PLAN.md` — gap closure plan 2.
- `?? .planning/notes/session-2026-04-25-phase4-uat-diagnosis.md` — this file.

## Handoff

User is migrating execution to Paperclip (https://github.com/paperclipai/paperclip). They already have CEO / Coder / Designer agents on the platform configured for the Reconquista (Unity grand strategy) project, and will spin up a Medieval Forge project alongside.

A Paperclip briefing pack was produced for the user inline in this session — see chat. The briefing references `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `.planning/phases/04-canvas-editing-basic/04-11-PLAN.md` and `04-12-PLAN.md`, and `04-HUMAN-UAT.md` as the canonical context Paperclip agents should read on first task assignment.

## Next session (whoever picks it up — local Claude or Paperclip Coder)

1. Execute 04-11 first (wave 1), commit atomic.
2. Execute 04-12 (wave 2, depends on 04-11), commit atomic.
3. Re-run the 5 failing UAT tests manually to confirm closure.
4. Mark UAT status `complete`, then proceed to Phase 5 (Canvas Editing — Advanced) discuss/plan.
