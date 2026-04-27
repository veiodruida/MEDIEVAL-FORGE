import { create } from 'zustand'

// Quick-task 260420-hkr rename:
// - 'terrain' layer added in Phase 05 (plan 5.1); default visibility OFF.
// - 'baronies' added so the BaronyLayer can be toggled independently of borders.
// Downstream plans (2.2/2.3/5.2) depend on this shape; do not change without
// updating all consumers (CanvasViewer, LayerTogglePanel, uiStore.test).
export type LayerName = 'condados' | 'baronies' | 'borders' | 'capitals' | 'labels' | 'terrain'

interface UIState {
  selectedTerritoryId: string | null
  layerVisibility: Record<LayerName, boolean>
  // Phase 5: reference overlay (client-side ephemeral, D-04)
  overlayImageUrl: string | null
  overlayOpacity: number  // 0.0 – 1.0
  select: (id: string | null) => void
  toggleLayer: (name: LayerName) => void
  setOverlayImageUrl: (url: string | null) => void
  setOverlayOpacity: (opacity: number) => void
}

// Initial visibility: condados/borders/capitals on; baronies/labels/terrain off.
// baronies defaults to off so the denser barony polygons do not obscure the
// condado colors on first view — the user opts in via the "Baronias" toggle.
// terrain defaults to off — user opts in via terrain layer toggle (Phase 5).
const DEFAULT_LAYER_VISIBILITY: Record<LayerName, boolean> = {
  condados: true,
  baronies: false,
  borders: true,
  capitals: true,
  labels: false,
  terrain: false,
}

export const useUIStore = create<UIState>((set) => ({
  selectedTerritoryId: null,
  layerVisibility: { ...DEFAULT_LAYER_VISIBILITY },
  overlayImageUrl: null,
  overlayOpacity: 0.5,

  select: (id) => set({ selectedTerritoryId: id }),

  toggleLayer: (name) =>
    set((state) => ({
      layerVisibility: {
        ...state.layerVisibility,
        [name]: !state.layerVisibility[name],
      },
    })),

  setOverlayImageUrl: (url) =>
    set((state) => {
      if (state.overlayImageUrl && state.overlayImageUrl !== url) {
        URL.revokeObjectURL(state.overlayImageUrl)
      }
      return { overlayImageUrl: url }
    }),

  setOverlayOpacity: (opacity) => set({ overlayOpacity: Math.min(1, Math.max(0, opacity)) }),
}))
