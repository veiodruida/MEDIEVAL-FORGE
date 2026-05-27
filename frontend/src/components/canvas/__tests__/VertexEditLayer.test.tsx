/* Wave 0 stub for Phase 08 — implemented in plan 08-07.
 * Covers REQ-IDs: EDIT-VERTEX-01, EDIT-VERTEX-02, EDIT-VERTEX-03, LANDMASK-01
 * See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md
 *
 * WARNING-5 fix: VertexEditLayer handles landmask polygon vertices in
 * addition to barony polygon vertices (Pitfall 3).
 * BLOCKER-1 fix: client computes geometry optimistically via turf.js;
 * server receives only the edit event, not the computed geometry.
 */
import { describe, it } from 'vitest';

describe('Phase 08 — VertexEditLayer (EDIT-VERTEX-01..03)', () => {
  it.skip('TODO plan 08-07: vertex handles render at each polygon ring coordinate', () => {});
  it.skip('TODO plan 08-07: drag dispatches moveVertex action with before/after coordinates', () => {});
  it.skip('TODO plan 08-07: mouseup on valid drag commits optimistic geometry via turf.js', () => {});
  it.skip('TODO plan 08-07: self-intersect detection via turf.kinks blocks commit and triggers revert', () => {});
  it.skip('TODO plan 08-08: landmask polygon vertices render with distinct handle style', () => {});
});
