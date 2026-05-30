/**
 * Phase 08.3 Plan 05 — Task 1 TDD (RED)
 * Tests for snapToEdge: nearest-point-on-edge within 12 screen-px (D-05, D-16).
 *
 * snapToEdge is snap-radius=12px zoom-aware (distinct from vertex snap SNAP_SCREEN_PX=5).
 * Default radiusPx=12; accepts radiusPx param so the pen can pass 12.
 */
import { describe, it, expect } from 'vitest';
import { snapToEdge } from './snap';
import type { SnapEdge, SnapEdgeResult } from './snap';

describe('snapToEdge (D-05, D-16 — pen edge snap)', () => {
  // Edge from (0,0) to (0,10) with stageScale=1 → world tol = 12/1 = 12
  const edge: SnapEdge = {
    id1: 'a',
    id2: 'b',
    a: { lat: 0, lon: 0 },
    b: { lat: 10, lon: 0 },
  };

  it('T1: cursor at (lon=0.3, lat=5) snaps to (lon=0, lat=5) on a vertical edge', () => {
    const result = snapToEdge(
      { lat: 5, lon: 0.3 },
      [edge],
      1,   // stageScale
      false,
    );
    expect(result).not.toBeNull();
    const r = result as SnapEdgeResult;
    expect(r.edgeEndpointIds).toEqual(['a', 'b']);
    // nearest point on edge from (lat=0,lon=0)→(lat=10,lon=0) for cursor (lat=5,lon=0.3)
    // is (lat=5, lon=0) — the perpendicular foot
    expect(r.lat).toBeCloseTo(5, 2);
    expect(r.lon).toBeCloseTo(0, 2);
  });

  it('T2: cursor far (lon=20, lat=5) at stageScale=1 — beyond 12 world units → null', () => {
    const result = snapToEdge(
      { lat: 5, lon: 20 },
      [edge],
      1,
      false,
    );
    expect(result).toBeNull();
  });

  it('T3: cursor exactly on the edge endpoint (lat=0, lon=0) → snaps to that endpoint', () => {
    const result = snapToEdge(
      { lat: 0, lon: 0 },
      [edge],
      1,
      false,
    );
    expect(result).not.toBeNull();
    const r = result as SnapEdgeResult;
    expect(r.lat).toBeCloseTo(0, 4);
    expect(r.lon).toBeCloseTo(0, 4);
  });

  it('T4: altHeld=true → always returns null (snap disabled)', () => {
    const result = snapToEdge(
      { lat: 5, lon: 0.3 },
      [edge],
      1,
      true, // altHeld
    );
    expect(result).toBeNull();
  });

  it('T5: empty edge list → null', () => {
    const result = snapToEdge({ lat: 5, lon: 0.3 }, [], 1, false);
    expect(result).toBeNull();
  });

  it('T6: zoom-aware — at stageScale=0.1 worldTol=120; cursor at lon=15 lat=5 snaps (15<120)', () => {
    const result = snapToEdge(
      { lat: 5, lon: 15 },
      [edge],
      0.1, // stageScale=0.1 → worldTol=12/0.1=120
      false,
    );
    expect(result).not.toBeNull();
  });

  it('T7: t clamped to [0,1] — cursor beyond endpoint clamps to endpoint', () => {
    // cursor far past lat=10 end → nearest point on segment is (lat=10, lon=0)
    const result = snapToEdge(
      { lat: 11, lon: 0.5 },
      [edge],
      1,
      false,
    );
    // world distance from (lat=11,lon=0.5) to (lat=10,lon=0) =
    // sqrt((0.5^2) + 1^2) ≈ 1.118 — within 12
    expect(result).not.toBeNull();
    const r = result as SnapEdgeResult;
    expect(r.lat).toBeCloseTo(10, 2);
    expect(r.lon).toBeCloseTo(0, 2);
  });

  it('T8: picks the nearest edge when multiple edges provided', () => {
    const edgeFar: SnapEdge = {
      id1: 'c',
      id2: 'd',
      a: { lat: 0, lon: 5 },
      b: { lat: 10, lon: 5 },
    };
    // cursor at (lat=5, lon=0.3) — close to first edge (lon=0), far from second (lon=5)
    const result = snapToEdge(
      { lat: 5, lon: 0.3 },
      [edgeFar, edge],
      1,
      false,
    );
    expect(result).not.toBeNull();
    const r = result as SnapEdgeResult;
    expect(r.edgeEndpointIds).toEqual(['a', 'b']); // first edge (lon=0), not edgeFar
  });
});
