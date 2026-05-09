import { memo } from 'react'
import { Line } from 'react-konva'
import type { TerritoryRender } from '../../hooks/useCanvasArtifacts'

interface TerritoryPolygonProps {
  territory: TerritoryRender
  fill: string
  isSelected: boolean
  showBorders: boolean
  onClick: (id: string, shift: boolean) => void
  onMouseEnter?: (id: string) => void
  onMouseLeave?: () => void
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
  showBorders,
  onClick,
  onMouseEnter,
  onMouseLeave,
}: TerritoryPolygonProps) {
  return (
    <Line
      key={territory.id}
      points={territory.points}
      closed
      fill={fill}
      stroke={showBorders ? "rgba(0, 0, 0, 0.35)" : "transparent"}
      strokeWidth={showBorders ? (isSelected ? 2.5 : 1) : 0}
      onClick={(e) => onClick(territory.id, e.evt.shiftKey === true)}
      onMouseEnter={onMouseEnter ? () => onMouseEnter(territory.id) : undefined}
      onMouseLeave={onMouseLeave ? () => onMouseLeave() : undefined}
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
    prev.showBorders === next.showBorders &&
    prev.onClick === next.onClick &&
    prev.onMouseEnter === next.onMouseEnter &&
    prev.onMouseLeave === next.onMouseLeave
  )
}

export const TerritoryPolygon = memo(TerritoryPolygonBase, areEqual)
