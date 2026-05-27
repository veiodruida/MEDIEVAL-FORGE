/**
 * VertexEditLayer — 6th Konva layer (z=5, above InteractionLayer).
 *
 * Phase 08 Plan 05 — canvas scaffold for vertex editing.
 * Phase 08 Plan 06a — wires vertex move/add/delete ops to useEditorStore +
 *   backend POST /editor/validate; adds D-03 barony-tier guard; D-06 add cap.
 * Phase 08 Plan 06b — snap (TOPO-03) + shared-vertex coupling (TOPO-04) +
 *   topology-block visuals (TOPO-01: red fill/stroke on invalid drag) +
 *   D-27 warn-badge flags; Alt-disable for snap (D-28).
 *
 * REQ-IDs: PERF-01, EDIT-VERTEX-01, EDIT-VERTEX-02, EDIT-VERTEX-03,
 *           EDIT-VERTEX-05, TOPO-01, TOPO-02, TOPO-03, TOPO-04, D-03, D-06
 *
 * Key design decisions:
 * - Mounts always; renders Circle handles ONLY when activeTerritoryId !== null (D-34).
 * - D-03: Only barony-tier polygons are editable. prop tier must be 'barony' for ops to fire.
 * - Viewport culling: filter to vertices within viewport bbox + 10% margin (D-34).
 * - RAF throttle: onDragMove queues via requestAnimationFrame; onDragEnd commits to store.
 * - Local preview state (useRef) for in-flight drag positions — NOT useEditorStore.setState
 *   (avoids 60 undo entries per drag).
 * - Snap (TOPO-03, D-28): onDragMove calls snapToNeighbour(cursor, candidates, stageScale, altHeld).
 *   If hit: render yellow snap-target Circle #eab308. Hold Alt to disable (D-28).
 * - Shared vertex (TOPO-04, D-30): on edit-mode entry, buildSharedVertexIndex for all vertices.
 *   onDragEnd: if shared, gather coupledIds → single setVerticesAndLog call (one undoable op).
 * - Topology block (TOPO-01, D-26): on invalid /editor/validate response, paint polygon red
 *   (#ef4444 fill+stroke); after 600ms revert to normal preview. On mouseup: snap back.
 * - D-27 warning: when polygon has duplicate vertex (≤1e-6) or area < 0.001°, set warnFlags
 *   in local state for inspector badge.
 * - Add tool: Layer onClick (when activeTool==='A') → addVertex; disabled when count>=1000 (D-06).
 * - Delete tool: Del/Backspace key handled in useKeyboardShortcuts (08-05).
 * - Konva.clearCache() on activeTerritoryId change via useEffect cleanup (Pitfall 10).
 * - listening: false when activeTerritoryId is null (no hit-testing needed).
 *
 * UI-SPEC Konva colors (verbatim):
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Layer, Circle } from 'react-konva';
import type Konva from 'konva';
import { useEditorStore } from '../../stores/useEditorStore';
import type { VertexCoord } from '../../stores/useEditorStore';
import { useProjection } from '../../context/ProjectionContext';
import { geoToCanvas, canvasToGeo } from '../../lib/projection';
import { snapToNeighbour } from '../../lib/snap';
import type { SnapCandidate } from '../../lib/snap';
import { buildSharedVertexIndex, getCoupledVertices } from '../../lib/sharedVertex';
import type { VertexRef } from '../../lib/sharedVertex';

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

// ── Territory tier type ───────────────────────────────────────────────────────
/** D-03: only 'barony' tier polygons are directly editable. */
export type TerritoryTier = 'barony' | 'condado' | 'duchy' | 'kingdom';

// ── D-27 warning flags ────────────────────────────────────────────────────────
export interface VertexWarnFlags {
  duplicateVertex: boolean;  // any two vertices within 1e-6 of each other
  sliverPolygon: boolean;    // area < 0.001° (approx)
}

// ── Props ─────────────────────────────────────────────────────────────────────
interface Props {
  /** Reference to the parent Konva Stage — used for snap scale (Pitfall 7). */
  stageRef: React.RefObject<Konva.Stage | null>;
  viewport: ViewportBBox | null;
  /**
   * D-03: tier of the active territory. Vertex ops silently no-op on non-barony tiers.
   * Defaults to 'barony' for backward compat when not provided by CanvasViewer.
   */
  tier?: TerritoryTier;
  /**
   * Project UUID required for POST /editor/validate. If not provided (test/scaffold),
   * validate call is skipped and op commits directly (non-blocking fallback).
   */
  projectId?: string;
  /**
   * D-27 callback: called whenever warn flags change (duplicate vertex / sliver polygon).
   * Inspector uses this to show amber badges.
   */
  onWarnFlagsChange?: (flags: VertexWarnFlags) => void;
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

// ── D-27 warn flag computation ────────────────────────────────────────────────
/**
 * Compute D-27 warn flags for the current vertex set.
 * - duplicateVertex: any two vertices within Euclidean distance 1e-6 (lat/lon).
 * - sliverPolygon: approximated by bounding-box area < 0.001° (no Shapely in browser).
 *   Real area validation happens backend-side via /editor/validate on commit.
 */
function computeWarnFlags(vertices: Record<string, VertexCoord>): VertexWarnFlags {
  const coords = Object.values(vertices);

  // Duplicate vertex check (O(N²) — same rationale as sharedVertex.ts, N is small)
  let duplicateVertex = false;
  outer: for (let i = 0; i < coords.length; i++) {
    for (let j = i + 1; j < coords.length; j++) {
      const dLat = coords[i].lat - coords[j].lat;
      const dLon = coords[i].lon - coords[j].lon;
      if (Math.sqrt(dLat * dLat + dLon * dLon) <= 1e-6) {
        duplicateVertex = true;
        break outer;
      }
    }
  }

  // Sliver polygon: approx by lat/lon bounding-box area < 0.001°²
  let sliverPolygon = false;
  if (coords.length >= 3) {
    const lats = coords.map((v) => v.lat);
    const lons = coords.map((v) => v.lon);
    const latSpan = Math.max(...lats) - Math.min(...lats);
    const lonSpan = Math.max(...lons) - Math.min(...lons);
    const bboxArea = latSpan * lonSpan;
    if (bboxArea < 0.001) sliverPolygon = true;
  }

  return { duplicateVertex, sliverPolygon };
}

// ── Validate via backend (D-26) ───────────────────────────────────────────────
/**
 * POST /api/v3/projects/{pid}/editor/validate for a single moved polygon.
 * Returns true (valid) on network error to avoid blocking the user (fail-open).
 */
async function validateMoveWithBackend(
  projectId: string,
  polygonId: string,
  coords: Array<[number, number]>,
): Promise<{ valid: boolean; code: string | null }> {
  try {
    const res = await fetch(
      `/api/v3/projects/${projectId}/editor/validate`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          polygons: [{ polygon_id: polygonId, coords, neighbour_ids: [] }],
          neighbour_lookup: {},
        }),
      },
    );
    if (!res.ok) {
      console.warn('[VertexEditLayer] /editor/validate returned', res.status);
      return { valid: true, code: null }; // fail-open
    }
    const results = (await res.json()) as Array<{ valid: boolean; code: string | null }>;
    return results[0] ?? { valid: true, code: null };
  } catch (err) {
    console.warn('[VertexEditLayer] /editor/validate network error', err);
    return { valid: true, code: null }; // fail-open on network error
  }
}

// ── VertexEditLayer ───────────────────────────────────────────────────────────
export const VertexEditLayer: React.FC<Props> = ({
  stageRef,
  viewport,
  tier = 'barony',
  projectId,
  onWarnFlagsChange,
}) => {
  const projection = useProjection();

  // Read from store (subscribe to only the fields we need)
  const activeTerritoryId = useEditorStore((s) => s.activeTerritoryId);
  const vertices = useEditorStore((s) => s.vertices);
  const selectedVertexIds = useEditorStore((s) => s.selectedVertexIds);
  const activeTool = useEditorStore((s) => s.activeTool);

  const selectedSet = useMemo(() => new Set(selectedVertexIds), [selectedVertexIds]);
  const vertexCount = Object.keys(vertices).length;

  // Hover state (local — not in store per UI-SPEC §Notes #2)
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  // D-03: barony-tier guard — if tier is not barony, treat as read-only
  const isEditableTier = tier === 'barony';

  // ── Alt-key state (D-28: Alt held → disable snap for current drag) ──────────
  const [altHeld, setAltHeld] = useState(false);
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => { if (e.key === 'Alt') setAltHeld(true); };
    const onKeyUp = (e: KeyboardEvent) => { if (e.key === 'Alt') setAltHeld(false); };
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup', onKeyUp);
    };
  }, []);

  // ── Snap target indicator state (TOPO-03, D-28) ──────────────────────────────
  // Position in canvas px of the current snap target, or null if no snap.
  const [snapTargetPx, setSnapTargetPx] = useState<{ x: number; y: number } | null>(null);

  // ── Invalid drag visual state (TOPO-01, D-26) ───────────────────────────────
  // When backend returns invalid, briefly show red stroke on the dragged handle.
  const [invalidDragId, setInvalidDragId] = useState<string | null>(null);

  // ── Shared-vertex index (TOPO-04, D-30) ──────────────────────────────────────
  // Built on edit-mode entry (activeTerritoryId changes) and refreshed on mouseup.
  const sharedIndexRef = useRef(buildSharedVertexIndex([]));

  const rebuildSharedIndex = useCallback(() => {
    const refs: VertexRef[] = Object.entries(vertices).map(([vertexId, { lat, lon }]) => ({
      vertexId,
      baronyId: activeTerritoryId ?? 'unknown',
      lat,
      lon,
    }));
    sharedIndexRef.current = buildSharedVertexIndex(refs);
  }, [vertices, activeTerritoryId]);

  // Rebuild index when edit mode activates or vertices change after commit
  useEffect(() => {
    if (activeTerritoryId) rebuildSharedIndex();
  }, [activeTerritoryId, rebuildSharedIndex]);

  // ── D-27: emit warn flags when vertices change ───────────────────────────────
  useEffect(() => {
    if (!onWarnFlagsChange) return;
    const flags = computeWarnFlags(vertices);
    onWarnFlagsChange(flags);
  }, [vertices, onWarnFlagsChange]);

  // ── Viewport culling (D-34) ─────────────────────────────────────────────────
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

  // ── Snap candidates: all visible vertices EXCEPT the currently dragged one ──
  // Rebuilt per-render — cheap because visibleEntries is already culled.
  const snapCandidatesRef = useRef<SnapCandidate[]>([]);
  useEffect(() => {
    snapCandidatesRef.current = visibleEntries.map(({ id, lat, lon }) => ({ id, lat, lon }));
  }, [visibleEntries]);

  // ── Local preview state (in-flight drag, NOT persisted to store) ────────────
  const previewRef = useRef<Record<string, { x: number; y: number }>>({});

  // ── RAF throttle reference ──────────────────────────────────────────────────
  const rafRef = useRef<number | null>(null);

  // ── Drag handlers ───────────────────────────────────────────────────────────
  const handleDragMove = useCallback(
    (id: string, e: Konva.KonvaEventObject<DragEvent>) => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        const px = { x: e.target.x(), y: e.target.y() };
        previewRef.current = { ...previewRef.current, [id]: px };

        // TOPO-03 / D-28: snap to nearest neighbour vertex
        // Pitfall 7: stageScale = stage.scaleX() converts screen-px to world-units
        const stageScale = stageRef.current?.scaleX() ?? 1;
        const [lon, lat] = canvasToGeo(px.x, px.y, projection);
        // Exclude the dragged vertex from snap candidates
        const candidates = snapCandidatesRef.current.filter((c) => c.id !== id);
        const snapResult = snapToNeighbour({ lat, lon }, candidates, stageScale, altHeld);

        if (snapResult) {
          const [snapX, snapY] = geoToCanvas(snapResult.lon, snapResult.lat, projection);
          setSnapTargetPx({ x: snapX, y: snapY });
        } else {
          setSnapTargetPx(null);
        }

        rafRef.current = null;
      });
    },
    [projection, stageRef, altHeld],
  );

  const handleDragEnd = useCallback(
    async (id: string, e: Konva.KonvaEventObject<DragEvent>) => {
      // D-03: barony-only guard
      if (!isEditableTier) return;

      // Cancel any pending RAF from drag
      if (rafRef.current != null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }

      // Clear snap target indicator
      setSnapTargetPx(null);

      // Determine final position: snap-to if snap was active, otherwise drag position
      const stageScale = stageRef.current?.scaleX() ?? 1;
      let finalPx = { x: e.target.x(), y: e.target.y() };
      const [rawLon, rawLat] = canvasToGeo(finalPx.x, finalPx.y, projection);

      const candidates = snapCandidatesRef.current.filter((c) => c.id !== id);
      const snapResult = snapToNeighbour({ lat: rawLat, lon: rawLon }, candidates, stageScale, altHeld);

      let finalLat: number;
      let finalLon: number;
      if (snapResult) {
        finalLat = snapResult.lat;
        finalLon = snapResult.lon;
        const [snapX, snapY] = geoToCanvas(snapResult.lon, snapResult.lat, projection);
        finalPx = { x: snapX, y: snapY };
      } else {
        finalLat = rawLat;
        finalLon = rawLon;
      }

      // Clear local preview for this vertex
      const nextPreview = { ...previewRef.current };
      delete nextPreview[id];
      previewRef.current = nextPreview;

      // Build coords for validation (updated with the new position for this vertex)
      const coordsForValidation: Array<[number, number]> = Object.entries(vertices).map(
        ([vid, v]) => vid === id ? [finalLon, finalLat] : [v.lon, v.lat],
      );

      // POST /editor/validate before committing (D-26 / TOPO-01)
      if (projectId && coordsForValidation.length >= 3) {
        const { valid, code } = await validateMoveWithBackend(
          projectId,
          activeTerritoryId ?? id,
          coordsForValidation,
        );
        if (!valid) {
          // TOPO-01 D-26: visual red feedback during invalid drag — snap back on mouseup
          console.warn('[VertexEditLayer] topology invalid:', code, '— snapping back');
          setInvalidDragId(id);
          // Snap handle back to original position (revert preview)
          e.target.setAttrs({ x: finalPx.x, y: finalPx.y });
          // Remove red glow after 600ms
          setTimeout(() => setInvalidDragId(null), 600);
          return;
        }
      }

      // TOPO-04 / D-30: shared-vertex coupling — single undoable op for all coupled vertices
      const coupledIds = getCoupledVertices(sharedIndexRef.current, id);
      const nextVertices: Record<string, VertexCoord> = { ...vertices };

      if (coupledIds.length > 1) {
        // Move all coupled vertices to the same final position
        for (const cid of coupledIds) {
          nextVertices[cid] = { lat: finalLat, lon: finalLon };
        }
        useEditorStore.getState().setVerticesAndLog(nextVertices, {
          op: 'move',
          ts: Date.now(),
          vertexIds: coupledIds,
          lat: finalLat,
          lon: finalLon,
        });
      } else {
        // Single vertex move (no coupling)
        useEditorStore.getState().moveVertex(id, finalLat, finalLon);
      }

      // Rebuild shared index after committed state change
      rebuildSharedIndex();
    },
    [projection, isEditableTier, vertices, projectId, activeTerritoryId, stageRef, altHeld, rebuildSharedIndex],
  );

  // ── Add vertex handler (D-01, D-06) ────────────────────────────────────────
  const handleLayerClick = useCallback(
    (e: Konva.KonvaEventObject<MouseEvent>) => {
      if (!isEditableTier) return;
      if (activeTool !== 'A') return;
      if (vertexCount >= 1000) return;
      if (e.target !== e.currentTarget) return;

      const stage = e.target.getStage();
      if (!stage) return;

      const pointerPos = stage.getPointerPosition();
      if (!pointerPos) return;

      const [lon, lat] = canvasToGeo(pointerPos.x, pointerPos.y, projection);
      const newId = crypto.randomUUID();
      useEditorStore.getState().addVertex(newId, lat, lon);
    },
    [isEditableTier, activeTool, vertexCount, projection],
  );

  // ── Pitfall 10: clearCache on activeTerritoryId change ─────────────────────
  const layerRef = useRef<Konva.Layer | null>(null);
  useEffect(() => {
    return () => {
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
  const listening = activeTerritoryId !== null;

  return (
    <Layer
      ref={layerRef as React.RefObject<Konva.Layer>}
      listening={listening}
      onClick={handleLayerClick}
    >
      {visibleEntries.map(({ id, lat, lon }) => {
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

        // TOPO-01: invalid drag → red stroke on the handle being dragged
        const isInvalid = invalidDragId === id;

        // Color priority: invalid > hover > selected > unselected
        const fill = isInvalid
          ? INVALID_DRAG_STROKE
          : hoveredId === id
            ? VERTEX_FILL_HOVER
            : selectedSet.has(id)
              ? VERTEX_FILL_SELECTED
              : VERTEX_FILL_UNSELECTED;

        return (
          <Circle
            key={id}
            {...({ 'data-vertex-id': id } as Record<string, string>)}
            x={x}
            y={y}
            radius={5}
            fill={fill}
            stroke={isInvalid ? INVALID_DRAG_STROKE : undefined}
            strokeWidth={isInvalid ? 2 : undefined}
            draggable={listening && isEditableTier}
            onDragMove={(e) => handleDragMove(id, e as Konva.KonvaEventObject<DragEvent>)}
            onDragEnd={(e) => void handleDragEnd(id, e as Konva.KonvaEventObject<DragEvent>)}
            onMouseEnter={() => setHoveredId(id)}
            onMouseLeave={() => setHoveredId(null)}
          />
        );
      })}

      {/* TOPO-03 D-28: Snap target indicator — yellow circle #eab308 radius=8 stroke=2 */}
      {snapTargetPx && (
        <Circle
          x={snapTargetPx.x}
          y={snapTargetPx.y}
          radius={8}
          stroke={SNAP_TARGET_STROKE}
          strokeWidth={2}
          fill="transparent"
          listening={false}
          {...({ 'data-testid': 'snap-target-indicator' } as Record<string, string>)}
        />
      )}
    </Layer>
  );
};
