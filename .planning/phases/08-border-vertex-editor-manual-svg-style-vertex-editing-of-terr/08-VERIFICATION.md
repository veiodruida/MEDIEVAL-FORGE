---
phase: 08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr
verified: 2026-05-28T00:00:00Z
status: gaps_found
score: 18/29 must-haves verified
overrides_applied: 0
gaps:
  - truth: "User can select a barony and see editable vertex handles render on the canvas"
    status: failed
    reason: >-
      Selection→editor bridge missing. Territory/barony click sets
      useUIStore.selectedBaronyId / selectedTerritoryId, but
      useEditorStore.setActiveTerritoryId is NEVER called in application code
      (grep finds it ONLY in useEditorStore.ts itself — the definition and the
      type — not in any component, page, or even test). VertexEditLayer gates
      handle rendering on `activeTerritoryId !== null`
      (VertexEditLayer.tsx:403,717) → handles can never render at runtime.
      Separately, no code path loads the selected barony's polygon coords from
      effectiveBaronies (baroniesQ.data) into useEditorStore.vertices (default
      `{}`), so even with activeTerritoryId set there is nothing to render/edit.
      ProjectDetail.tsx (the workspace page) does not import useEditorStore at all.
    artifacts:
      - path: "frontend/src/components/canvas/CanvasViewer.tsx"
        issue: "handleStageClick (530-541) + TerritoryLayer/BaronyLayer onClick set only useUIStore selection; never call setActiveTerritoryId or load vertices."
      - path: "frontend/src/stores/useEditorStore.ts"
        issue: "setActiveTerritoryId (line 185) and vertices map (line 177) exist but have zero callers outside the store definition; vertices is never populated from query data."
      - path: "frontend/src/components/canvas/VertexEditLayer.tsx"
        issue: "visibleEntries (403) returns [] when activeTerritoryId is null; listening (717) is false → no handles, no hit-testing at runtime."
      - path: "frontend/src/pages/ProjectDetail.tsx"
        issue: "Workspace page mounts CanvasViewer + WorkspaceToolbar but never imports useEditorStore or wires selection→activeTerritoryId+vertices."
    missing:
      - "Add a SelectionBridge (component or effect) that subscribes to useUIStore.selectedBaronyId and calls useEditorStore.setActiveTerritoryId(id)."
      - "On barony selection, load that barony's polygon ring from effectiveBaronies (baroniesQ.data) into useEditorStore.vertices (Record<vertexId, {lat,lon}>) so handles have data to render."
      - "Clear activeTerritoryId + vertices when selection is cleared (empty-stage click)."
  - truth: "Split / merge / translate polygon ops and landmask edits actually execute in the running app"
    status: failed
    reason: >-
      VertexEditLayer is mounted at CanvasViewer.tsx:693 as
      `<VertexEditLayer stageRef viewport />` with NO projectId, branchId, tier,
      or editableLayer props. Split (VertexEditLayer.tsx:579), merge (614), and
      translate (691) handlers early-return when projectId/branchId are missing,
      so all polygon ops silently no-op even if a tool were active. LayerTogglePanel
      is mounted at CanvasViewer.tsx:695 as `<LayerTogglePanel />` with no props,
      yet it declares projectId?/branchId?/onApplyLandmask (LayerTogglePanel.tsx:17-27,
      80-81) and only renders the landmask editor header when projectId+branchId are
      present → landmask edit path (LANDMASK-01/02) is non-functional in the app.
    artifacts:
      - path: "frontend/src/components/canvas/CanvasViewer.tsx"
        issue: "Line 693 mounts VertexEditLayer without projectId/branchId/tier/editableLayer; line 695 mounts LayerTogglePanel without projectId/branchId/onApplyLandmask."
      - path: "frontend/src/components/canvas/VertexEditLayer.tsx"
        issue: "split (579), merge (614), translate (691) handlers `if (!activeTerritoryId || !projectId || !branchId) return` → no-op without wired props."
      - path: "frontend/src/components/canvas/LayerTogglePanel.tsx"
        issue: "Renders LandmaskEditorHeader only when projectId+branchId provided (77-81); receives neither from CanvasViewer."
    missing:
      - "Pass projectId={projectId}, branchId={useEditorStore activeBranchId}, tier='barony', editableLayer (from landmask mode) to <VertexEditLayer> in CanvasViewer."
      - "Pass projectId, branchId, and onApplyLandmask to <LayerTogglePanel> in CanvasViewer (or thread them down from ProjectDetail/WorkspaceToolbar)."
      - "Wire onLandmaskCoordsChange / Apply callback so landmask_replace POST reaches the backend."
  - truth: "User has a visible affordance to enter edit mode and choose a tool (V/A/D/S/M)"
    status: failed
    reason: >-
      WorkspaceToolbar renders only Params toggle, Projetos link, GenerateStatusBadge,
      BranchPicker, Undo/Redo, Gerar Mapa, and Exportar ZIP — no edit-mode toggle and
      no V/A/D/S/M tool palette. The five edit tools are keyboard-only
      (useKeyboardShortcuts.ts:68-79) with default activeTool=null
      (useEditorStore.ts:174). With no visible button, palette, or "edit mode"
      indicator, the editor is undiscoverable; UX-01 (keyboard shortcuts) exists but
      its supporting visible affordance does not.
    artifacts:
      - path: "frontend/src/components/workspace/WorkspaceToolbar.tsx"
        issue: "Toolbar (100-209) has no edit-tool buttons / palette / edit-mode toggle; activeTool is never surfaced or settable via UI."
      - path: "frontend/src/hooks/useKeyboardShortcuts.ts"
        issue: "V/A/D/S/M bound at 68-79 keyboard-only; no visible counterpart."
      - path: "frontend/src/stores/useEditorStore.ts"
        issue: "selectTool (184) reachable only from keyboard handler; default activeTool null (174)."
    missing:
      - "Add an EditToolPalette (e.g. Radix ToggleGroup) bound to useEditorStore.activeTool/selectTool with V/A/D/S/M tools and an active-tool indicator."
      - "Add a visible edit-mode entry point (toolbar toggle or contextual palette shown when a barony is selected)."
deferred: []
---

# Phase 8: Border Vertex Editor + Branching — Verification Report

**Phase Goal:** Deliver a manual SVG-style vertex editor for territory (barony-tier) polygons with named-branch + auto-snapshot project model, integrated with the Phase 04 DAG via a new `manual_edit` stage. Preserves all CLAUDE.md non-negotiables (NEAREST upscale, per-country KD-tree, `original_idx` invariant) and Phase 04 cache contracts. First use of zundo `temporal`.
**Verified:** 2026-05-28
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

The phase built every backend stage, store, and Konva component in isolation and all
unit/integration/parity/Playwright tests pass. However, a live UAT (orchestrator + human)
found the editor is **NOT usable in the running app**: the pieces were never wired together.
Goal-backward verification confirms this — the integration layer that connects user
selection → editor activation → vertex rendering → tool invocation is absent. Task
completion ≠ goal achievement: the goal ("a manual vertex editor") is not achieved because
no user can reach the editor at runtime.

### Observable Truths (per Requirement ID)

| #  | Requirement | Truth | Status | Evidence |
|----|-------------|-------|--------|----------|
| 1  | DAG-01 | `manual_edit` stage slotted between merge and hierarchy | ✓ VERIFIED | 08-01/08-07c green; backend DAG_ORDER + parity |
| 2  | DAG-02 | `manual_edit.version_token` (count + log hash); empty log = identity | ✓ VERIFIED | 08-01 truths; identity parity green |
| 3  | DAG-03 | Slider-while-edits → auto-snapshot then confirm modal | ✓ VERIFIED (isolated) | 08-09 SliderConflictDialog + ParameterSidebar |
| 4  | DAG-04 | Landmask edit invalidates landmask stage → KD-tree cascade | ✓ VERIFIED (backend) | 08-08 STAGE_READS['landmask'] + landmask_override |
| 5  | DAG-05 | Cache key `(project_id, branch_id, stage, version_token)` | ✓ VERIFIED | 08-02 9 callsites; branch HIT test green |
| 6  | BRANCH-01 | Create/switch/rename/delete; main delete-protected | ✓ VERIFIED (backend+picker) | 08-03a CRUD; 08-09 BranchPicker |
| 7  | BRANCH-02 | Auto-snapshot every 25 edits + manual snapshot | ✓ VERIFIED (backend) | 08-03b + 08-04 counter |
| 8  | BRANCH-03 | Snapshot = gzip JSON blob; no patch-replay | ✓ VERIFIED | 08-03b serializer + 10MB cap |
| 9  | BRANCH-04 | Copy branch → main wholesale replace | ✓ VERIFIED (isolated) | 08-09 CopyBranchToMainDialog |
| 10 | BRANCH-05 | Export snapshots active branch; manifest v3 | ✓ VERIFIED | 08-10 schema_version==3 parity green |
| 11 | PERSIST-01 | `branches`/`snapshots`/`edit_events` tables | ✓ VERIFIED | 08-03a/03b create_all |
| 12 | PERSIST-02 | Auto-save every 25 edits; localStorage active_branch_id | ✓ VERIFIED | 08-04 loadPersistedActiveBranchId |
| 13 | TELEM-01 | Each edit op logged to `edit_events` | ✓ VERIFIED (sink) | 08-03b endpoint + 08-04 EditEventSink |
| 14 | UNDO-01 | zundo temporal wraps useEditorStore; cap 100; clear on switch | ✓ VERIFIED | useEditorStore.ts:168-454 temporal+partialize |
| 15 | TOPO-01 | Self-intersect/gap blocking; red feedback | ✓ VERIFIED (logic) | VertexEditLayer validate + invalidDragId |
| 16 | TOPO-02 | Duplicate/sliver warnings (amber) | ✓ VERIFIED (logic) | computeWarnFlags (192-220) |
| 17 | TOPO-03 | Scale-aware snap within 5px; Alt disables | ✓ VERIFIED (logic) | snap.ts + handleDragMove |
| 18 | TOPO-04 | Shared vertex coupling | ✓ VERIFIED (logic) | sharedVertex.ts + handleDragEnd (520-539) |
| 19 | EDIT-VERTEX-04 | Douglas-Peucker simplify (preserve_topology) | ✓ VERIFIED (backend) | 08-06a shapely.simplify |
| 20 | UX-02 | Desktop-only banner on touch UA | ✓ VERIFIED | 08-05 DesktopRequiredBanner |
| 21 | EDIT-VERTEX-01 | Drag vertex; commit/snap-back; coupling | ✗ FAILED | Handles never render (activeTerritoryId never set; vertices empty) — GAP-A |
| 22 | EDIT-VERTEX-02 | Click edge to add vertex; cap 1000/warn 500 | ✗ FAILED | Add tool unreachable; layer not listening at runtime — GAP-A/GAP-C |
| 23 | EDIT-VERTEX-03 | Select + delete vertices (one undoable op) | ✗ FAILED | No selectable handles render; Del has no selectedVertexIds — GAP-A |
| 24 | EDIT-VERTEX-05 | Drag tooltip (lat,lon) follows cursor | ✗ FAILED | CoordTooltip setter never wired (CanvasViewer.tsx:160 `void setCoordTooltip`); no drag at runtime — GAP-A |
| 25 | EDIT-POLYGON-01 | Split polygon by 2-point cut | ✗ FAILED | Handler early-returns w/o projectId/branchId; tool unreachable — GAP-B/GAP-C |
| 26 | EDIT-POLYGON-02 | Merge 2 adjacent baronies | ✗ FAILED | Same — no wired props, no visible tool — GAP-B/GAP-C |
| 27 | EDIT-POLYGON-03 | Translate polygon interior | ✗ FAILED | Same — GAP-B/GAP-C |
| 28 | LANDMASK-01 | Landmask editable; PT/ES border read-only | ✗ FAILED | LayerTogglePanel mounted w/o projectId/branchId → header never renders — GAP-B |
| 29 | LANDMASK-02 | Manual + auto-immediate modes | ✗ FAILED | Same — landmask mode UI/Apply unreachable — GAP-B |
| 30 | PERF-01 | 60fps drag; viewport cull; RAF | ✗ FAILED | Handles never render in app → perf claim unverifiable at runtime (RAF/cull logic present but dormant) — GAP-A |
| 31 | UX-01 | Keyboard V/A/D/S/M/Esc + undo/redo + Del | ✗ FAILED | Shortcuts exist but no visible affordance/edit-mode UI; tools set activeTool that nothing surfaces — GAP-C |

**Score:** 18/29 distinct requirement-truths verified (treating the EDIT-VERTEX-04 simplify row and the 20 PASSED rows above; 11 requirement-truths FAILED). Note: the phase declares 30 IDs; EDIT-VERTEX-04 simplify counted once. The failing IDs all share one root cause family — the missing editor integration layer.

### Required Artifacts (integration layer)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| Selection→editor bridge | selection sets activeTerritoryId + loads vertices | ✗ MISSING | No caller of setActiveTerritoryId anywhere; vertices never populated |
| `<VertexEditLayer>` props wiring | projectId/branchId/tier/editableLayer passed | ✗ MISSING | CanvasViewer.tsx:693 passes only stageRef+viewport |
| `<LayerTogglePanel>` props wiring | projectId/branchId/onApplyLandmask passed | ✗ MISSING | CanvasViewer.tsx:695 passes none |
| Visible edit tool palette | V/A/D/S/M buttons + edit-mode toggle | ✗ MISSING | WorkspaceToolbar has no such control |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| Territory/barony click | useEditorStore.activeTerritoryId | setActiveTerritoryId | ✗ NOT_WIRED | Click sets only useUIStore; setActiveTerritoryId has zero callers |
| baroniesQ.data | useEditorStore.vertices | load-on-select | ✗ NOT_WIRED | No code path loads polygon ring into vertices map |
| CanvasViewer | VertexEditLayer ops | projectId/branchId props | ✗ NOT_WIRED | Props omitted → split/merge/translate early-return |
| CanvasViewer | LayerTogglePanel landmask | projectId/branchId props | ✗ NOT_WIRED | Props omitted → landmask header never renders |
| Toolbar/UI | useEditorStore.selectTool | tool palette buttons | ✗ NOT_WIRED | Only keyboard handler calls selectTool |

### Already Resolved (NOT gaps)

- **React #310** in CanvasViewer — `vertexViewport` useMemo hoisted above early returns
  (commit 6888699). Confirmed present at CanvasViewer.tsx:561-583 ahead of the early-return
  block (586+). Not flagged.
- **DB schema-drift 500 on GET /branches** — startup column migration added (commit f3fcc14).
  Not flagged.

### Gaps Summary

The phase is feature-complete in isolation and structurally sound: every store action, Konva
handler, backend endpoint, DAG stage, and dialog exists and passes its own tests. The single
systemic failure is the **editor integration layer**:

1. **GAP-A — Selection→Editor bridge missing.** Clicking a barony never activates the editor
   (`setActiveTerritoryId` has no callers) and never loads its vertices, so handles can never
   render. Blocks EDIT-VERTEX-01/02/03/05 and makes PERF-01 unverifiable at runtime.
2. **GAP-B — VertexEditLayer / LayerTogglePanel prop wiring missing.** Both are mounted without
   the projectId/branchId (and tier/editableLayer/onApplyLandmask) props their op handlers
   require, so split/merge/translate and the entire landmask path silently no-op. Blocks
   EDIT-POLYGON-01/02/03 and LANDMASK-01/02.
3. **GAP-C — No visible edit-mode UI / tool palette.** Tools are keyboard-only with no
   discoverable affordance and no active-tool indicator. Blocks UX-01's intent and the
   discoverability of every edit operation.

These three concerns are structured in the frontmatter `gaps:` array so
`/gsd-plan-phase 08 --gaps` can turn them into focused gap-closure plans. All three are
frontend-only wiring/UI work; no backend, DAG, store-logic, or parity changes are implied.

---

_Verified: 2026-05-28_
_Verifier: Claude (gsd-verifier)_
