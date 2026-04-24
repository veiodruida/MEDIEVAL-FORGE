import { useEffect, useState } from 'react'
import { Layer, Circle } from 'react-konva'
import type { KonvaEventObject } from 'konva/lib/Node'
import { useEditorStore } from '../../stores/useEditorStore'
import { useProjectStore } from '../../stores/useProjectStore'
import { geoToCanvas, canvasToGeo } from '../../lib/projection'
import { useProjection } from '../../context/ProjectionContext'
import { fetchVertexHandles } from '../../api/edit'
import type { VertexHandle } from '../../api/edit'
import type { GeoJSONPolygon } from '../../types/editing'

/**
 * VertexHandlesLayer — renders ~12 draggable circular handles on the selected
 * condado's exterior ring in vertex-edit mode.
 *
 * Handles are fetched ONCE on vertex-edit entry from GET /vertex-handles (Plan 04 Task 3).
 * The backend runs services/voronoi.decimate_polygon (true Douglas-Peucker) and returns
 * each decimated vertex with its source_index in the ORIGINAL exterior ring.
 *
 * Dragging handle N writes to exterior[source_index_N], preserving full detail
 * between handles (D-02 per 04-CONTEXT.md).
 *
 * Per Pitfall 6 note in plan: clearCache() would be needed if TerritoryLayer shows
 * canvas desync after geometry updates. In practice, geometry reference changes on
 * setTerritory trigger React re-render of TerritoryPolygon (new points prop), so
 * Konva re-draws without explicit clearCache(). This is noted as A2 (ASSUMED) in SUMMARY.
 *
 * UI-SPEC §Color: fill=#ffffff, stroke=#6E56CF, strokeWidth=1.5, radius=6.
 */
export function VertexHandlesLayer() {
  const vertexEditId = useEditorStore((s) => s.vertexEditCondadoId)
  const territories = useProjectStore((s) => s.territories)
  const setTerritory = useProjectStore((s) => s.setTerritory)
  const projectId = useProjectStore((s) => s.projectId)
  const projection = useProjection()

  // Handles fetched once per vertex-edit session (source_index anchors are authoritative).
  const [handles, setHandles] = useState<VertexHandle[] | null>(null)
  const [handlesLoadedFor, setHandlesLoadedFor] = useState<string | null>(null)

  useEffect(() => {
    if (!vertexEditId || !projectId) {
      setHandles(null)
      setHandlesLoadedFor(null)
      return
    }
    if (handlesLoadedFor === vertexEditId) return // already fetched for this session
    let cancelled = false
    fetchVertexHandles(projectId, vertexEditId, 12)
      .then((res) => {
        if (cancelled) return
        setHandles(res.handles)
        setHandlesLoadedFor(vertexEditId)
      })
      .catch((err) => {
        if (cancelled) return
        // eslint-disable-next-line no-console
        console.error('fetchVertexHandles failed', err)
        setHandles(null)
      })
    return () => { cancelled = true }
  }, [vertexEditId, projectId, handlesLoadedFor])

  if (!vertexEditId || !handles) return null
  const geom = territories[vertexEditId]
  if (!geom || geom.type !== 'Polygon') return null

  const handleDragEnd = (sourceIndex: number) => (e: KonvaEventObject<DragEvent>) => {
    const node = e.target
    const [lon, lat] = canvasToGeo(node.x(), node.y(), projection)
    const poly = geom as GeoJSONPolygon
    const newCoords = poly.coordinates.map((ring, ringIdx) => {
      if (ringIdx !== 0) return ring // exterior ring only
      const newRing = [...ring]
      // Write to the ORIGINAL ring at source_index (not a decimated step index)
      newRing[sourceIndex] = [lon, lat]
      // Keep polygon closed: first and last coord must match
      if (sourceIndex === 0) newRing[newRing.length - 1] = [lon, lat]
      if (sourceIndex === newRing.length - 1) newRing[0] = [lon, lat]
      return newRing
    })
    setTerritory(vertexEditId, { type: 'Polygon', coordinates: newCoords })
    // Update local handle position so the Circle stays under cursor after drag
    setHandles((prev) =>
      prev?.map((h) =>
        h.source_index === sourceIndex ? { ...h, lon, lat } : h,
      ) ?? null,
    )
  }

  return (
    <Layer listening={true}>
      {handles.map((h) => {
        const [x, y] = geoToCanvas(h.lon, h.lat, projection)
        return (
          <Circle
            key={`vh-${h.source_index}`}
            x={x}
            y={y}
            radius={6}
            fill="#ffffff"
            stroke="#6E56CF"
            strokeWidth={1.5}
            draggable
            onDragEnd={handleDragEnd(h.source_index)}
          />
        )
      })}
    </Layer>
  )
}
