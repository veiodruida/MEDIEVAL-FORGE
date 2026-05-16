/**
 * Phase 07.1 Plan 06 Task 1 — TanStack Query hook wrapping
 * GET /api/projects/{id} (v1 legacy route that returns full ProjectResponse
 * with period_start / period_end — the v3 router only exposes POST for now).
 *
 * D-03 (Phase 07.1): seed source for ResearchDialog's two numeric period
 * inputs. The hook is disabled when projectId is null/undefined so the
 * InspectorSidebar can mount without a project selected.
 *
 * Backend shape reference: backend/medieval_forge/schemas.py ProjectResponse
 * (lines 95-110). All fields snake_case; created_at/updated_at are ISO 8601
 * datetime strings from FastAPI JSON serialisation.
 */
import { useQuery } from '@tanstack/react-query'

/**
 * Project — mirrors backend/medieval_forge/schemas.py `ProjectResponse`.
 * D-03 (Phase 07.1): period_start / period_end seed ResearchDialog's numeric
 * inputs. Fields are nullable in the DB (migration 0005).
 */
export interface Project {
  id: string
  name: string
  country_qid: string | null
  /** D-03 (Phase 07.1) — seed source for ResearchDialog numeric period inputs. */
  period_start: number | null
  /** D-03 (Phase 07.1) — seed source for ResearchDialog numeric period inputs. */
  period_end: number | null
  bbox_lon_min: number | null
  bbox_lon_max: number | null
  bbox_lat_min: number | null
  bbox_lat_max: number | null
  generator_config: Record<string, unknown> | null
  status: string
  created_at: string
  updated_at: string
  /** v3 region_key — present for v3 projects; absent on legacy v1 rows. */
  region_key?: string | null
}

/**
 * useProject — wraps GET /api/projects/{id}.
 *
 * NOTE: Uses the v1 legacy route because GET /api/v3/projects/{id} does not
 * yet exist (Phase 05 only added POST). The v1 route returns the full
 * ProjectResponse which already includes period_start / period_end. Tracked
 * as Rule 3 deviation in 07.1-06-SUMMARY.md.
 *
 * @param projectId — UUID string from route params. Pass null/undefined to
 *   keep query idle (no fetch).
 */
export function useProject(projectId: string | null | undefined) {
  return useQuery<Project>({
    queryKey: ['project', projectId],
    queryFn: async () => {
      if (!projectId) throw new Error('useProject: projectId required')
      const r = await fetch(`/api/projects/${projectId}`)
      if (!r.ok) throw new Error(`project fetch failed: ${r.status}`)
      return r.json() as Promise<Project>
    },
    enabled: Boolean(projectId),
    staleTime: 30_000,
  })
}
