/* Wave 0 stub for Phase 08 — implemented in plan 08-06b.
 * Covers REQ-IDs: TOPO-03, TOPO-04, PERF-01, UX-01
 * See: .planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-VALIDATION.md
 *
 * Review-4 (Gemini + OpenCode): snap-jitter zoom check (UAT step 5b).
 * Scale-aware snap: snap threshold = base_pixels / zoom_scale so the
 * visual snap radius is constant regardless of zoom level.
 */
import { describe, it } from 'vitest';

describe('Phase 08 — snap utility (TOPO-03, TOPO-04, PERF-01)', () => {
  it.skip('TODO plan 08-06b: snapToVertex returns nearest vertex when within threshold distance', () => {});
  it.skip('TODO plan 08-06b: snapToVertex returns null when no vertex is within threshold', () => {});
  it.skip('TODO plan 08-06b: snap threshold scales inversely with zoom level (scale-aware)', () => {});
  it.skip('TODO plan 08-06b: snapToVertex at zoom=2 has half the pixel-space radius of zoom=1', () => {});
});
