/**
 * CanvasViewer — top-level Konva canvas component for Plan 2.1.
 *
 * Renders: Stage + BackgroundLayer (terrain.png) only.
 * TerritoryLayer / BaronyLayer / DecorationsLayer / InteractionLayer are added
 * in plans 2.2 and 2.3 as seams above BackgroundLayer.
 *
 * Pitfall 1 (RESEARCH): Stage must not be rendered server-side; Konva is DOM-only.
 * Pitfall 6 (RESEARCH): territory data is injected via useCanvasArtifacts — no
 *   direct import of territory_data_v3.
 */
import { Stage } from 'react-konva'
import { BackgroundLayer } from './BackgroundLayer'
import { ProjectionProvider } from '../../context/ProjectionContext'
import { buildProjectionConfig } from '../../lib/projection'
import { useCanvasArtifacts } from '../../hooks/useCanvasArtifacts'

interface CanvasViewerProps {
  projectId: string
  /** Pixel width of the canvas container */
  width?: number
  /** Pixel height of the canvas container */
  height?: number
}

export function CanvasViewer({ projectId, width = 800, height = 600 }: CanvasViewerProps) {
  // Fetch metadata first with projection=null so we can build the projection config.
  // Then pass the projection to artifact queries (territories + baronies enabled only
  // after projection is available).
  const artifactsWithoutProjection = useCanvasArtifacts(projectId, null)
  const [, , , , metaQ] = artifactsWithoutProjection

  if (metaQ.isPending) {
    return <div style={{ padding: 24 }}>Loading map…</div>
  }

  if (metaQ.error) {
    const msg = (metaQ.error as Error).message
    if (msg === 'MAP_NOT_GENERATED') {
      return (
        <div style={{ padding: 24 }}>
          No map generated yet. Run the pipeline first.
        </div>
      )
    }
    return (
      <div style={{ padding: 24 }}>
        Failed to load territory data. Check the server is running.
      </div>
    )
  }

  if (!metaQ.data) return null

  const meta = metaQ.data
  const [mapW, mapH] = meta.map_size
  const bounds = meta.bounds
  const projection = buildProjectionConfig(
    { lonMin: bounds.lon_min, lonMax: bounds.lon_max, latMin: bounds.lat_min, latMax: bounds.lat_max },
    mapW,
    mapH,
  )

  // Scale the stage to fit the container while preserving aspect ratio
  const scaleX = width / mapW
  const scaleY = height / mapH
  const scale = Math.min(scaleX, scaleY)
  const stageW = mapW * scale
  const stageH = mapH * scale

  const terrainSrc = `/api/projects/${projectId}/preview/terrain.png`

  return (
    <ProjectionProvider value={projection}>
      <Stage width={stageW} height={stageH} scaleX={scale} scaleY={scale}>
        <BackgroundLayer src={terrainSrc} mapW={mapW} mapH={mapH} />
        {/* TerritoryLayer — plan 2.2 seam */}
        {/* BaronyLayer — plan 2.2 seam */}
        {/* DecorationsLayer — plan 2.3 seam */}
        {/* InteractionLayer — plan 2.3 seam */}
      </Stage>
    </ProjectionProvider>
  )
}
