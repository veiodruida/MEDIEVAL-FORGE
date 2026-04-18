import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useKeyboardShortcuts } from './useKeyboardShortcuts'
import { useUIStore } from '../stores/uiStore'

function fireKey(opts: Partial<KeyboardEventInit> & { key: string }) {
  const evt = new KeyboardEvent('keydown', { bubbles: true, cancelable: true, ...opts })
  window.dispatchEvent(evt)
  return evt
}

describe('useKeyboardShortcuts', () => {
  beforeEach(() => {
    useUIStore.setState({ selectedTerritoryId: 'C_X' })
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('Esc clears selection when no editable element is focused', () => {
    renderHook(() => useKeyboardShortcuts(() => {}))
    fireKey({ key: 'Escape' })
    expect(useUIStore.getState().selectedTerritoryId).toBeNull()
  })

  it('Esc does NOT clear selection when an <input> is focused', () => {
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()
    renderHook(() => useKeyboardShortcuts(() => {}))
    fireKey({ key: 'Escape' })
    expect(useUIStore.getState().selectedTerritoryId).toBe('C_X')
  })

  it('Esc does NOT clear selection when a <textarea> is focused', () => {
    const ta = document.createElement('textarea')
    document.body.appendChild(ta)
    ta.focus()
    renderHook(() => useKeyboardShortcuts(() => {}))
    fireKey({ key: 'Escape' })
    expect(useUIStore.getState().selectedTerritoryId).toBe('C_X')
  })

  it('Esc does NOT clear selection when a contenteditable is focused', () => {
    const div = document.createElement('div')
    div.contentEditable = 'true'
    document.body.appendChild(div)
    div.focus()
    renderHook(() => useKeyboardShortcuts(() => {}))
    fireKey({ key: 'Escape' })
    expect(useUIStore.getState().selectedTerritoryId).toBe('C_X')
  })

  it('Ctrl+0 calls onFitToView and preventDefault()', () => {
    const onFit = vi.fn()
    renderHook(() => useKeyboardShortcuts(onFit))
    const evt = fireKey({ key: '0', ctrlKey: true })
    expect(onFit).toHaveBeenCalledOnce()
    expect(evt.defaultPrevented).toBe(true)
  })

  it('Cmd+0 calls onFitToView and preventDefault()', () => {
    const onFit = vi.fn()
    renderHook(() => useKeyboardShortcuts(onFit))
    const evt = fireKey({ key: '0', metaKey: true })
    expect(onFit).toHaveBeenCalledOnce()
    expect(evt.defaultPrevented).toBe(true)
  })

  it('removes the listener on unmount (no leak between renders)', () => {
    const onFit = vi.fn()
    const { unmount } = renderHook(() => useKeyboardShortcuts(onFit))
    unmount()
    fireKey({ key: '0', ctrlKey: true })
    expect(onFit).not.toHaveBeenCalled()
  })
})
