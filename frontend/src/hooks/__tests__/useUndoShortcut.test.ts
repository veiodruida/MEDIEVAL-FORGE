import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { fireEvent } from '@testing-library/dom'
import { useUndoShortcut } from '../useUndoShortcut'  // will fail RED until P03
import { useProjectStore } from '../../stores/useProjectStore'  // will fail RED until P03

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('useUndoShortcut — keyboard bindings', () => {
  it('Ctrl+Z calls temporal.undo()', () => {
    const undoSpy = vi.fn()
    vi.spyOn(useProjectStore.temporal, 'getState').mockReturnValue({
      undo: undoSpy,
      redo: vi.fn(),
      pastStates: [],
      futureStates: [],
      pause: vi.fn(),
      resume: vi.fn(),
      clear: vi.fn(),
    } as ReturnType<typeof useProjectStore.temporal.getState>)

    renderHook(() => useUndoShortcut())

    fireEvent.keyDown(window, { key: 'z', ctrlKey: true })
    expect(undoSpy).toHaveBeenCalledTimes(1)
  })

  it('Ctrl+Y calls temporal.redo()', () => {
    const redoSpy = vi.fn()
    vi.spyOn(useProjectStore.temporal, 'getState').mockReturnValue({
      undo: vi.fn(),
      redo: redoSpy,
      pastStates: [],
      futureStates: [],
      pause: vi.fn(),
      resume: vi.fn(),
      clear: vi.fn(),
    } as ReturnType<typeof useProjectStore.temporal.getState>)

    renderHook(() => useUndoShortcut())

    fireEvent.keyDown(window, { key: 'y', ctrlKey: true })
    expect(redoSpy).toHaveBeenCalledTimes(1)
  })

  it('Cmd+Z on Mac also calls undo', () => {
    const undoSpy = vi.fn()
    vi.spyOn(useProjectStore.temporal, 'getState').mockReturnValue({
      undo: undoSpy,
      redo: vi.fn(),
      pastStates: [],
      futureStates: [],
      pause: vi.fn(),
      resume: vi.fn(),
      clear: vi.fn(),
    } as ReturnType<typeof useProjectStore.temporal.getState>)

    // Mock navigator.platform to simulate Mac
    Object.defineProperty(navigator, 'platform', {
      value: 'MacIntel',
      configurable: true,
    })

    renderHook(() => useUndoShortcut())

    fireEvent.keyDown(window, { key: 'z', metaKey: true })
    expect(undoSpy).toHaveBeenCalledTimes(1)

    // Restore
    Object.defineProperty(navigator, 'platform', {
      value: '',
      configurable: true,
    })
  })
})
