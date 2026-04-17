import { memo } from 'react'
import { Line } from 'react-konva'
import type { TerritoryRender } from '../../hooks/useCanvasArtifacts'

interface TerritoryPolygonProps {
  territory: TerritoryRender
  fill: string
  isSelected: boolean
  onClick: (id: string) => void
}

/**
 * Memoized condado polygon. areEqual ensures sibling polygons are NOT
 * re-rendered when selection changes in a different polygon (D-03/D-04 perf guard).
 *
 * Stroke: rgba(0, 0, 0, 0.35), 1px — UI-SPEC §Canvas Color System default border.
 * Selection highlight: strokeWidth 2.5, gold outline — plan 2.3 adds InteractionLayer
 * on top; here we just keep the data-attribute for testability.
 */
function TerritoryPolygonBase({
  territory,
  fill,
  isSelected,
  onClick,
}: TerritoryPolygonProps) {
  return (
    <Line
      key={territory.id}
      points={territory.points}
      closed
      fill={fill}
      stroke="rgba(0, 0, 0, 0.35)"
      strokeWidth={isSelected ? 2.5 : 1}
      onClick={() => onClick(territory.id)}
      listening
    />
  )
}

function areEqual(
  prev: TerritoryPolygonProps,
  next: TerritoryPolygonProps,
): boolean {
  return (
    prev.territory.id === next.territory.id &&
    prev.territory.points === next.territory.points &&
    prev.fill === next.fill &&
    prev.isSelected === next.isSelected &&
    prev.onClick === next.onClick
  )
}

export const TerritoryPolygon = memo(TerritoryPolygonBase, areEqual)
