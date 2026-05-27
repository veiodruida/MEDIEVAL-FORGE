---
phase: 8
slug: border-vertex-editor-manual-svg-style-vertex-editing-of-terr
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-26
updated: 2026-05-27
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) + vitest (frontend unit) + Playwright (UAT) |
| **Config file** | `backend/pyproject.toml`, `frontend/vitest.config.ts`, `tests/uat/playwright/playwright.config.ts` |
| **Quick run command** | `pytest tests/unit/test_phase08_*.py -x` / `cd frontend && npx vitest run src/**/__tests__/*phase08*` |
| **Full suite command** | `pytest tests/ -q && cd frontend && npx vitest run && npx playwright test tests/uat/playwright/phase08-*` |
| **Estimated runtime** | ~110 seconds quick / ~7 min full (Iberia 868 parity + BLOCKER-1 parity included) |

---

## Sampling Rate

- **After every task commit:** Run quick command for the task's plan
- **After every plan wave:** Run full unit + parity for the affected layer
- **Before `/gsd-verify-work`:** Full suite green incl. Playwright UAT
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

> Filled by planner. Every PLAN.md task gets a row mapping REQ-ID → command.
> Rows for revision-induced changes (BLOCKER-1, -2, WARNINGS 3-6) marked in Notes.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status | Notes |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|-------|
| 8-01-01 | 01 | 1 | DAG-01, DAG-02 | T-08-01-01 | Identity carry-forward | unit | `pytest backend/tests/unit/test_dag_manual_edit.py -x` | ✅ Wave 0 | ⬜ pending | BLOCKER-2 fix: now asserts count term in token |
| 8-01-02 | 01 | 1 | DAG-01, DAG-02 | — | Iberia parity carry-forward | parity | `pytest backend/tests/parity/test_iberia_868.py -x` | ✅ | ⬜ pending | |
| 8-04-01 | 04 | 3 | UNDO-01, PERSIST-02 | T-08-04-02 | Chokepoint sink registration (WARNING-6) | unit | `cd frontend && npx vitest run src/stores/__tests__/useEditorStore.test.ts` | ✅ Wave 0 | ⬜ pending | WARNING-6 fix: setVerticesAndLog is single sink chokepoint |
| 8-04-02 | 04 | 3 | UNDO-01 | T-08-04-01 | EditorSyncBridge mount registers sink | unit | `cd frontend && npx tsc --noEmit` | ✅ Wave 0 | ⬜ pending | New file EditorSyncBridge.tsx |
| 8-06a-01 | 06a | 5 | EDIT-VERTEX-01..04 | T-08-06a-01 | Topology validate batch | unit+int | `pytest backend/tests/unit/test_manual_edit_simplify.py backend/tests/integration/test_editor_validate_endpoint.py -x` | ✅ Wave 0 | ⬜ pending | |
| 8-06a-02 | 06a | 5 | EDIT-VERTEX-01..04 | — | Vertex cap badge | unit | `cd frontend && npx vitest run src/components/editor/__tests__/VertexCapBadge.test.tsx` | ✅ Wave 0 | ⬜ pending | |
| 8-06b-01 | 06b | 6 | TOPO-03, TOPO-04 | T-08-06b-02 | Snap + shared-vertex coupling | unit | `cd frontend && npx vitest run src/lib/__tests__/snap.test.ts src/lib/__tests__/sharedVertex.test.ts` | ✅ Wave 0 | ⬜ pending | |
| 8-06b-02 | 06b | 6 | TOPO-01, TOPO-02 | T-08-06b-01 | Topology block + coupling backend | unit | `pytest backend/tests/unit/test_topology_validate.py backend/tests/unit/test_shared_vertex_coupling.py -x` | ✅ Wave 0 | ⬜ pending | |
| 8-07-01 | 07 | 6 | EDIT-POLYGON-01..03 | T-08-07-01, T-08-07-02 | Replay helpers + /editor/apply persists-only (BLOCKER-1) | unit+int | `pytest backend/tests/unit/test_manual_edit_split.py backend/tests/unit/test_manual_edit_merge.py backend/tests/integration/test_editor_apply_persists_only.py -x` | ✅ Wave 0 | ⬜ pending | BLOCKER-1 fix: API persists only; new persists_only test |
| 8-07-02 | 07 | 6 | EDIT-POLYGON-01..03 | — | Optimistic frontend ops (turf.js) | unit | `cd frontend && npx vitest run src/components/canvas/__tests__/VertexEditLayer.test.tsx` | ✅ Wave 0 | ⬜ pending | BLOCKER-1 fix: client computes geometry optimistically |
| **8-07c-01** | **07c** | **7** | **EDIT-POLYGON-01..03, DAG-01, DAG-02** | **T-08-07c-01, -02, -03** | **compute() replay path (BLOCKER-1 closure)** | **unit** | `pytest backend/tests/unit/test_manual_edit_compute_replay.py -x` | **✅ Wave 0** | **⬜ pending** | **BLOCKER-1 closure: compute() loads snapshot, vectorises, replays, rasterises** |
| **8-07c-02** | **07c** | **7** | **DAG-01, DAG-02, EDIT-POLYGON-01..03** | **T-08-07c-02** | **lookup_barony.png mutates after edit (parity, NEW POLARITY)** | **parity** | `pytest backend/tests/parity/test_phase08_edit_visible_in_lookup.py -x` | **✅ Wave 0** | **⬜ pending** | **BLOCKER-1 closure: assertion is != not == — easy to write wrong direction** |
| 8-08-01 | 08 | 6 | LANDMASK-01, LANDMASK-02 | — | Landmask header + auto/manual mode | unit | `cd frontend && npx vitest run src/components/editor/__tests__/LandmaskEditorHeader.test.tsx` | ✅ Wave 0 | ⬜ pending | WARNING-5 fix: VertexEditLayer landmask handles + Pitfall 3 |
| 8-08-02 | 08 | 6 | LANDMASK-01, LANDMASK-02, DAG-04 | T-08-08-01, -02 | Landmask cascade + per-country KD-tree | int+parity | `pytest backend/tests/integration/test_landmask_edit.py backend/tests/integration/test_landmask_cascade.py backend/tests/parity/test_iberia_868.py -x` | ✅ Wave 0 | ⬜ pending | WARNING-4 fix: contracts.py + dag.py listed |
| 8-09-01 | 09 | 7 | BRANCH-01, BRANCH-02, BRANCH-04 | T-08-09-01, -02 | Branch picker + 4 dialogs + EditorSyncBridge mount | unit | `cd frontend && npx vitest run src/components/editor/__tests__/BranchPicker.test.tsx` | ✅ Wave 0 | ⬜ pending | WARNING-6 wiring: WorkspaceToolbar mounts EditorSyncBridge |
| 8-09-02 | 09 | 7 | DAG-03, BRANCH-04 | T-08-09-03 | Slider conflict modal Pitfall 9 ordering | unit | `cd frontend && npx vitest run src/components/editor/__tests__/SliderConflictDialog.test.tsx` | ✅ Wave 0 | ⬜ pending | WARNING-3 fix: ParameterSidebar.tsx in files_modified |

| 8-07c-01-review | 07c | 7 | EDIT-POLYGON-01..03, DAG-01 | T-08-07c-01 | Gemini review (LOW): rasterize uses all_touched=False | unit | `pytest backend/tests/unit/test_manual_edit_compute_replay.py::test_rasterize_uses_all_touched_false -x` | ✅ Wave 0 | ⬜ pending | Review-1: prevents raster-vector roundtrip artifacts (Pitfall: Unity byOriginalIdx shader) |
| 8-04-01-review | 04 | 3 | UNDO-01 | — | Gemini review UX: undoLabels/redoLabels stacks tracked in lockstep with zundo | unit | `cd frontend && npx vitest run src/stores/__tests__/useEditorStore.test.ts -t "undoLabels"` | ✅ Wave 0 | ⬜ pending | Review-2: enables "Desfazer Mover Vértice" tooltips in 08-09 |
| 8-09-01-review | 09 | 7 | BRANCH-01 | — | Gemini review UX: WorkspaceToolbar Undo/Redo tooltip reads undoLabels.at(-1) | unit | `cd frontend && npx vitest run src/components/editor/__tests__/BranchPicker.test.tsx -t "undoLabels tooltip"` | ✅ Wave 0 | ⬜ pending | Review-3: depends on 8-04-01-review row above |
| 8-11-03-review | 11 | 8 | EDIT-VERTEX-01, PERF-01 | — | Gemini + OpenCode review: snap-jitter zoom check (UAT step 5b) + --allow-manual-override perf flag | uat | manual + `ALLOW_MANUAL_OVERRIDE=1 npx playwright test tests/uat/08-perf-drag-60fps.spec.ts` (CI may waive) | ✅ Wave 0 | ⬜ pending | Review-4: Pitfall 7 scale-aware snap visual + CI flakiness mitigation |
*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `backend/tests/unit/test_dag_manual_edit.py` — stubs for `manual_edit` DAG stage tokens + identity pass-through + count term (BLOCKER-2)
- [x] `backend/tests/unit/test_models_branches.py` — stubs for Branch/Snapshot/EditEvent ORM round-trip
- [x] `backend/tests/unit/test_stage_cache_branch.py` — stubs for branch-keyed cache lifecycle (announces test_stage_cache.py rewrite in 08-02)
- [x] `backend/tests/unit/test_topology_validate.py` — stubs for topology validation codes (SELF_INTERSECT, NEIGHBOUR_GAP, DEGENERATE)
- [x] `backend/tests/unit/test_manual_edit_simplify.py` — stubs for polygon simplify / vertex cap
- [x] `backend/tests/unit/test_manual_edit_split.py` — stubs for territory split + DAG token emission
- [x] `backend/tests/unit/test_manual_edit_merge.py` — stubs for territory merge + original_idx preservation
- [x] `backend/tests/unit/test_shared_vertex_coupling.py` — stubs for shared-vertex propagation (TOPO-03/04)
- [x] `backend/tests/integration/test_branches_endpoint.py` — stubs for POST/GET/DELETE/PATCH branch endpoints
- [x] `backend/tests/integration/test_landmask_edit.py` — stubs for landmask edit + KD-tree rebuild (WARNING-4)
- [x] `backend/tests/integration/test_landmask_cascade.py` — stubs for landmask cascade DAG invalidation
- [x] `backend/tests/integration/test_snapshot_persistence.py` — stubs for snapshot save/restore lifecycle
- [x] `backend/tests/integration/test_editor_validate_endpoint.py` — stubs for /editor/validate endpoint
- [x] `backend/tests/integration/test_render_with_branch.py` — stubs for render isolation across branches
- [x] **`backend/tests/parity/test_phase08_edit_visible_in_lookup.py`** — **BLOCKER-1 closure**: stub asserting one-op mutates lookup_barony.png (pytest.mark.parity present)
- [x] **`backend/tests/unit/test_manual_edit_compute_replay.py`** — **BLOCKER-1 closure**: stub for vectorise→replay→rasterise + all_touched=False (Gemini review)
- [x] **`backend/tests/integration/test_editor_apply_persists_only.py`** — **BLOCKER-1 contract**: stub asserting /editor/apply response has no geometry/polygon/coords keys
- [x] `frontend/src/stores/__tests__/useEditorStore.test.ts` — zundo wiring stub + chokepoint sink mock + undoLabels/redoLabels (WARNING-6, Review-2)
- [x] `frontend/src/components/canvas/__tests__/VertexEditLayer.test.tsx` — handle render stub + landmask handle stub (WARNING-5, BLOCKER-1)
- [x] `frontend/src/components/editor/__tests__/BranchPicker.test.tsx` — branch picker + undoLabels tooltip stub (WARNING-6, Review-3)
- [x] `frontend/src/components/editor/__tests__/VertexCapBadge.test.tsx` — vertex count / cap badge stubs
- [x] `frontend/src/lib/__tests__/snap.test.ts` — scale-aware snap threshold stubs (Review-4)
- [x] `frontend/src/lib/__tests__/sharedVertex.test.ts` — shared-vertex propagation frontend stubs
- [x] `frontend/src/hooks/__tests__/useKeyboardShortcuts.phase08.test.ts` — Ctrl+Z / Escape / Delete key stubs
- [x] `frontend/src/components/__tests__/DesktopRequiredBanner.test.tsx` — mobile block stubs
- [x] `frontend/src/components/editor/__tests__/SliderConflictDialog.test.tsx` — conflict dialog ordering stubs (WARNING-3, Pitfall 9)
- [x] `frontend/src/components/editor/__tests__/LandmaskEditorHeader.test.tsx` — auto/manual mode header stubs (WARNING-5)
- [x] `frontend/tests/uat/08-vertex-drag.spec.ts` — Playwright vertex drag UAT stubs
- [x] `frontend/tests/uat/08-slider-conflict.spec.ts` — Playwright slider conflict UAT stubs
- [x] `frontend/tests/uat/08-perf-drag-60fps.spec.ts` — Playwright 60fps perf stubs + ALLOW_MANUAL_OVERRIDE flag (Review-4)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 60fps drag perceived smoothness | REQ-08-perf | Frame timing thresholds noisy in CI | Open Iberia 868, drag a barony vertex across screen, observe no jank |
| Snap visual feedback (yellow circle) | REQ-08-snap | Visual-only artifact | Hover vertex near neighbour vertex, confirm yellow circle appears |
| Purple shared-edge highlight | REQ-08-shared-edge | Visual-only | Hover edge between two baronies, confirm purple highlight |
| Edited lookup PNG visibly differs from baseline | REQ-08-d17 | Pixel-diff hard to assert in CI; parity test covers SHA-256 only | After running 08-07c parity test, open both `baseline/lookup_barony.png` and `edited/lookup_barony.png` in a viewer — confirm visible difference at the translated barony |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (including 3 NEW files from BLOCKER-1 closure)
- [x] No watch-mode flags
- [x] Feedback latency < 90s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** Wave 0 complete — 2026-05-27 (08-00 execution: 17 backend + 10 vitest + 3 playwright stubs; 58 pytest + 45 vitest + 11 playwright tests, all skip cleanly; commits 8aea489 + b7a6cff)

**Wave 8 sign-off — 2026-05-27 (08-11 execution):**
- [x] 4 Playwright UAT specs filled (08-vertex-drag: 5 tests, 08-slider-conflict: 3 tests, 08-perf-drag-60fps: 3 tests, 08-branch-flow: 5 tests) — 16 total passing
- [x] `test_phase08_edit_roundtrip.py` — 2 parity tests: 10-file identity byte-equal + golden fixture comparison (D-17 gate) — both passing (83s)
- [x] `test_phase08_edit_visible_in_lookup.py` — pre-existing 2 parity tests (identity + mutation polarity) — passing
- [x] ALLOW_MANUAL_OVERRIDE grep gate: 13 matches (>> 1 required by OpenCode review-4)
- [x] Grep gate 1 (v1 restoration): 0 hits — PASS
- [x] Grep gate 2 (global KD-tree): 0 hits — PASS
- [x] Grep gate 3 (BICUBIC/BILINEAR): 0 code hits (1 comment-only) — PASS
- [x] Grep gate 4 (branch_id in cache): all cache_put/cache_get calls use cfg.branch_id — PASS
- [x] Pre-existing vitest failures (37) and pytest failures (3) confirmed pre-Phase-08-11 — out of scope per CLAUDE.md deviation boundary
- [x] Awaiting: manual UAT checkpoint (Task 3 — 3 visual gates)
