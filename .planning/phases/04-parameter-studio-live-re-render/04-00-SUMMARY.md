---
phase: "04"
plan: "00"
subsystem: test-scaffolding
tags: [wave-0, stubs, pytest, vitest, playwright, tdd]
dependency_graph:
  requires: []
  provides:
    - backend/tests/unit/test_cleanup_split.py
    - backend/tests/unit/test_dag_tokens.py
    - backend/tests/unit/test_stage_cache.py
    - backend/tests/integration/test_render_endpoint.py
    - backend/tests/integration/test_render_cancel.py
    - backend/tests/parity/test_iberia_868_render_default.py
    - frontend/src/components/canvas/__tests__/ParameterSidebar.test.tsx
    - frontend/src/components/canvas/__tests__/SliderCard.test.tsx
    - frontend/src/components/canvas/__tests__/StageViewToggle.test.tsx
    - frontend/src/components/canvas/__tests__/CanvasViewer.clearCache.test.tsx
    - frontend/src/components/canvas/__tests__/BaronyLabels.test.tsx
    - frontend/src/api/__tests__/useRenderStream.test.ts
    - frontend/src/stores/__tests__/usePipelineParams.test.ts
    - frontend/src/components/workspace/__tests__/WorkspaceToolbar.cancel.test.tsx
    - frontend/tests/e2e/parameter-studio-sc3.spec.ts
    - frontend/tests/e2e/parameter-studio-cancel.spec.ts
  affects: []
tech_stack:
  added: []
  patterns:
    - "pytest.skip() stub pattern for Wave 0 test scaffolding"
    - "it.skip() stub pattern for vitest Wave 0"
    - "test.skip(true, ...) Playwright stub pattern"
key_files:
  created:
    - backend/tests/unit/test_cleanup_split.py
    - backend/tests/unit/test_dag_tokens.py
    - backend/tests/unit/test_stage_cache.py
    - backend/tests/integration/test_render_endpoint.py
    - backend/tests/integration/test_render_cancel.py
    - backend/tests/parity/test_iberia_868_render_default.py
    - frontend/src/components/canvas/__tests__/ParameterSidebar.test.tsx
    - frontend/src/components/canvas/__tests__/SliderCard.test.tsx
    - frontend/src/components/canvas/__tests__/StageViewToggle.test.tsx
    - frontend/src/components/canvas/__tests__/CanvasViewer.clearCache.test.tsx
    - frontend/src/components/canvas/__tests__/BaronyLabels.test.tsx
    - frontend/src/api/__tests__/useRenderStream.test.ts
    - frontend/src/stores/__tests__/usePipelineParams.test.ts
    - frontend/src/components/workspace/__tests__/WorkspaceToolbar.cancel.test.tsx
    - frontend/tests/e2e/parameter-studio-sc3.spec.ts
    - frontend/tests/e2e/parameter-studio-cancel.spec.ts
  modified:
    - pyproject.toml
    - frontend/playwright.config.ts
decisions:
  - "Register pytest.mark.unit in pyproject.toml (was missing; integration/parity were registered)"
  - "Expand Playwright testDir from ./tests/uat/playwright to ./tests to discover both uat/ and e2e/ directories (Rule 3 deviation)"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-10"
  tasks_completed: 3
  files_created: 16
  files_modified: 2
---

# Phase 04 Plan 00: Wave 0 Stub Bootstrap Summary

**One-liner:** 16 Wave 0 stub files (14 test stubs + 2 Playwright e2e stubs) scaffolding the full Phase 04 test suite — all skip cleanly with exit 0, enabling `<verify>` commands in Plans 04-01..04-06 to reference real file paths.

## What Was Built

### Task 1: 6 Backend Pytest Stubs

| File | Marker | Test Count | Covers |
|------|--------|------------|--------|
| `backend/tests/unit/test_cleanup_split.py` | `unit` | 6 | D-01 split functions, D-17 default-cfg parity |
| `backend/tests/unit/test_dag_tokens.py` | `unit` | 4 | D-02 token determinism + isolation |
| `backend/tests/unit/test_stage_cache.py` | `unit` | 4 | D-03 cache lifecycle |
| `backend/tests/integration/test_render_endpoint.py` | `integration` | 8 | D-04 endpoint + 409 single-flight, ASVS V5 |
| `backend/tests/integration/test_render_cancel.py` | `integration` | 4 | D-13/D-14 cancel mechanics |
| `backend/tests/parity/test_iberia_868_render_default.py` | `parity` | 1 | D-17 incremental-vs-full byte-equal |

Total backend stubs: **27 functions**, all `pytest.skip("Wave 0 stub — Plan 04-NN implements")`.

### Task 2: 8 Frontend Vitest Stubs

| File | Test Count | Covers |
|------|------------|--------|
| `ParameterSidebar.test.tsx` | 4 | D-05/D-06 sidebar layout |
| `SliderCard.test.tsx` | 5 | D-08 slider+input+reset |
| `StageViewToggle.test.tsx` | 4 | D-10/D-11 radio group |
| `CanvasViewer.clearCache.test.tsx` | 3 | SC-4 clearCache discipline |
| `BaronyLabels.test.tsx` | 5 | D-12 barony name labels |
| `useRenderStream.test.ts` | 5 | SSE consumer + stage_cancel handling |
| `usePipelineParams.test.ts` | 4 | Slider debounce + latest-wins |
| `WorkspaceToolbar.cancel.test.tsx` | 4 | Status-badge → cancel-button switch |

Total frontend stubs: **34 it.skip calls** (exactly matching acceptance criterion). vitest: 34 skipped, 0 failures.

### Task 3: 2 Playwright E2E Stubs

| File | Test Count | Covers |
|------|------------|--------|
| `parameter-studio-sc3.spec.ts` | 1 | SC-3: sigma 3.0→4.5 timing <500ms |
| `parameter-studio-cancel.spec.ts` | 1 | SC-4: cancel restores prior cfg <50ms |

Both stubs: `test.skip(true, "Wave 0 stub — Plan 04-06 implements")`. Playwright: 2 skipped, exit 0.

## Verification Results

- `pytest --collect-only -q` (6 backend stubs): 27 tests collected — exact names match 04-VALIDATION.md
- `python -m pytest -m "unit or integration or parity" -q`: 14 passed, 27 skipped, 0 failures
- `npx vitest run` (full frontend suite): 156 passed, 34 skipped, 0 failures
- `npx playwright test tests/e2e/... --reporter=list`: 2 skipped, exit 0
- `npx playwright test --list`: lists both new specs AND existing `03-canvas-workspace.spec.ts`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Config] Registered pytest.mark.unit in pyproject.toml**
- **Found during:** Task 1, pre-flight check
- **Issue:** `pytest.mark.unit` was not registered in `[tool.pytest.ini_options].markers`. The existing markers list had `slow`, `parity`, `integration`, `uat` but not `unit`. Without registration, pytest emits PytestUnknownMarkWarning on every stub run and `--strict-markers` (if ever enabled) would fail.
- **Fix:** Added `"unit: fast isolated unit tests (no DB, no HTTP, no filesystem)"` to the markers list.
- **Files modified:** `pyproject.toml`
- **Commit:** c8b778d

**2. [Rule 3 - Blocking Issue] Expanded Playwright testDir to discover tests/e2e/**
- **Found during:** Task 3, pre-flight check
- **Issue:** `playwright.config.ts` had `testDir: './tests/uat/playwright'`. The plan requires stubs at `frontend/tests/e2e/`, which is outside the configured testDir. Playwright would not discover the new specs without this change.
- **Fix:** Changed `testDir` from `'./tests/uat/playwright'` to `'./tests'`. The existing `testMatch: /.*\.spec\.ts$/` continues to filter correctly. The existing `03-canvas-workspace.spec.ts` spec is still discovered under `tests/uat/playwright/`.
- **Files modified:** `frontend/playwright.config.ts`
- **Commit:** dda01c0

## Commits

| Hash | Message | Files |
|------|---------|-------|
| c8b778d | chore(04-00): add 6 backend Wave 0 stub test files | pyproject.toml + 6 backend stubs |
| 53527e4 | chore(04-00): add 8 frontend Wave 0 stub test files | 8 frontend stubs + new api/__tests__/ dir |
| dda01c0 | chore(04-00): add 2 Playwright Wave 0 stub specs | playwright.config.ts + 2 e2e stubs |

## Known Stubs

All 16 files created in this plan are intentional stubs. They are not data stubs that block a plan's goal — they are the plan's goal. Each stub will be wired by its designated implementation plan (04-01..04-06). No stub affects UI rendering or pipeline execution.

## Threat Flags

None. Wave 0 adds test files only — no new HTTP endpoints, no auth surfaces, no user-input parsing.

## Self-Check: PASSED
