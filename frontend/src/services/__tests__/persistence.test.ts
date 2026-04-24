import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { onOperationFinalized, manualSave, initPersistence, setStrategy, usePersistenceStore } from '../persistence'

// Mock useProjectStore
vi.mock('../../stores/useProjectStore', () => ({
  useProjectStore: {
    getState: () => ({
      projectId: 'proj-1',
      territories: {},
      capitals: {},
    }),
  },
}))

// Mock api/edit saveSnapshot
vi.mock('../../api/edit', () => ({
  saveSnapshot: vi.fn().mockResolvedValue({ ok: true }),
}))

beforeEach(() => {
  // Reset store to clean state before each test
  usePersistenceStore.setState({ strategy: 'auto', status: 'saved', lastEditAt: null })
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('onOperationFinalized — strategy dispatch', () => {
  it('auto strategy: sets status to saving immediately', () => {
    setStrategy('auto')
    onOperationFinalized()
    expect(usePersistenceStore.getState().status).toBe('saving')
  })

  it('auto strategy: sets status to saved after 1500ms debounce', async () => {
    setStrategy('auto')
    onOperationFinalized()
    expect(usePersistenceStore.getState().status).toBe('saving')
    vi.advanceTimersByTime(1500)
    expect(usePersistenceStore.getState().status).toBe('saved')
  })

  it('auto strategy: debounce resets on rapid calls — only one saved transition', () => {
    setStrategy('auto')
    onOperationFinalized()
    vi.advanceTimersByTime(800)
    onOperationFinalized() // resets debounce
    vi.advanceTimersByTime(800) // still < 1500ms from 2nd call
    expect(usePersistenceStore.getState().status).toBe('saving')
    vi.advanceTimersByTime(700) // now 1500ms from 2nd call
    expect(usePersistenceStore.getState().status).toBe('saved')
  })

  it('per_op strategy: sets status to saved immediately', () => {
    setStrategy('per_op')
    onOperationFinalized()
    expect(usePersistenceStore.getState().status).toBe('saved')
  })

  it('explicit strategy: sets status to unsaved', () => {
    setStrategy('explicit')
    onOperationFinalized()
    expect(usePersistenceStore.getState().status).toBe('unsaved')
  })
})

describe('manualSave', () => {
  it('calls saveSnapshot and sets status to saved when strategy is explicit', async () => {
    const { saveSnapshot } = await import('../../api/edit')
    setStrategy('explicit')
    usePersistenceStore.setState({ status: 'unsaved' })
    await manualSave()
    expect(saveSnapshot).toHaveBeenCalledWith('proj-1', expect.objectContaining({
      territories: {},
      capitals: {},
    }))
    expect(usePersistenceStore.getState().status).toBe('saved')
  })

  it('is a no-op when strategy is not explicit', async () => {
    const { saveSnapshot } = await import('../../api/edit')
    setStrategy('auto')
    await manualSave()
    expect(saveSnapshot).not.toHaveBeenCalled()
  })
})

describe('initPersistence', () => {
  it('initializes strategy to auto by default and status to saved', () => {
    initPersistence()
    const state = usePersistenceStore.getState()
    expect(state.status).toBe('saved')
  })
})
