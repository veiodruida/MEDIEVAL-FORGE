---
created: 2026-06-01
source: user request after PEN-EXTEND-01 (08.3-10) approved
status: pending
relates_to: [08.3 pen-tool, 08.1 BezierEditLayer, 08.3-08 ghost preview, 08.3-08 auto-select]
---

# Feature: drag + edit-points a freshly pen-drawn shape BEFORE Apply

**User request (2026-06-01):** after drawing a shape with the pen and CLOSING it, be able to
**drag the whole shape** and **edit its points**, BEFORE clicking "Aplicar edições".

## Current state
- After a pen/freehand close, plan 08.3-08 auto-selects the new barony (post-refetch watcher) and
  the pending ring shows as a dashed ghost overlay. For a CARVE enclave, the selected barony then
  loads into BezierEditLayer so its POINTS can be edited (the carve-enclave-edit flow we fixed this
  session). But:
  - This is post-refetch/post-commit selection, not immediate manipulation of the just-closed ring.
  - There is no DRAG-the-whole-shape (translate) affordance for the pending drawn shape.
  - Behaviour for a CREATE (gap-fill) shape vs CARVE enclave may differ.

## Scope to design (new plan)
- Immediately after close (before Apply), keep the drawn ring as an editable working shape:
  - **Edit points:** drag individual vertices / Bézier handles of the pending ring (reuse
    BezierEditLayer or the PenDrawLayer anchor set) and update the pending op's ring.
  - **Drag whole shape:** a move/translate gesture on the pending shape that offsets the whole ring,
    updating the pending op (a translate of the drawn ring, not a per-vertex op).
- Persist these manipulations into the pending editLog op so Apply uses the manipulated geometry
  (the ghost preview should reflect the live manipulation).
- Works for BOTH create (gap-fill) and carve (enclave) drawn shapes.
- Decide the interaction handoff: pen close → editable-pending state → (drag/edit) → Apply, and how
  Esc/Cancel discards.
- Real-mouse UAT: draw → close → drag the shape + drag a vertex → ghost follows → Apply → final
  geometry matches the manipulated shape; reload persists.

## Relationship to existing follow-ups
- Builds on the ghost preview (08.3-08) and the carve-enclave-edit path (fixed this session).
- Distinct from [[2026-06-01-ghost-preview-for-border-edits]] (that is preview-only for EXISTING
  barony border edits; this is interactive manipulation of a NEW pending pen shape).

## Suggested handling
New plan / small decimal phase after 08.3. Touches PenDrawLayer + BezierEditLayer + the pending-op
model.
