/**
 * PenDrawLayer — Konva Layer at z=6 for Photoshop-style pen-tool barony authoring.
 * Phase 08.3 Plan 05.
 *
 * Implements the UI-SPEC §Interaction Contract state machine:
 *   IDLE → DRAWING_FIRST_ANCHOR → DRAWING → CLOSING_RING → CLOSED
 *
 * ALL draw state is component-local (anchors, cursorPos, altDragging, extendMode).
 * NO useEditorStore fields for in-progress draw (mirrors BezierEditLayer pattern).
 *
 * On CREATE close (valid ≥3 anchors, no self-intersection, area ≥ threshold):
 *   1. flattenPenPath(anchors) → ring
 *   2. Infer hierarchy from snap-neighbor barony properties (Plan 02 fields)
 *   3. GET /editor/country?lat=&lon= with ring centroid (Plan 04)
 *   4. setVerticesAndLog(vertices, {op:'create', ts, ring, allocated_original_idx:null, barony_meta})
 *   5. POST /editor/apply → patch editLog[-1].allocated_original_idx (mirrors split 277-289)
 *   6. selectTool('V') → PenDrawLayer unmounts → BezierEditLayer activates (D-04)
 *
 * On EXTEND close (first anchor snapped to existing contour):
 *   - Graft arc into target barony via standard op:'move'/'add' ops
 *   - NO op:'create' emitted
 *
 * D-17 validation: ≥3 anchors, no self-intersection, area ≥ threshold, EXTEND ends snapped.
 * D-12: mid-draw Ctrl+Z removes last anchor from local state only (never zundo).
 * D-03: Esc discards entire path, calls onDrawingStateChange(false).
 * D-16: snap radius 12 screen-px (zoom-aware), both vertex and edge.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react'
import type Konva from 'konva'
import { Layer, Group, Line, Circle, Rect, Text } from 'react-konva'
import { useEditorStore } from '../../stores/useEditorStore'
import { resolvePenSnap } from '../../lib/snap'
import type { SnapCandidate, SnapEdge } from '../../lib/snap'
import { flattenPenPath, flattenPenPathOpen, sampleAndSimplifyFreehand } from '../../lib/penFlatten'
import type { PenAnchor } from '../../lib/penFlatten'
import { geoToCanvas, canvasToGeo } from '../../lib/projection'
import type { ProjectionConfig } from '../../lib/projection'

// ── Color constants (UI-SPEC §Color table — pen draw layer) ──────────────────
const ANCHOR_STRAIGHT_FILL = '#4a9eff'   // blue — straight anchor Rect
const ANCHOR_CURVE_FILL = '#4a9eff'      // blue — curve anchor Circle
const FIRST_ANCHOR_STROKE = '#f0c040'    // amber — first anchor closeable highlight
const RUBBER_BAND_STROKE = '#f0c040'     // amber — rubber-band line (pending segment to cursor)
const CURVE_STROKE = '#22c55e'           // green — live committed-path curve (matches Bézier outline)
const HANDLE_FILL = '#e879f9'            // magenta — cp1/cp2 handle circles
const TETHER_STROKE = '#94a3b8'          // slate-gray — handle tether lines
const SNAP_VERTEX_STROKE = '#eab308'     // yellow — snap vertex marker
const SNAP_EDGE_STROKE = '#eab308'       // yellow — snap edge highlight
const VALIDATION_FILL = 'rgba(239,68,68,0.20)'  // red fill — invalid ring
const VALIDATION_STROKE = '#ef4444'      // red stroke — invalid ring
const STATUS_FILL = '#f0c040'            // amber — status hint text

// ── D-16 snap radius for pen tool ────────────────────────────────────────────
const PEN_SNAP_PX = 12  // screen-px snap radius for pen tool

// Double-click-to-close (user request 2026-05-31). Detected manually at mousedown:
// a second click within DBLCLICK_MS and within DBLCLICK_NEAR_PX (screen-px) of the
// previous click closes the contour on the points placed so far — the second click
// is NOT added as an anchor. This avoids the spurious-anchor / ring self-intersection
// that a Konva onDblClick handler hits (the dbl's own clicks corrupt the ring).
const DBLCLICK_MS = 600  // max ms between the two clicks (OS double-click speed is ~500ms; be forgiving)
const DBLCLICK_NEAR_PX = 16  // screen-px between the two clicks of a double-click

// ── D-17 area threshold ───────────────────────────────────────────────────────
const MIN_AREA_PX2 = 200  // minimum enclosed area in canvas-px (shoelace)

// ── Types ─────────────────────────────────────────────────────────────────────

interface SnapVertexResult { lat: number; lon: number; id: string }
interface SnapEdgeResultLocal { lat: number; lon: number; edgeEndpointIds: [string, string] }

/** GeoJSON Feature shape — from baronies.geojson raw or converted from BaronyRender. */
export interface BaronyFeatureForSnap {
  type: 'Feature'
  properties: {
    id: string
    name: string
    condado_idx?: number
    duchy_id?: string
    kingdom_id?: string
    condado_id?: string
    centroid?: [number, number]
  }
  geometry: {
    type: 'Polygon'
    coordinates: number[][][]
  }
}

/**
 * BaronyRender shape (from useCanvasArtifacts) — accepted as neighborCandidates
 * so CanvasViewer can pass effectiveBaronies directly without conversion.
 * Contains geoRing?: [number, number][] for polygon snap candidate building.
 */
export interface BaronyRenderForSnap {
  id: string
  name: string
  condado_id?: string
  condado_idx?: number
  duchy_id?: string
  kingdom_id?: string
  centroid?: [number, number]
  geoRing?: [number, number][]
  // Phase 08.3 Plan 07: raster index for carve parent_id resolution
  barony_idx?: number
}

/** Union of the two accepted neighbor-candidate shapes. */
export type AnyBaronyCandidate = BaronyFeatureForSnap | BaronyRenderForSnap

export interface PenDrawLayerProps {
  projection: ProjectionConfig
  currentScale: number
  /** Barony features from baroniesQ.data — used for snap candidates + hierarchy inherit.
   *  Accepts either BaronyFeatureForSnap (GeoJSON) or BaronyRenderForSnap (BaronyRender). */
  neighborCandidates: AnyBaronyCandidate[]
  /** Called when the path is successfully closed with a valid ring. */
  onPathClosed?: (ring: PenAnchor[]) => void
  /** Called when isDrawing state changes (WorkspaceToolbar uses to derive disabledTools). */
  onDrawingStateChange?: (isDrawing: boolean) => void
  /** Project id for POST /editor/apply */
  projectId?: string
  /** Branch id for POST /editor/apply */
  branchId?: string | null
  /**
   * Phase 08.3 Plan 08 (D-19): called after commitCreate resolves with the name
   * generated for the new barony (Baronato-${Date.now()}). CanvasViewer uses this
   * to set pendingSelectName for the post-refetch auto-select watcher.
   * Fires BEFORE selectTool('V') so CanvasViewer's state is set before PenDrawLayer unmounts.
   */
  onCreated?: (name: string) => void
  /**
   * Phase 08.3 Plan 08 (D-21): callback registration for the DOM action-bar buttons.
   * CanvasViewer calls this once PenDrawLayer mounts so the action-bar DOM buttons can
   * call closePath, cancelPath, removeLastAnchor, and setFreehandMode directly.
   * The handlers live in PenDrawLayer (Konva-land); the buttons live in CanvasViewer (DOM-land).
   */
  onHandlersReady?: (handlers: PenDrawHandlers) => void
}

/** Handlers exposed to CanvasViewer's DOM action-bar (D-21). */
export interface PenDrawHandlers {
  closePath: () => Promise<boolean>
  cancelPath: () => void
  removeLastAnchor: () => void
  setFreehandMode: (active: boolean) => void
  getFreehandMode: () => boolean
}

// ── Self-intersection check (inline cross-product) ────────────────────────────

function segmentsIntersect(
  p1x: number, p1y: number, p2x: number, p2y: number,
  p3x: number, p3y: number, p4x: number, p4y: number,
): boolean {
  const d1x = p2x - p1x, d1y = p2y - p1y
  const d2x = p4x - p3x, d2y = p4y - p3y
  const cross = d1x * d2y - d1y * d2x
  if (Math.abs(cross) < 1e-10) return false // parallel
  const dx = p3x - p1x, dy = p3y - p1y
  const t = (dx * d2y - dy * d2x) / cross
  const u = (dx * d1y - dy * d1x) / cross
  return t > 1e-8 && t < 1 - 1e-8 && u > 1e-8 && u < 1 - 1e-8
}

function hasSelfIntersection(pts: Array<{ x: number; y: number }>): boolean {
  const n = pts.length
  for (let i = 0; i < n; i++) {
    for (let j = i + 2; j < n; j++) {
      if (i === 0 && j === n - 1) continue // adjacent edge (close)
      const a = pts[i], b = pts[(i + 1) % n]
      const c = pts[j], d = pts[(j + 1) % n]
      if (segmentsIntersect(a.x, a.y, b.x, b.y, c.x, c.y, d.x, d.y)) return true
    }
  }
  return false
}

// ── Shoelace area (canvas px) ─────────────────────────────────────────────────

function ringAreaPx2(pts: Array<{ x: number; y: number }>): number {
  const n = pts.length
  if (n < 3) return 0
  let area = 0
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n
    area += pts[i].x * pts[j].y - pts[j].x * pts[i].y
  }
  return Math.abs(area) / 2
}

// ── Point-in-polygon (ray-casting) for carve interior-loop detection ─────────
// Works in geo (lon/lat) space. Ring is [lon, lat][] (exterior only).
// Returns true if (lon, lat) lies strictly inside the ring.

function pointInRing(lon: number, lat: number, ring: number[][]): boolean {
  const n = ring.length
  if (n < 3) return false
  let inside = false
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const xi = ring[i]?.[0] ?? 0, yi = ring[i]?.[1] ?? 0
    const xj = ring[j]?.[0] ?? 0, yj = ring[j]?.[1] ?? 0
    const intersect =
      yi > lat !== yj > lat &&
      lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi
    if (intersect) inside = !inside
  }
  return inside
}

// ── Normalize candidate to a common shape for snap building ──────────────────

interface NormalizedCandidate {
  id: string
  ring: number[][] | undefined  // [lon, lat][] coords
  condado_idx?: number
  duchy_id?: string
  kingdom_id?: string
  // Phase 08.3 Plan 07: raster index for carve parent_id (backend compute() int index)
  barony_idx?: number
}

function normalizeCandidate(c: AnyBaronyCandidate): NormalizedCandidate {
  // BaronyFeatureForSnap (has .type === 'Feature' + .geometry)
  if ('type' in c && c.type === 'Feature') {
    const f = c as BaronyFeatureForSnap
    return {
      id: f.properties.id,
      ring: f.geometry.type === 'Polygon' ? f.geometry.coordinates[0] : undefined,
      condado_idx: f.properties.condado_idx,
      duchy_id: f.properties.duchy_id,
      kingdom_id: f.properties.kingdom_id,
    }
  }
  // BaronyRenderForSnap (has .id + optional .geoRing)
  const r = c as BaronyRenderForSnap
  return {
    id: r.id,
    ring: r.geoRing,  // [lon, lat][] — same coordinate order
    condado_idx: r.condado_idx,
    duchy_id: r.duchy_id,
    kingdom_id: r.kingdom_id,
    barony_idx: r.barony_idx,
  }
}

// ── Build snap candidates from neighbor features ──────────────────────────────

function buildVertexCandidates(features: AnyBaronyCandidate[]): SnapCandidate[] {
  const out: SnapCandidate[] = []
  for (const f of features) {
    const { id, ring } = normalizeCandidate(f)
    if (!ring) continue
    for (let i = 0; i < ring.length; i++) {
      const pt = ring[i]
      if (!pt) continue
      out.push({ id: `${id}#${i}`, lat: pt[1], lon: pt[0] })
    }
  }
  return out
}

function buildEdgeCandidates(features: AnyBaronyCandidate[]): SnapEdge[] {
  const out: SnapEdge[] = []
  for (const f of features) {
    const { id, ring } = normalizeCandidate(f)
    if (!ring) continue
    for (let i = 0; i < ring.length - 1; i++) {
      const a = ring[i], b = ring[i + 1]
      if (!a || !b) continue
      out.push({
        id1: `${id}#${i}`,
        id2: `${id}#${i + 1}`,
        a: { lat: a[1], lon: a[0] },
        b: { lat: b[1], lon: b[0] },
      })
    }
  }
  return out
}

// ── Component ─────────────────────────────────────────────────────────────────

export const PenDrawLayer: React.FC<PenDrawLayerProps> = ({
  projection,
  currentScale,
  neighborCandidates,
  onPathClosed,
  onDrawingStateChange,
  projectId,
  branchId,
  onCreated,
  onHandlersReady,
}) => {
  const safeScale = currentScale > 0 ? currentScale : 1

  // Screen-space sizes (08.1-07 pattern: BASE/safeScale)
  const ANCHOR_BASE = 10
  const anchorSize = ANCHOR_BASE / safeScale
  const anchorHalf = anchorSize / 2
  const handleRadius = 4 / safeScale
  const snapRadius = 8 / safeScale
  const curveWidth = 2 / safeScale
  const textSize = 11 / safeScale

  // ── Component-local draw state (NEVER in store) ───────────────────────────
  const [anchors, setAnchors] = useState<PenAnchor[]>([])
  const [cursorPos, setCursorPos] = useState<{ x: number; y: number } | null>(null)
  const [extendMode, setExtendMode] = useState(false)
  const [extendBaronyId, setExtendBaronyId] = useState<string | null>(null)

  // ── Freehand (lasso) mode state (D-20) ───────────────────────────────────
  // When freehandMode is on, a mouse-press+drag+release accumulates raw geo points
  // that are simplified via sampleAndSimplifyFreehand and fed into commitCreate
  // (the SAME carve detection path as the click-pen — no duplication).
  const [freehandMode, setFreehandMode] = useState(false)
  const freehandPointsRef = useRef<Array<{ lat: number; lon: number }>>([])
  const isFreehandDraggingRef = useRef(false)
  // Live freehand preview points in canvas-px for rendering (updated on every mousemove)
  const [freehandPreviewPts, setFreehandPreviewPts] = useState<number[]>([])
  // Timestamp of last mousemove throttle (16ms / ~3px cadence)
  const lastFreehandMoveRef = useRef<number>(0)
  // firstAnchorSnap stored for EXTEND-mode detection; value not rendered directly
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_firstAnchorSnap, setFirstAnchorSnap] = useState<SnapVertexResult | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [snapVertexMarker, setSnapVertexMarker] = useState<{ x: number; y: number } | null>(null)
  const [snapEdgeMarker, setSnapEdgeMarker] = useState<{ x1: number; y1: number; x2: number; y2: number } | null>(null)
  // Live tangent preview while dragging out a curve anchor's handles (PEN-CURVE-01).
  // curveAnchor carries the in-progress anchor in GEO space so the live green curve can
  // include the bend toward this not-yet-committed anchor (Photoshop-style preview).
  const [dragPreview, setDragPreview] = useState<{
    anchor: [number, number]
    cp1: [number, number]
    cp2: [number, number]
    curveAnchor: PenAnchor
  } | null>(null)

  const anchorsRef = useRef<PenAnchor[]>([])
  anchorsRef.current = anchors

  // Double-click-to-close detection (manual): timestamp + map-px position of the
  // last anchor-placing click, so the next rapid+nearby click closes instead of
  // placing a spurious anchor.
  const lastClickAtRef = useRef<number | null>(null)
  const lastClickPosRef = useRef<{ x: number; y: number } | null>(null)

  const altRef = useRef(false)
  const extendModeRef = useRef(false)
  extendModeRef.current = extendMode
  const extendBaronyIdRef = useRef<string | null>(null)
  extendBaronyIdRef.current = extendBaronyId

  // ── Photoshop pen gesture state (press → optional drag → release) ─────────
  // A release with < DRAG_THRESHOLD_PX of movement = straight (corner) anchor;
  // a press-drag-release = curve (smooth) anchor whose tangent follows the drag.
  const isPointerDownRef = useRef(false)
  const pendingAnchorRef = useRef<{ lat: number; lon: number } | null>(null)
  const dragStartedRef = useRef(false)
  const pendingCloseRef = useRef(false)
  const DRAG_THRESHOLD_PX = 4

  const isDrawing = anchors.length > 0 || isFreehandDraggingRef.current

  // Notify parent on isDrawing changes
  useEffect(() => {
    onDrawingStateChange?.(anchors.length > 0)
  }, [anchors.length, onDrawingStateChange])

  // ── Alt key tracking ──────────────────────────────────────────────────────
  useEffect(() => {
    const down = (e: KeyboardEvent) => { if (e.altKey) altRef.current = true }
    const up = (e: KeyboardEvent) => { if (!e.altKey) altRef.current = false }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up) }
  }, [])

  // ── Remove last placed anchor (component-local only, never zundo) ─────────
  // Shared by Ctrl+Z mid-draw (D-12) and right-click (user request 2026-05-31).
  const removeLastAnchor = useCallback(() => {
    setValidationError(null)
    setAnchors((prev) => {
      const next = prev.slice(0, -1)
      if (next.length === 0) {
        setExtendMode(false)
        setExtendBaronyId(null)
        setFirstAnchorSnap(null)
      }
      return next
    })
  }, [])

  // ── Keyboard shortcuts (Ctrl+Z mid-draw, Esc) ─────────────────────────────
  // cancelPath is declared below (after closePath which it shares logic with);
  // we use a stable ref here so the keyboard handler always calls the fresh version.
  const cancelPathRef = useRef<(() => void) | null>(null)
  useEffect(() => {
    if (!isDrawing) return
    const handler = (e: KeyboardEvent) => {
      // Esc → discard path (routes through shared cancelPath via ref)
      if (e.key === 'Escape') {
        e.stopPropagation()
        cancelPathRef.current?.()
        return
      }
      // Ctrl+Z mid-draw → remove last anchor (component-local ONLY, no zundo)
      if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        e.stopPropagation()
        e.preventDefault()
        removeLastAnchor()
      }
    }
    window.addEventListener('keydown', handler, true) // capture phase — runs before global shortcuts
    return () => window.removeEventListener('keydown', handler, true)
  }, [isDrawing, removeLastAnchor])

  // ── Register handlers with CanvasViewer for DOM action-bar buttons (D-21) ──
  // cancelPath, closePath, removeLastAnchor are all stable useCallback refs.
  // freehandMode is a state value; use a getter ref so the action bar always
  // reads the live value (avoids stale closure in the DOM button onClick).
  // NOTE: closePathRef is initialized without a value here (closePath is declared
  // below via useCallback) and updated after closePath is in scope.
  const closePathRef = useRef<(() => Promise<boolean>) | null>(null)
  const removeLastAnchorRef2 = useRef<(() => void) | null>(null)
  const freehandModeStateRef = useRef(freehandMode)
  freehandModeStateRef.current = freehandMode

  useEffect(() => {
    if (!onHandlersReady) return
    onHandlersReady({
      closePath: () => closePathRef.current?.() ?? Promise.resolve(false),
      cancelPath: () => cancelPathRef.current?.(),
      removeLastAnchor: () => removeLastAnchorRef2.current?.(),
      setFreehandMode: (active: boolean) => setFreehandMode(active),
      getFreehandMode: () => freehandModeStateRef.current,
    })
  // Register once on mount; refs always hold the latest values.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onHandlersReady])

  // ── Build snap candidates ─────────────────────────────────────────────────
  const vertexCandidates = buildVertexCandidates(neighborCandidates)
  const edgeCandidates = buildEdgeCandidates(neighborCandidates)

  // ── Snap resolution (used on anchor drop) ────────────────────────────────
  const resolveSnap = useCallback(
    (worldPt: { lat: number; lon: number }): { lat: number; lon: number; snapVertex?: SnapVertexResult; snapEdge?: SnapEdgeResultLocal } => {
      // 08.3-07 UAT fix: snap runs in MAP-PIXEL space (resolvePenSnap). Feeding the
      // euclidean snap primitives lat/lon degrees made the 12-screen-px radius behave
      // like ~12 degrees (the whole peninsula) — every interior click snapped to the
      // parent's border and the close gesture never reached the first anchor.
      return resolvePenSnap(worldPt, vertexCandidates, edgeCandidates, projection, safeScale, altRef.current, PEN_SNAP_PX)
    },
    [vertexCandidates, edgeCandidates, projection, safeScale],
  )

  // ── Canvas coordinate helper ──────────────────────────────────────────────
  // Accepts both KonvaEventObject (real) and React.MouseEvent (jsdom/test mock).
  const eventToWorld = useCallback(
    (e: Konva.KonvaEventObject<MouseEvent>): { lat: number; lon: number } | null => {
      // Phase 08.3 (UAT fix): canvasToGeo expects MAP-SPACE pixels (0..mapW, 0..mapH), not
      // screen coords. getRelativePointerPosition() returns the pointer already mapped through
      // the Stage transform (pan + zoom) into layer/map space — the same space BezierEditLayer
      // uses (08.1-07 G7 fix). Using raw evt.clientX/Y here put anchors in the wrong place.
      const stage = (() => {
        try {
          return (e.target?.getStage?.() ?? null) as Konva.Stage | null
        } catch {
          return null
        }
      })()
      const rel = stage?.getRelativePointerPosition?.()
      if (rel) {
        const [lon, lat] = canvasToGeo(rel.x, rel.y, projection)
        return { lat, lon }
      }
      // jsdom/unit-test fallback: Konva mock has no Stage; React.MouseEvent carries clientX/Y,
      // which the tests pre-map into map space.
      const raw = e as unknown as { evt?: MouseEvent; clientX?: number; clientY?: number }
      const clientX = raw.evt?.clientX ?? raw.clientX ?? 0
      const clientY = raw.evt?.clientY ?? raw.clientY ?? 0
      const [lon, lat] = canvasToGeo(clientX, clientY, projection)
      return { lat, lon }
    },
    [projection],
  )

  // ── Mouse move — update cursor pos + snap markers ─────────────────────────
  const handleMouseMove = useCallback(
    (e: Konva.KonvaEventObject<MouseEvent>) => {
      const world = eventToWorld(e)
      if (!world) return

      // Freehand drag: accumulate points while mouse button is held (D-20).
      // eventToWorld uses getRelativePointerPosition (map-space) — NEVER clientX/Y.
      if (freehandMode && isFreehandDraggingRef.current) {
        const now = typeof performance !== 'undefined' ? performance.now() : Date.now()
        const [cx, cy] = geoToCanvas(world.lon, world.lat, projection)
        const pts = freehandPointsRef.current
        // Throttle: skip if < 16ms since last sample OR < 3px from last point
        if (now - lastFreehandMoveRef.current >= 16) {
          const last = pts[pts.length - 1]
          if (!last) {
            pts.push(world)
            lastFreehandMoveRef.current = now
          } else {
            const [lx, ly] = geoToCanvas(last.lon, last.lat, projection)
            if (Math.hypot(cx - lx, cy - ly) >= 3) {
              pts.push(world)
              lastFreehandMoveRef.current = now
              // Update live preview polyline (canvas-px flat array)
              const preview: number[] = []
              for (const p of pts) {
                const [px, py] = geoToCanvas(p.lon, p.lat, projection)
                preview.push(px, py)
              }
              setFreehandPreviewPts(preview)
            }
          }
        }
        setCursorPos({ x: cx, y: cy })
        return
      }

      // Dragging out a curve anchor's tangent handles (Photoshop pen, PEN-CURVE-01).
      if (isPointerDownRef.current && pendingAnchorRef.current) {
        const pa = pendingAnchorRef.current
        const [ax, ay] = geoToCanvas(pa.lon, pa.lat, projection)
        const [dx, dy] = geoToCanvas(world.lon, world.lat, projection)
        const screenDist = Math.hypot(dx - ax, dy - ay) * safeScale
        if (screenDist > DRAG_THRESHOLD_PX) {
          dragStartedRef.current = true
          const dLat = world.lat - pa.lat
          const dLon = world.lon - pa.lon
          const cp1 = geoToCanvas(pa.lon + dLon, pa.lat + dLat, projection) // outgoing
          const cp2 = geoToCanvas(pa.lon - dLon, pa.lat - dLat, projection) // mirror (incoming)
          // In-progress anchor in geo space — fed to flattenPenPathOpen so the green curve
          // shows the incoming bend toward this anchor LIVE, before mouse-up (Photoshop preview).
          const curveAnchor: PenAnchor = {
            lat: pa.lat,
            lon: pa.lon,
            type: 'curve',
            cp1: { lat: pa.lat + dLat, lon: pa.lon + dLon },
            cp2: { lat: pa.lat - dLat, lon: pa.lon - dLon },
          }
          setDragPreview({ anchor: [ax, ay], cp1, cp2, curveAnchor })
          setCursorPos({ x: dx, y: dy })
        }
        return
      }

      const [cx, cy] = geoToCanvas(world.lon, world.lat, projection)
      setCursorPos({ x: cx, y: cy })

      // Show snap markers on hover (08.3-07 UAT fix: resolve in map-pixel space so the
      // 12-screen-px radius is honored — hover markers now match anchor-drop snapping).
      const snap = resolvePenSnap(world, vertexCandidates, edgeCandidates, projection, safeScale, altRef.current, PEN_SNAP_PX)
      if (snap.snapVertex) {
        const [sx, sy] = geoToCanvas(snap.snapVertex.lon, snap.snapVertex.lat, projection)
        setSnapVertexMarker({ x: sx, y: sy })
        setSnapEdgeMarker(null)
      } else if (snap.snapEdge) {
        setSnapVertexMarker(null)
        const [ax, ay] = geoToCanvas(snap.snapEdge.lon, snap.snapEdge.lat, projection) // nearest edge point
        setSnapEdgeMarker({ x1: ax - 4, y1: ay - 4, x2: ax + 4, y2: ay + 4 })
      } else {
        setSnapVertexMarker(null)
        setSnapEdgeMarker(null)
      }
    },
    [eventToWorld, projection, vertexCandidates, edgeCandidates, safeScale],
  )

  // ── Commit CREATE or CARVE op (internal) ─────────────────────────────────
  // Carve detection (D-19 note): if ring centroid falls INSIDE an existing
  // barony's exterior ring, this is an enclave CARVE (N = drawn∩parent, parent'
  // = parent−N) NOT a plain CREATE. The parent's condado_idx is used as default
  // (D-26 default-to-parent assignment). Plan 08.3-07 scope.
  const commitCreate = useCallback(
    async (closedAnchors: PenAnchor[], neighborBaronyId: string | null) => {
      const ring = flattenPenPath(closedAnchors, projection)
      if (ring.length < 3) return

      // Compute centroid of ring for /editor/country + carve detection
      const avgLat = ring.reduce((s, p) => s + p.lat, 0) / ring.length
      const avgLon = ring.reduce((s, p) => s + p.lon, 0) / ring.length

      // ── Carve detection: check if centroid is inside any existing barony ──
      // Uses exterior ring only (normalizeCandidate reads coordinates[0]).
      // Containment test does NOT need interior rings — see D-25 hop disposition (b).
      let containingParent: NormalizedCandidate | null = null
      for (const candidate of neighborCandidates) {
        const n = normalizeCandidate(candidate)
        if (!n.ring || n.ring.length < 3) continue
        if (pointInRing(avgLon, avgLat, n.ring)) {
          containingParent = n
          break
        }
      }
      // DEV probe: expose last commit info for Playwright diagnostics
      if (import.meta.env.DEV) {
        ;(window as unknown as {
          __forgeLastCommit?: { avgLat: number; avgLon: number; isCarve: boolean; parentName: string | null; parentRasterIdx: number | null; ringLen: number }
        }).__forgeLastCommit = {
          avgLat,
          avgLon,
          isCarve: containingParent !== null,
          parentName: containingParent?.id ?? null,
          parentRasterIdx: containingParent?.barony_idx ?? null,
          ringLen: ring.length,
        }
      }

      // Inherit hierarchy from containing parent (carve) or snap-neighbor (create)
      let condado_idx = 0
      let duchy_id = ''
      let kingdom_id = ''
      // parent_id is the raster index (barony_idx from canvas_sidecars.py bi), NOT the name.
      // barony_idx is emitted by canvas_sidecars.py Phase 08.3-07 addition.
      let parentRasterIdx: number | null = null

      if (containingParent) {
        // CARVE: inherit from the parent being carved
        // Use barony_idx (raster index) as parent_id — backend compute() resolves by int index.
        parentRasterIdx = containingParent.barony_idx ?? null
        condado_idx = containingParent.condado_idx ?? 0
        duchy_id = containingParent.duchy_id ?? ''
        kingdom_id = containingParent.kingdom_id ?? ''
      } else if (neighborBaronyId) {
        // CREATE: inherit from snap-neighbor
        const neighbor = neighborCandidates.find((f) => {
          const n = normalizeCandidate(f)
          return n.id === neighborBaronyId
        })
        if (neighbor) {
          const n = normalizeCandidate(neighbor)
          condado_idx = n.condado_idx ?? 0
          duchy_id = n.duchy_id ?? ''
          kingdom_id = n.kingdom_id ?? ''
        }
      }

      // D-08: GET /editor/country for PT/ES inference
      let country: 'PT' | 'ES' = 'PT'
      if (projectId) {
        try {
          const resp = await fetch(
            `/api/v3/projects/${projectId}/editor/country?lat=${avgLat}&lon=${avgLon}`,
          )
          if (resp.ok) {
            const data = (await resp.json()) as { country: 'PT' | 'ES' }
            country = data.country
          }
        } catch {
          // Fall back to 'PT' if fetch fails (best-effort)
        }
      }

      const barony_meta = {
        name: `Baronato-${Date.now()}`,
        condado_idx,
        duchy_id,
        kingdom_id,
        country,
      }

      // Single store write.
      // For CARVE: use op:'carve' + parent_id so the snapshot's edit_log carries the
      // carve op that compute() needs to replay (compute() dispatches on op.op, not op_type).
      // For CREATE: keep op:'create' (unchanged D-13 path).
      const isCarveOp = containingParent !== null && parentRasterIdx !== null
      const currentVertices = useEditorStore.getState().vertices
      useEditorStore.getState().setVerticesAndLog(currentVertices, isCarveOp
        ? {
            op: 'carve',
            ts: Date.now(),
            parent_id: parentRasterIdx,
            ring,
            allocated_original_idx: null,
            barony_meta,
          }
        : {
            op: 'create',
            ts: Date.now(),
            ring,
            allocated_original_idx: null,
            barony_meta,
          }
      )

      // POST /editor/apply with op_type:'carve' or 'create' depending on detection
      if (projectId && branchId) {
        try {
          // isCarve requires both: (a) containingParent found AND (b) barony_idx available.
          // barony_idx is the raster index emitted by canvas_sidecars.py Phase 08.3-07.
          // Without it, fall back to 'create' (old cached baronies.geojson may lack barony_idx).
          const isCarve = containingParent !== null && parentRasterIdx !== null
          const payload = isCarve
            ? {
                parent_id: parentRasterIdx,   // raster int index (not the name string)
                ring,
                barony_meta,
                branch_id: branchId,
              }
            : { ring, barony_meta, branch_id: branchId }

          const resp = await fetch(`/api/v3/projects/${projectId}/editor/apply`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              op_type: isCarve ? 'carve' : 'create',
              payload,
              branch_id: branchId,
            }),
          })
          if (resp.ok) {
            const result = (await resp.json()) as { allocated_original_idx?: number }
            if (result.allocated_original_idx != null) {
              // Patch last editLog entry with allocated idx (mirrors split lines 279-289)
              useEditorStore.setState({
                editLog: [
                  ...useEditorStore.getState().editLog.slice(0, -1),
                  {
                    ...useEditorStore.getState().editLog[
                      useEditorStore.getState().editLog.length - 1
                    ],
                    allocated_original_idx: result.allocated_original_idx,
                  },
                ],
              })
            }
          }
        } catch {
          // Network error — idx stays null; user can retry Apply
        }
      }

      // D-19 (Plan 08): fire onCreated BEFORE selectTool('V') so CanvasViewer captures
      // the pending name while PenDrawLayer is still mounted. selectTool('V') at the
      // next line causes an unmount — onCreated must run first.
      onCreated?.(barony_meta.name)

      // D-04: switch to V tool → PenDrawLayer unmounts → BezierEditLayer activates
      useEditorStore.getState().selectTool('V')
    },
    [projection, neighborCandidates, projectId, branchId, onCreated],
  )

  // ── Commit EXTEND (graft arc into existing barony) ────────────────────────
  const commitExtend = useCallback(
    (closedAnchors: PenAnchor[], _targetBaronyId: string) => {
      // Flatten the drawn arc (excluding first/last anchors which are on the contour)
      const ring = flattenPenPath(closedAnchors, projection)
      if (ring.length < 2) return

      // Standard vertex add/move ops on the existing barony (no new 'create' op)
      // RESEARCH Target 5: choose shorter arc between the two contact points (Assumption A3)
      // Implementation: add the intermediate ring points as new vertices via op:'add'
      const currentVertices = useEditorStore.getState().vertices
      useEditorStore.getState().setVerticesAndLog(currentVertices, {
        op: 'add',
        ts: Date.now(),
        vertexIds: ring.map((_, i) => `extend-${i}`),
      })

      // D-04: return to V tool
      useEditorStore.getState().selectTool('V')
    },
    [projection],
  )

  // ── D-17 validation ───────────────────────────────────────────────────────
  // [Rule 1 fix 08.3-08]: validate() must check pts.length (the explicit set passed in),
  // NOT anchorsRef.current.length. closePath(explicitAnchors) passes the freehand-sampled
  // ring as explicitAnchors; anchorsRef.current stays [] throughout freehand draw (points
  // accumulate in freehandPointsRef, not anchors state). Using anchorsRef here silently
  // rejected every valid freehand close with "Mínimo de 3 pontos".
  const validate = useCallback(
    (pts: Array<{ x: number; y: number }>): string | null => {
      if (pts.length < 3) return 'Mínimo de 3 pontos para fechar o contorno.'
      if (hasSelfIntersection(pts)) return 'O contorno se cruza — ajuste os pontos e tente fechar novamente.'
      if (ringAreaPx2(pts) < MIN_AREA_PX2) return 'Área muito pequena — o baronato seria removido na limpeza. Amplie o contorno.'
      return null
    },
    [],
  )

  // ── Close the current path (validate + commit create/extend) ──────────────
  // Shared by the mouse-up close gesture, the double-click close, and the DEV
  // __forgePenClose hook. `explicitAnchors` lets a caller (double-click) pass a
  // deduped set without waiting for a setAnchors state flush.
  const closePath = useCallback(
    async (explicitAnchors?: PenAnchor[]): Promise<boolean> => {
      const cur = explicitAnchors ?? anchorsRef.current
      const pxPts = cur.map((a) => {
        const [x, y] = geoToCanvas(a.lon, a.lat, projection)
        return { x, y }
      })
      const err = validate(pxPts)
      if (err) {
        setValidationError(err)
        return false
      }
      setValidationError(null)
      const closedAnchors = [...cur]
      setAnchors([])
      setExtendMode(false)
      setFirstAnchorSnap(null)
      setDragPreview(null)

      onPathClosed?.(closedAnchors)

      if (extendModeRef.current && extendBaronyIdRef.current) {
        commitExtend(closedAnchors, extendBaronyIdRef.current)
      } else {
        // Nearest-neighbor barony for hierarchy inherit (first anchor's contour).
        const neighborId = closedAnchors[0]
          ? (() => {
              for (const f of neighborCandidates) {
                const n = normalizeCandidate(f)
                if (!n.ring) continue
                const match = n.ring.some(
                  (pt) =>
                    Array.isArray(pt) &&
                    Math.abs((pt[1] as number) - closedAnchors[0].lat) < 0.01 &&
                    Math.abs((pt[0] as number) - closedAnchors[0].lon) < 0.01,
                )
                if (match) return n.id
              }
              return null
            })()
          : null
        await commitCreate(closedAnchors, neighborId)
      }
      return true
    },
    [projection, validate, onPathClosed, commitExtend, commitCreate, neighborCandidates],
  )

  // Update closePathRef now that closePath is in scope
  closePathRef.current = closePath

  // ── cancelPath: shared by Esc handler AND the "Cancelar" DOM button (D-21) ──
  // Placed AFTER closePath so there is no forward-reference issue.
  // Extracting the Esc body here prevents logic divergence between keyboard and button.
  const cancelPath = useCallback(() => {
    setAnchors([])
    setExtendMode(false)
    setExtendBaronyId(null)
    setFirstAnchorSnap(null)
    setValidationError(null)
    setFreehandPreviewPts([])
    freehandPointsRef.current = []
    isFreehandDraggingRef.current = false
    onDrawingStateChange?.(false)
  }, [onDrawingStateChange])
  // Keep the cancelPathRef up-to-date so the keyboard handler can call the fresh version
  cancelPathRef.current = cancelPath
  // Keep removeLastAnchorRef2 up-to-date for the action-bar "Desfazer último ponto" button
  removeLastAnchorRef2.current = removeLastAnchor

  // ── Pointer-down: begin an anchor (close gesture, or start press/drag) ────
  const handleMouseDown = useCallback(
    (e: Konva.KonvaEventObject<MouseEvent>) => {
      const world = eventToWorld(e)
      if (!world) return

      // Freehand mode: begin accumulating drag samples (D-20).
      // Clear any stale points, record the first sample, set dragging flag.
      if (freehandMode) {
        freehandPointsRef.current = [world]
        isFreehandDraggingRef.current = true
        lastFreehandMoveRef.current = typeof performance !== 'undefined' ? performance.now() : Date.now()
        setFreehandPreviewPts([])
        return
      }

      const cur = anchorsRef.current
      const resolved = resolveSnap(world)
      const [rx, ry] = geoToCanvas(resolved.lon, resolved.lat, projection)

      // Double-click close: a 2nd click within DBLCLICK_MS and DBLCLICK_NEAR_PX of the
      // previous one closes the contour on the points already placed (the 1st click of
      // the dbl was its own anchor). The 2nd click is NOT added — routed through the
      // existing pendingClose path so handleMouseUp does not append it.
      const nowT = typeof performance !== 'undefined' ? performance.now() : Date.now()
      if (
        cur.length >= 3 &&
        lastClickAtRef.current != null &&
        nowT - lastClickAtRef.current <= DBLCLICK_MS &&
        lastClickPosRef.current != null &&
        Math.hypot(rx - lastClickPosRef.current.x, ry - lastClickPosRef.current.y) <= DBLCLICK_NEAR_PX / safeScale
      ) {
        lastClickAtRef.current = null
        pendingCloseRef.current = true
        return
      }
      lastClickAtRef.current = nowT
      lastClickPosRef.current = { x: rx, y: ry }

      // Close gesture: press on/near the first anchor (≥2 anchors placed).
      // fx/fy and cx/cy are MAP-pixels, so the screen-px radius must be divided by
      // safeScale (08.3-07 UAT fix — the raw PEN_SNAP_PX was only correct at scale 1).
      if (cur.length >= 2) {
        const [fx, fy] = geoToCanvas(cur[0].lon, cur[0].lat, projection)
        const [cx, cy] = geoToCanvas(resolved.lon, resolved.lat, projection)
        if (Math.hypot(cx - fx, cy - fy) <= PEN_SNAP_PX / safeScale) {
          pendingCloseRef.current = true
          return
        }
      }
      pendingCloseRef.current = false

      // EXTEND mode: first anchor snapped to an existing barony vertex.
      if (cur.length === 0 && resolved.snapVertex) {
        const snapVtx = resolved.snapVertex as SnapVertexResult
        setExtendMode(true)
        setFirstAnchorSnap(snapVtx)
        setExtendBaronyId(snapVtx.id.split('#')[0] ?? null)
      }

      pendingAnchorRef.current = { lat: resolved.lat, lon: resolved.lon }
      isPointerDownRef.current = true
      dragStartedRef.current = false
    },
    [eventToWorld, resolveSnap, projection, safeScale],
  )

  // ── Pointer-up: commit the pending anchor (straight or curve) or close ────
  const handleMouseUp = useCallback(
    async (e: Konva.KonvaEventObject<MouseEvent>) => {
      // Freehand mode: mouse-up ends the drag. Simplify accumulated points and
      // feed into the EXISTING commitCreate carve detection path (D-20).
      // eventToWorld is used throughout — NEVER clientX/Y (T-08.3-08-04 mitigation).
      if (freehandMode && isFreehandDraggingRef.current) {
        isFreehandDraggingRef.current = false
        setFreehandPreviewPts([])

        // Append the final mouse-up position to ensure the ring touches the release point
        const world = eventToWorld(e)
        if (world) freehandPointsRef.current.push(world)

        const raw = freehandPointsRef.current
        freehandPointsRef.current = []

        const geoRing = sampleAndSimplifyFreehand(raw, projection)
        if (geoRing.length < 3) {
          setValidationError('Mínimo de 3 pontos para fechar o contorno.')
          return
        }

        // Convert simplified geo ring back to PenAnchor[] (straight type, no handles).
        // Drop the closing duplicate (last === first) so closePath does not double-close.
        const ringAnchors: PenAnchor[] = geoRing
          .slice(0, -1) // remove closing point — closePath/flattenPenPath adds it
          .map((p) => ({ lat: p.lat, lon: p.lon, type: 'straight' as const }))

        // Route through the EXISTING closePath/commitCreate carve detection path (08.3-07).
        // closePath(explicitAnchors) bypasses the anchors state (which stays []) and uses
        // the provided ring directly. The carve detection (centroid-in-parent) runs in
        // commitCreate unchanged — no new backend call added here.
        await closePath(ringAnchors)
        return
      }

      // Close gesture queued on the matching mouse-down.
      if (pendingCloseRef.current) {
        pendingCloseRef.current = false
        isPointerDownRef.current = false
        pendingAnchorRef.current = null
        dragStartedRef.current = false
        setDragPreview(null)
        await closePath()
        return
      }

      const pa = pendingAnchorRef.current
      const wasDrag = dragStartedRef.current
      isPointerDownRef.current = false
      pendingAnchorRef.current = null
      dragStartedRef.current = false
      setDragPreview(null)
      if (!pa) return

      const world = eventToWorld(e)
      let newAnchor: PenAnchor
      if (wasDrag && world) {
        // Smooth anchor: outgoing handle (cp1) follows the drag; incoming (cp2) mirrors it.
        const dLat = world.lat - pa.lat
        const dLon = world.lon - pa.lon
        newAnchor = {
          lat: pa.lat,
          lon: pa.lon,
          type: 'curve',
          cp1: { lat: pa.lat + dLat, lon: pa.lon + dLon },
          cp2: { lat: pa.lat - dLat, lon: pa.lon - dLon },
        }
      } else {
        newAnchor = { lat: pa.lat, lon: pa.lon, type: 'straight' }
      }
      setAnchors((prev) => [...prev, newAnchor])
    },
    [eventToWorld, closePath],
  )

  // ── DEV hatch for Playwright (Plan 06) ────────────────────────────────────
  // Expose refs so trigger functions (registered below) can close over live state.
  const commitCreateRef = useRef(commitCreate)
  commitCreateRef.current = commitCreate
  const commitExtendRef = useRef(commitExtend)
  commitExtendRef.current = commitExtend
  const projectionRef = useRef(projection)
  projectionRef.current = projection
  const neighborCandidatesRef = useRef(neighborCandidates)
  neighborCandidatesRef.current = neighborCandidates

  useEffect(() => {
    if (!import.meta.env.DEV) return

    const win = window as unknown as {
      __forgePenState?: () => unknown
      __forgePenPlaceAnchor?: (lat: number, lon: number) => boolean
      __forgePenPlaceCurveAnchor?: (lat: number, lon: number, dLat: number, dLon: number) => boolean
      __forgePenClose?: () => Promise<boolean>
    }

    // Read-only state getter
    win.__forgePenState = () => ({
      anchorCount: anchorsRef.current.length,
      curveAnchorCount: anchorsRef.current.filter((a) => a.type === 'curve').length,
      isDrawing: anchorsRef.current.length > 0,
      extendMode: extendModeRef.current,
      editLogLength: useEditorStore.getState().editLog.length,
      // DEV-only diagnostic: neighbor candidate ring coverage (for carve detection debugging)
      neighborCount: neighborCandidatesRef.current.length,
      ringsPresent: neighborCandidatesRef.current.filter((c) => {
        const n = normalizeCandidate(c)
        return n.ring && n.ring.length >= 3
      }).length,
    })

    // Place a straight anchor at geo coordinates (lat, lon). Returns true on success.
    // Does NOT snap (for deterministic Playwright placement). Does NOT set extendMode.
    win.__forgePenPlaceAnchor = (lat: number, lon: number): boolean => {
      const newAnchor: PenAnchor = { lat, lon, type: 'straight' }
      setAnchors((prev) => [...prev, newAnchor])
      return true
    }

    // Place a CURVE (smooth) anchor: tangent (dLat,dLon) sets the outgoing handle (cp1)
    // and its mirror the incoming handle (cp2) — same math as the press-drag-release path.
    win.__forgePenPlaceCurveAnchor = (lat, lon, dLat, dLon): boolean => {
      const newAnchor: PenAnchor = {
        lat,
        lon,
        type: 'curve',
        cp1: { lat: lat + dLat, lon: lon + dLon },
        cp2: { lat: lat - dLat, lon: lon - dLon },
      }
      setAnchors((prev) => [...prev, newAnchor])
      return true
    }

    // Close the pen path deterministically (bypasses distance-to-first-anchor check).
    // Validates the current anchors via D-17 rules; if valid, commits CREATE or EXTEND.
    // Returns true if close was attempted (false if < 3 anchors or already closed).
    win.__forgePenClose = async (): Promise<boolean> => {
      const cur = anchorsRef.current
      if (cur.length < 3) return false

      // Build canvas-px points for validation
      const proj = projectionRef.current
      const pxPts = cur.map((a) => {
        const [x, y] = geoToCanvas(a.lon, a.lat, proj)
        return { x, y }
      })

      // Run D-17 validation
      if (cur.length < 3) { setValidationError('Mínimo de 3 pontos para fechar o contorno.'); return false }
      if (hasSelfIntersection(pxPts)) { setValidationError('O contorno se cruza — ajuste os pontos e tente fechar novamente.'); return false }
      if (ringAreaPx2(pxPts) < MIN_AREA_PX2) { setValidationError('Área muito pequena — o baronato seria removido na limpeza. Amplie o contorno.'); return false }

      setValidationError(null)
      const closedAnchors = [...cur]
      setAnchors([])

      if (extendModeRef.current && extendBaronyIdRef.current) {
        commitExtendRef.current(closedAnchors, extendBaronyIdRef.current)
      } else {
        // Nearest neighbor for hierarchy inherit (same as handleClick close path)
        const candidates = neighborCandidatesRef.current
        const neighborId = cur[0]
          ? (() => {
              for (const f of candidates) {
                const n = normalizeCandidate(f)
                if (!n.ring) continue
                const match = n.ring.some(
                  (pt) =>
                    Array.isArray(pt) &&
                    Math.abs((pt[1] as number) - cur[0].lat) < 0.01 &&
                    Math.abs((pt[0] as number) - cur[0].lon) < 0.01,
                )
                if (match) return n.id
              }
              return null
            })()
          : null
        await commitCreateRef.current(closedAnchors, neighborId)
      }
      return true
    }

    return () => {
      delete win.__forgePenState
      delete win.__forgePenPlaceAnchor
      delete win.__forgePenPlaceCurveAnchor
      delete win.__forgePenClose
    }
  }, [anchors.length])

  // ── Render ────────────────────────────────────────────────────────────────
  // Convert first anchor to canvas px for closeable-pulse check
  const firstAnchorPx =
    anchors.length > 0 ? geoToCanvas(anchors[0].lon, anchors[0].lat, projection) : null

  // Is cursor close enough to first anchor to close? (pulse trigger)
  // Map-px distance vs screen-px radius → divide by safeScale (08.3-07 UAT fix) so the
  // amber pulse fires exactly when the close gesture (handleMouseDown) would.
  const closeableHover =
    anchors.length >= 2 &&
    cursorPos !== null &&
    firstAnchorPx !== null &&
    Math.sqrt(
      Math.pow(cursorPos.x - firstAnchorPx[0], 2) +
      Math.pow(cursorPos.y - firstAnchorPx[1], 2),
    ) <= PEN_SNAP_PX / safeScale

  return (
    <Layer>
      <Group
        name="pen-draw-layer"
        data-testid="pen-draw-layer"
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseMove={handleMouseMove}
        onContextMenu={(e) => {
          // Right-click deletes the last placed anchor (user request 2026-05-31).
          // Suppress the browser context menu so right-click is a pure edit gesture.
          e.evt?.preventDefault?.()
          e.cancelBubble = true
          removeLastAnchor()
        }}
      >
        {/* Phase 08.3 (UAT fix): full map-space hit Rect. Konva only bubbles pointer events
            to this Group when a child SHAPE is the hit target — an empty-space click otherwise
            targets the Stage and never reaches handleClick. A transparent fill is still added
            to the hit graph (the hit canvas keys on shape identity, not fill alpha), so this
            Rect catches clicks/moves anywhere over the map without painting anything. */}
        <Rect
          x={0}
          y={0}
          width={projection.mapW}
          height={projection.mapH}
          fill="transparent"
          listening={true}
          data-testid="pen-hit-area"
        />

        {/* Live tangent preview while dragging out a curve anchor (PEN-CURVE-01). */}
        {dragPreview && (
          <>
            <Line
              points={[
                dragPreview.cp2[0], dragPreview.cp2[1],
                dragPreview.anchor[0], dragPreview.anchor[1],
                dragPreview.cp1[0], dragPreview.cp1[1],
              ]}
              stroke={HANDLE_FILL}
              strokeWidth={1 / safeScale}
              listening={false}
              data-testid="pen-drag-tangent"
            />
            <Circle x={dragPreview.cp1[0]} y={dragPreview.cp1[1]} radius={handleRadius} fill={HANDLE_FILL} listening={false} />
            <Circle x={dragPreview.cp2[0]} y={dragPreview.cp2[1]} radius={handleRadius} fill={HANDLE_FILL} listening={false} />
          </>
        )}

        {/* Validation error overlay (D-17) */}
        {validationError && (
          <>
            <Text
              x={10}
              y={10}
              text={validationError}
              fontSize={textSize}
              fill={VALIDATION_STROKE}
              listening={false}
              data-testid="pen-validation-error"
            />
          </>
        )}

        {/* Rubber-band: last anchor → cursor. Hidden while dragging out a curve anchor —
            the live green curve below already shows the bend toward the dragged anchor. */}
        {anchors.length >= 1 && cursorPos !== null && !dragPreview && (() => {
          const [lx, ly] = geoToCanvas(anchors[anchors.length - 1].lon, anchors[anchors.length - 1].lat, projection)
          return (
            <Line
              points={[lx, ly, cursorPos.x, cursorPos.y]}
              stroke={RUBBER_BAND_STROKE}
              strokeWidth={1 / safeScale}
              dash={[6, 4]}
              listening={false}
              data-testid="pen-rubber-band"
            />
          )
        })()}

        {/* Live curve between placed anchors. Phase 08.3 (UAT fix #2): the path is the
            ACTUAL bezier (sampled from each anchor's cp1/cp2 via flattenPenPathOpen), not a
            straight polyline — so the curve is visible WHILE drawing, like Photoshop. Uses the
            same per-segment sampling as the committed ring (flattenPenPath), so display ==
            committed shape by construction. Open path; the pending last-anchor→cursor segment
            stays a straight rubber-band above. */}
        {(() => {
          // While dragging, append the in-progress curve anchor so the green curve bends
          // toward it LIVE (before mouse-up). Otherwise show the committed open path.
          const previewAnchors = dragPreview
            ? [...anchors, dragPreview.curveAnchor]
            : anchors
          if (previewAnchors.length < 2) return null
          const curve = flattenPenPathOpen(previewAnchors, projection)
          const pts: number[] = []
          for (const p of curve) {
            const [x, y] = geoToCanvas(p.lon, p.lat, projection)
            pts.push(x, y)
          }
          return (
            <Line
              points={pts}
              stroke={CURVE_STROKE}
              strokeWidth={curveWidth}
              listening={false}
              data-testid="pen-path-curve"
            />
          )
        })()}

        {/* Validation error ring overlay (red fill when invalid) */}
        {validationError && anchors.length >= 3 && (() => {
          const pts: number[] = []
          for (const a of anchors) {
            const [x, y] = geoToCanvas(a.lon, a.lat, projection)
            pts.push(x, y)
          }
          return (
            <Line
              points={pts}
              closed
              fill={VALIDATION_FILL}
              stroke={VALIDATION_STROKE}
              strokeWidth={curveWidth}
              listening={false}
            />
          )
        })()}

        {/* Placed anchors */}
        {anchors.map((a, i) => {
          const [ax, ay] = geoToCanvas(a.lon, a.lat, projection)
          return (
            <React.Fragment key={i}>
              {a.type === 'curve' ? (
                <Circle
                  x={ax}
                  y={ay}
                  radius={anchorHalf}
                  fill={ANCHOR_CURVE_FILL}
                />
              ) : (
                <Rect
                  x={ax - anchorHalf}
                  y={ay - anchorHalf}
                  width={anchorSize}
                  height={anchorSize}
                  fill={ANCHOR_STRAIGHT_FILL}
                />
              )}

              {/* First anchor — closeable highlight pulse ring */}
              {i === 0 && anchors.length >= 2 && (
                <Circle
                  x={ax}
                  y={ay}
                  radius={snapRadius}
                  stroke={FIRST_ANCHOR_STROKE}
                  strokeWidth={2 / safeScale}
                  fill="transparent"
                  listening={false}
                  data-testid="pen-first-anchor"
                  opacity={closeableHover ? 1 : 0.6}
                />
              )}

              {/* Curve handles for curve anchors */}
              {a.type === 'curve' && a.cp1 && (() => {
                const [cp1x, cp1y] = geoToCanvas(a.cp1.lon, a.cp1.lat, projection)
                return (
                  <>
                    <Line
                      points={[ax, ay, cp1x, cp1y]}
                      stroke={TETHER_STROKE}
                      strokeWidth={1 / safeScale}
                      dash={[4, 4]}
                      listening={false}
                    />
                    <Circle x={cp1x} y={cp1y} radius={handleRadius} fill={HANDLE_FILL} />
                  </>
                )
              })()}
              {a.type === 'curve' && a.cp2 && (() => {
                const [cp2x, cp2y] = geoToCanvas(a.cp2.lon, a.cp2.lat, projection)
                return (
                  <>
                    <Line
                      points={[ax, ay, cp2x, cp2y]}
                      stroke={TETHER_STROKE}
                      strokeWidth={1 / safeScale}
                      dash={[4, 4]}
                      listening={false}
                    />
                    <Circle x={cp2x} y={cp2y} radius={handleRadius} fill={HANDLE_FILL} />
                  </>
                )
              })()}
            </React.Fragment>
          )
        })}

        {/* Snap vertex marker */}
        {snapVertexMarker && (
          <Circle
            x={snapVertexMarker.x}
            y={snapVertexMarker.y}
            radius={snapRadius}
            stroke={SNAP_VERTEX_STROKE}
            strokeWidth={2 / safeScale}
            fill="transparent"
            listening={false}
            data-testid="pen-snap-vertex"
          />
        )}

        {/* Snap edge marker */}
        {snapEdgeMarker && (
          <Line
            points={[snapEdgeMarker.x1, snapEdgeMarker.y1, snapEdgeMarker.x2, snapEdgeMarker.y2]}
            stroke={SNAP_EDGE_STROKE}
            strokeWidth={2 / safeScale}
            listening={false}
            data-testid="pen-snap-edge"
          />
        )}

        {/* Freehand (lasso) live preview — dashed green line while dragging (D-20) */}
        {freehandPreviewPts.length >= 4 && (
          <Line
            points={freehandPreviewPts}
            stroke={CURVE_STROKE}
            strokeWidth={curveWidth}
            dash={[6, 3]}
            listening={false}
            data-testid="pen-freehand-preview"
          />
        )}

        {/* Status hint (D-22): per-state PT-BR contextual text */}
        {cursorPos && (() => {
          let hintText: string
          if (freehandMode && isFreehandDraggingRef.current) {
            hintText = 'Solte para fechar o contorno livre'
          } else if (freehandMode) {
            hintText = 'Arraste para desenhar o contorno livre — solte para fechar'
          } else if (anchors.length >= 1) {
            hintText = 'Clique no primeiro ponto para fechar — Botão direito: desfazer último ponto — Esc: cancelar'
          } else {
            hintText = 'Clique: âncora reta — Arraste: curva Bézier — Botão direito: desfazer ponto'
          }
          return (
            <Text
              x={cursorPos.x + 8 / safeScale}
              y={cursorPos.y + 12 / safeScale}
              text={hintText}
              fontSize={textSize}
              fill={STATUS_FILL}
              opacity={0.75}
              listening={false}
              data-testid="pen-status-hint"
            />
          )
        })()}
      </Group>
    </Layer>
  )
}

export default PenDrawLayer
