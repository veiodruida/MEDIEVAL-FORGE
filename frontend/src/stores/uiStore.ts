import { create } from 'zustand'

// Layer names per D-09 spec. Downstream plans (2.2/2.3) add their own
// rendering logic; this slice shape must NOT be changed without updating all consumers.
export type LayerName = 'terrain' | 'territories' | 'borders' | 'capitals' | 'labels'

interface UIState {
  selectedTerritoryId: string | null
  layerVisibility: Record<LayerName, boolean>
  select: (id: string | null) => void
  toggleLayer: (name: LayerName) => void
}

// D-09 initial visibility: terrain=true, territories=true, borders=true,
// capitals=true, labels=false
const DEFAULT_LAYER_VISIBILITY: Record<LayerName, boolean> = {
  terrain: true,
  territories: true,
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
