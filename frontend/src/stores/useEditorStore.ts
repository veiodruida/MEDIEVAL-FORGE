/* Phase 08 D-25 + D-V3-04: NEW store (not restored from deleted v1).
 * zundo temporal middleware; scope = editor ops only (D-25).
 * Partialize narrows history to {vertices, editLog} — selection/activeTool excluded.
 *
 * WARNING-6 fix: setVerticesAndLog is the SINGLE chokepoint for all undoable
 * vertex mutations. Plans 08-06a/b/07/08 inherit the sink wiring for free.
 *
 * Gemini review (UX): undoLabels/redoLabels string[] mirror zundo
 * pastStates/futureStates. Every undoable commit appends an op-type label;
 * undo()/redo() move labels between stacks via temporal.subscribe. Surfaced in
 * toolbar tooltip by 08-09.
 *
 * D-37: auto-snapshot every 25 edits. editsSinceSnapshot counter increments on
 * every undoable commit; resets to 0 when snapshot_persisted confirmed by sink.
 *
 * localStorage persists active_branch_id per D-37 (worst-case crash <25 edits).
 */
import { create } from 'zustand';
import { temporal } from 'zundo';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type EditTool = 'V' | 'A' | 'D' | 'S' | 'M' | null;
export type LandmaskMode = 'manual' | 'auto-immediate';

export interface EditOp {
  op:
    | 'move' | 'add' | 'delete' | 'split' | 'merge' | 'translate'
    | 'simplify' | 'multi_delete'
    // Phase 08 Plan 08 — landmask ops (WARNING-6 chokepoint, D-35)
    | 'landmask_vertex_move' | 'landmask_vertex_add' | 'landmask_vertex_delete';
  ts: number;
  vertexIds?: string[];
  lat?: number;
  lon?: number;
  // Additional op-specific fields supplied by polygon ops (split/merge/translate)
  [key: string]: unknown;
}

export interface VertexCoord {
  lat: number;
  lon: number;
}

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

interface EditorState {
  // Branch state (NOT in zundo history — D-25)
  activeBranchId: string | null;
  landmaskMode: LandmaskMode;

  // Tool state (NOT in zundo history)
  activeTool: EditTool;
  activeTerritoryId: string | null;

  // Selection (NOT in zundo history — UI-SPEC Notes #2)
  selectedVertexIds: string[];

  // Editable state (IN zundo history — partialized)
  vertices: Record<string, VertexCoord>;
  editLog: EditOp[];

  // Counter for D-37 auto-snapshot cadence (NOT in zundo history — counts forward only)
  editsSinceSnapshot: number;

  // Gemini review (UX): op-type label stacks mirroring pastStates / futureStates.
  // NOT inside zundo partialize — mutated explicitly in lockstep with commits +
  // undo/redo via temporal.subscribe so 08-09 toolbar can show "Undo Split" vs "Undo".
  undoLabels: string[];
  redoLabels: string[];
}

// ---------------------------------------------------------------------------
// Actions shape
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Polygon op result types (plan 08-07 — optimistic preview + /editor/apply)
// ---------------------------------------------------------------------------

export interface ApplyOpResult {
  snapshot_id: string;
  edits_since_snapshot: number;
  new_hash: string;
  new_count: number;
  allocated_original_idx: number | null;
}

interface EditorActions {
  // Non-undoable
  selectTool: (t: EditTool) => void;
  setActiveTerritoryId: (id: string | null) => void;
  setSelectedVertexIds: (ids: string[]) => void;
  setActiveBranchId: (id: string | null) => void;
  setLandmaskMode: (m: LandmaskMode) => void;

  // Undoable (vertex/polygon ops) — all funnel through setVerticesAndLog
  moveVertex: (id: string, lat: number, lon: number) => void;
  addVertex: (id: string, lat: number, lon: number) => void;
  deleteVertices: (ids: string[]) => void;  // one undoable op per D-29 marquee

  // Plan 08-07: Polygon ops (EDIT-POLYGON-01..03)
  // Each action: (1) builds optimistic local geometry via turf.js, (2) calls
  // setVerticesAndLog for undo history, (3) POSTs to /editor/apply for
  // branch-level hash bump. Backend returns NO geometry (BLOCKER-1 contract).
  splitPolygon: (
    parentId: string,
    parentCoords: Array<[number, number]>,
    cutCoords: Array<[number, number]>,
    branchId: string,
    projectId: string,
  ) => Promise<ApplyOpResult | null>;

  mergePolygons: (
    firstId: string,
    firstCoords: Array<[number, number]>,
    secondId: string,
    secondCoords: Array<[number, number]>,
    branchId: string,
    projectId: string,
  ) => Promise<ApplyOpResult | { error: 'NOT_ADJACENT' } | null>;

  translatePolygon: (
    polygonId: string,
    dLat: number,
    dLon: number,
    branchId: string,
    projectId: string,
  ) => Promise<ApplyOpResult | null>;

  // CHOKEPOINT: all undoable ops land here. Fires sink (TELEM-01) and includes
  // snapshot_payload_if_due on every 25th commit (D-37 auto-snapshot).
  setVerticesAndLog: (next: Record<string, VertexCoord>, op: EditOp) => void;
}

// ---------------------------------------------------------------------------
// Edit-event sink (WARNING-6)
// ---------------------------------------------------------------------------

export interface EditEventSinkPayload {
  branchId: string | null;
  op: EditOp;
  edits_since_snapshot: number;
  snapshot_payload_if_due?: { vertices: Record<string, VertexCoord>; editLog: EditOp[] };
}

export type EditEventSink = (
  payload: EditEventSinkPayload,
) => Promise<{ snapshot_persisted?: boolean } | void>;

// Module-level sink reference — registered by EditorSyncBridge after
// useAppendEditEvent mutation is constructed. Single chokepoint so 08-06a/b/07/08
// inherit the wiring for free.
let _editEventSink: EditEventSink | null = null;

export function registerEditEventSink(sink: EditEventSink | null): void {
  _editEventSink = sink;
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useEditorStore = create<EditorState & EditorActions>()(
  temporal(
    (set, get) => ({
      // Initial state
      activeBranchId: null,
      landmaskMode: 'manual',
      activeTool: null,
      activeTerritoryId: null,
      selectedVertexIds: [],
      vertices: {},
      editLog: [],
      editsSinceSnapshot: 0,
      undoLabels: [],
      redoLabels: [],

      // Non-undoable actions
      selectTool: (t) => set({ activeTool: t }),
      setActiveTerritoryId: (id) => set({ activeTerritoryId: id }),
      setSelectedVertexIds: (ids) => set({ selectedVertexIds: ids }),
      setActiveBranchId: (id) => set({ activeBranchId: id }),
      setLandmaskMode: (m) => set({ landmaskMode: m }),

      // Undoable actions — all delegate to setVerticesAndLog (chokepoint)
      moveVertex: (id, lat, lon) => {
        const next = { ...get().vertices, [id]: { lat, lon } };
        get().setVerticesAndLog(next, { op: 'move', ts: Date.now(), vertexIds: [id], lat, lon });
      },

      addVertex: (id, lat, lon) => {
        const next = { ...get().vertices, [id]: { lat, lon } };
        get().setVerticesAndLog(next, { op: 'add', ts: Date.now(), vertexIds: [id], lat, lon });
      },

      deleteVertices: (ids) => {
        const next = { ...get().vertices };
        ids.forEach((i) => delete next[i]);
        get().setVerticesAndLog(next, { op: 'multi_delete', ts: Date.now(), vertexIds: ids });
      },

      // ── Plan 08-07: Polygon ops ────────────────────────────────────────────

      splitPolygon: async (parentId, parentCoords, cutCoords, branchId, projectId) => {
        // Step 1: Optimistic preview via turf.js lineSplit
        // Import turf lazily to keep initial bundle lean
        const turfLineSplit = await import('@turf/line-split').then((m) => m.default ?? m.lineSplit ?? m);
        const turfHelpers = await import('@turf/helpers');

        const parentPoly = turfHelpers.polygon([[...parentCoords, parentCoords[0]]]);
        const cutLine = turfHelpers.lineString(cutCoords);

        try {
          // Optimistic preview via turf — result not used for store state directly;
          // canonical vertex reconciliation happens when /render is invoked (BLOCKER-1 / D-17).
          turfLineSplit(cutLine, parentPoly);
        } catch {
          // Optimistic preview fails gracefully — backend still validates
        }

        // Step 2: Build optimistic next-vertices from pieces (simplified: keep existing vertices unchanged)
        const currentVertices = get().vertices;
        // setVerticesAndLog with the op for undo history (no geometry change to vertices map here —
        // full vertex reconciliation happens when /render is invoked in 08-07c)
        get().setVerticesAndLog(currentVertices, {
          op: 'split',
          ts: Date.now(),
          parentId,
          parentCoords,
          cutCoords,
        });

        // Step 3: POST /editor/apply for branch-level hash bump + original_idx allocation
        try {
          const resp = await fetch(`/api/v3/projects/${projectId}/editor/apply`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              op_type: 'split',
              payload: {
                parent_id: parentId,
                parent_coords: parentCoords,
                cut_coords: cutCoords,
                child_name: `${parentId} (2)`,
              },
              branch_id: branchId,
            }),
          });
          if (!resp.ok) {
            console.warn('[useEditorStore] /editor/apply split failed:', resp.status);
            return null;
          }
          const result = (await resp.json()) as ApplyOpResult;
          // Step 4: server allocated original_idx — log it for downstream use
          if (result.allocated_original_idx != null) {
            // Patch local state with allocated idx for reference (not in undo history)
            useEditorStore.setState({
              editLog: [
                ...get().editLog.slice(0, -1),
                {
                  ...get().editLog[get().editLog.length - 1],
                  allocated_original_idx: result.allocated_original_idx,
                },
              ],
            });
          }
          return result;
        } catch (err) {
          console.warn('[useEditorStore] /editor/apply split network error', err);
          return null;
        }
      },

      mergePolygons: async (firstId, firstCoords, secondId, secondCoords, branchId, projectId) => {
        // Step 1: Client-side adjacency check via turf.js booleanTouches
        const booleanTouches = await import('@turf/boolean-touches').then((m) => m.default ?? m.booleanTouches ?? m);
        const turfHelpers = await import('@turf/helpers');

        const polyA = turfHelpers.polygon([[...firstCoords, firstCoords[0]]]);
        const polyB = turfHelpers.polygon([[...secondCoords, secondCoords[0]]]);

        let clientAdjacent = false;
        try {
          clientAdjacent = booleanTouches(polyA, polyB);
        } catch {
          // Turf error → let backend decide
          clientAdjacent = true;
        }

        if (!clientAdjacent) {
          // Fast client-side rejection — no API call, no edit event
          return { error: 'NOT_ADJACENT' as const };
        }

        // Step 2: Compute optimistic union via turf.js union
        const turfUnion = await import('@turf/union').then((m) => m.default ?? m.union ?? m);
        let mergedCoords: Array<[number, number]> = [];
        try {
          const unionResult = turfUnion(turfHelpers.featureCollection([polyA, polyB]));
          if (unionResult?.geometry?.type === 'Polygon') {
            mergedCoords = unionResult.geometry.coordinates[0] as Array<[number, number]>;
          }
        } catch {
          // Optimistic union fails gracefully
        }

        // Step 3: Optimistic local update (no vertices map change — canonical in 08-07c)
        const currentVertices = get().vertices;
        get().setVerticesAndLog(currentVertices, {
          op: 'merge',
          ts: Date.now(),
          firstId,
          firstCoords,
          secondId,
          secondCoords,
          mergedCoords,
        });

        // Step 4: POST /editor/apply; server re-validates adjacency
        try {
          const resp = await fetch(`/api/v3/projects/${projectId}/editor/apply`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              op_type: 'merge',
              payload: {
                first_id: firstId,
                first_coords: firstCoords,
                second_id: secondId,
                second_coords: secondCoords,
              },
              branch_id: branchId,
            }),
          });
          if (resp.status === 400) {
            const body = (await resp.json()) as { detail?: string };
            if (body.detail?.includes('NOT_ADJACENT')) {
              // Server disagrees — rollback via zundo undo
              useEditorStore.temporal.getState().undo();
              return { error: 'NOT_ADJACENT' as const };
            }
          }
          if (!resp.ok) {
            console.warn('[useEditorStore] /editor/apply merge failed:', resp.status);
            useEditorStore.temporal.getState().undo();
            return null;
          }
          return (await resp.json()) as ApplyOpResult;
        } catch (err) {
          console.warn('[useEditorStore] /editor/apply merge network error', err);
          useEditorStore.temporal.getState().undo();
          return null;
        }
      },

      translatePolygon: async (polygonId, dLat, dLon, branchId, projectId) => {
        // Step 1: Optimistic local update — apply delta to all vertices of the polygon
        // (vertices map holds individual vertex coords; polygon boundary = all vertices)
        const currentVertices = get().vertices;
        const nextVertices: Record<string, VertexCoord> = {};
        for (const [id, v] of Object.entries(currentVertices)) {
          nextVertices[id] = { lat: v.lat + dLat, lon: v.lon + dLon };
        }
        get().setVerticesAndLog(nextVertices, {
          op: 'translate',
          ts: Date.now(),
          polygonId,
          dLat,
          dLon,
        });

        // Step 2: POST /editor/apply for branch hash bump
        try {
          const resp = await fetch(`/api/v3/projects/${projectId}/editor/apply`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              op_type: 'translate',
              payload: { polygon_id: polygonId, d_lat: dLat, d_lon: dLon },
              branch_id: branchId,
            }),
          });
          if (!resp.ok) {
            console.warn('[useEditorStore] /editor/apply translate failed:', resp.status);
            return null;
          }
          return (await resp.json()) as ApplyOpResult;
        } catch (err) {
          console.warn('[useEditorStore] /editor/apply translate network error', err);
          return null;
        }
      },

      // CHOKEPOINT — every undoable commit lands here.
      // 1. Updates vertices + editLog (enters zundo history).
      // 2. Appends op-type to undoLabels (Gemini UX); clears redoLabels (new commit invalidates redo).
      // 3. Fires the registered edit-event sink (TELEM-01).
      // 4. On 25th commit, includes snapshot_payload_if_due (D-37 auto-snapshot).
      setVerticesAndLog: (next, op) => {
        set((s) => ({
          vertices: next,
          editLog: [...s.editLog, op],
          editsSinceSnapshot: s.editsSinceSnapshot + 1,
          // Gemini review (UX): new commit invalidates redo stack (mirrors zundo clearing futureStates)
          undoLabels: [...s.undoLabels, op.op],
          redoLabels: [],
        }));

        const after = get();
        const sink = _editEventSink;
        if (sink) {
          const dueForSnapshot =
            after.editsSinceSnapshot > 0 && after.editsSinceSnapshot % 25 === 0;
          Promise.resolve(
            sink({
              branchId: after.activeBranchId,
              op,
              edits_since_snapshot: after.editsSinceSnapshot,
              snapshot_payload_if_due: dueForSnapshot
                ? { vertices: after.vertices, editLog: after.editLog }
                : undefined,
            }),
          )
            .then((res) => {
              if (res && res.snapshot_persisted) {
                // D-37: reset counter after confirmed auto-snapshot
                useEditorStore.setState({ editsSinceSnapshot: 0 });
              }
            })
            .catch(() => {
              // Silent — sink retries via TanStack mutation queue
            });
        }
      },
    }),
    {
      // D-25: history scope = editor ops only.
      // selectedVertexIds + activeTool + editsSinceSnapshot + undoLabels/redoLabels
      // are deliberately excluded.
      partialize: (s) => ({ vertices: s.vertices, editLog: s.editLog }),
      limit: 100, // D-25 history cap
      // equality: compare by reference for vertices and editLog arrays/objects.
      // Without equality, zundo compares the *new object* from partialize() to the
      // *old object* via Object.is — always false (different refs) → every setState
      // (even selectTool) would push to pastStates. Referential equality on the two
      // partialize fields means only real vertex/editLog mutations add history.
      equality: (a, b) => a.vertices === b.vertices && a.editLog === b.editLog,
    },
  ),
);

// ---------------------------------------------------------------------------
// Gemini review (UX): keep undoLabels/redoLabels in lockstep with zundo stacks.
// Subscribe to temporal state changes; detect undo vs redo vs clear by comparing
// previous and current pastStates/futureStates lengths.
//
// IMPORTANT: We must NOT call useEditorStore.setState() inside this subscriber —
// that would trigger zundo's wrapped store.setState which calls temporalHandleSet
// which triggers the subscriber again → infinite recursion (stack overflow).
//
// Solution: use the internal Zustand vanilla setState stored via getInternalSet()
// before the zundo wrapper overwrites it. This bypasses zundo's tracking for
// label-only updates (undoLabels/redoLabels are outside partialize anyway).
// ---------------------------------------------------------------------------

// Capture the vanilla Zustand setState before zundo wraps it.
// zundo wraps store.setState at middleware init time; we call getInternalSet()
// AFTER store creation — at that point store.setState IS the zundo-wrapped version.
// So we need a different approach: store a raw updater via the temporal handleSet hook
// or use getState() + setState() with a guard flag.

let _suppressSubscribe = false;
let _prevPastLen = 0;
let _prevFutureLen = 0;

useEditorStore.temporal.subscribe((temporalState) => {
  // Guard: if we're already inside this callback, skip (shouldn't happen with flag)
  if (_suppressSubscribe) return;

  const pastLen = temporalState.pastStates.length;
  const futureLen = temporalState.futureStates.length;

  const s = useEditorStore.getState();

  let nextUndoLabels: string[] | null = null;
  let nextRedoLabels: string[] | null = null;

  if (pastLen < _prevPastLen && futureLen > _prevFutureLen) {
    // undo() — pop one from undoLabels onto redoLabels
    if (s.undoLabels.length > 0) {
      const moved = s.undoLabels[s.undoLabels.length - 1];
      nextUndoLabels = s.undoLabels.slice(0, -1);
      nextRedoLabels = [...s.redoLabels, moved];
    }
  } else if (futureLen < _prevFutureLen && pastLen > _prevPastLen) {
    // redo() — pop one from redoLabels onto undoLabels
    if (s.redoLabels.length > 0) {
      const moved = s.redoLabels[s.redoLabels.length - 1];
      nextRedoLabels = s.redoLabels.slice(0, -1);
      nextUndoLabels = [...s.undoLabels, moved];
    }
  } else if (pastLen === 0 && futureLen === 0) {
    // temporal.clear() (branch switch) — reset both label stacks
    nextUndoLabels = [];
    nextRedoLabels = [];
  }

  if (nextUndoLabels !== null || nextRedoLabels !== null) {
    _suppressSubscribe = true;
    // Use the zundo-wrapped setState but with only non-partialized fields.
    // Since undoLabels/redoLabels are NOT in partialize({vertices, editLog}),
    // zundo's temporalHandleSet will compute pastState === currentState for the
    // partialized slice → equality check passes → no history entry added.
    // We add an explicit equality option to ensure this: see partialize config above.
    // Additionally, _suppressSubscribe prevents the re-entrant subscribe call from
    // doing anything even if the subscriber fires again during setState.
    useEditorStore.setState({
      ...(nextUndoLabels !== null ? { undoLabels: nextUndoLabels } : {}),
      ...(nextRedoLabels !== null ? { redoLabels: nextRedoLabels } : {}),
    });
    _suppressSubscribe = false;
  }

  _prevPastLen = pastLen;
  _prevFutureLen = futureLen;
});

// ---------------------------------------------------------------------------
// switchBranch — D-25 + D-37
// Rehydrates store from branch snapshot and clears temporal history.
// localStorage stores active_branch_id per D-37.
// ---------------------------------------------------------------------------

const LS_KEY = 'medieval-forge:active_branch_id';

export function switchBranch(
  branchId: string,
  snapshotPayload: {
    vertices: Record<string, VertexCoord>;
    editLog: EditOp[];
  },
): void {
  useEditorStore.setState({
    activeBranchId: branchId,
    vertices: snapshotPayload.vertices,
    editLog: snapshotPayload.editLog,
    selectedVertexIds: [],
    activeTool: null,
    activeTerritoryId: null,
    editsSinceSnapshot: 0,
    // Label stacks reset here for safety; temporal.subscribe also resets them on clear()
    undoLabels: [],
    redoLabels: [],
  });
  // D-25: clear history on branch switch
  useEditorStore.temporal.getState().clear();
  // D-37: persist active branch to localStorage
  try {
    localStorage.setItem(LS_KEY, branchId);
  } catch {
    // Ignore storage errors (private browsing, quota exceeded)
  }
}

export function loadPersistedActiveBranchId(): string | null {
  try {
    return localStorage.getItem(LS_KEY);
  } catch {
    return null;
  }
}
