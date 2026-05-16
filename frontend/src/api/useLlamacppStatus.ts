/**
 * Phase 07.1 Plan 06 Task 3 — review-fix #6 (Codex MEDIUM).
 *
 * Canonical "is a llama-server up?" source for the UI. Replaces the broken
 * `Boolean(launch.data?.ok) || health.data?.healthy` derivation that read
 * from TanStack mutation cache and went stale across close/reopen/refresh
 * (Gemini + Codex HIGH).
 *
 * Polls GET /api/v3/llm/llamacpp/launch every 5s — but ONLY while the
 * consumer enables it (pass `enabled = isOpen` from AuthSetupSheet so we
 * don't burn requests when the sheet is closed).
 *
 * Backend shape (plan 07.1-05 review-fix #4):
 *   {running: bool, pid: int|None, model: str|None, base_url: str|None, started_at: str|None}
 */
import { useQuery } from '@tanstack/react-query'

export interface LlamacppStatus {
  running: boolean
  pid: number | null
  model: string | null
  base_url: string | null
  started_at: string | null
}

/**
 * useLlamacppStatus — review-fix #6 (Codex MEDIUM).
 *
 * Canonical "is a llama-server up?" source for the UI. The 5s poll is
 * gated by the `enabled` flag so it only runs while AuthSetupSheet is open.
 * Both mutations (useLlamacppLaunch + useLlamacppShutdown) also invalidate
 * this queryKey on success for immediate feedback after user action.
 *
 * @param enabled — typically the AuthSetupSheet `open` prop.
 */
export function useLlamacppStatus(enabled = true) {
  return useQuery<LlamacppStatus>({
    queryKey: ['llamacpp-status'],
    queryFn: async () => {
      const r = await fetch('/api/v3/llm/llamacpp/launch')
      if (!r.ok) throw new Error(`llamacpp status fetch failed: ${r.status}`)
      return r.json() as Promise<LlamacppStatus>
    },
    enabled,
    refetchInterval: 5_000,
    staleTime: 4_000,
  })
}
