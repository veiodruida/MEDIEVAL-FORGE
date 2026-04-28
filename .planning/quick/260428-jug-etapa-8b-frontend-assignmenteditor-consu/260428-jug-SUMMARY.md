---
phase: quick-260428-jug
plan: 01
subsystem: frontend-research
tags: [research, assignments, edit, etapa-8b, frontend, radix-themes, tdd]
dependency_graph:
  requires:
    - quick-260428-h1t (PATCH /research/assignments backend endpoint)
  provides:
    - AssignmentEditor UI component consuming PATCH /api/projects/{id}/research/assignments
    - patchResearchAssignments API client function
  affects:
    - ResearchDialog (gains Editar assignments button in success/cached states)
    - useResearchStore (setManualResult updated with new MapResearchResult on save)
tech_stack:
  added: []
  patterns:
    - Radix Dialog.Root as controlled component (open/onOpenChange props)
    - computeDelta diff: only changed fields sent to PATCH endpoint
    - scrollIntoView jsdom stub in test-setup.ts for Radix Select in vitest
    - fireEvent.click on Select trigger + findByRole("option") for Radix Select in tests
    - New-shape type guard (Array.isArray condados) before mounting AssignmentEditor
key_files:
  created:
    - frontend/src/components/research/AssignmentEditor.tsx
    - frontend/src/components/research/AssignmentEditor.test.tsx
  modified:
    - frontend/src/api/edit.ts (MapResearchResult type + patchResearchAssignments)
    - frontend/src/components/research/ResearchDialog.tsx (Editar assignments button + AssignmentEditor mount)
    - frontend/src/test-setup.ts (scrollIntoView stub for jsdom)
decisions:
  - "Test 2 (barony Select change): interact via fireEvent.click(trigger) + findByRole('option') after adding scrollIntoView stub to test-setup.ts — avoids native select approach which requires isFormControl=true (needs form wrapper that Radix Dialog portal bypasses)"
  - "New-shape guard in ResearchDialog: only mount AssignmentEditor when result has condados array (MapResearchResult shape) — old ResearchResult from test mocks has condados_assignment, which would crash AssignmentEditor useState initializer"
  - "mapResearchResult type exported from edit.ts (not research.ts) — keeps legacy ResearchResult untouched; store-wide type unification is a deferred quick task"
metrics:
  duration: ~30min
  completed: 2026-04-28
  tasks_completed: 2
  files_changed: 5
---

# Phase quick-260428-jug Plan 01: AssignmentEditor — Frontend Consumes PATCH /research/assignments

**One-liner:** Radix Dialog AssignmentEditor with delta-only PATCH dispatch, error truncation, and ResearchDialog wiring, backed by 5 vitest+RTL tests using explicit symbolic fixtures.

## What Was Built

### API Client (`frontend/src/api/edit.ts`)
- `MapResearchResult` type (mirrors backend: kingdoms, duchies, condados[], barony_assignments)
- `CondadoRename` type (`{ name?, duchy_id? }`)
- `PatchAssignmentsRequest` interface
- `patchResearchAssignments(projectId, body)` — calls existing `patchJson`, unwraps `{ result: ... }`

### Component (`frontend/src/components/research/AssignmentEditor.tsx`)
- Radix `Dialog.Root` (controlled: `open` + `onOpenChange` props)
- Section 1: Barony → Condado assignments — each barony row shows `Select.Root` with current condado; `data-testid="barony-row-{bid}"` on trigger
- Section 2: Condado renames — `TextField.Root` for name (`data-testid="condado-name-{cid}"`) + `Select.Root` for duchy (`data-testid="condado-duchy-{cid}"`)
- `computeDelta()` — produces only changed `barony_assignments` and/or `condado_renames`; empty keys omitted
- `hasChanges` (useMemo) — Salvar disabled until at least one change
- Error Callout (`data-testid="error-callout"`) — renders only on error, truncated to 600 chars
- `handleSave` — `await patchResearchAssignments`, then `setManualResult(result)`, then `onOpenChange(false)`

### ResearchDialog Wiring (`frontend/src/components/research/ResearchDialog.tsx`)
- Added `manualResult` selector from `useResearchStore`
- Added `editorOpen` (`useState<boolean>`)
- "Editar assignments" button added to success and cached render branches
- `AssignmentEditor` mounted outside `Dialog.Root` (avoids nested Dialog z-index)
- New-shape guard: only mounts when result has `condados` array (MapResearchResult shape)

## Behavior Coverage

| Test | Fixture | Assertion |
|------|---------|-----------|
| 1 — renders barony rows + Salvar disabled | B_1→C_LEON, B_2→C_LEON, B_3→C_BURGOS | All 3 testids visible; trigger labels match condado names; save-button disabled |
| 2 — barony move sends delta only | Change B_2: C_LEON→C_BURGOS | fetch body = `{ barony_assignments: { B_2: "C_BURGOS" } }` (B_1, B_3 absent) |
| 3 — condado rename sends delta only | Edit C_LEON name | fetch body = `{ condado_renames: { C_LEON: { name: "..." } } }` (duchy_id absent) |
| 4 — 400 error shows Callout, dialog stays open, 1000-char truncated to ≤600 | longError = "x".repeat(1000) | error-callout present; textContent.length ≤ 600; onOpenChange(false) NOT called |
| 5 — success updates store + closes dialog | Mock 200 with updatedResult | setManualResult called once with returned result; onOpenChange(false) called |

## Test Run Results

| Suite | Before | After |
|-------|--------|-------|
| AssignmentEditor.test.tsx | 0 tests | 5/5 passing |
| ResearchDialog.test.tsx | 5/5 | 5/5 (no regression) |
| Full suite | 186/186 | 191/191 |

## Threat Mitigations Verified

| Threat | Mitigation | Test |
|--------|------------|------|
| T-jug-01 Tampering (computeDelta) | Deep-copy via spread in useState initializer; diff reads original prop | Tests 2, 3 assert delta shape |
| T-jug-02 Info Disclosure (error truncation) | `error.slice(0, 600)` in catch handler | Test 4: 1000-char error → ≤600 rendered |
| T-jug-04 Repudiation (optimistic write) | `setManualResult` called only after `await patchResearchAssignments` resolves | Test 5: spy asserts post-await call |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Radix Select scrollIntoView crash in jsdom**
- **Found during:** Task 2 (first GREEN run — Test 2 failed with `candidate?.scrollIntoView is not a function`)
- **Issue:** Radix Select calls `scrollIntoView` on mount to scroll selected item into view; jsdom does not implement this method
- **Fix:** Added `Element.prototype.scrollIntoView = function() {}` stub to `frontend/src/test-setup.ts` (same pattern as existing ResizeObserver stub)
- **Files modified:** `frontend/src/test-setup.ts`
- **Commit:** ed0ce92

**2. [Rule 1 - Bug] ResearchDialog cached-result test crashed when mounting AssignmentEditor**
- **Found during:** Task 2 full suite run — ResearchDialog "shows cached badge" test failed
- **Issue:** When `cachedQuery.data` contains old `ResearchResult` shape (has `condados_assignment`, no `condados`), the cast to `MapResearchResult` caused `researchResult.condados.map(...)` to throw in AssignmentEditor's `useState` initializer
- **Fix:** Added new-shape guard in ResearchDialog — only mounts `AssignmentEditor` when result has `Array.isArray(r.condados)` (MapResearchResult shape). Old-shape results skip the mount.
- **Files modified:** `frontend/src/components/research/ResearchDialog.tsx`
- **Commit:** ed0ce92

**3. [Rule 2 - Test approach] Radix Select interaction in jsdom requires trigger click + findByRole("option")**
- **Found during:** Task 1→2 test convergence
- **Plan said:** "Use `data-testid` if Radix Select labelling proves brittle" + "hidden native select" approach
- **Actual:** Radix Select native `<select>` only renders when `isFormControl=true` (trigger in a form). Radix Dialog portal bypasses any `<form>` wrapper. The working approach: click trigger (`fireEvent.click`) + `findByRole("option")` after adding scrollIntoView stub.
- **No code change** — test approach adjusted inline.

## Out of Scope

- Drag-drop reordering of barony/condado rows
- Kingdom-level or duchy-level renames (only condado renames implemented per plan)
- `ResearchResult` type unification in `useResearchStore` (deferred — separate quick task)
- Validation of condado name format in UI (backend enforces via Pydantic)
- Virtualization for large barony lists (>500 rows — T-jug-03 accepted for v1)

## Commits

| Hash | Message |
|------|---------|
| ddcc228 | `test(quick-260428-jug-01): add 5 failing tests for AssignmentEditor (RED)` |
| ed0ce92 | `feat(quick-260428-jug-01): implement AssignmentEditor + wire ResearchDialog (GREEN, 5 tests)` |

## Self-Check: PASSED

- `frontend/src/components/research/AssignmentEditor.tsx` — FOUND
- `frontend/src/components/research/AssignmentEditor.test.tsx` — FOUND
- `frontend/src/api/edit.ts` (patchResearchAssignments) — FOUND
- `frontend/src/components/research/ResearchDialog.tsx` (Editar assignments) — FOUND
- Commit ddcc228 — FOUND
- Commit ed0ce92 — FOUND
- 191/191 tests passing — VERIFIED
- `tsc --noEmit` — CLEAN
