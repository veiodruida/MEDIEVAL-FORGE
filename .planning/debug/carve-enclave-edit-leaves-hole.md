---
status: awaiting_human_verify
trigger: "carve-enclave-edit-leaves-hole"
created: 2026-06-01T00:00:00Z
updated: 2026-06-01T00:00:00Z
---

## Current Focus

hypothesis: Three bugs confirmed and fixed.
test: All automated regression tests GREEN (14 backend + 38 frontend).
next_action: Await human verification in live browser (Playwright pass by orchestrator).

## Symptoms

expected: After carving enclave N inside barony X, can edit N's contour; edit persists across deselect; Apply renders correctly with no hole.
actual: 1) Edit to N's contour is lost on deselect ("voltou ao 0"). 2) On "Aplicar edições" N vanishes and an unfilled hole is left in parent X.
errors: No console errors; failure is geometric (missing region) + lost-edit (state).
reproduction: Pen tool → carve closed loop inside a barony → auto-select fires → drag Bézier handle → click neighbour → edit lost → Apply → enclave gone + hole.
started: 2026-06-01 after plan 08.3-08 post-close auto-select was added.

## Eliminated

- hypothesis: Backend compute() has a bug for carve+N-edit combined ops (the prior investigation conclusion)
  evidence: TestCarveThenEnclaveEdit PASSES — but only because the hand-built test fixture INCLUDES "Carved-1" in barony_name_to_idx. The real orchestrator (line 428 of __init__.py) builds the map from bars[] BEFORE compute() runs, so freshly-carved N is never in the map. The prior tests did not cover the real orchestrator path.
  timestamp: 2026-06-01 (this session)

## Evidence

- timestamp: 2026-06-01
  checked: backend/medieval_forge/services/pipeline/__init__.py line 428
  found: `barony_name_to_idx = {b["name"]: i for i, b in enumerate(bars)}` is built BEFORE compute() is called. bars[] is extended AFTER compute() returns (lines 441-463). So "Baronato-<ts>" is never in the caller-supplied map when compute() executes.
  implication: replay_vertex_ring("Baronato-<ts>", barony_name_to_idx) finds None → silent return → N's edited ring is not rasterised → N keeps the original carve intersection ring, not the edited one.

- timestamp: 2026-06-01
  checked: backend/medieval_forge/services/pipeline/manual_edit.py D-25 re-apply loop (lines 367-384)
  found: `reapplied = parent_polys[0].difference(n_polys[0])` — parent_polys[0] is parent' (already has N_original hole). When user shrinks N (N_edited ⊊ N_original), the annulus N_original − N_edited belongs to neither parent' nor N_edited → falls through to ocean (-1). This is the exact "unfilled hole" the user reported.
  implication: 32 ocean(-1) pixels inside parent's footprint confirmed by test with 1-pixel shrink of N on all sides (rows 20-29 → 21-28). Invariant broken: parent_final ∪ N_final ≠ parent_original.

- timestamp: 2026-06-01
  checked: frontend/src/hooks/useBezierApply.ts runApply() line 57
  found: `const { vertices, editLog } = useEditorStore.getState()` — reads live store.vertices. SelectionBridge.tsx line 90 replaces store.vertices wholesale when user clicks a different barony. If user navigates away from N before Apply, snapshot.vertices has the neighbour's ring, not N's ring. Backend replay_vertex_ring can't find N's keys → N keeps original ring (or with the orchestrator-map bug, is skipped entirely).
  implication: Frontend RED test confirmed: after navigating to neighbour, snapshot sent has 0 enclave keys.

## Resolution

root_cause: Three bugs, two in backend one in frontend:
  BACKEND BUG 1: barony_name_to_idx built from pre-carve bars[] in __init__.py before compute() runs → replay_vertex_ring silently skips freshly-carved enclaves → vertex edits on N lost.
  BACKEND BUG 2: D-25 re-apply uses parent' (already has N_original hole) when re-subtracting N_edited → when N shrunk, annulus N_original-N_edited becomes ocean → unfilled hole reported by user.
  FRONTEND BUG A: useBezierApply.runApply reads store.vertices at Apply time; SelectionBridge wipes store.vertices on barony navigation → N's ring lost from snapshot → backend has no vertices for N to rebuild from.

fix:
  BACKEND FIX 1 (manual_edit.py lines 333-339): After the op loop and before the vertex-ring replay loop, extend barony_name_to_idx with entries from new_barony_meta (name→original_idx). Makes a local copy to avoid mutating caller's map. Now replay_vertex_ring("Baronato-<ts>") finds the correct idx.
  BACKEND FIX 2 (manual_edit.py lines 363-401): Capture N_original polygon immediately after each carve op in _carve_n_original dict. In D-25 re-apply loop, when N was edited (N_original ≠ N_final), reconstruct parent_original = parent'.union(N_original) then parent_final = parent_original.difference(N_final). Invariant parent_final ∪ N_final = parent_original restored.
  FRONTEND FIX A (useBezierApply.ts enrichVerticesFromEditLog()): Before posting snapshot, enrich vertices dict by synthesizing ${name}#i keys from each carve/create op's ring for any enclave whose vertex keys are absent from store.vertices. Live edits (if present) take precedence over synthesized fallback.

verification: 14 backend tests GREEN (including 2 new regression tests). 38 frontend tests GREEN (including 2 new regression tests). Pre-existing failures (test_llm_registry, test_pipeline_cli) confirmed pre-existing via git stash.

files_changed:
  - backend/medieval_forge/services/pipeline/manual_edit.py
  - backend/tests/unit/test_manual_edit_carve.py
  - frontend/src/hooks/useBezierApply.ts
  - frontend/src/hooks/__tests__/useBezierApply.carveEnclave.test.ts
