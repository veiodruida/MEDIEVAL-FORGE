import { Layer, Line } from 'react-konva'
import type Konva from 'konva'
import type { BaronyRender } from '../../hooks/useCanvasArtifacts'
import { useUIStore } from '../../stores/uiStore'

interface Props {
  baronies: BaronyRender[]
  baronyColors: Record<string, string>
  visible: boolean
}

const FALLBACK_FILL = '#999999'

/**
 * Phase 03 Plan 03-08 follow-up: when the Baronies toggle is ON, baronies
 * become click-targets that drive `useUIStore.selectBarony`. The layer reads
 * each barony's hex from `barony_colors.json` (Plan 03-01 sidecar — geojson
 * itself does NOT carry a `fill` property), matching how TerritoryLayer
 * resolves condado fills via condadoColors.
 *
 * Listening is gated on `visible` so when the Baronies toggle is OFF clicks
 * fall through to the condado polygons in TerritoryLayer (Phase 03 default).
 */
export function BaronyLayer({ baronies, baronyColors, visible }: Props) {
  const selectedBaronyId = useUIStore((s) => s.selectedBaronyId)
  const selectBarony = useUIStore((s) => s.selectBarony)

  const handleClick = (id: string) =>
    (e: Konva.KonvaEventObject<MouseEvent | TouchEvent>) => {
      // Stop the bubble so the Stage's empty-click handler does not fire.
      e.cancelBubble = true
      selectBarony(id)
    }

  return (
    <Layer listening={visible} visible={visible} opacity={0.85}>
      {baronies.map((b) => {
        const isSelected = b.id === selectedBaronyId
        return (
          <Line
            key={b.id}
            points={b.points}
            closed
            fill={baronyColors[b.id] ?? b.fill ?? FALLBACK_FILL}
            stroke={isSelected ? '#facc15' : 'rgba(0, 0, 0, 0.45)'}
            strokeWidth={isSelected ? 2 : 0.5}
            listening={visible}
            onClick={handleClick(b.id)}
            onTap={handleClick(b.id)}
          />
        )
      })}
    </Layer>
  )
}
