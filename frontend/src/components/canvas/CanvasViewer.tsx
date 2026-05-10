import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Stage } from 'react-konva'
import type Konva from 'konva'
import { BackgroundLayer } from './BackgroundLayer'
import { TerritoryLayer } from './TerritoryLayer'
import { BaronyLayer } from './BaronyLayer'
import { LayerTogglePanel } from './LayerTogglePanel'
import { LegendCard } from './LegendCard'
import { DecorationsLayer } from './DecorationsLayer'
import { InteractionLayer } from './InteractionLayer'
import { FitToViewButton } from './FitToViewButton'
import { HoverTooltip } from './HoverTooltip'
import { InspectorSidebar } from './InspectorSidebar'
import { ProjectionProvider } from '../../context/ProjectionContext'
import type { Project } from '../../api/client'
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
  // Cache-bust param: pass project.updated_at here so that when the pipeline
  // regenerates artifacts, both the TanStack queryKey AND the fetched URLs
  // change — forcing both the in-memory cache and the browser HTTP cache to
  // miss.
  cacheVersion?: string
  // When set, the right-docked InspectorSidebar (320px) renders alongside
  // the canvas. UI-SPEC §Layout Contract requires the sidebar in the
  // workspace shell; legacy unit tests that mount CanvasViewer in
  // isolation omit this prop and render canvas-only.
  project?: Project
}

const PADDING_PCT = 0.05

/**
 * Read-only canvas viewer for Phase 03 (read-only canvas redesign).
 *
 * Composition (5 Konva layers in z-order):
 *   BackgroundLayer  → terrain PNG
 *   TerritoryLayer   → condado polygons
 *   BaronyLayer      → barony polygons
 *   DecorationsLayer → capitals dual-ring + labels (listening=false)
 *   InteractionLayer → gold selection outline (listening=false)
 * Sibling absolute-positioned overlays: LayerTogglePanel, FitToViewButton, HoverTooltip.
 *
 * Interaction behavior (Phase 03 read-only):
 *   - draggable Stage with pan-clamp (makeDragBoundFunc)
 *   - cursor-anchored wheel zoom clamped to [minScale, 4*minScale]
 *   - Fit-to-view: button click OR Ctrl/Cmd+0 resets to minScale
 *   - Selection-change effect calls panToGeoCenter → centers canvas on new
 *     selection (D-15 single-select pan)
 *   - Empty-Stage click clears selection (D-16) using
 *     `e.target === e.target.getStage()` — race-free under React StrictMode
 *   - Plain click → selectIds([id]); shift+click toggles in/out (D-17)
 *   - mouseover condado → HoverTooltip overlay with name (D-15)
 *
 * GAP-05 fix carried verbatim from v1 Phase 2: Stage dimensions track the
 * parent container via a callback-ref ResizeObserver pattern. The callback-ref
 * (dis)connects the observer on every DOM mount/unmount so the observer always
 * targets the LIVE div across loading/content branch swaps.
 *
 * NOTE: Stage is NOT passed scaleX/scaleY props — scale is managed imperatively
 * via stage.scale() so wheel-zoom doesn't get reset on every React re-render.
 */
export function CanvasViewer({ projectId, width = 800, height = 600, cacheVersion, project }: CanvasViewerProps) {
  const stageRef = useRef<Konva.Stage | null>(null)

  // --- B-1 callback-ref ResizeObserver (verbatim from Pitfall 4) ----------
  const [viewportW, setViewportW] = useState<number>(width)
  const [viewportH, setViewportH] = useState<number>(height)

  const roRef = useRef<ResizeObserver | null>(null)
  const setContainerRef = useCallback((el: HTMLDivElement | null) => {
    if (roRef.current) {
      roRef.current.disconnect()
      roRef.current = null
    }
    if (el && typeof ResizeObserver !== 'undefined') {
      const ro = new ResizeObserver((entries) => {
        for (const entry of entries) {
          const cr = entry.contentRect
          if (cr.width > 0 && cr.height > 0) {
            setViewportW(Math.floor(cr.width))
            setViewportH(Math.floor(cr.height))
          }
        }
      })
      ro.observe(el)
      roRef.current = ro
      // Belt-and-suspenders sync read for browsers that don't deliver an
      // initial ResizeObserver entry.
      const rect = el.getBoundingClientRect()
      if (rect.width > 0 && rect.height > 0) {
        setViewportW(Math.floor(rect.width))
        setViewportH(Math.floor(rect.height))
      }
    }
  }, [])

  // Unmount safety: tear down observer if parent subtree unmounts before
  // setContainerRef(null) is invoked (e.g. react-router fast navigation).
  useEffect(() => {
    return () => {
      roRef.current?.disconnect()
      roRef.current = null
    }
  }, [])
  // -------------------------------------------------------------------------

  const [projection, setProjection] = useState<ProjectionConfig | null>(null)
  const [minScale, setMinScale] = useState(1)
  const [currentScale, setCurrentScale] = useState(1)

  const layerVisibility = useUIStore((s) => s.layerVisibility)
  const selectedId = useUIStore((s) => s.selectedTerritoryId)

  // Hover tooltip state (D-15). Local React state — UI-ephemeral, no store needed.
  const [hover, setHover] = useState<{ name: string | null; x: number; y: number }>({
    name: null,
    x: 0,
    y: 0,
  })

  const [territoriesQ, baroniesQ, condadoColorsQ, baronyColorsQ, metaQ] = useCanvasArtifacts(
    projectId,
    projection,
    cacheVersion,
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

  // Fit-to-view callback (shared by auto-fit on mount, button click, Ctrl+0).
  const fitToView = useCallback(() => {
    const stage = stageRef.current
    if (!projection) return
    const { scale, x, y } = computeFitToView(
      projection.mapW,
      projection.mapH,
      viewportW,
      viewportH,
      PADDING_PCT,
    )
    if (stage) {
      stage.scale({ x: scale, y: scale })
      stage.position({ x, y })
      stage.batchDraw()
    }
    setMinScale(scale)
    setCurrentScale(scale)
  }, [projection, viewportW, viewportH])

  // Auto-fit once projection lands AND whenever Stage dimensions change.
  useEffect(() => {
    if (projection) fitToView()
  }, [projection, fitToView, viewportW, viewportH])

  // Ctrl/Cmd+0 fit-to-view shortcut
  useKeyboardShortcuts(fitToView)

  // Pan canvas to center the newly selected territory (D-15 single-select pan).
  // Read scale live from stage.scaleX() — DO NOT add currentScale or
  // viewportW/H to the dep array (would re-trigger pan on every wheel tick or
  // resize event).
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

  // Pitfall 5 (verbatim): canonical empty-Stage click deselect using
  // e.target === e.target.getStage(). Race-free under React StrictMode.
  const handleStageClick = useCallback(
    (e: Konva.KonvaEventObject<MouseEvent | TouchEvent>) => {
      if (e.target === e.target.getStage()) {
        useUIStore.getState().selectIds([])
      }
    },
    [],
  )

  // D-15 hover tooltip wiring — translate id → name + read pointer position.
  const handleHoverEnter = useCallback(
    (id: string) => {
      const stage = stageRef.current
      const condado = metaQ.data?.condados.find((c) => c.id === id)
      const name = condado?.name ?? null
      const pos = stage?.getPointerPosition() ?? { x: 0, y: 0 }
      setHover({ name, x: pos.x, y: pos.y })
    },
    [metaQ.data],
  )

  const handleHoverLeave = useCallback(() => {
    setHover((h) => (h.name === null ? h : { name: null, x: h.x, y: h.y }))
  }, [])

  // ------------------------------------------------------------------------
  // EARLY RETURNS — safe because every hook above has been called. Every
  // branch must carry `ref={setContainerRef}` so the observer migrates.
  // ------------------------------------------------------------------------
  if (metaQ.isPending) {
    return (
      <div ref={setContainerRef} style={{ width: '100%', height: '100%', padding: 24 }}>
        Loading map…
      </div>
    )
  }

  if (metaQ.error) {
    const msg = (metaQ.error as Error).message
    const text =
      msg === 'MAP_NOT_GENERATED'
        ? 'No map generated yet. Run the pipeline first.'
        : 'Failed to load territory data. Check the server is running.'
    return (
      <div ref={setContainerRef} style={{ width: '100%', height: '100%', padding: 24 }}>
        {text}
      </div>
    )
  }

  if (
    !metaQ.data ||
    !projection ||
    !territoriesQ.data ||
    !condadoColorsQ.data ||
    !baroniesQ.data ||
    !baronyColorsQ.data
  ) {
    return (
      <div ref={setContainerRef} style={{ width: '100%', height: '100%', padding: 24 }}>
        Loading map…
      </div>
    )
  }

  const vSuffix = cacheVersion ? `?v=${encodeURIComponent(cacheVersion)}` : ''
  const terrainSrc = `/api/v3/projects/${projectId}/artifacts/terrain.png${vSuffix}`

  const canvasPane = (
    <div
      ref={setContainerRef}
      data-testid="canvas-stage"
      style={{
        position: 'relative',
        flex: 1,
        height: '100%',
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
          visible={layerVisibility.condados}
        />
        <TerritoryLayer
          territories={territoriesQ.data}
          condadoColors={condadoColorsQ.data}
          visible={layerVisibility.condados}
          showBorders={layerVisibility.borders}
          onHoverEnter={handleHoverEnter}
          onHoverLeave={handleHoverLeave}
        />
        <BaronyLayer
          baronies={baroniesQ.data}
          baronyColors={baronyColorsQ.data}
          visible={layerVisibility.baronies}
        />
        <DecorationsLayer
          condados={metaQ.data.condados}
          condadoColors={condadoColorsQ.data}
          layerVisibility={{
            capitals: layerVisibility.capitals,
            labels: layerVisibility.labels,
          }}
          currentScale={currentScale}
          minScale={minScale}
          isEditMode={false}
        />
        <InteractionLayer territories={territoriesQ.data} />
      </Stage>
      <LayerTogglePanel />
      <LegendCard />
      <FitToViewButton onFit={fitToView} />
      <HoverTooltip name={hover.name} x={hover.x} y={hover.y} />
      <span data-testid="territory-layer-ready" hidden />
    </div>
  )

  return (
    <ProjectionProvider value={projection}>
      <div
        style={{
          display: 'flex',
          width: '100%',
          height: '100%',
        }}
      >
        {canvasPane}
        {project && (
          <aside
            data-testid="inspector-sidebar"
            style={{
              width: 320,
              height: '100%',
              overflow: 'auto',
              borderLeft: '1px solid var(--gray-6)',
              background: 'var(--color-panel-solid)',
              padding: 16,
            }}
          >
            <InspectorSidebar
              metadata={metaQ.data}
              territories={territoriesQ.data}
              project={{
                name: project.name,
                country_qid: project.country_qid,
                period_start: project.period_start,
                period_end: project.period_end,
              }}
            />
          </aside>
        )}
      </div>
    </ProjectionProvider>
  )
}
