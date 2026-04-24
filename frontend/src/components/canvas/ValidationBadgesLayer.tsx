import { Layer, Circle } from 'react-konva'
import { useValidationStore } from '../../stores/useValidationStore'
import { geoToCanvas } from '../../lib/projection'
import { useProjection } from '../../context/ProjectionContext'
import type { TerritoryMetadataCondado } from '../../hooks/useCanvasArtifacts'

/**
 * ValidationBadgesLayer (D-06) — Konva Layer rendering per-condado validation badges.
 *
 * Renders an 8px circle at each condado's centroid for each issue:
 *   - severity=error   → #e5484d (Radix red-9)
 *   - severity=warning → #f76b15 (Radix orange-9)
 *
 * Uses useProjection() — safe here because this component is rendered as a child
 * inside <Stage> which is inside <ProjectionProvider> in CanvasViewer.
 *
 * Offset: +12px on Y so badge doesn't overlap the capital dual-ring icon center.
 */
export function ValidationBadgesLayer({
  condados,
}: {
  condados: TerritoryMetadataCondado[]
}) {
  const issues = useValidationStore((s) => s.issues)
  const projection = useProjection()

  if (issues.length === 0) return null

  const byId = new Map(condados.map((c) => [c.id, c]))

  return (
    <Layer listening={false}>
      {issues.map((issue, idx) => {
        const c = byId.get(issue.condado_id)
        if (!c) return null
        const [x, y] = geoToCanvas(c.lon, c.lat, projection)
        const fill = issue.severity === 'error' ? '#e5484d' : '#f76b15'
        return (
          <Circle
            key={`${issue.condado_id}-${idx}`}
            x={x}
            y={y + 12}
            radius={8}
            fill={fill}
          />
        )
      })}
    </Layer>
  )
}
