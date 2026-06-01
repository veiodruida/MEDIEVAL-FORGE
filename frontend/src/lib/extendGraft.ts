/**
 * Phase 08.3 Plan 10 — PEN-EXTEND-01: pure helpers for the EXTEND graft.
 *
 * `spliceExtendRing` — splice a drawn open arc into a target barony's closed ring.
 *   Algorithm (Assumption A3):
 *     1. Find the two contour indices nearest arc[0] and arc[last] (contact indices).
 *     2. The two contact indices split the contour into TWO arcs. Identify which is SHORTER
 *        by accumulated point-to-point distance.
 *     3. Replace the SHORTER arc with the drawn arc points.
 *     4. Return the full new closed ring, preserving winding.
 *
 * `buildExtendVerticesMap` — given current store vertices, target barony name, and the spliced
 *   ring, delete every stale `${name}#*` key and write the new contiguous `#0..#N` keys.
 *   This is the stale-key trap guard (FACT 2 / manual_edit.py:622-638).
 *
 * Both functions are PURE — no React, no Konva, no store imports.
 */

export type GeoPoint = { lat: number; lon: number };
export type VertexCoord = { lat: number; lon: number };

// ---------------------------------------------------------------------------
// Internal geometry helpers
// ---------------------------------------------------------------------------

/** Euclidean distance in the lat/lon plane (sufficient for local-area splice). */
function dist2(a: GeoPoint, b: GeoPoint): number {
  const dlat = a.lat - b.lat;
  const dlon = a.lon - b.lon;
  return dlat * dlat + dlon * dlon;
}

/** Accumulated arc length (sum of point-to-point distances) for a slice of pts. */
function arcLength(pts: GeoPoint[], from: number, to: number): number {
  // from and to are indices; the arc is the points pts[from], pts[(from+1)%N], ...pts[to]
  // traversing in the forward direction (mod N).
  const N = pts.length;
  let len = 0;
  let cur = from;
  while (cur !== to) {
    const nxt = (cur + 1) % N;
    len += Math.sqrt(dist2(pts[cur]!, pts[nxt]!));
    cur = nxt;
  }
  return len;
}

/** Find index of the point in `contour` nearest to `target`. */
function nearestIndex(contour: GeoPoint[], target: GeoPoint): number {
  let best = 0;
  let bestD = Infinity;
  for (let i = 0; i < contour.length; i++) {
    const d = dist2(contour[i]!, target);
    if (d < bestD) {
      bestD = d;
      best = i;
    }
  }
  return best;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Splice a drawn open arc into a closed contour ring.
 *
 * @param contour  Target barony's closed ring as {lat,lon}[]. May be open (last ≠ first)
 *                 or closed (last === first). A trailing duplicate is stripped internally.
 * @param arc      Drawn open arc as {lat,lon}[]. arc[0] and arc[last] are the contact points
 *                 (near the contour). Must have ≥ 2 points.
 * @returns        New closed ring (last point === first point) with the shorter contour arc
 *                 between the two contact indices replaced by the drawn arc.
 *                 Returns a copy of the original ring if arc has < 2 points.
 */
export function spliceExtendRing(contour: GeoPoint[], arc: GeoPoint[]): GeoPoint[] {
  if (arc.length < 2) return [...contour];

  // Strip trailing duplicate if the contour is closed (GeoJSON convention last===first)
  const ring: GeoPoint[] =
    contour.length >= 2 &&
    contour[0]!.lat === contour[contour.length - 1]!.lat &&
    contour[0]!.lon === contour[contour.length - 1]!.lon
      ? contour.slice(0, -1)
      : [...contour];

  const N = ring.length;
  if (N < 2) return [...contour];

  // Contact indices on the contour
  const iA = nearestIndex(ring, arc[0]!);
  const iB = nearestIndex(ring, arc[arc.length - 1]!);

  // If both contact points map to the same contour index, degenerate — return unchanged
  if (iA === iB) return [...contour];

  // Measure the two arcs between iA and iB on the contour:
  //   arc1: iA → iB (forward, wrapping)
  //   arc2: iB → iA (forward, wrapping) — the "other" arc
  const len1 = arcLength(ring, iA, iB);
  const len2 = arcLength(ring, iB, iA);

  // We will REPLACE the shorter arc. The shorter arc runs from contact point A to contact
  // point B in whichever direction is shorter. The resulting ring is built by:
  //   1. Take the LONGER arc (kept as-is, from one contact to the other).
  //   2. Append the drawn arc in the direction that continues forward from iA to iB
  //      (or reversed if iB→iA is the shorter arc).
  //
  // Result ordering (shorter arc replaced):
  //   If len1 ≤ len2 (iA→iB forward is SHORTER → replace it):
  //     keep: ring[iB], ring[(iB+1)%N], ..., ring[iA]  (the longer arc: iB→iA)
  //     + drawn arc: arc[0](iA) → arc[1] → ... → arc[last](iB)   [forward direction]
  //   If len2 < len1  (iB→iA forward is SHORTER → replace it):
  //     keep: ring[iA], ring[(iA+1)%N], ..., ring[iB]  (the longer arc: iA→iB)
  //     + drawn arc REVERSED: arc[last](iB) → ... → arc[0](iA)

  let result: GeoPoint[];

  if (len1 <= len2) {
    // Shorter arc is iA→iB (forward). Keep the iB→iA arc, then append drawn arc forward.
    // Collect longer arc: iB, (iB+1)%N, ..., iA (inclusive of both endpoints)
    const longer: GeoPoint[] = [];
    let cur = iB;
    while (cur !== iA) {
      longer.push(ring[cur]!);
      cur = (cur + 1) % N;
    }
    longer.push(ring[iA]!); // contact point A

    // Append drawn arc from iA to iB (arc[0]=iA side, arc[last]=iB side)
    // Don't duplicate iA (it's already the last point in `longer`)
    for (let k = 1; k < arc.length; k++) {
      longer.push(arc[k]!);
    }

    // Close by returning to the start (ring[iB] is longer[0])
    longer.push({ ...longer[0]! });
    result = longer;
  } else {
    // Shorter arc is iB→iA (forward). Keep the iA→iB arc, then append drawn arc REVERSED.
    const longer: GeoPoint[] = [];
    let cur = iA;
    while (cur !== iB) {
      longer.push(ring[cur]!);
      cur = (cur + 1) % N;
    }
    longer.push(ring[iB]!); // contact point B

    // Append drawn arc REVERSED from iB to iA (arc[last]=iB side, arc[0]=iA side)
    // Don't duplicate iB (already last in `longer`)
    for (let k = arc.length - 2; k >= 0; k--) {
      longer.push(arc[k]!);
    }

    // Close
    longer.push({ ...longer[0]! });
    result = longer;
  }

  return result;
}

/**
 * Build the next vertices map for EXTEND:
 *   1. Copy current store vertices.
 *   2. DELETE every key whose prefix is `${targetName}#` (stale-key trap, FACT 2).
 *   3. Write the spliced ring as `${targetName}#0`, `${targetName}#1`, ...
 *
 * Returns the new vertices map (does NOT mutate the input).
 */
export function buildExtendVerticesMap(
  currentVertices: Record<string, VertexCoord>,
  targetName: string,
  splicedRing: GeoPoint[],
): Record<string, VertexCoord> {
  const prefix = targetName + '#';

  // 1. Copy, excluding all stale ${targetName}#* keys
  const next: Record<string, VertexCoord> = {};
  for (const [k, v] of Object.entries(currentVertices)) {
    if (!k.startsWith(prefix)) {
      next[k] = v;
    }
  }

  // 2. Write new contiguous #0..#N for the spliced ring
  for (let i = 0; i < splicedRing.length; i++) {
    next[`${targetName}#${i}`] = { lat: splicedRing[i]!.lat, lon: splicedRing[i]!.lon };
  }

  return next;
}
