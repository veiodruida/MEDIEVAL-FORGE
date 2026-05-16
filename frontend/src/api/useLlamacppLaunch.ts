/**
 * Phase 07.1 Plan 06 Task 2 — TanStack Query mutations for llama.cpp
 * launch and shutdown (D-08 / D-08b).
 *
 * Pitfall 9 mitigation: both onSuccess callbacks invalidate THREE queryKeys so
 * all dependent views re-render with fresh server state:
 *   - ['v3', 'research', 'providers']  → ResearchDialog ProviderSelector
 *   - ['llamacpp-health']              → AuthSetupSheet model dropdown
 *   - ['llamacpp-status']              → AuthSetupSheet isRunning badge (review-fix #6)
 *
 * NOTE: The plan lists the providers queryKey as ['providers']. That is a bug
 * in the plan — useProviders.ts (Phase 07) registers the key as
 * ['v3', 'research', 'providers']. Using the wrong prefix would silently break
 * Pitfall 9 mitigation. Fixed here as Rule 1 (queryKey mismatch).
 *
 * Mutation errors surface the backend's JSON `detail` field so consumers can
 * render inline error messages (409 conflict path: "modelo X ativo — pare-o
 * antes via DELETE").
 */
import { useMutation, useQueryClient } from '@tanstack/react-query'

export interface LaunchResult {
  ok: boolean
  base_url: string
  pid: number
  model: string
  started_at: string
}

export interface ShutdownResult {
  ok: boolean
  was_running: boolean
}

/**
 * useLlamacppLaunch — POST /api/v3/llm/llamacpp/launch (D-08).
 *
 * Body: `{ "model": "<filename>.gguf" }`. On HTTP 409 the backend returns a
 * PT-BR `detail` string (e.g. "modelo `m.gguf` ativo — pare-o antes via
 * DELETE"); the mutation surfaces this as Error.message so the UI can render
 * inline.
 *
 * Pitfall 9: onSuccess invalidates providers + llamacpp-health +
 * llamacpp-status queryKeys.
 */
export function useLlamacppLaunch() {
  const qc = useQueryClient()
  return useMutation<LaunchResult, Error, { model: string }>({
    mutationFn: async ({ model }) => {
      const r = await fetch('/api/v3/llm/llamacpp/launch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model }),
      })
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
      return r.json() as Promise<LaunchResult>
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['v3', 'research', 'providers'] })
      qc.invalidateQueries({ queryKey: ['llamacpp-health'] })
      qc.invalidateQueries({ queryKey: ['llamacpp-status'] })
    },
  })
}

/**
 * useLlamacppShutdown — DELETE /api/v3/llm/llamacpp/launch (D-08b).
 *
 * Returns {ok: true, was_running} per Discretion #7 (idempotent 200, not 404).
 * Same invalidation policy as useLlamacppLaunch.
 */
export function useLlamacppShutdown() {
  const qc = useQueryClient()
  return useMutation<ShutdownResult, Error, void>({
    mutationFn: async () => {
      const r = await fetch('/api/v3/llm/llamacpp/launch', {
        method: 'DELETE',
      })
      if (!r.ok) {
        let msg = `shutdown failed: ${r.status}`
        try {
          const body = await r.json()
          if (body?.detail) msg = body.detail
        } catch {
          /* ignore parse errors */
        }
        throw new Error(msg)
      }
      return r.json() as Promise<ShutdownResult>
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['v3', 'research', 'providers'] })
      qc.invalidateQueries({ queryKey: ['llamacpp-health'] })
      qc.invalidateQueries({ queryKey: ['llamacpp-status'] })
    },
  })
}
