/**
 * Phase 08.3 Plan 05 — flattenPenPath
 * Phase 08.3 Plan 08 — sampleAndSimplifyFreehand (Douglas-Peucker clean-ring)
 *
 * Pure functions: PenAnchor[] / raw drag points → closed {lat, lon}[] ring.
 * Reuses flattenSegment from bezierFlatten.ts for curve anchors.
 * Straight anchors contribute both endpoints directly.
 *
 * Returns a closed ring (last point == first point).
 * No imports from stores or react-konva (pure function).
 */

import { flattenSegment } from './bezierFlatten';
import { geoToCanvas, canvasToGeo } from './projection';
import type { ProjectionConfig } from './projection';

export interface PenAnchor {
  lat: number;
  lon: number;
  type: 'straight' | 'curve';
  /** Outgoing control point (cp1 = handle leaving this anchor). */
  cp1?: { lat: number; lon: number };
  /** Incoming control point of the NEXT anchor's side (cp2 = handle arriving at next anchor). */
  cp2?: { lat: number; lon: number };
}

/**
 * Flatten a pen-tool anchor path to a closed {lat, lon}[] ring.
 *
 * Algorithm:
 *   For each segment i → (i+1) % N (including the closing segment):
 *   - If both anchors are 'straight' (or have no handles), emit both endpoints (dedup on join).
 *   - If the segment has curve handles (cp1/cp2 on the outgoing/incoming side),
 *     build a BezierCubic in canvas-px space and flatten via flattenSegment.
 *
 * BezierCubic convention (matching bezierFlatten.ts):
 *   [p0, c1, c2, p3] where c1 is near p0 (outgoing) and c2 is near p3 (incoming).
 *   For a curve segment i→j:
 *     p0 = anchor[i] px, c1 = anchor[i].cp1 px (outgoing handle of i)
 *     c2 = anchor[j].cp2 px (incoming handle of j), p3 = anchor[j] px
 *   Fallback if handles missing: c1=p0, c2=p3 (degenerate linear).
 *
 * @param anchors    PenAnchor[] from PenDrawLayer (must have ≥ 1 anchor).
 * @param projection ProjectionConfig for geo↔canvas conversion.
 * @returns Closed {lat, lon}[] ring (last point == first point).
 */
export function flattenPenPath(
  anchors: PenAnchor[],
  projection: ProjectionConfig,
): Array<{ lat: number; lon: number }> {
  const N = anchors.length;
  if (N === 0) return [];
  if (N === 1) return [{ lat: anchors[0].lat, lon: anchors[0].lon }];

  const ring: Array<{ lat: number; lon: number }> = [];

  for (let i = 0; i < N; i++) {
    const anchor = anchors[i];
    const next = anchors[(i + 1) % N];

    // Convert to canvas px for flattenSegment
    const [p0x, p0y] = geoToCanvas(anchor.lon, anchor.lat, projection);
    const [p3x, p3y] = geoToCanvas(next.lon, next.lat, projection);

    // Determine if this segment has curve handles
    const hasCurveHandles = anchor.cp1 != null || next.cp2 != null;

    if (hasCurveHandles) {
      // Curve segment: build BezierCubic and flatten
      const c1 = anchor.cp1
        ? geoToCanvas(anchor.cp1.lon, anchor.cp1.lat, projection)
        : ([p0x, p0y] as [number, number]);
      const c2 = next.cp2
        ? geoToCanvas(next.cp2.lon, next.cp2.lat, projection)
        : ([p3x, p3y] as [number, number]);

      // BezierCubic: [p0, c1, c2, p3]
      const cubic: [[number, number], [number, number], [number, number], [number, number]] = [
        [p0x, p0y],
        c1,
        c2,
        [p3x, p3y],
      ];

      // Use ~10 samples per segment for smooth curve
      const targetCount = 12;
      const flat = flattenSegment(cubic, targetCount, projection);

      // flat is Array<[lon, lat]> (canvasToGeo returns [lon, lat])
      // Emit all but the LAST point (dedup: next segment starts at p3)
      for (let k = 0; k < flat.length - 1; k++) {
        const [lon, lat] = flat[k];
        ring.push({ lat, lon });
      }
    } else {
      // Straight segment: emit anchor[i] (next segment will emit anchor[i+1])
      ring.push({ lat: anchor.lat, lon: anchor.lon });
    }
  }

  // Close the ring: append the first point as last
  ring.push({ lat: ring[0].lat, lon: ring[0].lon });

  return ring;
}

/**
 * Flatten the OPEN pen path (segments 0..N-2 only — no closing/wrap segment) for the
 * live on-screen preview while drawing. Uses the exact same per-segment cubic sampling
 * as flattenPenPath, so what the user sees mid-draw equals the committed ring's shape
 * (minus the not-yet-drawn closing segment). Straight segments contribute their start
 * anchor; curve segments are bezier-sampled. The final anchor is always appended.
 *
 * @param anchors    PenAnchor[] (>= 1).
 * @param projection ProjectionConfig for geo↔canvas conversion.
 * @returns Open {lat, lon}[] polyline (NOT closed).
 */
// ── sampleAndSimplifyFreehand ─────────────────────────────────────────────────
// Phase 08.3 Plan 08 (D-20): Douglas-Peucker simplify + light smoothing for
// freehand drag samples. Pure function: lat/lon[] in → closed lat/lon[] ring out.
// No new npm dependencies — RDP is inline.

/** Options for sampleAndSimplifyFreehand. */
export interface FreehandSimplifyOpts {
  /** RDP tolerance in canvas-px (default 2.5). */
  tolerancePx?: number
  /** Hard cap on output point count (default 60; uniform decimation if still over). */
  maxPoints?: number
}

/**
 * Ramer-Douglas-Peucker perpendicular-distance recursion.
 * Operates in canvas-px space (units are screen pixels at map scale).
 * Returns the simplified indices into `pts`.
 */
function rdpIndices(
  pts: Array<[number, number]>,
  start: number,
  end: number,
  tolerancePx: number,
  result: Set<number>,
): void {
  if (end <= start + 1) return
  // Find the point with the maximum perpendicular distance to the start–end line
  const [x1, y1] = pts[start]!
  const [x2, y2] = pts[end]!
  const dx = x2 - x1
  const dy = y2 - y1
  const lineLen = Math.sqrt(dx * dx + dy * dy)

  let maxDist = 0
  let maxIdx = start

  for (let i = start + 1; i < end; i++) {
    const [px, py] = pts[i]!
    let dist: number
    if (lineLen < 1e-10) {
      // Degenerate line segment — use point-to-point distance
      dist = Math.sqrt((px - x1) ** 2 + (py - y1) ** 2)
    } else {
      // Perpendicular distance = |cross| / |line|
      dist = Math.abs(dx * (y1 - py) - (x1 - px) * dy) / lineLen
    }
    if (dist > maxDist) {
      maxDist = dist
      maxIdx = i
    }
  }

  if (maxDist > tolerancePx) {
    result.add(maxIdx)
    rdpIndices(pts, start, maxIdx, tolerancePx, result)
    rdpIndices(pts, maxIdx, end, tolerancePx, result)
  }
}

/**
 * Simplify and smooth a raw freehand drag sample array into a clean closed ring.
 *
 * Algorithm (D-20):
 * 1. < 3 input points → return [].
 * 2. Map each {lat,lon} to canvas-px (screen-space simplify is scale-stable).
 * 3. Ramer-Douglas-Peucker with tolerancePx (default 2.5 px).
 * 4. Optional 3-tap moving-average pass (count-preserving) so corners are not razor-sharp.
 * 5. Hard cap at maxPoints (default 60) via uniform decimation.
 * 6. Map simplified px points back to {lat,lon}.
 * 7. Close ring: append copy of first point as last.
 *
 * @param points     Raw drag samples in {lat,lon} (geo degrees).
 * @param projection Affine projection for geo↔canvas-px conversion.
 * @param opts       Optional tolerancePx + maxPoints overrides.
 * @returns Closed {lat,lon}[] ring (first === last) or [] for degenerate input.
 */
export function sampleAndSimplifyFreehand(
  points: Array<{ lat: number; lon: number }>,
  projection: ProjectionConfig,
  opts?: FreehandSimplifyOpts,
): Array<{ lat: number; lon: number }> {
  if (points.length < 3) return []

  const tolerancePx = opts?.tolerancePx ?? 2.5
  const maxPoints = opts?.maxPoints ?? 60

  // Step 2: geo → canvas-px
  const pxPts: Array<[number, number]> = points.map(({ lat, lon }) => {
    const [x, y] = geoToCanvas(lon, lat, projection)
    return [x, y]
  })

  // Step 3: Ramer-Douglas-Peucker
  const keptIndices = new Set<number>([0, pxPts.length - 1])
  rdpIndices(pxPts, 0, pxPts.length - 1, tolerancePx, keptIndices)
  const sortedIndices = Array.from(keptIndices).sort((a, b) => a - b)
  let simplified: Array<[number, number]> = sortedIndices.map((i) => pxPts[i]!)

  // Step 4: 3-tap moving-average smoothing (count-preserving; does NOT double points).
  // Apply one pass: each middle point is replaced by the average of its neighbors.
  // Endpoints are fixed (RDP kept them as structural corners).
  if (simplified.length >= 3) {
    const smoothed: Array<[number, number]> = [simplified[0]!]
    for (let i = 1; i < simplified.length - 1; i++) {
      const prev = simplified[i - 1]!
      const cur = simplified[i]!
      const next = simplified[i + 1]!
      smoothed.push([
        (prev[0] + cur[0] + next[0]) / 3,
        (prev[1] + cur[1] + next[1]) / 3,
      ])
    }
    smoothed.push(simplified[simplified.length - 1]!)
    simplified = smoothed
  }

  // Step 5: hard cap via uniform decimation (take every k-th point)
  if (simplified.length > maxPoints) {
    const step = simplified.length / maxPoints
    const decimated: Array<[number, number]> = []
    for (let i = 0; i < maxPoints; i++) {
      const idx = Math.min(Math.round(i * step), simplified.length - 1)
      decimated.push(simplified[idx]!)
    }
    // Always keep the last original point as endpoint
    decimated[decimated.length - 1] = simplified[simplified.length - 1]!
    simplified = decimated
  }

  if (simplified.length < 3) return []

  // Step 6: canvas-px → geo
  const geoRing: Array<{ lat: number; lon: number }> = simplified.map(([x, y]) => {
    const [lon, lat] = canvasToGeo(x, y, projection)
    return { lat, lon }
  })

  // Step 7: close ring
  geoRing.push({ lat: geoRing[0]!.lat, lon: geoRing[0]!.lon })

  return geoRing
}

export function flattenPenPathOpen(
  anchors: PenAnchor[],
  projection: ProjectionConfig,
): Array<{ lat: number; lon: number }> {
  const N = anchors.length;
  if (N === 0) return [];
  if (N === 1) return [{ lat: anchors[0].lat, lon: anchors[0].lon }];

  const out: Array<{ lat: number; lon: number }> = [];

  for (let i = 0; i < N - 1; i++) {
    const anchor = anchors[i];
    const next = anchors[i + 1];
    const [p0x, p0y] = geoToCanvas(anchor.lon, anchor.lat, projection);
    const [p3x, p3y] = geoToCanvas(next.lon, next.lat, projection);
    const hasCurveHandles = anchor.cp1 != null || next.cp2 != null;

    if (hasCurveHandles) {
      const c1 = anchor.cp1
        ? geoToCanvas(anchor.cp1.lon, anchor.cp1.lat, projection)
        : ([p0x, p0y] as [number, number]);
      const c2 = next.cp2
        ? geoToCanvas(next.cp2.lon, next.cp2.lat, projection)
        : ([p3x, p3y] as [number, number]);
      const cubic: [[number, number], [number, number], [number, number], [number, number]] = [
        [p0x, p0y],
        c1,
        c2,
        [p3x, p3y],
      ];
      const flat = flattenSegment(cubic, 12, projection);
      // Emit all but the last point (next segment starts at p3); the final anchor is
      // appended once after the loop.
      for (let k = 0; k < flat.length - 1; k++) {
        const [lon, lat] = flat[k];
        out.push({ lat, lon });
      }
    } else {
      out.push({ lat: anchor.lat, lon: anchor.lon });
    }
  }

  // Append the last anchor (open path endpoint).
  out.push({ lat: anchors[N - 1].lat, lon: anchors[N - 1].lon });

  return out;
}
