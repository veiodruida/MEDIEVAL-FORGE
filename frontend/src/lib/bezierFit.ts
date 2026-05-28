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
      // Force full coverage regardless of float drift.
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
