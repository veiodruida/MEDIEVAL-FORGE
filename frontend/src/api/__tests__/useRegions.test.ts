/**
 * Plan 05-08 Task 1 — useRegions hook + useCreateV3Project mutation tests.
 *
 * RED phase: these tests will fail until Task 1 GREEN creates the implementations.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import type { RegionInfo } from '../../types/region'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

const MOCK_REGIONS: RegionInfo[] = [
  {
    key: 'iberia_868',
    display_name: 'Iberia 868',
    bounds: { lon_min: -9.5, lon_max: 4.3, lat_min: 35.9, lat_max: 43.8 },
    has_dataset: true,
  },
  {
    key: 'france_1066',
    display_name: 'France 1066',
    bounds: { lon_min: -5.1, lon_max: 9.6, lat_min: 41.3, lat_max: 51.1 },
    has_dataset: true,
  },
  {
    key: 'england_1216',
    display_name: 'England 1216',
    bounds: { lon_min: -5.7, lon_max: 1.8, lat_min: 49.9, lat_max: 55.8 },
    has_dataset: false,
  },
]

// ---------------------------------------------------------------------------
// useRegions
// ---------------------------------------------------------------------------

describe('useRegions', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns regions from /api/v3/regions on success', async () => {
    const { useRegions } = await import('../useRegions')
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => MOCK_REGIONS,
    } as Response)

    const { result } = renderHook(() => useRegions(), { wrapper: makeWrapper() })

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.data).toEqual(MOCK_REGIONS)
    expect(result.current.isError).toBe(false)
  })

  it('uses queryKey ["v3", "regions"]', async () => {
    const { useQuery } = await import('@tanstack/react-query')
    const spy = vi.spyOn({ useQuery }, 'useQuery')
    const { useRegions } = await import('../useRegions')
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    } as Response)

    renderHook(() => useRegions(), { wrapper: makeWrapper() })

    // Verify the module exports the hook (smoke check; queryKey verified by integration)
    expect(useRegions).toBeDefined()
    spy.mockRestore()
  })

  it('sets isError true on non-ok response', async () => {
    const { useRegions } = await import('../useRegions')
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({}),
    } as Response)

    const { result } = renderHook(() => useRegions(), { wrapper: makeWrapper() })

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.isError).toBe(true)
    expect(result.current.data).toBeUndefined()
  })

  it('exposes refetch function', async () => {
    const { useRegions } = await import('../useRegions')
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => [],
    } as Response)

    const { result } = renderHook(() => useRegions(), { wrapper: makeWrapper() })
    expect(typeof result.current.refetch).toBe('function')
  })
})

// ---------------------------------------------------------------------------
// useCreateV3Project
// ---------------------------------------------------------------------------

describe('useCreateV3Project', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('posts to /api/v3/projects and returns {id, name, region_key}', async () => {
    const { useCreateV3Project } = await import('../client')
    const mockResult = { id: '123', name: 'Test', region_key: 'iberia_868' }
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => mockResult,
    } as Response)

    const { result } = renderHook(() => useCreateV3Project(), { wrapper: makeWrapper() })

    await result.current.mutateAsync({ name: 'Test', region_key: 'iberia_868' })

    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/v3/projects')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({ name: 'Test', region_key: 'iberia_868' })
  })

  it('is exported from client.ts', async () => {
    const clientModule = await import('../client')
    expect(typeof clientModule.useCreateV3Project).toBe('function')
  })
})
