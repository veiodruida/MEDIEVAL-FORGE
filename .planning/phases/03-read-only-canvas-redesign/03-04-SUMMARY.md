---
phase: 03-read-only-canvas-redesign
plan: 04
subsystem: frontend
tags: [react, sse, eventsource, run-state-machine, workspace-shell, vitest, radix-themes]

# Dependency graph
requires:
  - phase: 03-read-only-canvas-redesign
    plan: 02
    provides: POST /api/v3/projects/{id}/generate + GET /generate/stream + GET /status endpoints
  - phase: 03-read-only-canvas-redesign
    plan: 03
    provides: useRunStore (5-state machine + 11-stage PIPELINE_STAGES) + useStatusManifest precondition
provides:
  - "ProjectDetail.tsx workspace shell (160 LOC vs 697 baseline) — composes WorkspaceToolbar + canvas-state body + collapsible RunLogPanel"
  - "WorkspaceToolbar / GenerateStatusBadge / RunLogPanel / EmptyCanvasState / GeneratingCanvasState / ErrorCanvasCallout — 6 chrome components per UI-SPEC §Layout Contract"
  - "useGenerateStream() hook — EventSource subscriber translating Plan 02 SSE envelope to useRunStore actions; silently degrades on Pitfall 9 refresh-mid-run"
  - "useStatusManifest(projectId) TanStack Query hook on /api/v3/projects/{id}/status (queryKey ['v3-status', id])"
affects:
  - "03-05 (canvas surface — once read-only refactor lands, ProjectDetail body conditional already routes to CanvasViewer when has_artifacts.territory_metadata.json is true)"
  - "03-06 / 03-07 (Wave 3 deletion — ProjectDetail.tsx no longer references Stepper/StepCard/Research/Edit modules, unblocking their physical removal)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "EventSource subscriber as a React hook (useGenerateStream) — encapsulates esRef + cleanup; mirrors the v1 useResearchStream pattern but on the standard browser EventSource API instead of fetch+ReadableStream"
    - "Server-sourced run_id (POST /generate response) seeded into useRunStore.start() — keeps client runId in lock-step with server _RUN_QUEUES key"
    - "Substring-matcher fetch mock + in-memory FakeEventSource polyfill for jsdom — 16-spec integration suite covers happy path + state machine + parse-error + retry"
    - "data-testid='stage-row-{done|active|pending|error}' selectors on RunLogPanel rows — single source of truth for state-machine assertions in vitest"

key-files:
  created:
    - frontend/src/components/workspace/WorkspaceToolbar.tsx
    - frontend/src/components/workspace/GenerateStatusBadge.tsx
    - frontend/src/components/workspace/RunLogPanel.tsx
    - frontend/src/components/workspace/EmptyCanvasState.tsx
    - frontend/src/components/workspace/GeneratingCanvasState.tsx
    - frontend/src/components/workspace/ErrorCanvasCallout.tsx
    - frontend/src/components/workspace/__tests__/WorkspaceToolbar.test.tsx
    - frontend/src/components/workspace/__tests__/GenerateStatusBadge.test.tsx
    - frontend/src/components/workspace/__tests__/RunLogPanel.test.tsx
    - frontend/src/components/workspace/__tests__/ProjectDetail.workspace.test.tsx
    - frontend/src/api/useGenerateStream.ts
  modified:
    - frontend/src/pages/ProjectDetail.tsx (full rewrite: 697 -> 160 LOC; named export `ProjectDetail` preserved for App.tsx route)
    - frontend/src/api/client.ts (+1 hook: useStatusManifest + StatusManifest interface; legacy hooks left untouched for non-workspace consumers — Wave 3 cleans them up)

key-decisions:
  - "Extract SSE wiring into frontend/src/api/useGenerateStream.ts (advisor recommendation) — keeps ProjectDetail.tsx comfortably under the 280-LOC budget AND makes the EventSource bridge unit-testable as a hook in isolation"
  - "Use existing useExport() mutation (POST /api/projects/{id}/export -> anchor.click()) rather than the plan's pseudocode `window.location.href = '/api/projects/{id}/export'` — the v1 endpoint is POST-returning-JSON, NOT a GET download URL. Plan pseudocode was incorrect; the existing hook is the canonical pattern (advisor flag #1)"
  - "Server run_id from POST /generate response feeds run.start() — replaces plan's pseudocode `crypto.randomUUID()`. Keeps client state in lock-step with server _RUN_QUEUES (advisor flag #6)"
  - "EventSource onerror handler silently degrades (close + no state transition) instead of pushing to error state — Pitfall 9 (refresh-mid-run) means /stream may 404 after the producer cleared even though the run completed successfully; /status query reconciles real outcome (advisor flag #5)"
  - "FakeEventSource polyfill defined inline in the test file (NOT in test-setup.ts) — narrow scope, no global pollution, matches Karpathy 'minimum code' principle"
  - "logPanelOpen as local React state in ProjectDetail (NOT in useRunStore) — UI ephemeral state doesn't belong in a SSE-driven domain store; keeps useRunStore single-purpose (run lifecycle)"
  - "WorkspaceToolbar CTA label flips to 'Regenerar' during generating runs (in addition to hasArtifacts/generated cases) — UI-SPEC State Machine table specifies the disabled affordance keeps the regenerate semantic; the test asserts this exact contract"
  - "Done event also invalidates ['projects', id] not just ['v3-status', id] — without the project query refetch, project.updated_at stays stale and CanvasViewer's cacheVersion never bumps (advisor flag #4 — D-19 cache-bust)"

requirements-completed: [SC-1, SC-2, SC-3]

# Metrics
duration: ~14min
completed: 2026-05-09
---

# Phase 03 Plan 04: Workspace shell rewrite Summary

**Six new Radix UI Themes chrome components + a 160-LOC ProjectDetail rewrite (vs 697 baseline) + a useGenerateStream EventSource hook + 16-spec integration test suite covering the full SSE-driven state machine. Old v1 stepper imports purged from ProjectDetail; Wave 3 deletion path now unblocked. Full vitest suite 268/268 green.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-05-09T22:15Z
- **Completed:** 2026-05-09T22:29Z
- **Tasks:** 3
- **Commits:** 3 atomic
- **Files created:** 11
- **Files modified:** 2

## Accomplishments

- **6 chrome components built per UI-SPEC §Layout Contract.** WorkspaceToolbar (48px sticky, back link + project name + status badge + CTAs), GenerateStatusBadge (5-state color/copy mapping), RunLogPanel (11 canonical stages with done/active/pending/error glyphs + data-testid selectors), EmptyCanvasState (D-05), GeneratingCanvasState (D-07), ErrorCanvasCallout (D-08 with copyable error block + retry).
- **PT-BR copy locked verbatim** from UI-SPEC §Copywriting Contract: "← Projetos", "Gerar Mapa", "Regenerar", "Exportar ZIP", "Pronto", "Mapa gerado", "Erro", "Gerar mapa medieval para [país] [período]", "Nenhum mapa gerado…", "Gerando mapa…", "Falha no estágio: [stage_name]", "Tentar novamente", "Copiar". Acceptance grep returns 9+ matches.
- **ProjectDetail rewritten as ProjectDetailWorkspace** — 160 LOC vs 697 baseline. State machine: idle (no artifacts → EmptyCanvasState; with artifacts → CanvasViewer) → generating (GeneratingCanvasState) → generated (CanvasViewer) → error (ErrorCanvasCallout). Status badge click toggles a floating RunLogPanel overlay.
- **useGenerateStream hook** (`frontend/src/api/useGenerateStream.ts`) — EventSource subscriber that parses the structured SSE envelope from Plan 02, dispatches to useRunStore (start/startStage/finishStage/finish/appendLog), and handles three failure modes: (a) malformed JSON (T-03-FE-WORKSPACE-01 — appendLog `[parse-error]`, no state transition), (b) `error` event (finish('error', message, stage) + close), (c) EventSource onerror (silent degrade per Pitfall 9 refresh-mid-run).
- **useStatusManifest hook** added to `client.ts` — TanStack Query on `/api/v3/projects/{id}/status`, queryKey `['v3-status', id]`, staleTime 5s. The SSE done handler invalidates BOTH `['v3-status', id]` AND `['projects', id]` so CanvasViewer's `cacheVersion={project.updated_at}` bumps after a successful run (D-19).
- **Zero references to deleted v1 modules in ProjectDetail.** The plan's forbidden-symbol grep (useEditorStore, usePipelineStore, useResearchStore, useValidationStore, useProjectStore, EditToolbar, SplitTool, VertexHandlesLayer, TerritoryEditor, TerrainBadgesLayer, SaveStatusIndicator, ResearchDialog, AssignmentEditor, CodexViewer, Stepper, StepCard, ProviderEffortPicker, TerrainDataSection, BaronyGranularitySlider) returns zero on the new file. SC-3 prerequisite met for this surface.
- **30 specs across 4 test files green.** WorkspaceToolbar (5), GenerateStatusBadge (6), RunLogPanel (3), ProjectDetail.workspace (16) — covering happy path, state transitions, SSE flow, retry, garbage envelope, unmount cleanup, file LOC, deleted-module check, 11-stage keystone integration.

## Task Commits

| # | Task | Type | Commit |
|---|------|------|--------|
| 1 | Add 6 workspace chrome components + 3 component tests | feat | `460c507` |
| 2 | Rewrite ProjectDetail as workspace shell + useGenerateStream + useStatusManifest + integration test (10 specs) | feat | `82f95e1` |
| 3 | Extend integration test with 6 state-machine specs | test | `3fe5b7f` |

## Files Created/Modified

### Created (11)

- `frontend/src/components/workspace/WorkspaceToolbar.tsx` — 91 lines. 48px sticky toolbar; left zone (back link + project name), center (status badge), right (Gerar Mapa/Regenerar + Exportar ZIP).
- `frontend/src/components/workspace/GenerateStatusBadge.tsx` — 56 lines. Maps RunState × currentStage × hasArtifacts → {color, copy}. data-color attribute for assertions.
- `frontend/src/components/workspace/RunLogPanel.tsx` — 67 lines. Imports PIPELINE_STAGES, renders 11 rows with rowState-derived data-testid selectors (`stage-row-done|active|pending|error`).
- `frontend/src/components/workspace/EmptyCanvasState.tsx` — 31 lines. Centered icon + heading + body + CTA per UI-SPEC §Canvas States.
- `frontend/src/components/workspace/GeneratingCanvasState.tsx` — 31 lines. Centered caption + inline RunLogPanel.
- `frontend/src/components/workspace/ErrorCanvasCallout.tsx` — 61 lines. Red Callout + monospace error block + Copiar/Tentar novamente buttons.
- `frontend/src/components/workspace/__tests__/WorkspaceToolbar.test.tsx` — 5 specs (project name, back link, Gerar Mapa, disabled Regenerar mid-run, Exportar ZIP, 48px height).
- `frontend/src/components/workspace/__tests__/GenerateStatusBadge.test.tsx` — 6 specs (idle/no-artifacts → gray Pronto; idle/with-artifacts → grass Mapa gerado; generating+voronoi → amber Gerando: voronoi; generated → grass; error → red; click).
- `frontend/src/components/workspace/__tests__/RunLogPanel.test.tsx` — 3 specs (11 stages canonical order; completed/current/pending mix; errorStage override).
- `frontend/src/components/workspace/__tests__/ProjectDetail.workspace.test.tsx` — 16 specs (empty/error/generated bodies, POST /generate dispatch, SSE happy path, retry, unmount close, 11-stage SSE keystone, badge expansion toggle, garbage envelope, disabled Regenerar mid-run, POST 500 → error state, file LOC, deleted-module grep).
- `frontend/src/api/useGenerateStream.ts` — 99 lines. EventSource hook with try/catch around JSON.parse, silent onerror degrade, terminal close on done/error.

### Modified (2)

- `frontend/src/pages/ProjectDetail.tsx` — full rewrite, 697 → 160 LOC. Named export `ProjectDetail` preserved for App.tsx route. Composes the 6 workspace components + CanvasViewer (already stripped in Plan 03 of v1 imports).
- `frontend/src/api/client.ts` — added `useStatusManifest` hook + `StatusManifest` interface. Legacy hooks (useGenerate, useExport, useIngestStream, useIngestStatus, useTerritoryTemplate, useRenderModern) remain — non-workspace surfaces still consume them; Wave 3 (Plan 03-06/07) cleans them up.

## Decisions Made

- **useGenerateStream extracted as a hook (advisor recommendation).** Plan offered "inline OR companion file" — extraction kept ProjectDetail at 160 LOC and made the SSE bridge isolatable for the parse-error / retry / Pitfall 9 tests.
- **handleExport uses existing useExport mutation, not direct navigation.** The plan's pseudocode `window.location.href = '/api/projects/{id}/export'` was incorrect: the v1 endpoint is `POST` returning `{download_url, zip_filename}`. The existing `useExport` hook in `client.ts:280` already implements POST → anchor.click(). Used as-is.
- **Server-sourced run_id seeded into useRunStore.start().** Plan pseudocode used `crypto.randomUUID()` locally; replaced with the `run_id` from POST /generate JSON body so client state matches server `_RUN_QUEUES` key. Two `run.start()` calls now: optimistic `'pending'` before fetch, then re-start with the server run_id once the response lands.
- **EventSource onerror silently degrades.** Pitfall 9 (refresh-mid-run): if a fresh client mounts mid-run and subscribes, the server-side single-flight `_RUN_QUEUES` may have already cleared after a successful done, returning 404 on /stream. We close the connection without transitioning to error state — the /status query reconciles real outcome.
- **FakeEventSource defined inline in the test file.** jsdom does not implement EventSource. The polyfill is scoped to the integration test file; it exposes synchronous `emit()` / `emitRaw()` / `triggerError()` methods so the test can drive SSE flow deterministically without timers.
- **Done event invalidates BOTH `['v3-status', id]` AND `['projects', id]`.** D-19 cache-bust requires `project.updated_at` to refetch so CanvasViewer's `cacheVersion` query key changes; without the second invalidation, the canvas reads stale post-regen data.
- **Regenerar label during generating runs.** First implementation pass kept "Gerar Mapa" while running (only flipping on hasArtifacts/generated). UI-SPEC §State Machine rows say the CTA stays "Regenerar" + disabled during runs. Adjusted; test asserts disabled `Regenerar` when state=generating. (1 fix-on-RED iteration on Task 1.)

## Deviations from Plan

**Total deviations:** 4 — all addressed inline; advisor-confirmed where applicable.

### Auto-fixed Issues

**1. [Rule 1 — Bug] Plan pseudocode for Exportar ZIP was incorrect**
- **Found during:** Task 2 implementation.
- **Issue:** Plan said `window.location.href = '/api/projects/{id}/export'`. Reality: that endpoint is `POST` returning `{download_url, zip_filename}` per `client.ts:280`. Direct navigation would hit a 405 Method Not Allowed.
- **Fix:** Use existing `useExport()` mutation hook. `handleExport = () => exportZip.mutate()`. Hook already handles the anchor.click() download flow.
- **Files modified:** `frontend/src/pages/ProjectDetail.tsx`.
- **Committed in:** `82f95e1` (Task 2).

**2. [Rule 3 — Blocking] jsdom lacks EventSource**
- **Found during:** Task 2 first test run.
- **Issue:** `new EventSource(url)` throws ReferenceError in jsdom; the integration test cannot exercise the SSE bridge without a polyfill.
- **Fix:** In-memory `FakeEventSource` class defined inline in the test file; installs as `globalThis.EventSource` in `beforeEach`. Exposes synchronous `emit()` / `emitRaw()` / `triggerError()` for deterministic test control.
- **Files modified:** `frontend/src/components/workspace/__tests__/ProjectDetail.workspace.test.tsx`.
- **Committed in:** `82f95e1` (Task 2).

**3. [Rule 1 — Bug] First-pass Regenerar label logic missed mid-run case**
- **Found during:** Task 1 first test run (RED → GREEN iteration).
- **Issue:** Initial WorkspaceToolbar logic: `ctaLabel = hasArtifacts || runState === 'generated' ? 'Regenerar' : 'Gerar Mapa'`. Test asserts `Regenerar` when `runState === 'generating'` (no hasArtifacts prop). Plan's `<behavior>` block makes this contract explicit: "renders disabled Regenerar button when runState='generating'".
- **Fix:** Add `|| isRunning` to the label predicate. Single-line change; test green.
- **Files modified:** `frontend/src/components/workspace/WorkspaceToolbar.tsx`.
- **Committed in:** `460c507` (Task 1).

**4. [Rule 1 — Bug] 11-stage test asserted against 22 rows due to dual RunLogPanel mount**
- **Found during:** Task 3 first test run.
- **Issue:** Test opened the floating log panel via badge click AND was running while body was `GeneratingCanvasState` (which itself nests a RunLogPanel). Two RunLogPanels mounted → 22 `stage-row-done` rows after 11 stage_done events. Assertion expected 11.
- **Fix:** Removed the badge-click step from the 11-stage test. Body is `GeneratingCanvasState` while `state==='generating'`, which already renders the inline RunLogPanel — single instance. Badge expansion is covered by a separate test that asserts the toggle behavior in the empty state (where no inline panel exists).
- **Files modified:** `frontend/src/components/workspace/__tests__/ProjectDetail.workspace.test.tsx`.
- **Committed in:** `3fe5b7f` (Task 3).

## Authentication Gates

None. Phase 03 is local-only by D-20.

## Issues Encountered

None outside the 4 deviations above.

## User Setup Required

None.

## Next Phase Readiness

- **Plan 03-05 ready (canvas surface refactor).** ProjectDetail body conditional already routes to `<CanvasViewer projectId cacheVersion>` when `status.has_artifacts['territory_metadata.json']` is true. Plan 05 can rip the v1 imports out of `CanvasViewer.tsx` (useEditorStore, useResearchStore, SplitTool, etc.) without touching ProjectDetail.tsx.
- **Plan 03-06 / 03-07 (Wave 3 deletion) cleared.** ProjectDetail.tsx is the last file that imported the v1 stepper / research / edit modules; deletion is now mechanical.
- **Phase 03 SC-3 (no console errors) close to satisfaction.** Old stepper invisible + new component graph references only surviving modules. Final verification will be the Plan 08 Playwright UAT.

## Verification

- `cd frontend && npm run test -- --run src/components/workspace/__tests__/` → **30/30 green** (5+6+3+16)
- `cd frontend && npm run test -- --run` (full suite) → **268/268 green across 43 files** (was 262 after Plan 03; +6 net new specs from Tasks 1+3 minus the 4 absorbed by integration)
- `wc -l frontend/src/pages/ProjectDetail.tsx` → **160** (< 280 budget; vs 697 baseline = 77% reduction)
- `grep -nE "useEditorStore|usePipelineStore|useResearchStore|useValidationStore|useProjectStore|EditToolbar|SplitTool|VertexHandlesLayer|TerritoryEditor|TerrainBadgesLayer|SaveStatusIndicator|ResearchDialog|AssignmentEditor|CodexViewer|Stepper|StepCard|ProviderEffortPicker|TerrainDataSection|BaronyGranularitySlider" frontend/src/pages/ProjectDetail.tsx` → **zero hits**
- `grep -nE "EventSource|/api/v3/projects/.*/generate" frontend/src/pages/ProjectDetail.tsx frontend/src/api/useGenerateStream.ts` → **6 hits** (SSE wiring + URL templates present)
- `grep -E "Gerar Mapa|Regenerar|Exportar ZIP|Projetos|Tentar novamente" frontend/src/components/workspace/*.tsx | wc -l` → **9** (PT-BR copy locked)
- `grep -E "from 'lucide|from '@?floating|from 'react-tooltip|from 'tailwind" frontend/src/components/workspace/*.tsx` → **zero** (no new deps)
- `grep -c "PIPELINE_STAGES" frontend/src/components/workspace/RunLogPanel.tsx` → **2** (import + use)
- `grep -nE 'data-testid' frontend/src/components/workspace/RunLogPanel.tsx` → **2 hits** (testId variable + JSX prop)
- `grep -n "Exportar ZIP" frontend/src/components/workspace/WorkspaceToolbar.tsx` → **2 hits** (button label + comment)

## Self-Check: PASSED

- FOUND: frontend/src/components/workspace/WorkspaceToolbar.tsx
- FOUND: frontend/src/components/workspace/GenerateStatusBadge.tsx
- FOUND: frontend/src/components/workspace/RunLogPanel.tsx
- FOUND: frontend/src/components/workspace/EmptyCanvasState.tsx
- FOUND: frontend/src/components/workspace/GeneratingCanvasState.tsx
- FOUND: frontend/src/components/workspace/ErrorCanvasCallout.tsx
- FOUND: frontend/src/components/workspace/__tests__/WorkspaceToolbar.test.tsx (5 specs green)
- FOUND: frontend/src/components/workspace/__tests__/GenerateStatusBadge.test.tsx (6 specs green)
- FOUND: frontend/src/components/workspace/__tests__/RunLogPanel.test.tsx (3 specs green)
- FOUND: frontend/src/components/workspace/__tests__/ProjectDetail.workspace.test.tsx (16 specs green)
- FOUND: frontend/src/api/useGenerateStream.ts
- FOUND: frontend/src/pages/ProjectDetail.tsx (160 LOC)
- FOUND: frontend/src/api/client.ts (useStatusManifest exported)
- FOUND commit: 460c507 (Task 1 — feat workspace chrome)
- FOUND commit: 82f95e1 (Task 2 — feat ProjectDetail rewrite)
- FOUND commit: 3fe5b7f (Task 3 — test state machine)
- VITEST: full suite 268/268 green; no regressions

---
*Phase: 03-read-only-canvas-redesign*
*Completed: 2026-05-09*
