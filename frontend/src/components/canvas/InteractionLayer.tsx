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
 * - renders one closed Line per polygon for EACH selected territory id
 *   (D-17 multi-select: every id in uiStore.selectedTerritoryIds gets a gold outline)
 * - renders 0 children when selectedTerritoryIds is empty
 *
 * O(1) selection pattern (RESEARCH §Pattern 7): do not mutate TerritoryPolygon;
 * paint the selection on a dedicated layer so sibling polygons don't re-render
 * when selection changes.
 */
export function InteractionLayer({ territories }: Props) {
  const selectedIds = useUIStore((s) => s.selectedTerritoryIds)
  const idsSet = new Set(selectedIds)
  const selectedPolygons = idsSet.size > 0
    ? territories.filter((t) => idsSet.has(t.id))
    : []

  return (
    <Layer listening={false}>
      {selectedPolygons.map((t, i) => (
        <Line
          key={`${t.id}-${i}`}
          points={t.points}
          closed
          stroke="#f0c040"
          strokeWidth={3}
          listening={false}
        />
      ))}
    </Layer>
  )
}
