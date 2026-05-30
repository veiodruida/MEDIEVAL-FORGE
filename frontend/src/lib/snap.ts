/**
 * Phase 08 Plan 06b — scale-aware snap utility (TOPO-03, D-28).
 *
 * Pitfall 7: D-28 says "snap within 5px". User zooms 10× → snap should still
 * be 5 screen-pixels = 0.5 world-units. Hardcoding 5 world-units would make
 * snap invisible at high zoom and over-sensitive at low zoom.
 *
 * Fix: snapWorldDist = SNAP_SCREEN_PX / stageScale
 * Caller supplies stageScale = stage.scaleX() from the Konva Stage.
 *
 * D-28: Hold Alt → disable snap for current drag.
 * D-28: Snap target indicator = yellow circle #eab308 radius=8 stroke=2.
 */

export interface SnapCandidate {
  id: string;
  lat: number;
  lon: number;
}

export interface SnapResult {
  id: string;
  lat: number;
  lon: number;
}

/**
 * An edge defined by two endpoints (world lat/lon) with their vertex ids.
 * Used by snapToEdge for pen-tool edge snapping (D-05, D-16).
 */
export interface SnapEdge {
  id1: string;
  id2: string;
  a: { lat: number; lon: number };
  b: { lat: number; lon: number };
}

/**
 * Result of snapToEdge: the nearest point on the edge (in world lat/lon)
 * plus the two endpoint ids.
 */
export interface SnapEdgeResult {
  lat: number;
  lon: number;
  edgeEndpointIds: [string, string];
}

/** Base snap radius in screen pixels (D-28: "within 5px"). */
const SNAP_SCREEN_PX = 5;

/**
 * Find the nearest snap candidate within the scale-aware tolerance.
 *
 * @param cursorWorld  Current cursor position in world coordinates (lat/lon).
 * @param candidates   List of snap targets (e.g., vertices of visible baronies).
 * @param stageScale   Current Konva stage zoom level (stage.scaleX()).
 *                     Pitfall 7: converts screen-pixel tolerance to world units.
 * @param altHeld      When true, snap is disabled for this drag (D-28).
 * @param radiusPx     Snap radius in screen pixels (default 5 for vertex snap; pass 12 for pen).
 * @returns The nearest candidate within tolerance, or null if none.
 */
export function snapToNeighbour(
  cursorWorld: { lat: number; lon: number },
  candidates: SnapCandidate[],
  stageScale: number,
  altHeld: boolean,
  radiusPx = SNAP_SCREEN_PX,
): SnapResult | null {
  // D-28: Alt held → disable snap for current drag
  if (altHeld) return null;

  // Pitfall 7: convert screen-px tolerance to world-units via current scale.
  const worldTol = radiusPx / stageScale;

  let best: { c: SnapCandidate; d: number } | null = null;

  for (const c of candidates) {
    const dLat = c.lat - cursorWorld.lat;
    const dLon = c.lon - cursorWorld.lon;
    const d = Math.sqrt(dLat * dLat + dLon * dLon);
    if (d <= worldTol && (best === null || d < best.d)) {
      best = { c, d };
    }
  }

  return best ? { id: best.c.id, lat: best.c.lat, lon: best.c.lon } : null;
}

/**
 * Find the nearest point on a set of polygon edges within snap radius (D-05, D-16).
 *
 * Pen tool uses a 12 screen-px snap radius (D-16 — distinct from vertex SNAP_SCREEN_PX=5).
 * Computes the perpendicular foot on each edge segment; clamps t ∈ [0,1] so the
 * snap point is always ON the segment (not its extension). Returns the closest edge
 * that is within the tolerance, with both endpoint ids.
 *
 * @param cursorWorld  Cursor position in world coordinates (lat/lon).
 * @param edges        Edge list from neighbor barony rings.
 * @param stageScale   Current Konva stage zoom level (stage.scaleX()).
 * @param altHeld      When true, snap is disabled (D-28 parity).
 * @param radiusPx     Snap radius in screen pixels (default 12 for pen tool).
 * @returns Nearest edge point + endpoint ids, or null if none within tolerance.
 */
export function snapToEdge(
  cursorWorld: { lat: number; lon: number },
  edges: SnapEdge[],
  stageScale: number,
  altHeld: boolean,
  radiusPx = 12,
): SnapEdgeResult | null {
  if (altHeld) return null;
  if (edges.length === 0) return null;

  const worldTol = radiusPx / stageScale;

  let best: { d: number; lat: number; lon: number; id1: string; id2: string } | null = null;

  for (const edge of edges) {
    const { a, b, id1, id2 } = edge;
    // Vector ab and ac (cursor - a)
    const abLat = b.lat - a.lat;
    const abLon = b.lon - a.lon;
    const acLat = cursorWorld.lat - a.lat;
    const acLon = cursorWorld.lon - a.lon;

    const abLen2 = abLat * abLat + abLon * abLon;

    let nearLat: number, nearLon: number;
    if (abLen2 === 0) {
      // Degenerate edge (both endpoints identical) — snap to the point
      nearLat = a.lat;
      nearLon = a.lon;
    } else {
      // t = dot(ac, ab) / |ab|^2 — projection parameter, clamped to [0,1]
      const t = Math.max(0, Math.min(1, (acLat * abLat + acLon * abLon) / abLen2));
      nearLat = a.lat + t * abLat;
      nearLon = a.lon + t * abLon;
    }

    const dLat = cursorWorld.lat - nearLat;
    const dLon = cursorWorld.lon - nearLon;
    const d = Math.sqrt(dLat * dLat + dLon * dLon);

    if (d <= worldTol && (best === null || d < best.d)) {
      best = { d, lat: nearLat, lon: nearLon, id1, id2 };
    }
  }

  if (!best) return null;
  return { lat: best.lat, lon: best.lon, edgeEndpointIds: [best.id1, best.id2] };
}
