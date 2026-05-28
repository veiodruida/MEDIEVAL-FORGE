/**
 * useLandmaskRing — Phase 08 Plan 16 (LANDMASK-01, Path B).
 *
 * Fetches the current landmask polygon ring from the backend for the given
 * project + branch. Returns `Array<[lon, lat]>` to seed VertexEditLayer's
 * cyan landmask handles.
 *
 * Priority (handled by backend):
 *   1. Branch landmask_replace EditEvent coords (if any exist for branch_id)
 *   2. Natural Earth PT+ES union exterior ring
 *   3. 404 → returns undefined (caller shows empty handles)
 *
 * Query is stale-while-revalidate: after an Apply, invalidate
 * ['landmask-ring', projectId, branchId] to pick up the new coords.
 *
 * REQ-IDs: LANDMASK-01, LANDMASK-02
 */
import { useQuery } from '@tanstack/react-query'

export interface LandmaskRingResult {
  ring: Array<[number, number]>
  source: 'branch_edit_event' | 'natural_earth'
}

async function fetchLandmaskRing(
  projectId: string,
  branchId: string | undefined,
): Promise<LandmaskRingResult> {
  const params = branchId ? `?branch_id=${encodeURIComponent(branchId)}` : ''
  const res = await fetch(`/api/v3/projects/${projectId}/editor/landmask_ring${params}`)
  if (!res.ok) {
    throw new Error(`LANDMASK_RING_FETCH_FAILED: ${res.status}`)
  }
  return res.json() as Promise<LandmaskRingResult>
}

/**
 * Returns the landmask polygon ring as Array<[lon, lat]> for the given
 * project + branch. Returns undefined while loading or on error.
 *
 * @param projectId - UUID of the active project
 * @param branchId  - UUID of the active branch (optional; backend falls back to NE ring)
 */
export function useLandmaskRing(
  projectId: string | undefined,
  branchId: string | undefined,
): Array<[number, number]> | undefined {
  const query = useQuery({
    queryKey: ['landmask-ring', projectId, branchId] as const,
    queryFn: () => fetchLandmaskRing(projectId!, branchId),
    enabled: Boolean(projectId),
    // Natural Earth ring is stable; branch edit-event ring changes on Apply.
    // staleTime: 0 so Apply → queryClient.invalidateQueries picks it up immediately.
    staleTime: 0,
    gcTime: 5 * 60 * 1000,
    // On 404 (no ring available), return undefined rather than throwing.
    retry: false,
  })
  return query.data?.ring
}
