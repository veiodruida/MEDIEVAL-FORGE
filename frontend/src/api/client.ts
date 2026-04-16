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
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
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
