import { describe, it, expect } from 'vitest'
import { fitPolygonToBezier, buildPolyIndexMap, BEZ_FIT_ERROR } from '../bezierFit'
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
