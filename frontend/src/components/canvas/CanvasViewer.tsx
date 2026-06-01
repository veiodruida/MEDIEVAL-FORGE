import Konva from 'konva'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Layer, Line, Stage } from 'react-konva'
import { BackgroundLayer } from './BackgroundLayer'
import { TerritoryLayer } from './TerritoryLayer'
import { BaronyLayer } from './BaronyLayer'
import { LayerTogglePanel } from './LayerTogglePanel'
import { LegendCard } from './LegendCard'
import { DecorationsLayer } from './DecorationsLayer'
import { InteractionLayer } from './InteractionLayer'
import { VertexEditLayer } from './VertexEditLayer'
import { BezierEditLayer } from './BezierEditLayer'
import { PenDrawLayer } from './PenDrawLayer'
import type { PenDrawHandlers } from './PenDrawLayer'
import { PenShapeManipulateLayer } from './PenShapeManipulateLayer'
import { CondadoPicker } from './CondadoPicker'
import type { CondadoPickerValue, CondadoPickerCondado } from './CondadoPicker'
import { CoordTooltip } from './CoordTooltip'
import { FitToViewButton } from './FitToViewButton'
import { HoverTooltip } from './HoverTooltip'
import { InspectorSidebar } from './InspectorSidebar'
import { SelectionBridge } from '../editor/SelectionBridge'
import { ProjectionProvider } from '../../context/ProjectionContext'
import type { Project } from '../../api/client'
import {
  buildProjectionConfig,
  computeFitToView,
  geoToCanvas,
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
import { useLandmaskRing } from '../../hooks/useLandmaskRing'
import { useUIStore } from '../../stores/uiStore'
import { usePipelineParams } from '../../stores/usePipelineParams'
import { useRunStore } from '../../stores/useRunStore'
import { useEditorStore } from '../../stores/useEditorStore'
import type { ViewportBBox } from './VertexEditLayer'
import type { BaronyRender } from '../../hooks/useCanvasArtifacts'

// ── Phase 08.3 Plan 08 (D-19): resolveAutoSelect ──────────────────────────────
// Pure helper: matches the pending barony name against the refetched baronies array.
// Exact id equality (NOT substring). Exported for the postCloseAutoSelect vitest spec.
// Returns the matching name (to call selectBarony with) or null if not yet present.
export function resolveAutoSelect(
  pendingName: string,
  baronies: BaronyRender[],
): string | null {
  if (!pendingName) return null
  const found = baronies.find((b) => b.id === pendingName)
  return found ? found.id : null
}

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
  /** Phase 08.3 Plan 05: callback propagated up from PenDrawLayer.onDrawingStateChange.
   *  WorkspaceToolbar passes this down to derive disabledTools during pen drawing. */
  onPenDrawingChange?: (isDrawing: boolean) => void
}

const PADDING_PCT = 0.05

/**
 * Read-only canvas viewer for Phase 03 (read-only canvas redesign).
 *
 * Composition (5 Konva layers in z-order):
 *   BackgroundLayer  → terrain PNG (or stage raster when stageView !== 'render-final')
 *   TerritoryLayer   → condado polygons (hidden in stage-overlay views)
 *   BaronyLayer      → barony polygons (hidden in stage-overlay views)
 *   DecorationsLayer → capitals dual-ring + labels (hidden in stage-overlay views)
 *   InteractionLayer → gold selection outline (listening=false)
 * Sibling absolute-positioned overlays: LayerTogglePanel, FitToViewButton, HoverTooltip.
 *
 * Phase 04 additions:
 *   - stageView from usePipelineParams gates layer visibility (UI-SPEC §StageViewToggle)
 *   - priorTokens from useRunStore enables D-13 cancel revert via effectiveCacheVersion
 *   - Centralized Konva.clearCache() per layer fires AFTER hydration completes (Pitfall 6)
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
export function CanvasViewer({ projectId, width = 800, height = 600, cacheVersion, project, onPenDrawingChange }: CanvasViewerProps) {
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

  // CoordTooltip state for vertex drag (D-33, Phase 08 Plan 05).
  // setCoordTooltip wired by 08-06a when drag emits lat/lon cursor position.
  // Declared here so CoordTooltip renders as a DOM sibling from the start.
  const [coordTooltip, setCoordTooltip] = useState<{
    visible: boolean;
    lat: number;
    lon: number;
    cursorX: number;
    cursorY: number;
  }>({ visible: false, lat: 0, lon: 0, cursorX: 0, cursorY: 0 })
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  void setCoordTooltip // suppress TS6133 until 08-06a wires drag callback

  // Phase 08: activeTerritoryId from useEditorStore (for VertexEditLayer + clearCache)
  const activeTerritoryId = useEditorStore((s) => s.activeTerritoryId)
  // Phase 08 Plan 14 (GAP-B): activeBranchId forwarded to VertexEditLayer + LayerTogglePanel
  // so split/merge/translate no longer early-return with null branchId.
  const activeBranchId = useEditorStore((s) => s.activeBranchId)
  // Phase 08 Plan 16 (LANDMASK-01): editableLayer drives cyan handle rendering
  const editableLayer = useEditorStore((s) => s.editableLayer)
  const landmaskMode = useEditorStore((s) => s.landmaskMode)

  // Phase 08.3 Plan 05: activeTool selector — drives PenDrawLayer z=6 mount gate AND
  // the bezierActive mutual-exclusion below (read before bezierActive so the gate can
  // suppress BezierEditLayer while the pen tool is active).
  const activeTool = useEditorStore((s) => s.activeTool)

  // Phase 08.3 Plan 08 (user request): ghost overlay ring — the most-recent pending
  // create/carve op ring from the editLog. Rendered as a semi-transparent dashed overlay
  // while pendingSelectName is active (between commit and Apply+refetch settling).
  // Cleared when pendingSelectName clears (the real enclave appears after Apply).
  const editLog = useEditorStore((s) => s.editLog)

  // Phase 08.1 (BEZ-UAT-01): z=5 mutual-exclusion gate. When a barony is selected on
  // the baronies layer, mount BezierEditLayer (curve anchors) instead of VertexEditLayer
  // (raw vertex handles). BezierEditLayer self-gates on the V tool internally and renders
  // null otherwise, so under S/M tools neither layer shows handles (S/M operate at
  // territory level, not per-vertex — see SUMMARY mutual-exclusion note).
  const bezierActive = editableLayer === 'baronies' && activeTerritoryId !== null

  // Phase 08.3 Plan 05: penDrawing state — driven by PenDrawLayer.onDrawingStateChange.
  // WorkspaceToolbar reads this via the onPenDrawingChange prop to derive disabledTools.
  const [penDrawing, setPenDrawing] = useState(false)
  const handlePenDrawingChange = useCallback(
    (isDrawing: boolean) => {
      setPenDrawing(isDrawing)
      onPenDrawingChange?.(isDrawing)
    },
    [onPenDrawingChange],
  )

  // Phase 08.3 Plan 08 (D-21): action-bar handlers registered by PenDrawLayer on mount.
  // PenDrawLayer lives inside the Konva tree; DOM buttons live in CanvasViewer.
  // Handlers are registered via onHandlersReady callback and stored in a ref.
  const penHandlersRef = useRef<PenDrawHandlers | null>(null)
  const handlePenHandlersReady = useCallback((handlers: PenDrawHandlers) => {
    penHandlersRef.current = handlers
  }, [])

  // Phase 08.3 Plan 08 (D-21): freehand toggle state mirrored in CanvasViewer so the
  // DOM button label can show the current mode (active/inactive) and the action bar can
  // show the correct button label (Modo livre vs click-pen).
  const [freehandActive, setFreehandActive] = useState(false)
  const handleFreehandToggle = useCallback(() => {
    const handlers = penHandlersRef.current
    if (!handlers) return
    const next = !handlers.getFreehandMode()
    handlers.setFreehandMode(next)
    setFreehandActive(next)
  }, [])

  // Phase 08.3 Plan 08 (D-19): pendingSelectName — set when PenDrawLayer fires onCreated.
  // The auto-select watcher effect (keyed on effectiveBaronies) fires selectBarony(name)
  // only AFTER the baroniesQ refetch carries the new barony — never optimistically.
  const [pendingSelectName, setPendingSelectName] = useState<string | null>(null)
  const handlePenCreated = useCallback((name: string) => {
    setPendingSelectName(name)
    setFreehandActive(false) // reset freehand toggle after commit
    setPickedCondado(null)   // reset picker for next draw (09 D-26 reset on commit)
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  // Phase 08.3 Plan 09 (D-26): CondadoPicker state.
  // pickedCondado: the user's explicit condado override; null = inherit from parent (07 default).
  // parentCondadoIdx: the enclosing barony's condado_idx as the cursor moves, for the picker label.
  const [pickedCondado, setPickedCondado] = useState<CondadoPickerValue | null>(null)
  const [parentCondadoIdx, setParentCondadoIdx] = useState<number | null>(null)
  const handleParentCondadoChange = useCallback((idx: number | null) => {
    setParentCondadoIdx(idx)
  }, [])

  // Suppress unused-var: penDrawing kept for future CanvasViewer-local gate use
  void penDrawing

  // Phase 08 Plan 16: landmask ring from backend (branch edit-event or NE union)
  const landmaskRing = useLandmaskRing(projectId, activeBranchId ?? undefined)

  // Phase 08 Plan 16: latestLandmaskRef keeps the most recent coords buffered by
  // VertexEditLayer, seeded with the query ring so Apply with no drags is a replay.
  const latestLandmaskRef = useRef<Array<[number, number]>>(landmaskRing ?? [])
  // Sync seed when ring loads (e.g. first query resolve)
  useEffect(() => {
    if (landmaskRing && landmaskRing.length > 0) {
      latestLandmaskRef.current = landmaskRing
    }
  }, [landmaskRing])

  // Phase 08 Plan 16: called by VertexEditLayer on every landmask handle dragend.
  // Always buffers in latestLandmaskRef; POSTs immediately when auto-immediate mode.
  const handleLandmaskCoordsChange = useCallback(
    (coords: Array<[number, number]>) => {
      latestLandmaskRef.current = coords
      // In auto-immediate mode, POST on every dragend (per-edit cascade)
      if (landmaskMode === 'auto-immediate' && projectId && activeBranchId) {
        void fetch(`/api/v3/projects/${projectId}/editor/apply`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            op_type: 'landmask_replace',
            payload: { new_landmask_coords: coords },
            branch_id: activeBranchId,
          }),
        }).catch(() => {})
      }
    },
    [landmaskMode, projectId, activeBranchId],
  )

  // Phase 08 Plan 16: Apply button callback (manual mode).
  // POSTs latestLandmaskRef.current — which was seeded from the query ring on load
  // and updated on every dragend, so Apply never sends [].
  const handleApplyLandmask = useCallback(async () => {
    if (!projectId || !activeBranchId) return
    await fetch(`/api/v3/projects/${projectId}/editor/apply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        op_type: 'landmask_replace',
        payload: { new_landmask_coords: latestLandmaskRef.current },
        branch_id: activeBranchId,
      }),
    }).catch(() => {})
  }, [projectId, activeBranchId])

  // Pitfall 10: clearCache on activeTerritoryId change (Phase 08).
  // Fires AFTER hydration completes — guard on stageRef.current.
  useEffect(() => {
    const stage = stageRef.current
    if (!stage) return
    stage.getLayers().forEach((layer) => {
      layer.clearCache()
    })
  }, [activeTerritoryId])

  // Phase 04: stageView from usePipelineParams (UI-SPEC §StageViewToggle)
  const stageView = usePipelineParams((s) => s.stageView)

  // Phase 04 D-13: priorTokens populated by useRunStore.revertStage (04-03 Task 4)
  // When a stage_cancel SSE fires, revertStage sets priorTokens[stage] = prior_token.
  // Using priorTokens.render as effectiveCacheVersion forces CanvasViewer to
  // re-fetch artifacts at the prior token's URL (?v=<prior_token>) so the canvas
  // reverts to the state before the cancelled render.
  const priorTokens = useRunStore((s) => s.priorTokens)

  // D-02 (Phase 04.1): hold-spacebar before/after preview gesture.
  //
  // Track the previous cacheVersion via useRef + useState. Every time the
  // `cacheVersion` prop transitions (slider-driven render completed → backend
  // bumped proj.updated_at → TanStack refetched → new prop value), promote
  // the prior value to `previousCacheVersion` state. The browser HTTP cache
  // retains the previous artifact URLs (`?v=<previousCacheVersion>`) thanks
  // to query-string cache-busting (useCanvasArtifacts.ts:64,123), so the
  // gesture serves from warm cache — instant raster swap.
  //
  // This is INTENTIONALLY decoupled from priorTokens.render (D-13), which
  // serves a different purpose: post-cancel revert display. The gesture and
  // D-13 are distinct features and their state derives from different sources.
  const [previousCacheVersion, setPreviousCacheVersion] = useState<string | undefined>(undefined)
  const lastCacheVersionRef = useRef<string | undefined>(cacheVersion)

  useEffect(() => {
    // Promote the previously-seen cacheVersion to state on every transition.
    // Initial mount: lastCacheVersionRef seeded with the first cacheVersion
    // value; no transition happens, previousCacheVersion stays undefined.
    // First transition (v1 → v2): previousCacheVersion becomes v1.
    // Subsequent transitions (v2 → v3): previousCacheVersion becomes v2.
    if (
      cacheVersion !== undefined &&
      lastCacheVersionRef.current !== undefined &&
      lastCacheVersionRef.current !== cacheVersion
    ) {
      setPreviousCacheVersion(lastCacheVersionRef.current)
    }
    lastCacheVersionRef.current = cacheVersion
  }, [cacheVersion])

  const [previewPrior, setPreviewPrior] = useState(false)

  // Gesture enabled only when a previous render exists. On the FIRST render
  // of a project (no cacheVersion transition yet) the gesture is a no-op.
  const previewEnabled = previousCacheVersion !== undefined

  useEffect(() => {
    if (!previewEnabled) {
      // If previousCacheVersion clears mid-hold (rare), reset.
      setPreviewPrior(false)
      return
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code !== 'Space' || e.repeat) return
      // Don't intercept when user is typing in a slider/inspector input.
      const tag = (e.target as HTMLElement | null)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || (e.target as HTMLElement | null)?.isContentEditable) return
      e.preventDefault() // prevent page-scroll-on-space default
      setPreviewPrior(true)
    }
    const onKeyUp = (e: KeyboardEvent) => {
      if (e.code !== 'Space') return
      setPreviewPrior(false)
    }
    const onBlur = () => setPreviewPrior(false)
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    window.addEventListener('blur', onBlur)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
      window.removeEventListener('blur', onBlur)
    }
  }, [previewEnabled])

  // D-02 + D-13 precedence (top wins):
  //   1. Spacebar gesture (highest priority) → previousCacheVersion
  //   2. D-13 cancel revert (preserved from Phase 04) → priorTokens.render
  //   3. Default → cacheVersion (prop, current settled state)
  // The two "prior" semantics are intentionally distinct:
  //   - previousCacheVersion: "the render that was current right before the
  //     latest slider-driven re-render replaced it" — observable only on
  //     hold-spacebar; on release the raster returns to cacheVersion (NOT
  //     to priorTokens.render). This is the gesture per D-02.
  //   - priorTokens.render: "the prior render that the user reverted to
  //     after cancelling an in-flight render" — always-on display from the
  //     moment the stage_cancel SSE fires until the next successful render.
  //     This is the cancel revert per D-13/SC-4.
  const effectiveCacheVersion =
    previewPrior && previousCacheVersion !== undefined
      ? previousCacheVersion
      : priorTokens.render !== undefined
        ? priorTokens.render
        : cacheVersion

  const [territoriesQ, baroniesQ, condadoColorsQ, baronyColorsQ, metaQ, stageRasterUrl] =
    useCanvasArtifacts(projectId, projection, effectiveCacheVersion, stageView)

  // Phase 04.1 debug 04.1-bug-pan-reset fix: TanStack v5 `keepPreviousData`
  // (the `placeholderData` helper) does NOT carry data across queryKey changes
  // when used inside `useQueries`. When `cacheVersion` bumps (slider re-render),
  // every queryKey changes -> all queries go pending -> `!metaQ.data` etc fire
  // true -> CanvasViewer unmounts the Konva Stage -> imperative x/y/scale lost
  // -> next mount sits at default (0,0,1) -> fit-to-view recenters to upper-left
  // (the reported "pan reset" symptom).
  //
  // Fix: keep the last-good data in refs at the component level so the early-
  // return guards can fall back to stale data while a refetch is in flight.
  // This keeps the Stage mounted across cacheVersion transitions.
  const lastGoodMetaRef = useRef(metaQ.data)
  const lastGoodTerritoriesRef = useRef(territoriesQ.data)
  const lastGoodBaroniesRef = useRef(baroniesQ.data)
  const lastGoodCondadoColorsRef = useRef(condadoColorsQ.data)
  const lastGoodBaronyColorsRef = useRef(baronyColorsQ.data)
  if (metaQ.data) lastGoodMetaRef.current = metaQ.data
  if (territoriesQ.data) lastGoodTerritoriesRef.current = territoriesQ.data
  if (baroniesQ.data) lastGoodBaroniesRef.current = baroniesQ.data
  if (condadoColorsQ.data) lastGoodCondadoColorsRef.current = condadoColorsQ.data
  if (baronyColorsQ.data) lastGoodBaronyColorsRef.current = baronyColorsQ.data
  const effectiveMeta = metaQ.data ?? lastGoodMetaRef.current
  const effectiveTerritories = territoriesQ.data ?? lastGoodTerritoriesRef.current
  const effectiveBaronies = baroniesQ.data ?? lastGoodBaroniesRef.current
  const effectiveCondadoColors = condadoColorsQ.data ?? lastGoodCondadoColorsRef.current
  const effectiveBaronyColors = baronyColorsQ.data ?? lastGoodBaronyColorsRef.current

  // Phase 08.3 Plan 08 (D-19): post-close auto-select watcher.
  // effectiveBaronies is now in scope — this effect fires on every baroniesQ refetch.
  // When the refetched array contains a feature with id === pendingSelectName,
  // selectBarony(name) fires and the watcher clears. Never optimistic.
  // eslint-disable-next-line react-hooks/rules-of-hooks
  useEffect(() => {
    if (!pendingSelectName) return
    const match = resolveAutoSelect(pendingSelectName, effectiveBaronies ?? [])
    if (match) {
      useUIStore.getState().selectBarony(match)
      setPendingSelectName(null)
    }
  // effectiveBaronies reference change = new refetch data arrived — that is the trigger
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingSelectName, effectiveBaronies])

  // Build projection when metadata loads OR when metadata bounds change.
  // Phase 04.1 D-01: previously this effect ran `if (metaQ.data && !projection)`
  // which froze projection at the first value seen — preventing fit-to-view
  // from ever responding to a region/project switch. We now rebuild projection
  // when the underlying bounds actually change, gated by a useMemo on the
  // primitive scalars so a slider re-render that produces a new metaQ.data
  // object reference with identical bounds is a no-op.
  const metaBoundsKey = useMemo(() => {
    if (!metaQ.data) return null
    const [mapW, mapH] = metaQ.data.map_size
    const { bounds } = metaQ.data
    return `${mapW}x${mapH}:${bounds.lon_min},${bounds.lon_max},${bounds.lat_min},${bounds.lat_max}`
  }, [metaQ.data])

  useEffect(() => {
    if (!metaQ.data || metaBoundsKey === null) return
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [metaBoundsKey])

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

  // Phase 08.3 (UAT fix C): auto-zoom to a barony when it is selected for editing.
  // Small baronies render their ~5 Bézier anchors in an overlapping ~20px cluster at
  // fit zoom — impossible to grab. This frames the selected barony at ~half the viewport
  // (clamped to the wheel zoom range) so the anchors separate. Imperative scale/position
  // mirrors fitToView; it does NOT touch minScale, so Fit-to-view / Ctrl+0 still resets
  // to the whole map. Only currentScale syncs (drives screen-space handle sizing).
  const zoomToBarony = useCallback(
    (ring: [number, number][]) => {
      const stage = stageRef.current
      if (!stage || !projection || ring.length === 0) return
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
      for (const [lon, lat] of ring) {
        const [x, y] = geoToCanvas(lon, lat, projection)
        if (x < minX) minX = x
        if (y < minY) minY = y
        if (x > maxX) maxX = x
        if (y > maxY) maxY = y
      }
      const bw = maxX - minX
      const bh = maxY - minY
      if (bw <= 0 || bh <= 0) return
      // Frame the barony at ~half the viewport so there is surrounding context.
      const target = Math.min((viewportW * 0.5) / bw, (viewportH * 0.5) / bh)
      const maxScale = minScale * MAX_SCALE_MULTIPLIER
      const scale = Math.max(minScale, Math.min(target, maxScale))
      const cx = (minX + maxX) / 2
      const cy = (minY + maxY) / 2
      stage.scale({ x: scale, y: scale })
      stage.position({ x: viewportW / 2 - cx * scale, y: viewportH / 2 - cy * scale })
      stage.batchDraw()
      setCurrentScale(scale)
    },
    [projection, viewportW, viewportH, minScale],
  )

  // Fire zoomToBarony only when the selected barony actually CHANGES (not on every
  // re-render / baronies refetch) so it never clobbers the user's manual zoom mid-edit.
  const prevZoomedBaronyRef = useRef<string | null>(null)
  useEffect(() => {
    if (activeTerritoryId === null || editableLayer !== 'baronies' || activeTool === 'P') {
      prevZoomedBaronyRef.current = null
      return
    }
    if (prevZoomedBaronyRef.current === activeTerritoryId) return
    const b = effectiveBaronies?.find((x) => x.id === activeTerritoryId)
    if (!b?.geoRing || b.geoRing.length === 0) return
    prevZoomedBaronyRef.current = activeTerritoryId
    zoomToBarony(b.geoRing)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTerritoryId, editableLayer, activeTool, effectiveBaronies, zoomToBarony])

  // D-01 (Phase 04.1): stable projection-bounds key prevents fitToView from
  // re-firing when a slider triggers a metadata refetch → new projection
  // object with identical bounds. fitToView still fires when bounds actually
  // change (project switch, region load) — those cases bump the bounds key.
  // Viewport resize is handled by a separate effect below so the two
  // independent reasons to fit (bounds change vs. viewport change) can't
  // entangle.
  const projectionBoundsKey = useMemo(() => {
    if (!projection) return null
    return `${projection.mapW}x${projection.mapH}:${projection.lonMin},${projection.lonMax},${projection.latMin},${projection.latMax}`
  }, [
    projection?.mapW,
    projection?.mapH,
    projection?.lonMin,
    projection?.lonMax,
    projection?.latMin,
    projection?.latMax,
  ])

  const prevBoundsKeyRef = useRef<string | null>(null)

  // Auto-fit on first mount AND on real bounds change. Slider re-renders that
  // produce a new projection ref with identical bounds DO NOT fire fitToView
  // here — the bounds-key compare gates the actual call (UAT gap #1).
  useEffect(() => {
    if (!projection || projectionBoundsKey === null) return
    if (prevBoundsKeyRef.current !== projectionBoundsKey) {
      prevBoundsKeyRef.current = projectionBoundsKey
      fitToView()
    }
  }, [projection, projectionBoundsKey, fitToView])

  // Separate effect for viewport resize: fit-to-view stays responsive to
  // window/container resize but is NOT entangled with projection reference
  // changes. Without this, a slider re-render that produces a new projection
  // object with identical bounds would still reset zoom (UAT gap #1).
  const viewportKeyRef = useRef<string>('')
  useEffect(() => {
    if (!projection) return
    const vkey = `${viewportW}x${viewportH}`
    if (viewportKeyRef.current === '') {
      // First measurement — handled by the bounds-key effect above
      viewportKeyRef.current = vkey
      return
    }
    if (viewportKeyRef.current !== vkey) {
      viewportKeyRef.current = vkey
      // Plan 04.1-05 D-01 fix: only re-fit if the user has NOT manually
      // zoomed. Otherwise a viewport oscillation (workspace layout settle,
      // sidebar mount, container flex re-measure, slider-driven refetch
      // briefly re-flowing the layout) clobbers the user's chosen zoom.
      // This mirrors the bounds-key gate's intent: "don't clobber user zoom".
      // Legitimate fit cases (genuine window resize from the same baseline)
      // still fire because currentScale === minScale at that moment.
      if (Math.abs(currentScale - minScale) < 1e-6) {
        fitToView()
      }
    }
  }, [viewportW, viewportH, projection, fitToView, currentScale, minScale])

  // Ctrl/Cmd+0 fit-to-view shortcut
  useKeyboardShortcuts(fitToView)

  // Plan 04.1-05 (D-01 E2E gate): expose Konva Stage scale to Playwright via
  // a window-level escape hatch. Gated on `import.meta.env.DEV` so the hook
  // never ships in production builds (mitigates T-04.1-05-01). Mirrors
  // `currentScale` (already kept in sync with stage.scaleX() by the wheel
  // handler at line 422-423 and by fitToView at line 295).
  useEffect(() => {
    if (!import.meta.env.DEV) return
    ;(window as unknown as { __forgeStageScale?: number }).__forgeStageScale =
      currentScale
    return () => {
      delete (window as unknown as { __forgeStageScale?: number })
        .__forgeStageScale
    }
  }, [currentScale])

  // Phase 08.3 Plan 11 (UAT fix): expose the pending ring's SCREEN positions to
  // Playwright so drag-gesture anchors land exactly on the rendered shape.
  //
  // Returns an array of {x, y} in canvas-container-relative pixels (i.e., relative
  // to the top-left of the data-testid="canvas-stage" div).  Add stageBox.x/y in
  // the spec to convert to absolute page coordinates.
  //
  // Read-only — never used as input.  All gestures stay real page.mouse.
  useEffect(() => {
    if (!import.meta.env.DEV) return
    const w = window as unknown as Record<string, unknown>
    w.__forgePendingRingScreen = () => {
      const stage = stageRef.current
      const proj = projection
      if (!stage || !proj) return null
      const log = useEditorStore.getState().editLog
      let ring: Array<{ lat: number; lon: number }> | null = null
      for (let i = log.length - 1; i >= 0; i--) {
        const op = log[i]
        if ((op.op === 'create' || op.op === 'carve') && op.ring && op.ring.length >= 3) {
          ring = op.ring
          break
        }
      }
      if (!ring) return null
      const scale = stage.scaleX()
      const pos = stage.position()
      return ring.map((pt: { lat: number; lon: number }) => {
        const [cx, cy] = geoToCanvas(pt.lon, pt.lat, proj)
        return {
          x: pos.x + cx * scale,
          y: pos.y + cy * scale,
        }
      })
    }
    return () => {
      delete w.__forgePendingRingScreen
    }
  // projection and stageRef.current are stable after initial mount; currentScale
  // changes on zoom but the hatch reads live from stage.scaleX() so no dep needed.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projection])

  // Pan canvas to center the newly selected territory (D-15 single-select pan).
  // Read scale live from stage.scaleX() — DO NOT add currentScale or
  // viewportW/H to the dep array (would re-trigger pan on every wheel tick or
  // resize event).
  //
  // Phase 04.1 follow-up (debug session 04.1-bug-pan-reset): the effect MUST
  // only fire on a real selectedId TRANSITION. `metaQ.data` was historically
  // in the dep array because the pan needs metadata to resolve lon/lat — but
  // metaQ.data REFERENCE changes on every successful TanStack refetch
  // (slider drag → cacheVersion bump → refetch → select() builds fresh
  // condado objects → mergedMeta useMemo emits a new object). Without a
  // selection-CHANGE gate, every slider drag re-fired panToGeoCenter,
  // overwriting the user's manual pan. The fix: track prevSelectedIdRef and
  // bail when selectedId hasn't actually changed (mirrors Plan 04.1-03's
  // prevBoundsKeyRef pattern for the auto-fit effect).
  const prevSelectedIdRef = useRef<string | null>(null)
  useEffect(() => {
    const stage = stageRef.current
    if (!stage || !projection || !selectedId || !metaQ.data) {
      // Keep ref in sync with selection clears so a future re-select of the
      // SAME id still fires (clear → re-select === transition).
      prevSelectedIdRef.current = selectedId ?? null
      return
    }
    if (prevSelectedIdRef.current === selectedId) return
    prevSelectedIdRef.current = selectedId
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

  // CLAUDE.md non-negotiable: Konva.clearCache() after every geometric mutation.
  // Phase 04: cacheVersion or stageView change = geometric mutation. Pitfall 6:
  // fire AFTER hydration completes — guard inside the effect on stageRef.current
  // and on all query data being present. By the time this effect runs with all
  // queries resolved, the early-return branches below have already been bypassed,
  // and all Konva layers are mounted (stageRef.current is the live Konva.Stage).
  useEffect(() => {
    const stage = stageRef.current
    if (!stage) return
    // Guard: only clear cache after data is fully hydrated (Pitfall 6).
    // territoriesQ/baroniesQ/metaQ are all loaded by the time stageRef.current
    // is populated, but we add explicit guards for safety.
    if (!territoriesQ.data || !baroniesQ.data || !metaQ.data) return
    // getLayers() returns every Konva.Layer in the stage in z-order.
    stage.getLayers().forEach((layer) => {
      layer.clearCache()
      layer.batchDraw()
    })
    // Dependencies: effectiveCacheVersion + stageView.
    // effectiveCacheVersion folds priorTokens.render so cancel triggers a
    // re-cache bust per D-13 + D-14.
  }, [effectiveCacheVersion, stageView]) // eslint-disable-line react-hooks/exhaustive-deps

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
      // Phase 08.3 (UAT fix): while the pen tool is active, the PenDrawLayer hit-Rect
      // owns empty-canvas clicks (anchor placement). Do not clear the selection here or
      // the in-progress draw context (selected neighbor barony) would be wiped mid-path.
      if (useEditorStore.getState().activeTool === 'P') return
      if (e.target === e.target.getStage()) {
        // Clear both selection tiers at once — empty-stage click should land
        // on the placeholder regardless of which mode the inspector was in.
        const s = useUIStore.getState()
        s.selectIds([])
        s.selectBarony(null)
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

  // Phase 08 Plan 05: compute viewport bbox in world (lat/lon) coords for VertexEditLayer culling.
  // MUST be declared before the early returns below (Rules of Hooks — error #310 otherwise).
  const vertexViewport = useMemo((): ViewportBBox | null => {
    if (!projection) return null
    const stage = stageRef.current
    const scale = stage?.scaleX() ?? currentScale
    const pos = stage?.position() ?? { x: 0, y: 0 }
    const mapX0 = -pos.x / scale
    const mapY0 = -pos.y / scale
    const mapX1 = mapX0 + viewportW / scale
    const mapY1 = mapY0 + viewportH / scale
    const cx0 = Math.max(0, mapX0)
    const cy0 = Math.max(0, mapY0)
    const cx1 = Math.min(projection.mapW, mapX1)
    const cy1 = Math.min(projection.mapH, mapY1)
    const span = (projection.lonMax - projection.lonMin) * projection.lonScale
    const lonAt = (x: number) => (x / projection.mapW) * span / projection.lonScale + projection.lonMin
    const latAt = (y: number) => projection.latMax - (y / projection.mapH) * (projection.latMax - projection.latMin)
    return {
      lonMin: lonAt(cx0),
      lonMax: lonAt(cx1),
      latMin: latAt(cy1),
      latMax: latAt(cy0),
    }
  }, [projection, currentScale, viewportW, viewportH])

  // ------------------------------------------------------------------------
  // EARLY RETURNS — safe because every hook above has been called. Every
  // branch must carry `ref={setContainerRef}` so the observer migrates.
  // ------------------------------------------------------------------------
  // Phase 04.1 debug 04.1-bug-pan-reset fix: do NOT unmount the Stage just
  // because the query is in pending state — when cacheVersion bumps (slider
  // re-render), the queryKey changes and metaQ.isPending flips to true even
  // though placeholderData carries the prior data. The data-guard below
  // (`!metaQ.data`) handles the genuine "no data" case. Keeping this branch
  // would still unmount Stage and clobber x/y/scale (default Konva Stage is
  // 0,0,1 = top-left corner — exactly the reported sympton).
  if (metaQ.isPending && !effectiveMeta) {
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
    !effectiveMeta ||
    !projection ||
    !effectiveTerritories ||
    !effectiveCondadoColors ||
    !effectiveBaronies ||
    !effectiveBaronyColors
  ) {
    return (
      <div ref={setContainerRef} style={{ width: '100%', height: '100%', padding: 24 }}>
        Loading map…
      </div>
    )
  }

  // UI-SPEC §StageViewToggle: hide territory/barony/decoration layers when
  // displaying an intermediate stage raster (non-final stage views show a
  // raw colorized raster in BackgroundLayer; overlaying vector data would
  // be misleading).
  const isStageOverlay = stageView !== 'render-final'

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
        // Phase 08.3 (UAT fix): disable Stage pan while the pen tool is active, otherwise
        // the Stage drag swallows the pointer and PenDrawLayer never receives mousedown.
        draggable={activeTool !== 'P'}
        dragBoundFunc={dragBound}
        onWheel={handleWheel}
        onClick={handleStageClick}
        onTap={handleStageClick}
      >
        {/* BackgroundLayer always shows the raster — either visual_condado.png
            (render-final) or /stage/{name}.png (intermediate stage view). */}
        <BackgroundLayer
          src={stageRasterUrl}
          mapW={projection.mapW}
          mapH={projection.mapH}
          visible={layerVisibility.condados}
        />
        <TerritoryLayer
          territories={effectiveTerritories}
          condadoColors={effectiveCondadoColors}
          visible={!isStageOverlay && layerVisibility.condados}
          showBorders={layerVisibility.borders}
          onHoverEnter={handleHoverEnter}
          onHoverLeave={handleHoverLeave}
        />
        <BaronyLayer
          baronies={effectiveBaronies}
          baronyColors={effectiveBaronyColors}
          visible={!isStageOverlay && layerVisibility.baronies}
        />
        <DecorationsLayer
          condados={effectiveMeta.condados}
          condadoColors={effectiveCondadoColors}
          layerVisibility={{
            capitals: !isStageOverlay && layerVisibility.capitals,
            labels: !isStageOverlay && layerVisibility.labels,
          }}
          currentScale={currentScale}
          minScale={minScale}
          isEditMode={false}
        />
        <InteractionLayer territories={effectiveTerritories} />
        {/* Phase 08 Plan 05: 6th Konva layer (z=5) — VertexEditLayer with viewport-culled handles.
            Plan 14 (GAP-B): projectId/branchId/tier='barony' wired so split/merge/translate
            no longer early-return.
            Plan 16 (LANDMASK-01/02): editableLayer + landmaskCoords + onLandmaskCoordsChange
            plumbed so cyan handles render and Apply/auto-immediate reach the backend.

            Phase 08.1 (BEZ-UAT-01): z=5 mutual exclusion (UI-SPEC §Konva Layer Stack).
            When a barony is selected on the baronies layer, the raw-vertex VertexEditLayer
            is REPLACED by BezierEditLayer so the designer never sees ~100 raw dots — only
            ~4 Bézier anchors. In landmask mode (or no barony selected) VertexEditLayer mounts
            as before. Exactly ONE of the two is mounted at z=5 — never both (double handlers),
            never neither (feature unreachable): the T-08.1-04-01 mitigation. */}
        {/* Phase 08.3 (UAT fix): while the pen tool is active, mount NEITHER edit layer.
            Without this guard the ternary falls through to VertexEditLayer, dumping hundreds
            of raw vertex handles over the map the moment a barony is selected in pen mode. */}
        {activeTool === 'P' ? null : bezierActive ? (
          <BezierEditLayer projection={projection} currentScale={currentScale} />
        ) : (
          <VertexEditLayer
            stageRef={stageRef}
            viewport={vertexViewport}
            tier="barony"
            projectId={projectId}
            branchId={activeBranchId ?? undefined}
            editableLayer={editableLayer}
            landmaskCoords={landmaskRing}
            onLandmaskCoordsChange={handleLandmaskCoordsChange}
          />
        )}
        {/* Phase 08.3 Plan 08 (user request): pending create/carve ring overlay.
            Plan 11: when activeTool!=='P' and a pending ring exists, mount the interactive
            PenShapeManipulateLayer so the user can drag the shape and edit vertices pre-Apply.
            The interactive layer SUPERSEDES the static ghost (never both rendered — FACT 5).
            Static ghost is the at-rest fallback only when PenShapeManipulateLayer is not active
            (e.g. if activeTool==='P' while a ring is pending from a prior close — edge case).
            Both are gated on pendingSelectName (set by onCreated, cleared by resolveAutoSelect). */}
        {pendingSelectName && projection && activeTool !== 'P' && (
          <PenShapeManipulateLayer
            projection={projection}
            currentScale={currentScale}
          />
        )}
        {pendingSelectName && activeTool === 'P' && (() => {
          // Static ghost fallback: pen tool still active (edge case — should not normally occur
          // since PenDrawLayer calls selectTool('V') on close, but kept for robustness).
          const lastOpWithRing = [...editLog].reverse().find((op) => op.ring && op.ring.length >= 3)
          if (!lastOpWithRing?.ring || !projection) return null
          const pts: number[] = []
          for (const p of lastOpWithRing.ring) {
            const [x, y] = geoToCanvas(p.lon, p.lat, projection)
            pts.push(x, y)
          }
          return (
            <Layer listening={false}>
              <Line
                points={pts}
                closed
                fill="rgba(34, 197, 94, 0.12)"
                stroke="#22c55e"
                strokeWidth={2 / currentScale}
                dash={[8 / currentScale, 4 / currentScale]}
                opacity={0.8}
                listening={false}
                data-testid="pen-ghost-overlay"
              />
            </Layer>
          )
        })()}
        {/* Phase 08.3 Plan 05: PenDrawLayer at z=6 — mounted ONLY when activeTool==='P'.
            Mutually exclusive with BezierEditLayer's active editing state: after path close,
            activeTool returns to 'V' and PenDrawLayer unmounts → BezierEditLayer activates (D-04).
            They are never mounted simultaneously.
            Plan 08: onHandlersReady + onCreated wired for action-bar (D-21) + auto-select (D-19). */}
        {activeTool === 'P' && (
          <PenDrawLayer
            projection={projection}
            currentScale={currentScale}
            neighborCandidates={effectiveBaronies ?? []}
            onPathClosed={() => { /* ring committed inside PenDrawLayer */ }}
            onDrawingStateChange={handlePenDrawingChange}
            projectId={projectId}
            branchId={activeBranchId}
            onHandlersReady={handlePenHandlersReady}
            onCreated={handlePenCreated}
            onParentCondadoChange={handleParentCondadoChange}
            pickedCondado={pickedCondado}
          />
        )}
      </Stage>
      {/* Plan 16 (LANDMASK-01/02): onApplyLandmask wired with real coord-carrying callback.
          Manual Apply POSTs latestLandmaskRef.current (seeded from query ring, updated on drag). */}
      <LayerTogglePanel
        projectId={projectId}
        branchId={activeBranchId ?? undefined}
        onApplyLandmask={handleApplyLandmask}
      />
      <LegendCard />
      <FitToViewButton onFit={fitToView} />
      <HoverTooltip name={hover.name} x={hover.x} y={hover.y} />
      {/* Phase 08 Plan 12 (GAP-A): SelectionBridge wires barony selection →
          useEditorStore.activeTerritoryId + vertices. Returns null (effect only). */}
      <SelectionBridge baronies={effectiveBaronies} />
      {/* Phase 08 Plan 05: CoordTooltip DOM overlay for vertex drag (D-33) */}
      <CoordTooltip
        lat={coordTooltip.lat}
        lon={coordTooltip.lon}
        cursorX={coordTooltip.cursorX}
        cursorY={coordTooltip.cursorY}
        visible={coordTooltip.visible}
      />
      {previewPrior && (
        <div
          data-testid="preview-prior-badge"
          style={{
            position: 'absolute',
            top: 12,
            left: 12,
            padding: '4px 10px',
            background: 'var(--gray-12)',
            color: 'var(--gray-1)',
            borderRadius: 6,
            fontSize: 12,
            fontWeight: 500,
            zIndex: 30,
            pointerEvents: 'none',
          }}
        >
          Anterior
        </div>
      )}
      {/* Phase 08.3 Plan 08 (D-21): on-canvas action bar — visible while Pen tool is active.
          DOM overlay (absolute-positioned) so buttons are real DOM elements Playwright can click.
          HOST DECISION: PenDrawLayer returns <Layer>…</Layer>; react-konva rejects DOM children.
          Buttons call PenDrawLayer handlers via the penHandlersRef registered by onHandlersReady. */}
      {activeTool === 'P' && (
        <div
          data-testid="pen-action-bar"
          style={{
            position: 'absolute',
            top: 12,
            right: 12,
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
            zIndex: 20,
            pointerEvents: 'auto',
          }}
        >
          {/* Phase 08.3 Plan 09 (D-26): CondadoPicker — DOM overlay, keyed on activeTool==='P'.
              De-dupe effectiveTerritories by id (MultiPolygon condados emit multiple TerritoryRender rows).
              parentCondadoIdx defaults to -1 when no enclosing barony found yet (cursor over ocean). */}
          {(() => {
            const seenIds = new Set<string>()
            const condadoList: CondadoPickerCondado[] = []
            for (const t of (effectiveTerritories ?? [])) {
              if (!seenIds.has(t.id) && t.idx !== undefined) {
                seenIds.add(t.id)
                condadoList.push({
                  id: t.id,
                  name: t.name,
                  idx: t.idx,
                  duchy_id: t.duchy_id,
                  kingdom_id: t.kingdom_id,
                })
              }
            }
            return (
              <CondadoPicker
                condados={condadoList}
                value={pickedCondado?.condado_idx ?? null}
                parentCondadoIdx={parentCondadoIdx ?? 0}
                onChange={setPickedCondado}
              />
            )
          })()}
          {/* Freehand mode toggle */}
          <button
            data-testid="pen-freehand-toggle"
            onClick={handleFreehandToggle}
            style={{
              padding: '4px 10px',
              background: freehandActive ? 'var(--accent-9)' : 'var(--gray-4)',
              color: freehandActive ? 'var(--accent-1)' : 'var(--gray-12)',
              border: '1px solid var(--gray-6)',
              borderRadius: 4,
              fontSize: 12,
              fontWeight: 500,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            {freehandActive ? 'Modo livre (ativo)' : 'Modo livre (lasso)'}
          </button>
          {/* Fechar contorno */}
          <button
            data-testid="pen-btn-close"
            onClick={() => void penHandlersRef.current?.closePath()}
            style={{
              padding: '4px 10px',
              background: 'var(--gray-4)',
              color: 'var(--gray-12)',
              border: '1px solid var(--gray-6)',
              borderRadius: 4,
              fontSize: 12,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            Fechar contorno
          </button>
          {/* Transformar em baronia */}
          <button
            data-testid="pen-btn-commit"
            onClick={() => void penHandlersRef.current?.closePath()}
            style={{
              padding: '4px 10px',
              background: 'var(--accent-9)',
              color: 'var(--accent-1)',
              border: '1px solid var(--accent-7)',
              borderRadius: 4,
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            Transformar em baronia
          </button>
          {/* Cancelar */}
          <button
            data-testid="pen-btn-cancel"
            onClick={() => { penHandlersRef.current?.cancelPath(); setPickedCondado(null) }}
            style={{
              padding: '4px 10px',
              background: 'var(--gray-4)',
              color: 'var(--red-11)',
              border: '1px solid var(--red-7)',
              borderRadius: 4,
              fontSize: 12,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            Cancelar
          </button>
          {/* Desfazer último ponto */}
          <button
            data-testid="pen-btn-undo"
            onClick={() => penHandlersRef.current?.removeLastAnchor()}
            style={{
              padding: '4px 10px',
              background: 'var(--gray-4)',
              color: 'var(--gray-12)',
              border: '1px solid var(--gray-6)',
              borderRadius: 4,
              fontSize: 12,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            Desfazer último ponto
          </button>
        </div>
      )}
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
              metadata={effectiveMeta}
              territories={effectiveTerritories}
              baronies={effectiveBaronies}
              project={{
                id: project.id,
                name: project.name,
                country_qid: project.country_qid,
                period_start: project.period_start,
                period_end: project.period_end,
                status: project.status,
              }}
            />
          </aside>
        )}
      </div>
    </ProjectionProvider>
  )
}
