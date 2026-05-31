/**
 * Phase 08.3 Plan 05 — Task 1 TDD (RED)
 * Tests for flattenPenPath: PenAnchor[] → closed {lat,lon}[] ring.
 *
 * Reuses flattenSegment from bezierFlatten.ts for curve anchors.
 * Returns a closed ring (first point == last point, or explicitly appended).
 */
import { describe, it, expect } from 'vitest';
import { flattenPenPath, flattenPenPathOpen } from './penFlatten';
import type { PenAnchor } from './penFlatten';

// ---- minimal projection for flattenSegment (lat/lon pass-through space) -----
// Use a simple 1000×1000 map for testing; geoToCanvas / canvasToGeo round-trip.
const PROJECTION = {
  lonMin: -10,
  lonMax: 10,
  latMin: 30,
  latMax: 50,
  mapW: 1000,
  mapH: 1000,
  lonScale: Math.cos((40 * Math.PI) / 180),
};

describe('flattenPenPath (PEN-CURVE-01)', () => {
  it('T1: 3 straight anchors → triangle ring with ≥ 3 distinct points, closed (first == last)', () => {
    const anchors: PenAnchor[] = [
      { lat: 40, lon: -8, type: 'straight' },
      { lat: 41, lon: -7, type: 'straight' },
      { lat: 40, lon: -6, type: 'straight' },
    ];
    const ring = flattenPenPath(anchors, PROJECTION);
    // ring must include all 3 anchor positions
    expect(ring.length).toBeGreaterThanOrEqual(3);
    // ring must be closed: first == last
    const first = ring[0];
    const last = ring[ring.length - 1];
    expect(last.lat).toBeCloseTo(first.lat, 4);
    expect(last.lon).toBeCloseTo(first.lon, 4);
  });

  it('T2: 3 straight anchors include the anchor coords themselves', () => {
    const anchors: PenAnchor[] = [
      { lat: 40, lon: -8, type: 'straight' },
      { lat: 41, lon: -7, type: 'straight' },
      { lat: 40, lon: -6, type: 'straight' },
    ];
    const ring = flattenPenPath(anchors, PROJECTION);
    // First anchor should appear in the ring
    expect(ring.some((p) => Math.abs(p.lat - 40) < 0.05 && Math.abs(p.lon - (-8)) < 0.05)).toBe(true);
  });

  it('T3: 1 curve anchor segment (2 anchors with cp1/cp2) → multiple intermediate points', () => {
    // A single curve segment between 2 anchors; cp1/cp2 create a Bézier arc
    const anchors: PenAnchor[] = [
      {
        lat: 40,
        lon: -8,
        type: 'curve',
        cp1: { lat: 40.5, lon: -8.5 },
        cp2: { lat: 40.5, lon: -7.5 },
      },
      {
        lat: 41,
        lon: -7,
        type: 'straight',
      },
    ];
    const ring = flattenPenPath(anchors, PROJECTION);
    // A curve segment should produce more than just the 2 endpoints
    expect(ring.length).toBeGreaterThan(3);
    // Ring is closed
    const first = ring[0];
    const last = ring[ring.length - 1];
    expect(last.lat).toBeCloseTo(first.lat, 4);
    expect(last.lon).toBeCloseTo(first.lon, 4);
  });

  it('T4: single anchor → returns empty or minimal ring (degenerate, no crash)', () => {
    const anchors: PenAnchor[] = [
      { lat: 40, lon: -8, type: 'straight' },
    ];
    // Should not throw; may return [] or a degenerate ring
    expect(() => flattenPenPath(anchors, PROJECTION)).not.toThrow();
  });

  it('T5: pure function — no imports from stores or react-konva', () => {
    // This is a module-level assertion: if the file imports from stores/react-konva, tsc would error.
    // At runtime we just confirm the function returns an array without side effects.
    const anchors: PenAnchor[] = [
      { lat: 40, lon: -8, type: 'straight' },
      { lat: 41, lon: -7, type: 'straight' },
      { lat: 40, lon: -6, type: 'straight' },
    ];
    const result1 = flattenPenPath(anchors, PROJECTION);
    const result2 = flattenPenPath(anchors, PROJECTION);
    // Pure: same input → same output
    expect(JSON.stringify(result1)).toBe(JSON.stringify(result2));
  });

  it('T6: 4-anchor mixed ring has all 4 anchor positions within the ring', () => {
    const anchors: PenAnchor[] = [
      { lat: 40, lon: -9, type: 'straight' },
      { lat: 41, lon: -9, type: 'straight' },
      { lat: 41, lon: -7, type: 'straight' },
      { lat: 40, lon: -7, type: 'straight' },
    ];
    const ring = flattenPenPath(anchors, PROJECTION);
    expect(ring.length).toBeGreaterThanOrEqual(4);
    // Verify ring closure
    expect(ring[ring.length - 1].lat).toBeCloseTo(ring[0].lat, 4);
  });
});

describe('flattenPenPathOpen (PEN-CURVE-01 live preview)', () => {
  it('T7: open path is NOT closed — last point is the final anchor, not the first', () => {
    const anchors: PenAnchor[] = [
      { lat: 40, lon: -8, type: 'straight' },
      { lat: 41, lon: -7, type: 'straight' },
      { lat: 40, lon: -6, type: 'straight' },
    ];
    const open = flattenPenPathOpen(anchors, PROJECTION);
    // Last point is the final anchor (40, -6), not the first anchor (40, -8).
    expect(open[open.length - 1].lat).toBeCloseTo(40, 4);
    expect(open[open.length - 1].lon).toBeCloseTo(-6, 4);
    // Open path does NOT wrap back to the first point.
    const first = open[0];
    const last = open[open.length - 1];
    expect(Math.abs(last.lon - first.lon)).toBeGreaterThan(0.5);
  });

  it('T8: a curve segment is bezier-sampled (more points than the 2 straight endpoints)', () => {
    const anchors: PenAnchor[] = [
      {
        lat: 40,
        lon: -8,
        type: 'curve',
        cp1: { lat: 40.8, lon: -8 },
        cp2: { lat: 40.8, lon: -7 },
      },
      { lat: 41, lon: -7, type: 'straight' },
    ];
    const open = flattenPenPathOpen(anchors, PROJECTION);
    // One curve segment → sampled into many intermediate points, not just 2 endpoints.
    expect(open.length).toBeGreaterThan(3);
  });

  it('T9: open preview shares the non-closing segments with the closed ring', () => {
    // Both functions must sample the same per-segment cubic so display == committed shape.
    const anchors: PenAnchor[] = [
      { lat: 40, lon: -8, type: 'curve', cp1: { lat: 40.5, lon: -8.5 }, cp2: { lat: 40.5, lon: -7.5 } },
      { lat: 41, lon: -7, type: 'straight' },
      { lat: 40, lon: -6, type: 'straight' },
    ];
    const open = flattenPenPathOpen(anchors, PROJECTION);
    const closed = flattenPenPath(anchors, PROJECTION);
    // The open preview must be a strict prefix-shape of the closed ring's leading segments:
    // its first sampled point matches the closed ring's first sampled point.
    expect(open[0].lat).toBeCloseTo(closed[0].lat, 6);
    expect(open[0].lon).toBeCloseTo(closed[0].lon, 6);
    // Open path is shorter than the closed ring (no closing segment + no wrap dup).
    expect(open.length).toBeLessThan(closed.length);
  });
});
