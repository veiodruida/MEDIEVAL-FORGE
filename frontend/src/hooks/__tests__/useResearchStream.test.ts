/**
 * Plan 07-09a Task 2 RED — useResearchStream unit tests.
 *
 * Verifies:
 *   - EventSource subscribe/unsubscribe lifecycle
 *   - Structured envelope dispatch (event_type, stage)
 *   - Dual-shape SSE tolerance (REVIEWS fix #3, Plan 03 verdict (a) — KEEP)
 *   - AbortError → terminal {phase:'failed', error_code:'aborted'} (REVIEWS fix #7)
 *   - temporal.pause()/resume() wrap (CLAUDE.md zundo discipline)
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

// ---------------------------------------------------------------------------
// FakeEventSource shim (jsdom does not implement EventSource).
// Mirrors the one in src/api/__tests__/useRenderStream.test.ts.
// ---------------------------------------------------------------------------

interface FakeEventSourceCtor {
  new (url: string): FakeEventSource
  instances: FakeEventSource[]
  reset: () => void
}

class FakeEventSource {
  static instances: FakeEventSource[] = []
  url: string
  readyState = 1
  onmessage: ((e: MessageEvent) => void) | null = null
  onerror: ((e: Event) => void) | null = null
  closed = false

  constructor(url: string) {
    this.url = url
    ;(this.constructor as unknown as FakeEventSourceCtor).instances.push(this)
  }

  emit(data: unknown) {
    if (this.closed) return
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent)
  }

  emitRaw(raw: string) {
    if (this.closed) return
    this.onmessage?.({ data: raw } as MessageEvent)
  }

  triggerAbort() {
    const err = new DOMException('aborted', 'AbortError')
    this.onerror?.(err as unknown as Event)
  }

  triggerError() {
    this.onerror?.(new Event('error'))
  }

  close() {
    this.closed = true
    this.readyState = 2
  }
}

vi.stubGlobal('EventSource', FakeEventSource)

function lastInstance(): FakeEventSource {
  const instances = (FakeEventSource as unknown as FakeEventSourceCtor)
    .instances
  return instances[instances.length - 1]
}

describe('useResearchStream', () => {
  beforeEach(() => {
    FakeEventSource.instances = []
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('subscribe opens EventSource at /api/v3/research/stream/{run_id}', async () => {
    const { useResearchStream } = await import('../useResearchStream')
    const { result } = renderHook(() => useResearchStream())

    act(() => {
      result.current.subscribe('run-abc')
    })

    const es = lastInstance()
    expect(es).toBeDefined()
    expect(es.url).toBe('/api/v3/research/stream/run-abc')
  })

  it('dispatches structured envelope to currentStage on stage_start', async () => {
    const { useResearchStream } = await import('../useResearchStream')
    const { result } = renderHook(() => useResearchStream())

    act(() => {
      result.current.subscribe('run-abc')
    })

    act(() => {
      lastInstance().emit({
        event_type: 'stage_start',
        stage: 'kingdoms',
        message: '',
        progress: 0,
      })
    })

    expect(result.current.state.phase).toBe('running')
    expect(result.current.state.currentStage).toBe('kingdoms')
  })

  it('transitions through 4 stages kingdoms → duchies → condados → baronies', async () => {
    const { useResearchStream } = await import('../useResearchStream')
    const { result } = renderHook(() => useResearchStream())

    act(() => {
      result.current.subscribe('run-1')
    })

    for (const stage of [
      'kingdoms',
      'duchies',
      'condados',
      'baronies',
    ] as const) {
      act(() => {
        lastInstance().emit({
          event_type: 'stage_start',
          stage,
          message: '',
          progress: 0,
        })
      })
      expect(result.current.state.currentStage).toBe(stage)
    }
  })

  it('terminal success envelope sets phase to succeeded', async () => {
    const { useResearchStream } = await import('../useResearchStream')
    const { result } = renderHook(() => useResearchStream())

    act(() => {
      result.current.subscribe('run-1')
    })

    act(() => {
      lastInstance().emit({
        event_type: 'terminal',
        status: 'success',
        stage: null,
        message: 'done',
      })
    })

    expect(result.current.state.phase).toBe('succeeded')
  })

  it('REVIEWS fix #3 — dual-shape: raw "Tentativa N/M" PT-BR frame parsed as retry', async () => {
    // Plan 03 SUMMARY verdict (a) confirmed: retry.py emits raw `data: Tentativa N/M`
    // SSE frames in addition to the runner's structured envelopes. The hook
    // MUST accept both shapes — see 07-03-SUMMARY.md lines 67-91.
    const { useResearchStream } = await import('../useResearchStream')
    const { result } = renderHook(() => useResearchStream())

    act(() => {
      result.current.subscribe('run-1')
    })

    // Bring the stream to a known running stage first
    act(() => {
      lastInstance().emit({
        event_type: 'stage_start',
        stage: 'condados',
        message: '',
        progress: 0,
      })
    })

    act(() => {
      // Raw PT-BR string emitted by retry.py — not JSON-parseable.
      lastInstance().emitRaw('Tentativa 2/3: JSON inválido')
    })

    expect(result.current.state.retryAttempt).toEqual({ current: 2, max: 3 })
  })

  it("REVIEWS fix #7 — AbortError maps to terminal {phase:'failed', error_code:'aborted'}", async () => {
    const { useResearchStream } = await import('../useResearchStream')
    const { result } = renderHook(() => useResearchStream())

    act(() => {
      result.current.subscribe('run-1')
    })
    act(() => {
      lastInstance().emit({
        event_type: 'stage_start',
        stage: 'kingdoms',
        message: '',
      })
    })

    act(() => {
      lastInstance().triggerAbort()
    })

    expect(result.current.state.phase).toBe('failed')
    expect(result.current.state.error_code).toBe('aborted')
    expect(result.current.state.error_message).toBe(
      'Pesquisa cancelada pelo usuário.',
    )
  })

  it('non-abort EventSource error maps to phase:failed + error_code:network', async () => {
    const { useResearchStream } = await import('../useResearchStream')
    const { result } = renderHook(() => useResearchStream())

    act(() => {
      result.current.subscribe('run-1')
    })

    act(() => {
      lastInstance().triggerError()
    })

    expect(result.current.state.phase).toBe('failed')
    expect(result.current.state.error_code).toBe('network')
  })

  it('close() shuts EventSource and clears phase to idle on next subscribe', async () => {
    const { useResearchStream } = await import('../useResearchStream')
    const { result } = renderHook(() => useResearchStream())

    act(() => {
      result.current.subscribe('run-1')
    })
    const es = lastInstance()

    act(() => {
      result.current.close()
    })

    expect(es.closed).toBe(true)
  })
})
