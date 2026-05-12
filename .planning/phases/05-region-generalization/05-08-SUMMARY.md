---
phase: "05"
plan: "08"
subsystem: frontend
tags: [modal, react, radix-ui, tanstack-query, region-select, new-project, vitest]
dependency_graph:
  requires:
    - phase: "05-04"
      provides: "POST /api/v3/projects endpoint"
    - phase: "05-07"
      provides: "GET /api/v3/regions endpoint"
  provides:
    - "NewProjectModal component (Radix Dialog + Select region picker)"
    - "useRegions TanStack Query hook (GET /api/v3/regions)"
    - "useCreateV3Project TanStack mutation (POST /api/v3/projects)"
    - "RegionInfo + RegionBounds TypeScript interfaces"
    - "ProjectList wired to modal trigger (Link to /projects/new removed)"
  affects:
    - "05-10 (Playwright E2E uses data-testid=new-project-button/modal/region-select)"
tech_stack:
  added: []
  patterns:
    - "Radix UI Themes Dialog.Root + Dialog.Trigger (no asChild — Themes types don't expose it)"
    - "TanStack Query useQuery queryKey ['v3', 'regions'] for region list"
    - "invalidateQueries(['projects']) on useCreateV3Project success matches useProjects key (R-08)"
    - "Toast.Provider + Toast.Root for async error notification; Toast.Viewport in test wrapper"
    - "defaultValue='iberia_868' with fallback to first has_dataset:true region"
    - "TDD: RED commit then GREEN commit per task"
key_files:
  created:
    - "frontend/src/types/region.ts"
    - "frontend/src/api/useRegions.ts"
    - "frontend/src/components/projects/NewProjectModal.tsx"
    - "frontend/src/api/__tests__/useRegions.test.ts"
  modified:
    - "frontend/src/api/client.ts (added useCreateV3Project + V3ProjectCreatePayload/Result)"
    - "frontend/src/pages/ProjectList.tsx (swap Link/Button for NewProjectModal)"
    - "frontend/src/components/projects/__tests__/NewProjectModal.test.tsx (8 cases, replaced placeholder)"
decisions:
  - "Dialog.Trigger without asChild: @radix-ui/themes DialogTriggerProps doesn't include asChild; placed data-testid on inner Button instead; testid discoverable via getByTestId per R-07"
  - "Cancel button uses handleOpenChange(false) instead of Dialog.Close asChild: same type constraint; Dialog.Close without asChild wraps in extra div — onClick approach is cleaner"
  - "Removed duplicate Select.Item for loading state: Select.Trigger placeholder already shows 'Carregando regioes...' when disabled; adding a Select.Item caused getByText to find two matches"
  - "Dialog.Title text-only (no Heading wrapper): Heading renders h1 inside Dialog.Title's h2 — nested heading elements cause React hydration warning"
  - "Toast.Viewport added to test wrapper: Toast.Root renders into Viewport; without it toast text is not in test DOM"
metrics:
  duration: "~6 minutes"
  completed: "2026-05-12"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  files_modified: 3
requirements-completed: [SC-2]
---

# Phase 05 Plan 08: NewProjectModal Frontend Summary

**One-liner:** `NewProjectModal` ships as Radix Dialog + region `Select.Root` backed by `useRegions` hook, replacing the `ProjectList` `Link to /projects/new` trigger with an in-place modal per UI-SPEC.

## What Was Built

### Task 1: useRegions hook + RegionInfo type + useCreateV3Project mutation

**Commits:** d87662f (RED) + 232107c (GREEN)

- `frontend/src/types/region.ts`: `RegionInfo` + `RegionBounds` interfaces matching GET /api/v3/regions response shape
- `frontend/src/api/useRegions.ts`: TanStack Query hook, `queryKey: ['v3', 'regions']`, `/api/v3/regions` endpoint, returns `{ data, isLoading, isError, refetch }`
- `frontend/src/api/client.ts`: `useCreateV3Project` mutation posting to `/api/v3/projects` with `{name, region_key}`; `onSuccess` invalidates `['projects']` — byte-identical to `useProjects` queryKey (R-08 satisfied)
- Legacy `useCreateProject` untouched; `ProjectNew.tsx` still imports it unchanged

### Task 2: NewProjectModal.tsx + vitest + ProjectList trigger swap

**Commits:** bd12ef9 (RED) + 5cde7fe (GREEN)

- `NewProjectModal.tsx` (231 LOC): `Dialog.Root` + `Dialog.Trigger` wrapping `Button data-testid="new-project-button"`, `Dialog.Content data-testid="new-project-modal"`, `Select.Root defaultValue="iberia_868"`, `Select.Trigger data-testid="region-select"`
- Loading state: `Select.Root disabled` + trigger placeholder `Carregando regiões...`
- Error state: `Toast.Root` with `Não foi possível carregar a lista de regiões. Tente novamente.` + `Tentar novamente` retry button
- Populated state: all regions listed; `has_dataset: false` items disabled with `(sem dataset)` suffix
- Validation: name 1–64 chars + region has_dataset:true; submit disabled until both pass
- Submit: `create.mutateAsync` → `setOpen(false)` → `navigate('/projects/${id}')`; error shown inline
- Cancel: `handleOpenChange(false)` resets all form state
- `ProjectList.tsx`: replaced `<Link to="/projects/new"><Button>` with `<NewProjectModal />`; `Button` import restored; route `/projects/new` still registered in `App.tsx`; `ProjectNew.tsx` unchanged

## Verification

```
cd frontend && npx vitest run --no-coverage
→ 36 test files, 226 tests passed

cd frontend && npx tsc --noEmit
→ exit 0

cd frontend && npm run build
→ ✓ built in 2.11s (chunk size warning pre-existing)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Dialog.Trigger/Close asChild not in @radix-ui/themes types**
- **Found during:** Task 2 (tsc check)
- **Issue:** `@radix-ui/themes` `DialogTriggerProps` and `DialogCloseProps` don't expose `asChild`; using it caused two TS2322 errors
- **Fix:** Removed `asChild` on `Dialog.Trigger` (Button child still gets `data-testid`); replaced `Dialog.Close asChild` + Button with plain Button + `onClick={() => handleOpenChange(false)}`
- **Files modified:** `NewProjectModal.tsx`
- **Commit:** 5cde7fe

**2. [Rule 1 - Bug] Duplicate "Carregando regiões..." in loading state**
- **Found during:** Task 2 (test run — `getByText` found two matches)
- **Issue:** Both `Select.Trigger placeholder` and a `Select.Item value="__loading__"` rendered the same string; RTL `getByText` throws on multiple matches
- **Fix:** Removed the redundant `Select.Item`; trigger placeholder alone correctly indicates loading state
- **Files modified:** `NewProjectModal.tsx`
- **Commit:** 5cde7fe

**3. [Rule 1 - Bug] Nested heading elements in Dialog.Title**
- **Found during:** Task 2 (test run — React hydration warning `<h1> cannot be a child of <h1>`)
- **Issue:** `Dialog.Title` renders as `h2`; wrapping `<Heading size="4">` renders as `h1` inside it — invalid HTML nesting
- **Fix:** Used `Dialog.Title` with plain text string; Radix Themes applies correct heading styles automatically
- **Files modified:** `NewProjectModal.tsx`
- **Commit:** 5cde7fe

**4. [Rule 2 - Missing critical] Toast.Viewport absent from test wrapper**
- **Found during:** Task 2 (toast test could not find toast text in DOM)
- **Issue:** `Toast.Root` renders its children into `Toast.Viewport`; without a `Toast.Viewport` in the test wrapper the toast text never appears in the document
- **Fix:** Added `React.createElement(Toast.Viewport)` to `makeWrapper()` in the test file
- **Files modified:** `NewProjectModal.test.tsx`
- **Commit:** 5cde7fe

**5. [Rule 3 - Blocker] Button import accidentally removed from ProjectList.tsx**
- **Found during:** Task 2 (tsc — TS2304 on `Button`)
- **Issue:** When editing the import line to add `NewProjectModal`, `Button` was dropped; ProjectList still uses `Button` for Abrir/Excluir
- **Fix:** Restored `Button` in the import
- **Files modified:** `ProjectList.tsx`
- **Commit:** 5cde7fe

## Known Stubs

- **ESC key / overlay click cancel coverage**: Radix Dialog handles ESC + overlay click natively at runtime; tests cover the `Cancelar` button path only. The functional behavior is correct but the two additional dismiss paths have no dedicated test case. Flagged for Plan 05-10 Playwright to cover end-to-end.

## Threat Surface

| Flag | File | Description |
|------|------|-------------|
| None | — | No new network endpoints, auth paths, or trust-boundary surfaces introduced. T-05-08-01 (client-side region_key) and T-05-08-02 (XSS via display_name) mitigations confirmed: no `pattern` bypass possible via disabled Select items; React JSX auto-escapes `display_name` interpolation. |

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `frontend/src/types/region.ts` exists | FOUND |
| `frontend/src/api/useRegions.ts` exists | FOUND |
| `frontend/src/components/projects/NewProjectModal.tsx` exists (≥120 lines) | FOUND (231 lines) |
| `grep 'Novo projeto' NewProjectModal.tsx` | FOUND (lines 100, 107) |
| `grep 'defaultValue="iberia_868"' NewProjectModal.tsx` | FOUND (line 145) |
| `grep 'sem dataset' NewProjectModal.tsx` | FOUND (line 165) |
| `grep 'data-testid="new-project-modal"'` | FOUND (line 104) |
| `grep 'data-testid="new-project-button"'` | FOUND (line 100) |
| `grep 'data-testid="region-select"'` | FOUND (line 151) |
| `grep 'NewProjectModal' ProjectList.tsx` | FOUND (lines 4, 24) |
| `grep 'to="/projects/new"' ProjectList.tsx` | 0 matches (R-05 PASS) |
| Route `/projects/new` in App.tsx | FOUND (line 13) |
| `git diff ProjectNew.tsx` | empty (PASS) |
| 226/226 vitest green | PASSED |
| tsc --noEmit exit 0 | PASSED |
| npm run build success | PASSED |
| Commit d87662f (Task 1 RED) | FOUND |
| Commit 232107c (Task 1 GREEN) | FOUND |
| Commit bd12ef9 (Task 2 RED) | FOUND |
| Commit 5cde7fe (Task 2 GREEN) | FOUND |
