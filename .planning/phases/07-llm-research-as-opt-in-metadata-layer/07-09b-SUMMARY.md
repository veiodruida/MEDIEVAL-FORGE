---
phase: 07-llm-research-as-opt-in-metadata-layer
plan: 09b
subsystem: frontend/inspector-sidebar
tags: [research, inspector, microcopy, ui-spec, reviews-fix-2, blocker-3]
requires:
  - frontend/src/components/research/ResearchDialog.tsx (Plan 09a)
  - frontend/src/api/useResearchOverlay.ts (Plan 09a)
provides:
  - InspectorSidebar placeholder-mode research trigger
  - Dual-timestamp microcopy (REVIEWS fix #2)
  - Condado + barony "Pesquisa aplicada" green badge
  - "Atualizar pesquisa" reopen link with forceRefresh pre-checked
  - In-sidebar ResearchDialog mount (BLOCKER 3 partition)
affects:
  - frontend/src/components/canvas/InspectorSidebar.tsx
  - frontend/src/components/canvas/CanvasViewer.tsx (project.id + project.status threaded through)
tech-stack:
  added: []
  patterns:
    - Local useState for dialog open + initialForceRefresh
    - Radix Tooltip with explicit data-tooltip-body for test assertion without pointer events
    - Inline timestampsMatch + formatDate helpers (no date-fns dependency)
key-files:
  created: []
  modified:
    - frontend/src/components/canvas/InspectorSidebar.tsx
    - frontend/src/components/canvas/__tests__/InspectorSidebar.test.tsx
    - frontend/src/components/canvas/CanvasViewer.tsx
decisions:
  - Dialog mount lives at sidebar root inside placeholder + condado + barony branches; not in multi-select / project-overview branches because no trigger lives there.
  - regionDisplayNameFor() maps country_qid → friendly label, defaulting to qid when no mapping registered. Avoids hard-coding "Iberia 868 AD" in two places.
  - data-tooltip-body attribute on the Tooltip wrapper exposes the tooltip body to vitest without booting Radix portal + pointer events.
metrics:
  duration: ~30min
  completed: 2026-05-14T15:48Z
  tasks: 1/1
  files_modified: 3
  commits: 2 (RED + GREEN)
---

# Phase 07 Plan 09b: InspectorSidebar Research Trigger + Dual-Timestamp Microcopy Summary

Wired Plan 09a's `ResearchDialog` + `useResearchOverlay` into `InspectorSidebar` per UI-SPEC §Surface 2, with the REVIEWS fix #2 dual-timestamp microcopy (single-line on fresh runs, two-line on cache-hit re-applies).

## What landed

- **Placeholder-mode trigger.** `Pesquisar metadados históricos` button with `<MagnifyingGlassIcon />`, disabled when `project.status !== 'generated'`, wrapped in a Radix `Tooltip` carrying `Gere o mapa antes de pesquisar metadados.`
- **REVIEWS fix #2 microcopy.** Renders below the trigger button when `overlay.exists && meta != null`. Same-instant (within 1s) → single-line `Última pesquisa: {provider} · {model} · {YYYY-MM-DD HH:mm}`. Different timestamps → two-line `Pesquisa gerada: {provider} · {model} · {generated_at}` + `· aplicada: {applied_at}`.
- **Condado + barony badges.** Green `Pesquisa aplicada` badge + `Atualizar pesquisa` reopen link rendered when `overlay.covered_condado_ids` includes the condado id (parent condado id for barony mode).
- **BLOCKER 3 partition honored.** `<ResearchDialog>` mounted inside `InspectorSidebar` via local `useState`; `ProjectDetail.tsx` was NOT modified (verified by grep: returns 0 lines).
- **Phase 03 D-16 lock preserved.** PLACEHOLDER_PT and the entire COPY constant remain byte-identical.

## Test plan

`frontend/src/components/canvas/__tests__/InspectorSidebar.test.tsx` — 9 NEW cases (26 total, all green):

| Suite | Case |
|-------|------|
| placeholder mode | trigger button renders with PT-BR label |
| placeholder mode | trigger disabled + tooltip body when status !== 'generated' |
| placeholder mode | clicking trigger opens dialog with force-refresh = false |
| placeholder mode | REVIEWS fix #2 single-line microcopy (timestamps match) |
| placeholder mode | REVIEWS fix #2 two-line microcopy (timestamps differ) |
| placeholder mode | microcopy absent when overlay.meta is null |
| condado mode    | `Pesquisa aplicada` badge appears for covered id |
| condado mode    | `Atualizar pesquisa` click → dialog open + force-refresh = true |
| condado mode    | badge hidden when overlay does not cover id |
| barony mode     | `Pesquisa aplicada` rendered for parent condado id |
| barony mode     | `Atualizar pesquisa` click → dialog open + force-refresh = true |

Mocks: `useResearchOverlay` (vi.hoisted ref) + `ResearchDialog` (renders `<div data-testid="research-dialog-mock" data-force-refresh="...">` when `open=true`). Real component is exercised in Plan 09a's dedicated suite.

## Verification

- `cd frontend && npx vitest run src/components/canvas/__tests__/InspectorSidebar.test.tsx` → 26/26 pass.
- `cd frontend && npm run build` → `tsc -b && vite build` exit 0 (475 modules, 841 kB bundle).
- Adjacent suites: CanvasViewer.test.tsx + ProjectDetail.errorBoundary.test.tsx → 8/8 pass (no regressions).
- BLOCKER 3 check: `grep -l "ResearchDialog\|setResearchOpen" frontend/src/pages/ProjectDetail.tsx` → exit 1 (no matches).

## Deviations from Plan

**1. [Rule 2 - Correctness] Threaded `project.id` + `project.status` through `CanvasViewer.tsx` → `InspectorSidebar.tsx`.**
- **Found during:** Task 1 — `useResearchOverlay(projectId)` requires the project id; the trigger disabled-state requires `status`.
- **Issue:** The plan's `<read_first>` listed `InspectorSidebarProps.project` (existing shape: name/country_qid/period_start/period_end), but the action items reference `project?.status !== 'generated'` and a `projectId` for the dialog without specifying who provides them.
- **Fix:** Extended `ProjectSummary` interface with `id: string` and `status: string`. Updated `CanvasViewer.tsx` (the sole call-site) to pass them through from its `project: Project` prop. Both fields already exist on the upstream `Project` API type (`frontend/src/api/client.ts:8-22`).
- **Files modified:** `frontend/src/components/canvas/InspectorSidebar.tsx`, `frontend/src/components/canvas/CanvasViewer.tsx`.
- **Commits:** 5c78827.

**2. [Rule 2 - Test ergonomics] Added `data-tooltip-body` attribute to the trigger's Tooltip wrapper.**
- **Found during:** Writing the disabled-tooltip vitest case.
- **Issue:** Radix `Tooltip` mounts its body in a portal only after pointer-enter; asserting via `screen.getByText` would require simulating pointer events with `act()` wrappers and risk flakiness in jsdom.
- **Fix:** Wrapper `<span data-testid="research-trigger-tooltip" data-tooltip-body="Gere o mapa antes de pesquisar metadados.">` exposes the literal for direct assertion. The Tooltip itself still uses the real `content` prop for production behavior.
- **Files modified:** `frontend/src/components/canvas/InspectorSidebar.tsx`.
- **Commits:** 5c78827.

**3. [Rule 3 - Build infra] Restored frontend node_modules junction.**
- **Found during:** Initial vitest invocation failed with "Could not resolve 'vitest/config'".
- **Issue:** The worktree's `frontend/node_modules` junction was absent; the main-repo `frontend/node_modules` was also empty (412 packages missing).
- **Fix:** `npm ci` in main `frontend/`, then `mklink /J node_modules <absolute-path>` in worktree. The relative-path attempt resolved incorrectly (`..\\..\\..\\..\\..\\` collapsed past the repo root) — switched to the absolute form.
- **Files modified:** none (junction is gitignored; main repo's node_modules is unchanged from the freshly installed state).

## Acceptance criteria

| Criterion | Status |
|-----------|--------|
| `Pesquisar metadados históricos` literal in InspectorSidebar.tsx (≥1 match) | 3 matches |
| `Pesquisa aplicada` literal (≥2 — condado + barony) | 4 matches |
| `Atualizar pesquisa` literal (≥1) | 5 matches |
| `Gere o mapa antes de pesquisar metadados` (≥1) | 2 matches |
| `useResearchOverlay` (≥1) | 2 matches |
| `MagnifyingGlassIcon` (≥1) | 2 matches |
| `Última pesquisa:` (REVIEWS fix #2 single-line) | 1 match |
| `Pesquisa gerada:` (REVIEWS fix #2 two-line) | 1 match |
| `· aplicada:` (REVIEWS fix #2 two-line) | 1 match |
| `meta.provider|meta.model` (≥2) | 2 matches |
| `meta.generated_at` (≥1) | 3 matches |
| `meta.applied_at` (≥1) | 2 matches |
| `timestampsMatch` helper (≥1) | 3 matches |
| `Clique num território para ver detalhes` (Phase 03 D-16 preserved) | 1 match |
| `PROJECT_OVERVIEW: 'Project overview'` (D-16 COPY block) | preserved at line 51 (note: plan acceptance string uses `=`; actual file uses `:` per object-literal syntax — D-16 lock semantically intact) |
| `color="green" variant="soft"` (≥1) | 1 match |
| `<ResearchDialog` (≥1 — BLOCKER 3 mount) | 2 matches |
| `ProjectDetail.tsx` contains 0 ResearchDialog/setResearchOpen refs (BLOCKER 3) | 0 matches (exit=1) |
| vitest cases in InspectorSidebar.test.tsx | 26 (was 17 — 9 new added) |
| vitest case asserts SINGLE-LINE microcopy substring `Última pesquisa:` | yes |
| vitest case asserts BOTH `Pesquisa gerada:` AND `· aplicada:` | yes |
| `npx vitest run src/components/canvas/__tests__/InspectorSidebar.test.tsx` exits 0 | exit 0 (26/26 pass) |
| `npm run build` exits 0 | exit 0 (475 modules, 2.02s) |

## Threat Model Verification

| Threat ID | Mitigation | Verification |
|-----------|------------|--------------|
| T-07-09b-01 (XSS via microcopy) | All meta.* values rendered as React text children | `grep -n "dangerouslySetInnerHTML" frontend/src/components/canvas/InspectorSidebar.tsx` → 0 matches |
| T-07-09b-02 (tampered covered_condado_ids) | accept — not a security boundary | n/a |
| T-07-09b-03 (timestamp display confusion) | mitigate — dual microcopy + 1s tolerance window | `timestampsMatch` helper + 2 vitest cases asserting both render paths |

## Commits

| Hash | Type | Message |
|------|------|---------|
| 452bd86 | test | add failing tests for InspectorSidebar research trigger + dual-timestamp microcopy (RED) |
| 5c78827 | feat | InspectorSidebar research trigger + dual-timestamp microcopy + applied badge (GREEN) |

## Self-Check: PASSED

- [x] FOUND: frontend/src/components/canvas/InspectorSidebar.tsx (modified)
- [x] FOUND: frontend/src/components/canvas/__tests__/InspectorSidebar.test.tsx (extended)
- [x] FOUND: frontend/src/components/canvas/CanvasViewer.tsx (project.id/status threaded)
- [x] FOUND: commit 452bd86 (test RED)
- [x] FOUND: commit 5c78827 (feat GREEN)
- [x] vitest 26/26 pass
- [x] tsc -b && vite build exit 0
- [x] BLOCKER 3 honored (ProjectDetail.tsx untouched)
