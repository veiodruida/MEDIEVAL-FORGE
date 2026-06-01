---
created: 2026-06-01
source: user request during 08.3-08 UAT
status: pending
relates_to: [08.3-08 ghost preview, 08.1 BezierEditLayer]
---

# Ghost / pending-preview for barony border edits

**User request (2026-06-01):** apply the same "ghost preview" mechanic built for new-enclave
carve (plan 08.3-08) to BORDER editing of an existing barony — i.e. when the user moves
vertices / Bézier control points of an existing barony's contour, show a persistent pending
preview of the edited contour before "Aplicar edições", so the user is confident the edit is
captured.

## Why it's separate from 08.3
- Plan 08.3-08's ghost renders the pending **create/carve ring** (a brand-new loop) from
  `editLog` `op.ring`.
- Border editing goes through **BezierEditLayer** (phase 08.1) and emits `op:'move'`/`op:'add'`
  vertex ops on an EXISTING barony — there is no single new ring; the pending state is the
  barony's modified contour, which currently only shows live while the Bézier editor is active
  and reverts to the old contour after deselect until Apply.

## Scope to design
- Compute the pending contour for each edited barony from its `editLog` vertex ops (or reuse the
  BezierEditLayer's working geometry) and render it as the same dashed semi-transparent ghost in
  CanvasViewer, cleared on Apply re-render.
- Decide overlay vs replace styling so the user can compare old vs pending.
- Real-mouse UAT: drag a vertex of an existing barony → deselect → ghost of the edited contour
  persists → Apply → ghost clears, real contour updates.

## Suggested handling
New plan in phase 08.3 (e.g. 08.3-10) AFTER 08.3-09 (condado picker), or a small decimal phase —
since it touches the 08.1 Bézier editor it deserves its own scoped plan, not an ad-hoc add-on.
