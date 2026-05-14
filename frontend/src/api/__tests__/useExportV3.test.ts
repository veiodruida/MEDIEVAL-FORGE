/**
 * Phase 07 Plan 10 Task 1 — useExportV3 mutation tests.
 *
 * Contract:
 *   - POSTs to /api/v3/projects/{id}/export (NOT v1 /api/projects/{id}/export)
 *   - 201 returns ExportResponse
 *   - 422 throws ExportValidationError with parsed envelope
 *   - 5xx throws generic Error
 *   - dryRun=true appends ?dry_run=true and returns DryRunReport on 200
 *   - dryRun=true 422 also throws ExportValidationError (same envelope shape)
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import {
  useExportV3,
  ExportValidationError,
  type ValidationEnvelope,
} from '../useExportV3'

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0 },
      mutations: { retry: false },
    },
  })
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      QueryClientProvider,
      { client: queryClient },
      children,
    )
  }
}

const PROJECT_ID = '00000000-0000-4000-8000-000000000001'

const MOCK_201: import('../useExportV3').ExportResponse = {
  project_id: PROJECT_ID,
  zip_filename: `medieval-forge-${PROJECT_ID}-2026-05-14T00-00-00Z.zip`,
  size_bytes: 1024,
  download_url: `/api/v3/projects/${PROJECT_ID}/export/download`,
}

const MOCK_422_ENVELOPE: ValidationEnvelope = {
  detail: {
    summary: '2 errors blocked export',
    errors: [
      {
        code: 'COLOR_COLLISION',
        severity: 'error',
        file: 'lookup_barony_colors.json',
        context: { rgb: [255, 0, 0] },
        message: 'Two regions share the same color',
      },
      {
        code: 'MISSING_ORIGINAL_IDX',
        severity: 'error',
        file: 'territory_metadata.json',
        context: { index: 17 },
        message: 'condado 17 lacks original_idx',
      },
    ],
    warnings: [],
  },
}

describe('useExportV3', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('POSTs to /api/v3/projects/{id}/export (v3 endpoint, not v1)', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => MOCK_201,
      text: async () => '',
    } as Response)

    const { result } = renderHook(() => useExportV3(PROJECT_ID), {
      wrapper: makeWrapper(),
    })
    await result.current.mutateAsync({})

    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit]
    expect(url).toBe(`/api/v3/projects/${PROJECT_ID}/export`)
    expect(url).not.toContain('/api/projects/')
    expect(init.method).toBe('POST')
  })

  it('returns ExportResponse on 201', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => MOCK_201,
      text: async () => '',
    } as Response)

    const { result } = renderHook(() => useExportV3(PROJECT_ID), {
      wrapper: makeWrapper(),
    })
    const data = await result.current.mutateAsync({})
    expect(data).toEqual(MOCK_201)
  })

  it('throws ExportValidationError on 422 with parsed envelope', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: async () => MOCK_422_ENVELOPE,
      text: async () => JSON.stringify(MOCK_422_ENVELOPE),
    } as Response)

    const { result } = renderHook(() => useExportV3(PROJECT_ID), {
      wrapper: makeWrapper(),
    })

    let caught: unknown = null
    try {
      await result.current.mutateAsync({})
    } catch (err) {
      caught = err
    }
    expect(caught).toBeInstanceOf(ExportValidationError)
    const validationErr = caught as ExportValidationError
    expect(validationErr.envelope).toEqual(MOCK_422_ENVELOPE)
    expect(validationErr.envelope.detail.errors).toHaveLength(2)
  })

  it('throws generic Error on 500', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: async () => ({}),
      text: async () => 'boom',
    } as Response)

    const { result } = renderHook(() => useExportV3(PROJECT_ID), {
      wrapper: makeWrapper(),
    })

    let caught: unknown = null
    try {
      await result.current.mutateAsync({})
    } catch (err) {
      caught = err
    }
    expect(caught).toBeInstanceOf(Error)
    expect(caught).not.toBeInstanceOf(ExportValidationError)
    expect((caught as Error).message).toContain('500')
  })

  it('appends ?dry_run=true when dryRun: true and returns DryRunReport', async () => {
    const dryRunOk = { dry_run: true, passed: true, errors: [], warnings: [] }
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => dryRunOk,
      text: async () => '',
    } as Response)

    const { result } = renderHook(() => useExportV3(PROJECT_ID), {
      wrapper: makeWrapper(),
    })
    const data = await result.current.mutateAsync({ dryRun: true })

    const [url] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit]
    expect(url).toBe(`/api/v3/projects/${PROJECT_ID}/export?dry_run=true`)
    expect(data).toEqual(dryRunOk)
  })

  it('throws ExportValidationError on dryRun 422 (same envelope as real export)', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: async () => ({ dry_run: true, ...MOCK_422_ENVELOPE }),
      text: async () => '',
    } as Response)

    const { result } = renderHook(() => useExportV3(PROJECT_ID), {
      wrapper: makeWrapper(),
    })

    let caught: unknown = null
    try {
      await result.current.mutateAsync({ dryRun: true })
    } catch (err) {
      caught = err
    }
    expect(caught).toBeInstanceOf(ExportValidationError)
    expect((caught as ExportValidationError).envelope.detail.errors).toHaveLength(2)
  })

  it('throws when projectId is undefined', async () => {
    const { result } = renderHook(() => useExportV3(undefined), {
      wrapper: makeWrapper(),
    })
    await expect(result.current.mutateAsync({})).rejects.toThrow(/projectId/)
  })
})
