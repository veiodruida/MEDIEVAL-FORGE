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
  // Cache-bust param: pass project.updated_at here so that when the pipeline
  // regenerates artifacts, both the TanStack queryKey AND the fetched URLs
  // change — forcing both the in-memory cache and the browser HTTP cache to
  // miss. Without this, /preview/*.json stays stale after regeneration and
  // the user sees the prior map until they hard-refresh.
  cacheVersion?: string
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
 * GAP-05 fix (02-05): Stage dimensions track the parent container via a
 * callback-ref ResizeObserver pattern (B-1 fix). The naive
 * `useEffect(() => { ref.current ... }, [])` approach captures the loading div
 * once at mount and never migrates when React swaps in the content div after
 * metaQ resolves. The callback-ref below (dis)connects the observer on every
 * DOM mount/unmount so the observer always targets the LIVE div.
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
export function CanvasViewer({ projectId, width = 800, height = 600, cacheVersion }: CanvasViewerProps) {
  const stageRef = useRef<Konva.Stage | null>(null)

  // --- B-1 callback-ref ResizeObserver ------------------------------------
  // Viewport state — MUST be declared BEFORE any conditional early returns so
  // hook order stays stable across the loading/error/content branches. The
  // width/height props act as a fallback when CanvasViewer is mounted outside
  // a flex parent (preserves existing test suite behavior).
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
          // T-02-05-01: guard against 0x0 transient measurements that occur
          // during fast unmount/remount sequences. A 0x0 write would collapse
          // the Stage and break minScale recompute.
          if (cr.width > 0 && cr.height > 0) {
            setViewportW(Math.floor(cr.width))
            setViewportH(Math.floor(cr.height))
          }
        }
      })
      ro.observe(el)
      roRef.current = ro
      // GAP-05 belt-and-suspenders: some browsers deliver the initial
      // ResizeObserver entry asynchronously (or not at all when the element
      // is already laid out before observe() is called).  Read the live rect
      // synchronously right after observe() so the Stage never stays locked
      // at the 800×600 prop defaults if the observer fires late or is dropped.
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
  const select = useUIStore((s) => s.select)

  const [territoriesQ, baroniesQ, condadoColorsQ, , metaQ] = useCanvasArtifacts(
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
  // Uses viewportW/viewportH directly (state) rather than stage.width()/height()
  // so it recomputes with fresh dims on the SAME render as the resize update —
  // stage.width() would still reflect the previous Stage prop at this point.
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

  // D-12: auto-fit once projection lands AND whenever Stage dimensions change.
  // viewportW/H in the dep array re-runs fitToView on resize so minScale stays
  // correct. DO NOT add viewportW/H to the pan-on-select effect's deps —
  // that would re-pan on every resize event.
  useEffect(() => {
    if (projection) fitToView()
  }, [projection, fitToView, viewportW, viewportH])

  // Ctrl/Cmd+0 + Esc shortcuts
  useKeyboardShortcuts(fitToView)

  // RESEARCH §Pitfall 5 + UI-SPEC §Neighbor Navigation: pan canvas to center the
  // newly selected territory. Runs for any selection change — initial click AND
  // neighbor-chip navigation — so the inspector-driven flow is handled uniformly.
  //
  // IMPORTANT: do NOT list currentScale in the dep array. It is read live from
  // stage.scaleX() inside the effect. If we depended on it, wheel zoom's
  // setCurrentScale would retrigger this effect and snap the viewport back to
  // the selected territory on every wheel tick. Also do NOT add viewportW/H —
  // resize events should not re-trigger selection-pan behavior.
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

  // ------------------------------------------------------------------------
  // EARLY RETURNS — safe because every hook above has been called. B-1:
  // `ref={setContainerRef}` MUST appear on the root div of EVERY branch so
  // the observer migrates from the loading div to the content div when metaQ
  // resolves. Missing the ref on any branch silently breaks the B-1 fix.
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
    !baroniesQ.data
  ) {
    return (
      <div ref={setContainerRef} style={{ width: '100%', height: '100%', padding: 24 }}>
        Loading map…
      </div>
    )
  }

  const vSuffix = cacheVersion ? `?v=${encodeURIComponent(cacheVersion)}` : ''
  const terrainSrc = `/api/projects/${projectId}/preview/terrain.png${vSuffix}`

  return (
    <ProjectionProvider value={projection}>
      {/* The wrapping div uses 100%/100% — NOT viewportW/H — to avoid a
          feedback loop where observer→state→size→observer cycles forever. */}
      <div
        ref={setContainerRef}
        style={{
          position: 'relative',
          width: '100%',
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
