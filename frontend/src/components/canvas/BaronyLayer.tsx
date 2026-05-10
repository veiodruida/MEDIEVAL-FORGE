import { Layer, Line } from 'react-konva'
import type { BaronyRender } from '../../hooks/useCanvasArtifacts'

interface Props {
  baronies: BaronyRender[]
  baronyColors: Record<string, string>
  visible: boolean
}

const FALLBACK_FILL = '#999999'

/**
 * D-02: baronies render at 85% opacity above condados when the Baronies toggle
 * is ON. Plan 03-01 emits baronies.geojson (no `fill` property) plus
 * barony_colors.json — the layer reads each barony's hex from the colors map by
 * id, mirroring how TerritoryLayer resolves condado fills via condadoColors.
 *
 * listening=false on the Layer — selection uses condados only (D-03 scope).
 */
export function BaronyLayer({ baronies, baronyColors, visible }: Props) {
  return (
    <Layer listening={false} visible={visible} opacity={0.85}>
      {baronies.map((b) => (
        <Line
          key={b.id}
          points={b.points}
          closed
          fill={baronyColors[b.id] ?? b.fill ?? FALLBACK_FILL}
          stroke="rgba(0, 0, 0, 0.45)"
          strokeWidth={0.5}
          listening={false}
        />
      ))}
    </Layer>
  )
}
