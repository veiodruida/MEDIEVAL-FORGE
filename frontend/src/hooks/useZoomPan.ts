import type Konva from 'konva'
import { geoToCanvas, type ProjectionConfig } from '../lib/projection'

export const SCALE_BY = 1.05
export const MAX_SCALE_MULTIPLIER = 4

export interface PanClampConfig {
  mapW: number
  mapH: number
}

/**
 * Clamp stage position so the scaled map stays within the viewport.
 * When the scaled map is smaller than the viewport on an axis, center it on that axis.
 * When larger, prevent scrolling past the map edges.
 */
export function applyPanClamp(
  stage: Konva.Stage,
  scale: number,
  cfg: PanClampConfig,
): void {
  const scaledW = cfg.mapW * scale
  const scaledH = cfg.mapH * scale
  const vw = stage.width()
  const vh = stage.height()
  let x = stage.x()
  let y = stage.y()
  if (scaledW <= vw) {
    x = (vw - scaledW) / 2
  } else {
    x = Math.min(0, Math.max(vw - scaledW, x))
  }
  if (scaledH <= vh) {
    y = (vh - scaledH) / 2
  } else {
    y = Math.min(0, Math.max(vh - scaledH, y))
  }
  stage.position({ x, y })
}

/**
 * Cursor-anchored wheel zoom. RESEARCH §Pattern 4 + §Example 4.
 * - deltaY < 0 → zoom in by SCALE_BY
 * - deltaY > 0 → zoom out by SCALE_BY
 * - clamped to [minScale, maxScale]
 * - anchors the zoom at the pointer position (pointer → world coord stays fixed)
 * - applies pan clamp after the scale+position update
 */
export function makeWheelHandler(
  minScale: number,
  maxScale: number,
  cfg: PanClampConfig,
) {
  return (e: Konva.KonvaEventObject<WheelEvent>) => {
    e.evt.preventDefault()
    const stage = e.target.getStage()
    if (!stage) return
    const oldScale = stage.scaleX()
    const pointer = stage.getPointerPosition()
    if (!pointer) return
    const mousePointTo = {
      x: (pointer.x - stage.x()) / oldScale,
      y: (pointer.y - stage.y()) / oldScale,
    }
    const direction = e.evt.deltaY > 0 ? -1 : 1
    let newScale = direction > 0 ? oldScale * SCALE_BY : oldScale / SCALE_BY
    newScale = Math.max(minScale, Math.min(maxScale, newScale))
    if (newScale === oldScale) return
    stage.scale({ x: newScale, y: newScale })
    stage.position({
      x: pointer.x - mousePointTo.x * newScale,
      y: pointer.y - mousePointTo.y * newScale,
    })
    applyPanClamp(stage, newScale, cfg)
  }
}

/**
 * dragBoundFunc for Stage drag-pan. Mirrors applyPanClamp's math but returns a
 * new position instead of mutating the stage. Konva calls this during drag and
 * uses the returned value as the effective position.
 */
export function makeDragBoundFunc(
  cfg: PanClampConfig,
  getScale: () => number,
) {
  return (
    pos: { x: number; y: number },
    _e: unknown,
    stage?: Konva.Stage,
  ): { x: number; y: number } => {
    const s = getScale()
    const vw = stage?.width() ?? 0
    const vh = stage?.height() ?? 0
    const scaledW = cfg.mapW * s
    const scaledH = cfg.mapH * s
    let x = pos.x
    let y = pos.y
    if (scaledW <= vw) {
      x = (vw - scaledW) / 2
    } else {
      x = Math.min(0, Math.max(vw - scaledW, x))
    }
    if (scaledH <= vh) {
      y = (vh - scaledH) / 2
    } else {
      y = Math.min(0, Math.max(vh - scaledH, y))
    }
    return { x, y }
  }
}

/**
 * Pan the stage so (lon, lat) lands at the viewport center at the given scale.
 * RESEARCH §Pitfall 5 + UI-SPEC §Neighbor Navigation: used by CanvasViewer when
 * selectedTerritoryId changes (including via neighbor-chip click). The final
 * applyPanClamp() prevents over-pan past the map edge.
 */
export function panToGeoCenter(
  stage: Konva.Stage,
  lon: number,
  lat: number,
  projection: ProjectionConfig,
  scale: number,
  cfg: PanClampConfig,
): void {
  const [cx, cy] = geoToCanvas(lon, lat, projection)
  const vw = stage.width()
  const vh = stage.height()
  stage.scale({ x: scale, y: scale })
  stage.position({ x: vw / 2 - cx * scale, y: vh / 2 - cy * scale })
  applyPanClamp(stage, scale, cfg)
}
