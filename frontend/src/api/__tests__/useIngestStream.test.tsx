/**
 * Tests for useIngestStream — AbortController stop() integration.
 *
 * Test 1: hook returns object with stop function
 * Test 2: calling stop() while streaming → AbortError filtered (error stays null)
 * Test 3: after stop(), isStreaming becomes false and hook is ready for next start()
 * Test 4: start() after stop() creates a NEW AbortController (no stale signal reused)
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useIngestStream } from '../client'

// ---------------------------------------------------------------------------
// Wrapper
// ---------------------------------------------------------------------------

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
  return Wrapper
}

// ---------------------------------------------------------------------------
// Fetch mock helpers
// ---------------------------------------------------------------------------

/**
 * Build a fetch mock that returns a ReadableStream which:
 * 1. Pushes one SSE chunk immediately.
 * 2. Then blocks indefinitely (until the abort signal fires).
 *
 * Returns { abortedPromise } so tests can await actual abort.
 */
function makeStreamingFetch(signal?: AbortSignal) {
  let resolveBlock: () => void
  const blockPromise = new Promise<void>((res) => { resolveBlock = res })

  const stream = new ReadableStream({
    start(controller) {
      const encoder = new TextEncoder()
      controller.enqueue(encoder.encode('data: hello\n\n'))
      // Block until abort or manual resolve
      blockPromise.then(() => controller.close())
    },
  })

  return {
    resolveStream: resolveBlock!,
    response: new Response(stream, { status: 200 }),
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useIngestStream — AbortController', () => {
  let originalFetch: typeof globalThis.fetch

  beforeEach(() => {
    originalFetch = globalThis.fetch
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.restoreAllMocks()
  })

  // Test 1: hook exposes stop function
  it('returns an object with a stop function', () => {
    const Wrapper = makeWrapper()
    const { result } = renderHook(() => useIngestStream('proj-1'), { wrapper: Wrapper })
    expect(typeof result.current.stop).toBe('function')
    expect(typeof result.current.start).toBe('function')
    expect(typeof result.current.isStreaming).toBe('boolean')
  })

  // Test 2: stop() during stream → AbortError not forwarded to error state
  it('stop() while streaming does not set error (AbortError filtered)', async () => {
    const Wrapper = makeWrapper()

    // Track when fetch is called so we can stop() mid-stream
    let resolveFetch!: (r: Response) => void
    const fetchCalled = new Promise<void>((res) => {
      globalThis.fetch = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
        const { resolveStream, response } = makeStreamingFetch(init?.signal ?? undefined)
        // Abort the stream when signal fires
        init?.signal?.addEventListener('abort', () => resolveStream())
        res() // signal that fetch was called
        return new Promise<Response>((r) => { resolveFetch = r; r(response) })
      })
    })

    const { result } = renderHook(() => useIngestStream('proj-1'), { wrapper: Wrapper })

    // Start streaming (don't await — it runs indefinitely)
    act(() => { result.current.start('osm') })

    // Wait for fetch to be called
    await fetchCalled

    // Give the hook time to enter the read loop
    await act(async () => { await new Promise((r) => setTimeout(r, 20)) })

    // Stop mid-stream
    act(() => { result.current.stop() })

    // Wait for isStreaming to become false
    await waitFor(() => expect(result.current.isStreaming).toBe(false), { timeout: 2000 })

    // Error must be null — AbortError must be filtered out
    expect(result.current.error).toBeNull()
  })

  // Test 3: after stop(), isStreaming=false, ready for another start()
  it('after stop(), isStreaming is false and hook accepts a subsequent start()', async () => {
    const Wrapper = makeWrapper()

    let abortSignalRef: AbortSignal | undefined
    globalThis.fetch = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      abortSignalRef = init?.signal ?? undefined
      const { resolveStream, response } = makeStreamingFetch(abortSignalRef)
      abortSignalRef?.addEventListener('abort', () => resolveStream())
      return Promise.resolve(response)
    })

    const { result } = renderHook(() => useIngestStream('proj-1'), { wrapper: Wrapper })

    act(() => { result.current.start('osm') })
    await act(async () => { await new Promise((r) => setTimeout(r, 20)) })

    // Confirm streaming started
    expect(result.current.isStreaming).toBe(true)

    // Stop
    act(() => { result.current.stop() })
    await waitFor(() => expect(result.current.isStreaming).toBe(false), { timeout: 2000 })

    // Should be able to start again without error
    act(() => { result.current.start('osm') })
    await act(async () => { await new Promise((r) => setTimeout(r, 20)) })
    expect(result.current.isStreaming).toBe(true)

    // Cleanup
    act(() => { result.current.stop() })
    await waitFor(() => expect(result.current.isStreaming).toBe(false), { timeout: 2000 })
  })

  // Test 4: start() after stop() creates a NEW AbortController (verified via distinct signals)
  it('start() after stop() passes a fresh signal to fetch (distinct signal instances)', async () => {
    const Wrapper = makeWrapper()

    const signals: AbortSignal[] = []
    globalThis.fetch = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      if (init?.signal) signals.push(init.signal)
      const { resolveStream, response } = makeStreamingFetch(init?.signal ?? undefined)
      init?.signal?.addEventListener('abort', () => resolveStream())
      return Promise.resolve(response)
    })

    const { result } = renderHook(() => useIngestStream('proj-1'), { wrapper: Wrapper })

    // First start
    act(() => { result.current.start('osm') })
    await act(async () => { await new Promise((r) => setTimeout(r, 20)) })
    act(() => { result.current.stop() })
    await waitFor(() => expect(result.current.isStreaming).toBe(false), { timeout: 2000 })

    // Second start
    act(() => { result.current.start('osm') })
    await act(async () => { await new Promise((r) => setTimeout(r, 20)) })

    // fetch must have been called twice with DIFFERENT signal instances
    expect(signals.length).toBeGreaterThanOrEqual(2)
    // The second signal must be a new object (new AbortController() was called)
    expect(signals[0]).not.toBe(signals[1])
    // The first signal must have been aborted; the second must still be active
    expect(signals[0].aborted).toBe(true)
    expect(signals[1].aborted).toBe(false)

    // Cleanup
    act(() => { result.current.stop() })
    await waitFor(() => expect(result.current.isStreaming).toBe(false), { timeout: 2000 })
  })
})
