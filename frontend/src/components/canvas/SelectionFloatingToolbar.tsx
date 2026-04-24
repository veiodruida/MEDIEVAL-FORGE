import { useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Card, Flex, Button } from '@radix-ui/themes'
import * as Toast from '@radix-ui/react-toast'
import { useEditorStore } from '../../stores/useEditorStore'
import {
  useProjectStore,
  beginTransaction,
  endTransaction,
} from '../../stores/useProjectStore'
import { mergeTerritories } from '../../api/edit'
import type Konva from 'konva'
import { geoToCanvas } from '../../lib/projection'
import { useProjection } from '../../context/ProjectionContext'
import type { TerritoryMetadataCondado } from '../../hooks/useCanvasArtifacts'
import { useSaveStrategy, onOperationFinalized } from '../../services/persistence'
import { useValidationStore } from '../../stores/useValidationStore'
import { validateTerritories } from '../../services/validation'
import type { ValidationIssue } from '../../types/editing'

interface Props {
  condados: TerritoryMetadataCondado[]
  stageRef: React.RefObject<Konva.Stage | null>
}

/**
 * SelectionFloatingToolbar — appears above the rubber-band selection bounding box.
 *
 * Renders when rubberBandSelectionIds.length >= 2.
 * Position: viewport-relative absolute div, 8px above the bounding-box top-midpoint
 * of selection in screen coordinates (Open Question 3 pattern: viewport-relative div).
 *
 * Fundir (Merge) button:
 *  - Wraps mergeTerritories API call in beginTransaction/endTransaction (EDIT-08).
 *  - Applies response: updated primary territory + removes merged-away territories.
 *  - Pushes undo label "Fundir {N} territórios".
 *  - If warning === 'non_adjacent_multipolygon': shows amber Toast (D-03).
 *  - Clears rubber-band selection on success.
 */
export function SelectionFloatingToolbar({ condados, stageRef }: Props) {
  const selectionIds = useEditorStore((s) => s.rubberBandSelectionIds)
  const clearSelection = useEditorStore((s) => s.clearRubberBandSelection)
  const pushUndoLabel = useEditorStore((s) => s.pushUndoLabel)
  const applyBatchUpdate = useProjectStore((s) => s.applyBatchUpdate)
  const removeTerritories = useProjectStore((s) => s.removeTerritories)
  const projectId = useProjectStore((s) => s.projectId)
  const projection = useProjection()
  const saveStrategy = useSaveStrategy()
  const queryClient = useQueryClient()
  const setIssuesForIds = useValidationStore((s) => s.setIssuesForIds)
  const [toastMsg, setToastMsg] = useState<string | null>(null)
  const [toastOpen, setToastOpen] = useState(false)

  // Compute viewport-relative position of toolbar above selection bounding box.
  // Uses Stage.getAbsoluteTransform() to convert canvas-space centroid positions
  // to viewport coordinates (accounts for zoom/pan transforms).
  const position = useMemo(() => {
    if (selectionIds.length < 2) return null
    const stage = stageRef.current
    if (!stage) return null
    const selected = condados.filter((c) => selectionIds.includes(c.id))
    if (selected.length === 0) return null
    // Canvas-space bounding box of centroids
    const points = selected.map((c) => geoToCanvas(c.lon, c.lat, projection))
    const minX = Math.min(...points.map((p) => p[0]))
    const maxX = Math.max(...points.map((p) => p[0]))
    const minY = Math.min(...points.map((p) => p[1]))
    const topMidX = (minX + maxX) / 2
    const topY = minY
    // Apply stage transform (zoom/pan) to get screen-space coordinates
    const absPos = stage.getAbsoluteTransform().point({ x: topMidX, y: topY })
    // Convert to viewport coords using container bounding rect
    const containerRect = stage.container().getBoundingClientRect()
    return {
      left: containerRect.left + absPos.x,
      top: containerRect.top + absPos.y - 48, // 8px gap above ~40px toolbar
    }
  }, [selectionIds, condados, stageRef, projection])

  if (selectionIds.length < 2 || !position) return null

  const handleMerge = async () => {
    if (!projectId) return
    // Primary = first in selection (pragmatic default; true largest-area calc deferred to P08).
    // TODO(P08): compute actual largest-area primary from store polygon coordinates.
    const primary_id = selectionIds[0]
    const label = `Fundir ${selectionIds.length} territórios`

    const persist = saveStrategy !== 'explicit'
    beginTransaction()
    try {
      const response = await mergeTerritories(projectId, {
        condado_ids: selectionIds,
        primary_id,
      }, { persist })
      // Apply merged geometry to primary territory; remove the others
      applyBatchUpdate({ [response.merged_id]: response.merged_territory }, {})
      removeTerritories(response.removed_ids)
      // D-06: revalidate merged territory after finalize
      const mergedAffected = [response.merged_id]
      const storeState = {
        territories: useProjectStore.getState().territories,
        capitals: useProjectStore.getState().capitals,
      }
      const mergeIssues: ValidationIssue[] = validateTerritories(mergedAffected, storeState)
      if (response.warning === 'non_adjacent_multipolygon') {
        mergeIssues.push({
          condado_id: response.merged_id,
          severity: 'warning',
          rule: 'non_adjacent_merge',
          message: 'Território não adjacente — multipolígono criado',
        })
        setToastMsg('Territórios não adjacentes. Fundir criará um multipolígono (aviso de validação).')
        setToastOpen(true)
      }
      setIssuesForIds(mergedAffected, mergeIssues)
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('mergeTerritories failed', err)
      endTransaction()
      return // Do not push label on failure
    }
    endTransaction()
    pushUndoLabel(label)
    onOperationFinalized()
    if (saveStrategy !== 'explicit') {
      queryClient.invalidateQueries({ queryKey: ['territories-geojson', projectId] })
      queryClient.invalidateQueries({ queryKey: ['territory-metadata', projectId] })
    }
    clearSelection()
  }

  return (
    <>
      <div
        style={{
          position: 'fixed',
          left: position.left,
          top: position.top,
          transform: 'translateX(-50%)',
          zIndex: 20,
        }}
      >
        <Card variant="surface" size="1">
          <Flex gap="2" align="center" p="1">
            <Button size="2" variant="solid" onClick={() => void handleMerge()}>
              Fundir
            </Button>
          </Flex>
        </Card>
      </div>
      <Toast.Root
        open={toastOpen}
        onOpenChange={setToastOpen}
        duration={4000}
        className="rounded-md bg-amber-2 border border-amber-7 p-3 shadow-md"
      >
        <Toast.Description>{toastMsg}</Toast.Description>
      </Toast.Root>
    </>
  )
}
