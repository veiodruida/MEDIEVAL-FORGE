/**
 * Phase 08.3 Plan 10 — PEN-EXTEND-01
 *
 * Unit tests for the pure extendGraft helpers:
 *   spliceExtendRing — splice a drawn arc into a closed barony contour
 *   buildExtendVerticesMap — delete stale keys, write new contiguous #0..#N
 *
 * All fixtures are explicit and numeric (project memory: descriptive names + numeric fixtures).
 */

import { describe, it, expect } from 'vitest';
import { spliceExtendRing, buildExtendVerticesMap } from './extendGraft';

// ---------------------------------------------------------------------------
// FIXTURE A — right-edge outward bump
//
// Contour: a unit square with vertices at integer lat/lon
//   (lat=0, lon=0) → (lat=10, lon=0) → (lat=10, lon=10) → (lat=0, lon=10)
//   (open ring, CCW when plotted in lon-right / lat-up space)
//
// Arc: outward bump on the right edge (lon≈10 side), bulging to lon=13
//   arc[0]  = {lat:2, lon:10}   (on the right edge between (0,10) and (10,10))
//   arc[1]  = {lat:5, lon:13}   (the bulge point)
//   arc[2]  = {lat:8, lon:10}   (back on the right edge)
//
// The right edge runs from (lat=0,lon=10) to (lat=10,lon=10).
// The two contact points (lat=2 and lat=8) split the contour into:
//   shorter arc: (2,10) → (8,10) along the right edge  [2 intermediate steps]
//   longer arc:  (8,10) → (10,10) → (0,0) → (0,10) → (2,10)  [larger path]
//
// Expected: the shorter right-edge arc between lat=2 and lat=8 is replaced by the bump,
// so the result includes (5,13) and is LARGER in area than the original square.
// ---------------------------------------------------------------------------

const SQUARE_CONTOUR = [
  { lat: 0, lon: 0 },
  { lat: 10, lon: 0 },
  { lat: 10, lon: 10 },
  { lat: 0, lon: 10 },
];

const BUMP_ARC = [
  { lat: 2, lon: 10 },   // contact A — on right edge
  { lat: 5, lon: 13 },   // bulge
  { lat: 8, lon: 10 },   // contact B — on right edge
];

describe('spliceExtendRing — FIXTURE A: right-edge outward bump', () => {
  it('returns a ring that includes the bump point (5, 13)', () => {
    const result = spliceExtendRing(SQUARE_CONTOUR, BUMP_ARC);
    const hasBump = result.some((p) => Math.abs(p.lat - 5) < 1e-9 && Math.abs(p.lon - 13) < 1e-9);
    expect(hasBump).toBe(true);
  });

  it('result is a closed ring (last point equals first point)', () => {
    const result = spliceExtendRing(SQUARE_CONTOUR, BUMP_ARC);
    expect(result.length).toBeGreaterThanOrEqual(4);
    const first = result[0]!;
    const last = result[result.length - 1]!;
    expect(last.lat).toBeCloseTo(first.lat, 9);
    expect(last.lon).toBeCloseTo(first.lon, 9);
  });

  it('result contains the corner points of the original square NOT on the replaced arc', () => {
    const result = spliceExtendRing(SQUARE_CONTOUR, BUMP_ARC);
    // Original corners (0,0), (10,0), (10,10), (0,10) should be present
    // The right edge from (2,10) to (8,10) is REPLACED; top-right (10,10) and
    // bottom-right (0,10) are on the LONGER arc and should be kept.
    const hasTopRight = result.some((p) => Math.abs(p.lat - 10) < 1e-9 && Math.abs(p.lon - 10) < 1e-9);
    const hasBottomRight = result.some((p) => Math.abs(p.lat - 0) < 1e-9 && Math.abs(p.lon - 10) < 1e-9);
    const hasBottomLeft = result.some((p) => Math.abs(p.lat - 0) < 1e-9 && Math.abs(p.lon - 0) < 1e-9);
    const hasTopLeft = result.some((p) => Math.abs(p.lat - 10) < 1e-9 && Math.abs(p.lon - 0) < 1e-9);
    expect(hasTopRight).toBe(true);
    expect(hasBottomRight).toBe(true);
    expect(hasBottomLeft).toBe(true);
    expect(hasTopLeft).toBe(true);
  });

  it('result does NOT contain any point with lon=10 between lat=2 and lat=8 (right edge replaced)', () => {
    const result = spliceExtendRing(SQUARE_CONTOUR, BUMP_ARC);
    // No intermediate right-edge points between contact indices should exist
    // (contacts themselves may or may not appear, but no lon=10 lat in (2,8))
    const staleEdgePoint = result.some(
      (p) => Math.abs(p.lon - 10) < 1e-9 && p.lat > 2 + 1e-9 && p.lat < 8 - 1e-9,
    );
    expect(staleEdgePoint).toBe(false);
  });

  it('result area is strictly larger than original square area', () => {
    const result = spliceExtendRing(SQUARE_CONTOUR, BUMP_ARC);
    // Shoelace area
    function area(pts: { lat: number; lon: number }[]): number {
      const n = pts.length;
      let a = 0;
      for (let i = 0; i < n; i++) {
        const j = (i + 1) % n;
        a += pts[i]!.lon * pts[j]!.lat - pts[j]!.lon * pts[i]!.lat;
      }
      return Math.abs(a) / 2;
    }
    const originalArea = area(SQUARE_CONTOUR);  // 10*10 = 100
    const newArea = area(result);
    expect(newArea).toBeGreaterThan(originalArea);
  });
});

// ---------------------------------------------------------------------------
// FIXTURE B — shorter-arc tie-break
//
// Contour: asymmetric rectangle with vertices:
//   (0,0), (0,20), (2,20), (2,0)
//   (4 points, CCW in lon-right / lat-up)
//
// Arc: bump on the short left side (lon=0) from (lat=0) to (lat=2):
//   arc[0] = {lat:0, lon:0}   (bottom-left corner)
//   arc[1] = {lat:1, lon:-3}  (bulge outward to the left)
//   arc[2] = {lat:2, lon:0}   (top-left corner)
//
// The two contact points are at (0,0) and (2,0).
// Short arc: (0,0)→(2,0) — just the left edge (length 2 in lat space).
// Long arc:  (2,0)→(2,20)→(0,20)→(0,0) — the three remaining sides (length 2+20+20=42).
//
// Expected: the SHORT left edge (length=2) is replaced, NOT the long path.
// Result must contain (-3 lon) bulge and must NOT contain both bottom-left AND top-left
// as adjacent vertices (since that edge is replaced by the arc).
// ---------------------------------------------------------------------------

const ASYMMETRIC_CONTOUR = [
  { lat: 0, lon: 0 },    // bottom-left  (contact A)
  { lat: 2, lon: 0 },    // top-left     (contact B)
  { lat: 2, lon: 20 },   // top-right
  { lat: 0, lon: 20 },   // bottom-right
];

const LEFT_BUMP_ARC = [
  { lat: 0, lon: 0 },    // contact A = bottom-left
  { lat: 1, lon: -3 },   // bulge left
  { lat: 2, lon: 0 },    // contact B = top-left
];

describe('spliceExtendRing — FIXTURE B: shorter-arc tie-break on asymmetric rectangle', () => {
  it('replaces the SHORT side (left edge) — result contains the lon=-3 bulge', () => {
    const result = spliceExtendRing(ASYMMETRIC_CONTOUR, LEFT_BUMP_ARC);
    const hasBulge = result.some((p) => Math.abs(p.lon - (-3)) < 1e-9 && Math.abs(p.lat - 1) < 1e-9);
    expect(hasBulge).toBe(true);
  });

  it('does NOT replace the long arc — top-right (2,20) and bottom-right (0,20) are kept', () => {
    const result = spliceExtendRing(ASYMMETRIC_CONTOUR, LEFT_BUMP_ARC);
    const hasTopRight = result.some((p) => Math.abs(p.lat - 2) < 1e-9 && Math.abs(p.lon - 20) < 1e-9);
    const hasBottomRight = result.some((p) => Math.abs(p.lat - 0) < 1e-9 && Math.abs(p.lon - 20) < 1e-9);
    expect(hasTopRight).toBe(true);
    expect(hasBottomRight).toBe(true);
  });

  it('result is a closed ring', () => {
    const result = spliceExtendRing(ASYMMETRIC_CONTOUR, LEFT_BUMP_ARC);
    const first = result[0]!;
    const last = result[result.length - 1]!;
    expect(last.lat).toBeCloseTo(first.lat, 9);
    expect(last.lon).toBeCloseTo(first.lon, 9);
  });
});

// ---------------------------------------------------------------------------
// buildExtendVerticesMap — stale-key trap + contiguous #0..#N
// ---------------------------------------------------------------------------

describe('buildExtendVerticesMap — stale-key trap + contiguous write', () => {
  it('removes all prior Barony-1#* keys before writing the new ring', () => {
    // Simulate the stale-key trap: existing store has Barony-1#0..#19 (20 vertices)
    const currentVertices: Record<string, { lat: number; lon: number }> = {};
    for (let i = 0; i < 20; i++) {
      currentVertices[`Barony-1#${i}`] = { lat: i, lon: i };
    }
    // Also an unrelated barony that MUST be preserved
    currentVertices['Barony-0#0'] = { lat: 99, lon: 99 };
    currentVertices['Barony-0#1'] = { lat: 98, lon: 98 };

    const splicedRing = [
      { lat: 0, lon: 0 },
      { lat: 5, lon: 13 },
      { lat: 10, lon: 0 },
      { lat: 0, lon: 0 },   // closed
    ];

    const result = buildExtendVerticesMap(currentVertices, 'Barony-1', splicedRing);

    // No stale Barony-1#* keys beyond the new ring length
    const barony1Keys = Object.keys(result).filter((k) => k.startsWith('Barony-1#'));
    expect(barony1Keys.length).toBe(splicedRing.length);

    // No keys like Barony-1#4, #5, ... #19 from the old ring
    for (let i = splicedRing.length; i < 20; i++) {
      expect(result[`Barony-1#${i}`]).toBeUndefined();
    }

    // Contiguous: keys 0..N-1 present with correct coords
    for (let i = 0; i < splicedRing.length; i++) {
      expect(result[`Barony-1#${i}`]).toEqual({
        lat: splicedRing[i]!.lat,
        lon: splicedRing[i]!.lon,
      });
    }

    // Unrelated barony preserved
    expect(result['Barony-0#0']).toEqual({ lat: 99, lon: 99 });
    expect(result['Barony-0#1']).toEqual({ lat: 98, lon: 98 });
  });

  it('no extend-N synthetic keys appear in the result', () => {
    const currentVertices: Record<string, { lat: number; lon: number }> = {
      'Barony-1#0': { lat: 0, lon: 0 },
    };

    const splicedRing = [
      { lat: 0, lon: 0 },
      { lat: 3, lon: 5 },
      { lat: 0, lon: 0 },
    ];

    const result = buildExtendVerticesMap(currentVertices, 'Barony-1', splicedRing);

    // No extend-N keys (these are the WRONG keys the old stub wrote)
    const extendKeys = Object.keys(result).filter((k) => k.startsWith('extend-'));
    expect(extendKeys.length).toBe(0);
  });

  it('does not mutate the input currentVertices', () => {
    const currentVertices: Record<string, { lat: number; lon: number }> = {
      'Barony-1#0': { lat: 1, lon: 1 },
    };
    const original = { ...currentVertices };
    buildExtendVerticesMap(currentVertices, 'Barony-1', [{ lat: 0, lon: 0 }, { lat: 1, lon: 1 }]);
    expect(currentVertices).toEqual(original);
  });

  it('does not confuse Barony-10 stale keys when target is Barony-1', () => {
    // FACT 2 guard: prefix must be "Barony-1#" (with #) not just "Barony-1"
    const currentVertices: Record<string, { lat: number; lon: number }> = {
      'Barony-1#0': { lat: 0, lon: 0 },
      'Barony-10#0': { lat: 5, lon: 5 },   // must NOT be deleted
    };

    const splicedRing = [{ lat: 1, lon: 1 }, { lat: 2, lon: 2 }];
    const result = buildExtendVerticesMap(currentVertices, 'Barony-1', splicedRing);

    // Barony-10#0 preserved
    expect(result['Barony-10#0']).toEqual({ lat: 5, lon: 5 });
    // Barony-1#0 replaced by new ring
    expect(result['Barony-1#0']).toEqual({ lat: 1, lon: 1 });
  });
});
