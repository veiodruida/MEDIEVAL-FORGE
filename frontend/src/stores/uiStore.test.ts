import { describe, it, expect, beforeEach } from 'vitest'
import { useUIStore } from './uiStore'
import { act } from 'react'

// Reset store between tests
beforeEach(() => {
  useUIStore.setState({
    selectedTerritoryId: null,
    layerVisibility: {
      terrain: true,
      territories: true,
      borders: true,
      capitals: true,
      labels: false,
    },
  })
})

describe('uiStore default state (D-09)', () => {
  it('selectedTerritoryId is null', () => {
    expect(useUIStore.getState().selectedTerritoryId).toBeNull()
  })

  it('terrain is visible by default', () => {
    expect(useUIStore.getState().layerVisibility.terrain).toBe(true)
  })

  it('territories is visible by default', () => {
    expect(useUIStore.getState().layerVisibility.territories).toBe(true)
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
  it('toggles terrain from true to false', () => {
    act(() => useUIStore.getState().toggleLayer('terrain'))
    expect(useUIStore.getState().layerVisibility.terrain).toBe(false)
  })

  it('toggles labels from false to true', () => {
    act(() => useUIStore.getState().toggleLayer('labels'))
    expect(useUIStore.getState().layerVisibility.labels).toBe(true)
  })

  it('double toggle restores original value', () => {
    act(() => useUIStore.getState().toggleLayer('territories'))
    act(() => useUIStore.getState().toggleLayer('territories'))
    expect(useUIStore.getState().layerVisibility.territories).toBe(true)
  })
})
