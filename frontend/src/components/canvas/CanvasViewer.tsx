import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Stage } from 'react-konva'
import type Konva from 'konva'
import { BackgroundLayer } from './BackgroundLayer'
import { TerritoryLayer } from './TerritoryLayer'
import { BaronyLayer } from './BaronyLayer'
import { LayerTogglePanel } from './LayerTogglePanel'
import { DecorationsLayer } from './DecorationsLayer'
import { InteractionLayer } from './InteractionLayer'
import { FitToViewButton } from './FitToViewButton'
import { ProjectionProvider } from '../../context/ProjectionContext'
import {
  buildProjectionConfig,
  computeFitToView,
  type ProjectionConfig,
} from '../../lib/projection'
import {
  makeDragBoundFunc,
  makeWheelHandler,
  panToGeoCenter,
  MAX_SCALE_MULTIPLIER,
} from '../../hooks/useZoomPan'
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts'
import { useCanvasArtifacts } from '../../hooks/useCanvasArtifacts'
import { useUIStore } from '../../stores/uiStore'

interface CanvasViewerProps {
  projectId: string
  width?: number
  height?: number
}

const PADDING_PCT = 0.05

/**
 * Read-only canvas viewer for Phase 2.
 *
 * Composition (5 Konva layers in z-order):
 *   BackgroundLayer  → terrain PNG (D-01)
 *   TerritoryLayer   → condado polygons (D-01/D-02)
 *   BaronyLayer      → barony polygons at 85% opacity (D-02)
 *   DecorationsLayer → capitals dual-ring + labels (D-04 + D-10/11, listening=false)
 *   InteractionLayer → gold selection outline (D-03, listening=false)
 * Sibling absolute-positioned overlays: LayerTogglePanel, FitToViewButton.
 *
 * Interaction behavior:
 *   - draggable Stage with pan-clamp (makeDragBoundFunc)
 *   - cursor-anchored wheel zoom clamped to [minScale, 4*minScale]
 *   - Fit-to-view: button click OR Ctrl/Cmd+0 resets to minScale
 *   - Selection-change effect calls panToGeoCenter → centers canvas on new
 *     selection (RESEARCH §Pitfall 5 + UI-SPEC §Neighbor Navigation)
 *   - Empty-Stage click deselects using e.target === e.target.getStage()
 *     — race-free under React StrictMode (RESEARCH §Pitfall 6)
 *
 * NOTE: Stage is NOT passed scaleX/scaleY props — scale is managed imperatively
 * via stage.scale() so wheel-zoom doesn't get reset on every React re-render.
 */
export function CanvasViewer({ projectId, width = 800, height = 600 }: CanvasViewerProps) {
  const stageRef = useRef<Konva.Stage | null>(null)
  const [projection, setProjection] = useState<ProjectionConfig | null>(null)
  const [minScale, setMinScale] = useState(1)
  const [currentScale, setCurrentScale] = useState(1)

  const layerVisibility = useUIStore((s) => s.layerVisibility)
  const selectedId = useUIStore((s) => s.selectedTerritoryId)
  const select = useUIStore((s) => s.select)

  const [territoriesQ, baroniesQ, condadoColorsQ, , metaQ] = useCanvasArtifacts(
    projectId,
    projection,
  )

  // Build projection once metadata loads
  useEffect(() => {
    if (metaQ.data && !projection) {
      const [mapW, mapH] = metaQ.data.map_size
      const { bounds } = metaQ.data
      setProjection(
        buildProjectionConfig(
          {
            lonMin: bounds.lon_min,
            lonMax: bounds.lon_max,
            latMin: bounds.lat_min,
            latMax: bounds.lat_max,
          },
          mapW,
          mapH,
        ),
      )
    }
  }, [metaQ.data, projection])

  // Fit-to-view callback (shared by auto-fit on mount, button click, Ctrl+0)
  const fitToView = useCallback(() => {
    const stage = stageRef.current
    if (!stage || !projection) return
    const { scale, x, y } = computeFitToView(
      projection.mapW,
      projection.mapH,
      stage.width(),
      stage.height(),
      PADDING_PCT,
    )
    stage.scale({ x: scale, y: scale })
    stage.position({ x, y })
    setMinScale(scale)
    setCurrentScale(scale)
    stage.batchDraw()
  }, [projection])

  // D-12: auto-fit once projection lands
  useEffect(() => {
    if (projection) fitToView()
  }, [projection, fitToView])

  // Ctrl/Cmd+0 + Esc shortcuts
  useKeyboardShortcuts(fitToView)

  // RESEARCH §Pitfall 5 + UI-SPEC §Neighbor Navigation: pan canvas to center the
  // newly selected territory. Runs for any selection change — initial click AND
  // neighbor-chip navigation — so the inspector-driven flow is handled uniformly.
  //
  // IMPORTANT: do NOT list currentScale in the dep array. It is read live from
  // stage.scaleX() inside the effect. If we depended on it, wheel zoom's
  // setCurrentScale would retrigger this effect and snap the viewport back to
  // the selected territory on every wheel tick.
  useEffect(() => {
    const stage = stageRef.current
    if (!stage || !projection || !selectedId || !metaQ.data) return
    const condado = metaQ.data.condados.find((c) => c.id === selectedId)
    if (!condado) return
    panToGeoCenter(
      stage,
      condado.lon,
      condado.lat,
      projection,
      stage.scaleX(),
      { mapW: projection.mapW, mapH: projection.mapH },
    )
    stage.batchDraw()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, projection, metaQ.data])

  // Wheel handler — keep currentScale state in sync for label gating
  const wheelHandler = useMemo(
    () =>
      projection
        ? makeWheelHandler(minScale, minScale * MAX_SCALE_MULTIPLIER, {
            mapW: projection.mapW,
            mapH: projection.mapH,
          })
        : undefined,
    [projection, minScale],
  )

  const dragBound = useMemo(
    () =>
      projection
        ? makeDragBoundFunc(
            { mapW: projection.mapW, mapH: projection.mapH },
            () => stageRef.current?.scaleX() ?? 1,
            () => stageRef.current,
          )
        : undefined,
    [projection],
  )

  const handleWheel = useCallback(
    (e: Konva.KonvaEventObject<WheelEvent>) => {
      if (wheelHandler) wheelHandler(e)
      const s = stageRef.current?.scaleX()
      if (typeof s === 'number') setCurrentScale(s)
    },
    [wheelHandler],
  )

  // RESEARCH §Pitfall 6: canonical empty-Stage click deselect. Use
  // e.target.getStage() — race-free under React StrictMode double-invocation.
  // Do NOT compare against stageRef.current; that pattern fails when the stage
  // is remounted between StrictMode passes.
  //
  // Konva 10.2.5 verified: drag-then-release does NOT fire click on the Stage
  // (DragAndDrop sets _mouseListenClick=false on drag start, which gates the
  // click event in Stage._pointerup), so an empty-Stage click only fires from
  // a real click with no intervening drag.
  const handleStageClick = useCallback(
    (e: Konva.KonvaEventObject<MouseEvent | TouchEvent>) => {
      if (e.target === e.target.getStage()) {
        select(null)
      }
    },
    [select],
  )

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

  if (
    !metaQ.data ||
    !projection ||
    !territoriesQ.data ||
    !condadoColorsQ.data ||
    !baroniesQ.data
  ) {
    return <div style={{ padding: 24 }}>Loading map…</div>
  }

  // Viewport sized to fill the parent (ProjectDetail canvas-region flex:1 Box).
  // width/height props provide fallback when mounted outside a flex container.
  const viewportW = width
  const viewportH = height
  const terrainSrc = `/api/projects/${projectId}/preview/terrain.png`

  return (
    <ProjectionProvider value={projection}>
      <div
        style={{
          position: 'relative',
          width: viewportW,
          height: viewportH,
          overflow: 'hidden',
        }}
      >
        <Stage
          ref={stageRef}
          width={viewportW}
          height={viewportH}
          draggable
          dragBoundFunc={dragBound}
          onWheel={handleWheel}
          onClick={handleStageClick}
          onTap={handleStageClick}
        >
          <BackgroundLayer
            src={terrainSrc}
            mapW={projection.mapW}
            mapH={projection.mapH}
            visible={layerVisibility.terrain}
          />
          <TerritoryLayer
            territories={territoriesQ.data}
            condadoColors={condadoColorsQ.data}
            visible={layerVisibility.territories}
          />
          <BaronyLayer baronies={baroniesQ.data} visible={layerVisibility.borders} />
          <DecorationsLayer
            condados={metaQ.data.condados}
            condadoColors={condadoColorsQ.data}
            layerVisibility={{
              capitals: layerVisibility.capitals,
              labels: layerVisibility.labels,
            }}
            currentScale={currentScale}
            minScale={minScale}
          />
          <InteractionLayer territories={territoriesQ.data} />
        </Stage>
        <LayerTogglePanel />
        <FitToViewButton onFit={fitToView} />
      </div>
    </ProjectionProvider>
  )
}
