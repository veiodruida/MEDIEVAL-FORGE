---
phase: 04
slug: parameter-studio-live-re-render
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-10
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend)** | pytest 8.x with markers `unit`, `parity`, `integration` |
| **Framework (frontend)** | vitest 3.x + React Testing Library + Playwright |
| **Config file (backend)** | `pyproject.toml` ([tool.pytest.ini_options]) |
| **Config file (frontend)** | `frontend/vitest.config.ts`, `frontend/playwright.config.ts` |
| **Quick run command (backend)** | `pytest -m "unit and not parity" -x` |
| **Quick run command (frontend)** | `cd frontend && npm run test:unit -- --run` |
| **Full suite command** | `pytest && cd frontend && npm run test && npm run test:e2e` |
| **Parity command** | `pytest -m parity` (non-skippable, byte-equal vs Reconquista) |
| **Estimated runtime (quick)** | ~30 seconds (backend unit) + ~20 seconds (frontend unit) |
| **Estimated runtime (full)** | ~5 minutes including parity + Playwright |

---

## Sampling Rate

- **After every task commit:** Run quick run command (backend or frontend depending on `files_modified`)
- **After every plan wave:** Run full suite for the modified surface (backend or frontend)
- **Before `/gsd-verify-work`:** Full suite + parity green; Playwright SC-3 timing test green
- **Max feedback latency:** 60 seconds for unit tier; 5 minutes for full

---

## Per-Task Verification Map

> Filled by planner during plan creation. Each plan task receives a row mapping it to a concrete test command.

| Task ID | Plan | Wave | Decision Ref | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|--------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | D-01 | — | N/A | unit | `pytest tests/unit/test_cleanup_split.py -x` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | D-02, D-03 | — | N/A | unit | `pytest tests/unit/test_dag_tokens.py tests/unit/test_stage_cache.py -x` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 1 | D-17 | — | N/A | parity | `pytest tests/parity/test_iberia_868.py -x` | ✅ | ⬜ pending |
| 04-02-01 | 02 | 2 | D-04 | T-04-01 (single-flight DoS) | 409 on concurrent /render or /generate | integration | `pytest tests/integration/test_render_endpoint.py -x` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 2 | D-13, D-14 | — | StageCancelled propagates as `stage_cancel` SSE event | integration | `pytest tests/integration/test_render_cancel.py -x` | ❌ W0 | ⬜ pending |
| 04-02-03 | 02 | 2 | D-17, D-18 | — | N/A | parity | `pytest tests/parity/test_iberia_868_render_default.py -x` | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 3 | D-05..D-08 | — | N/A | unit | `cd frontend && npm run test:unit -- ParameterSidebar SliderCard --run` | ❌ W0 | ⬜ pending |
| 04-03-02 | 03 | 3 | D-04, D-07 | — | N/A | unit | `cd frontend && npm run test:unit -- useRenderStream usePipelineParams --run` | ❌ W0 | ⬜ pending |
| 04-03-03 | 03 | 3 | D-09..D-11 | — | N/A | unit | `cd frontend && npm run test:unit -- StageViewToggle --run` | ❌ W0 | ⬜ pending |
| 04-03-04 | 03 | 3 | D-13, D-16 | — | useRenderStore -> useRunStore migration absorbed (per checker B1); Cancel button visible only during `state ∈ {generating, rendering}` | unit | `cd frontend && npm run test:unit -- useRunStore WorkspaceToolbar.cancel --run` | ❌ W0 | ⬜ pending |
| 04-04-01 | 04 | 3 | D-09, D-10, D-11 | — | useCanvasArtifacts queries re-key on stageView (no cross-stage data leak across radio toggles) | unit | `cd frontend && npm run test:unit -- useCanvasArtifacts --run` | ❌ W0 | ⬜ pending |
| 04-04-02 | 04 | 3 | SC-4 (CLAUDE.md non-negotiable rule) | — | Konva.clearCache called on every cacheVersion change after hydration completes (Pitfall 6) | unit | `cd frontend && npm run test:unit -- CanvasViewer.clearCache --run` | ❌ W0 | ⬜ pending |
| 04-05-01 | 05 | 3 | D-12 | — | N/A | unit | `cd frontend && npm run test:unit -- BaronyLabels --run` | ❌ W0 | ⬜ pending |
| 04-06-01 | 06 | 4 | SC-3 | — | σ 3.0→4.5 produces visible canvas pixel diff in <500 ms | uat | `cd frontend && npm run test:e2e -- parameter-studio-sc3.spec.ts` | ❌ W0 | ⬜ pending |
| 04-06-02 | 06 | 4 | SC-4 | — | Cancel restores prior cfg + canvas swap <50 ms | uat | `cd frontend && npm run test:e2e -- parameter-studio-cancel.spec.ts` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky · W0 = file created in Wave 0*

> Planner: confirm task IDs match the actual plans created. Add rows for any plans not yet listed (e.g., barony labels split into separate plan, or extra UAT scenarios).

---

## Nyquist Anti-Symmetry Samples

> Smallest signals that, if violated, break a Phase 04 contract. Each sample maps to a concrete test that catches the violation.

| # | Anti-Symmetry Sample | Contract Broken | Catching Test |
|---|----------------------|-----------------|---------------|
| 1 | Slider on `smooth_sigma` invalidates `apply_median`'s token | D-02 (reads-scoped tokens), SC-3 (no full re-run) | `tests/unit/test_dag_tokens.py::test_sigma_change_does_not_invalidate_median` |
| 2 | `apply_median(raw, cfg)` mutates `raw` in-place | D-03 (cache holds prior), D-17 (parity bit-equal) | `tests/unit/test_cleanup_split.py::test_apply_median_does_not_mutate_input` |
| 3 | `_STAGE_CACHE` not cleared on `/generate` | D-03 (fresh run resets) | `tests/integration/test_render_endpoint.py::test_generate_clears_cache` |
| 4 | Concurrent `/render` + `/generate` for same `project_id` accepted | D-04 (single-flight) | `tests/integration/test_render_endpoint.py::test_render_409_when_generate_alive` |
| 5 | `cfg.stop_event` not checked between median passes (8 passes [11,11,9,9,7,7,5,5]) | D-14 (cancel <2 s worst-case) | `tests/integration/test_render_cancel.py::test_cancel_during_median_returns_within_2s` |
| 6 | Cancel without prior_array (first render) leaves canvas in indeterminate state | D-13 (prior swap) | `tests/integration/test_render_cancel.py::test_cancel_on_first_render_falls_back_to_generate_baseline` |
| 7 | `Konva.clearCache()` skipped on `cacheVersion` change | CLAUDE.md non-negotiable rule, SC-4 | `frontend/src/components/canvas/__tests__/CanvasViewer.clearCache.test.tsx::test_clearCache_called_on_token_change` |
| 8 | `version_token` non-deterministic across runs (e.g., dict iteration order) | D-02 (stable token), D-17 (parity) | `tests/unit/test_dag_tokens.py::test_token_stable_across_runs` |
| 9 | Slider drag fires `/render` without 250 ms debounce (latest-wins broken) | D-07 | `frontend/src/api/__tests__/usePipelineParams.test.ts::test_slider_change_debounces_250ms` |
| 10 | `stage_view = 'voronoi-raw'` re-runs the pipeline (visualization-only contract) | D-09 | `tests/integration/test_render_endpoint.py::test_stage_view_change_does_not_recompute` |
| 11 | σ at default cfg via `/render` produces non-byte-equal vs `/generate` | D-17 (parity bit-equal at default) | `tests/parity/test_iberia_868_render_default.py::test_render_at_default_cfg_matches_generate_byte_equal` |
| 12 | Project's persisted cfg mutated by `/render` call | D-18 (per-render copy) | `tests/integration/test_render_endpoint.py::test_render_does_not_mutate_persisted_cfg` |

---

## Wave 0 Requirements

- [ ] `tests/unit/test_cleanup_split.py` — stubs for D-01 split functions (4 functions × ~3 cases each)
- [ ] `tests/unit/test_dag_tokens.py` — stubs for D-02 token derivation (stability, scoping, edge cases)
- [ ] `tests/unit/test_stage_cache.py` — stubs for D-03 cache lifecycle (insert, prior-swap, clear-on-generate)
- [ ] `tests/integration/test_render_endpoint.py` — stubs for D-04 endpoint (202+stream, 409 single-flight, stage_view)
- [ ] `tests/integration/test_render_cancel.py` — stubs for D-13/D-14 cancel (cooperative stop, prior swap)
- [ ] `tests/parity/test_iberia_868_render_default.py` — stub asserting byte-equal default-cfg output via `/render` matches `/generate`
- [ ] `frontend/src/components/canvas/__tests__/ParameterSidebar.test.tsx` — stubs for D-05/D-06 sidebar layout
- [ ] `frontend/src/components/canvas/__tests__/SliderCard.test.tsx` — stubs for D-08 slider+input+reset
- [ ] `frontend/src/components/canvas/__tests__/StageViewToggle.test.tsx` — stubs for D-10/D-11 radio group
- [ ] `frontend/src/components/canvas/__tests__/CanvasViewer.clearCache.test.tsx` — stubs for SC-4 (clearCache discipline)
- [ ] `frontend/src/components/canvas/__tests__/BaronyLabels.test.tsx` — stubs for D-12 barony name labels
- [ ] `frontend/src/api/__tests__/useRenderStream.test.ts` — stubs for SSE consumer + `stage_cancel` event
- [ ] `frontend/src/stores/__tests__/usePipelineParams.test.ts` — stubs for slider state + debounce + latest-wins
- [ ] `frontend/src/components/workspace/__tests__/WorkspaceToolbar.cancel.test.tsx` — stubs for status-badge → cancel-button switch
- [ ] `frontend/tests/e2e/parameter-studio-sc3.spec.ts` — Playwright stub for σ 3.0→4.5 timing
- [ ] `frontend/tests/e2e/parameter-studio-cancel.spec.ts` — Playwright stub for cancel UI flow

> Frameworks already installed (pytest, vitest, Playwright). Wave 0 only needs stub files committed before any implementation task. Planner: emit a `wave: 0` plan that creates these stubs as the first commit set.

---

## Manual-Only Verifications

| Behavior | Decision Ref | Why Manual | Test Instructions |
|----------|--------------|------------|-------------------|
| Slider drag feels live (subjective <500 ms perception, not just measured) | SC-3 | Perception is human; automated test asserts pixel diff but not feel | Open browser, drag σ slider 3.0→4.5 over 1 second, confirm canvas keeps up without lag |
| Stage-view radios show distinguishable rasters (visual sanity) | D-10 | Colormap correctness is visual | Switch radios, confirm each view looks plausibly different from `render-final` |
| Barony labels readable at default zoom | D-12 | Typography legibility is visual | Toggle Baronies layer on, confirm labels readable across all 150 baronies |
| Cancel button color/contrast (red) accessible | D-16 | Color accessibility is design judgment | Verify cancel button passes WCAG AA contrast vs panel bg |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags (Playwright + vitest run with `--run`/non-watch)
- [ ] Feedback latency < 60 s for unit tier
- [ ] All 12 Nyquist anti-symmetry samples mapped to concrete tests
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
