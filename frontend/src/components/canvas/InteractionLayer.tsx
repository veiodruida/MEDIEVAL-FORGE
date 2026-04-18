import { Layer, Line } from 'react-konva'
import { useUIStore } from '../../stores/uiStore'
import type { TerritoryRender } from '../../hooks/useCanvasArtifacts'

interface Props {
  territories: TerritoryRender[]
}

/**
 * InteractionLayer renders the gold selection outline on top of everything.
 * - listening=false: selection is purely visual; hit-testing stays on TerritoryLayer
 * - stroke #f0c040 (UI-SPEC gold), strokeWidth=3
 * - renders exactly one closed Line for the currently selected territory
 * - renders 0 children when selectedTerritoryId is null or unknown
 *
 * This is the O(1) selection pattern from RESEARCH §Pattern 7: do not mutate
 * TerritoryPolygon; paint the selection on a dedicated layer so sibling polygons
 * don't re-render when selection changes.
 */
export function InteractionLayer({ territories }: Props) {
  const selectedTerritoryId = useUIStore((s) => s.selectedTerritoryId)
  const selected = selectedTerritoryId
    ? territories.find((t) => t.id === selectedTerritoryId)
    : null

  return (
    <Layer listening={false}>
      {selected && (
        <Line
          points={selected.points}
          closed
          stroke="#f0c040"
          strokeWidth={3}
          listening={false}
        />
      )}
    </Layer>
  )
}
