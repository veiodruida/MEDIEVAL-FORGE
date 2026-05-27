/* Phase 08 Plan 06b — sharedVertex utility tests (TOPO-04).
 * Rule 1 deviation: stub used 'findSharedVertices'/'propagateVertexMove';
 * plan-spec API is 'buildSharedVertexIndex'/'getCoupledVertices'.
 * Replaced entirely per 08-06a precedent (Deviation #3).
 */
import { describe, it, expect } from 'vitest';
import { buildSharedVertexIndex, getCoupledVertices } from '../sharedVertex';
import type { VertexRef } from '../sharedVertex';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

/** Two baronies sharing exactly one vertex at (0.0, 0.0) — tolerance 1e-6. */
const SHARED_FIXTURE: VertexRef[] = [
  { vertexId: 'a-v0', baronyId: 'barony-A', lat: 0.0, lon: 0.0 },
  { vertexId: 'a-v1', baronyId: 'barony-A', lat: 1.0, lon: 0.0 },
  { vertexId: 'b-v0', baronyId: 'barony-B', lat: 0.0000001, lon: 0.0000001 }, // within 1e-6
  { vertexId: 'b-v1', baronyId: 'barony-B', lat: 0.0, lon: 1.0 },
];

/** Vertex that is clearly isolated — not shared with anyone. */
const ISOLATED_FIXTURE: VertexRef[] = [
  { vertexId: 'c-v0', baronyId: 'barony-C', lat: 10.0, lon: 10.0 },
  { vertexId: 'd-v0', baronyId: 'barony-D', lat: 20.0, lon: 20.0 },
];

describe('buildSharedVertexIndex — coincident vertices within tolerance', () => {
  it('returns Map where a-v0 and b-v0 are coupled (distance ≈ 1.4e-7 < 1e-6)', () => {
    const index = buildSharedVertexIndex(SHARED_FIXTURE, 1e-6);
    // a-v0 and b-v0 are within 1e-6 → they should be coupled
    expect(index.has('a-v0')).toBe(true);
    expect(index.has('b-v0')).toBe(true);
    const aGroup = index.get('a-v0')!;
    expect(aGroup).toContain('a-v0');
    expect(aGroup).toContain('b-v0');
  });

  it('does not add isolated vertices to the index (a-v1 and b-v1 are not coincident)', () => {
    const index = buildSharedVertexIndex(SHARED_FIXTURE, 1e-6);
    // a-v1 at (1.0, 0.0), b-v1 at (0.0, 1.0) — distance = sqrt(2) ≈ 1.41, not shared
    expect(index.has('a-v1')).toBe(false);
    expect(index.has('b-v1')).toBe(false);
  });

  it('returns empty Map when no vertices are within tolerance of each other', () => {
    const index = buildSharedVertexIndex(ISOLATED_FIXTURE, 1e-6);
    expect(index.size).toBe(0);
  });

  it('uses default tolerance 1e-6 when not specified', () => {
    // b-v0 is at (0.0000001, 0.0000001) — distance sqrt(2e-14) ≈ 1.41e-7 < 1e-6
    const index = buildSharedVertexIndex(SHARED_FIXTURE);
    expect(index.has('a-v0')).toBe(true);
  });
});

describe('getCoupledVertices — retrieve group from index', () => {
  it('returns the full coupled group [a-v0, b-v0] for vertex a-v0', () => {
    const index = buildSharedVertexIndex(SHARED_FIXTURE, 1e-6);
    const group = getCoupledVertices(index, 'a-v0');
    expect(group).toContain('a-v0');
    expect(group).toContain('b-v0');
    expect(group.length).toBe(2);
  });

  it('returns [vertexId] singleton for an isolated vertex not in index', () => {
    const index = buildSharedVertexIndex(SHARED_FIXTURE, 1e-6);
    // a-v1 is not shared — getCoupledVertices returns [a-v1] fallback
    const group = getCoupledVertices(index, 'a-v1');
    expect(group).toEqual(['a-v1']);
  });

  it('symmetry: getCoupledVertices(index, b-v0) also contains a-v0', () => {
    const index = buildSharedVertexIndex(SHARED_FIXTURE, 1e-6);
    const group = getCoupledVertices(index, 'b-v0');
    expect(group).toContain('a-v0');
    expect(group).toContain('b-v0');
  });
});

describe('buildSharedVertexIndex — three-way coincidence', () => {
  it('couples all three vertices when three baronies share the same corner', () => {
    // Three baronies all with a vertex at the exact same point (0, 0)
    const threeWay: VertexRef[] = [
      { vertexId: 'x1', baronyId: 'B1', lat: 0, lon: 0 },
      { vertexId: 'x2', baronyId: 'B2', lat: 0, lon: 0 },
      { vertexId: 'x3', baronyId: 'B3', lat: 0, lon: 0 },
    ];
    const index = buildSharedVertexIndex(threeWay, 1e-6);
    const group1 = getCoupledVertices(index, 'x1');
    expect(group1).toContain('x1');
    expect(group1).toContain('x2');
    expect(group1).toContain('x3');
  });
});
