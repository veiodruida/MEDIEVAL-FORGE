import { useEffect, useRef } from 'react'
import { Layer, Circle, Text } from 'react-konva'
import type Konva from 'konva'
import { useProjection } from '../../context/ProjectionContext'
import { geoToCanvas, canvasToGeo } from '../../lib/projection'
import type { TerritoryMetadataCondado } from '../../hooks/useCanvasArtifacts'

/**
 * Label gate: labels render only when the stage is zoomed in to at least
 * 1.5× the fit-to-view scale. UAT feedback (GAP-08) showed 2.0× was too high —
 * users perceived the Labels toggle as broken at default zoom. Compromise
 * value per 02-HUMAN-UAT.md fix_hint. Paired Radix Tooltip on the Labels
 * checkbox in LayerTogglePanel explains the threshold to the user.
 */
export const LABEL_ZOOM_THRESHOLD_RELATIVE = 1.5

interface Props {
  condados: TerritoryMetadataCondado[]
  condadoColors: Record<string, string>
  layerVisibility: { capitals: boolean; labels: boolean }
  currentScale: number
  minScale: number
  // Phase 4 — edit mode props:
  isEditMode: boolean
  onCapitalDragEnd?: (condadoId: string, lon: number, lat: number) => void | Promise<void>
}

/**
 * Post-mount label-centering: measure the real rendered text width via Konva's
 * getTextWidth() once the node is mounted, then set offsetX = width/2. The
 * character-count heuristic from prior drafts centers incorrectly for most
 * proportional-font strings (short capitals → over-offset; wide letters like W/M
 * → under-offset). Using the real measured width keeps labels pixel-centered.
 */
function CenteredLabel(props: { x: number; y: number; text: string }) {
  const ref = useRef<Konva.Text | null>(null)
  useEffect(() => {
    const n = ref.current
    if (!n) return
    const width =
      typeof (n as unknown as { getTextWidth?: () => number }).getTextWidth === 'function'
        ? (n as unknown as { getTextWidth: () => number }).getTextWidth()
        : n.width()
    n.offsetX(width / 2)
    n.getLayer()?.batchDraw()
  }, [props.text])

  return (
    <Text
      ref={ref as never}
      x={props.x}
      y={props.y}
      text={props.text}
      fontFamily="system-ui, sans-serif"
      fontSize={12}
      fill="#1a1a1a"
      stroke="rgba(255,255,255,0.7)"
      strokeWidth={1}
      listening={false}
      offsetY={14}
    />
  )
}

/**
 * DecorationsLayer renders capital dots (D-04 dual-ring) + territory labels.
 *
 * Phase 4 changes (Plan 05):
 *   - Accepts `isEditMode` prop; Layer listening={isEditMode} (Pitfall 8 fix).
 *     When isEditMode=false, Layer is purely visual (Phase 2 behavior preserved).
 *   - Capital inner Circle is draggable={isEditMode}; onDragEnd fires onCapitalDragEnd
 *     with geo coordinates converted via canvasToGeo.
 *   - Dark outer ring remains non-draggable (decorative only).
 *
 * D-04 dual-ring capital (UI-SPEC §Color §capital):
 *   OUTER (dark ring): Circle radius=6.75 fill=rgba(0,0,0,0.6)
 *   INNER (colored):   Circle radius=6 fill=condadoColor stroke=#ffffff strokeWidth=1.5
 *
 * NO canvas shadow — the dark ring is a real geometric circle, never a blur filter.
 */
export function DecorationsLayer({
  condados,
  condadoColors,
  layerVisibility,
  currentScale,
  minScale,
  isEditMode,
  onCapitalDragEnd,
}: Props) {
  const projection = useProjection()
  const showLabels =
    layerVisibility.labels &&
    currentScale >= LABEL_ZOOM_THRESHOLD_RELATIVE * minScale

  return (
    // Pitfall 8 fix: Layer must be listening when in edit mode so drag events fire.
    // When isEditMode=false the Layer is purely visual — all click/drag events
    // pass through to TerritoryLayer (Phase 2 read-only behavior preserved).
    <Layer listening={isEditMode}>
      {layerVisibility.capitals &&
        condados.flatMap((c) => {
          const [x, y] = geoToCanvas(c.lon, c.lat, projection)
          const color = condadoColors[c.id] ?? '#666666'
          return [
            // Dark outer ring — decorative, never draggable
            <Circle
              key={`cap-dark-${c.id}`}
              data-role="capital-dark-ring"
              x={x}
              y={y}
              radius={6.75}
              fill="rgba(0, 0, 0, 0.6)"
            />,
            // Inner colored circle — draggable in edit mode (Research §Pattern 3)
            // Per Pitfall 5: do NOT setState in onDragMove. Only react on onDragEnd.
            <Circle
              key={`cap-${c.id}`}
              data-role="capital"
              x={x}
              y={y}
              radius={6}
              fill={color}
              stroke="#ffffff"
              strokeWidth={1.5}
              draggable={isEditMode}
              onDragEnd={(e) => {
                if (!onCapitalDragEnd) return
                const node = e.target
                const canvasX = node.x()
                const canvasY = node.y()
                const [lon, lat] = canvasToGeo(canvasX, canvasY, projection)
                void onCapitalDragEnd(c.id, lon, lat)
              }}
            />,
          ]
        })}
      {showLabels &&
        condados.map((c) => {
          const [x, y] = geoToCanvas(c.lon, c.lat, projection)
          return <CenteredLabel key={`lbl-${c.id}`} x={x} y={y} text={c.name} />
        })}
    </Layer>
  )
}
