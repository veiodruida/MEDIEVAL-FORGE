/**
 * Phase 07 Plan 09a Task 1 — TanStack Query hook wrapping
 * GET /api/v3/research/providers.
 *
 * Returns the merged provider+health list emitted by the v3 research router
 * (`backend/medieval_forge/api/v3/research.py:get_providers`). Each entry is
 * scrubbed of secrets server-side (T-07-07b-01) and may carry the optional
 * `available_models` array — REVIEWS fix #5 — which the ProviderSelector
 * consumes to apply its ordered preference list.
 *
 * Interaction contract (UI-SPEC §Interaction Contract, "Provider health
 * refresh" row): poll every 15s while the ResearchDialog is open. The hook
 * is opt-in via the `enabled` flag so the InspectorSidebar can keep the
 * query idle (and silent) when the dialog is not mounted, and switch it on
 * when the dialog opens.
 */
import { useQuery } from '@tanstack/react-query'

export interface ProviderEntry {
  provider_id: string
  display_name: string
  healthy: boolean
  message: string
  configured: boolean
  /**
   * REVIEWS fix #5 — present for Ollama (sourced from `client.list()`).
   * Absent for Claude (no local model registry). The frontend ProviderSelector
   * applies an ordered preference list against this array to pick a default.
   */
  available_models?: string[]
}

/**
 * useProviders — wraps GET /api/v3/research/providers.
 *
 * @param enabled when false, the query is idle (no fetch, no interval). The
 *   ResearchDialog flips this to true on `Dialog.Root` open and back to false
 *   on close so we do not burn polls in the background.
 */
export function useProviders(enabled: boolean = true) {
  return useQuery<ProviderEntry[]>({
    queryKey: ['v3', 'research', 'providers'],
    queryFn: async () => {
      const res = await fetch('/api/v3/research/providers')
      if (!res.ok) throw new Error(`providers fetch failed: ${res.status}`)
      return res.json() as Promise<ProviderEntry[]>
    },
    enabled,
    // 15s — UI-SPEC §Interaction Contract row "Provider health refresh".
    refetchInterval: enabled ? 15_000 : false,
  })
}
