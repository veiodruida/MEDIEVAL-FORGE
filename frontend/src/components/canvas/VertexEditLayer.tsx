/**
 * VertexEditLayer — 6th Konva layer (z=5, above InteractionLayer).
 *
 * Phase 08 Plan 05 — canvas scaffold for vertex editing.
 * REQ-IDs: PERF-01, EDIT-VERTEX-05
 *
 * Key design decisions:
 * - Mounts always; renders Circle handles ONLY when activeTerritoryId !== null (D-34).
 * - Viewport culling: filter to vertices within viewport bbox + 10% margin (D-34).
 * - RAF throttle: onDragMove queues via requestAnimationFrame; onDragEnd commits to store.
 * - Local preview state (useRef) for in-flight drag positions — NOT useEditorStore.setState
 *   (avoids 60 undo entries per drag).
 * - onDragEnd: inverse-project px → lat/lon → call useEditorStore.getState().moveVertex.
 * - Konva.clearCache() on activeTerritoryId change via useEffect cleanup (Pitfall 10).
 * - listening: false when activeTerritoryId is null (no hit-testing needed).
 *
 * UI-SPEC Konva colors (verbatim):
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Layer, Circle } from 'react-konva';
import type Konva from 'konva';
import { useEditorStore } from '../../stores/useEditorStore';
import { useProjection } from '../../context/ProjectionContext';
import { geoToCanvas, canvasToGeo } from '../../lib/projection';

// ── UI-SPEC color constants (verbatim hex literals) ──────────────────────────
const VERTEX_FILL_UNSELECTED = '#4a9eff';
const VERTEX_FILL_SELECTED = '#f0c040';
const VERTEX_FILL_HOVER = '#ffffff';
const SNAP_TARGET_STROKE = '#eab308';
const INVALID_DRAG_STROKE = '#ef4444';

// Expose for tests and sibling components that need the constants.
export {
  VERTEX_FILL_UNSELECTED,
  VERTEX_FILL_SELECTED,
  VERTEX_FILL_HOVER,
  SNAP_TARGET_STROKE,
  INVALID_DRAG_STROKE,
};

// ── Viewport bbox type ────────────────────────────────────────────────────────
export interface ViewportBBox {
  latMin: number;
  latMax: number;
  lonMin: number;
  lonMax: number;
}

// ── Props ─────────────────────────────────────────────────────────────────────
interface Props {
  /** Reference to the parent Konva Stage — passed through for future snap/zoom ops (08-06a). */
  stageRef: React.RefObject<Konva.Stage | null>;
  viewport: ViewportBBox | null;
}

// ── Viewport expand helper ────────────────────────────────────────────────────
function expandBBox(bbox: ViewportBBox, margin: number): ViewportBBox {
  const latSpan = bbox.latMax - bbox.latMin;
  const lonSpan = bbox.lonMax - bbox.lonMin;
  return {
    latMin: bbox.latMin - latSpan * margin,
    latMax: bbox.latMax + latSpan * margin,
    lonMin: bbox.lonMin - lonSpan * margin,
    lonMax: bbox.lonMax + lonSpan * margin,
  };
}

// ── VertexEditLayer ───────────────────────────────────────────────────────────
export const VertexEditLayer: React.FC<Props> = ({ stageRef: _stageRef, viewport }) => {
  const projection = useProjection();

  // Read from store (subscribe to only the fields we need)
  const activeTerritoryId = useEditorStore((s) => s.activeTerritoryId);
  const vertices = useEditorStore((s) => s.vertices);
  const selectedVertexIds = useEditorStore((s) => s.selectedVertexIds);

  const selectedSet = useMemo(() => new Set(selectedVertexIds), [selectedVertexIds]);

  // Hover state (local — not in store per UI-SPEC §Notes #2)
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  // ── Viewport culling (D-34) ─────────────────────────────────────────────────
  // Filter to vertices inside viewport + 10% margin. Culling is in world coords.
  const visibleEntries = useMemo<Array<{ id: string; lat: number; lon: number }>>(() => {
    if (!activeTerritoryId || !viewport) return [];
    const expanded = expandBBox(viewport, 0.1);
    return Object.entries(vertices)
      .filter(([, { lat, lon }]) =>
        lat >= expanded.latMin &&
        lat <= expanded.latMax &&
        lon >= expanded.lonMin &&
        lon <= expanded.lonMax,
      )
      .map(([id, { lat, lon }]) => ({ id, lat, lon }));
  }, [vertices, viewport, activeTerritoryId]);

  // ── Local preview state (in-flight drag, NOT persisted to store) ────────────
  // Keys are vertex ids; values are current drag px positions.
  const previewRef = useRef<Record<string, { x: number; y: number }>>({});

  // ── RAF throttle reference ──────────────────────────────────────────────────
  const rafRef = useRef<number | null>(null);

  // ── Drag handlers ───────────────────────────────────────────────────────────
  const handleDragMove = useCallback(
    (id: string, e: Konva.KonvaEventObject<DragEvent>) => {
      // Cancel any pending RAF frame (T-08-05-01 runaway RAF guard)
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        // Write to local preview only — NOT useEditorStore (avoids 60 undo entries)
        previewRef.current = {
          ...previewRef.current,
          [id]: { x: e.target.x(), y: e.target.y() },
        };
        rafRef.current = null;
      });
    },
    [],
  );

  const handleDragEnd = useCallback(
    (id: string, e: Konva.KonvaEventObject<DragEvent>) => {
      // Cancel any pending RAF from drag
      if (rafRef.current != null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      // Clear local preview for this vertex
      const nextPreview = { ...previewRef.current };
      delete nextPreview[id];
      previewRef.current = nextPreview;

      // Inverse-project px → lat/lon → single undoable store commit
      const [lon, lat] = canvasToGeo(e.target.x(), e.target.y(), projection);
      useEditorStore.getState().moveVertex(id, lat, lon);
    },
    [projection],
  );

  // ── Pitfall 10: clearCache on activeTerritoryId change ─────────────────────
  // useEffect cleanup fires when activeTerritoryId changes, clearing stale Konva cache.
  const layerRef = useRef<Konva.Layer | null>(null);
  useEffect(() => {
    return () => {
      // Cleanup: clear this layer's cache when activeTerritoryId changes
      if (layerRef.current) {
        layerRef.current.clearCache();
      }
    };
  }, [activeTerritoryId]);

  // Cleanup RAF on unmount
  useEffect(() => {
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  // ── Render ──────────────────────────────────────────────────────────────────
  // Layer always mounts at z=5; listening=false when no active territory (skip hit-testing)
  const listening = activeTerritoryId !== null;

  return (
    <Layer
      ref={layerRef as React.RefObject<Konva.Layer>}
      listening={listening}
    >
      {visibleEntries.map(({ id, lat, lon }) => {
        // Use preview px if dragging, otherwise project from world coord
        const preview = previewRef.current[id];
        let x: number;
        let y: number;
        if (preview) {
          x = preview.x;
          y = preview.y;
        } else {
          const [cx, cy] = geoToCanvas(lon, lat, projection);
          x = cx;
          y = cy;
        }

        // Color priority: hover > selected > unselected
        const fill =
          hoveredId === id
            ? VERTEX_FILL_HOVER
            : selectedSet.has(id)
              ? VERTEX_FILL_SELECTED
              : VERTEX_FILL_UNSELECTED;

        return (
          <Circle
            key={id}
            // Custom data attribute for test assertions
            {...({ 'data-vertex-id': id } as Record<string, string>)}
            x={x}
            y={y}
            radius={5}
            fill={fill}
            draggable={listening}
            onDragMove={(e) => handleDragMove(id, e as Konva.KonvaEventObject<DragEvent>)}
            onDragEnd={(e) => handleDragEnd(id, e as Konva.KonvaEventObject<DragEvent>)}
            onMouseEnter={() => setHoveredId(id)}
            onMouseLeave={() => setHoveredId(null)}
          />
        );
      })}
    </Layer>
  );
};
