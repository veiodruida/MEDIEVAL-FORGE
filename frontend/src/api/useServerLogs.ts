/**
 * TanStack Query hooks for tailing llama-server and ollama-serve stdout/stderr.
 *
 * UAT 2026-05-22 — user couldn't see what the model was doing during a run.
 * Backend captures combined stdout/stderr into a ring buffer (1000 lines max)
 * exposed at GET /api/v3/llm/{llamacpp,ollama}/logs?tail=N. These hooks poll
 * every 2s while their consumer is enabled (i.e. while the log panel is open).
 */
import { useQuery } from '@tanstack/react-query'

export interface ServerLogs {
  lines: string[]
}

export function useLlamacppLogs(enabled = true, tail = 200) {
  return useQuery<ServerLogs>({
    queryKey: ['llamacpp-logs', tail],
    queryFn: async () => {
      const r = await fetch(`/api/v3/llm/llamacpp/logs?tail=${tail}`)
      if (!r.ok) throw new Error(`llamacpp logs fetch failed: ${r.status}`)
      return r.json() as Promise<ServerLogs>
    },
    enabled,
    refetchInterval: 2_000,
    staleTime: 1_500,
  })
}

export function useOllamaLogs(enabled = true, tail = 200) {
  return useQuery<ServerLogs>({
    queryKey: ['ollama-logs', tail],
    queryFn: async () => {
      const r = await fetch(`/api/v3/llm/ollama/logs?tail=${tail}`)
      if (!r.ok) throw new Error(`ollama logs fetch failed: ${r.status}`)
      return r.json() as Promise<ServerLogs>
    },
    enabled,
    refetchInterval: 2_000,
    staleTime: 1_500,
  })
}
