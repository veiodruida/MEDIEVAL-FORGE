/**
 * Phase 07 Plan 10 — TanStack mutation wrapping POST /api/v3/projects/{id}/export
 * with the D-08 422 envelope branch and gate-only dry-run support.
 *
 * Behavior contract (07-UI-SPEC §Surface 3 + 07-RESEARCH §Example 5):
 *  - dryRun: false (default) → real export endpoint
 *      201 → returns ExportResponse JSON (download_url + zip_filename + size_bytes)
 *      422 → throws ExportValidationError(envelope)
 *      4xx (non-422) / 5xx / network → throws generic Error
 *  - dryRun: true → same endpoint with the gate-only query flag
 *      200 → returns DryRunReport { dry_run, passed, errors, warnings }
 *      422 → throws ExportValidationError(envelope) — same envelope as real export
 *
 * Replaces the legacy `useExport` hook in client.ts (DELETED in Plan 10 Task 3
 * per WARNING 4 / D-V3-04 no transitional shims).
 */
import { useMutation, useQueryClient } from '@tanstack/react-query'

// ---------------------------------------------------------------------------
// Wire types
// ---------------------------------------------------------------------------

export interface ExportResponse {
  project_id: string
  zip_filename: string
  size_bytes: number
  download_url: string
}

export interface ValidationErrorEntry {
  code: string
  severity: 'error' | 'warning'
  file: string | null
  context: Record<string, unknown>
  message: string
}

export interface ValidationEnvelope {
  detail: {
    summary: string
    errors: ValidationErrorEntry[]
    warnings: ValidationErrorEntry[]
  }
  dry_run?: boolean
}

export interface DryRunReport {
  dry_run: true
  passed: boolean
  errors: ValidationErrorEntry[]
  warnings: ValidationErrorEntry[]
}

/**
 * Typed error surfaced when the backend returns 422 with the D-08 envelope.
 * The caller pattern-matches via `err instanceof ExportValidationError` and
 * pulls `err.envelope.detail` to render the `ExportErrorDialog`.
 */
export class ExportValidationError extends Error {
  readonly envelope: ValidationEnvelope
  constructor(envelope: ValidationEnvelope) {
    const count = envelope.detail?.errors?.length ?? 0
    super(`Export validation failed (${count} error${count === 1 ? '' : 's'})`)
    this.name = 'ExportValidationError'
    this.envelope = envelope
  }
}

export interface UseExportV3Variables {
  dryRun?: boolean
}

export type UseExportV3Result = ExportResponse | DryRunReport

/**
 * TanStack mutation for the v3 export endpoint. Pass `{ dryRun: true }` to
 * trigger the gate-only path. On 422 the mutation rejects with
 * `ExportValidationError` whose `envelope` is the parsed JSON body.
 */
export function useExportV3(projectId: string | undefined) {
  const qc = useQueryClient()
  return useMutation<UseExportV3Result, Error, UseExportV3Variables>({
    mutationFn: async ({ dryRun = false } = {}) => {
      if (!projectId) {
        throw new Error('useExportV3: projectId is required')
      }
      const qs = dryRun ? '?dry_run=true' : ''
      const res = await fetch(`/api/v3/projects/${projectId}/export${qs}`, {
        method: 'POST',
      })
      if (res.status === 422) {
        const envelope = (await res.json()) as ValidationEnvelope
        throw new ExportValidationError(envelope)
      }
      if (!res.ok) {
        const text = await res.text().catch(() => '')
        throw new Error(
          `EXPORT_FAILED: ${res.status} ${res.statusText}${text ? ` — ${text}` : ''}`,
        )
      }
      return (await res.json()) as UseExportV3Result
    },
    onSuccess: (_data, variables) => {
      // Only invalidate project caches for real exports (dry-run does not flip status).
      if (!variables?.dryRun) {
        qc.invalidateQueries({ queryKey: ['projects', projectId] })
        qc.invalidateQueries({ queryKey: ['projects'] })
        qc.invalidateQueries({ queryKey: ['v3-status', projectId] })
      }
    },
  })
}
