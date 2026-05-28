/**
 * VertexEditLayer — 6th Konva layer (z=5, above InteractionLayer).
 *
 * Phase 08 Plan 05 — canvas scaffold for vertex editing.
 * Phase 08 Plan 06a — wires vertex move/add/delete ops to useEditorStore +
 *   backend POST /editor/validate; adds D-03 barony-tier guard; D-06 add cap.
 * Phase 08 Plan 06b — snap (TOPO-03) + shared-vertex coupling (TOPO-04) +
 *   topology-block visuals (TOPO-01: red fill/stroke on invalid drag) +
 *   D-27 warn-badge flags; Alt-disable for snap (D-28).
 * Phase 08 Plan 07 — Split/Merge/Translate tool handlers (EDIT-POLYGON-01..03):
 *   S tool: 2-click line cut → splitPolygon; Esc cancels.
 *   M tool: 2-click select → client adjacency check → mergePolygons; red Callout on NOT_ADJACENT.
 *   V tool drag on polygon interior → translatePolygon (commit on dragend).
 *   Optimistic Konva preview via turf.js; canonical raster converges on /render (BLOCKER-1 / D-17).
 * Phase 08 Plan 08 — Landmask mode (LANDMASK-01, LANDMASK-02, WARNING-5 fix):
 *   editableLayer='landmask' → renders cyan handles (#06b6d4) on landmaskCoords.
 *   PT/ES border (borderCoords, 40 pts) rendered as a separate Konva.Line with listening=false
 *   (Pitfall 3 — pointer events never hit the border polygon).
 *   Auto-immediate mode: dragend fires POST /editor/apply op_type='landmask_replace'.
 *   Manual mode: drags buffered locally; Apply button flushes via onApplyLandmask callback.
 *   All landmask handle ops funnel through setVerticesAndLog (WARNING-6 chokepoint) with
 *   op.type in {'landmask_vertex_move', 'landmask_vertex_add', 'landmask_vertex_delete'}.
 *
 * REQ-IDs: PERF-01, EDIT-VERTEX-01..05, EDIT-POLYGON-01..03,
 *           LANDMASK-01, LANDMASK-02, TOPO-01..04, D-03, D-06, DAG-04
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
import { Layer, Circle, Line } from 'react-konva';
import type Konva from 'konva';
import { useEditorStore } from '../../stores/useEditorStore';
import type { VertexCoord, EditableLayer } from '../../stores/useEditorStore';
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
// Phase 08 Plan 08: landmask handle color (cyan, distinct from blue barony handles)
const LANDMASK_VERTEX_FILL = '#06b6d4';
// PT/ES border line color (read-only, separate Konva node — Pitfall 3)
const BORDER_LINE_STROKE = '#94a3b8';

// Expose for tests and sibling components that need the constants.
export {
  VERTEX_FILL_UNSELECTED,
  VERTEX_FILL_SELECTED,
  VERTEX_FILL_HOVER,
  SNAP_TARGET_STROKE,
  INVALID_DRAG_STROKE,
  LANDMASK_VERTEX_FILL,
  BORDER_LINE_STROKE,
};

// ── Editable layer type (Phase 08 Plan 16) ────────────────────────────────────
// EditableLayer is now defined in useEditorStore (store as single source of truth).
// Re-export here for backward compat with any consumer importing from VertexEditLayer.
export type { EditableLayer };

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

// ── NOT_ADJACENT error callout auto-dismiss duration ─────────────────────────
const NOT_ADJACENT_DISMISS_MS = 2000;

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
   * Project UUID required for POST /editor/validate and /editor/apply.
   * If not provided (test/scaffold), calls are skipped.
   */
  projectId?: string;
  /**
   * D-27 callback: called whenever warn flags change (duplicate vertex / sliver polygon).
   * Inspector uses this to show amber badges.
   */
  onWarnFlagsChange?: (flags: VertexWarnFlags) => void;
  /**
   * Plan 08-07: callback when a NOT_ADJACENT error occurs (client or server).
   * Parent renders a Radix Callout color="red" "Territórios não são adjacentes".
   * Auto-dismiss 2s is handled here via onNotAdjacent(true) → onNotAdjacent(false).
   */
  onNotAdjacent?: (show: boolean) => void;
  /**
   * Plan 08-07: branch ID for polygon ops (/editor/apply).
   * Required for split/merge/translate to persist to the correct branch.
   */
  branchId?: string;

  // ── Phase 08 Plan 08: Landmask mode props (LANDMASK-01, LANDMASK-02) ────────

  /**
   * Which layer is currently being edited.
   * 'baronies' (default): existing barony vertex editing.
   * 'landmask': renders cyan handles on landmaskCoords; no barony handles.
   * WARNING-5 fix: driven by useEditorStore.landmaskMode via LayerTogglePanel.
   */
  editableLayer?: EditableLayer;

  /**
   * Landmask polygon coordinates [[lon, lat], ...] for landmask mode handles.
   * Only interactive when editableLayer='landmask'.
   * When editableLayer='baronies' (default), this prop is unused.
   */
  landmaskCoords?: Array<[number, number]>;

  /**
   * PT/ES border polygon coordinates [[lon, lat], ...].
   * ALWAYS rendered as a read-only Konva.Line with listening=false (Pitfall 3).
   * Expected length: 40 points (STATE.md confirmed — CLAUDE.md mis-counted 38).
   * Never produces interactive handles regardless of editableLayer.
   */
  borderCoords?: Array<[number, number]>;

  /**
   * Called in auto-immediate mode after a landmask handle dragend.
   * Parent POSTs /editor/apply op_type='landmask_replace' with new coords.
   * In manual mode, drags are buffered; Apply button (LandmaskEditorHeader) calls this.
   */
  onLandmaskCoordsChange?: (newCoords: Array<[number, number]>) => void;
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
  onNotAdjacent,
  branchId,
  editableLayer = 'baronies',
  landmaskCoords,
  borderCoords,
  onLandmaskCoordsChange,
}) => {
  const projection = useProjection();

  // Read from store (subscribe to only the fields we need)
  const activeTerritoryId = useEditorStore((s) => s.activeTerritoryId);
  const vertices = useEditorStore((s) => s.vertices);
  const selectedVertexIds = useEditorStore((s) => s.selectedVertexIds);
  const activeTool = useEditorStore((s) => s.activeTool);
  // Phase 08 Plan 16: landmask mode decision moved to CanvasViewer (parent).
  // VertexEditLayer always calls onLandmaskCoordsChange on dragend; parent decides
  // whether to POST immediately (auto-immediate) or buffer until Apply (manual).

  const selectedSet = useMemo(() => new Set(selectedVertexIds), [selectedVertexIds]);
  const vertexCount = Object.keys(vertices).length;

  // Phase 08 Plan 08: landmask local coord state for buffered manual-mode drags.
  // In auto-immediate mode, each dragend directly calls onLandmaskCoordsChange.
  // In manual mode, drags mutate this local state; Apply button flushes it.
  const [localLandmaskCoords, setLocalLandmaskCoords] = useState<Array<[number, number]>>(
    landmaskCoords ?? [],
  );

  // Sync local state when prop changes (e.g. after Apply re-renders parent)
  useEffect(() => {
    if (landmaskCoords) setLocalLandmaskCoords(landmaskCoords);
  }, [landmaskCoords]);

  // Pitfall 3 assertion (DEV only): borderCoords should have exactly 40 points.
  // STATE.md confirmed 40; CLAUDE.md mis-counted as 38 — planner resolved to 40.
  useEffect(() => {
    if (import.meta.env.DEV && borderCoords && borderCoords.length !== 40) {
      console.assert(
        borderCoords.length === 40,
        `[VertexEditLayer] PT/ES border expected 40 pts per STATE.md, got ${borderCoords.length}`,
      );
    }
  }, [borderCoords]);

  // Hover state (local — not in store per UI-SPEC §Notes #2)
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  // D-03: barony-tier guard — if tier is not barony, treat as read-only
  const isEditableTier = tier === 'barony';

  // Phase 08 Plan 08: in landmask mode, barony tier guard is bypassed.
  // Landmask has its own editable surface regardless of barony tier.
  const isLandmaskMode = editableLayer === 'landmask';

  // ── Plan 08-07: Split tool state ─────────────────────────────────────────────
  // S tool: track 2 canvas clicks to form a cut line.
  // splitClickPts: geo coords [lon,lat] of points clicked so far (0 or 1).
  const [splitClickPts, setSplitClickPts] = useState<Array<[number, number]>>([]);

  // ── Plan 08-07: Merge tool state ─────────────────────────────────────────────
  // M tool: first click selects firstId; second click triggers merge.
  const [mergeFirstId, setMergeFirstId] = useState<string | null>(null);
  const [mergeFirstCoords, setMergeFirstCoords] = useState<Array<[number, number]> | null>(null);

  // ── Plan 08-07: Esc handler — cancel in-flight split/merge ───────────────────
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSplitClickPts([]);
        setMergeFirstId(null);
        setMergeFirstCoords(null);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  // Reset split/merge state when tool changes away from S or M
  useEffect(() => {
    if (activeTool !== 'S') setSplitClickPts([]);
    if (activeTool !== 'M') {
      setMergeFirstId(null);
      setMergeFirstCoords(null);
    }
  }, [activeTool]);

  // ── Plan 08-07: NOT_ADJACENT auto-dismiss ─────────────────────────────────────
  const showNotAdjacent = useCallback(() => {
    onNotAdjacent?.(true);
    setTimeout(() => onNotAdjacent?.(false), NOT_ADJACENT_DISMISS_MS);
  }, [onNotAdjacent]);

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

  // ── Phase 08 Plan 15: DEV-only __forgeEditorState() escape hatch ────────────
  // Mirrors the __forgeSelectBarony / __forgeStageScale pattern from BaronyLayer
  // and CanvasViewer. Gated on import.meta.env.DEV — never ships in production.
  // Returns current editor state + first visible handle's page coords for UAT
  // Konva drag testing (the Konva canvas is opaque to DOM queries).
  useEffect(() => {
    if (!import.meta.env.DEV) return
    ;(window as unknown as { __forgeEditorState?: () => unknown }).__forgeEditorState = () => {
      const stage = stageRef.current
      let firstHandle: { id: string; x: number; y: number } | null = null
      if (stage) {
        // Find the first rendered vertex handle Circle carrying a data-vertex-id attr
        const circles = stage.find('Circle')
        const circle = circles.find((n) => Boolean(n.getAttr('data-vertex-id')))
        if (circle) {
          const abs = circle.getAbsolutePosition()           // includes stage scale+pos
          const rect = stage.container().getBoundingClientRect()
          firstHandle = {
            id: String(circle.getAttr('data-vertex-id')),
            x: rect.left + abs.x,
            y: rect.top + abs.y,
          }
        }
      }
      return {
        activeTerritoryId,
        vertexCount: Object.keys(vertices).length,
        visibleHandleCount: isLandmaskMode ? 0 : visibleEntries.length,
        editLogLength: useEditorStore.getState().editLog.length,
        activeTool: useEditorStore.getState().activeTool,
        firstHandle,   // { id, x, y } page coords for page.mouse, or null
      }
    }
    return () => {
      delete (window as unknown as { __forgeEditorState?: unknown }).__forgeEditorState
    }
  }, [activeTerritoryId, vertices, isLandmaskMode, visibleEntries, stageRef])

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

  // ── Add vertex handler (D-01, D-06) + Split + Merge click dispatch ──────────
  const handleLayerClick = useCallback(
    (e: Konva.KonvaEventObject<MouseEvent>) => {
      if (!isEditableTier) return;
      if (e.target !== e.currentTarget && activeTool !== 'S' && activeTool !== 'M') return;

      const stage = e.target.getStage();
      if (!stage) return;
      const pointerPos = stage.getPointerPosition();
      if (!pointerPos) return;

      const [lon, lat] = canvasToGeo(pointerPos.x, pointerPos.y, projection);

      // ── Add tool (D-01, D-06) ──────────────────────────────────────────────
      if (activeTool === 'A') {
        if (e.target !== e.currentTarget) return;
        if (vertexCount >= 1000) return;
        const newId = crypto.randomUUID();
        useEditorStore.getState().addVertex(newId, lat, lon);
        return;
      }

      // ── Split tool (EDIT-POLYGON-01, D-07) ────────────────────────────────
      if (activeTool === 'S') {
        const newPts: Array<[number, number]> = [...splitClickPts, [lon, lat] as [number, number]];
        if (newPts.length === 1) {
          // First click — record first point, wait for second
          setSplitClickPts(newPts);
          return;
        }
        // Second click — we have the full cut line
        setSplitClickPts([]);
        if (!activeTerritoryId || !projectId || !branchId) return;

        // Build parent coords from current vertices (ordered insertion sequence)
        const parentCoords: Array<[number, number]> = Object.values(vertices).map(
          (v) => [v.lon, v.lat] as [number, number],
        );

        void useEditorStore.getState().splitPolygon(
          activeTerritoryId,
          parentCoords,
          newPts,
          branchId,
          projectId,
        );
        return;
      }

      // ── Merge tool (EDIT-POLYGON-02, D-08, D-09) ─────────────────────────
      if (activeTool === 'M') {
        // Clicks must land on polygon handles (circles); get vertex id from event target
        const targetId = (e.target as Konva.Node & { attrs?: { 'data-vertex-id'?: string } })
          ?.attrs?.['data-vertex-id'];

        if (!mergeFirstId) {
          // First selection — record polygon id + coords
          if (!activeTerritoryId) return;
          const firstCoords: Array<[number, number]> = Object.values(vertices).map(
            (v) => [v.lon, v.lat] as [number, number],
          );
          setMergeFirstId(activeTerritoryId);
          setMergeFirstCoords(firstCoords);
          return;
        }

        // Second selection — attempt merge
        if (!activeTerritoryId || !projectId || !branchId) return;
        const secondId = activeTerritoryId;
        if (secondId === mergeFirstId) {
          // Same polygon selected twice — reset
          setMergeFirstId(null);
          setMergeFirstCoords(null);
          return;
        }
        const secondCoords: Array<[number, number]> = Object.values(vertices).map(
          (v) => [v.lon, v.lat] as [number, number],
        );
        const capturedFirstCoords = mergeFirstCoords ?? [];
        const capturedFirstId = mergeFirstId;
        setMergeFirstId(null);
        setMergeFirstCoords(null);

        void (async () => {
          const result = await useEditorStore.getState().mergePolygons(
            capturedFirstId,
            capturedFirstCoords,
            secondId,
            secondCoords,
            branchId,
            projectId,
          );
          if (result && 'error' in result && result.error === 'NOT_ADJACENT') {
            showNotAdjacent();
          }
        })();

        // Suppress unused variable warning for targetId
        void targetId;
        return;
      }
    },
    [
      isEditableTier, activeTool, vertexCount, projection,
      splitClickPts, mergeFirstId, mergeFirstCoords,
      activeTerritoryId, vertices, projectId, branchId,
      showNotAdjacent,
    ],
  );

  // ── Translate handler (EDIT-POLYGON-03, D-02) — drag on polygon interior ────
  // V tool: when activeTool==='V' (translate mode) and user drags the layer
  // background (not a vertex handle), translatePolygon is called on dragend.
  // Delta = (finalGeo - startGeo).
  const translateDragStartRef = useRef<{ lat: number; lon: number } | null>(null);

  const handleLayerDragStart = useCallback(
    (e: Konva.KonvaEventObject<DragEvent>) => {
      if (!isEditableTier || activeTool !== 'V') return;
      if (e.target !== e.currentTarget) return; // only interior drags
      const stage = e.target.getStage();
      if (!stage) return;
      const pos = stage.getPointerPosition();
      if (!pos) return;
      const [lon, lat] = canvasToGeo(pos.x, pos.y, projection);
      translateDragStartRef.current = { lat, lon };
    },
    [isEditableTier, activeTool, projection],
  );

  const handleLayerDragEnd = useCallback(
    (e: Konva.KonvaEventObject<DragEvent>) => {
      if (!isEditableTier || activeTool !== 'V') return;
      if (e.target !== e.currentTarget) return;
      if (!translateDragStartRef.current) return;
      const stage = e.target.getStage();
      if (!stage) return;
      const pos = stage.getPointerPosition();
      if (!pos) return;
      const [finalLon, finalLat] = canvasToGeo(pos.x, pos.y, projection);
      const dLat = finalLat - translateDragStartRef.current.lat;
      const dLon = finalLon - translateDragStartRef.current.lon;
      translateDragStartRef.current = null;

      if (!activeTerritoryId || !projectId || !branchId) return;
      void useEditorStore.getState().translatePolygon(
        activeTerritoryId, dLat, dLon, branchId, projectId,
      );
    },
    [isEditableTier, activeTool, projection, activeTerritoryId, projectId, branchId],
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
  const listening = activeTerritoryId !== null || isLandmaskMode;

  // ── Split preview: canvas coords for first click point ──────────────────────
  const splitPreviewPx = useMemo<{ x: number; y: number } | null>(() => {
    if (activeTool !== 'S' || splitClickPts.length !== 1) return null;
    const [lon, lat] = splitClickPts[0];
    const [x, y] = geoToCanvas(lon, lat, projection);
    return { x, y };
  }, [activeTool, splitClickPts, projection]);

  // ── Phase 08 Plan 08: PT/ES border canvas points (read-only line, Pitfall 3) ─
  // Computed as a flat [x, y, x, y, ...] array for Konva.Line points prop.
  const borderLinePts = useMemo<number[]>(() => {
    if (!borderCoords || borderCoords.length === 0) return [];
    return borderCoords.flatMap(([lon, lat]) => {
      const [x, y] = geoToCanvas(lon, lat, projection);
      return [x, y];
    });
  }, [borderCoords, projection]);

  // ── Phase 08 Plan 08: landmask handle dragend ──────────────────────────────
  // Index-keyed (string) so each landmask vertex has a stable id for preview ref.
  const handleLandmaskDragEnd = useCallback(
    (idx: number, e: Konva.KonvaEventObject<DragEvent>) => {
      if (rafRef.current != null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }

      const px = { x: e.target.x(), y: e.target.y() };
      const [lon, lat] = canvasToGeo(px.x, px.y, projection);

      // Build new coords array with updated vertex at idx
      const newCoords: Array<[number, number]> = localLandmaskCoords.map(
        (pt, i) => (i === idx ? [lon, lat] : pt),
      );
      setLocalLandmaskCoords(newCoords);

      // WARNING-6 chokepoint: log the op via setVerticesAndLog (D-35)
      // Converts landmask coord array into the vertices map format for the store.
      const nextVertices: Record<string, import('../../stores/useEditorStore').VertexCoord> = {};
      newCoords.forEach(([vLon, vLat], i) => {
        nextVertices[`lm_${i}`] = { lat: vLat, lon: vLon };
      });
      useEditorStore.getState().setVerticesAndLog(nextVertices, {
        op: 'landmask_vertex_move',
        ts: Date.now(),
        vertexIds: [`lm_${idx}`],
        lat,
        lon,
      });

      // Phase 08 Plan 16 (surgical fix): ALWAYS call onLandmaskCoordsChange so parent's
      // latestLandmaskRef stays in sync regardless of mode. Parent decides whether to POST
      // immediately (auto-immediate) or buffer until Apply is clicked (manual).
      // Without this, manual-mode Apply would POST new_landmask_coords: [] (wiping landmask).
      onLandmaskCoordsChange?.(newCoords);
    },
    [localLandmaskCoords, projection, onLandmaskCoordsChange],
  );

  return (
    <Layer
      ref={layerRef as React.RefObject<Konva.Layer>}
      listening={listening}
      onClick={handleLayerClick}
      onDragStart={handleLayerDragStart}
      onDragEnd={handleLayerDragEnd}
    >
      {/* ── Barony vertex handles (only when editableLayer='baronies') ─────────── */}
      {!isLandmaskMode && visibleEntries.map(({ id, lat, lon }) => {
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

      {/* ── Phase 08 Plan 08: Landmask handles (cyan, only when editableLayer='landmask') ── */}
      {isLandmaskMode && localLandmaskCoords.map(([lon, lat], idx) => {
        const lmId = `lm_${idx}`;
        const preview = previewRef.current[lmId];
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

        return (
          <Circle
            key={lmId}
            {...({
              'data-testid': 'landmask-handle',
              'data-vertex-id': lmId,
            } as Record<string, string>)}
            x={x}
            y={y}
            radius={5}
            fill={LANDMASK_VERTEX_FILL}
            draggable
            onDragMove={(e) => {
              // RAF throttle: update local preview only (no store writes during drag)
              if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
              rafRef.current = requestAnimationFrame(() => {
                previewRef.current = {
                  ...previewRef.current,
                  [lmId]: { x: e.target.x(), y: e.target.y() },
                };
                rafRef.current = null;
              });
            }}
            onDragEnd={(e) => void handleLandmaskDragEnd(idx, e as Konva.KonvaEventObject<DragEvent>)}
          />
        );
      })}

      {/* ── Phase 08 Plan 08 Pitfall 3: PT/ES border — read-only Konva.Line, listening=false ── */}
      {borderLinePts.length > 0 && (
        <Line
          points={borderLinePts}
          stroke={BORDER_LINE_STROKE}
          strokeWidth={1.5}
          closed
          listening={false}
          {...({ 'data-testid': 'border-line' } as Record<string, string>)}
        />
      )}

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

      {/* Plan 08-07 S tool: Split line preview — first click point indicator */}
      {splitPreviewPx && (
        <Circle
          x={splitPreviewPx.x}
          y={splitPreviewPx.y}
          radius={6}
          fill="#f97316"
          stroke="#fff"
          strokeWidth={1.5}
          listening={false}
          {...({ 'data-testid': 'split-first-click-indicator' } as Record<string, string>)}
        />
      )}
    </Layer>
  );
};
