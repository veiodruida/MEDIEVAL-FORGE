/**
 * Phase 08.3 Plan 07 — UAT-fix regression for resolvePenSnap (pen anchor-drop snapping).
 *
 * Root cause this pins: the pen layer fed the euclidean snap primitives lat/lon DEGREES,
 * while their tolerance (radiusPx / stageScale) is in MAP-PIXEL units. A degree distance
 * (Iberia ≈ 0.0x deg per click-gap) compared against a ~12 pixel-derived tolerance made
 * the snap radius ≈ the whole peninsula: every interior carve click snapped to the parent
 * barony's border, and the close gesture snapped the closing click to the border instead of
 * the first anchor → the territory could never be closed.
 *
 * resolvePenSnap converts cursor + candidates to map-pixels via the projection, so a
 * 12-SCREEN-px radius means 12 screen-px — not 12 degrees. These tests assert the radius is
 * honored in PIXELS, with explicit numeric fixtures.
 *
 * Fixture projection: lon/lat 0..10 → 1000×1000 map-px. With lonMin=0 the lonScale cancels,
 * giving the clean mapping  x = lon*100,  y = 1000 - lat*100  (1 degree = 100 map-px, both axes).
 */
import { describe, it, expect } from 'vitest';
import { resolvePenSnap } from './snap';
import type { SnapCandidate, SnapEdge } from './snap';
import { buildProjectionConfig } from './projection';

const projection = buildProjectionConfig(
  { lonMin: 0, lonMax: 10, latMin: 0, latMax: 10 },
  1000,
  1000,
);
// Sanity: 1 degree == 100 map-px on both axes for this square fixture.
// geoToCanvas(5,5) === [500, 500].

const PEN_RADIUS_PX = 12;
const SCALE_1 = 1;

describe('resolvePenSnap — vertex snap honors a 12 SCREEN-px radius in pixel space', () => {
  const vertex: SnapCandidate = { id: 'baronyX#3', lat: 5, lon: 5 }; // → map-px (500, 500)

  it('snaps a cursor 5 map-px away (0.05 deg) to the vertex (5 px <= 12 px)', () => {
    // cursor at lon=5.05 → x=505, lat=5 → y=500 : 5 px from the vertex
    const r = resolvePenSnap({ lat: 5, lon: 5.05 }, [vertex], [], projection, SCALE_1, false, PEN_RADIUS_PX);
    expect(r.snapVertex).toBeDefined();
    expect(r.snapVertex?.id).toBe('baronyX#3');
    expect(r.lat).toBeCloseTo(5, 6);
    expect(r.lon).toBeCloseTo(5, 6);
  });

  it('does NOT snap a cursor 50 map-px away (0.5 deg) — the exact regression the degree bug hid', () => {
    // cursor at lon=5.5 → x=550 : 50 px from the vertex. Old degree code saw 0.5 < 12 and snapped.
    const r = resolvePenSnap({ lat: 5, lon: 5.5 }, [vertex], [], projection, SCALE_1, false, PEN_RADIUS_PX);
    expect(r.snapVertex).toBeUndefined();
    expect(r.snapEdge).toBeUndefined();
    // returns the cursor unchanged
    expect(r.lat).toBeCloseTo(5, 6);
    expect(r.lon).toBeCloseTo(5.5, 6);
  });
});

describe('resolvePenSnap — edge snap honors the pixel radius', () => {
  // Horizontal edge at lat=5 from lon=4 (x=400) to lon=6 (x=600), at map-px y=500.
  const edge: SnapEdge = {
    id1: 'baronyX#7',
    id2: 'baronyX#8',
    a: { lat: 5, lon: 4 },
    b: { lat: 5, lon: 6 },
  };

  it('snaps a cursor 5 px above the edge to its perpendicular foot (lon=5, lat=5)', () => {
    // cursor lon=5 (x=500), lat=5.05 (y=495) : 5 px above the edge
    const r = resolvePenSnap({ lat: 5.05, lon: 5 }, [], [edge], projection, SCALE_1, false, PEN_RADIUS_PX);
    expect(r.snapEdge).toBeDefined();
    expect(r.snapEdge?.edgeEndpointIds).toEqual(['baronyX#7', 'baronyX#8']);
    expect(r.lat).toBeCloseTo(5, 6);
    expect(r.lon).toBeCloseTo(5, 6);
  });

  it('does NOT snap a cursor 60 px from the edge (0.6 deg)', () => {
    // cursor lat=5.6 (y=440) : 60 px above the edge
    const r = resolvePenSnap({ lat: 5.6, lon: 5 }, [], [edge], projection, SCALE_1, false, PEN_RADIUS_PX);
    expect(r.snapEdge).toBeUndefined();
    expect(r.lat).toBeCloseTo(5.6, 6);
    expect(r.lon).toBeCloseTo(5, 6);
  });
});

describe('resolvePenSnap — scale-aware tolerance (proves pixel units, not degrees)', () => {
  const vertex: SnapCandidate = { id: 'v', lat: 5, lon: 5 }; // map-px (500, 500)

  it('a cursor 8 map-px away snaps at stageScale=1 (tol 12 px) but NOT at stageScale=2 (tol 6 px)', () => {
    // cursor lon=5.08 → x=508 : 8 map-px from the vertex
    const cursor = { lat: 5, lon: 5.08 };

    const atScale1 = resolvePenSnap(cursor, [vertex], [], projection, 1, false, PEN_RADIUS_PX);
    expect(atScale1.snapVertex).toBeDefined(); // 8 px <= 12/1

    const atScale2 = resolvePenSnap(cursor, [vertex], [], projection, 2, false, PEN_RADIUS_PX);
    expect(atScale2.snapVertex).toBeUndefined(); // 8 px > 12/2 = 6
  });
});

describe('resolvePenSnap — Alt disables snap (D-28)', () => {
  const vertex: SnapCandidate = { id: 'v', lat: 5, lon: 5 };

  it('returns the cursor unchanged when altHeld is true, even on top of a candidate', () => {
    const r = resolvePenSnap({ lat: 5, lon: 5 }, [vertex], [], projection, SCALE_1, true, PEN_RADIUS_PX);
    expect(r.snapVertex).toBeUndefined();
    expect(r.snapEdge).toBeUndefined();
    expect(r.lat).toBeCloseTo(5, 6);
    expect(r.lon).toBeCloseTo(5, 6);
  });
});
