/**
 * BezierEditLayer — Konva Layer at z=5 for Bézier-assisted barony contour editing
 * (Phase 08.1 Plan 02).
 *
 * On entry (editableLayer='baronies' + activeTerritoryId set + V-tool + ≥3 vertices),
 * this layer fits the polygon ring to cubic Béziers in canvas-px space, builds the
 * anchor display state in COMPONENT-LOCAL state, and renders:
 *   - the curve outline (Konva.Path)
 *   - one anchor square (Konva.Rect 10×10) per cubic endpoint
 *   - for the ACTIVE anchor only: two control handles (Konva.Circle r=4) + dashed tethers
 *
 * Click-to-activate switches the active anchor. This plan is RENDER + ACTIVATE ONLY —
 * the drag-commit path (which is the only thing that writes geometry back to the store)
 * lands in a later plan. Because nothing here writes to the store, the empty-log identity
 * contract (BEZ-IDENTITY-01) holds trivially by construction: enter+exit with zero drags
 * leaves useEditorStore.vertices byte-identical (RESEARCH §Identity Contract; UI-SPEC Note #2).
 *
 * ALL Bézier display state lives in useState/useRef here — zero new fields in
 * useEditorStore, zero zundo partialize change. `activeAnchorIdx` is component-local
 * (RESEARCH anti-pattern: never put it in the store).
 *
 * UI-SPEC Konva color table (imperative hex literals — CSS vars cannot be used in Konva):
 *   anchor inactive #4a9eff / active #f0c040 / hover #ffffff (Rect 10×10)
 *   control handle  #94a3b8 (Circle r=4, active anchor only)
 *   tether          #94a3b8 width 1 dash [4,4] listening=false (active anchor only)
 *   curve outline   #4a9eff width 2 fill transparent listening=false
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type Konva from 'konva'
import { Layer, Path, Rect, Circle, Line } from 'react-konva'
import { useEditorStore } from '../../stores/useEditorStore'
import {
  fitPolygonToBezier,
  buildPolyIndexMap,
  type BezierCubic,
} from '../../lib/bezierFit'
import { flattenSegment } from '../../lib/bezierFlatten'
import { geoToCanvas, canvasToGeo, type ProjectionConfig } from '../../lib/projection'
import { snapToNeighbour } from '../../lib/snap'
import type { SnapCandidate } from '../../lib/snap'
import {
  buildSharedVertexIndex,
  getCoupledVertices,
  type SharedVertexIndex,
  type VertexRef,
} from '../../lib/sharedVertex'

// UI-SPEC Konva color literals
export const ANCHOR_INACTIVE_FILL = '#4a9eff'
export const ANCHOR_ACTIVE_FILL = '#f0c040'
export const ANCHOR_HOVER_FILL = '#ffffff'
export const HANDLE_FILL = '#94a3b8'
export const TETHER_STROKE = '#94a3b8'
export const CURVE_STROKE = '#4a9eff'

/**
 * Derived display state for one Bézier anchor. ALL component-local — never in the store.
 * polyRangeStart/End are the original-polygon vertex indices this anchor's outgoing cubic
 * spans; the later drag-commit plan uses them to flatten only the affected ranges.
 */
export interface BezierAnchor {
  idx: number
  anchorPx: [number, number]
  cp1Px: [number, number]
  cp2Px: [number, number]
  polyRangeStart: number
  polyRangeEnd: number
}

export interface BezierEditLayerProps {
  /** Projection passed by the parent (CanvasViewer reads it from useProjection at mount). */
  projection: ProjectionConfig
}

/**
 * Sort vertex keys ('b1#0', 'b1#1', … 'b1#10') by their numeric `#N` suffix to preserve
 * ring order. Lexicographic sort would place '#10' before '#2', corrupting the ring.
 */
function sortRingKeys(keys: string[]): string[] {
  return [...keys].sort((a, b) => {
    const na = parseInt(a.split('#')[1] ?? '0', 10)
    const nb = parseInt(b.split('#')[1] ?? '0', 10)
    return na - nb
  })
}

/** Extract the barony id from a vertex key `<baronyId>#<n>`. */
function keyBarony(key: string): string {
  return key.split('#')[0]
}

/** Build the SVG cubic path string for the full curve outline (RESEARCH §Pattern 3). */
export function buildPathData(anchors: BezierAnchor[]): string {
  if (anchors.length === 0) return ''
  let d = `M ${anchors[0].anchorPx[0]} ${anchors[0].anchorPx[1]}`
  for (let i = 0; i < anchors.length - 1; i++) {
    const { cp2Px } = anchors[i]
    const { cp1Px, anchorPx } = anchors[i + 1]
    d += ` C ${cp2Px[0]} ${cp2Px[1]} ${cp1Px[0]} ${cp1Px[1]} ${anchorPx[0]} ${anchorPx[1]}`
  }
  return d
}

/**
 * Derive BezierAnchor[] from the fitted cubics + per-cubic polygon index ranges.
 * Anchor j is cubic j's p0; its outgoing handle cp2 is cubic j's c2 and its incoming
 * handle cp1 is the PREVIOUS cubic's c1 (or this cubic's c1 for the first anchor).
 */
export function deriveAnchors(cubics: BezierCubic[], ranges: ReturnType<typeof buildPolyIndexMap>): BezierAnchor[] {
  const anchors: BezierAnchor[] = []
  for (let j = 0; j < cubics.length; j++) {
    const [p0, c1] = cubics[j]
    const range = ranges[j] ?? { rangeStart: 0, rangeEnd: 0 }
    anchors.push({
      idx: j,
      anchorPx: [p0[0], p0[1]],
      // fit-curve convention: c1 is near p0 (this anchor), c2 is near p3 (next anchor).
      // incoming handle (cp1) of anchor j is the PREVIOUS cubic's c2 (near prev p3 = this
      // anchor); for the first anchor it falls back to this cubic's c1.
      cp1Px: j > 0 ? [cubics[j - 1][2][0], cubics[j - 1][2][1]] : [c1[0], c1[1]],
      // outgoing handle (cp2) of anchor j is THIS cubic's c1 (near p0 = this anchor).
      // [Plan 03 Rule-1 fix] Plan 02 used c2 here, which sits near the NEXT anchor —
      // verified on IBERIA_BARONY_RING (|p0->c1|≈9-13px vs |p0->c2|≈65-92px). Using c2
      // made the outgoing tether stretch to the next anchor and broke rigid handle
      // translation on drag. cp2 must be c1 (the handle that genuinely leaves this anchor).
      cp2Px: [c1[0], c1[1]],
      polyRangeStart: range.rangeStart,
      polyRangeEnd: range.rangeEnd,
    })
  }
  return anchors
}

/**
 * Convenience: fit the store's barony vertices to anchors in one call.
 * Pure (no React) — used by the drag flatten path and by tests to compute the
 * expected dirty ranges. Vertices are keyed `<baronyId>#<n>`; sorted by #N.
 */
export function deriveAnchorsFromStore(
  vertices: Record<string, { lat: number; lon: number }>,
  projection: ProjectionConfig,
): BezierAnchor[] {
  const orderedKeys = sortRingKeys(Object.keys(vertices))
  const coords: Array<[number, number]> = orderedKeys.map((k) => {
    const v = vertices[k]
    return [v.lon, v.lat]
  })
  const cubics = fitPolygonToBezier(coords, projection)
  if (cubics.length === 0) return []
  const pxPts: Array<[number, number]> = coords.map(([lon, lat]) =>
    geoToCanvas(lon, lat, projection),
  )
  const ranges = buildPolyIndexMap(pxPts, cubics)
  return deriveAnchors(cubics, ranges)
}

/** Drag kind: an anchor square, or one of the active anchor's two control handles. */
type DragKind = 'anchor' | 'cp1' | 'cp2'

/**
 * Konva center px of the dragged node. The anchor Rect is positioned by its top-left
 * (`x = anchorPx - 5` for a 10×10 square), so after a drag `e.target.x()` is the new
 * top-left and the true anchor CENTER is `x()+5, y()+5`. Control handles are Circles
 * (center-anchored) so their reported px IS the center.
 */
function draggedCenterPx(kind: DragKind, x: number, y: number): [number, number] {
  return kind === 'anchor' ? [x + 5, y + 5] : [x, y]
}

/**
 * Produce a new anchor list with the dragged element moved to `targetPx`.
 * Anchor drag rigidly translates BOTH control handles by the same delta (preserves local
 * curve shape, no cusp). Control-handle drag moves only that handle. Pure — no snap here
 * (snap is applied to `targetPx` by the caller before this runs, anchors only).
 */
function applyDragToAnchors(
  anchors: BezierAnchor[],
  kind: DragKind,
  idx: number,
  targetPx: [number, number],
): BezierAnchor[] {
  const working = anchors.map((x) => ({
    ...x,
    anchorPx: [...x.anchorPx] as [number, number],
    cp1Px: [...x.cp1Px] as [number, number],
    cp2Px: [...x.cp2Px] as [number, number],
  }))
  const w = working[idx]
  if (!w) return working
  if (kind === 'anchor') {
    const dx = targetPx[0] - w.anchorPx[0]
    const dy = targetPx[1] - w.anchorPx[1]
    w.anchorPx = targetPx
    w.cp1Px = [w.cp1Px[0] + dx, w.cp1Px[1] + dy]
    w.cp2Px = [w.cp2Px[0] + dx, w.cp2Px[1] + dy]
  } else if (kind === 'cp1') {
    w.cp1Px = targetPx
  } else {
    w.cp2Px = targetPx
  }
  return working
}

export const BezierEditLayer: React.FC<BezierEditLayerProps> = ({ projection }) => {
  const editableLayer = useEditorStore((s) => s.editableLayer)
  const activeTerritoryId = useEditorStore((s) => s.activeTerritoryId)
  const activeTool = useEditorStore((s) => s.activeTool)
  const vertices = useEditorStore((s) => s.vertices)

  const vertexCount = Object.keys(vertices).length

  // Active gate: nothing renders unless we are editing a selected barony with the V tool
  // and the polygon has enough points to fit. fitPolygonToBezier also guards <3 (Plan 01).
  const isActive =
    editableLayer === 'baronies' &&
    activeTerritoryId !== null &&
    activeTool === 'V' &&
    vertexCount >= 3

  // ── Component-local Bézier display state (NEVER in the store) ────────────────
  const [anchors, setAnchors] = useState<BezierAnchor[]>([])
  const [activeAnchorIdx, setActiveAnchorIdx] = useState<number | null>(null)
  const [hoverAnchorIdx, setHoverAnchorIdx] = useState<number | null>(null)
  // Live dirty-segment count surfaced via __forgeBezierState (Plan 03).
  const [dirtyCount, setDirtyCount] = useState(0)
  // Live in-flight preview anchors during a drag (UI-SPEC §Anchor step 1). When set,
  // the curve outline + handles render from this instead of committed `anchors` — so the
  // whole curve follows the drag, not just the dragged Konva node. Cleared on dragEnd.
  const [previewAnchors, setPreviewAnchors] = useState<BezierAnchor[] | null>(null)
  // Original ordered coords, px points + ordered store keys, retained for the flatten path.
  const originalRef = useRef<{
    coords: Array<[number, number]>
    pxPts: Array<[number, number]>
    orderedKeys: string[]
    baronyId: string
  }>({ coords: [], pxPts: [], orderedKeys: [], baronyId: '' })
  // anchors snapshot for handlers (avoids stale closures without re-binding every render).
  const anchorsRef = useRef<BezierAnchor[]>([])
  anchorsRef.current = anchors
  // in-flight drag preview (px) — NOT persisted to the store (mirrors VertexEditLayer.previewRef).
  const previewRef = useRef<{ kind: 'anchor' | 'cp1' | 'cp2'; idx: number; px: [number, number] } | null>(
    null,
  )
  // shared-vertex index over the editable vertex set; rebuilt on entry + after commit.
  const sharedIndexRef = useRef<SharedVertexIndex>(new Map())
  // snap candidates (anchor drags only) — vertices NOT belonging to the active barony.
  const snapCandidatesRef = useRef<SnapCandidate[]>([])
  // Alt held → disable snap for current drag (D-28 parity).
  const altHeldRef = useRef(false)

  // ── Fit on entry / activeTerritoryId change ─────────────────────────────────
  // vertices are loaded once by SelectionBridge and stable for the layer's life, so the
  // dep is activeTerritoryId (+ count as a cheap identity key). We DO NOT write the store.
  useEffect(() => {
    if (!isActive || activeTerritoryId === null) {
      setAnchors([])
      setActiveAnchorIdx(null)
      setDirtyCount(0)
      originalRef.current = { coords: [], pxPts: [], orderedKeys: [], baronyId: '' }
      sharedIndexRef.current = new Map()
      snapCandidatesRef.current = []
      return
    }
    // Use the subscribed `vertices` (Plan 02 read path) — never getState here, so the
    // Plan 02 render-test mock (selector-only) keeps working. Filter to the active barony:
    // SelectionBridge normally loads only one barony, but a coupled neighbour vertex may
    // also be present, and it must not pollute the ring fit.
    const all = vertices
    const ringKeys = Object.keys(all).filter((k) => keyBarony(k) === activeTerritoryId)
    // Fallback: if no key matches activeTerritoryId (e.g. keys use a different prefix
    // scheme in some harness), fit over all vertices — preserves Plan 02 behavior.
    const orderedKeys = sortRingKeys(ringKeys.length > 0 ? ringKeys : Object.keys(all))
    const coords: Array<[number, number]> = orderedKeys.map((k) => {
      const v = all[k]
      return [v.lon, v.lat]
    })
    const cubics = fitPolygonToBezier(coords, projection)
    const pxPts: Array<[number, number]> = coords.map(([lon, lat]) => geoToCanvas(lon, lat, projection))
    const ranges = buildPolyIndexMap(pxPts, cubics)
    originalRef.current = { coords, pxPts, orderedKeys, baronyId: activeTerritoryId }
    setAnchors(deriveAnchors(cubics, ranges))
    setActiveAnchorIdx(null)
    setDirtyCount(0)
    rebuildSharedIndex(all)
    rebuildSnapCandidates(all, activeTerritoryId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isActive, activeTerritoryId, vertexCount, projection])

  // ── Shared-vertex index + snap candidates (mirror VertexEditLayer rebuild) ───
  const rebuildSharedIndex = useCallback(
    (all: Record<string, { lat: number; lon: number }>) => {
      const refs: VertexRef[] = Object.entries(all).map(([vid, v]) => ({
        vertexId: vid,
        baronyId: keyBarony(vid),
        lat: v.lat,
        lon: v.lon,
      }))
      sharedIndexRef.current = buildSharedVertexIndex(refs)
    },
    [],
  )

  const rebuildSnapCandidates = useCallback(
    (all: Record<string, { lat: number; lon: number }>, activeBarony: string) => {
      // Anchor snap targets = vertices that do NOT belong to the active barony
      // (neighbour barony vertices), same intent as VertexEditLayer snapCandidatesRef.
      snapCandidatesRef.current = Object.entries(all)
        .filter(([vid]) => keyBarony(vid) !== activeBarony)
        .map(([vid, v]) => ({ id: vid, lat: v.lat, lon: v.lon }))
    },
    [],
  )

  // Alt key tracking (snap disable for current drag — D-28 parity).
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.altKey) altHeldRef.current = true
    }
    const up = (e: KeyboardEvent) => {
      if (!e.altKey) altHeldRef.current = false
    }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
    }
  }, [])

  // ── Drag handlers (the ONLY store-writing path; op MUST be 'move') ───────────
  // Live preview during move — repaint only, no store write (UI-SPEC §Anchor step 1).
  const handleDragMove = useCallback(
    (kind: DragKind, idx: number, e: Konva.KonvaEventObject<DragEvent>) => {
      const center = draggedCenterPx(kind, e.target.x(), e.target.y())
      previewRef.current = { kind, idx, px: center }
      // Live preview: repaint the whole curve + handles following the drag (no store write).
      setPreviewAnchors(applyDragToAnchors(anchorsRef.current, kind, idx, center))
      setDirtyCount(idx === 0 || kind === 'cp2' ? 1 : 2)
    },
    [],
  )

  const handleDragEnd = useCallback(
    (kind: DragKind, idx: number, e: Konva.KonvaEventObject<DragEvent>) => {
      previewRef.current = null
      setPreviewAnchors(null)
      const curAnchors = anchorsRef.current
      const a = curAnchors[idx]
      if (!a) return
      const { orderedKeys, baronyId } = originalRef.current
      if (orderedKeys.length === 0) return

      // Konva center px of the dragged node (anchor Rect is top-left anchored → +5,+5).
      let finalPx = draggedCenterPx(kind, e.target.x(), e.target.y())

      // Snap (anchors only) — convert px → geo, snap to neighbour barony vertex, then use
      // the snapped position. Control-handle drags SKIP snap entirely (RESEARCH constraint 2).
      if (kind === 'anchor') {
        const stage = e.target.getStage?.()
        const stageScale = stage?.scaleX?.() ?? 1
        const [rawLon, rawLat] = canvasToGeo(finalPx[0], finalPx[1], projection)
        const snap = snapToNeighbour(
          { lat: rawLat, lon: rawLon },
          snapCandidatesRef.current,
          stageScale,
          altHeldRef.current,
        )
        if (snap) finalPx = geoToCanvas(snap.lon, snap.lat, projection)
      }

      // 1) Working anchors with the dragged element moved (rigid handle translation on
      //    anchor drag; single-handle move on control-handle drag — handled in the helper).
      const working = applyDragToAnchors(curAnchors, kind, idx, finalPx)

      // 2) Dirty segments. Segment s runs from anchor s (p0=anchorPx, c1=cp2Px) to
      //    anchor s+1 (c2=cp1Px of s+1, p3=anchorPx of s+1).
      //    Anchor idx drag affects segment idx-1 (ends at idx) and segment idx
      //    (starts at idx). cp2 of an anchor only shapes the OUTGOING segment idx;
      //    cp1 only shapes the INCOMING segment idx-1.
      const N = working.length
      const dirty = new Set<number>()
      const addSeg = (s: number) => {
        if (s >= 0 && s < N - 1) dirty.add(s) // segment N-1 is the non-editable closing segment
      }
      if (kind === 'anchor') {
        addSeg(idx - 1)
        addSeg(idx)
      } else if (kind === 'cp1') {
        addSeg(idx - 1)
      } else {
        addSeg(idx)
      }

      // 3) Flatten ONLY dirty segments; copy non-dirty ranges VERBATIM from store.
      const storeVerts = useEditorStore.getState().vertices
      const nextVertices: Record<string, { lat: number; lon: number }> = { ...storeVerts }
      const changedIds: string[] = []

      for (const s of dirty) {
        const startAnchor = working[s]
        const endAnchor = working[s + 1]
        // cubic for segment s in px: [p0, c1, c2, p3]
        const cubic: BezierCubic = [
          startAnchor.anchorPx,
          startAnchor.cp2Px, // outgoing handle of start anchor (c1, near p0)
          endAnchor.cp1Px, // incoming handle of end anchor (c2, near p3)
          endAnchor.anchorPx,
        ]
        const rangeStart = startAnchor.polyRangeStart
        const rangeEnd = startAnchor.polyRangeEnd
        const targetCount = rangeEnd - rangeStart + 1
        const flat = flattenSegment(cubic, targetCount, projection)
        for (let k = 0; k < targetCount; k++) {
          const key = orderedKeys[rangeStart + k]
          if (key === undefined) continue
          const [lon, lat] = flat[k]
          nextVertices[key] = { lat, lon }
          changedIds.push(key)
        }
      }

      if (changedIds.length === 0) {
        // closing-segment-only drag (no editable segment) — nothing to commit.
        setDirtyCount(0)
        return
      }

      // 4) Shared-vertex coupling — move coupled partners to the same coord.
      for (const id of [...changedIds]) {
        const coupled = getCoupledVertices(sharedIndexRef.current, id)
        if (coupled.length > 1) {
          const coord = nextVertices[id]
          for (const partner of coupled) {
            if (partner === id) continue
            nextVertices[partner] = { lat: coord.lat, lon: coord.lon }
            changedIds.push(partner)
          }
        }
      }

      // 5) Commit through the single chokepoint. op MUST be 'move' (never 'bezier_drag').
      useEditorStore.getState().setVerticesAndLog(nextVertices, {
        op: 'move',
        ts: Date.now(),
        vertexIds: changedIds,
      })

      // 6) Recompute display state from the updated store + refresh indices.
      const updated = useEditorStore.getState().vertices
      const refit = deriveAnchorsFromStore(
        Object.fromEntries(
          Object.entries(updated).filter(([k]) => keyBarony(k) === baronyId),
        ),
        projection,
      )
      const refitKeys = sortRingKeys(
        Object.keys(updated).filter((k) => keyBarony(k) === baronyId),
      )
      originalRef.current = {
        coords: refitKeys.map((k) => [updated[k].lon, updated[k].lat]),
        pxPts: refitKeys.map((k) => geoToCanvas(updated[k].lon, updated[k].lat, projection)),
        orderedKeys: refitKeys,
        baronyId,
      }
      setAnchors(refit)
      setDirtyCount(0)
      rebuildSharedIndex(updated)
      rebuildSnapCandidates(updated, baronyId)
    },
    [projection, rebuildSharedIndex, rebuildSnapCandidates],
  )

  // ── DEV-only escape hatch for the later Playwright reachability spec ─────────
  // Mirrors VertexEditLayer's __forgeEditorState pattern. dirtySegmentCount is 0 here;
  // the drag-commit plan makes it live. Cleaned up on unmount so it never leaks.
  useEffect(() => {
    if (!import.meta.env.DEV) return
    ;(window as unknown as { __forgeBezierState?: () => unknown }).__forgeBezierState = () => ({
      anchorCount: anchors.length,
      activeAnchorIdx,
      dirtySegmentCount: dirtyCount,
    })
    return () => {
      delete (window as unknown as { __forgeBezierState?: unknown }).__forgeBezierState
    }
  }, [anchors.length, activeAnchorIdx, dirtyCount])

  // During a drag, render the curve outline + handles from the live preview so the WHOLE
  // curve follows the drag (UI-SPEC §Anchor step 1) — not just the dragged Konva node.
  // The anchor squares keep rendering from committed `anchors` so the dragged Konva node
  // (which Konva positions internally during the gesture) is not fought by a React re-pos.
  const displayAnchors = previewAnchors ?? anchors
  const pathData = useMemo(() => buildPathData(displayAnchors), [displayAnchors])

  if (!isActive || anchors.length === 0) {
    return null
  }

  return (
    <Layer
      onClick={(e) => {
        // Click on empty background (the Layer itself) clears the active anchor.
        if (e.target === e.currentTarget) setActiveAnchorIdx(null)
      }}
    >
      {/* Curve outline — static, non-interactive */}
      <Path
        data={pathData}
        stroke={CURVE_STROKE}
        strokeWidth={2}
        fill="transparent"
        listening={false}
        data-testid="bezier-curve-outline"
      />

      {/* Anchors — one square per cubic endpoint */}
      {anchors.map((a) => {
        const fill =
          a.idx === activeAnchorIdx
            ? ANCHOR_ACTIVE_FILL
            : a.idx === hoverAnchorIdx
              ? ANCHOR_HOVER_FILL
              : ANCHOR_INACTIVE_FILL
        return (
          <Rect
            key={`anchor-${a.idx}`}
            x={a.anchorPx[0] - 5}
            y={a.anchorPx[1] - 5}
            width={10}
            height={10}
            fill={fill}
            draggable
            onClick={() => setActiveAnchorIdx(a.idx)}
            onDragStart={() => setActiveAnchorIdx(a.idx)}
            onDragMove={(e: Konva.KonvaEventObject<DragEvent>) => handleDragMove('anchor', a.idx, e)}
            onDragEnd={(e: Konva.KonvaEventObject<DragEvent>) => handleDragEnd('anchor', a.idx, e)}
            onMouseEnter={() => setHoverAnchorIdx(a.idx)}
            onMouseLeave={() => setHoverAnchorIdx((cur) => (cur === a.idx ? null : cur))}
            data-testid="bezier-anchor"
            data-anchor-idx={a.idx}
          />
        )
      })}

      {/* Control handles + tethers — active anchor ONLY (follows live preview during drag) */}
      {activeAnchorIdx !== null &&
        displayAnchors[activeAnchorIdx] &&
        (() => {
          const a = displayAnchors[activeAnchorIdx]
          return (
            <React.Fragment key={`handles-${a.idx}`}>
              <Line
                points={[a.anchorPx[0], a.anchorPx[1], a.cp1Px[0], a.cp1Px[1]]}
                stroke={TETHER_STROKE}
                strokeWidth={1}
                dash={[4, 4]}
                listening={false}
                data-testid="bezier-tether"
              />
              <Line
                points={[a.anchorPx[0], a.anchorPx[1], a.cp2Px[0], a.cp2Px[1]]}
                stroke={TETHER_STROKE}
                strokeWidth={1}
                dash={[4, 4]}
                listening={false}
                data-testid="bezier-tether"
              />
              <Circle
                x={a.cp1Px[0]}
                y={a.cp1Px[1]}
                radius={4}
                fill={HANDLE_FILL}
                draggable
                onDragMove={(e: Konva.KonvaEventObject<DragEvent>) => handleDragMove('cp1', a.idx, e)}
                onDragEnd={(e: Konva.KonvaEventObject<DragEvent>) => handleDragEnd('cp1', a.idx, e)}
                data-testid="bezier-handle"
                data-handle-kind="cp1"
              />
              <Circle
                x={a.cp2Px[0]}
                y={a.cp2Px[1]}
                radius={4}
                fill={HANDLE_FILL}
                draggable
                onDragMove={(e: Konva.KonvaEventObject<DragEvent>) => handleDragMove('cp2', a.idx, e)}
                onDragEnd={(e: Konva.KonvaEventObject<DragEvent>) => handleDragEnd('cp2', a.idx, e)}
                data-testid="bezier-handle"
                data-handle-kind="cp2"
              />
            </React.Fragment>
          )
        })()}
    </Layer>
  )
}

export default BezierEditLayer
