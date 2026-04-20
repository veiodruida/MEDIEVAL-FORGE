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
  const select = useUIStore((s) => s.select)

  const handleClick = useCallback(
    (id: string) => select(id),
    [select],
  )

  return (
    <Layer visible={visible}>
      {territories.map((t) => (
        <TerritoryPolygon
          key={t.id}
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
