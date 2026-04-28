---
phase: quick-260428-lyh
plan: 01
subsystem: frontend/pipeline-ui
tags: [pipeline, stepper, zustand, radix-ui, tdd]
dependency_graph:
  requires: [260428-lka]
  provides: [pipeline-stepper-ui, usePipelineStore]
  affects: [ProjectDetail, CodexViewer, AssignmentEditor, BaronyGranularitySlider]
tech_stack:
  added: []
  patterns: [zustand-plain-create, radix-card-layout, step-switch-render]
key_files:
  created:
    - frontend/src/stores/usePipelineStore.ts
    - frontend/src/stores/__tests__/usePipelineStore.test.ts
    - frontend/src/components/pipeline/Stepper.tsx
    - frontend/src/components/pipeline/Stepper.test.tsx
    - frontend/src/components/pipeline/StepCard.tsx
    - frontend/src/components/pipeline/StepCard.test.tsx
    - frontend/src/components/pipeline/ProviderEffortPicker.tsx
    - frontend/src/components/pipeline/ProviderEffortPicker.test.tsx
  modified:
    - frontend/src/pages/ProjectDetail.tsx
decisions:
  - "usePipelineStore uses plain create() — no zundo/temporal; pipeline nav state must NOT enter undo/redo history"
  - "renderStepContent() captures proj = project const to work around TS control-flow narrowing in nested function bodies"
  - "manualResult cast via as unknown as MapResearchResult (consistent with existing codebase pattern in AssignmentEditor)"
  - "Step 5 has dual provider picker (ProviderEffortPicker + CodexViewer internal ProviderSelector) — UX wart, not fixed (rewriting CodexViewer out of scope)"
metrics:
  duration: ~35min
  completed: 2026-04-28
  tasks: 3
  files_changed: 9
---

# Quick Task 260428-lyh: Etapa 11 — Pipeline UI completa (Stepper + StepCards + usePipelineStore)

**One-liner:** Zustand pipeline store (5 steps, no undo) + Stepper (data-status nodes) + StepCard (Radix Card layout) + ProviderEffortPicker (ProviderSelector + effort segmented control), wired into ProjectDetail replacing the legacy Tabs.Root pipeline block.

## Files Created (5 src + 4 test)

| File | Purpose |
|------|---------|
| `stores/usePipelineStore.ts` | Zustand store: currentStep (1-5), per-step status/provider/effort, granularity, reset |
| `stores/__tests__/usePipelineStore.test.ts` | 6 tests: defaults, setCurrentStep, setStepStatus, setStepProvider, setBaroniesGranularity, reset |
| `components/pipeline/Stepper.tsx` | 5-node flex Stepper (OSM/Baronies/Pesquisa/Mapa/Codex) with data-status + aria-current + onStepClick |
| `components/pipeline/Stepper.test.tsx` | 6 tests: labels, data-status for done/active/error, onStepClick, aria-current |
| `components/pipeline/StepCard.tsx` | Radix Card wrapper: title + optional description + children + optional footer |
| `components/pipeline/StepCard.test.tsx` | 6 tests: title, description, children, footer present/absent |
| `components/pipeline/ProviderEffortPicker.tsx` | Composes ProviderSelector + 3 effort Buttons (Baixo/Médio/Alto) with data-active |
| `components/pipeline/ProviderEffortPicker.test.tsx` | 4 tests: providers load, effort buttons + active marking, effort change, provider change |

## Files Modified

| File | Change |
|------|--------|
| `pages/ProjectDetail.tsx` | Replaced `<Card><Tabs.Root>` pipeline/territory block with `<Stepper>` + `renderStepContent()` switch; added usePipelineStore, new imports, useEffect hooks for osm/map status sync |

## Test Count Delta

| Metric | Value |
|--------|-------|
| Tests before | 200 |
| Tests added | 22 (6 store + 6 Stepper + 6 StepCard + 4 ProviderEffortPicker) |
| Tests after | 222 |
| All passing | Yes |

## Commits (3)

| Hash | Message |
|------|---------|
| cb50958 | feat(quick-260428-lyh-01): usePipelineStore + Stepper component (5-node visual pipeline) |
| 8ae6c88 | feat(quick-260428-lyh-02): StepCard + ProviderEffortPicker (composes ProviderSelector + effort segmented control) |
| 23078f6 | feat(quick-260428-lyh-03): refactor ProjectDetail to Stepper + StepCard + usePipelineStore |

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Minor Adjustments (not deviations)

**1. TS control-flow narrowing in nested function body**
- `renderStepContent()` is defined after the `if (!project) return null` guard but TypeScript doesn't narrow through nested function bodies.
- Fix: added `const proj = project` immediately after the guard; used `proj` inside `renderStepContent`.
- No behavior change.

**2. `manualResult` type cast**
- `useResearchStore` holds `ResearchResult | null`; `AssignmentEditor` expects `MapResearchResult`.
- Fix: `manualResult as unknown as MapResearchResult` — consistent with existing codebase pattern (`setManualResult(result as unknown as ResearchResult)` in AssignmentEditor).

**3. ProviderEffortPicker test: radio click strategy**
- Initial test used `findByDisplayValue('llamacpp')` — Radix RadioGroup renders a hidden native input not found by display value.
- Fix: used `getAllByRole('radio')[1]` (second radio = llamacpp) — a standard ARIA pattern.

## Known Stubs

| Stub | File | Line | Reason |
|------|------|------|--------|
| Gerar Baronies button | ProjectDetail.tsx | Step 2 footer | Backend /baronies endpoint wiring is out of scope for etapa-11; logs console.warn + advances step |

## Known UX Warts

**Step 5 dual ProviderSelector:** Step 5 renders both `<ProviderEffortPicker>` (for store binding) AND `<CodexViewer>` which contains its own internal `<ProviderSelector>`. This creates two provider pickers in step 5. Fixing this would require modifying CodexViewer to accept an external provider/effort (controlled component), which is a separate refactor. Documented here for follow-up.

## Self-Check: PASSED

- All 8 new files found on disk: PASSED
- All 3 commits found in git log: PASSED
- `npm run build` clean (no TS errors): PASSED
- `npm test -- --run` 222/222 passing: PASSED
- No backend files modified: PASSED (only `frontend/**` touched)
