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
import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Layer, Path, Rect, Circle, Line } from 'react-konva'
import { useEditorStore } from '../../stores/useEditorStore'
import {
  fitPolygonToBezier,
  buildPolyIndexMap,
  type BezierCubic,
} from '../../lib/bezierFit'
import { geoToCanvas, type ProjectionConfig } from '../../lib/projection'

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
    const [p0, c1, c2] = cubics[j]
    const range = ranges[j] ?? { rangeStart: 0, rangeEnd: 0 }
    anchors.push({
      idx: j,
      anchorPx: [p0[0], p0[1]],
      // incoming handle: previous cubic's c2 if available, else this cubic's c1
      cp1Px: j > 0 ? [cubics[j - 1][2][0], cubics[j - 1][2][1]] : [c1[0], c1[1]],
      cp2Px: [c2[0], c2[1]],
      polyRangeStart: range.rangeStart,
      polyRangeEnd: range.rangeEnd,
    })
  }
  return anchors
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
  // Original ordered coords + px points, retained for the later flatten path (Plan 03).
  const originalRef = useRef<{
    coords: Array<[number, number]>
    pxPts: Array<[number, number]>
  }>({ coords: [], pxPts: [] })

  // ── Fit on entry / activeTerritoryId change ─────────────────────────────────
  // vertices are loaded once by SelectionBridge and stable for the layer's life, so the
  // dep is activeTerritoryId (+ count as a cheap identity key). We DO NOT write the store.
  useEffect(() => {
    if (!isActive) {
      setAnchors([])
      setActiveAnchorIdx(null)
      originalRef.current = { coords: [], pxPts: [] }
      return
    }
    const orderedKeys = sortRingKeys(Object.keys(vertices))
    const coords: Array<[number, number]> = orderedKeys.map((k) => {
      const v = vertices[k]
      return [v.lon, v.lat]
    })
    const cubics = fitPolygonToBezier(coords, projection)
    const pxPts: Array<[number, number]> = coords.map(([lon, lat]) => geoToCanvas(lon, lat, projection))
    const ranges = buildPolyIndexMap(pxPts, cubics)
    originalRef.current = { coords, pxPts }
    setAnchors(deriveAnchors(cubics, ranges))
    setActiveAnchorIdx(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isActive, activeTerritoryId, vertexCount, projection])

  // ── DEV-only escape hatch for the later Playwright reachability spec ─────────
  // Mirrors VertexEditLayer's __forgeEditorState pattern. dirtySegmentCount is 0 here;
  // the drag-commit plan makes it live. Cleaned up on unmount so it never leaks.
  useEffect(() => {
    if (!import.meta.env.DEV) return
    ;(window as unknown as { __forgeBezierState?: () => unknown }).__forgeBezierState = () => ({
      anchorCount: anchors.length,
      activeAnchorIdx,
      dirtySegmentCount: 0,
    })
    return () => {
      delete (window as unknown as { __forgeBezierState?: unknown }).__forgeBezierState
    }
  }, [anchors.length, activeAnchorIdx])

  const pathData = useMemo(() => buildPathData(anchors), [anchors])

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
            onClick={() => setActiveAnchorIdx(a.idx)}
            onMouseEnter={() => setHoverAnchorIdx(a.idx)}
            onMouseLeave={() => setHoverAnchorIdx((cur) => (cur === a.idx ? null : cur))}
            data-testid="bezier-anchor"
            data-anchor-idx={a.idx}
          />
        )
      })}

      {/* Control handles + tethers — active anchor ONLY */}
      {activeAnchorIdx !== null &&
        anchors[activeAnchorIdx] &&
        (() => {
          const a = anchors[activeAnchorIdx]
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
                data-testid="bezier-handle"
              />
              <Circle
                x={a.cp2Px[0]}
                y={a.cp2Px[1]}
                radius={4}
                fill={HANDLE_FILL}
                data-testid="bezier-handle"
              />
            </React.Fragment>
          )
        })()}
    </Layer>
  )
}

export default BezierEditLayer
