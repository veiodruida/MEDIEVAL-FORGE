import { useCallback } from 'react'
import { Layer } from 'react-konva'
import { TerritoryPolygon } from './TerritoryPolygon'
import { useUIStore } from '../../stores/uiStore'
import type { TerritoryRender } from '../../hooks/useCanvasArtifacts'

const FALLBACK_FILL = '#666666'

interface TerritoryLayerProps {
  territories: TerritoryRender[]
  condadoColors: Record<string, string>
  visible: boolean
  showBorders: boolean
  onHoverEnter?: (id: string) => void
  onHoverLeave?: () => void
}

/**
 * Konva Layer rendering all condado polygons with fills from condado_colors.json sidecar.
 *
 * Phase 03 read-only contract:
 *   - Plain click       → uiStore.selectIds([id])
 *   - Shift+click       → toggle id in/out of uiStore.selectedTerritoryIds (D-17)
 *   - mouseover         → onHoverEnter(id) callback (D-15 hover tooltip)
 *   - mouseout          → onHoverLeave() callback
 *
 * Narrow Zustand selector (Pattern 3) — only the first selected id is read so
 * a multi-select set change does NOT re-render the entire layer; the gold
 * outline is painted on InteractionLayer instead.
 *
 * FALLBACK_FILL: '#666666' for any condado id not present in the colors map.
 */
export function TerritoryLayer({
  territories,
  condadoColors,
  visible,
  showBorders,
  onHoverEnter,
  onHoverLeave,
}: TerritoryLayerProps) {
  const selectedTerritoryId = useUIStore((s) => s.selectedTerritoryId)

  // Stable across shift-click mutations: handleClick has NO state deps.
  // Reading via getState() inside the body sees fresh values on each call but
  // keeps the callback reference === so React.memo on TerritoryPolygon does
  // not invalidate. Essential at 800 territories (<500ms target).
  const handleClick = useCallback((id: string, shift: boolean) => {
    const ui = useUIStore.getState()
    const current = ui.selectedTerritoryIds
    if (shift) {
      ui.selectIds(current.includes(id) ? current.filter((x) => x !== id) : [...current, id])
    } else {
      ui.selectIds([id])
    }
  }, []) // intentionally empty: all reads are via getState() above

  return (
    <Layer visible={visible}>
      {territories.map((t, i) => {
        const fill = condadoColors[t.id] ?? FALLBACK_FILL
        return (
          <TerritoryPolygon
            key={`${t.id}-${i}`}
            territory={t}
            fill={fill}
            isSelected={selectedTerritoryId === t.id}
            showBorders={showBorders}
            onClick={handleClick}
            onMouseEnter={onHoverEnter}
            onMouseLeave={onHoverLeave}
          />
        )
      })}
    </Layer>
  )
}
