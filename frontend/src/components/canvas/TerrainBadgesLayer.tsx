import { Layer, Text } from 'react-konva'
import { geoToCanvas } from '../../lib/projection'
import { useProjectStore } from '../../stores/useProjectStore'
import { TERRAIN_EMOJI } from '../../types/editing'
import type { ProjectionConfig } from '../../lib/projection'
import type { TerritoryMetadataCondado } from '../../hooks/useCanvasArtifacts'

interface Props {
  condados: TerritoryMetadataCondado[]
  projection: ProjectionConfig
}

/**
 * TerrainBadgesLayer — renders one emoji Konva Text per territory that has a
 * terrain_type assigned in useProjectStore.
 *
 * - Layer listening={false}: badges never need hit testing.
 * - Emoji at centroid coordinates projected via geoToCanvas.
 * - Territories without a terrain entry render NOTHING.
 * - Always rendered regardless of the 'terrain' layer visibility toggle
 *   (badges are informational overlays, not part of the color mode).
 */
export function TerrainBadgesLayer({ condados, projection }: Props) {
  const terrainTypes = useProjectStore((s) => s.terrain_types)

  return (
    <Layer listening={false}>
      {condados.map((c) => {
        const terrain = terrainTypes[c.id]
        if (!terrain) return null
        const [x, y] = geoToCanvas(c.lon, c.lat, projection)
        return (
          <Text
            key={`terrain-badge-${c.id}`}
            x={x}
            y={y}
            text={TERRAIN_EMOJI[terrain]}
            fontSize={14}
            listening={false}
            align="center"
            verticalAlign="middle"
            offsetX={7}
            offsetY={7}
          />
        )
      })}
    </Layer>
  )
}
