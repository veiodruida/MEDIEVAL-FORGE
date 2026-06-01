/**
 * Phase 08.3 Plan 11 — Pure ring-manipulation geometry helpers.
 *
 * Exports: translateRing, moveRingVertex
 *
 * Ring type = Array<{lat:number; lon:number}> (matches EditOp.ring in useEditorStore.ts:48).
 * A closed ring has first === last (duplicate closing vertex).
 *
 * Coordinate convention: lat=y-axis, lon=x-axis.
 * Deltas are in geo-space degrees (matches manual_edit.py:587 xoff=d_lon, yoff=d_lat).
 *
 * NO imports from stores or react-konva (pure functions — mirrors penFlatten.ts:9-10).
 */

export type RingPoint = { lat: number; lon: number }

/**
 * Return a new ring with every vertex shifted by (dLat, dLon).
 * Preserves the closed-ring invariant automatically: the first and last
 * vertices are both shifted by the same delta, so first === last if they
 * were equal in the input.
 *
 * @param ring   Closed ring Array<{lat,lon}> — first === last.
 * @param dLat   Geo latitude delta (degrees north).
 * @param dLon   Geo longitude delta (degrees east).
 * @returns A NEW array (input is never mutated).
 */
export function translateRing(
  ring: ReadonlyArray<RingPoint>,
  dLat: number,
  dLon: number,
): RingPoint[] {
  return ring.map((pt) => ({ lat: pt.lat + dLat, lon: pt.lon + dLon }))
}

/**
 * Return a new ring with the vertex at `index` relocated to (lat, lon).
 *
 * Closed-ring invariant: if the ring is closed (ring[0] coord-equals ring[last])
 * and the moved index is 0 OR the last index, BOTH the first and last vertex are
 * updated so the ring stays closed.
 *
 * @param ring   Closed ring Array<{lat,lon}> — first === last.
 * @param index  Zero-based index of the vertex to move.
 * @param lat    New latitude for the vertex.
 * @param lon    New longitude for the vertex.
 * @returns A NEW array (input is never mutated).
 */
export function moveRingVertex(
  ring: ReadonlyArray<RingPoint>,
  index: number,
  lat: number,
  lon: number,
): RingPoint[] {
  const result: RingPoint[] = ring.map((pt) => ({ ...pt }))
  const lastIdx = result.length - 1

  // Determine whether the ring is closed (first point coord-equals last point).
  const isClosed =
    ring.length >= 2 &&
    ring[0].lat === ring[lastIdx].lat &&
    ring[0].lon === ring[lastIdx].lon

  // Move the target vertex.
  result[index] = { lat, lon }

  // If closed and moving first or last vertex, keep both in sync.
  if (isClosed) {
    if (index === 0) {
      result[lastIdx] = { lat, lon }
    } else if (index === lastIdx) {
      result[0] = { lat, lon }
    }
  }

  return result
}
