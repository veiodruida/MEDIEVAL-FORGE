import { Layer, Line } from 'react-konva'
import type { BaronyRender } from '../../hooks/useCanvasArtifacts'

interface Props {
  baronies: BaronyRender[]
  visible: boolean
}

/**
 * D-02: baronies render at 85% opacity above condados when the Borders toggle is ON.
 * Plan 2.1 Task 1 emits baronies.geojson (via read-back from lookup_barony.png +
 * the backend-resolved per-barony hex colors inside the feature properties +
 * territory_metadata.json). Each BaronyRender already carries its `fill` (hex) and
 * projected `points`, so this layer is a pure renderer.
 *
 * listening=false on the Layer — selection uses condados only (D-03 scope).
 */
export function BaronyLayer({ baronies, visible }: Props) {
  return (
    <Layer listening={false} visible={visible} opacity={0.85}>
      {baronies.map((b) => (
        <Line
          key={b.id}
          points={b.points}
          closed
          fill={b.fill}
          stroke="rgba(0, 0, 0, 0.25)"
          strokeWidth={0.5}
          listening={false}
        />
      ))}
    </Layer>
  )
}
