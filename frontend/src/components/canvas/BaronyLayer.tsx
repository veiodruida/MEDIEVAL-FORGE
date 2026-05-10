import { Layer, Line, Text } from 'react-konva'
import type Konva from 'konva'
import type { BaronyRender } from '../../hooks/useCanvasArtifacts'
import { useUIStore } from '../../stores/uiStore'

interface Props {
  baronies: BaronyRender[]
  baronyColors: Record<string, string>
  visible: boolean
}

const FALLBACK_FILL = '#999999'
const LABEL_MAX_CHARS = 12
const LABEL_FONT_SIZE = 10

/**
 * Compute the polygon centroid as the arithmetic mean of all (x, y) point pairs.
 * Konva expects flat number[] in [x0, y0, x1, y1, ...] order. This is the simple
 * vertex-average centroid (NOT the area-weighted centroid). Acceptable here because
 * baronies are roughly convex and the average gives a pixel near the visual center;
 * D-12 readability requirement does not specify area-weighted accuracy.
 */
function vertexCentroid(points: number[]): { x: number; y: number } {
  if (points.length === 0) return { x: 0, y: 0 }
  let sx = 0, sy = 0
  const n = points.length / 2
  for (let i = 0; i < points.length; i += 2) {
    sx += points[i]
    sy += points[i + 1]
  }
  return { x: sx / n, y: sy / n }
}

function truncate(name: string): string {
  if (name.length <= LABEL_MAX_CHARS) return name
  return name.slice(0, LABEL_MAX_CHARS - 1) + '…'
}

/**
 * Phase 03 Plan 03-08 follow-up: when the Baronies toggle is ON, baronies
 * become click-targets that drive `useUIStore.selectBarony`. The layer reads
 * each barony's hex from `barony_colors.json` (Plan 03-01 sidecar — geojson
 * itself does NOT carry a `fill` property), matching how TerritoryLayer
 * resolves condado fills via condadoColors.
 *
 * Listening is gated on `visible` so when the Baronies toggle is OFF clicks
 * fall through to the condado polygons in TerritoryLayer (Phase 03 default).
 *
 * Phase 04 D-12 addition: each barony renders a Konva Text label at its centroid
 * when `visible` is true. Labels are listening={false} (decorative — do NOT intercept
 * clicks).
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
      {visible && baronies.map((b) => {
        const { x, y } = vertexCentroid(b.points)
        const text = truncate(b.name)
        // Approximate centering: offsetX = textWidth/2 (rough estimate at 10px font:
        // ~6px per char). Konva can compute precise width post-mount via ref, but
        // for UI-SPEC compliance the rough estimate is sufficient — the halo +
        // small font keep the label readable even if off-center by 1-2px.
        const approxTextWidth = text.length * 6
        return (
          <Text
            key={`label-${b.id}`}
            data-testid={`barony-label-${b.id}`}
            x={x}
            y={y}
            text={text}
            fontSize={LABEL_FONT_SIZE}
            fill="#FFFFFF"
            fontStyle="normal"
            offsetX={approxTextWidth / 2}
            offsetY={LABEL_FONT_SIZE / 2}
            shadowColor="black"
            shadowBlur={1}
            shadowOffset={{ x: 0, y: 0 }}
            shadowOpacity={1}
            listening={false}
          />
        )
      })}
    </Layer>
  )
}
