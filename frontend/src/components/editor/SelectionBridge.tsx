/**
 * SelectionBridge — closes GAP-A: selection → editor activation bridge.
 *
 * Phase 08 Plan 12 (gap-closure plan).
 *
 * PURPOSE: This null-rendering effect component subscribes to useUIStore's
 * selection fields and wires them to useEditorStore:
 *
 *   - barony selected (selectedBaronyId non-null, selectedTerritoryId null):
 *     → setActiveTerritoryId(baronyId)
 *     → setState({ vertices: Record<"${baronyId}#${index}", {lat,lon}> })
 *
 *   - condado selected (selectedTerritoryId non-null) or deselect:
 *     → setActiveTerritoryId(null)
 *     → setState({ vertices: {} })
 *
 * D-03 ENFORCEMENT (barony-tier only):
 *   Condado selection does NOT populate editable vertices. The SelectionBridge
 *   always clears the editor state when a condado is selected.
 *
 * VERTEX ID SCHEME: "${baronyId}#${index}" — index = ring position 0..N-1.
 *   Stable across re-renders for identical geometry (zundo diff-safe).
 *   Closed rings (last point === first point) drop the duplicate last point.
 *
 * UNDO SAFETY:
 *   Loading a selection must NOT create an undo entry (the user should not
 *   "undo" clicking a barony). We wrap the setState call with
 *   useEditorStore.temporal.getState().pause() / .resume() so that zundo's
 *   temporal middleware does not record the transition in pastStates.
 *
 * Returns null — no DOM output.
 *
 * @see 08-VERIFICATION.md — GAP-A definition
 */
import { useEffect } from 'react'
import { useUIStore } from '../../stores/uiStore'
import { useEditorStore } from '../../stores/useEditorStore'
import type { BaronyRender } from '../../hooks/useCanvasArtifacts'

interface SelectionBridgeProps {
  /** effectiveBaronies from CanvasViewer — the BaronyRender[] with geoRing populated. */
  baronies: BaronyRender[]
}

export function SelectionBridge({ baronies }: SelectionBridgeProps): null {
  const selectedBaronyId = useUIStore((s) => s.selectedBaronyId)
  const selectedTerritoryId = useUIStore((s) => s.selectedTerritoryId)

  useEffect(() => {
    const temporal = useEditorStore.temporal.getState()

    // CASE 1: deselect or condado selected (D-03: condado does NOT populate vertices)
    if (selectedBaronyId === null || selectedTerritoryId !== null) {
      temporal.pause()
      useEditorStore.getState().setActiveTerritoryId(null)
      useEditorStore.setState({ vertices: {} })
      temporal.resume()
      return
    }

    // CASE 2: barony selected
    const b = baronies.find((x) => x.id === selectedBaronyId)

    if (!b || !b.geoRing) {
      // Barony not found or no geometry available — activate id but no handles
      temporal.pause()
      useEditorStore.getState().setActiveTerritoryId(selectedBaronyId)
      useEditorStore.setState({ vertices: {} })
      temporal.resume()
      return
    }

    // Build stable vertices Record from the outer ring.
    // Drop the closing duplicate point if ring[0] === ring[last] (closed ring).
    const ring = b.geoRing
    const closed =
      ring.length > 1 &&
      ring[0][0] === ring[ring.length - 1][0] &&
      ring[0][1] === ring[ring.length - 1][1]
    const n = closed ? ring.length - 1 : ring.length

    const vertices: Record<string, { lat: number; lon: number }> = {}
    for (let i = 0; i < n; i++) {
      const [lon, lat] = ring[i]
      vertices[`${selectedBaronyId}#${i}`] = { lat, lon }
    }

    temporal.pause()
    useEditorStore.getState().setActiveTerritoryId(selectedBaronyId)
    useEditorStore.setState({ vertices })
    temporal.resume()
  }, [selectedBaronyId, selectedTerritoryId, baronies])

  return null
}
