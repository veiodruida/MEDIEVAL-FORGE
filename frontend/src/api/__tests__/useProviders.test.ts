/**
 * Plan 07-09a Task 1 RED — useProviders hook unit tests.
 *
 * Verifies:
 *   - TanStack Query hook hitting GET /api/v3/research/providers
 *   - Returns ProviderEntry[] with optional available_models (REVIEWS fix #5)
 *   - refetchInterval 15s when enabled; disabled when not (UI-SPEC §Interaction Contract)
 *   - isError true on non-ok response
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

const PROVIDERS_OLLAMA_AND_CLAUDE_HEALTHY = [
  {
    provider_id: 'claude',
    display_name: 'Claude (Anthropic)',
    healthy: true,
    message: 'ok',
    configured: true,
  },
  {
    provider_id: 'ollama',
    display_name: 'Ollama (local)',
    healthy: true,
    message: 'ok',
    configured: true,
    available_models: ['qwen2.5:7b', 'qwen2.5-coder:14b'],
  },
]

describe('useProviders', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('fetches GET /api/v3/research/providers and returns ProviderEntry[] with available_models', async () => {
    const { useProviders } = await import('../useProviders')
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => PROVIDERS_OLLAMA_AND_CLAUDE_HEALTHY,
    } as Response)

    const { result } = renderHook(() => useProviders(true), {
      wrapper: makeWrapper(),
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.data).toEqual(PROVIDERS_OLLAMA_AND_CLAUDE_HEALTHY)
    expect(vi.mocked(fetch)).toHaveBeenCalledWith('/api/v3/research/providers')

    // available_models surfaced on the Ollama entry (REVIEWS fix #5)
    const ollama = result.current.data?.find((p) => p.provider_id === 'ollama')
    expect(ollama?.available_models).toEqual(['qwen2.5:7b', 'qwen2.5-coder:14b'])
  })

  it('returns disabled query when enabled=false (no fetch)', async () => {
    const { useProviders } = await import('../useProviders')
    const { result } = renderHook(() => useProviders(false), {
      wrapper: makeWrapper(),
    })
    // Disabled query — never enters loading
    await new Promise((r) => setTimeout(r, 10))
    expect(result.current.fetchStatus).toBe('idle')
    expect(vi.mocked(fetch)).not.toHaveBeenCalled()
  })

  it('sets isError true on non-ok provider response', async () => {
    const { useProviders } = await import('../useProviders')
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 503,
      json: async () => ({}),
    } as Response)

    const { result } = renderHook(() => useProviders(true), {
      wrapper: makeWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.data).toBeUndefined()
  })
})
