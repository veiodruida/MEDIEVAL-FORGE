/**
 * Phase 08.3 Plan 11 — PenShapeManipulateLayer
 *
 * Interactive Konva layer that allows the user to:
 *   1. DRAG THE WHOLE pending create/carve shape (body drag → translateRing)
 *   2. DRAG INDIVIDUAL VERTICES of the pending shape (vertex drag → moveRingVertex)
 *
 * Before "Aplicar edições" — for BOTH a CREATE (gap-fill) and a CARVE (enclave) pending op.
 *
 * Architecture (PLAN FACT 1-6):
 *   - Reads the pending op (last editLog op with op:'create'|'carve' AND ring.length>=3).
 *   - All in-progress drag state is COMPONENT-LOCAL (FACT 6b — mirrors PenDrawLayer pattern).
 *   - Gesture-end: writes op.ring back ONCE with a NEW editLog array ref (FACT 6a).
 *   - Does NOT call setVerticesAndLog → no vertex op emitted → vertex_ops_present stays false (FACT 3).
 *   - Esc during drag: discards liveRing, no store write (FACT 6b).
 *   - Renders the pending ring with the same green palette as the static ghost (FACT 5).
 *   - This layer SUPERSEDES the static ghost while mounted (CanvasViewer suppresses the ghost).
 *
 * Drag implementation (UAT fix — 08.3-11 debug session):
 *   Uses Konva's built-in `draggable` prop on the Line and Circle nodes.
 *   This is critical: manual mousedown/mousemove/mouseup on a Layer only fires events
 *   bubbled from direct children; once the pointer leaves the shape, the Stage swallows
 *   mousemove/mouseup so the Layer handlers never fire → the drag appears to be a no-op.
 *   With `draggable`, Konva captures stage-wide pointer events automatically during drag
 *   (same pattern as BezierEditLayer anchors).
 *
 *   Body: onDragMove accumulates the canvas-space offset (e.target.x/y), converts to geo
 *   delta, updates liveRing.  onDragEnd commits to store and resets node position to (0,0).
 *   Vertex: Circle's x/y IS the canvas-space position.  onDragEnd reads final position,
 *   converts to geo, commits to store.
 *
 * Coordinate space: all drag deltas are computed in geo-space via
 *   getRelativePointerPosition() → canvasToGeo on start + current pointer.
 * (Same fix as PenDrawLayer.tsx:488-515 and BezierEditLayer.tsx 08.1-07 G7 fix.)
 */

import React, { useCallback, useEffect, useRef, useState } from 'react'
import type Konva from 'konva'
import { Layer, Line, Circle } from 'react-konva'
import { useEditorStore } from '../../stores/useEditorStore'
import type { EditOp } from '../../stores/useEditorStore'
import { geoToCanvas, canvasToGeo } from '../../lib/projection'
import type { ProjectionConfig } from '../../lib/projection'
import { translateRing, moveRingVertex } from '../../lib/penShapeManipulate'

// ── Color constants (match static ghost palette — FACT 5) ────────────────────
const BODY_FILL = 'rgba(34, 197, 94, 0.12)'
const BODY_STROKE = '#22c55e'
const VERTEX_FILL = '#22c55e'
const VERTEX_ACTIVE_FILL = '#f0c040' // amber when being dragged

// ── Sizing constants (screen-space, scaled like PenDrawLayer) ─────────────────
const BASE_VERTEX_RADIUS = 6   // screen-px at scale=1
const BASE_STROKE_WIDTH = 2    // screen-px at scale=1

// ── Types ─────────────────────────────────────────────────────────────────────

interface Props {
  projection: ProjectionConfig
  currentScale: number
}

// ── Component ─────────────────────────────────────────────────────────────────

export function PenShapeManipulateLayer({ projection, currentScale }: Props): React.ReactElement | null {
  // ── Read pending op from store ─────────────────────────────────────────────
  // Re-read via selector every render so we get the latest committed ring.
  const editLog = useEditorStore((s) => s.editLog)

  // Find the LAST create|carve op that has a valid ring.
  const pendingOpIdx = (() => {
    for (let i = editLog.length - 1; i >= 0; i--) {
      const op = editLog[i]
      if ((op.op === 'create' || op.op === 'carve') && op.ring && op.ring.length >= 3) {
        return i
      }
    }
    return -1
  })()

  const committedRing = pendingOpIdx >= 0 ? editLog[pendingOpIdx].ring! : null

  // ── Component-local gesture state (NEVER in store — FACT 6b) ──────────────
  const [activeVertexIdx, setActiveVertexIdx] = useState<number>(-1)
  const [liveRing, setLiveRing] = useState<Array<{ lat: number; lon: number }> | null>(null)

  // Stable refs for values needed inside drag callbacks
  const committedRingRef = useRef<Array<{ lat: number; lon: number }> | null>(null)
  committedRingRef.current = committedRing

  // pendingOpIdx captured in a ref so commitRing closures are always fresh
  const pendingOpIdxRef = useRef(pendingOpIdx)
  pendingOpIdxRef.current = pendingOpIdx

  // Body drag start position (canvas-space) — used by jsdom fallback to compute offset
  const bodyDragStartCanvasRef = useRef<{ x: number; y: number } | null>(null)

  // Last live canvas-space position seen during body/vertex drag-move.
  // Used in drag-end instead of e.target.x()/y() because React-controlled x/y props
  // fight Konva's internal drag: after a move re-render, e.target.x() can report the
  // PRE-drag position at dragEnd (same issue as BezierEditLayer UAT fix #1, line 474-480).
  const bodyLastCanvasPosRef = useRef<{ x: number; y: number } | null>(null)
  const vertexLastCanvasPosRef = useRef<{ x: number; y: number } | null>(null)

  // ── Inert when no pending op ───────────────────────────────────────────────
  if (pendingOpIdx < 0 || !committedRing) return null

  // ── Render ring: use liveRing during drag, committedRing at rest ───────────
  const renderRing = liveRing ?? committedRing

  // ── Write the manipulated ring back to the store (gesture-end only) ────────
  function commitRing(newRing: Array<{ lat: number; lon: number }>) {
    // Read current editLog at commit time (not captured at gesture-start)
    const log = useEditorStore.getState().editLog
    const idx = pendingOpIdxRef.current
    // NEW array ref (FACT 6a — referential equality in partialize requires this)
    const nextLog: EditOp[] = log.map((op, i) =>
      i === idx ? { ...op, ring: newRing } : op,
    )
    useEditorStore.setState({ editLog: nextLog })
  }

  // ── Canvas-position extractor: stage pointer (preferred) vs jsdom fallback ──
  // For vertex drag: use stage.getRelativePointerPosition() — the pointer location
  // in canvas-space, independent of the Circle's React-controlled x/y props.
  // Circles have x/y bound to displayAnchors; React re-renders during drag reset
  // the node position (Konva can't move a React-controlled prop freely), so
  // e.target.x()/y() at dragEnd reflects the start position, not the drop.
  // stage.getRelativePointerPosition() is immune because it tracks the raw cursor.
  // (Same root cause as BezierEditLayer UAT-fix #1, line 474-480.)
  function pointerCanvasPos(
    e: Konva.KonvaEventObject<DragEvent | MouseEvent>,
  ): { x: number; y: number } {
    // Real Konva: getRelativePointerPosition gives cursor in canvas-space
    const stage = (() => {
      try { return (e.target as unknown as { getStage?: () => Konva.Stage | null })?.getStage?.() ?? null } catch { return null }
    })()
    const rel = stage?.getRelativePointerPosition?.()
    if (rel) return { x: rel.x, y: rel.y }
    // jsdom fallback: clientX/Y passed by tests as canvas-space values
    const raw = e as unknown as { evt?: MouseEvent; clientX?: number; clientY?: number }
    return {
      x: raw.evt?.clientX ?? raw.clientX ?? 0,
      y: raw.evt?.clientY ?? raw.clientY ?? 0,
    }
  }

  // ── Node offset extractor for BODY drag (Line is uncontrolled — safe) ───────
  // The body Line has NO React-controlled x/y props (they come from the points
  // array, not x/y). Konva freely accumulates the offset in node.x()/y() — safe
  // to read here. jsdom: compute delta from start position.
  function nodeCanvasPos(
    e: Konva.KonvaEventObject<DragEvent | MouseEvent>,
  ): { x: number; y: number } {
    const t = e.target as unknown as { x?: () => number; y?: () => number }
    if (typeof t.x === 'function' && typeof t.y === 'function') {
      return { x: t.x(), y: t.y() }
    }
    // jsdom fallback: raw event clientX/Y treated as canvas-space
    const raw = e as unknown as { evt?: MouseEvent; clientX?: number; clientY?: number }
    return {
      x: raw.evt?.clientX ?? raw.clientX ?? 0,
      y: raw.evt?.clientY ?? raw.clientY ?? 0,
    }
  }

  // ── Body drag handlers (draggable Line) ───────────────────────────────────
  // Konva's draggable captures stage-wide pointer events during drag so
  // mousemove/mouseup fire even when the cursor leaves the shape boundary.
  // We track the geo-space delta from the canvas-space node offset that Konva
  // accumulates in e.target.x() / e.target.y().

  const handleBodyDragStart = useCallback((e: Konva.KonvaEventObject<DragEvent>) => {
    // Record start position for jsdom fallback (Konva resets node.x/y to 0 on
    // drag start, so we only need this for the test environment where clientX/Y
    // are absolute canvas-space coords and we need to compute the delta ourselves).
    const pos = nodeCanvasPos(e)
    bodyDragStartCanvasRef.current = pos
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleBodyDragMove = useCallback((e: Konva.KonvaEventObject<DragEvent>) => {
    const committed = committedRingRef.current
    if (!committed) return
    // Konva: e.target.x()/y() is the accumulated offset from the drag origin.
    // jsdom fallback: compute delta from start position captured in dragStart.
    const t = e.target as unknown as { x?: () => number }
    let dCanvasX: number
    let dCanvasY: number
    if (typeof t.x === 'function') {
      dCanvasX = (e.target as unknown as { x: () => number }).x()
      dCanvasY = (e.target as unknown as { y: () => number }).y()
    } else {
      const pos = nodeCanvasPos(e)
      const start = bodyDragStartCanvasRef.current ?? { x: 0, y: 0 }
      dCanvasX = pos.x - start.x
      dCanvasY = pos.y - start.y
    }
    // Track for dragEnd (avoids the BezierEditLayer UAT-fix#1 problem where
    // e.target.x()/y() reports pre-drag position after a React re-render).
    bodyLastCanvasPosRef.current = { x: dCanvasX, y: dCanvasY }
    // Convert canvas-space delta to geo delta (affine projection — delta is constant).
    const [lon0, lat0] = canvasToGeo(0, 0, projection)
    const [lon1, lat1] = canvasToGeo(dCanvasX, dCanvasY, projection)
    const dLon = lon1 - lon0
    const dLat = lat1 - lat0
    setLiveRing(translateRing(committed, dLat, dLon))
  }, [projection]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleBodyDragEnd = useCallback((e: Konva.KonvaEventObject<DragEvent>) => {
    const committed = committedRingRef.current
    // Prefer the last-move delta (avoids stale e.target.x() after React re-render).
    // Fall back to computing from event if no moves were recorded.
    const lastPos = bodyLastCanvasPosRef.current
    bodyLastCanvasPosRef.current = null
    let dCanvasX: number
    let dCanvasY: number
    if (lastPos) {
      dCanvasX = lastPos.x
      dCanvasY = lastPos.y
    } else {
      const t = e.target as unknown as { x?: () => number; position?: (p: { x: number; y: number }) => void }
      if (typeof t.x === 'function') {
        dCanvasX = (t.x as () => number)()
        dCanvasY = (e.target as unknown as { y: () => number }).y()
        if (typeof t.position === 'function') t.position({ x: 0, y: 0 })
      } else {
        const pos = nodeCanvasPos(e)
        const start = bodyDragStartCanvasRef.current ?? { x: 0, y: 0 }
        dCanvasX = pos.x - start.x
        dCanvasY = pos.y - start.y
      }
    }
    // Reset node position so the Line stays at its canonical origin
    const tPos = e.target as unknown as { position?: (p: { x: number; y: number }) => void }
    if (typeof tPos.position === 'function') tPos.position({ x: 0, y: 0 })
    bodyDragStartCanvasRef.current = null
    if (!committed) { setLiveRing(null); return }
    const [lon0, lat0] = canvasToGeo(0, 0, projection)
    const [lon1, lat1] = canvasToGeo(dCanvasX, dCanvasY, projection)
    const dLon = lon1 - lon0
    const dLat = lat1 - lat0
    const finalRing = translateRing(committed, dLat, dLon)
    setLiveRing(null)
    commitRing(finalRing)
  }, [projection]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Vertex drag handlers (draggable Circle) ───────────────────────────────
  // The Circle's x/y IS the canvas-space position of the vertex.  After drag,
  // e.target.x()/y() is the new canvas-space position — convert directly to geo.
  // jsdom fallback: clientX/Y passed by tests are treated as canvas-space coords.
  //
  // IMPORTANT: use vertexLastCanvasPosRef (set in dragMove) at dragEnd instead of
  // e.target.x()/y().  React-controlled x/y props cause Konva to report the
  // pre-drag canvas position in e.target at dragEnd (BezierEditLayer UAT-fix #1).

  const handleVertexDragStart = useCallback((
    e: Konva.KonvaEventObject<DragEvent>,
    vIdx: number,
  ) => {
    e.cancelBubble = true
    vertexLastCanvasPosRef.current = null
    setActiveVertexIdx(vIdx)
    setLiveRing([...(committedRingRef.current ?? [])])
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleVertexDragMove = useCallback((
    e: Konva.KonvaEventObject<DragEvent>,
    vIdx: number,
  ) => {
    const committed = committedRingRef.current
    if (!committed) return
    // Use stage pointer position — immune to React-controlled x/y prop reset.
    const pos = pointerCanvasPos(e)
    vertexLastCanvasPosRef.current = pos
    const [lon, lat] = canvasToGeo(pos.x, pos.y, projection)
    setLiveRing(moveRingVertex(committed, vIdx, lat, lon))
  }, [projection]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleVertexDragEnd = useCallback((
    e: Konva.KonvaEventObject<DragEvent>,
    vIdx: number,
  ) => {
    const committed = committedRingRef.current
    // Trust last-move pointer position (set in dragMove, immune to React prop reset).
    // Fall back to current pointer position if no dragMove was seen.
    const lastPos = vertexLastCanvasPosRef.current ?? pointerCanvasPos(e)
    vertexLastCanvasPosRef.current = null
    const [lon, lat] = canvasToGeo(lastPos.x, lastPos.y, projection)
    setActiveVertexIdx(-1)
    setLiveRing(null)
    if (!committed) return
    const finalRing = moveRingVertex(committed, vIdx, lat, lon)
    commitRing(finalRing)
  }, [projection]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Esc handler: discard in-progress manipulation (FACT 6b / D-03) ─────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      e.stopPropagation()
      setActiveVertexIdx(-1)
      setLiveRing(null)
      // Do NOT write to store — discard the in-progress drag (FACT 6b)
    }
    window.addEventListener('keydown', handler, true) // capture phase
    return () => window.removeEventListener('keydown', handler, true)
  }, [])

  // ── Build vertex handles (drop the closing duplicate) ─────────────────────
  // A closed ring has first === last; we only show N-1 unique handles.
  const uniqueVertices = committedRing.length >= 2
    ? committedRing.slice(0, committedRing.length - 1)
    : committedRing

  // ── Build Konva points for the body Line ───────────────────────────────────
  const bodyPoints: number[] = []
  for (const pt of renderRing) {
    const [x, y] = geoToCanvas(pt.lon, pt.lat, projection)
    bodyPoints.push(x, y)
  }

  const strokeWidth = BASE_STROKE_WIDTH / currentScale
  const vertexRadius = BASE_VERTEX_RADIUS / currentScale

  // ── DEV-only read-only hatch (FACT 6 / plan spec §action) ─────────────────
  // Exposes current committed op.ring for Playwright assertions ONLY.
  // Input gestures in UAT use REAL page.mouse — never this hook.
  if (typeof window !== 'undefined' && (import.meta as { env?: { DEV?: boolean } }).env?.DEV) {
    const w = window as unknown as Record<string, unknown>
    w.__forgePendingRing = () => {
      const log = useEditorStore.getState().editLog
      for (let i = log.length - 1; i >= 0; i--) {
        const op = log[i]
        if ((op.op === 'create' || op.op === 'carve') && op.ring && op.ring.length >= 3) {
          return [...op.ring]
        }
      }
      return null
    }
  }

  return (
    <Layer name="pen-manipulate-layer">
      {/* Body shape — draggable captures stage-wide pointer events (UAT fix) */}
      <Line
        points={bodyPoints}
        closed
        fill={BODY_FILL}
        stroke={BODY_STROKE}
        strokeWidth={strokeWidth}
        dash={[8 / currentScale, 4 / currentScale]}
        opacity={0.9}
        listening
        draggable
        onDragStart={handleBodyDragStart}
        onDragMove={handleBodyDragMove}
        onDragEnd={handleBodyDragEnd}
        data-testid="pen-manipulate-body"
      />
      {/* Vertex handles — one per unique ring point (closing duplicate excluded) */}
      {uniqueVertices.map((pt, i) => {
        // Use renderRing for vertex positions so handles track the live ring during body drag
        const renderPt = (liveRing ?? committedRing)[i] ?? pt
        const [x, y] = geoToCanvas(renderPt.lon, renderPt.lat, projection)
        const isActive = activeVertexIdx === i
        return (
          <Circle
            key={i}
            x={x}
            y={y}
            radius={vertexRadius}
            fill={isActive ? VERTEX_ACTIVE_FILL : VERTEX_FILL}
            stroke="#fff"
            strokeWidth={1 / currentScale}
            listening
            draggable
            onDragStart={(e) => handleVertexDragStart(e, i)}
            onDragMove={(e) => handleVertexDragMove(e, i)}
            onDragEnd={(e) => handleVertexDragEnd(e, i)}
            data-testid="pen-manipulate-vertex"
          />
        )
      })}
    </Layer>
  )
}
