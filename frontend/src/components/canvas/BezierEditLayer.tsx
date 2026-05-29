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
 *   control handle  #e879f9 magenta (Circle r=4, active anchor only) — distinct from tether
 *   tether          #94a3b8 slate-gray width 1 dash [4,4] listening=false (active anchor only)
 *   curve outline   #22c55e green width 2 fill transparent listening=false
 * [G4 fix Plan 08.1-05]: CURVE_STROKE changed #4a9eff→#22c55e (was same as ANCHOR_INACTIVE_FILL,
 *   collision resolved). HANDLE_FILL changed #94a3b8→#e879f9 (was same as TETHER_STROKE).
 *   5 visually distinct colors: green / blue / amber / white / magenta / slate-gray.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type Konva from 'konva'
import { Layer, Path, Rect, Circle, Line } from 'react-konva'
import { useEditorStore } from '../../stores/useEditorStore'
import {
  fitPolygonToBezier,
  buildPolyIndexMap,
  splitPolyRange,
  findNearestSegmentAndVertex,
  type BezierCubic,
} from '../../lib/bezierFit'
import { flattenSegment, cubicBezierAt } from '../../lib/bezierFlatten'
import { geoToCanvas, canvasToGeo, type ProjectionConfig } from '../../lib/projection'
import { snapToNeighbour } from '../../lib/snap'
import type { SnapCandidate } from '../../lib/snap'
import {
  buildSharedVertexIndex,
  getCoupledVertices,
  type SharedVertexIndex,
  type VertexRef,
} from '../../lib/sharedVertex'

// UI-SPEC Konva color literals (G4 fix: 5 visually distinct hexes — no collision)
export const ANCHOR_INACTIVE_FILL = '#4a9eff'  // inactive anchor — blue
export const ANCHOR_ACTIVE_FILL = '#f0c040'    // active anchor — amber
export const ANCHOR_HOVER_FILL = '#ffffff'      // hover — white
export const HANDLE_FILL = '#e879f9'            // control handle — magenta (distinct from tether)
export const TETHER_STROKE = '#94a3b8'          // tether line — slate-gray
export const CURVE_STROKE = '#22c55e'           // curve outline — green (was #4a9eff, collided with inactive anchor)

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
  /** Live stage scale from CanvasViewer — used to keep anchor/handle/hit-path sizes
   *  constant in screen space (= BASE / currentScale, mirroring DecorationsLayer). */
  currentScale: number
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

/** Build the SVG cubic path string for the full curve outline (RESEARCH §Pattern 3).
 * Emits N cubic C commands (N === anchors.length), including the wrap-around closing
 * segment anchor[N-1] → anchor[0], so the outline forms a fully closed ring (G1).
 */
export function buildPathData(anchors: BezierAnchor[]): string {
  if (anchors.length === 0) return ''
  let d = `M ${anchors[0].anchorPx[0]} ${anchors[0].anchorPx[1]}`
  for (let i = 0; i < anchors.length - 1; i++) {
    const { cp2Px } = anchors[i]
    const { cp1Px, anchorPx } = anchors[i + 1]
    d += ` C ${cp2Px[0]} ${cp2Px[1]} ${cp1Px[0]} ${cp1Px[1]} ${anchorPx[0]} ${anchorPx[1]}`
  }
  // Closing segment: anchor[N-1] → anchor[0] — uses last anchor's cp2Px (outgoing) and
  // anchor[0]'s cp1Px (incoming from the closing segment). This is the G1 fix: the outline
  // now forms a closed loop with exactly N cubic commands (not N-1, which left the ring open).
  const lastA = anchors[anchors.length - 1]
  const firstA = anchors[0]
  d += ` C ${lastA.cp2Px[0]} ${lastA.cp2Px[1]} ${firstA.cp1Px[0]} ${firstA.cp1Px[1]} ${firstA.anchorPx[0]} ${firstA.anchorPx[1]}`
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
      // anchor); for anchor 0 it comes from the LAST cubic's c2 (c2 of the closing segment
      // cubic), connecting the incoming handle of anchor 0 to the closing segment (G1 fix).
      cp1Px: j > 0
        ? [cubics[j - 1][2][0], cubics[j - 1][2][1]]
        : [cubics[cubics.length - 1][2][0], cubics[cubics.length - 1][2][1]],
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
 * (`x = anchorPx - anchorHalf`), so after a drag `e.target.x()` is the new top-left
 * and the true anchor CENTER is `x() + anchorHalf, y() + anchorHalf`. Control handles
 * are Circles (center-anchored) so their reported px IS the center.
 * anchorHalf must be the LIVE half-size (= ANCHOR_BASE_PX / safeScale / 2) to stay in
 * sync with the Rect offset — a desync would commit the drag to the wrong center (T-08.1-07-01).
 */
function draggedCenterPx(kind: DragKind, x: number, y: number, anchorHalf: number): [number, number] {
  return kind === 'anchor' ? [x + anchorHalf, y + anchorHalf] : [x, y]
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

export const BezierEditLayer: React.FC<BezierEditLayerProps> = ({ projection, currentScale }) => {
  // Screen-space sizing constants (G5): all interactive nodes keep a constant on-screen
  // size by dividing their map-space base value by the live stage scale — mirroring the
  // DecorationsLayer `value / safeScale` inversion pattern (already shipping).
  const ANCHOR_BASE_PX = 10      // on-screen square size
  const HANDLE_BASE_PX = 9       // on-screen handle diameter → radius = HANDLE_BASE_PX / 2 / safeScale
  const HITPATH_BASE_PX = 24     // on-screen dbl-click target width (wider than before for real dblclick — G7)
  const TETHER_BASE_PX = 1.5     // on-screen tether stroke width
  const CURVE_BASE_PX = 2        // on-screen curve outline stroke width
  const safeScale = currentScale > 0 ? currentScale : 1   // guard against 0/NaN (T-08.1-07-02)
  const anchorSize = ANCHOR_BASE_PX / safeScale
  const anchorHalf = anchorSize / 2
  const handleRadius = (HANDLE_BASE_PX / 2) / safeScale
  const hitPathWidth = HITPATH_BASE_PX / safeScale
  const tetherWidth = TETHER_BASE_PX / safeScale
  const curveWidth = CURVE_BASE_PX / safeScale

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
  // Live half-size ref — updated every render so draggedCenterPx and the DEV drag hook
  // always use the current anchorHalf (T-08.1-07-01: desync guard).
  const anchorHalfRef = useRef(anchorHalf)
  anchorHalfRef.current = anchorHalf
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
  // Plan 04 (BEZ-UAT-01): ref to the Konva Layer so __forgeBezierState can read a
  // rendered anchor's absolute SCREEN position for a real Playwright Konva mouse drag
  // (the canvas is opaque to DOM queries — mirrors VertexEditLayer's firstHandle hatch).
  const layerRef = useRef<Konva.Layer | null>(null)

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

  // ── Insert handler (G3 — double-click inserts anchor; pure component-local NO-OP) ──
  // A bare insert does NOT call setVerticesAndLog — store stays byte-identical (BEZ-IDENTITY-01).
  // The new anchor snaps to the nearest original polygon vertex strictly inside the segment's
  // range so both sub-ranges remain valid integer-bounded contiguous ranges (splitPolyRange
  // shared-endpoint convention). cp1Px/cp2Px are derived from the local tangent for display
  // only; the first commit happens on a subsequent drag via the existing op:'move' path.
  const handleInsertAtPx = useCallback((clickPx: [number, number]): boolean => {
    const cur = anchorsRef.current
    const pxPts = originalRef.current.pxPts
    if (cur.length < 2 || pxPts.length === 0) return false

    const hit = findNearestSegmentAndVertex(clickPx, cur, pxPts)
    if (hit === null) return false

    const { segmentIdx, splitVertexIndex } = hit
    const a = cur[segmentIdx]
    const N = cur.length
    const b = cur[(segmentIdx + 1) % N]

    // Snap the new anchor to the actual original polygon vertex (integer index)
    const snapPx = pxPts[splitVertexIndex]
    if (!snapPx) return false

    // Split the segment's poly range at the snap vertex
    const [leftRange, rightRange] = splitPolyRange(
      { rangeStart: a.polyRangeStart, rangeEnd: a.polyRangeEnd },
      splitVertexIndex,
    )

    // Derive cp1/cp2 for the new anchor from the cubic tangent at t≈0.5.
    // The tangent direction gives a small display-only handle; the actual geometry
    // is committed verbatim from the store on the next drag (no store write here).
    // Derive cp1/cp2 tangent direction from the cubic at t=0.5 using a small finite difference.
    const cubic: BezierCubic = [a.anchorPx, a.cp2Px, b.cp1Px, b.anchorPx]
    const midNext = cubicBezierAt(cubic[0], cubic[1], cubic[2], cubic[3], 0.55)
    const midPrev = cubicBezierAt(cubic[0], cubic[1], cubic[2], cubic[3], 0.45)
    const tanDx = midNext[0] - midPrev[0]
    const tanDy = midNext[1] - midPrev[1]
    const tanLen = Math.sqrt(tanDx * tanDx + tanDy * tanDy) || 1
    const handleOffset = 15
    const normX = (tanDx / tanLen) * handleOffset
    const normY = (tanDy / tanLen) * handleOffset

    const newAnchor: BezierAnchor = {
      idx: segmentIdx + 1, // will be renumbered below
      anchorPx: [snapPx[0], snapPx[1]],
      cp1Px: [snapPx[0] - normX, snapPx[1] - normY],
      cp2Px: [snapPx[0] + normX, snapPx[1] + normY],
      polyRangeStart: rightRange.rangeStart,
      polyRangeEnd: rightRange.rangeEnd,
    }

    // Update the split anchor (the original segment anchor now covers only the left sub-range)
    const next: BezierAnchor[] = cur.map((anchor) =>
      anchor.idx === a.idx
        ? { ...anchor, polyRangeStart: leftRange.rangeStart, polyRangeEnd: leftRange.rangeEnd }
        : { ...anchor },
    )

    // Insert the new anchor after segmentIdx and renumber all idx fields
    next.splice(segmentIdx + 1, 0, newAnchor)
    next.forEach((anchor, i) => { anchor.idx = i })

    // Component-local only — zero store writes (identity-safe insert, BEZ-IDENTITY-01)
    setAnchors(next)
    setActiveAnchorIdx(segmentIdx + 1)
    return true
  }, [])

  // ── Drag handlers (the ONLY store-writing path; op MUST be 'move') ───────────
  // Live preview during move — repaint only, no store write (UI-SPEC §Anchor step 1).
  const handleDragMove = useCallback(
    (kind: DragKind, idx: number, e: Konva.KonvaEventObject<DragEvent>) => {
      const center = draggedCenterPx(kind, e.target.x(), e.target.y(), anchorHalfRef.current)
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

      // Konva center px of the dragged node (anchor Rect is top-left anchored → +anchorHalf).
      let finalPx = draggedCenterPx(kind, e.target.x(), e.target.y(), anchorHalfRef.current)

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
      //    anchor (s+1)%N (c2=cp1Px of (s+1)%N, p3=anchorPx of (s+1)%N).
      //    Anchor idx drag affects segment idx-1 (ends at idx) and segment idx
      //    (starts at idx). cp2 of an anchor only shapes the OUTGOING segment idx;
      //    cp1 only shapes the INCOMING segment (idx-1). For idx=0 the INCOMING
      //    segment is the closing segment N-1 (the wrap-around), not -1. (G2 fix)
      const N = working.length
      const dirty = new Set<number>()
      const addSeg = (s: number) => {
        if (s >= 0 && s < N) dirty.add(s) // all N segments editable incl. closing segment N-1 (G1)
      }
      // For anchor 0: cp1 shapes the closing segment N-1 (incoming = wrap-around from last anchor).
      // For anchor 0: anchor drag also affects the closing segment (the outgoing of the previous,
      // which wraps from N-1 back to 0). Use (idx - 1 + N) % N to resolve wrap correctly.
      const incomingSeg = (idx - 1 + N) % N // closing segment for idx=0
      if (kind === 'anchor') {
        addSeg(incomingSeg)
        addSeg(idx)
      } else if (kind === 'cp1') {
        // cp1 shapes the INCOMING segment of this anchor (the segment that ENDS at this anchor)
        addSeg(incomingSeg)
      } else {
        addSeg(idx)
      }

      // 3) Flatten ONLY dirty segments; copy non-dirty ranges VERBATIM from store.
      const storeVerts = useEditorStore.getState().vertices
      const nextVertices: Record<string, { lat: number; lon: number }> = { ...storeVerts }
      const changedIds: string[] = []

      for (const s of dirty) {
        const startAnchor = working[s]
        const endAnchor = working[(s + 1) % N] // wrap-around: closing segment (s=N-1) uses anchor[0]
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
      // WR-02: clamp activeAnchorIdx so it never silently points past the new array length.
      // After a commit-refit that yields fewer cubics, a stale activeAnchorIdx would make
      // displayAnchors[activeAnchorIdx] undefined and the handles/tethers disappear silently.
      setActiveAnchorIdx((cur) => (cur === null ? null : Math.min(cur, refit.length - 1)))
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
    ;(window as unknown as { __forgeBezierState?: () => unknown }).__forgeBezierState = () => {
      // Plan 04 (BEZ-UAT-01): resolve the first rendered anchor's SCREEN coords so a
      // Playwright spec can drive a REAL Konva mouse drag (canvas is opaque to the DOM).
      // Mirrors VertexEditLayer.firstHandle: abs position (stage scale+pos applied) +
      // the canvas container's page offset. Returns null if no anchor is mounted.
      let firstAnchor: { idx: number; x: number; y: number } | null = null
      const layer = layerRef.current
      if (layer) {
        try {
          const stage = layer.getStage()
          const rect = layer.find('Rect').find((n) => n.getAttr('data-testid') === 'bezier-anchor')
          if (stage && rect) {
            // Compute firstAnchor page coords from anchorPx (map-space) + stage transform.
            // getClientRect({relativeTo:stage}) returns map-space px (before stage scale/pos).
            // To reach PAGE coords: containerOffset + stage.position + anchorMapPx * stageScale.
            // anchorPx is the stage-local (map-space) center of the anchor square.
            // We read it directly from the stored anchor rather than from Konva to avoid
            // any getClientRect coordinate-space ambiguity.
            const containerRect = stage.container().getBoundingClientRect()
            const stageScale = stage.scaleX()
            const stageX = stage.x()
            const stageY = stage.y()
            // anchorPx is the stored center of the anchor square in map space.
            // The anchor Rect is drawn at (anchorPx - anchorHalf), but its center is anchorPx.
            const a0 = anchorsRef.current[0]
            if (a0) {
              firstAnchor = {
                idx: 0,
                x: containerRect.left + stageX + a0.anchorPx[0] * stageScale,
                y: containerRect.top  + stageY + a0.anchorPx[1] * stageScale,
              }
            }
          }
        } catch {
          // In jsdom/unit-test environments the Konva mock doesn't provide getStage();
          // firstAnchor stays null — anchorCount/activeAnchorIdx/editLogLength are still valid.
        }
      }
      // Plan 07 (G7): expose a MID-SEGMENT on-curve point between anchor 0 and anchor 1
      // as PAGE coords for the real dblclick target in the new spec. This is READ-ONLY
      // inspection — NOT a trigger hook. Returns null if < 2 anchors.
      //
      // COORDINATE CONVERSION (mirrors firstAnchor's getClientRect approach):
      // anchorPx values are STAGE-LOCAL px (layer content coords, no stage transform applied).
      // To reach PAGE coords: apply stage scale + position, then add container page offset.
      //   screenX = containerRect.left + stage.x() + stagePx.x * stage.scaleX()
      //   screenY = containerRect.top  + stage.y() + stagePx.y * stage.scaleY()
      // This matches how getClientRect({relativeTo:stage}) works for rendered Rect nodes.
      let midCurvePoint: { x: number; y: number } | null = null
      const anchorsList = anchorsRef.current
      if (layer && anchorsList.length >= 2) {
        try {
          const stage = layer.getStage()
          if (stage) {
            const a0 = anchorsList[0]
            const a1 = anchorsList[1]
            // Stage-local px at t=0.5 of the cubic from anchor 0 to anchor 1
            const midStagePx = cubicBezierAt(a0.anchorPx, a0.cp2Px, a1.cp1Px, a1.anchorPx, 0.5)
            // Convert stage-local px → page coords using stage transform + container offset
            const containerRect = stage.container().getBoundingClientRect()
            const stageScale = stage.scaleX()
            const stagePosX = stage.x()
            const stagePosY = stage.y()
            midCurvePoint = {
              x: containerRect.left + stagePosX + midStagePx[0] * stageScale,
              y: containerRect.top  + stagePosY + midStagePx[1] * stageScale,
            }
          }
        } catch {
          // jsdom/unit-test: Konva mock doesn't provide stage methods; midCurvePoint stays null.
        }
      }
      return {
        anchorCount: anchors.length,
        activeAnchorIdx,
        dirtySegmentCount: dirtyCount,
        editLogLength: useEditorStore.getState().editLog.length,
        firstAnchor, // { idx, x, y } page coords for page.mouse, or null
        midCurvePoint, // { x, y } page coords of mid-segment on-curve point (between anchor 0 and 1), or null
      }
    }
    // Plan 04 (BEZ-UAT-01, plan-sanctioned DEV-hook drag — Task 2 <action> "or use a DEV
    // hook to trigger a drag"): synthesize an anchor drag by invoking the SAME real
    // handlers (handleDragMove + handleDragEnd) the Konva onDrag* props call. This flows
    // through flattenSegment → setVerticesAndLog(op:'move') — it is NOT a direct store
    // write (which would be useEditorStore.getState().setVerticesAndLog(...)). A real
    // page.mouse drag on the ~3px anchor square at Iberia fit-to-view scale is too brittle
    // to be deterministic; this hook drives the identical commit path.
    ;(window as unknown as {
      __forgeBezierTriggerDrag?: (idx?: number, dx?: number, dy?: number) => boolean
    }).__forgeBezierTriggerDrag = (idx = 0, dx = 30, dy = 30) => {
      const a = anchorsRef.current[idx]
      if (!a) return false
      // onDrag* read e.target.x()/y() as the Rect TOP-LEFT (anchorPx - anchorHalf);
      // draggedCenterPx adds +anchorHalf back to recover the center.
      // MUST use anchorHalfRef.current (not the literal 5) so this stays in sync with
      // the live Rect offset after sizing changes (T-08.1-07-01: silent third "5" site).
      const targetX = a.anchorPx[0] - anchorHalfRef.current + dx
      const targetY = a.anchorPx[1] - anchorHalfRef.current + dy
      // In jsdom/unit-test the Konva mock doesn't provide getStage(); fall back to null.
      const stage = (() => { try { return layerRef.current?.getStage() } catch { return null } })()
      const evt = {
        target: { x: () => targetX, y: () => targetY, getStage: () => stage },
      } as unknown as Konva.KonvaEventObject<DragEvent>
      handleDragMove('anchor', idx, evt)
      handleDragEnd('anchor', idx, evt)
      return true
    }
    // Plan 05 (G2 closing-segment re-verify): handle-drag DEV hook for Playwright.
    // Mirrors __forgeBezierTriggerDrag but for CONTROL HANDLES (Circles, center-anchored).
    // CRITICAL: handles are center-anchored (not top-left like anchor Rects), so
    // draggedCenterPx('cp1'|'cp2', x, y) returns [x, y] with NO +5 offset.
    // Therefore: targetX = cp1Px[0] + dx (NOT cp1Px[0] - 5 + dx, which is Rect-specific).
    ;(window as unknown as {
      __forgeBezierTriggerHandleDrag?: (kind?: 'cp1' | 'cp2', idx?: number, dx?: number, dy?: number) => boolean
    }).__forgeBezierTriggerHandleDrag = (kind = 'cp1', idx = 0, dx = 25, dy = 25) => {
      const a = anchorsRef.current[idx]
      if (!a) return false
      // Center-anchored Circle: no -5 offset (unlike anchor Rect which uses anchorPx-5).
      // This is the center-anchored offset CRITICAL noted in the plan spec.
      const targetX = (kind === 'cp1' ? a.cp1Px[0] : a.cp2Px[0]) + dx
      const targetY = (kind === 'cp1' ? a.cp1Px[1] : a.cp2Px[1]) + dy
      // In jsdom/unit-test the Konva mock doesn't provide getStage(); fall back to null.
      const stage = (() => { try { return layerRef.current?.getStage() } catch { return null } })()
      const evt = {
        target: { x: () => targetX, y: () => targetY, getStage: () => stage },
      } as unknown as Konva.KonvaEventObject<DragEvent>
      handleDragMove(kind, idx, evt)
      handleDragEnd(kind, idx, evt)
      return true
    }
    // Plan 06 (G3 insert re-verify): index-based insert DEV hook for Playwright + unit tests.
    // COORDINATE-SPACE NOTE: __forgeBezierState().firstAnchor exposes PAGE coords (built for
    // page.mouse). They are NOT usable as hit-test input for findNearestSegmentAndVertex, which
    // expects STAGE-LOCAL px. This hook is INDEX-based: it computes its own stage-local mid-curve
    // px from segmentIdx so callers never supply px coords (avoiding the page-vs-stage trap).
    // Signature: __forgeBezierTriggerInsert(segmentIdx?: number): boolean  (default segmentIdx=0)
    ;(window as unknown as {
      __forgeBezierTriggerInsert?: (segmentIdx?: number) => boolean
    }).__forgeBezierTriggerInsert = (segmentIdx = 0) => {
      const a = anchorsRef.current[segmentIdx]
      const N = anchorsRef.current.length
      const b = anchorsRef.current[(segmentIdx + 1) % N]
      if (!a || !b) return false
      // Compute the stage-local px at the cubic mid-point (t=0.5). This is the SAME px space
      // the anchors live in, so findNearestSegmentAndVertex will hit segment segmentIdx reliably.
      const midPx = cubicBezierAt(a.anchorPx, a.cp2Px, b.cp1Px, b.anchorPx, 0.5)
      // Delegate to the SAME real insert handler the dbl-click uses — never setAnchors directly.
      return handleInsertAtPx(midPx)
    }
    // Plan 07 (G5/G7 Playwright setup): pan the Konva Stage so the mid-curve point between
    // anchor 0 and anchor 1 is at the viewport center. This ensures both the drag target
    // (anchor 0 near center) and the dblclick target (midCurvePoint between 0 and 1) are
    // in the visible area and not obscured by DOM overlays (Layers panel on left edge).
    // Read-only state access + imperative stage mutation only (no store write, no React change).
    ;(window as unknown as {
      __forgePanToFirstAnchor?: () => boolean
    }).__forgePanToFirstAnchor = () => {
      const a0 = anchorsRef.current[0]
      const a1 = anchorsRef.current[1]
      if (!a0) return false
      const layer = layerRef.current
      if (!layer) return false
      try {
        const stage = layer.getStage()
        if (!stage) return false
        const scale = stage.scaleX()
        const containerRect = stage.container().getBoundingClientRect()
        const vw = containerRect.width
        const vh = containerRect.height
        // Center on mid-curve point between anchor 0 and anchor 1 (t=0.5) if ≥2 anchors,
        // otherwise center on anchor 0. The mid-curve point is the dblclick target (G7).
        const targetPx = a1
          ? cubicBezierAt(a0.anchorPx, a0.cp2Px, a1.cp1Px, a1.anchorPx, 0.5)
          : a0.anchorPx
        const newX = vw / 2 - targetPx[0] * scale
        const newY = vh / 2 - targetPx[1] * scale
        stage.x(newX)
        stage.y(newY)
        stage.batchDraw()
        return true
      } catch {
        return false
      }
    }
    return () => {
      delete (window as unknown as { __forgeBezierState?: unknown }).__forgeBezierState
      delete (window as unknown as { __forgeBezierTriggerDrag?: unknown }).__forgeBezierTriggerDrag
      delete (window as unknown as { __forgeBezierTriggerHandleDrag?: unknown }).__forgeBezierTriggerHandleDrag
      delete (window as unknown as { __forgeBezierTriggerInsert?: unknown }).__forgeBezierTriggerInsert
      delete (window as unknown as { __forgePanToFirstAnchor?: unknown }).__forgePanToFirstAnchor
    }
  }, [anchors.length, activeAnchorIdx, dirtyCount, handleDragMove, handleDragEnd, handleInsertAtPx])

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
      ref={layerRef}
      onClick={(e) => {
        // Click on empty background (the Layer itself) clears the active anchor.
        if (e.target === e.currentTarget) setActiveAnchorIdx(null)
      }}
    >
      {/* Curve outline — static, non-interactive (BEZ-RENDER: MUST stay listening={false}) */}
      <Path
        data={pathData}
        stroke={CURVE_STROKE}
        strokeWidth={curveWidth}
        fill="transparent"
        listening={false}
        data-testid="bezier-curve-outline"
      />

      {/* Dedicated double-click hit-Path — transparent wider stroke for easy dbl-click target.
          SEPARATE from the visible outline so the outline stays listening={false} (BEZ-RENDER).
          hitPathWidth = HITPATH_BASE_PX / safeScale keeps the target constant in screen space (G7).
          hitStrokeWidth is set explicitly so Konva's hit canvas uses the wider stroke for detection.
          onDblClick resolves the pointer position and delegates to handleInsertAtPx. */}
      <Path
        data={pathData}
        stroke="transparent"
        strokeWidth={hitPathWidth}
        hitStrokeWidth={hitPathWidth}
        fill={undefined}
        listening={true}
        data-testid="bezier-hit-path"
        onDblClick={(e: Konva.KonvaEventObject<MouseEvent>) => {
          const stage = e.target.getStage()
          if (!stage) return
          // getRelativePointerPosition() inverts the node's absolute transform to return
          // map-space px — the same coordinate space as anchorPx / pxPts in handleInsertAtPx.
          // CRITICAL: stage.getPointerPosition() returns SCREEN px (container-relative), NOT
          // map-space. At any non-identity scale/pan, screen px ≠ map px by hundreds of pixels,
          // causing findNearestSegmentAndVertex to find nothing and insert to silently fail.
          // getRelativePointerPosition() on the stage accounts for scale+position and gives
          // the correct map-space coord. (G7 fix — Plan 07)
          const pos = stage.getRelativePointerPosition()
          if (!pos) {
            // Fallback: convert clientX/clientY manually via stage transform
            if (!e.evt) return
            const containerRect = stage.container().getBoundingClientRect()
            const stageScale = stage.scaleX()
            const stageX = stage.x()
            const stageY = stage.y()
            const mapX = (e.evt.clientX - containerRect.left - stageX) / stageScale
            const mapY = (e.evt.clientY - containerRect.top  - stageY) / stageScale
            handleInsertAtPx([mapX, mapY])
            return
          }
          // pos is map-space px (stage.getRelativePointerPosition inverts scale+position)
          handleInsertAtPx([pos.x, pos.y])
        }}
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
            x={a.anchorPx[0] - anchorHalf}
            y={a.anchorPx[1] - anchorHalf}
            width={anchorSize}
            height={anchorSize}
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
                strokeWidth={tetherWidth}
                dash={[4, 4]}
                listening={false}
                data-testid="bezier-tether"
              />
              <Line
                points={[a.anchorPx[0], a.anchorPx[1], a.cp2Px[0], a.cp2Px[1]]}
                stroke={TETHER_STROKE}
                strokeWidth={tetherWidth}
                dash={[4, 4]}
                listening={false}
                data-testid="bezier-tether"
              />
              <Circle
                x={a.cp1Px[0]}
                y={a.cp1Px[1]}
                radius={handleRadius}
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
                radius={handleRadius}
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
