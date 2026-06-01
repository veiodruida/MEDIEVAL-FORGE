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

type DragMode = 'none' | 'body' | 'vertex'

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
  const [dragMode, setDragMode] = useState<DragMode>('none')
  const [activeVertexIdx, setActiveVertexIdx] = useState<number>(-1)
  const [liveRing, setLiveRing] = useState<Array<{ lat: number; lon: number }> | null>(null)

  // Refs for stable pointer-position tracking during drag
  const dragStartGeoRef = useRef<{ lat: number; lon: number } | null>(null)
  const isDraggingRef = useRef(false)
  const dragModeRef = useRef<DragMode>('none')
  const activeVertexIdxRef = useRef<number>(-1)
  const liveRingRef = useRef<Array<{ lat: number; lon: number }> | null>(null)
  const committedRingRef = useRef<Array<{ lat: number; lon: number }> | null>(null)
  committedRingRef.current = committedRing

  // Keep live ring ref in sync with state
  liveRingRef.current = liveRing
  dragModeRef.current = dragMode
  activeVertexIdxRef.current = activeVertexIdx

  // ── Inert when no pending op ───────────────────────────────────────────────
  if (pendingOpIdx < 0 || !committedRing) return null

  // ── Render ring: use liveRing during drag, committedRing at rest ───────────
  const renderRing = liveRing ?? committedRing

  // ── Coordinate helper: KonvaEvent → geo world point ───────────────────────
  function eventToGeo(e: Konva.KonvaEventObject<MouseEvent>): { lat: number; lon: number } | null {
    // Real Konva: getRelativePointerPosition (map-space, as PenDrawLayer.tsx:494-504)
    const stage = (() => {
      try { return (e.target?.getStage?.() ?? null) as Konva.Stage | null } catch { return null }
    })()
    const rel = stage?.getRelativePointerPosition?.()
    if (rel) {
      const [lon, lat] = canvasToGeo(rel.x, rel.y, projection)
      return { lat, lon }
    }
    // jsdom/test fallback: use clientX/Y mapped through projection
    const raw = e as unknown as { evt?: MouseEvent; clientX?: number; clientY?: number }
    const clientX = raw.evt?.clientX ?? raw.clientX ?? 0
    const clientY = raw.evt?.clientY ?? raw.clientY ?? 0
    const [lon, lat] = canvasToGeo(clientX, clientY, projection)
    return { lat, lon }
  }

  // ── Write the manipulated ring back to the store (gesture-end only) ────────
  function commitRing(newRing: Array<{ lat: number; lon: number }>) {
    // Read current editLog at commit time (not captured at gesture-start)
    const log = useEditorStore.getState().editLog
    // NEW array ref (FACT 6a — referential equality in partialize requires this)
    const nextLog: EditOp[] = log.map((op, i) =>
      i === pendingOpIdx ? { ...op, ring: newRing } : op,
    )
    useEditorStore.setState({ editLog: nextLog })
  }

  // ── Body drag handlers ─────────────────────────────────────────────────────
  const handleBodyMouseDown = useCallback((e: Konva.KonvaEventObject<MouseEvent>) => {
    const world = eventToGeo(e)
    if (!world || !committedRingRef.current) return
    e.cancelBubble = true
    isDraggingRef.current = true
    setDragMode('body')
    dragStartGeoRef.current = world
    setLiveRing([...committedRingRef.current])
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleBodyMouseMove = useCallback((e: Konva.KonvaEventObject<MouseEvent>) => {
    if (!isDraggingRef.current || dragModeRef.current !== 'body') return
    const world = eventToGeo(e)
    const start = dragStartGeoRef.current
    const committed = committedRingRef.current
    if (!world || !start || !committed) return
    const dLat = world.lat - start.lat
    const dLon = world.lon - start.lon
    setLiveRing(translateRing(committed, dLat, dLon))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleBodyMouseUp = useCallback((e: Konva.KonvaEventObject<MouseEvent>) => {
    if (!isDraggingRef.current || dragModeRef.current !== 'body') return
    const world = eventToGeo(e)
    const start = dragStartGeoRef.current
    const committed = committedRingRef.current
    isDraggingRef.current = false
    setDragMode('none')
    dragStartGeoRef.current = null
    if (!world || !start || !committed) { setLiveRing(null); return }
    const dLat = world.lat - start.lat
    const dLon = world.lon - start.lon
    const finalRing = translateRing(committed, dLat, dLon)
    setLiveRing(null)
    commitRing(finalRing)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Vertex drag handlers ───────────────────────────────────────────────────
  const handleVertexMouseDown = useCallback((
    e: Konva.KonvaEventObject<MouseEvent>,
    vIdx: number,
  ) => {
    if (!committedRingRef.current) return
    e.cancelBubble = true
    isDraggingRef.current = true
    setDragMode('vertex')
    setActiveVertexIdx(vIdx)
    setLiveRing([...committedRingRef.current])
  }, [])

  const handleVertexMouseMove = useCallback((e: Konva.KonvaEventObject<MouseEvent>) => {
    if (!isDraggingRef.current || dragModeRef.current !== 'vertex') return
    const world = eventToGeo(e)
    const committed = committedRingRef.current
    if (!world || !committed) return
    const vIdx = activeVertexIdxRef.current
    setLiveRing(moveRingVertex(committed, vIdx, world.lat, world.lon))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleVertexMouseUp = useCallback((e: Konva.KonvaEventObject<MouseEvent>) => {
    if (!isDraggingRef.current || dragModeRef.current !== 'vertex') return
    const world = eventToGeo(e)
    const committed = committedRingRef.current
    isDraggingRef.current = false
    const vIdx = activeVertexIdxRef.current
    setDragMode('none')
    setActiveVertexIdx(-1)
    if (!world || !committed) { setLiveRing(null); return }
    const finalRing = moveRingVertex(committed, vIdx, world.lat, world.lon)
    setLiveRing(null)
    commitRing(finalRing)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Esc handler: discard in-progress manipulation (FACT 6b / D-03) ─────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      if (!isDraggingRef.current) return
      e.stopPropagation()
      isDraggingRef.current = false
      setDragMode('none')
      setActiveVertexIdx(-1)
      dragStartGeoRef.current = null
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
    <Layer
      name="pen-manipulate-layer"
      onMouseMove={dragMode === 'body' ? handleBodyMouseMove : dragMode === 'vertex' ? handleVertexMouseMove : undefined}
      onMouseUp={dragMode === 'body' ? handleBodyMouseUp : dragMode === 'vertex' ? handleVertexMouseUp : undefined}
    >
      {/* Body shape — draggable, supersedes static ghost */}
      <Line
        points={bodyPoints}
        closed
        fill={BODY_FILL}
        stroke={BODY_STROKE}
        strokeWidth={strokeWidth}
        dash={[8 / currentScale, 4 / currentScale]}
        opacity={0.9}
        listening
        onMouseDown={handleBodyMouseDown}
        data-testid="pen-manipulate-body"
      />
      {/* Vertex handles — one per unique ring point (closing duplicate excluded) */}
      {uniqueVertices.map((pt, i) => {
        const [x, y] = geoToCanvas(pt.lon, pt.lat, projection)
        const isActive = dragMode === 'vertex' && activeVertexIdx === i
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
            onMouseDown={(e) => handleVertexMouseDown(e, i)}
            data-testid="pen-manipulate-vertex"
          />
        )
      })}
    </Layer>
  )
}
