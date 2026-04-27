import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useUIStore } from '../uiStore'

// jsdom does not define URL.revokeObjectURL — define a no-op so vi.spyOn can patch it.
if (typeof URL.revokeObjectURL === 'undefined') {
  URL.revokeObjectURL = () => undefined
}

beforeEach(() => {
  // Reset store state before each test
  useUIStore.setState({
    selectedTerritoryId: null,
    layerVisibility: {
      condados: true,
      baronies: false,
      borders: true,
      capitals: true,
      labels: false,
      terrain: false,
    },
    overlayImageUrl: null,
    overlayOpacity: 0.5,
  })
})

describe('useUIStore — overlay + terrain layer extensions', () => {
  it('test_overlay_initial_state: overlayImageUrl is null and overlayOpacity is 0.5', () => {
    const state = useUIStore.getState()
    expect(state.overlayImageUrl).toBeNull()
    expect(state.overlayOpacity).toBe(0.5)
  })

  it('test_setOverlayImageUrl_revokes_prior_url: replacing blob URL revokes the old one', () => {
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    const store = useUIStore.getState()
    store.setOverlayImageUrl('blob:a')
    store.setOverlayImageUrl('blob:b')
    expect(revokeSpy).toHaveBeenCalledTimes(1)
    expect(revokeSpy).toHaveBeenCalledWith('blob:a')
    revokeSpy.mockRestore()
  })

  it('test_setOverlayImageUrl_to_null_revokes: setting null revokes the prior URL', () => {
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    const store = useUIStore.getState()
    store.setOverlayImageUrl('blob:a')
    store.setOverlayImageUrl(null)
    expect(revokeSpy).toHaveBeenCalledTimes(1)
    expect(revokeSpy).toHaveBeenCalledWith('blob:a')
    expect(useUIStore.getState().overlayImageUrl).toBeNull()
    revokeSpy.mockRestore()
  })

  it('test_terrain_layer_default_off: layerVisibility.terrain is false by default', () => {
    const state = useUIStore.getState()
    expect(state.layerVisibility.terrain).toBe(false)
  })

  it('test_toggleLayer_terrain_flips: toggleLayer terrain flips from false to true', () => {
    useUIStore.getState().toggleLayer('terrain')
    expect(useUIStore.getState().layerVisibility.terrain).toBe(true)
  })
})
