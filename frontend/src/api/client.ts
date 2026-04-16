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

export function useGenerate(projectId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (territoryData?: Record<string, unknown>) => {
      const body: Record<string, unknown> = {}
      if (territoryData) body.territory_data = territoryData
      return jsonFetch<{ project_id: string; status: string }>(
        `/api/projects/${projectId}/generate`,
        { method: 'POST', body: JSON.stringify(body) },
      )
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects', projectId] })
      qc.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

// ---------- INGEST-04: SSE streaming hook (D-09) ----------

import { useCallback, useState } from 'react'

export interface IngestStreamHandle {
  lines: string[]
  start: (source: 'wikidata' | 'osm') => Promise<void>
  isStreaming: boolean
  error: Error | null
}

export function useIngestStream(projectId: string | undefined): IngestStreamHandle {
  const qc = useQueryClient()
  const [lines, setLines] = useState<string[]>([])
  const [isStreaming, setStreaming] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const start = useCallback(
    async (source: 'wikidata' | 'osm') => {
      if (!projectId) return
      setLines([])
      setError(null)
      setStreaming(true)
      try {
        const res = await fetch(
          `/api/projects/${projectId}/ingest?source=${source}`,
          { method: 'POST' },
        )
        if (!res.ok || !res.body) {
          throw new Error(`HTTP ${res.status}`)
        }
        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buf = ''
        while (true) {
          const { value, done } = await reader.read()
          if (done) break
          buf += decoder.decode(value, { stream: true })
          // SSE events are separated by blank lines (\n\n).
          let idx
          while ((idx = buf.indexOf('\n\n')) !== -1) {
            const eventBlock = buf.slice(0, idx)
            buf = buf.slice(idx + 2)
            // Strip the "data: " prefix from each line in the block.
            const text = eventBlock
              .split('\n')
              .map((l) => (l.startsWith('data: ') ? l.slice(6) : l))
              .join('\n')
            setLines((prev) => [...prev, text + '\n'])
          }
        }
      } catch (e) {
        setError(e as Error)
      } finally {
        setStreaming(false)
        qc.invalidateQueries({ queryKey: ['projects', projectId] })
        qc.invalidateQueries({ queryKey: ['projects'] })
      }
    },
    [projectId, qc],
  )

  return { lines, start, isStreaming, error }
}
