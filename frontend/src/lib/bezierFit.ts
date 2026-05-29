/**
 * Pure curve-fitting wrapper around fit-curve for the Bézier contour editor (Phase 08.1).
 *
 * The fit happens in CANVAS PIXEL space (not geo space) to avoid near-pole distortion
 * (UI-SPEC Note #3, RESEARCH §Pattern 1). Geo coords only materialize again at the
 * flatten step (bezierFlatten.ts). No React, no Konva, no store — pure functions only.
 *
 * fit-curve does NOT return which polygon vertices each cubic spans, so
 * `buildPolyIndexMap` recovers that mapping with an O(N) post-fit scan
 * (RESEARCH §Split-Index Gap, Option A).
 */

import fitCurve from 'fit-curve'
import { geoToCanvas, type ProjectionConfig } from './projection'
import { cubicBezierAt } from './bezierFlatten'

/** A cubic Bézier segment in canvas px: [p0, c1, c2, p3]. */
export type BezierCubic = [
  [number, number],
  [number, number],
  [number, number],
  [number, number],
]

/** Inclusive original-polygon vertex index range covered by one cubic. */
export interface PolyRange {
  rangeStart: number
  rangeEnd: number
}

/**
 * Calibrated px error tolerance for fit-curve (RESEARCH §6, Open Q1).
 * At 30 the real Iberia barony fixture (σ=3.0 shape) fits to 4 cubics in 1920×1080
 * px space — inside the 4..30 "normal" band. Retune only if the fixture calibration
 * test forces it, and document the change in the plan SUMMARY.
 */
export const BEZ_FIT_ERROR = 30

/**
 * Fit a closed [lon, lat] polygon ring to cubic Bézier segments in canvas px space.
 * Returns [] for degenerate (< 3 point) input — fit-curve throws on those.
 */
export function fitPolygonToBezier(
  coords: Array<[number, number]>,
  projection: ProjectionConfig,
  error: number = BEZ_FIT_ERROR,
): BezierCubic[] {
  // Security guard (T-08.1-01-01): fit-curve throws on < 3 points.
  if (coords.length < 3) return []

  // Project to px BEFORE fitting (UI-SPEC Note #3 — fit is in px space).
  const pts: number[][] = coords.map(([lon, lat]) => geoToCanvas(lon, lat, projection))

  // Drop the closing duplicate so the ring is an open polyline (RESEARCH §Pattern 1, Approach A).
  const last = pts[pts.length - 1]
  const first = pts[0]
  const open =
    pts.length > 1 && first[0] === last[0] && first[1] === last[1]
      ? pts.slice(0, -1)
      : pts

  // Over-dense guard (T-08.1-01-02): raise tolerance rather than freeze the UI.
  const fitError = open.length > 1500 ? error * 4 : error

  return fitCurve(open, fitError) as BezierCubic[]
}

/**
 * Recover, per cubic, the contiguous original-vertex index range it covers
 * (RESEARCH §Split-Index Gap, Option A). O(N) forward scan: each cubic's endpoint
 * p3 equals some input vertex; the last cubic is forced to close on the final index
 * to guarantee full coverage under float drift.
 */
export function buildPolyIndexMap(
  inputPxPts: Array<[number, number]>,
  cubics: BezierCubic[],
): PolyRange[] {
  const ranges: PolyRange[] = []
  const tol = 1e-4
  let prevEnd = 0

  for (let j = 0; j < cubics.length; j++) {
    const [endX, endY] = cubics[j][3]
    let k = prevEnd

    if (j === cubics.length - 1) {
      // Force full coverage to the closing-duplicate vertex (index M-1).
      // fitCurve drops the closing duplicate so cubics[N-1].p3 = P_{M-2}, not P_{M-1}.
      // A forward-scan would find P_{M-2} at index M-2, leaving vertex M-1 (the closing
      // duplicate, coincident with anchor 0) without a range owner. With k=M-1, the
      // closing segment's flatten writes orderedKeys[q..M-1], so dragging anchor 0 moves
      // BOTH index 0 and index M-1, keeping the ring closed (G1 guard against reopening).
      k = inputPxPts.length - 1
    } else {
      // Scan forward for the nearest input vertex matching this cubic's endpoint.
      let found = -1
      for (let i = prevEnd; i < inputPxPts.length; i++) {
        const dx = inputPxPts[i][0] - endX
        const dy = inputPxPts[i][1] - endY
        if (Math.sqrt(dx * dx + dy * dy) <= tol) {
          found = i
          break
        }
      }
      k = found === -1 ? Math.min(prevEnd + 1, inputPxPts.length - 1) : found
    }

    ranges.push({ rangeStart: prevEnd, rangeEnd: k })
    prevEnd = k
  }

  return ranges
}

/**
 * Split one PolyRange at an interior vertex index into two contiguous sub-ranges
 * that SHARE `splitIndex` as their boundary endpoint (08.1-06 G3). The shared-endpoint
 * convention mirrors buildPolyIndexMap, where adjacent cubics share a vertex
 * (`prevEnd` becomes the next range's `rangeStart`).
 *
 * A split at or outside the range bounds would create a zero-width sub-range, so
 * `splitIndex` is clamped to the strictly-interior band [rangeStart+1, rangeEnd-1].
 * For a range too narrow to split (rangeEnd - rangeStart < 2) the left sub-range
 * collapses to a single shared vertex — documented, deterministic behavior.
 */
export function splitPolyRange(
  range: PolyRange,
  splitIndex: number,
): [PolyRange, PolyRange] {
  const lo = range.rangeStart
  const hi = range.rangeEnd
  // Clamp into the strictly-interior band so neither sub-range is zero-width
  // (when width >= 2). For width < 2 this clamps to lo+1 capped at hi.
  const clamped = Math.max(lo + 1, Math.min(splitIndex, Math.max(lo + 1, hi - 1)))
  const split = Math.min(clamped, hi)
  return [
    { rangeStart: lo, rangeEnd: split },
    { rangeStart: split, rangeEnd: hi },
  ]
}

/**
 * Given a click point in STAGE-LOCAL px, find the curve segment passing nearest the
 * click and the original-polygon vertex index (strictly inside that segment's range)
 * nearest the click (08.1-06 G3). All inputs share one px space.
 *
 * Each segment s is the cubic [a.anchorPx, a.cp2Px, b.cp1Px, b.anchorPx] where
 * a = anchors[s], b = anchors[(s+1) % N]. The cubic is sampled at `samples` evenly
 * spaced t values; the segment with the closest sample (within `tolerancePx`) wins.
 * Within that segment's poly range the nearest original vertex in `pxPts` is chosen,
 * snapped to a real integer index strictly between rangeStart and rangeEnd.
 * Returns null when no segment is within tolerance.
 */
export function findNearestSegmentAndVertex(
  clickPx: [number, number],
  anchors: Array<{
    anchorPx: [number, number]
    cp1Px: [number, number]
    cp2Px: [number, number]
    polyRangeStart: number
    polyRangeEnd: number
  }>,
  pxPts: Array<[number, number]>,
  tolerancePx = 8,
  samples = 16,
): { segmentIdx: number; splitVertexIndex: number } | null {
  const N = anchors.length
  if (N < 2) return null
  const dist2 = (a: [number, number], b: [number, number]) => {
    const dx = a[0] - b[0]
    const dy = a[1] - b[1]
    return dx * dx + dy * dy
  }

  let bestSeg = -1
  let bestSegDist2 = Infinity
  // Only editable segments 0..N-2 (segment N-1 is the non-editable closing segment).
  for (let s = 0; s < N - 1; s++) {
    const a = anchors[s]
    const b = anchors[s + 1]
    for (let i = 0; i <= samples; i++) {
      const t = i / samples
      const p = cubicBezierAt(a.anchorPx, a.cp2Px, b.cp1Px, b.anchorPx, t)
      const d2 = dist2(p, clickPx)
      if (d2 < bestSegDist2) {
        bestSegDist2 = d2
        bestSeg = s
      }
    }
  }

  if (bestSeg === -1 || bestSegDist2 > tolerancePx * tolerancePx) return null

  const { polyRangeStart: lo, polyRangeEnd: hi } = anchors[bestSeg]
  // Need at least one strictly-interior index.
  if (hi - lo < 2) return null

  let bestVtx = -1
  let bestVtxDist2 = Infinity
  for (let i = lo + 1; i <= hi - 1; i++) {
    const pt = pxPts[i]
    if (!pt) continue
    const d2 = dist2(pt, clickPx)
    if (d2 < bestVtxDist2) {
      bestVtxDist2 = d2
      bestVtx = i
    }
  }
  if (bestVtx === -1) return null

  return { segmentIdx: bestSeg, splitVertexIndex: bestVtx }
}
