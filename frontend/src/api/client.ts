import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryResult,
} from '@tanstack/react-query'

export interface Project {
  id: string
  name: string
  country_qid: string
  period_start: number
  period_end: number
  bbox_lon_min: number | null
  bbox_lon_max: number | null
  bbox_lat_min: number | null
  bbox_lat_max: number | null
  generator_config: Record<string, unknown> | null
  status: string
  created_at: string
  updated_at: string
}

export interface ProjectCreatePayload {
  name: string
  country_qid: string
  period_start: number
  period_end: number
  bbox_lon_min?: number | null
  bbox_lon_max?: number | null
  bbox_lat_min?: number | null
  bbox_lat_max?: number | null
  generator_config?: Record<string, unknown> | null
}

export type ProjectUpdatePayload = Partial<ProjectCreatePayload> & {
  status?: string
}

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  })
  if (!res.ok) {
    const text = await res.text()
    let message = `${res.status} ${res.statusText}: ${text}`
    try {
      const json = JSON.parse(text)
      if (typeof json.detail === 'string') message = json.detail
    } catch { /* not JSON, keep original */ }
    throw new Error(message)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export interface Preset {
  label: string
  country: string
  country_qid: string
  bbox: { lon_min: number; lat_min: number; lon_max: number; lat_max: number }
  period_example: [number, number]
}

// ---------- Phase 03 Plan 02: v3 status manifest ----------

export interface StatusManifest {
  status: string
  has_artifacts: Record<string, boolean>
  last_generated_at: string | null
}

/**
 * GET /api/v3/projects/{id}/status — returns the per-project status + a
 * has_artifacts manifest over the 14-file allowlist. Frontend reads this on
 * mount to decide which UI state (empty / generating / ready / error) to
 * render. queryKey ['v3-status', id] is invalidated by the SSE done handler
 * to force a re-fetch and re-evaluate the canvas body.
 */
export function useStatusManifest(
  projectId: string | undefined,
): UseQueryResult<StatusManifest> {
  return useQuery({
    queryKey: ['v3-status', projectId],
    queryFn: () =>
      jsonFetch<StatusManifest>(`/api/v3/projects/${projectId}/status`),
    enabled: Boolean(projectId),
    staleTime: 5_000,
  })
}

export function usePresets(): UseQueryResult<Preset[]> {
  return useQuery({
    queryKey: ['presets'],
    queryFn: () => jsonFetch<Preset[]>('/api/projects/presets'),
    staleTime: Infinity, // presets são estáticos
  })
}

export function useProjects(): UseQueryResult<Project[]> {
  return useQuery({
    queryKey: ['projects'],
    queryFn: () => jsonFetch<Project[]>('/api/projects'),
  })
}

export function useProject(id: string | undefined) {
  return useQuery({
    queryKey: ['projects', id],
    queryFn: () => jsonFetch<Project>(`/api/projects/${id}`),
    enabled: Boolean(id),
    // Poll every 2s while the project is in a transient processing state.
    refetchInterval: (query) => {
      const data = query.state.data as Project | undefined
      if (data && (data.status === 'generating' || data.status.startsWith('ingesting'))) {
        return 2000
      }
      return false
    },
  })
}

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: ProjectCreatePayload) =>
      jsonFetch<Project>('/api/projects', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  })
}

export function useUpdateProject(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: ProjectUpdatePayload) =>
      jsonFetch<Project>(`/api/projects/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      qc.invalidateQueries({ queryKey: ['projects', id] })
    },
  })
}

export function useDeleteProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      jsonFetch<void>(`/api/projects/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  })
}

// ---------- v3 EXPORT (Phase 07 Plan 10) ----------
//
// The legacy v1 `useExport` hook (and its `ExportResponse` interface) lived
// here until Phase 07 Plan 10. Both were DELETED per WARNING 4 / D-V3-04
// (no transitional shims). The v3 swap is in `frontend/src/api/useExportV3.ts`
// (typed 422 envelope branch + dry_run support). Consumer wiring is in
// `frontend/src/pages/ProjectDetail.tsx` (handleExport blob download +
// ExportErrorDialog mount + Toast.Provider network fallback).

// ---------- Plan 05-08: v3 project creation ----------

export interface V3ProjectCreatePayload {
  name: string
  region_key: string
}

export interface V3ProjectCreateResult {
  id: string
  name: string
  region_key: string
}

export function useCreateV3Project() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: V3ProjectCreatePayload) =>
      jsonFetch<V3ProjectCreateResult>('/api/v3/projects', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    // Invalidate the exact same queryKey used by useProjects so ProjectList refreshes.
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  })
}

// ---------------------------------------------------------------------------
// Etapa 2: Baronies builder
// ---------------------------------------------------------------------------

export interface BuildBaroniesResponse {
  baronies_count: number
  municipalities_count: number
}

export async function buildBaronies(
  projectId: string,
  count: number | 'all',
): Promise<BuildBaroniesResponse> {
  const params = new URLSearchParams({ count: String(count) })
  const res = await fetch(
    `/api/projects/${projectId}/baronies?${params.toString()}`,
    { method: 'POST' },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `buildBaronies failed: ${res.status}`)
  }
  return (await res.json()) as BuildBaroniesResponse
}
