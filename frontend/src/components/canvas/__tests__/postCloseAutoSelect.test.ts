/**
 * Phase 08.3 Plan 08 — postCloseAutoSelect vitest spec (TDD RED→GREEN)
 *
 * Tests the pure resolveAutoSelect helper: pending name absent → no select;
 * pending name present → returns name; exact match (not substring).
 *
 * Descriptive test names + explicit string fixtures per project memory
 * feedback-tests-descriptive.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { resolveAutoSelect } from '../CanvasViewer'
import type { BaronyRender } from '../../../hooks/useCanvasArtifacts'
import { useUIStore } from '../../../stores/uiStore'

// ── Minimal BaronyRender fixtures ─────────────────────────────────────────────
function makeBarony(id: string): BaronyRender {
  return {
    id,
    name: id,
    color: [100, 100, 100],
  } as unknown as BaronyRender
}

describe('resolveAutoSelect', () => {
  it('pending name absent from baronies → returns null (no selectBarony call)', () => {
    const baronies = [makeBarony('Baronato-111'), makeBarony('Baronato-222')]
    const result = resolveAutoSelect('Baronato-999', baronies)
    expect(result).toBeNull()
  })

  it('pending name present in baronies → returns the matching name', () => {
    const baronies = [makeBarony('Baronato-111'), makeBarony('Baronato-X'), makeBarony('Baronato-222')]
    const result = resolveAutoSelect('Baronato-X', baronies)
    expect(result).toBe('Baronato-X')
  })

  it('name match is exact id equality — not substring: "Baronato-X-suffix" does NOT satisfy "Baronato-X"', () => {
    const baronies = [makeBarony('Baronato-X-suffix'), makeBarony('Baronato-X-other')]
    const result = resolveAutoSelect('Baronato-X', baronies)
    expect(result).toBeNull()
  })

  it('empty pending name returns null regardless of baronies', () => {
    const baronies = [makeBarony('Baronato-X')]
    expect(resolveAutoSelect('', baronies)).toBeNull()
  })

  it('empty baronies array → returns null', () => {
    expect(resolveAutoSelect('Baronato-X', [])).toBeNull()
  })
})

describe('auto-select watcher semantics (selectBarony call integration)', () => {
  beforeEach(() => {
    // Reset uiStore selection state before each test
    useUIStore.setState({ selectedBaronyId: null } as Parameters<typeof useUIStore.setState>[0])
  })

  it('when resolveAutoSelect returns a name, selectBarony is called with that name', () => {
    const spy = vi.spyOn(useUIStore.getState(), 'selectBarony')
    const baronies = [makeBarony('Baronato-X')]
    const match = resolveAutoSelect('Baronato-X', baronies)
    if (match) useUIStore.getState().selectBarony(match)
    expect(spy).toHaveBeenCalledWith('Baronato-X')
    expect(spy).toHaveBeenCalledTimes(1)
    spy.mockRestore()
  })

  it('when resolveAutoSelect returns null, selectBarony is NOT called', () => {
    const spy = vi.spyOn(useUIStore.getState(), 'selectBarony')
    const baronies = [makeBarony('Baronato-111')]
    const match = resolveAutoSelect('Baronato-X', baronies)
    if (match) useUIStore.getState().selectBarony(match)
    expect(spy).not.toHaveBeenCalled()
    spy.mockRestore()
  })
})
