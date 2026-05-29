import { describe, it, expect } from 'vitest'
import { fitPolygonToBezier, buildPolyIndexMap, BEZ_FIT_ERROR, splitPolyRange, findNearestSegmentAndVertex } from '../bezierFit'
import { buildProjectionConfig, geoToCanvas } from '../projection'
import {
  IBERIA_BARONY_RING,
  RING_100,
} from '../../components/canvas/__fixtures__/iberiaBaronyRing'

// Iberia 868 bbox + 1920×1080 lookup resolution. Fit happens in this px space.
const projection = buildProjectionConfig(
  { lonMin: -10, lonMax: 3, latMin: 36, latMax: 44 },
  1920,
  1080,
)

describe('fitPolygonToBezier (BEZ-FIT-01)', () => {
  it('returns between 3 and 40 cubic segments for a 100-vertex closed ring', () => {
    const cubics = fitPolygonToBezier(RING_100, projection, 30)
    expect(cubics.length).toBeGreaterThanOrEqual(3)
    expect(cubics.length).toBeLessThanOrEqual(40)
  })

  it('returns cubics shaped as [[x,y],[x,y],[x,y],[x,y]] in canvas px', () => {
    const cubics = fitPolygonToBezier(RING_100, projection, 30)
    for (const cubic of cubics) {
      expect(cubic).toHaveLength(4)
      for (const point of cubic) {
        expect(point).toHaveLength(2)
        expect(typeof point[0]).toBe('number')
        expect(typeof point[1]).toBe('number')
      }
    }
  })
})

describe('fitPolygonToBezier calibration against the real Iberia barony ring (A1)', () => {
  it('fits the IBERIA_BARONY_RING fixture to a count inside the 4..30 normal band at BEZ_FIT_ERROR', () => {
    // Empirical lock for Assumption A1 / RESEARCH Open Q1. BEZ_FIT_ERROR=30
    // produces 4 cubics on this σ=3.0-shaped ring. If this assertion ever lands
    // outside the band, retune BEZ_FIT_ERROR in bezierFit.ts and document in SUMMARY.
    const cubics = fitPolygonToBezier(IBERIA_BARONY_RING, projection, BEZ_FIT_ERROR)
    expect(cubics.length).toBeGreaterThanOrEqual(4)
    expect(cubics.length).toBeLessThanOrEqual(30)
  })

  it('locks BEZ_FIT_ERROR at the calibrated default of 30', () => {
    expect(BEZ_FIT_ERROR).toBe(30)
  })
})

describe('fitPolygonToBezier <3-point security guard (T-08.1-01-01)', () => {
  it('returns [] for a 2-point input and does NOT throw', () => {
    const twoPoints: Array<[number, number]> = [
      [-7.5, 40.5],
      [-7.4, 40.6],
    ]
    expect(() => fitPolygonToBezier(twoPoints, projection, 30)).not.toThrow()
    expect(fitPolygonToBezier(twoPoints, projection, 30)).toEqual([])
  })

  it('returns [] for an empty input and does NOT throw', () => {
    expect(fitPolygonToBezier([], projection, 30)).toEqual([])
  })
})

describe('buildPolyIndexMap (BEZ-INDEX-01)', () => {
  // Build the px input the way fitPolygonToBezier does internally: project to px,
  // then drop the closing duplicate so indices align with the fitted cubics.
  const pxPts = (() => {
    const pts = IBERIA_BARONY_RING.map(([lon, lat]) => geoToCanvas(lon, lat, projection))
    const last = pts[pts.length - 1]
    const first = pts[0]
    return first[0] === last[0] && first[1] === last[1] ? pts.slice(0, -1) : pts
  })()
  const cubics = fitPolygonToBezier(IBERIA_BARONY_RING, projection, BEZ_FIT_ERROR)
  const ranges = buildPolyIndexMap(pxPts, cubics)

  it('returns exactly one PolyRange per cubic', () => {
    expect(ranges).toHaveLength(cubics.length)
  })

  it('starts the first range at index 0', () => {
    expect(ranges[0].rangeStart).toBe(0)
  })

  it('ends the last range at inputPxPts.length - 1 (full coverage)', () => {
    expect(ranges[ranges.length - 1].rangeEnd).toBe(pxPts.length - 1)
  })

  it('produces contiguous ranges with no gap and no overlap', () => {
    for (let j = 0; j < ranges.length - 1; j++) {
      expect(ranges[j].rangeEnd).toBe(ranges[j + 1].rangeStart)
    }
  })

  it('produces monotonically non-decreasing range bounds', () => {
    for (const r of ranges) {
      expect(r.rangeEnd).toBeGreaterThanOrEqual(r.rangeStart)
    }
  })
})

describe('buildPolyIndexMap closing-segment coverage (G1 guard)', () => {
  // Build pxPts with a closing duplicate to simulate the full ring with M points
  // where pxPts[0] === pxPts[M-1] (the duplicate appended by fitPolygonToBezier caller).
  // The closing segment (last cubic) must map to rangeEnd = pxPts.length - 1.
  const rawPts = IBERIA_BARONY_RING.map(([lon, lat]) => geoToCanvas(lon, lat, projection)) as Array<[number, number]>
  // Ensure the ring has the closing duplicate (same as first point).
  const pxPtsWithDup: Array<[number, number]> = [...rawPts]
  if (pxPtsWithDup[0][0] !== pxPtsWithDup[pxPtsWithDup.length - 1][0] ||
      pxPtsWithDup[0][1] !== pxPtsWithDup[pxPtsWithDup.length - 1][1]) {
    pxPtsWithDup.push([pxPtsWithDup[0][0], pxPtsWithDup[0][1]])
  }
  const cubics = fitPolygonToBezier(IBERIA_BARONY_RING, projection, BEZ_FIT_ERROR)
  const ranges = buildPolyIndexMap(pxPtsWithDup, cubics)

  it('closing segment rangeEnd equals inputPxPts.length - 1 (covers the closing-duplicate vertex)', () => {
    // DISCRIMINATING: catches a forward-scan regression where pxPts[M-2] is found early,
    // leaving vertex M-1 (the closing duplicate) without a range owner.
    expect(ranges[ranges.length - 1].rangeEnd).toBe(pxPtsWithDup.length - 1)
  })

  it('ranges.length equals cubics.length even with closing duplicate in pxPts', () => {
    expect(ranges).toHaveLength(cubics.length)
  })

  it('interior ranges are contiguous (range[j].rangeEnd === range[j+1].rangeStart) for all j < N-1', () => {
    for (let j = 0; j < ranges.length - 1; j++) {
      expect(ranges[j].rangeEnd).toBe(ranges[j + 1].rangeStart)
    }
  })
})

// ── splitPolyRange (08.1-06 G3) ────────────────────────────────────────────────

describe('splitPolyRange (G3 — split one PolyRange into two contiguous sub-ranges)', () => {
  it('returns two sub-ranges with left.rangeEnd === right.rangeStart (shared endpoint)', () => {
    // Explicit numeric fixture: {4,9} split at 6 → [{4,6},{6,9}]
    const [left, right] = splitPolyRange({ rangeStart: 4, rangeEnd: 9 }, 6)
    expect(left.rangeEnd).toBe(right.rangeStart)
  })

  it('preserves full coverage: left.rangeStart === original.rangeStart, right.rangeEnd === original.rangeEnd', () => {
    const range = { rangeStart: 4, rangeEnd: 9 }
    const [left, right] = splitPolyRange(range, 6)
    expect(left.rangeStart).toBe(4)
    expect(right.rangeEnd).toBe(9)
  })

  it('split at 6 gives left=[4,6] and right=[6,9] — exact numeric fixture', () => {
    const [left, right] = splitPolyRange({ rangeStart: 4, rangeEnd: 9 }, 6)
    expect(left).toEqual({ rangeStart: 4, rangeEnd: 6 })
    expect(right).toEqual({ rangeStart: 6, rangeEnd: 9 })
  })

  it('clamps splitIndex === rangeStart upward so neither sub-range is zero-width', () => {
    // splitIndex=4 (equals rangeStart=4) → clamped to rangeStart+1=5
    const [left, right] = splitPolyRange({ rangeStart: 4, rangeEnd: 9 }, 4)
    expect(left.rangeStart).toBe(4)
    expect(left.rangeEnd).toBeGreaterThan(4) // no zero-width left sub-range
    expect(right.rangeEnd).toBe(9)
    expect(left.rangeEnd).toBe(right.rangeStart)
  })

  it('clamps splitIndex === rangeEnd downward so right sub-range is not zero-width', () => {
    // splitIndex=9 (equals rangeEnd=9) → clamped to rangeEnd-1=8
    const [left, right] = splitPolyRange({ rangeStart: 4, rangeEnd: 9 }, 9)
    expect(right.rangeEnd).toBe(9)
    expect(right.rangeStart).toBeLessThan(9) // no zero-width right sub-range
    expect(left.rangeStart).toBe(4)
    expect(left.rangeEnd).toBe(right.rangeStart)
  })

  it('clamps splitIndex well below rangeStart', () => {
    // splitIndex=-1 → clamped to rangeStart+1=5
    const [left, right] = splitPolyRange({ rangeStart: 4, rangeEnd: 9 }, -1)
    expect(left.rangeStart).toBe(4)
    expect(left.rangeEnd).toBeGreaterThan(4)
    expect(right.rangeEnd).toBe(9)
    expect(left.rangeEnd).toBe(right.rangeStart)
  })
})

// ── findNearestSegmentAndVertex (08.1-06 G3) ───────────────────────────────────

describe('findNearestSegmentAndVertex (G3 — locate segment + snap vertex for dbl-click insert)', () => {
  // Explicit 3-anchor fixture in a simple px space (no projection required — pure px).
  // Anchors form a triangle ring:
  //   anchor 0: (0,0),   cp1=(−5,−2), cp2=(5,−2)
  //   anchor 1: (100,0), cp1=(90,−5), cp2=(110,5)
  //   anchor 2: (50,80), cp1=(40,70), cp2=(60,70)
  // Segment 0 (anchor 0 → anchor 1): cubic [A0.anchorPx, A0.cp2Px, A1.cp1Px, A1.anchorPx]
  // Segment 1 (anchor 1 → anchor 2): cubic [A1.anchorPx, A1.cp2Px, A2.cp1Px, A2.anchorPx]
  // Segment 2 (anchor 2 → anchor 0): closing segment — wraps back to anchor 0
  //   cubic [A2.anchorPx, A2.cp2Px, A0.cp1Px, A0.anchorPx]
  //
  // pxPts simulates the original polygon vertex list (15 pts for segment 0: indices 0..10,
  // then 3 pts per segment 1 and 2 for the other segments; simplified to keep the fixture small).
  // Segment 0 uses range {0,10}; segment 1 uses {10,13}; segment 2 (closing) uses {13,15}.

  const anchors = [
    { anchorPx: [0, 0] as [number, number], cp1Px: [-5, -2] as [number, number], cp2Px: [5, -2] as [number, number], polyRangeStart: 0, polyRangeEnd: 10 },
    { anchorPx: [100, 0] as [number, number], cp1Px: [90, -5] as [number, number], cp2Px: [110, 5] as [number, number], polyRangeStart: 10, polyRangeEnd: 13 },
    { anchorPx: [50, 80] as [number, number], cp1Px: [40, 70] as [number, number], cp2Px: [60, 70] as [number, number], polyRangeStart: 13, polyRangeEnd: 15 },
  ]

  // Build pxPts: 16 pts, indices 0..15.
  // Segment 0 spans indices 0..10 (11 pts, several interior vertices near the midpoint at ~(50,0)).
  const pxPts: Array<[number, number]> = []
  for (let i = 0; i <= 10; i++) {
    pxPts.push([i * 10, 0]) // 0,10,20,...,100 along x axis
  }
  // Segment 1 spans indices 10..13
  pxPts.push([80, 30])   // 11
  pxPts.push([65, 60])   // 12
  pxPts.push([50, 80])   // 13
  // Segment 2 (closing) spans indices 13..15
  pxPts.push([25, 40])   // 14
  pxPts.push([0, 0])     // 15 — closing duplicate of anchor 0

  it('click near segment 0 midpoint returns segmentIdx === 0', () => {
    // Midpoint of segment 0 cubic at t≈0.5 is approximately (50, 0) given the nearly-flat
    // control points. Click at (50, 3) — within 8px tolerance.
    const result = findNearestSegmentAndVertex([50, 3], anchors, pxPts)
    expect(result).not.toBeNull()
    expect(result!.segmentIdx).toBe(0)
  })

  it('splitVertexIndex is strictly inside the target segment range (rangeStart < idx < rangeEnd)', () => {
    const result = findNearestSegmentAndVertex([50, 3], anchors, pxPts)
    expect(result).not.toBeNull()
    const { segmentIdx, splitVertexIndex } = result!
    const a = anchors[segmentIdx]
    expect(splitVertexIndex).toBeGreaterThan(a.polyRangeStart)
    expect(splitVertexIndex).toBeLessThan(a.polyRangeEnd)
  })

  it('returns null when click is far from all segments (>8px tolerance)', () => {
    // Click at (500, 500) — well outside any cubic in this fixture.
    const result = findNearestSegmentAndVertex([500, 500], anchors, pxPts)
    expect(result).toBeNull()
  })

  it('closing segment (segmentIdx === N-1 === 2) is reachable — click near its midpoint returns segmentIdx === 2', () => {
    // DISCRIMINATING test for the G1+G2 closing-segment-is-editable requirement.
    // Segment 2 (closing): cubic [A2.anchorPx=(50,80), A2.cp2Px=(60,70), A0.cp1Px=(-5,-2), A0.anchorPx=(0,0)]
    // At t=0.5 the cubic evaluates near (28, 37) (rough estimate for de Casteljau on these pts).
    // We click at (25, 40) — that is also pxPts[14], which lies in the closing segment's range {13,15}.
    // If the loop only covers s < N-1 (old bug), this click is silently dropped; with s < N it hits seg 2.
    const result = findNearestSegmentAndVertex([25, 40], anchors, pxPts, 20)
    expect(result).not.toBeNull()
    // MUST identify the closing segment (index 2 = N-1)
    expect(result!.segmentIdx).toBe(2)
    // split vertex must lie strictly inside the closing segment range {13,15}
    expect(result!.splitVertexIndex).toBeGreaterThan(13)
    expect(result!.splitVertexIndex).toBeLessThan(15)
  })
})
