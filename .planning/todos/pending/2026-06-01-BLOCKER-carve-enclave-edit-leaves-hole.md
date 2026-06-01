---
created: 2026-06-01
source: user UAT during 08.3-09 checkpoint
status: pending
severity: blocker
relates_to: [08.3-07 carve, 08.3-08 auto-select, 08.1 BezierEditLayer]
---

# BLOCKER: editing a freshly-carved enclave leaves an unfilled hole on Apply

**User UAT (2026-06-01, screenshots):**
1. Carved an enclave (Baronato-17) inside Cuenca (auto-selected by plan 08 D-19).
2. Edited the enclave's Bézier contour, then clicked a neighbouring barony → the pending edit was
   NOT saved ("voltou ao 0" — reverted to initial).
3. Clicked "Aplicar edições" → the new enclave VANISHED and an unfilled HOLE was left in the parent
   (neither the enclave, Cuenca, nor Albarracín filled it).

## Diagnosis so far
- **Backend RULED OUT (for synthetic fixtures).** Added `TestCarveThenEnclaveEdit` to
  `backend/tests/unit/test_manual_edit_carve.py` (commit 5e57c76): carve N + vertex `move` op on N,
  WITH and WITHOUT N's ring in vertices_dict. BOTH pass — `compute()` keeps N and leaves no
  `-1/9999` sentinel. So `manual_edit.compute()` carve+N-edit geometry is not the cause in the
  simple case.
- **Bug is in the real frontend flow.** Two halves, possibly linked:
  - **Persistence (Bug A):** edits to the pending carve-enclave are lost on deselect. N has no
    `original_idx` until Apply, and BezierEditLayer keys edits by `original_idx` / barony in
    baronies.geojson — but N is not in baronies.geojson yet (pending editLog only). So the Bézier
    editor likely can't load/persist N's contour edits.
  - **Hole (Bug B):** on Apply, the op(s) sent for N's edit must be making N degenerate/empty (or
    referencing N by a name/idx the backend can't map → N rebuilt empty → parent hole stays a -1
    sentinel). Real-data geometry near the Cuenca/Albarracín border may also clip N to empty.

## Next steps (dedicated /gsd-debug session)
1. Reproduce live: carve enclave → edit its contour → dump `useEditorStore.editLog` after the edit
   and after click-away (does the N-vertex op persist? what baronyName / vertexIndex / coords?).
2. On Apply, capture the exact POST payload and compare the op's baronyName/idx against what the
   backend resolves (barony_name_to_idx for a pending N with allocated_original_idx).
3. Check whether BezierEditLayer can even target a pending carve-enclave (no original_idx) — likely
   the root of Bug A.
4. Add a backend guard if a malformed/empty N-edit could ever drop N (defensive, even if frontend
   is the trigger).

## Impact
Phase 08.3 headline feature (carve) produces ocean holes in a normal user flow once the user edits
the new enclave. **Blocks "phase 08.3 complete"** even though the condado picker (09) and the
clean-carve path (07/08) pass their own UATs.
