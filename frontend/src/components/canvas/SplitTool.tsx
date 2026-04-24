import { useState, useCallback, useRef, useEffect } from 'react'
import { Layer, Line, Circle } from 'react-konva'
import * as Toast from '@radix-ui/react-toast'
import type { KonvaEventObject } from 'konva/lib/Node'
import type Konva from 'konva'
import { useEditorStore } from '../../stores/useEditorStore'
import {
  useProjectStore,
  beginTransaction,
  endTransaction,
} from '../../stores/useProjectStore'
import { useUIStore } from '../../stores/uiStore'
import { splitTerritory, EditApiError } from '../../api/edit'
import { canvasToGeo, type ProjectionConfig } from '../../lib/projection'
import type { TerritoryMetadataCondado } from '../../hooks/useCanvasArtifacts'
import { useSaveStrategy, onOperationFinalized } from '../../services/persistence'
import { useValidationStore } from '../../stores/useValidationStore'
import { validateTerritories } from '../../services/validation'

interface Args {
  condados: TerritoryMetadataCondado[]
  stageRef: React.RefObject<Konva.Stage | null>
  /** Projection config passed in by CanvasViewer (matches useRubberBandSelection pattern).
   *  When null (projection not yet resolved), all handlers no-op. */
  projection: ProjectionConfig | null
}

/**
 * useSplitTool — hook-style split tool (Pattern consistent with useRubberBandSelection).
 *
 * Returns { previewLayer, toastEl, onStageMouseDown, onStageMouseMove, onStageMouseUp, onStageDblClick }.
 * - previewLayer: Konva <Layer> with cut-line preview (rendered INSIDE <Stage>)
 * - toastEl: <Toast.Root> DOM element for 422 errors (rendered OUTSIDE <Stage>)
 *
 * The dual-return separation is required because Toast.Root is a DOM element
 * and cannot be rendered inside the Konva <Stage> SVG/canvas tree.
 *
 * 3 sub-modes (D-04):
 *   snap      — 2 clicks; fires splitTerritory on 2nd click
 *   polyline  — N clicks; dblClick finishes; fires splitTerritory
 *   freehand  — mousedown-drag-mouseup; decimates every 4th point (T-04-07-03)
 *
 * Threat mitigations:
 *   T-04-07-01: catch block parses 422 EditApiError → Portuguese toast (Pitfall 4 end-to-end)
 *   T-04-07-03: freehand decimation (every 4th point) before POST
 */
export function useSplitTool({ condados, stageRef, projection }: Args) {
  const activeTool = useEditorStore((s) => s.activeTool)
  const subMode = useEditorStore((s) => s.splitSubMode)
  const setActiveTool = useEditorStore((s) => s.setActiveTool)
  const pushUndoLabel = useEditorStore((s) => s.pushUndoLabel)
  const selectedId = useUIStore((s) => s.selectedTerritoryId)
  const projectId = useProjectStore((s) => s.projectId)
  const applyBatchUpdate = useProjectStore((s) => s.applyBatchUpdate)
  const removeTerritories = useProjectStore((s) => s.removeTerritories)
  const setIssuesForIds = useValidationStore((s) => s.setIssuesForIds)
  const strategy = useSaveStrategy()

  // Canvas-space points of the in-progress cut line (transient drawing state)
  const [points, setPoints] = useState<Array<[number, number]>>([])
  const isDrawing = useRef(false)
  const [errorToast, setErrorToast] = useState<string | null>(null)

  const active = activeTool === 'split' && selectedId !== null

  // Clear in-progress cut line when split tool is deactivated (e.g. Esc mid-polyline)
  useEffect(() => {
    if (!active) {
      setPoints([])
      isDrawing.current = false
    }
  }, [active])

  const getStagePos = () => {
    const stage = stageRef.current
    if (!stage) return null
    return stage.getRelativePointerPosition()
  }

  const commit = useCallback(
    async (canvasPoints: Array<[number, number]>) => {
      if (!projectId || !selectedId || canvasPoints.length < 2 || !projection) {
        setPoints([])
        return
      }
      const condado = condados.find((c) => c.id === selectedId)
      const geoCutLine: Array<[number, number]> = canvasPoints.map(([x, y]) =>
        canvasToGeo(x, y, projection),
      )

      const persist = strategy !== 'explicit'
      beginTransaction()
      try {
        const response = await splitTerritory(projectId, selectedId, {
          cut_line: geoCutLine,
          mode: subMode,
        }, { persist })
        // Remove original; add both halves
        removeTerritories([response.original_id])
        applyBatchUpdate(
          {
            [response.new_territory_a.id]: response.new_territory_a.geometry,
            [response.new_territory_b.id]: response.new_territory_b.geometry,
          },
          {},
        )
        pushUndoLabel(`Dividir ${condado?.name ?? selectedId}`)
        onOperationFinalized()
        // D-06: revalidate split territories after finalize
        const splitAffected = [response.new_territory_a.id, response.new_territory_b.id]
        const storeState = {
          territories: useProjectStore.getState().territories,
          capitals: useProjectStore.getState().capitals,
        }
        setIssuesForIds(splitAffected, validateTerritories(splitAffected, storeState))
      } catch (err) {
        // T-04-07-01: surface 422 backend detail as Portuguese toast (Pitfall 4)
        let msg = 'Linha de corte deve cruzar o território em dois pontos.'
        if (err instanceof EditApiError) {
          try {
            const parsed = JSON.parse(err.message) as { detail?: unknown }
            if (parsed?.detail) msg = String(parsed.detail)
          } catch {
            msg = err.message || msg
          }
        }
        setErrorToast(msg)
      } finally {
        endTransaction()
      }

      setPoints([])
      setActiveTool('select')
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [projectId, selectedId, condados, subMode, projection, strategy, applyBatchUpdate, removeTerritories, pushUndoLabel, setActiveTool, setIssuesForIds],
  )

  // Mode dispatch — mousedown
  const onStageMouseDown = (_e: KonvaEventObject<MouseEvent>) => {
    if (!active || !projection) return
    const pos = getStagePos()
    if (!pos) return

    if (subMode === 'snap') {
      const next: Array<[number, number]> = [...points, [pos.x, pos.y]]
      if (next.length >= 2) {
        void commit(next)
      } else {
        setPoints(next)
      }
    } else if (subMode === 'polyline') {
      setPoints((prev) => [...prev, [pos.x, pos.y]])
    } else if (subMode === 'freehand') {
      isDrawing.current = true
      setPoints([[pos.x, pos.y]])
    }
  }

  const onStageMouseMove = (_e: KonvaEventObject<MouseEvent>) => {
    if (!active || !projection) return
    if (subMode !== 'freehand') return
    if (!isDrawing.current) return
    const pos = getStagePos()
    if (!pos) return
    setPoints((prev) => [...prev, [pos.x, pos.y]])
  }

  const onStageMouseUp = () => {
    if (!active || !projection) return
    if (subMode === 'freehand' && isDrawing.current) {
      isDrawing.current = false
      // T-04-07-03: client-side decimation (every 4th point) before POST
      const sampled = points.filter((_, i) => i % 4 === 0)
      if (sampled.length !== points.length && points.length > 0) {
        sampled.push(points[points.length - 1])
      }
      void commit(sampled)
    }
  }

  const onStageDblClick = () => {
    if (!active || !projection) return
    if (subMode === 'polyline' && points.length >= 2) {
      void commit(points)
    }
  }

  // previewLayer: Konva Layer with cut-line preview (goes INSIDE Stage)
  const previewLayer =
    active && points.length > 0 ? (
      <Layer listening={false}>
        <Line
          points={points.flat()}
          stroke="#6E56CF"
          strokeWidth={2}
          dash={[6, 3]}
          lineCap="round"
          lineJoin="round"
        />
        {points.map((p, i) => (
          <Circle key={i} x={p[0]} y={p[1]} radius={3} fill="#6E56CF" />
        ))}
      </Layer>
    ) : null

  // toastEl: DOM element for 422 error (goes OUTSIDE Stage in regular DOM)
  const toastEl = (
    <Toast.Root
      open={errorToast !== null}
      onOpenChange={(o) => {
        if (!o) setErrorToast(null)
      }}
      duration={6000}
      className="rounded-md bg-red-2 border border-red-7 p-3 shadow-md"
    >
      <Toast.Description>{errorToast}</Toast.Description>
    </Toast.Root>
  )

  return {
    previewLayer,
    toastEl,
    onStageMouseDown,
    onStageMouseMove,
    onStageMouseUp,
    onStageDblClick,
  }
}
