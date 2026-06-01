---
status: resolved
trigger: "carve-enclave-edit-leaves-hole"
created: 2026-06-01T00:00:00Z
updated: 2026-06-01T15:00:00Z
---

## Current Focus

hypothesis: CONFIRMED — vacated land after border-shrink vertex op is never reassigned;
  stays fill=-1 (ocean). Fix: gap-fill vacated-land mask using nearest eligible barony
  (excluding edited baronies) via scipy distance_transform_edt.
test: test_manual_edit_border_shrink.py — 2/2 GREEN after fix.
next_action: DONE.

## RESOLVED (user-confirmed 2026-06-01)

Fix commit 396f58e. User live real-mouse: border-shrink no longer leaves an ocean hole —
the vacated strip is absorbed by the neighbour ("ele estendeu o azul claro"). NO regression:
the user reported the extended region "wasn't editable", but the discriminator test (toggle
Baronies layer ON → click region) confirmed it edits normally as a barony — it was merely the
default CONDADO view (uiStore default: condados ON, baronies OFF), not a dropped geojson entry.

Follow-up scoped SEPARATELY (NOT part of this session):
- Condado-boundary editing as a unit → .planning/todos/pending/2026-06-01-condado-boundary-editing.md
- Shared-border create-vs-extend prompt → .planning/todos/pending/2026-06-01-shared-border-move-create-vs-extend-prompt.md

## GROUND TRUTH (captured 2026-06-01, real Apply payload — not hypothesised)

Instrumented POST /branches/{id}/snapshots (the route border-edit Apply actually uses;
/editor/apply is NOT hit for vertex edits). Captured one failing Apply:
  - trigger=manual, edit_log = 4 `move` ops (vertexIds lists of 100/100/29/45, NO coords —
    final coords live in vertices dict).
  - vertices_keys = 464 keys, ALL `Consuegra#*` — ONLY the edited barony's ring is present.
    The neighbour barony is NOT in the snapshot at all.
Mechanism (manual_edit.compute, confirmed by reading the code):
  1. replay_vertex_ring("Consuegra") rebuilds ONLY polygons_by_id[consuegra_idx] from the
     shrunken ring. Neighbour polygon untouched. (manual_edit.py:548-620)
  2. rasterize(..., fill=-1) → vacated land pixels become -1. (manual_edit.py:427-434)
  3. restore: ocean_mask = (input==-1) & (out==-1). Vacated pixels had input=consuegra_idx
     (≠ -1) so they are NOT restored — they stay -1 = ocean hole. (manual_edit.py:441-444)
This is exactly the user's "só vira buraco quando mexo nos limites da baronia vizinha".

## RED test (non-circular — authored from the captured shape, then run)

backend/tests/unit/test_manual_edit_border_shrink.py — two adjacent baronies A|B; A's
shared border dragged inward via a `move` op + A's shrunken ring in vertices_dict.
Run result (2026-06-01): **RED** — 129 land pixels became -1; the 5×20 vacated strip is
100% ocean. Confirms the contract violation deterministically without a browser, without a
carve op. "Backend ruled out" (earlier) was WRONG for the border-edit path.

## Fix strategy (for the continuation debugger)

Location: manual_edit.compute(), AFTER rasterize + the ocean/ignore restore (manual_edit.py
~427-444). New step BEFORE returning `out`:
  - vacated-land mask = (input_array is a real barony idx: >=0 and != 9999) & (out == -1).
  - Reassign each vacated-land pixel to the NEAREST barony present in `out`, EXCLUDING the
    edited baronies (the `barony_names` set whose rings were replayed) — so the gap EXTENDS
    the neighbour instead of snapping back to the shrunk barony (which would silently undo
    the user's edit). scipy nearest (distance_transform_edt indices / cKDTree) over `out`'s
    non-edited barony pixels.
  - Never touch genuine ocean (input_array == -1) or 9999 ignore.
Guards / edge cases to handle:
  - Coastal shrink (vacated land borders only ocean, no other barony nearby): acceptable to
    leave ocean — but the user's repro is an INTERIOR shared border, which always has a
    neighbour. The RED test pins the interior case.
  - Parity MUST stay green: this step only runs when vacated land exists after a vertex op;
    the zero-edit identity path (empty hash) returns before any of this.
Verification gate: test_manual_edit_border_shrink.py GREEN (2/2) + full carve suite GREEN +
parity 22/0. Then orchestrator does live real-mouse confirm with the user.

## Prior carve-path fix (39b3836) — still valid but NOT this bug

The sections below diagnosed/fixed a DIFFERENT path (carve enclave + edit N). That fix is
correct for its path and stays. It did not resolve the user's repro because the user's
repro emits move ops on an existing barony, not a carve op.

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
  BACKEND BUG 3 (this session): replay_vertex_ring rebuilds ONLY the edited barony polygon; vacated land pixels receive fill=-1 from rasterize; ocean_mask restore only covers pixels where input_array==-1, so vacated land (input_array==real_idx) stays -1 → ocean hole. This is the direct cause of the user's "buraco".
  FRONTEND BUG A: useBezierApply.runApply reads store.vertices at Apply time; SelectionBridge wipes store.vertices on barony navigation → N's ring lost from snapshot → backend has no vertices for N to rebuild from.

fix:
  BACKEND FIX 1 (manual_edit.py lines 333-339): After the op loop and before the vertex-ring replay loop, extend barony_name_to_idx with entries from new_barony_meta (name→original_idx). Makes a local copy to avoid mutating caller's map. Now replay_vertex_ring("Baronato-<ts>") finds the correct idx.
  BACKEND FIX 2 (manual_edit.py lines 363-401): Capture N_original polygon immediately after each carve op in _carve_n_original dict. In D-25 re-apply loop, when N was edited (N_original ≠ N_final), reconstruct parent_original = parent'.union(N_original) then parent_final = parent_original.difference(N_final). Invariant parent_final ∪ N_final = parent_original restored.
  BACKEND FIX 3 (manual_edit.py, D-27 gap-fill block after sentinel restores): Compute vacated-land mask = (input_array>=0) & (input_array!=9999) & (out==-1). If any vacated pixels exist, build eligible mask = (out>=0) & (out!=9999) excluding edited-barony indices (derived from vertices_dict keys via barony_name_to_idx). Use scipy.ndimage.distance_transform_edt(~eligible, return_indices=True) to find nearest eligible source pixel per vacated pixel and assign out[vacated] = out[nearest_row, nearest_col]. Guard: if no eligible pixel exists (coastal shrink), leave as ocean — no crash.
  FRONTEND FIX A (useBezierApply.ts enrichVerticesFromEditLog()): Before posting snapshot, enrich vertices dict by synthesizing ${name}#i keys from each carve/create op's ring for any enclave whose vertex keys are absent from store.vertices. Live edits (if present) take precedence over synthesized fallback.

verification:
  - test_manual_edit_border_shrink.py: 2/2 GREEN (was RED before fix — 129 ocean pixels)
  - test_manual_edit_carve.py: 14/14 GREEN (no regression to carve path)
  - tests/parity/: 22 passed, 6 xfailed, 4 xpassed, 0 failed (zero-edit identity byte-identical)

files_changed:
  - backend/medieval_forge/services/pipeline/manual_edit.py
  - backend/tests/unit/test_manual_edit_border_shrink.py
  - backend/tests/unit/test_manual_edit_carve.py (prior session)
  - frontend/src/hooks/useBezierApply.ts (prior session)
  - frontend/src/hooks/__tests__/useBezierApply.carveEnclave.test.ts (prior session)
