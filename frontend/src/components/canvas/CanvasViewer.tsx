import { useState, useEffect } from 'react'
import { Stage } from 'react-konva'
import { BackgroundLayer } from './BackgroundLayer'
import { TerritoryLayer } from './TerritoryLayer'
import { BaronyLayer } from './BaronyLayer'
import { LayerTogglePanel } from './LayerTogglePanel'
import { ProjectionProvider } from '../../context/ProjectionContext'
import { buildProjectionConfig, type ProjectionConfig } from '../../lib/projection'
import { useCanvasArtifacts } from '../../hooks/useCanvasArtifacts'
import { useUIStore } from '../../stores/uiStore'

interface CanvasViewerProps {
  projectId: string
  width?: number
  height?: number
}

export function CanvasViewer({ projectId, width = 800, height = 600 }: CanvasViewerProps) {
  const [projection, setProjection] = useState<ProjectionConfig | null>(null)
  const layerVisibility = useUIStore((s) => s.layerVisibility)

  const [territoriesQ, baroniesQ, condadoColorsQ, , metaQ] = useCanvasArtifacts(projectId, projection)

  useEffect(() => {
    if (metaQ.data && !projection) {
      const [mapW, mapH] = metaQ.data.map_size
      const { bounds } = metaQ.data
      setProjection(
        buildProjectionConfig(
          { lonMin: bounds.lon_min, lonMax: bounds.lon_max, latMin: bounds.lat_min, latMax: bounds.lat_max },
          mapW,
          mapH,
        ),
      )
    }
  }, [metaQ.data, projection])

  if (metaQ.isPending) {
    return <div style={{ padding: 24 }}>Loading map…</div>
  }

  if (metaQ.error) {
    const msg = (metaQ.error as Error).message
    if (msg === 'MAP_NOT_GENERATED') {
      return <div style={{ padding: 24 }}>No map generated yet. Run the pipeline first.</div>
    }
    return <div style={{ padding: 24 }}>Failed to load territory data. Check the server is running.</div>
  }

  if (!metaQ.data || !projection || !territoriesQ.data || !condadoColorsQ.data || !baroniesQ.data) {
    return <div style={{ padding: 24 }}>Loading map…</div>
  }

  const [mapW, mapH] = metaQ.data.map_size
  const scaleX = width / mapW
  const scaleY = height / mapH
  const scale = Math.min(scaleX, scaleY)
  const stageW = mapW * scale
  const stageH = mapH * scale
  const terrainSrc = `/api/projects/${projectId}/preview/terrain.png`

  return (
    <ProjectionProvider value={projection}>
      <div style={{ position: 'relative', width: stageW, height: stageH }}>
        <Stage width={stageW} height={stageH} scaleX={scale} scaleY={scale}>
          <BackgroundLayer src={terrainSrc} mapW={mapW} mapH={mapH} visible={layerVisibility.terrain} />
          <TerritoryLayer
            territories={territoriesQ.data}
            condadoColors={condadoColorsQ.data}
            visible={layerVisibility.territories}
          />
          <BaronyLayer baronies={baroniesQ.data} visible={layerVisibility.borders} />
          {/* DecorationsLayer — plan 2.3 seam */}
          {/* InteractionLayer — plan 2.3 seam */}
        </Stage>
        <LayerTogglePanel />
      </div>
    </ProjectionProvider>
  )
}
