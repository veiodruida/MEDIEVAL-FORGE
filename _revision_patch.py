"""One-shot revision patch for Phase 08 plans. Deleted after run."""
import pathlib

# ---------- 08-04: WARNING-6 chokepoint ----------
p = pathlib.Path('.planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-04-PLAN.md')
s = p.read_text(encoding='utf-8')

old_truth = '    - "localStorage persists active_branch_id per D-37"'
new_truth = (
    '    - "localStorage persists active_branch_id per D-37"\n'
    '    - "WARNING-6 fix: setVerticesAndLog is the single chokepoint that POSTs to /branches/:id/edit-events on every undoable commit (TELEM-01); 08-06a/b/07/08 inherit for free"\n'
    '    - "snapshot_payload_if_due piggy-backs on the same POST when editLog.length crosses a multiple of 25 (D-37 auto-snapshot)"'
)
assert old_truth in s, 'truth1 missing'
s = s.replace(old_truth, new_truth)

old_truth2 = '    - "history limit = 100; oldest evicted on push"'
new_truth2 = (
    '    - "history limit = 100; oldest evicted on push"\n'
    '    - "editsSinceSnapshot counter increments on every undoable commit; resets to 0 when snapshot persisted"'
)
assert old_truth2 in s
s = s.replace(old_truth2, new_truth2)

old_behav = "    - Test: marquee delete = single setVerticesAndLog({vertices: pruned, editLog: editLog+'multi_delete'}) → pastStates +1 (one undoable op for N vertices)"
new_behav = old_behav + (
    "\n    - Test (WARNING-6): every undoable action (move/add/delete/setVerticesAndLog) invokes the registered edit-event sink exactly once with the op payload; mocked sink asserts call count"
    "\n    - Test (D-37 auto-snapshot): registering sink + performing 25 moveVertex calls → sink's 25th invocation receives snapshot_payload_if_due (current vertices+editLog) instead of undefined"
    "\n    - Test: switchBranch resets editsSinceSnapshot to 0"
)
assert old_behav in s
s = s.replace(old_behav, new_behav)

old_actions = """      moveVertex: (id, lat, lon) => set((s) => ({
        vertices: { ...s.vertices, [id]: { lat, lon } },
        editLog: [...s.editLog, { op: 'move', ts: Date.now(), vertexIds: [id], lat, lon }],
      })),
      addVertex: (id, lat, lon) => set((s) => ({
        vertices: { ...s.vertices, [id]: { lat, lon } },
        editLog: [...s.editLog, { op: 'add', ts: Date.now(), vertexIds: [id], lat, lon }],
      })),
      deleteVertices: (ids) => set((s) => {
        const next = { ...s.vertices };
        ids.forEach(i => delete next[i]);
        return {
          vertices: next,
          editLog: [...s.editLog, { op: 'multi_delete', ts: Date.now(), vertexIds: ids }],
        };
      }),
      setVerticesAndLog: (next, op) => set((s) => ({
        vertices: next, editLog: [...s.editLog, op],
      })),"""

new_actions = """      // WARNING-6 fix: every undoable action funnels through setVerticesAndLog.
      moveVertex: (id, lat, lon) => {
        const s = get();
        const next = { ...s.vertices, [id]: { lat, lon } };
        get().setVerticesAndLog(next, { op: 'move', ts: Date.now(), vertexIds: [id], lat, lon });
      },
      addVertex: (id, lat, lon) => {
        const s = get();
        const next = { ...s.vertices, [id]: { lat, lon } };
        get().setVerticesAndLog(next, { op: 'add', ts: Date.now(), vertexIds: [id], lat, lon });
      },
      deleteVertices: (ids) => {
        const s = get();
        const next = { ...s.vertices };
        ids.forEach(i => delete next[i]);
        get().setVerticesAndLog(next, { op: 'multi_delete', ts: Date.now(), vertexIds: ids });
      },
      // CHOKEPOINT — every undoable commit lands here. Fires the registered
      // edit-event sink (TELEM-01) and includes snapshot_payload_if_due on every
      // 25th commit (D-37 auto-snapshot).
      setVerticesAndLog: (next, op) => {
        set((s) => ({
          vertices: next,
          editLog: [...s.editLog, op],
          editsSinceSnapshot: s.editsSinceSnapshot + 1,
        }));
        const after = get();
        const sink = _editEventSink;
        if (sink) {
          const dueForSnapshot = after.editsSinceSnapshot > 0 && after.editsSinceSnapshot % 25 === 0;
          Promise.resolve(sink({
            branchId: after.activeBranchId,
            op,
            edits_since_snapshot: after.editsSinceSnapshot,
            snapshot_payload_if_due: dueForSnapshot
              ? { vertices: after.vertices, editLog: after.editLog }
              : undefined,
          })).then((res) => {
            if (res && res.snapshot_persisted) {
              useEditorStore.setState({ editsSinceSnapshot: 0 });
            }
          }).catch(() => { /* silent — sink retries via TanStack mutation queue */ });
        }
      },"""

assert old_actions in s, 'actions block missing'
s = s.replace(old_actions, new_actions)

old_state = """  // Editable state (IN zundo history)
  vertices: Record<string, VertexCoord>;
  editLog: EditOp[];
}"""
new_state = """  // Editable state (IN zundo history)
  vertices: Record<string, VertexCoord>;
  editLog: EditOp[];
  // Counter for D-37 auto-snapshot cadence (NOT in zundo history — counts forward only)
  editsSinceSnapshot: number;
}"""
assert old_state in s
s = s.replace(old_state, new_state)

old_init = """      selectedVertexIds: [],
      vertices: {},
      editLog: [],"""
new_init = """      selectedVertexIds: [],
      vertices: {},
      editLog: [],
      editsSinceSnapshot: 0,"""
assert old_init in s
s = s.replace(old_init, new_init)

old_pre = "export const useEditorStore = create<EditorState & EditorActions>()("
new_pre = """// WARNING-6 fix: sink registered by EditorSyncBridge after useAppendEditEvent
// mutation is constructed. Single chokepoint so 08-06a/b/07/08 inherit for free.
export type EditEventSink = (payload: {
  branchId: string | null;
  op: EditOp;
  edits_since_snapshot: number;
  snapshot_payload_if_due?: { vertices: Record<string, VertexCoord>; editLog: EditOp[] };
}) => Promise<{ snapshot_persisted?: boolean } | void>;

let _editEventSink: EditEventSink | null = null;
export function registerEditEventSink(sink: EditEventSink | null) { _editEventSink = sink; }

export const useEditorStore = create<EditorState & EditorActions>()("""
assert old_pre in s
s = s.replace(old_pre, new_pre)

old_switch = """  useEditorStore.setState({
    activeBranchId: branchId,
    vertices: snapshotPayload.vertices,
    editLog: snapshotPayload.editLog,
    selectedVertexIds: [],
    activeTool: null,
    activeTerritoryId: null,
  });"""
new_switch = """  useEditorStore.setState({
    activeBranchId: branchId,
    vertices: snapshotPayload.vertices,
    editLog: snapshotPayload.editLog,
    selectedVertexIds: [],
    activeTool: null,
    activeTerritoryId: null,
    editsSinceSnapshot: 0,
  });"""
assert old_switch in s
s = s.replace(old_switch, new_switch)

old_task2 = """Create `snapshots.ts` with hooks: `useBranchSnapshots(projectId, branchId)`, `useCreateSnapshot()`, `useRestoreSnapshot()`, `useAppendEditEvent()`. The `useAppendEditEvent` mutation must accept `snapshot_payload_if_due` optionally per 08-03b D-37 contract."""
new_task2 = old_task2 + """

**WARNING-6 wiring (chokepoint registration):** Also create `frontend/src/components/editor/EditorSyncBridge.tsx`:
  1. Inside the component, call `useAppendEditEvent()` to get `mutateAsync`
  2. In a `useEffect` on mount, call `registerEditEventSink((payload) => mutateAsync(payload))`
  3. In the effect cleanup, call `registerEditEventSink(null)`
  4. Return `null` (no DOM output)
Plan 08-09 will mount `<EditorSyncBridge />` once inside `WorkspaceToolbar` (or workspace shell). Add a header comment in EditorSyncBridge stating this mount-point requirement so 08-09 cannot miss it. Backend response shape from `/branches/:id/edit-events`: `{ snapshot_persisted: boolean, snapshot_id?: string }` so the store can reset `editsSinceSnapshot` on the 25-th commit per D-37."""

assert old_task2 in s
s = s.replace(old_task2, new_task2)

old_files = """  - frontend/src/api/branches.ts
  - frontend/src/api/snapshots.ts"""
new_files = """  - frontend/src/api/branches.ts
  - frontend/src/api/snapshots.ts
  - frontend/src/components/editor/EditorSyncBridge.tsx"""
assert old_files in s
s = s.replace(old_files, new_files)

p.write_text(s, encoding='utf-8')
print('08-04 updated')


# ---------- 08-07: BLOCKER-1 — /editor/apply persists only, no geometry mutation ----------
p7 = pathlib.Path('.planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-07-PLAN.md')
s7 = p7.read_text(encoding='utf-8')

# Replace key_links truth set wording about /editor/apply executing geometry
old7_truths = """  truths:
    - "POST /editor/apply executes split/merge/translate server-side via Shapely (split uses ops.split; merge uses unary_union)"
    - "Split: parent condado inherited; name = '<orig> (2)'; original_idx = branch.original_idx_high_water + 1; branch counter incremented atomically (D-07, D-22)"
    - "Merge: adjacency check via shapely.touches; winner=first-selected keeps id/name/condado/original_idx; loser's idx freed but NEVER reused (D-08)"
    - "Cross-condado merge allowed (D-09) — hierarchy stage re-derives owner"
    - "Translate: drag polygon interior; shared vertices (D-30) follow via coupling from 08-06b"
    - "Frontend Split tool: click→click 2-point line preview; Esc cancels"
    - "Frontend Merge tool: click adjacent territory pair; non-adjacent → red Callout 'Territórios não são adjacentes'" """

new7_truths = """  truths:
    - "BLOCKER-1 fix: POST /editor/apply PERSISTS the op to snapshot blob + bumps manual_edit_log_hash AND manual_edit_log_count — it does NOT return mutated geometry. Single producer of edited rasters is compute() in 08-07c via the DAG."
    - "Replay helpers replay_split/replay_merge/replay_translate live in manual_edit.py and are invoked from compute(), NOT from the HTTP handler (D-17 — manual edits are the OUTPUT of the manual_edit stage)"
    - "Split contract (replay): parent condado inherited; name = '<orig> (2)'; original_idx = branch.original_idx_high_water + 1; branch counter incremented atomically (D-07, D-22)"
    - "Merge contract (replay): adjacency check via shapely.touches; winner=first-selected keeps id/name/condado/original_idx; loser's idx freed but NEVER reused (D-08)"
    - "Cross-condado merge allowed (D-09) — hierarchy stage re-derives owner"
    - "Translate contract (replay): polygon interior drag; shared vertices (D-30) coupled via 08-06b"
    - "Frontend Split tool: click→click 2-point line preview; Esc cancels"
    - "Frontend Merge tool: client-side adjacency check for instant feedback (red Callout 'Territórios não são adjacentes' on touches()==false); backend re-validates on /editor/apply"
    - "Frontend updates Konva preview OPTIMISTICALLY using local Shapely-equivalent JS calc (turf.js or hand-rolled for split/merge/translate); canonical raster converges only when /render is invoked (slider, Generate Map, Apply landmask)" """

assert old7_truths in s7, 'truths block in 08-07 missing'
s7 = s7.replace(old7_truths, new7_truths)

# Update artifacts.contains pattern + provides
old7_art = '''    - path: "backend/medieval_forge/api/v3/editor.py"
      provides: "POST /editor/apply with split/merge/translate handlers"
      contains: "ops.split\\|unary_union"
    - path: "backend/medieval_forge/services/pipeline/manual_edit.py"
      provides: "replay logic for split/merge/translate ops"
      contains: "_replay_split\\|_replay_merge\\|_replay_translate"'''
new7_art = '''    - path: "backend/medieval_forge/api/v3/editor.py"
      provides: "POST /editor/apply — persists op + bumps hash+count; returns {snapshot_id, edits_since_snapshot, new_hash, new_count}; NO geometry in response (BLOCKER-1 fix)"
      contains: "manual_edit_log_count"
    - path: "backend/medieval_forge/services/pipeline/manual_edit.py"
      provides: "replay helpers replay_split/replay_merge/replay_translate invoked from compute() in 08-07c (D-17)"
      contains: "replay_split\\|replay_merge\\|replay_translate"'''
assert old7_art in s7
s7 = s7.replace(old7_art, new7_art)

# Update key_links to reflect new contract
old7_kl = '''  key_links:
    - from: "VertexEditLayer (Split/Merge/Translate tools)"
      to: "POST /editor/apply"
      via: "frontend builds op payload → backend Shapely → returns updated GeoJSON + new branch.original_idx_high_water"
      pattern: "editor/apply"'''
new7_kl = '''  key_links:
    - from: "VertexEditLayer (Split/Merge/Translate tools)"
      to: "POST /editor/apply"
      via: "frontend builds op payload + optimistic Konva preview → backend persists op + bumps hash/count + (for split only) allocates next original_idx → returns {snapshot_id, new_hash, new_count, allocated_original_idx?} — NO geometry"
      pattern: "editor/apply"
    - from: "POST /editor/apply"
      to: "manual_edit.compute() in DAG (plan 08-07c)"
      via: "hash+count bump → cache miss on manual_edit stage → DAG re-runs → compute() loads snapshot blob, applies edit log, re-rasterises → lookup PNGs reflect edits"
      pattern: "manual_edit_log_count"'''
assert old7_kl in s7
s7 = s7.replace(old7_kl, new7_kl)

# Rewrite Task 1 action Step 3 (the /editor/apply endpoint) to match new contract
old7_step3 = """**Step 3 — `api/v3/editor.py`:** Add `/editor/apply` endpoint accepting `{op_type, payload, branch_id}`. Routes split/merge/translate to replay_* helpers. For split: allocates next original_idx via service. For merge: returns winner barony record + freed-id metadata. For translate: applies coord delta to all selected polygons (sharedVertex coupling already done client-side; backend re-validates topology).

Return shape: `{updated_baronies: [{id, coords, name, original_idx, condado_id}], freed_idxs: []}`."""

new7_step3 = """**Step 3 — `api/v3/editor.py` (BLOCKER-1 fix — D-17):** Add `/editor/apply` endpoint accepting `{op_type, payload, branch_id}`. The handler MUST NOT mutate geometry out-of-band. It:
  1. Loads the active branch's current snapshot blob (or seeds an empty edit log if branch has no snapshot yet)
  2. Appends the op to `edit_events` table (08-03b)
  3. For `op_type='split'` only: allocates next `original_idx` via `allocate_next_original_idx` (atomic) and embeds it inside the op payload before persisting
  4. For `op_type='merge'`: server-side re-validates `touches()` (Pitfall 2); on false → raise 400 NOT_ADJACENT BEFORE persisting
  5. Updates branch row: `manual_edit_log_count += 1` and `manual_edit_log_hash = sha256(edit_op_log_json)[:16]`
  6. Persists `branch.original_idx_high_water` if it was bumped
  7. Returns `{snapshot_id: str, edits_since_snapshot: int, new_hash: str, new_count: int, allocated_original_idx: int | None}` — NO `updated_baronies`, NO `freed_idxs`. The geometry only materialises when the DAG re-runs `manual_edit.compute()` (plan 08-07c).

The replay helpers from Step 2 (`replay_split`/`replay_merge`/`replay_translate`) are NOT called here. They are imported by `compute()` in 08-07c."""

assert old7_step3 in s7, 'step 3 block missing'
s7 = s7.replace(old7_step3, new7_step3)

# Rewrite Task 2 action to use optimistic preview (no server-returned geometry)
old7_task2_action = """**Step 1 — `useEditorStore.ts`:** Add 3 undoable actions:
- `splitPolygon(parentId, cutLineCoords) → calls API → setVerticesAndLog(next, {op:'split',...})`
- `mergePolygons(firstId, secondId) → API → setVerticesAndLog`
- `translatePolygon(polygonId, dLat, dLon) → API → setVerticesAndLog`

**Step 2 — `VertexEditLayer.tsx`:** Tool dispatch in onClick/onDrag based on `activeTool`:
- S tool: track 2 clicks → build LineString → call splitPolygon
- M tool: track first click selection; on second click → check adjacency client-side (touches via local poly check) for fast feedback; otherwise rely on backend NOT_ADJACENT error
- V tool drag on polygon interior (not handle) → translatePolygon
- Render Split preview line in tool mode
- On NOT_ADJACENT: show Radix Callout `color="red"` "Territórios não são adjacentes" auto-dismiss 2s"""

new7_task2_action = """**Step 1 — `useEditorStore.ts`:** Add 3 undoable actions that build optimistic local geometry FIRST, then POST /editor/apply for persistence (BLOCKER-1 fix — the API does not return geometry):
- `splitPolygon(parentId, cutLineCoords)`:
    1. Compute split locally with turf.js `lineSplit` (already a project dep; if missing add to package.json and note in plan task)
    2. Call `setVerticesAndLog(nextVertices, {op:'split', parentId, cutLineCoords, ts})` — the chokepoint (08-04) POSTs to /edit-events; THIS action ALSO POSTs to /editor/apply for branch-level hash bump + original_idx allocation
    3. On `/editor/apply` response with `allocated_original_idx`, patch the local child barony record with the server-allocated idx
- `mergePolygons(firstId, secondId)`:
    1. Client adjacency check (turf.js `booleanTouches`) → if false, show red Callout and abort (no API call)
    2. If true, compute union locally with turf.js `union`
    3. Call `setVerticesAndLog(nextVertices, {op:'merge', firstId, secondId, ts})` + POST /editor/apply
    4. On 400 NOT_ADJACENT (server disagrees), rollback via temporal.undo() and show red Callout
- `translatePolygon(polygonId, dLat, dLon)`:
    1. Apply delta locally
    2. Call `setVerticesAndLog(nextVertices, {op:'translate', polygonId, dLat, dLon, ts})` + POST /editor/apply

**Note (D-17 — canonical raster):** Optimistic Konva preview is for IMMEDIATE visual feedback only. The canonical `lookup_barony.png` only converges when `/render` is invoked (slider change, Generate Map button, Apply landmask). Plan 08-07c parity test asserts this convergence end-to-end.

**Step 2 — `VertexEditLayer.tsx`:** Tool dispatch in onClick/onDrag based on `activeTool`:
- S tool: track 2 clicks → build LineString → call splitPolygon
- M tool: track first click selection; on second click → client adjacency check via turf.js → if false, red Callout; if true → mergePolygons
- V tool drag on polygon interior (not handle) → translatePolygon (commit on dragend)
- Render Split preview line in tool mode
- On NOT_ADJACENT (client OR server): show Radix Callout `color="red"` "Territórios não são adjacentes" auto-dismiss 2s"""

assert old7_task2_action in s7, 'task 2 action block missing'
s7 = s7.replace(old7_task2_action, new7_task2_action)

# Add files_modified — package.json may need turf.js added
old7_files = """files_modified:
  - backend/medieval_forge/services/pipeline/manual_edit.py
  - backend/medieval_forge/api/v3/editor.py
  - backend/medieval_forge/services/branches/service.py
  - frontend/src/components/canvas/VertexEditLayer.tsx
  - frontend/src/stores/useEditorStore.ts
  - backend/tests/unit/test_manual_edit_split.py
  - backend/tests/unit/test_manual_edit_merge.py"""
new7_files = """files_modified:
  - backend/medieval_forge/services/pipeline/manual_edit.py
  - backend/medieval_forge/api/v3/editor.py
  - backend/medieval_forge/services/branches/service.py
  - backend/medieval_forge/services/branches/models.py
  - frontend/src/components/canvas/VertexEditLayer.tsx
  - frontend/src/stores/useEditorStore.ts
  - frontend/package.json
  - backend/tests/unit/test_manual_edit_split.py
  - backend/tests/unit/test_manual_edit_merge.py
  - backend/tests/integration/test_editor_apply_persists_only.py"""
assert old7_files in s7
s7 = s7.replace(old7_files, new7_files)

# Extend Task 1 behaviour with a persists-only assertion
old7_behav = """    - Test (split): square polygon + diagonal line cut → 2 triangles; child idx = high_water+1; branch.original_idx_high_water incremented
    - Test (split): line that does NOT cut polygon → 400 SPLIT_INVALID
    - Test (split): name format "<orig> (2)"
    - Test (merge): two adjacent squares → 1 rectangle; winner's id/name/condado/original_idx preserved; loser idx freed (not reused)
    - Test (merge): two non-adjacent squares → 400 NOT_ADJACENT
    - Test (merge): cross-condado adjacent → allowed (D-09)"""
new7_behav = old7_behav + """
    - Test (BLOCKER-1, replay-helper unit): replay_split(square, diagonal) returns 2 triangles whose union equals input (pure function — no DB)
    - Test (BLOCKER-1, replay-helper unit): replay_merge(adjacent squares) returns rectangle (pure function — no DB)
    - Test (BLOCKER-1, /editor/apply integration, test_editor_apply_persists_only.py): POST split op → response has {snapshot_id, new_hash, new_count, allocated_original_idx} and DOES NOT contain keys 'updated_baronies' or 'freed_idxs' (assert strict response shape)
    - Test (BLOCKER-1, persistence): after POST, branch.manual_edit_log_count == previous+1 AND branch.manual_edit_log_hash != previous
    - Test (BLOCKER-1, server validation): POST merge with non-adjacent polygons → 400 NOT_ADJACENT AND edit_events row NOT created (rollback)"""
assert old7_behav in s7
s7 = s7.replace(old7_behav, new7_behav)

# Add a Step 4 to the action covering integration test file
old7_step4 = """**Step 4 — fill both tests** with explicit numeric fixtures (e.g., `Polygon([(0,0),(1,0),(1,1),(0,1)])`)."""
new7_step4 = """**Step 4 — fill three tests** (test_manual_edit_split.py, test_manual_edit_merge.py — pure replay-helper unit tests; test_editor_apply_persists_only.py — integration test asserting the BLOCKER-1 contract). Use explicit numeric fixtures (e.g., `Polygon([(0,0),(1,0),(1,1),(0,1)])`). In test_editor_apply_persists_only.py, assert the response JSON keys are exactly `{snapshot_id, edits_since_snapshot, new_hash, new_count, allocated_original_idx}` — no geometry keys present."""
assert old7_step4 in s7
s7 = s7.replace(old7_step4, new7_step4)

# Update verify command
old7_verify = """    <automated>cd backend && python -m pytest tests/unit/test_manual_edit_split.py tests/unit/test_manual_edit_merge.py -v -x</automated>"""
new7_verify = """    <automated>cd backend && python -m pytest tests/unit/test_manual_edit_split.py tests/unit/test_manual_edit_merge.py tests/integration/test_editor_apply_persists_only.py -v -x</automated>"""
assert old7_verify in s7
s7 = s7.replace(old7_verify, new7_verify)

p7.write_text(s7, encoding='utf-8')
print('08-07 updated')


# ---------- 08-08: WARNING-4 + WARNING-5 ----------
p8 = pathlib.Path('.planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-08-PLAN.md')
s8 = p8.read_text(encoding='utf-8')

# WARNING-4: add contracts.py + dag.py to files_modified
old8_files = """files_modified:
  - frontend/src/components/editor/LandmaskEditorHeader.tsx
  - frontend/src/components/editor/__tests__/LandmaskEditorHeader.test.tsx
  - frontend/src/components/canvas/VertexEditLayer.tsx
  - frontend/src/components/canvas/LayerTogglePanel.tsx
  - backend/medieval_forge/services/pipeline/landmask.py
  - backend/medieval_forge/api/v3/editor.py
  - backend/tests/integration/test_landmask_edit.py
  - backend/tests/integration/test_landmask_cascade.py"""
new8_files = """files_modified:
  - frontend/src/components/editor/LandmaskEditorHeader.tsx
  - frontend/src/components/editor/__tests__/LandmaskEditorHeader.test.tsx
  - frontend/src/components/canvas/VertexEditLayer.tsx
  - frontend/src/components/canvas/LayerTogglePanel.tsx
  - backend/medieval_forge/services/pipeline/landmask.py
  - backend/medieval_forge/services/pipeline/contracts.py
  - backend/medieval_forge/services/pipeline/dag.py
  - backend/medieval_forge/api/v3/editor.py
  - backend/tests/integration/test_landmask_edit.py
  - backend/tests/integration/test_landmask_cascade.py"""
assert old8_files in s8
s8 = s8.replace(old8_files, new8_files)

# WARNING-5: extend VertexEditLayer action to cover landmask-handle rendering + PT/ES read-only routing.
# Add a new step inside Task 1 action covering VertexEditLayer extension explicitly.
old8_task1_action_close = "**Step 3 — fill test file.**"
new8_task1_action_close = """**Step 3 — `VertexEditLayer.tsx` (WARNING-5 fix — Pitfall 3 landmask handle rendering):** Extend the existing VertexEditLayer with a `landmask_layer` mode branch:
  - When the active editable layer is the landmask (driven by a new `editableLayer: 'baronies' | 'landmask'` prop sourced from useEditorStore), render landmask polygon handles using the same handle component as baronies (Konva Circle, radius 5, fill cyan #06b6d4 for landmask vs blue for baronies to differentiate visually).
  - Pitfall 3 enforcement (CRITICAL): the PT/ES border polygon (40 pts, separate dataset) is rendered as a SEPARATE Konva Line node with `listening={false}` so pointer events never hit it. The component receives both `landmaskCoords` and `borderCoords` props; only `landmaskCoords` produces interactive handles. Add a runtime assertion `if (process.env.NODE_ENV !== 'production') console.assert(borderCoords.length === 40, 'PT/ES border expected 40 pts per CLAUDE.md/STATE.md')`.
  - In auto-immediate mode (D-05 — Header toggle), each handle dragend triggers POST /editor/apply op_type='landmask_replace' with the full new landmask coords. In manual mode, drags are buffered locally and only the Apply button (Task 1 Step 1) flushes.
  - All landmask handle ops MUST funnel through `setVerticesAndLog` so the WARNING-6 chokepoint (08-04) records them into edit_events with op.type='landmask_vertex_move'/'landmask_vertex_add'/'landmask_vertex_delete'.

**Step 4 — fill test file.**

**Step 5 — extend VertexEditLayer.test.tsx with 3 landmask-specific tests:**
  - Test: when editableLayer='landmask', cyan #06b6d4 handles render on landmask vertices
  - Test: borderCoords props produces a Konva.Line with listening=false (no handle rendering)
  - Test: in auto-immediate mode, landmask handle dragend POSTs op_type='landmask_replace' AND fires the edit-event sink (chokepoint integration)"""

assert old8_task1_action_close in s8, 'Task 1 step 3 closer missing in 08-08'
s8 = s8.replace(old8_task1_action_close, new8_task1_action_close)

# Add a truth about VertexEditLayer landmask handling
old8_truths_end = '    - "Apply button uses variant=\"outline\" (secondary; UI-SPEC Discretion #5)"'
new8_truths_end = '''    - "Apply button uses variant=\"outline\" (secondary; UI-SPEC Discretion #5)"
    - "WARNING-5 fix: VertexEditLayer renders landmask handles (cyan #06b6d4) ONLY when editableLayer=\'landmask\'; PT/ES border (40 pts) routed as a separate Konva.Line with listening=false (Pitfall 3)"
    - "WARNING-4 fix: contracts.py gains landmask_override field; dag.py STAGE_READS[\'landmask\'] includes \'landmask_override\' so version_token invalidates on edit"'''
assert old8_truths_end in s8
s8 = s8.replace(old8_truths_end, new8_truths_end)

p8.write_text(s8, encoding='utf-8')
print('08-08 updated')


# ---------- 08-09: WARNING-3 add ParameterSidebar.tsx ----------
p9 = pathlib.Path('.planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-09-PLAN.md')
s9 = p9.read_text(encoding='utf-8')

old9_files = """  - frontend/src/components/editor/SnapshotTimeline.tsx
  - frontend/src/components/workspace/WorkspaceToolbar.tsx
  - frontend/src/components/editor/__tests__/BranchPicker.test.tsx
  - frontend/src/components/editor/__tests__/SliderConflictDialog.test.tsx"""
new9_files = """  - frontend/src/components/editor/SnapshotTimeline.tsx
  - frontend/src/components/workspace/WorkspaceToolbar.tsx
  - frontend/src/components/canvas/ParameterSidebar.tsx
  - frontend/src/components/editor/__tests__/BranchPicker.test.tsx
  - frontend/src/components/editor/__tests__/SliderConflictDialog.test.tsx"""
assert old9_files in s9, 'files_modified block in 08-09 missing'
s9 = s9.replace(old9_files, new9_files)

# Also mount EditorSyncBridge here per WARNING-6 wiring contract from 08-04
old9_truths_end = '    - "SnapshotTimeline = floating Card listing snapshots reverse-chronological with Restore button each (RESEARCH Open Q3)"'
new9_truths_end = '''    - "SnapshotTimeline = floating Card listing snapshots reverse-chronological with Restore button each (RESEARCH Open Q3)"
    - "WARNING-3 fix: ParameterSidebar.tsx is explicitly listed in files_modified — Task 2 extends it with snapshot-before-modal sequencing (Pitfall 9)"
    - "WARNING-6 wiring: WorkspaceToolbar mounts <EditorSyncBridge /> once (created in 08-04) so the edit-event sink is registered for the whole workspace lifetime"'''
assert old9_truths_end in s9
s9 = s9.replace(old9_truths_end, new9_truths_end)

# Add WorkspaceToolbar EditorSyncBridge mount note to Task 1 Step 6
old9_step6 = """**Step 6 — `WorkspaceToolbar.tsx`:** Add Branch Picker zone left of "Gerar Mapa" button per UI-SPEC §Toolbar Layout."""
new9_step6 = """**Step 6 — `WorkspaceToolbar.tsx`:** Add Branch Picker zone left of "Gerar Mapa" button per UI-SPEC §Toolbar Layout. **WARNING-6 mount (chokepoint registration):** also render `<EditorSyncBridge />` once inside the toolbar (zero-DOM component created in 08-04) so the edit-event sink registers for the whole workspace session."""
assert old9_step6 in s9
s9 = s9.replace(old9_step6, new9_step6)

p9.write_text(s9, encoding='utf-8')
print('08-09 updated')

print('All targeted edits complete.')
