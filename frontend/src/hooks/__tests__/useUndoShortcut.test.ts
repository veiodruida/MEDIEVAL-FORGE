import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { fireEvent } from '@testing-library/dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import { useUndoShortcut } from '../useUndoShortcut'
import { useProjectStore } from '../../stores/useProjectStore'
import { useEditorStore } from '../../stores/useEditorStore'

function createWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children)
}

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

    renderHook(() => useUndoShortcut(), { wrapper: createWrapper() })

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

    renderHook(() => useUndoShortcut(), { wrapper: createWrapper() })

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

    renderHook(() => useUndoShortcut(), { wrapper: createWrapper() })

    fireEvent.keyDown(window, { key: 'z', metaKey: true })
    expect(undoSpy).toHaveBeenCalledTimes(1)

    // Restore
    Object.defineProperty(navigator, 'platform', {
      value: '',
      configurable: true,
    })
  })

  it('Ctrl+Z also calls popUndoLabel (label stack synchronization — Pitfall 7)', () => {
    vi.spyOn(useProjectStore.temporal, 'getState').mockReturnValue({
      undo: vi.fn(),
      redo: vi.fn(),
      pastStates: [],
      futureStates: [],
      pause: vi.fn(),
      resume: vi.fn(),
      clear: vi.fn(),
    } as ReturnType<typeof useProjectStore.temporal.getState>)

    const popUndoLabelSpy = vi.spyOn(useEditorStore.getState(), 'popUndoLabel')

    renderHook(() => useUndoShortcut(), { wrapper: createWrapper() })

    fireEvent.keyDown(window, { key: 'z', ctrlKey: true })
    expect(popUndoLabelSpy).toHaveBeenCalledTimes(1)
  })

  it('Ctrl+Y also calls popRedoLabel (label stack synchronization — Pitfall 7)', () => {
    vi.spyOn(useProjectStore.temporal, 'getState').mockReturnValue({
      undo: vi.fn(),
      redo: vi.fn(),
      pastStates: [],
      futureStates: [],
      pause: vi.fn(),
      resume: vi.fn(),
      clear: vi.fn(),
    } as ReturnType<typeof useProjectStore.temporal.getState>)

    const popRedoLabelSpy = vi.spyOn(useEditorStore.getState(), 'popRedoLabel')

    renderHook(() => useUndoShortcut(), { wrapper: createWrapper() })

    fireEvent.keyDown(window, { key: 'y', ctrlKey: true })
    expect(popRedoLabelSpy).toHaveBeenCalledTimes(1)
  })
})
