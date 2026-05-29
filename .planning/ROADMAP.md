### Phase 08.1: Bezier-assisted barony contour editing — UI-layer Bezier control points over the existing polygon model (parity-safe: store stays polygon, curve-fit derived for display, only edited segments flatten back) (INSERTED)

**Goal:** Replace the unusable raw per-vertex handle model (hundreds of dots per smoothed Voronoi barony) with a Bézier-assisted control-point editor that shows ~10-20 anchors + active-anchor handles. Bézier lives ONLY in the editor UI layer (component-local state, never in useEditorStore, never in zundo); anchors/handles are curve-fit derived from the polygon for display; only DIRTY (dragged) segments flatten back to polygon vertices; non-dirty ranges copy verbatim. The single non-negotiable invariant is the empty-log identity contract: enter+exit edit mode with zero drags leaves useEditorStore.vertices byte-identical and editLog unchanged (frontend port of the Phase 08 08-07c parity test). Backend, DAG, /editor/apply, export schema, and the 12-file raster parity contract are unchanged.
**Requirements**: BEZ-IDENTITY-01, BEZ-FIT-01, BEZ-INDEX-01, BEZ-FLATTEN-01, BEZ-FLATTEN-02, BEZ-RENDER-01, BEZ-RENDER-02, BEZ-DRAG-01, BEZ-UAT-01, BEZ-UAT-02 (validation-ID spine from RESEARCH §Validation Architecture; no formal REQ-IDs for this UI-only phase)
**Depends on:** Phase 8
**Plans:** 8/8 plans complete

Plans:
- [x] 08.1-01-PLAN.md — Wave 1: pure geometry libs — bezierFit.ts (fitPolygonToBezier + buildPolyIndexMap split-index recovery) + bezierFlatten.ts (de Casteljau density-match) + iberiaBaronyRing fixture + fit-curve@0.2.0 dep [BEZ-FIT-01, BEZ-INDEX-01, BEZ-FLATTEN-01, BEZ-FLATTEN-02]
- [x] 08.1-02-PLAN.md — Wave 2: BezierEditLayer render + click-to-activate (NO drag) + BEZ-IDENTITY-01 empty-log byte-identity guard (authored before any drag code) + __forgeBezierState DEV hatch [BEZ-RENDER-01, BEZ-RENDER-02, BEZ-IDENTITY-01]
- [x] 08.1-03-PLAN.md — Wave 3: anchor + control-handle drag → dirty-segment flatten → setVerticesAndLog(op:'move') with snap (anchors only) + shared-vertex coupling reused from Phase 08 [BEZ-DRAG-01]
- [x] 08.1-04-PLAN.md — Wave 4: integration — CanvasViewer z=5 mutual-exclusion mount + EditToolPalette disabledTools (A/D disabled in Bézier mode) threaded from WorkspaceToolbar + Playwright BEZ-UAT-01 reachability/drag + BEZ-UAT-02 identity-through-export [BEZ-UAT-01, BEZ-UAT-02]
- [x] 08.1-05-PLAN.md — Wave 1 (gap-closure): G1 close Bezier ring + G2 commit closing-segment drags (WR-02 clamp, WR-03 flatten endpoints, WR-01 superseded) + G4 distinct color palette [BEZ-IDENTITY-01, BEZ-DRAG-01]
- [x] 08.1-06-PLAN.md — Wave 2 (gap-closure): G3 add control points — double-click insert anchor at nearest curve param, identity-safe NO-OP split of poly range [BEZ-IDENTITY-01, BEZ-INDEX-01]
- [x] 08.1-07-PLAN.md — Wave 1 (gap-closure G5+G7): screen-space sizing for anchors/handles/hit-path (size = BASE / currentScale, mirror DecorationsLayer) + MAX_SCALE_MULTIPLIER 4→16 + the three "5" half-size sites synced + Playwright REAL page.mouse drag & dblclick at usable zoom (bans __forgeBezierTrigger*) [BEZ-RENDER-01, BEZ-RENDER-02, BEZ-DRAG-01, BEZ-UAT-01]
- [x] 08.1-08-PLAN.md — Wave 2 (gap-closure G6): real-mouse reproduction (drag commits + colored map stale, G6 independent of G5) + live edited-contour overlay rendered read-only from store.vertices (option a — no /editor/apply, no /render; phase boundary preserved) + Playwright real-drag overlay-reflects-edit [BEZ-DRAG-01, BEZ-RENDER-01, BEZ-UAT-01]

### Phase 08.2: Bézier edit-to-map convergence — backend vertex move/add/delete replay + render cascade so barony contour edits reach the colored map and 12-file export (INSERTED)

**Goal:** Close G8 (08.1-HUMAN-UAT). Today a Bézier contour edit commits `op:'move'` and IS persisted to the branch edit-log (POST `/edit-events`), but the render pipeline silently drops it: `backend/medieval_forge/services/pipeline/manual_edit.py:128` only replays `split`/`merge`/`translate` — `move`/`add`/`delete` were deferred in Phase 08 and never implemented, and `render.py:148-167` only feeds `landmask_replace` into render. Net: the colored barony boundary + the 12-file Unity export NEVER reflect a Bézier edit, even after a re-render (the 08.1 overlay is a live preview only). This phase implements barony vertex-op replay in `manual_edit.compute()` and wires a render cascade (or explicit Apply) after Bézier commit so the edited contour converges to the colored `BaronyLayer` and the export — mirroring the existing `landmask_replace → cfg.landmask_override → /render` cascade. Iberia 10/10 byte/SSIM parity MUST stay green (sentinel ops only fire when a branch has barony edit-events; the zero-edit path is unchanged).

**Requirements**: BEZ-CONV-01 (move replay in manual_edit), BEZ-CONV-02 (add/delete replay), BEZ-CONV-03 (render cascade trigger + baroniesQ refetch post-edit), BEZ-CONV-04 (Iberia parity 10/10 unchanged on zero-edit path), BEZ-CONV-05 (UAT: real-mouse Bézier edit → colored barony boundary changes + survives reload + appears in export) — proposed spine, to be formalized in /gsd-plan-phase.
**Depends on:** Phase 08.1
**Plans:** Not planned yet

Plans:
- (none yet — run /gsd-plan-phase 08.2)
