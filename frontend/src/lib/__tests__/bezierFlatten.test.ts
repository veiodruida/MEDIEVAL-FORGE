import { describe, it, expect } from 'vitest'
import { cubicBezierAt, flattenSegment } from '../bezierFlatten'
import { fitPolygonToBezier, buildPolyIndexMap, BEZ_FIT_ERROR } from '../bezierFit'
import { buildProjectionConfig, canvasToGeo, geoToCanvas } from '../projection'
import { IBERIA_BARONY_RING } from '../../components/canvas/__fixtures__/iberiaBaronyRing'

const projection = buildProjectionConfig(
  { lonMin: -10, lonMax: 3, latMin: 36, latMax: 44 },
  1920,
  1080,
)

describe('flattenSegment count (BEZ-FLATTEN-01)', () => {
  const cubic = fitPolygonToBezier(IBERIA_BARONY_RING, projection, BEZ_FIT_ERROR)[0]

  it('returns exactly M=8 [lon,lat] pairs', () => {
    const out = flattenSegment(cubic, 8, projection)
    expect(out).toHaveLength(8)
    for (const p of out) expect(p).toHaveLength(2)
  })

  it('returns exactly M=25 [lon,lat] pairs', () => {
    const out = flattenSegment(cubic, 25, projection)
    expect(out).toHaveLength(25)
    for (const p of out) expect(p).toHaveLength(2)
  })
})

describe('flattenSegment endpoints map p0/p3 back to geo', () => {
  const cubic = fitPolygonToBezier(IBERIA_BARONY_RING, projection, BEZ_FIT_ERROR)[0]
  const M = 12
  const out = flattenSegment(cubic, M, projection)

  it('returns canvasToGeo(p0) at k=0 within 1e-9°', () => {
    const expected = canvasToGeo(cubic[0][0], cubic[0][1], projection)
    expect(out[0][0]).toBeCloseTo(expected[0], 9)
    expect(out[0][1]).toBeCloseTo(expected[1], 9)
  })

  it('returns canvasToGeo(p3) at k=M-1 within 1e-9°', () => {
    const expected = canvasToGeo(cubic[3][0], cubic[3][1], projection)
    expect(out[M - 1][0]).toBeCloseTo(expected[0], 9)
    expect(out[M - 1][1]).toBeCloseTo(expected[1], 9)
  })
})

describe('cubicBezierAt evaluates endpoints exactly', () => {
  const p0: [number, number] = [0, 0]
  const c1: [number, number] = [10, 20]
  const c2: [number, number] = [30, 40]
  const p3: [number, number] = [50, 60]

  it('returns p0 at t=0', () => {
    expect(cubicBezierAt(p0, c1, c2, p3, 0)).toEqual([0, 0])
  })

  it('returns p3 at t=1', () => {
    const r = cubicBezierAt(p0, c1, c2, p3, 1)
    expect(r[0]).toBeCloseTo(50, 9)
    expect(r[1]).toBeCloseTo(60, 9)
  })
})

describe('density-match fidelity on an unedited segment (BEZ-FLATTEN-02)', () => {
  // Project the ring to px the way fitPolygonToBezier does, then drop the closing dup.
  const pxPts = (() => {
    const pts = IBERIA_BARONY_RING.map(([lon, lat]) => geoToCanvas(lon, lat, projection))
    const last = pts[pts.length - 1]
    const first = pts[0]
    return first[0] === last[0] && first[1] === last[1] ? pts.slice(0, -1) : pts
  })()
  const cubics = fitPolygonToBezier(IBERIA_BARONY_RING, projection, BEZ_FIT_ERROR)
  const ranges = buildPolyIndexMap(pxPts, cubics)

  it('reflattens an unedited segment close to (but not byte-identical to) the original ring vertices', () => {
    // RESEARCH §Pitfall 2 intent: a reflattened unedited segment approximates the
    // original ring but is NOT byte-identical — which is exactly why only DIRTY
    // segments flatten at commit. The plan's literal 1e-4° tolerance is the float-
    // drift figure, which only holds if the fit were exact; at BEZ_FIT_ERROR=30 the
    // fit deviates ~0.004° per vertex by design (≈0.3px, well inside the 30px budget).
    // Tolerance relaxed to 0.01° (Rule 1 deviation, see SUMMARY) — still tight enough
    // that an off-by-one in t-stepping or a broken cubic eval would fail it.
    const FIT_TOLERANCE_DEG = 0.01
    const seg = 0
    const { rangeStart, rangeEnd } = ranges[seg]
    const targetCount = rangeEnd - rangeStart + 1
    const flattened = flattenSegment(cubics[seg], targetCount, projection)

    expect(flattened).toHaveLength(targetCount)
    for (let i = 0; i < targetCount; i++) {
      const [origLon, origLat] = IBERIA_BARONY_RING[rangeStart + i]
      expect(Math.abs(flattened[i][0] - origLon)).toBeLessThan(FIT_TOLERANCE_DEG)
      expect(Math.abs(flattened[i][1] - origLat)).toBeLessThan(FIT_TOLERANCE_DEG)
    }
  })
})
