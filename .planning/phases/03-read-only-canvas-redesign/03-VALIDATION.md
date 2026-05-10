---
phase: 03
slug: read-only-canvas-redesign
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-09
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Filled by gsd-planner during planning. Wave 0 tasks must close all `❌ W0` rows.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend)** | pytest 7.x (markers: `unit`, `parity`, `integration`) |
| **Framework (frontend)** | vitest 2.x + Playwright (UAT) |
| **Config file (backend)** | `backend/pyproject.toml` |
| **Config file (frontend)** | `frontend/vitest.config.ts` + `frontend/playwright.config.ts` |
| **Quick run command (backend)** | `cd backend && pytest -m "unit and not parity" -x` |
| **Quick run command (frontend)** | `cd frontend && npm run test -- --run` |
| **Full suite command (backend)** | `cd backend && pytest` |
| **Full suite command (frontend)** | `cd frontend && npm run test -- --run && npx playwright test` |
| **Estimated runtime** | backend quick ~5s, full ~25s; frontend quick ~10s, Playwright ~30s |

---

## Sampling Rate

- **After every task commit:** Run quick command for the modified surface (backend or frontend)
- **After every plan wave:** Run full suite (both surfaces)
- **Before `/gsd-verify-work`:** Full suite + Playwright UAT must be green; Phase 01 parity test still 10/10
- **Max feedback latency:** 30 seconds (quick) / 60 seconds (full)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-T1 | 01 | 0 | SC-4 | — | atomic geojson write helper relocated; legacy callsites still resolve | unit | `cd backend && pytest tests/unit/test_paths_write_geojson_atomic.py tests/parity/test_iberia_868.py -x` | yes (Plan 01) | ⬜ pending |
| 01-T2 | 01 | 0 | SC-4 | — | cfg.on_stage callback slot; default None preserves parity | unit + parity | `cd backend && pytest tests/unit/test_run_pipeline_on_stage.py tests/parity/test_iberia_868.py -x` | yes | ⬜ pending |
| 01-T3 | 01 | 0 | SC-1, SC-4 | — | 4 canvas-sidecar files emitted from run_pipeline; 10-file parity preserved | parity | `cd backend && pytest tests/parity/test_iberia_868.py -x` | yes | ⬜ pending |
| 02-T1 | 02 | 1 | SC-1, SC-4 | T-03-01, T-03-05 | UUID validation + allowlist + path containment on /artifacts; status manifest reads 14-file allowlist | unit | `cd backend && pytest tests/unit/test_v3_artifacts.py tests/unit/test_v3_status.py -x` | yes | ⬜ pending |
| 02-T2 | 02 | 1 | SC-1, SC-4 | T-03-02, T-03-03 | per-project queue keying (T-03-02); 409 single-flight gate (T-03-03); error event emits class name only (T-02-04-05 mirror) | unit | `cd backend && pytest tests/unit/test_v3_generate.py -x` | yes | ⬜ pending |
| 02-T3 | 02 | 1 | SC-1, SC-4 | — | 3 v3 routers registered without disturbing Phase 02 ingest | unit | `cd backend && pytest tests/unit/test_v3_routers_registered.py -x` | yes | ⬜ pending |
| 03-T1 | 03 | 1 | SC-2 | T-03-FE-PLUMB-01 | LOG_CAP=500 enforced on appendLog; finishStage idempotent | unit | `cd frontend && npm run test -- --run src/stores/__tests__/useRunStore.test.ts` | yes | ⬜ pending |
| 03-T2 | 03 | 1 | SC-2 | — | selection state shape promoted to multi-id; 'terrain' LayerName + overlay fields removed | unit | `cd frontend && npm run test -- --run src/stores/uiStore.test.ts` | yes | ⬜ pending |
| 03-T3 | 03 | 1 | SC-1, SC-4 | — | URL prefix swap to /api/v3/projects/{id}/artifacts/*; query keys + select transforms unchanged | unit | `cd frontend && npm run test -- --run src/hooks/useCanvasArtifacts.cacheVersion.test.ts src/components/canvas/__tests__/CanvasViewer.test.tsx src/components/canvas/__tests__/CanvasViewer.hydrate.test.tsx src/components/canvas/__tests__/CanvasViewer.resize.test.tsx src/components/canvas/__tests__/CanvasViewer.panOnSelect.test.tsx` | yes | ⬜ pending |
| 04-T1 | 04 | 2 | SC-1, SC-2 | — | 6 chrome components built per UI-SPEC; PT-BR copy verbatim; no new deps | unit | `cd frontend && npm run test -- --run src/components/workspace/__tests__/` | yes | ⬜ pending |
| 04-T2 | 04 | 2 | SC-1, SC-3 | T-03-FE-WORKSPACE-01, T-03-FE-WORKSPACE-02 | ProjectDetail < 280 LOC; SSE→useRunStore wiring; zero deleted-module imports; 11-stage flow | unit | `cd frontend && npm run test -- --run src/components/workspace/__tests__/ProjectDetail.workspace.test.tsx` | yes | ⬜ pending |
| 04-T3 | 04 | 2 | SC-1, SC-2 | — | full SSE happy path renders 11 ✓ marks; cacheVersion invalidation on updated_at change; selection survives state transitions | unit | `cd frontend && npm run test -- --run src/components/workspace/__tests__/ProjectDetail.workspace.test.tsx` | yes | ⬜ pending |
| 05-T1 | 05 | 2 | SC-1, SC-2 | T-03-FE-CANVAS-01 | CanvasViewer ≤420 LOC + zero deleted-module imports; multi-id InteractionLayer; shift+click TerritoryLayer; canonical empty-stage deselect | unit | `cd frontend && npm run test -- --run src/components/canvas/__tests__/InteractionLayer.multiSelect.test.tsx src/components/canvas/__tests__/TerritoryLayer.shiftClick.test.tsx src/components/canvas/__tests__/CanvasViewer.test.tsx src/components/canvas/__tests__/CanvasViewer.hydrate.test.tsx src/components/canvas/__tests__/CanvasViewer.resize.test.tsx src/components/canvas/__tests__/CanvasViewer.panOnSelect.test.tsx` | yes | ⬜ pending |
| 05-T2 | 05 | 2 | SC-2 | T-03-FE-CANVAS-02 | hover tooltip via Stage.getPointerPosition(); MultiSelectInspector aggregate; InspectorSidebar 3-mode dispatch; English COPY untouched | unit | `cd frontend && npm run test -- --run src/components/canvas/__tests__/HoverTooltip.test.tsx src/components/canvas/__tests__/MultiSelectInspector.test.tsx src/components/canvas/__tests__/InspectorSidebar.test.tsx` | yes | ⬜ pending |
| 06-T1 | 06 | 3 | SC-3 | T-03-FE-PURGE-01 | partial Pitfall-1 grep zero (D-10 set); npm build green; vitest green | build + grep | `cd frontend && npm run build 2>&1 | tail -30 && npm run test -- --run 2>&1 | tail -20` | yes | ⬜ pending |
| 06-T2 | 06 | 3 | SC-3 | T-03-FE-PURGE-01, T-03-FE-PURGE-02 | full Pitfall-1 grep zero (D-11+D-13 frontend); vite + vitest + tsc green; ~30 files deleted | build + grep + tsc | `cd frontend && npm run build 2>&1 | tail -10 && npm run test -- --run 2>&1 | tail -20 && npx tsc --noEmit -p tsconfig.app.json 2>&1 | tail -5` | yes | ⬜ pending |
| 07-T1 | 07 | 3 | SC-3, SC-4 | — | v1 ingest backend deletions; Phase 01 parity 10/10; Plan 02 endpoints green | parity + unit | `cd backend && pytest tests/parity/test_iberia_868.py tests/unit/test_v3_ingest.py tests/unit/test_v3_generate.py tests/unit/test_v3_status.py tests/unit/test_v3_artifacts.py -x` | yes | ⬜ pending |
| 07-T2 | 07 | 3 | SC-3, SC-4 | T-03-04, T-03-BE-PURGE-01, T-03-BE-PURGE-02 | full LLM stack deletion incl. auth.py + credential_store.py + 3 ORM models; main.py importable; Phase 01 parity 10/10 | parity + unit | `cd backend && pytest tests/parity/test_iberia_868.py tests/unit/ -x` | yes | ⬜ pending |
| 08-T1 | 08 | 4 | SC-1, SC-4 | T-03-UAT-01 | seed_phase01_artifacts copies all 14 files; idempotent; UUID-validated | unit | `cd backend && pytest tests/unit/test_seed_phase01_artifacts.py -x` | yes | ⬜ pending |
| 08-T2 | 08 | 4 | SC-1, SC-2, SC-3, SC-4 | — | Playwright happy path: pan/zoom/click/multi-select/hover/empty-stage; zero console errors; zero /preview/* requests; cross-surface grep zero; Phase 01 parity 10/10 | uat + parity + grep | `cd backend && pytest tests/parity/test_iberia_868.py tests/unit/test_seed_phase01_artifacts.py -x && cd ../frontend && npx playwright test 03-canvas-workspace.spec.ts --reporter=line` | yes | ⬜ pending |
| 08-T3 | 08 | 4 | SC-1, SC-2, SC-3 | — | Visual sign-off vs UI-SPEC §Layout Contract; SSE log panel shows 11 ✓ in DAG order | manual (checkpoint:human-verify) | manual — see Plan 08 Task 3 instructions | yes | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

> Wave 0 is the test-infra + canvas-sidecar emitter task chain that must complete before downstream waves.

- [ ] Canvas-sidecar emitter (`run_pipeline` extension) — emits `territories.geojson`, `baronies.geojson`, `condado_colors.json`, `barony_colors.json` (BLOCKER from RESEARCH.md Q1) — **Plan 01 Task 3**
- [ ] `_write_geojson_atomic` lift to `services/paths.py` — gates D-12 v1 ingest delete (RESEARCH.md Q2) — **Plan 01 Task 1**
- [ ] `cfg.on_stage` callback slot on `RegionConfig` + 22 hook events in `run_pipeline` — feeds Plan 02 SSE producer — **Plan 01 Task 2**
- [ ] Test stubs for `/api/v3/projects/{id}/generate` POST + SSE pair — **Plan 02 Task 2** (depends on Plan 01)
- [ ] Test stubs for `/api/v3/projects/{id}/status` GET — **Plan 02 Task 1**
- [ ] Test stubs for `/api/v3/projects/{id}/artifacts/{file_name}` GET — **Plan 02 Task 1**
- [ ] Playwright fixture: project seeded with Phase 01 artifacts — **Plan 08 Task 1**
- [ ] Frontend: `useRunStore` + `useCanvasArtifacts` URL switch test scaffold — **Plan 03 Tasks 1, 3**

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual parity of Mapbox-like shell with UI-SPEC.md mockup | SC-3 | Layout aesthetics not asserted in unit tests | Open `/projects/<seeded-id>` in dev server; compare against UI-SPEC.md §"Layout Contract" — see Plan 08 Task 3 checkpoint |
| SSE stage-by-stage check progression in expanded log panel | D-03 | Streaming UX flow with real ~10s pipeline | Click "Regenerar" → expand status badge → confirm 11 ✓ marks appear in DAG order — see Plan 08 Task 3 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (1 task is `checkpoint:human-verify` — Plan 08 Task 3 — by design per UI-SPEC visual contract)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (only Plan 08 T3 is manual; T1 + T2 carry automation)
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending (awaiting executor + checker pass)
