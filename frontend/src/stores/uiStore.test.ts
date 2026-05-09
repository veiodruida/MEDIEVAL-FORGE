import { describe, it, expect, beforeEach } from 'vitest'
import { useUIStore, selectSelectedTerritoryId, type LayerName } from './uiStore'
import { act } from 'react'

// Reset store state between tests using the canonical default. Mirrors the
// Phase 03 evolution: selectedTerritoryIds = [], 'terrain' gone from LayerName,
// overlay fields removed.
beforeEach(() => {
  useUIStore.setState({
    selectedTerritoryIds: [],
    layerVisibility: {
      condados: true,
      baronies: false,
      borders: true,
      capitals: true,
      labels: false,
    },
  })
})

describe('uiStore — multi-select state shape (Phase 03 D-17)', () => {
  it('test_initial_selectedTerritoryIds_is_empty: selectSelectedTerritoryId returns null', () => {
    expect(useUIStore.getState().selectedTerritoryIds).toEqual([])
    expect(selectSelectedTerritoryId(useUIStore.getState())).toBeNull()
  })

  it('test_selectIds_with_two_ids: stores both; selector returns first', () => {
    act(() => useUIStore.getState().selectIds(['a', 'b']))
    expect(useUIStore.getState().selectedTerritoryIds).toEqual(['a', 'b'])
    expect(selectSelectedTerritoryId(useUIStore.getState())).toBe('a')
  })

  it('test_legacy_select_string_writes_singleton_array', () => {
    act(() => useUIStore.getState().select('x'))
    expect(useUIStore.getState().selectedTerritoryIds).toEqual(['x'])
    expect(selectSelectedTerritoryId(useUIStore.getState())).toBe('x')
  })

  it('test_legacy_select_null_clears_array', () => {
    act(() => useUIStore.getState().selectIds(['x', 'y']))
    act(() => useUIStore.getState().select(null))
    expect(useUIStore.getState().selectedTerritoryIds).toEqual([])
    expect(selectSelectedTerritoryId(useUIStore.getState())).toBeNull()
  })
})

describe('uiStore — LayerName cleanup', () => {
  it("test_layerVisibility_does_not_have_terrain_key", () => {
    const keys = Object.keys(useUIStore.getState().layerVisibility) as LayerName[]
    expect(keys).not.toContain('terrain' as unknown as LayerName)
    // Sanity: the five remaining layer names are present
    expect(keys.sort()).toEqual(['baronies', 'borders', 'capitals', 'condados', 'labels'])
  })

  it("test_overlay_fields_absent_at_runtime: overlayImageUrl + overlayOpacity removed", () => {
    const state = useUIStore.getState() as Record<string, unknown>
    expect(state.overlayImageUrl).toBeUndefined()
    expect(state.overlayOpacity).toBeUndefined()
    expect(state.setOverlayImageUrl).toBeUndefined()
    expect(state.setOverlayOpacity).toBeUndefined()
  })
})

describe('uiStore — toggleLayer (carry-over)', () => {
  it('test_toggleLayer_condados_flips_to_false', () => {
    act(() => useUIStore.getState().toggleLayer('condados'))
    expect(useUIStore.getState().layerVisibility.condados).toBe(false)
  })

  it('test_toggleLayer_labels_flips_to_true', () => {
    act(() => useUIStore.getState().toggleLayer('labels'))
    expect(useUIStore.getState().layerVisibility.labels).toBe(true)
  })
})
