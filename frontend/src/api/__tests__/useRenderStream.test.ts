/**
 * Plan 04-03 Task 1/4 — useRenderStream unit tests.
 * Tests the SSE consumer: subscribes to /render/stream, dispatches to useRunStore.
 * Task 4 migration: all dispatches now go through useRunStore (useRenderStore deleted).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useRenderStream } from '../useRenderStream'
import { useRunStore } from '../../stores/useRunStore'

// ---------------------------------------------------------------------------
// FakeEventSource — jsdom does not implement EventSource; this shim allows
// synchronous message injection via instance.emit().
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

  triggerError() {
    this.onerror?.(new Event('error'))
  }

  close() {
    this.closed = true
    this.readyState = 2
  }

  static reset() {
    FakeEventSource.instances = []
  }
}

// Install globally before tests
vi.stubGlobal('EventSource', FakeEventSource)

function lastInstance(): FakeEventSource {
  const instances = (FakeEventSource as unknown as FakeEventSourceCtor).instances
  return instances[instances.length - 1]
}

describe('useRenderStream', () => {
  beforeEach(() => {
    FakeEventSource.instances = []
    useRunStore.getState().reset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('subscribes to /api/v3/projects/{id}/render/stream', () => {
    const { result } = renderHook(() => useRenderStream())

    act(() => {
      result.current.subscribe('proj-1')
    })

    const es = lastInstance()
    expect(es).toBeDefined()
    expect(es.url).toBe('/api/v3/projects/proj-1/render/stream')
  })

  it('translates stage_start envelope to runStore.startStage', () => {
    const { result } = renderHook(() => useRenderStream())

    act(() => {
      result.current.subscribe('proj-1')
    })

    act(() => {
      lastInstance().emit({ event_type: 'stage_start', stage: 'smooth', message: '' })
    })

    expect(useRunStore.getState().currentStage).toBe('smooth')
  })

  it('translates stage_done envelope to runStore.finishStage', () => {
    const { result } = renderHook(() => useRenderStream())

    act(() => {
      result.current.subscribe('proj-1')
    })

    act(() => {
      lastInstance().emit({ event_type: 'stage_start', stage: 'smooth', message: '' })
    })
    act(() => {
      lastInstance().emit({ event_type: 'stage_done', stage: 'smooth', message: '' })
    })

    expect(useRunStore.getState().completedStages).toContain('smooth')
    expect(useRunStore.getState().currentStage).toBeNull()
  })

  it('translates stage_cancel envelope to runStore.revertStage', () => {
    const { result } = renderHook(() => useRenderStream())

    act(() => {
      result.current.subscribe('proj-1')
    })

    // Seed a rendering state so revertStage is meaningful
    act(() => {
      useRunStore.getState().startRender('r-1')
    })

    act(() => {
      lastInstance().emit({
        event_type: 'stage_cancel',
        stage: 'smooth',
        message: 'prior-token-abc',
      })
    })

    // priorTokens now lives in useRunStore (Task 4 migration)
    const priorTokens = useRunStore.getState().priorTokens
    expect(priorTokens['smooth']).toBe('prior-token-abc')
  })

  it('handles done envelope by closing EventSource and finish(generated)', () => {
    const { result } = renderHook(() => useRenderStream())

    act(() => {
      result.current.subscribe('proj-1')
    })

    const es = lastInstance()

    act(() => {
      es.emit({ event_type: 'done', stage: null, message: '' })
    })

    // EventSource should be closed after done
    expect(es.closed).toBe(true)
    // run store should transition to generated
    expect(useRunStore.getState().state).toBe('generated')
  })
})
