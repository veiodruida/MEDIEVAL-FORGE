import { describe, it, expect, beforeEach } from 'vitest'
import { useUIStore } from './uiStore'
import { act } from 'react'

// Reset store between tests. Mirrors DEFAULT_LAYER_VISIBILITY after the
// 260420-hkr rename: condados/borders/capitals on; baronies/labels off.
beforeEach(() => {
  useUIStore.setState({
    selectedTerritoryId: null,
    layerVisibility: {
      condados: true,
      baronies: false,
      borders: true,
      capitals: true,
      labels: false,
    },
  })
})

describe('uiStore default state (post-260420-hkr rename)', () => {
  it('selectedTerritoryId is null', () => {
    expect(useUIStore.getState().selectedTerritoryId).toBeNull()
  })

  it('condados is visible by default', () => {
    expect(useUIStore.getState().layerVisibility.condados).toBe(true)
  })

  it('baronies is hidden by default', () => {
    expect(useUIStore.getState().layerVisibility.baronies).toBe(false)
  })

  it('borders is visible by default', () => {
    expect(useUIStore.getState().layerVisibility.borders).toBe(true)
  })

  it('capitals is visible by default', () => {
    expect(useUIStore.getState().layerVisibility.capitals).toBe(true)
  })

  it('labels is hidden by default', () => {
    expect(useUIStore.getState().layerVisibility.labels).toBe(false)
  })
})

describe('select action', () => {
  it('sets selectedTerritoryId to a string', () => {
    act(() => useUIStore.getState().select('C_BRAGA'))
    expect(useUIStore.getState().selectedTerritoryId).toBe('C_BRAGA')
  })

  it('clears selectedTerritoryId to null', () => {
    act(() => useUIStore.getState().select('C_BRAGA'))
    act(() => useUIStore.getState().select(null))
    expect(useUIStore.getState().selectedTerritoryId).toBeNull()
  })
})

describe('toggleLayer action', () => {
  it('toggles condados from true to false', () => {
    act(() => useUIStore.getState().toggleLayer('condados'))
    expect(useUIStore.getState().layerVisibility.condados).toBe(false)
  })

  it('toggles labels from false to true', () => {
    act(() => useUIStore.getState().toggleLayer('labels'))
    expect(useUIStore.getState().layerVisibility.labels).toBe(true)
  })

  it('double toggle on baronies restores original (false) value', () => {
    act(() => useUIStore.getState().toggleLayer('baronies'))
    act(() => useUIStore.getState().toggleLayer('baronies'))
    expect(useUIStore.getState().layerVisibility.baronies).toBe(false)
  })
})
