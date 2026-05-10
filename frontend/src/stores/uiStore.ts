import { create } from 'zustand'

/**
 * Phase 03 (read-only canvas redesign) evolution:
 *
 * - selectedTerritoryId (single string|null) → selectedTerritoryIds (string[])
 *   to support D-17 shift+click multi-select. Legacy `select(id|null)` is kept
 *   as a thin convenience that writes [id] or []. Consumers migrate via the
 *   exported `selectSelectedTerritoryId` selector (returns ids[0] ?? null).
 *
 * - LayerName: 'terrain' removed. Terrain rendering is deferred to Phase 06
 *   (DEM/HydroSHEDS wire-up); the read-only canvas does not toggle a terrain
 *   layer in v3 Phase 03. Other consumers of 'terrain' were scrubbed by
 *   Plans 05/06.
 *
 * - overlayImageUrl + overlayOpacity removed. Reference-image overlay was a v1
 *   Phase 5 feature; not in the v3 Phase 03 read-only contract. Plan 05 deletes
 *   any remaining consumers.
 */
export type LayerName = 'condados' | 'baronies' | 'borders' | 'capitals' | 'labels'

interface UIState {
  selectedTerritoryIds: string[]
  // Mirror of selectedTerritoryIds[0] ?? null. Kept as a real state field (not a
  // getter) so existing Zustand subscribers like CanvasViewer's
  // `useUIStore((s) => s.selectedTerritoryId)` keep working without modification.
  // Plan 05 migrates consumers to `selectSelectedTerritoryId` and drops this mirror.
  selectedTerritoryId: string | null
  // Plan 03-08 follow-up: barony-level selection. Mutually exclusive with
  // `selectedTerritoryIds` — calling `selectBarony` clears the condado
  // selection, and any condado select clears the barony. Phase 04 will lift
  // both to a richer selection model with vertex-edit affordances.
  selectedBaronyId: string | null
  layerVisibility: Record<LayerName, boolean>
  selectIds: (ids: string[]) => void
  // Legacy convenience: writes [id] or []. Equivalent to selectIds(id ? [id] : []).
  // Prefer `selectIds` in new code.
  select: (id: string | null) => void
  selectBarony: (id: string | null) => void
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
  selectedTerritoryIds: [],
  selectedTerritoryId: null,
  selectedBaronyId: null,
  layerVisibility: { ...DEFAULT_LAYER_VISIBILITY },

  selectIds: (ids) =>
    set({
      selectedTerritoryIds: ids,
      selectedTerritoryId: ids[0] ?? null,
      // Selecting any condado(s) clears any barony selection — single-tier
      // selection at a time keeps the inspector dispatcher unambiguous.
      selectedBaronyId: ids.length > 0 ? null : null,
    }),

  select: (id) =>
    set({
      selectedTerritoryIds: id ? [id] : [],
      selectedTerritoryId: id,
      selectedBaronyId: null,
    }),

  selectBarony: (id) =>
    set({
      selectedBaronyId: id,
      // Mutually exclusive with condado selection.
      selectedTerritoryIds: [],
      selectedTerritoryId: null,
    }),

  toggleLayer: (name) =>
    set((state) => ({
      layerVisibility: {
        ...state.layerVisibility,
        [name]: !state.layerVisibility[name],
      },
    })),
}))

/**
 * Selector returning the first selected territory id, or null.
 * Use this in place of the removed `selectedTerritoryId` field:
 *   const id = useUIStore(selectSelectedTerritoryId)
 */
export const selectSelectedTerritoryId = (s: UIState): string | null =>
  s.selectedTerritoryIds[0] ?? null
