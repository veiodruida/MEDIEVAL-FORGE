/**
 * Plan 07-09a Task 1 RED — useResearchOverlay hook unit tests.
 *
 * Verifies (BLOCKER 2 + REVIEWS fix #2):
 *   - Returns {exists, covered_condado_ids, meta} from GET /api/v3/projects/{id}/research/overlay
 *   - meta carries BOTH generated_at AND applied_at (REVIEWS fix #2)
 *   - meta is null when overlay missing or sidecar missing
 *   - generated_at and applied_at can differ (cache-hit scenario)
 *   - 30s staleTime
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'

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

describe('useResearchOverlay', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns exists:false + meta:null when backend reports no overlay', async () => {
    const { useResearchOverlay } = await import('../useResearchOverlay')
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        exists: false,
        covered_condado_ids: [],
        meta: null,
      }),
    } as Response)

    const { result } = renderHook(
      () => useResearchOverlay('00000000-0000-0000-0000-000000000001'),
      { wrapper: makeWrapper() },
    )

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.data).toEqual({
      exists: false,
      covered_condado_ids: [],
      meta: null,
    })
  })

  it('returns exists:true + meta with BOTH generated_at AND applied_at (REVIEWS fix #2)', async () => {
    const { useResearchOverlay } = await import('../useResearchOverlay')
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        exists: true,
        covered_condado_ids: ['cd-leon', 'cd-castilla'],
        meta: {
          provider: 'ollama',
          model: 'qwen2.5:7b',
          generated_at: '2026-05-12T08:00:00Z',
          applied_at: '2026-05-12T08:00:01Z',
        },
      }),
    } as Response)

    const { result } = renderHook(
      () => useResearchOverlay('00000000-0000-0000-0000-000000000002'),
      { wrapper: makeWrapper() },
    )

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.data?.exists).toBe(true)
    expect(result.current.data?.covered_condado_ids).toEqual([
      'cd-leon',
      'cd-castilla',
    ])
    expect(result.current.data?.meta?.provider).toBe('ollama')
    expect(result.current.data?.meta?.model).toBe('qwen2.5:7b')
    expect(result.current.data?.meta?.generated_at).toBe('2026-05-12T08:00:00Z')
    expect(result.current.data?.meta?.applied_at).toBe('2026-05-12T08:00:01Z')
  })

  it('graceful degrade: exists:true + meta:null when sidecar is missing', async () => {
    const { useResearchOverlay } = await import('../useResearchOverlay')
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        exists: true,
        covered_condado_ids: ['cd-leon'],
        meta: null,
      }),
    } as Response)

    const { result } = renderHook(
      () => useResearchOverlay('00000000-0000-0000-0000-000000000003'),
      { wrapper: makeWrapper() },
    )

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.data?.exists).toBe(true)
    expect(result.current.data?.meta).toBeNull()
  })

  it('REVIEWS fix #2 — generated_at and applied_at differ on cache-hit re-apply', async () => {
    const { useResearchOverlay } = await import('../useResearchOverlay')
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        exists: true,
        covered_condado_ids: ['cd-leon'],
        meta: {
          provider: 'ollama',
          model: 'qwen2.5:7b',
          // generated_at: original LLM-output timestamp from prior run
          generated_at: '2026-05-10T09:00:00Z',
          // applied_at: NOW — runner re-wrote overlay from cache on second click
          applied_at: '2026-05-13T15:30:00Z',
        },
      }),
    } as Response)

    const { result } = renderHook(
      () => useResearchOverlay('00000000-0000-0000-0000-000000000004'),
      { wrapper: makeWrapper() },
    )

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.data?.meta?.generated_at).not.toBe(
      result.current.data?.meta?.applied_at,
    )
    expect(result.current.data?.meta?.generated_at).toBe('2026-05-10T09:00:00Z')
    expect(result.current.data?.meta?.applied_at).toBe('2026-05-13T15:30:00Z')
  })

  it('disabled query when projectId is undefined (no fetch)', async () => {
    const { useResearchOverlay } = await import('../useResearchOverlay')
    const { result } = renderHook(() => useResearchOverlay(undefined), {
      wrapper: makeWrapper(),
    })

    await new Promise((r) => setTimeout(r, 10))
    expect(result.current.fetchStatus).toBe('idle')
    expect(vi.mocked(fetch)).not.toHaveBeenCalled()
  })

  it('treats network 404 as exists:false + meta:null fallback (defensive — backend returns 200 with exists:false but caller may hit a misrouted path)', async () => {
    const { useResearchOverlay } = await import('../useResearchOverlay')
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'not found' }),
    } as Response)

    const { result } = renderHook(
      () => useResearchOverlay('00000000-0000-0000-0000-000000000005'),
      { wrapper: makeWrapper() },
    )

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.data).toEqual({
      exists: false,
      covered_condado_ids: [],
      meta: null,
    })
  })
})
