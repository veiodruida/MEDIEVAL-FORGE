import { useState, useRef, useCallback } from 'react'
import type { KonvaEventObject } from 'konva/lib/Node'
import type Konva from 'konva'
import { useEditorStore } from '../stores/useEditorStore'
import { geoToCanvas } from '../lib/projection'
import type { TerritoryMetadataCondado } from './useCanvasArtifacts'
import type { ProjectionConfig } from '../lib/projection'

export interface SelectionRect {
  x: number
  y: number
  w: number
  h: number
}

interface Args {
  condados: TerritoryMetadataCondado[]
  projection: ProjectionConfig
  stageRef: React.RefObject<Konva.Stage | null>
}

/**
 * Rubber-band selection hook.
 *
 * Pattern 4 (Research): transparent Rect on mousemove, centroid containment on mouseup.
 * Pitfall 2 mitigation: caller (CanvasViewer) MUST disable Stage draggable when
 * activeTool === 'select', otherwise Stage pan intercepts mousedown-drag.
 */
export function useRubberBandSelection({ condados, projection, stageRef }: Args) {
  const [selectionRect, setSelectionRect] = useState<SelectionRect | null>(null)
  const dragStartPos = useRef<{ x: number; y: number } | null>(null)
  const editMode = useEditorStore((s) => s.editMode)
  const activeTool = useEditorStore((s) => s.activeTool)
  const setRubberBandSelectionIds = useEditorStore((s) => s.setRubberBandSelectionIds)

  const isActive = editMode && activeTool === 'select'

  const onMouseDown = useCallback((e: KonvaEventObject<MouseEvent>) => {
    if (!isActive) return
    const stage = e.target.getStage()
    if (!stage) return
    // Only trigger on empty Stage area (not on a territory or capital)
    if (e.target !== stage) return
    const pos = stage.getRelativePointerPosition()
    if (!pos) return
    dragStartPos.current = pos
    setSelectionRect({ x: pos.x, y: pos.y, w: 0, h: 0 })
  }, [isActive])

  const onMouseMove = useCallback((e: KonvaEventObject<MouseEvent>) => {
    if (!dragStartPos.current) return
    const stage = e.target.getStage?.() ?? stageRef.current
    if (!stage) return
    const pos = stage.getRelativePointerPosition()
    if (!pos) return
    const start = dragStartPos.current
    setSelectionRect({
      x: Math.min(start.x, pos.x),
      y: Math.min(start.y, pos.y),
      w: Math.abs(pos.x - start.x),
      h: Math.abs(pos.y - start.y),
    })
  }, [stageRef])

  const onMouseUp = useCallback(() => {
    if (!selectionRect || !dragStartPos.current) {
      dragStartPos.current = null
      setSelectionRect(null)
      return
    }
    const { x, y, w, h } = selectionRect
    const selected = condados.filter((c) => {
      const [cx, cy] = geoToCanvas(c.lon, c.lat, projection)
      return cx >= x && cx <= x + w && cy >= y && cy <= y + h
    })
    setRubberBandSelectionIds(selected.map((c) => c.id))
    setSelectionRect(null)
    dragStartPos.current = null
  }, [selectionRect, condados, projection, setRubberBandSelectionIds])

  return { selectionRect, onMouseDown, onMouseMove, onMouseUp, isActive }
}
