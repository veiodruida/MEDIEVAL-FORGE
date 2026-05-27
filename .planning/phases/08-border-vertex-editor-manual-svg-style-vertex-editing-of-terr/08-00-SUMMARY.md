---
phase: "08"
plan: "00"
subsystem: test-scaffolds
tags: [wave-0, nyquist, test-stubs, backend, frontend, playwright]
dependency_graph:
  requires: []
  provides:
    - backend/tests/unit/test_topology_validate.py
    - backend/tests/unit/test_manual_edit_simplify.py
    - backend/tests/unit/test_manual_edit_split.py
    - backend/tests/unit/test_manual_edit_merge.py
    - backend/tests/unit/test_shared_vertex_coupling.py
    - backend/tests/unit/test_dag_manual_edit.py
    - backend/tests/unit/test_stage_cache_branch.py
    - backend/tests/unit/test_models_branches.py
    - backend/tests/integration/test_branches_endpoint.py
    - backend/tests/integration/test_landmask_edit.py
    - backend/tests/integration/test_landmask_cascade.py
    - backend/tests/integration/test_snapshot_persistence.py
    - backend/tests/integration/test_editor_validate_endpoint.py
    - backend/tests/integration/test_render_with_branch.py
    - backend/tests/unit/test_manual_edit_compute_replay.py
    - backend/tests/parity/test_phase08_edit_visible_in_lookup.py
    - backend/tests/integration/test_editor_apply_persists_only.py
    - frontend/src/stores/__tests__/useEditorStore.test.ts
    - frontend/src/components/canvas/__tests__/VertexEditLayer.test.tsx
    - frontend/src/components/editor/__tests__/BranchPicker.test.tsx
    - frontend/src/components/editor/__tests__/VertexCapBadge.test.tsx
    - frontend/src/lib/__tests__/snap.test.ts
    - frontend/src/lib/__tests__/sharedVertex.test.ts
    - frontend/src/hooks/__tests__/useKeyboardShortcuts.phase08.test.ts
    - frontend/src/components/__tests__/DesktopRequiredBanner.test.tsx
    - frontend/src/components/editor/__tests__/SliderConflictDialog.test.tsx
    - frontend/src/components/editor/__tests__/LandmaskEditorHeader.test.tsx
    - frontend/tests/uat/08-vertex-drag.spec.ts
    - frontend/tests/uat/08-slider-conflict.spec.ts
    - frontend/tests/uat/08-perf-drag-60fps.spec.ts
    - 08-VALIDATION.md (nyquist_compliant: true, wave_0_complete: true)
  affects: []
tech_stack:
  added: []
  patterns:
    - "pytestmark = pytest.mark.skip(reason='Wave 0 stub — implementation lands in plan 08-XX')"
    - "pytestmark = [pytest.mark.parity, pytest.mark.skip(...)] for parity stubs"
    - "it.skip('TODO plan 08-XX: descriptive name', () => {}) for vitest stubs"
    - "test.skip('TODO plan 08-11: ...', async ({ page }) => {}) for Playwright stubs"
key_files:
  created:
    - backend/tests/unit/test_topology_validate.py
    - backend/tests/unit/test_manual_edit_simplify.py
    - backend/tests/unit/test_manual_edit_split.py
    - backend/tests/unit/test_manual_edit_merge.py
    - backend/tests/unit/test_shared_vertex_coupling.py
    - backend/tests/unit/test_dag_manual_edit.py
    - backend/tests/unit/test_stage_cache_branch.py
    - backend/tests/unit/test_models_branches.py
    - backend/tests/integration/test_branches_endpoint.py
    - backend/tests/integration/test_landmask_edit.py
    - backend/tests/integration/test_landmask_cascade.py
    - backend/tests/integration/test_snapshot_persistence.py
    - backend/tests/integration/test_editor_validate_endpoint.py
    - backend/tests/integration/test_render_with_branch.py
    - backend/tests/unit/test_manual_edit_compute_replay.py
    - backend/tests/parity/test_phase08_edit_visible_in_lookup.py
    - backend/tests/integration/test_editor_apply_persists_only.py
    - frontend/src/stores/__tests__/useEditorStore.test.ts
    - frontend/src/components/canvas/__tests__/VertexEditLayer.test.tsx
    - frontend/src/components/editor/__tests__/BranchPicker.test.tsx
    - frontend/src/components/editor/__tests__/VertexCapBadge.test.tsx
    - frontend/src/lib/__tests__/snap.test.ts
    - frontend/src/lib/__tests__/sharedVertex.test.ts
    - frontend/src/hooks/__tests__/useKeyboardShortcuts.phase08.test.ts
    - frontend/src/components/__tests__/DesktopRequiredBanner.test.tsx
    - frontend/src/components/editor/__tests__/SliderConflictDialog.test.tsx
    - frontend/src/components/editor/__tests__/LandmaskEditorHeader.test.tsx
    - frontend/tests/uat/08-vertex-drag.spec.ts
    - frontend/tests/uat/08-slider-conflict.spec.ts
    - frontend/tests/uat/08-perf-drag-60fps.spec.ts
  modified:
    - .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md
decisions:
  - "Wave 0 scaffold files placed at paths specified in 08-00-PLAN.md files_modified list (not in playwright/ subdir) because playwright.config.ts testDir=./tests + testMatch=*.spec.ts discovers them automatically"
  - "test_phase08_edit_visible_in_lookup.py carries BOTH pytest.mark.parity AND pytest.mark.skip so parity counter is accurate from Wave 0"
  - "test_editor_apply_persists_only.py docstring includes BLOCKER-1 contract verbatim: /editor/apply response JSON must have no geometry/polygon/coords keys"
  - "test_stage_cache_branch.py docstring notes it announces the 08-02 atomic swap of test_stage_cache.py without deleting the old file yet"
  - "test_manual_edit_compute_replay.py includes test_rasterize_uses_all_touched_false stub to close Gemini Review-1 (LOW) from 08-VALIDATION.md"
metrics:
  duration_minutes: 15
  completed_date: "2026-05-27"
  tasks_completed: 3
  tasks_total: 3
  files_created: 30
  files_modified: 1
  tests_added: 114
---

# Phase 08 Plan 00: Wave 0 Test Scaffolds Summary

**One-liner:** 30 skip-marked test scaffold files (17 backend + 10 vitest + 3 Playwright) providing Nyquist-compliant executable targets for all Wave 1–8 implementation tasks; VALIDATION.md flipped to nyquist_compliant + wave_0_complete = true.

---

## What Was Built

Wave 0 Blocker plan: landed all 31 scaffold files listed in `08-00-PLAN.md` (the plan header says 31 but `files_modified` lists 30; 30 files were created per the canonical list).

### Backend (17 files)

**Unit scaffolds (8):**
- `test_topology_validate.py` — TOPO-01/02 codes: SELF_INTERSECT, NEIGHBOUR_GAP, DEGENERATE, valid
- `test_manual_edit_simplify.py` — EDIT-VERTEX-04 RDP simplification + vertex cap
- `test_manual_edit_split.py` — EDIT-POLYGON-01 territory split + DAG token
- `test_manual_edit_merge.py` — EDIT-POLYGON-02/03 merge + original_idx preservation
- `test_shared_vertex_coupling.py` — TOPO-03/04 shared-vertex propagation
- `test_dag_manual_edit.py` — DAG-01/02/03 count-term token, identity, stage order (BLOCKER-2)
- `test_stage_cache_branch.py` — BRANCH-01/02 + DAG-04/05 branch-keyed cache (announces 08-02 swap)
- `test_models_branches.py` — BRANCH-01/03 + PERSIST-01 ORM round-trip
- `test_manual_edit_compute_replay.py` — BLOCKER-1 closure: vectorise→replay→rasterise + all_touched=False (Gemini Review-1)

**Integration scaffolds (7):**
- `test_branches_endpoint.py` — BRANCH-01/02/04/05 REST endpoint stubs
- `test_landmask_edit.py` — LANDMASK-01/02 + DAG-04 edit + KD-tree rebuild
- `test_landmask_cascade.py` — DAG-04/05 cascade invalidation
- `test_snapshot_persistence.py` — PERSIST-01/02 save/restore
- `test_editor_validate_endpoint.py` — EDIT-VERTEX-01/02 + TOPO-01/02 validate endpoint
- `test_render_with_branch.py` — DAG-01/02 + BRANCH-04/05 render isolation
- `test_editor_apply_persists_only.py` — BLOCKER-1 contract: /editor/apply has no geometry/polygon/coords keys

**Parity scaffolds (1):**
- `test_phase08_edit_visible_in_lookup.py` — BLOCKER-1 closure: lookup_barony.png mutates after edit (assertion polarity: !=); carries pytest.mark.parity even while skip-marked

### Frontend Vitest (10 files)
- `useEditorStore.test.ts` — UNDO-01 zundo temporal + undoLabels/redoLabels stacks (WARNING-6, Review-2)
- `VertexEditLayer.test.tsx` — EDIT-VERTEX-01..03 handles + landmask handle (WARNING-5, BLOCKER-1)
- `BranchPicker.test.tsx` — BRANCH-01/02/04 + undoLabels tooltip (WARNING-6, Review-3)
- `VertexCapBadge.test.tsx` — EDIT-VERTEX-04 vertex count / cap badge
- `snap.test.ts` — TOPO-03/04 scale-aware snap threshold (Review-4)
- `sharedVertex.test.ts` — TOPO-03/04 shared-vertex propagation frontend
- `useKeyboardShortcuts.phase08.test.ts` — UX-01/02 + UNDO-01 keyboard shortcuts
- `DesktopRequiredBanner.test.tsx` — UX-01/02 mobile block
- `SliderConflictDialog.test.tsx` — DAG-03 + BRANCH-04 Pitfall 9 ordering (WARNING-3)
- `LandmaskEditorHeader.test.tsx` — LANDMASK-01/02 auto/manual mode toggle (WARNING-5)

### Playwright UAT (3 files)
- `08-vertex-drag.spec.ts` — EDIT-VERTEX-01 drag + snap + undo + shared-vertex
- `08-slider-conflict.spec.ts` — DAG-03 slider conflict dialog (WARNING-3)
- `08-perf-drag-60fps.spec.ts` — PERF-01 60fps + zoom jitter + ALLOW_MANUAL_OVERRIDE flag (Review-4)

### VALIDATION.md
- `nyquist_compliant: false` → `true`
- `wave_0_complete: false` → `true`
- Per-task table: all 20 rows updated from `❌ W0` → `✅ Wave 0`
- Wave 0 Requirements checklist: 30 items ticked
- Validation Sign-Off: all 6 items checked

---

## Deviations from Plan

None — plan executed exactly as written. All 30 files in `files_modified` created; scaffold patterns match plan interfaces verbatim. Three BLOCKER-1 closure files include the specific content required by acceptance criteria:
1. `test_phase08_edit_visible_in_lookup.py` — dual marker `[pytest.mark.parity, pytest.mark.skip(...)]`
2. `test_editor_apply_persists_only.py` — BLOCKER-1 contract phrase in module docstring
3. `test_manual_edit_compute_replay.py` — `test_rasterize_uses_all_touched_false` stub for Gemini Review-1

---

## Known Stubs

All 30 files are intentional stubs. Every test function body is `pass`. Implementation lands in plans 08-01 through 08-11 per the VALIDATION.md per-task table. This is the design intent of Wave 0 — stubs are the deliverable, not a deficiency.

---

## Threat Flags

None — Wave 0 produces only test scaffolds. No production code, no API surface, no DB writes. No new security-relevant surface introduced.

---

## Self-Check: PASSED

**Files (sample):**
- FOUND: `backend/tests/unit/test_topology_validate.py`
- FOUND: `backend/tests/parity/test_phase08_edit_visible_in_lookup.py`
- FOUND: `frontend/tests/uat/08-perf-drag-60fps.spec.ts`
- All 30 files: 0 missing

**Commits:**
- FOUND: `8aea489` — test(08-00): wave 0 backend test scaffolds (17 files)
- FOUND: `b7a6cff` — test(08-00): wave 0 frontend test scaffolds (13 files)
- FOUND: `2a29402` — docs(08-00): flip nyquist_compliant + wave_0_complete to true

**Test collection:**
- pytest `--co -q`: 58 tests collected, 0 errors
- vitest run: 10 files skipped, 45 tests skipped, 0 failed
- playwright --list: 11 tests listed across 3 files

**VALIDATION.md:**
- `nyquist_compliant: true`: 2 occurrences (frontmatter + sign-off checklist)
- `wave_0_complete: true`: 1 occurrence (frontmatter)
