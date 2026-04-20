import { create } from 'zustand'

// Quick-task 260420-hkr rename:
// - 'terrain' layer belongs to Phase 05 (not yet implemented); removed here.
// - 'baronies' added so the BaronyLayer can be toggled independently of borders.
// Downstream plans (2.2/2.3) depend on this shape; do not change without
// updating all consumers (CanvasViewer, LayerTogglePanel, uiStore.test).
export type LayerName = 'condados' | 'baronies' | 'borders' | 'capitals' | 'labels'

interface UIState {
  selectedTerritoryId: string | null
  layerVisibility: Record<LayerName, boolean>
  select: (id: string | null) => void
  toggleLayer: (name: LayerName) => void
}

// Initial visibility: condados/borders/capitals on; baronies/labels off.
// baronies defaults to off so the denser barony polygons do not obscure the
// condado colors on first view — the user opts in via the "Baronias" toggle.
const DEFAULT_LAYER_VISIBILITY: Record<LayerName, boolean> = {
  condados: true,
  baronies: false,
  borders: true,
  capitals: true,
  labels: false,
}

export const useUIStore = create<UIState>((set) => ({
  selectedTerritoryId: null,
  layerVisibility: { ...DEFAULT_LAYER_VISIBILITY },

  select: (id) => set({ selectedTerritoryId: id }),

  toggleLayer: (name) =>
    set((state) => ({
      layerVisibility: {
        ...state.layerVisibility,
        [name]: !state.layerVisibility[name],
      },
    })),
}))
