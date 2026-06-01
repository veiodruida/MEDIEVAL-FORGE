---
created: 2026-06-01
source: user UAT during 08.3 carve-enclave-hole debug
status: pending
relates_to: [08.3-07 carve, 08.1 BezierEditLayer, D-27 sentinel rule]
---

# Feature: moving a shared border should prompt "create new barony vs extend neighbour"

**User request (2026-06-01):** when the user edits a contour vertex/segment that is a border
SHARED with another barony (i.e. moving it vacates area that previously belonged to a territory),
the tool should ASK the user what to do with the vacated/gained area:
- **create a new barony** in the vacated gap, OR
- **extend the neighbouring barony** that borders the moved edge to absorb the gap.

## Relationship to the carve-enclave-hole BLOCKER
- This is a UX layer ON TOP of the geometry fix. It is NOT the bug fix.
- The current defect (vacated area becomes ocean `-1`) violates the D-27 sentinel contract
  regardless of UX. Geometry must first guarantee vacated space reverts to the parent (no `-1`
  inside a parent). Only then does the create-vs-extend prompt make sense.
- Do NOT ship the prompt while Apply still writes ocean holes.

## Scope to design (separate plan, after the BLOCKER is resolved)
- Detect when a moved edge is shared with a neighbour (adjacency at the moved segment).
- Surface a choice (Radix dialog / action bar): "Nova baronia no espaço" vs "Estender <vizinha>".
- Wire the choice into the op payload so the backend fills the gap accordingly
  (new carve/create vs neighbour union), never leaving `-1`.
- Real-mouse UAT for both branches.

## Suggested handling
New plan after the carve-enclave-hole blocker is resolved (e.g. 08.3-11 or a decimal phase).
