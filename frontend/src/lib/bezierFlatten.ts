/**
 * Pure flatten helpers for the Bézier contour editor (Phase 08.1).
 *
 * A fitted cubic lives in canvas px space (bezierFit.ts). On commit, only DIRTY
 * segments are re-flattened back to [lon, lat] vertices at a density matching the
 * original polygon range (RESEARCH §Pattern 2). Geo coords materialize ONLY here
 * (UI-SPEC Note #3). Inline de Casteljau — no bezier-js dependency.
 */

import { canvasToGeo, type ProjectionConfig } from './projection'
import type { BezierCubic } from './bezierFit'

/** Evaluate a cubic Bézier at parameter t ∈ [0, 1] (uniform de Casteljau, px space). */
export function cubicBezierAt(
  p0: [number, number],
  c1: [number, number],
  c2: [number, number],
  p3: [number, number],
  t: number,
): [number, number] {
  const mt = 1 - t
  const mt2 = mt * mt
  const mt3 = mt2 * mt
  const t2 = t * t
  const t3 = t2 * t
  return [
    mt3 * p0[0] + 3 * mt2 * t * c1[0] + 3 * mt * t2 * c2[0] + t3 * p3[0],
    mt3 * p0[1] + 3 * mt2 * t * c1[1] + 3 * mt * t2 * c2[1] + t3 * p3[1],
  ]
}

/**
 * Flatten a cubic into `targetCount` [lon, lat] pairs, evenly spaced in t.
 * Evaluation is in px space; each sample is mapped back to geo via canvasToGeo.
 * targetCount = the original polygon range size, so the re-flattened segment keeps
 * the same vertex density as its neighbors.
 *
 * WR-03 hardening: when targetCount < 2, always emit BOTH endpoints [p0, p3] rather
 * than a single t=0 sample. This prevents a degenerate flatten that would collapse a
 * segment to a single point and corrupt the ring (e.g. when the closing segment's
 * rangeEnd - rangeStart + 1 is 0 or 1 after index-map tiling).
 */
export function flattenSegment(
  cubic: BezierCubic,
  targetCount: number,
  projection: ProjectionConfig,
): Array<[number, number]> {
  const [p0, c1, c2, p3] = cubic
  // WR-03: degenerate guard — always emit both endpoints for targetCount < 2.
  if (targetCount < 2) {
    return [canvasToGeo(p0[0], p0[1], projection), canvasToGeo(p3[0], p3[1], projection)]
  }
  const result: Array<[number, number]> = []
  for (let k = 0; k < targetCount; k++) {
    const t = k / (targetCount - 1)
    const [x, y] = cubicBezierAt(p0, c1, c2, p3, t)
    result.push(canvasToGeo(x, y, projection))
  }
  return result
}
