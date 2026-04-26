import { useCallback } from 'react'
import { Layer } from 'react-konva'
import { TerritoryPolygon } from './TerritoryPolygon'
import { useUIStore } from '../../stores/uiStore'
import { useEditorStore } from '../../stores/useEditorStore'
import type { TerritoryRender } from '../../hooks/useCanvasArtifacts'

const FALLBACK_FILL = '#666666'

interface TerritoryLayerProps {
  territories: TerritoryRender[]
  condadoColors: Record<string, string>
  visible: boolean
  showBorders: boolean
}

/**
 * Konva Layer rendering all condado polygons with fills from condado_colors.json sidecar.
 *
 * Narrow Zustand selector (§Pattern 3) — only selectedTerritoryId is subscribed so
 * changing a different store slice does NOT re-render this layer.
 *
 * FALLBACK_FILL: '#666666' for any condado id not present in the colors map.
 */
export function TerritoryLayer({
  territories,
  condadoColors,
  visible,
  showBorders,
}: TerritoryLayerProps) {
  const selectedTerritoryId = useUIStore((s) => s.selectedTerritoryId)

  // Stable across shift-click mutations: handleClick has NO state deps.
  // Reading via getState() inside the body sees fresh values on each call but
  // keeps the callback reference === so React.memo on TerritoryPolygon does
  // not invalidate. Essential at 800 territories (checker MINOR 6, <500ms target).
  const handleClick = useCallback((id: string, shift: boolean) => {
    const editor = useEditorStore.getState()
    const ui = useUIStore.getState()

    // Shift-click only engages multi-select in edit mode (gap-closure 04-12).
    // Outside edit mode, fall through to plain single-select.
    if (shift && editor.editMode) {
      // Toggle membership in the existing rubber-band selection set.
      // SelectionFloatingToolbar renders Fundir when length >= 2.
      const current = editor.rubberBandSelectionIds
      const next = current.includes(id)
        ? current.filter((x) => x !== id)
        : [...current, id]
      editor.setRubberBandSelectionIds(next)
      return
    }

    // Plain click: clear any multi-select from a prior shift-click/rubber-band
    // and set a single selection.
    if (editor.rubberBandSelectionIds.length > 0) {
      editor.clearRubberBandSelection()
    }
    ui.select(id)
  }, [])  // intentionally empty: all reads are via getState() above

  return (
    <Layer visible={visible}>
      {territories.map((t, i) => (
        <TerritoryPolygon
          key={`${t.id}-${i}`}
          territory={t}
          fill={condadoColors[t.id] ?? FALLBACK_FILL}
          isSelected={selectedTerritoryId === t.id}
          showBorders={showBorders}
          onClick={handleClick}
        />
      ))}
    </Layer>
  )
}
