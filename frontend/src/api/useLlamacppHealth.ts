/**
 * Phase 07.1 Plan 06 Task 2 — TanStack Query hook for llama.cpp health.
 *
 * D-09 (Phase 07.1): filters GET /api/v3/research/providers to the llamacpp
 * entry. No new backend endpoint — reuses the existing providers list.
 *
 * UI-SPEC §Interaction Contract: staleTime 10s, no polling interval. The
 * consumer (AuthSetupSheet) passes `enabled = isOpen` to keep the query idle
 * when the sheet is closed.
 */
import { useQuery } from '@tanstack/react-query'

/** Provider entry shape from /api/v3/research/providers (Phase 07 + 07.1). */
interface ProviderEntry {
  provider_id: string
  display_name: string
  healthy: boolean
  message: string
  configured: boolean
  /** D-09 (Phase 07.1): list of .gguf filenames (Llama.cpp) or model tags (Ollama). */
  available_models?: string[] | null
}

export interface LlamacppHealth {
  healthy: boolean
  message: string
  /** Always populated when models dir scan succeeded; may be empty array. */
  available_models: string[]
}

/**
 * useLlamacppHealth — D-09 Phase 07.1.
 *
 * Filters /api/v3/research/providers to the llamacpp entry. No polling
 * interval (per UI-SPEC §Interaction Contract — user refreshes by reopening
 * AuthSetupSheet). Stale time 10s.
 *
 * @param enabled - typically `isOpen` so the query only fires while
 *   AuthSetupSheet is open.
 */
export function useLlamacppHealth(enabled = true) {
  return useQuery<LlamacppHealth>({
    queryKey: ['llamacpp-health'],
    queryFn: async () => {
      const r = await fetch('/api/v3/research/providers')
      if (!r.ok) throw new Error(`providers fetch failed: ${r.status}`)
      const entries = (await r.json()) as ProviderEntry[]
      const entry = entries.find((e) => e.provider_id === 'llamacpp')
      if (!entry) {
        return { healthy: false, message: 'llamacpp not registered', available_models: [] }
      }
      return {
        healthy: entry.healthy,
        message: entry.message,
        available_models: entry.available_models ?? [],
      }
    },
    enabled,
    staleTime: 10_000,
  })
}
