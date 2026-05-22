/**
 * TanStack Query mutation + status hook for the Ollama daemon launcher.
 *
 * The "Iniciar Ollama" button in ProviderSelector calls useOllamaLaunch().mutate();
 * useOllamaStatus polls GET /api/v3/llm/ollama/launch every 5s while enabled,
 * mirroring useLlamacppStatus. No shutdown — Ollama is a shared system service.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

export interface OllamaLaunchResult {
  ok: boolean
  was_running: boolean
  base_url: string
}

export interface OllamaStatus {
  running: boolean
  base_url: string | null
}

export function useOllamaLaunch() {
  const qc = useQueryClient()
  return useMutation<OllamaLaunchResult, Error, void>({
    mutationFn: async () => {
      const r = await fetch('/api/v3/llm/ollama/launch', { method: 'POST' })
      if (!r.ok) {
        let msg = `launch failed: ${r.status}`
        try {
          const body = await r.json()
          if (body?.detail) msg = body.detail
        } catch {
          /* ignore parse errors */
        }
        throw new Error(msg)
      }
      return r.json() as Promise<OllamaLaunchResult>
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['v3', 'research', 'providers'] })
      qc.invalidateQueries({ queryKey: ['ollama-status'] })
    },
  })
}

export function useOllamaStatus(enabled = true) {
  return useQuery<OllamaStatus>({
    queryKey: ['ollama-status'],
    queryFn: async () => {
      const r = await fetch('/api/v3/llm/ollama/launch')
      if (!r.ok) throw new Error(`ollama status fetch failed: ${r.status}`)
      return r.json() as Promise<OllamaStatus>
    },
    enabled,
    refetchInterval: 5_000,
    staleTime: 4_000,
  })
}
