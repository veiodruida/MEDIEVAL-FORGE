/**
 * Phase 08.3 Plan 05 — flattenPenPath
 *
 * Pure function: PenAnchor[] → closed {lat, lon}[] ring.
 * Reuses flattenSegment from bezierFlatten.ts for curve anchors.
 * Straight anchors contribute both endpoints directly.
 *
 * Returns a closed ring (last point == first point).
 * No imports from stores or react-konva (pure function).
 */

import { flattenSegment } from './bezierFlatten';
import { geoToCanvas } from './projection';
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
