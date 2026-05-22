/**
 * Phase 07 Plan 09a Task 1 — TanStack Query hook wrapping
 * GET /api/v3/projects/{id}/research/overlay.
 *
 * BLOCKER 2 + REVIEWS fix #2 — `meta` carries BOTH `generated_at` AND
 * `applied_at`. Plan 09b microcopy renders single-line when they match,
 * two-line when they differ (cache-hit re-apply scenario where the original
 * LLM-output timestamp pre-dates the runner's `applied_at` write).
 *
 * Endpoint shape on miss: `{exists:false, covered_condado_ids:[], meta:null}`
 * (backend returns 200, not 404). The 404 branch here is defensive — if the
 * request mis-routes (typo'd project id, etc.), we surface the same
 * zero-overlay shape so the InspectorSidebar's "Pesquisa aplicada" badge
 * stays hidden without throwing.
 */
import { useQuery } from '@tanstack/react-query'

export interface ResearchOverlayMeta {
  provider: string
  model: string
  /** REVIEWS fix #2 — ISO 8601 timestamp of the original LLM output. */
  generated_at: string
  /** REVIEWS fix #2 — ISO 8601 timestamp of when the runner wrote the overlay. */
  applied_at: string
}

export interface ResearchOverlayEntry {
  name: string | null
  kingdom_owner: string | null
  historical_notes: string | null
}

export interface ResearchOverlay {
  exists: boolean
  covered_condado_ids: string[]
  /**
   * UAT 2026-05-22 — full per-condado overlay payload. The dialog renders a
   * "Resultado" panel from this map after a successful run. Empty `{}` on
   * miss; absent on backends that pre-date this field (treated as empty).
   */
  entries?: Record<string, ResearchOverlayEntry>
  meta: ResearchOverlayMeta | null
}

const EMPTY_OVERLAY: ResearchOverlay = {
  exists: false,
  covered_condado_ids: [],
  entries: {},
  meta: null,
}

export function useResearchOverlay(projectId: string | undefined) {
  return useQuery<ResearchOverlay>({
    queryKey: ['v3', 'projects', projectId, 'research', 'overlay'],
    queryFn: async () => {
      const res = await fetch(
        `/api/v3/projects/${projectId}/research/overlay`,
      )
      // Defensive: backend returns 200 with exists:false; 404 should not
      // happen on the happy path. Treat 404 as "no overlay" rather than
      // crashing the InspectorSidebar.
      if (res.status === 404) return EMPTY_OVERLAY
      if (!res.ok) throw new Error(`overlay fetch failed: ${res.status}`)
      return res.json() as Promise<ResearchOverlay>
    },
    enabled: Boolean(projectId),
    staleTime: 30_000,
  })
}
