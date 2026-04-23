import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useCanvasArtifacts } from './useCanvasArtifacts'

// Minimal projection — enough to gate `enabled: Boolean(projectId && projection)`
const FAKE_PROJECTION = {
  mapW: 1920,
  mapH: 1080,
  lonToX: (x: number) => x,
  latToY: (y: number) => y,
} as unknown as Parameters<typeof useCanvasArtifacts>[1]

const fetchSpy = vi.fn()
beforeEach(() => {
  fetchSpy.mockReset()
  fetchSpy.mockResolvedValue(
    new Response(JSON.stringify({ type: 'FeatureCollection', features: [] }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
  ;(globalThis as unknown as { fetch: typeof fetch }).fetch = fetchSpy as unknown as typeof fetch
})

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return function W({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: qc }, children)
  }
}

describe('useCanvasArtifacts — GAP-04 H4 cache-bust (cacheVersion propagation)', () => {
  it('appends ?v=<cacheVersion> to every preview URL so browser HTTP cache is invalidated', async () => {
    renderHook(() => useCanvasArtifacts('p1', FAKE_PROJECTION, '2026-04-23T10:00:00Z'), {
      wrapper: wrapper(),
    })

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalled()
    })

    const urls = fetchSpy.mock.calls.map((c) => c[0] as string)
    // Every fetched preview URL must carry ?v=<encoded cacheVersion>
    for (const url of urls) {
      expect(url).toMatch(/\?v=2026-04-23T10%3A00%3A00Z$/)
    }
    // All five sidecar/geojson endpoints should have been queued
    expect(urls.some((u) => u.includes('territories.geojson'))).toBe(true)
    expect(urls.some((u) => u.includes('condado_colors.json'))).toBe(true)
    expect(urls.some((u) => u.includes('barony_colors.json'))).toBe(true)
    expect(urls.some((u) => u.includes('territory_metadata.json'))).toBe(true)
  })

  it('omits ?v= when cacheVersion is undefined (back-compat for callers without updated_at)', async () => {
    renderHook(() => useCanvasArtifacts('p1', FAKE_PROJECTION, undefined), {
      wrapper: wrapper(),
    })

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalled()
    })

    const urls = fetchSpy.mock.calls.map((c) => c[0] as string)
    for (const url of urls) {
      expect(url).not.toMatch(/\?v=/)
    }
  })
})
