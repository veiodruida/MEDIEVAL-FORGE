/**
 * Phase 08 Plan 06b — shared-vertex index + coupled-drag logic (TOPO-04, D-30).
 *
 * D-30: Shared vertex moves together across all baronies — default and ONLY
 * behaviour. No escape hatch.
 *
 * D-28: Snap (snap.ts) guarantees coincident-vertex identification by bringing
 * the cursor to an existing vertex position. buildSharedVertexIndex then maps
 * that position to all coupled vertex IDs across baronies.
 *
 * RESEARCH §Don't Hand-Roll: "Naive O(N²) — small N per editable region;
 * refresh on edit-mode entry + mouseup. Replace with KDTree only when
 * measured-slow." (Karpathy: don't optimise hypothetically — §Pitfall 8.)
 *
 * Build once on edit-mode entry; rebuild on mouseup (committed state may change
 * coincident pairs). Keep per-country — CLAUDE.md Rule #3 (no global KD-tree
 * across PT/ES boundary; baronies from different countries cannot share vertices).
 */

/** A single vertex belonging to a barony, in world coordinates (lat/lon). */
export interface VertexRef {
  vertexId: string;
  baronyId: string;
  lat: number;
  lon: number;
}

/**
 * Maps each vertex ID to the list of ALL vertex IDs (including itself) that are
 * spatially coincident within `tolerance`. Only vertices that ARE coupled with
 * at least one other vertex appear as keys.
 */
export type SharedVertexIndex = Map<string, string[]>;

/**
 * Build a shared-vertex index from a flat list of vertex references.
 *
 * Naive O(N²) scan — acceptable because N per editable region is small
 * (typical barony has <200 vertices; viewport culling keeps visible set low).
 * Replace with scipy KDTree if ever measured-slow (Karpathy: don't pre-optimize).
 *
 * @param vertices   All vertex refs for the current editing session (per country).
 * @param tolerance  Euclidean distance threshold in world units (lat/lon degrees).
 *                   Default 1e-6 (matches snap.ts SNAP_SCREEN_PX / stageScale
 *                   at typical zoom).
 * @returns SharedVertexIndex — only coupled vertices appear as keys.
 */
export function buildSharedVertexIndex(
  vertices: VertexRef[],
  tolerance: number = 1e-6,
): SharedVertexIndex {
  const index: SharedVertexIndex = new Map();

  for (let i = 0; i < vertices.length; i++) {
    const vi = vertices[i];
    const coupled: string[] = [vi.vertexId];

    for (let j = 0; j < vertices.length; j++) {
      if (i === j) continue;
      const vj = vertices[j];
      const dLat = vi.lat - vj.lat;
      const dLon = vi.lon - vj.lon;
      const d = Math.sqrt(dLat * dLat + dLon * dLon);
      if (d <= tolerance) {
        coupled.push(vj.vertexId);
      }
    }

    // Only add to index if there is at least one coupling partner
    if (coupled.length > 1) {
      index.set(vi.vertexId, coupled);
    }
  }

  return index;
}

/**
 * Return all vertex IDs that must move together when `vertexId` is dragged.
 *
 * D-30: this is the ONLY coupling behaviour — no escape hatch.
 *
 * @param index     SharedVertexIndex from buildSharedVertexIndex.
 * @param vertexId  The vertex being dragged.
 * @returns Array of vertex IDs to update (always includes `vertexId` itself).
 *          Returns `[vertexId]` singleton if the vertex has no coupling partners.
 */
export function getCoupledVertices(
  index: SharedVertexIndex,
  vertexId: string,
): string[] {
  return index.get(vertexId) ?? [vertexId];
}
