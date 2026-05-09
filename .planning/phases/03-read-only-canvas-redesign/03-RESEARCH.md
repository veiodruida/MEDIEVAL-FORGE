# Phase 03: Read-only canvas redesign - Research

**Researched:** 2026-05-09
**Domain:** FastAPI artifact serving + SSE pipeline triggers + read-only Konva workspace + v1 deletion graph
**Confidence:** HIGH (most claims verified against codebase grep + Phase 02 SSE template; one external reference verified via WebSearch)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

Copied verbatim from `.planning/phases/03-read-only-canvas-redesign/03-CONTEXT.md` (`<decisions>` block) — D-01 through D-23 are the planning contract. The planner MUST honor every locked decision.

**Workspace shell**
- **D-01:** Mapbox-like full-bleed canvas. Top toolbar (thin) carries project name + status badge + "Generate Map" + "Export ZIP" + breadcrumb-back. Inspector right ~320 px, collapsible. `LayerTogglePanel` + `LegendCard` stack upper-left as floating overlays. `FitToView` + zoom controls float in another corner.
- **D-02:** Single "Generate Map" CTA dispatches ingest+generate sequentially. Frontend run state machine: `idle → ingesting → generating → generated | error`. Button label flips to "Re-generate" after first success.
- **D-03:** Toolbar status badge streams SSE event text inline. Click expands an inline log panel listing the 11 DAG stages (`landmask → border → voronoi → cleanup → smooth → merge → hierarchy → render → lookup → metadata → export`) with a checkmark per SSE event. No modal.
- **D-04:** No cancel in Phase 03. Per-stage `stop_event` slot reserved for Phase 04.

**Empty / loading / error**
- **D-05:** Empty state — placeholder + icon + "Gerar mapa medieval para [país] [período]" + centered CTA.
- **D-06:** Ingesting — grey country silhouette + status badge streams `/api/v3/.../ingest` SSE.
- **D-07:** Generating — placeholder + inline expanded log; no partial render.
- **D-08:** Error — top-of-canvas red callout (failed stage + last log line + copyable error + Retry); status badge red; back/Export remain functional.

**Canvas core reuse**
- **D-09:** Reuse 5-layer Konva stack (`CanvasViewer`, `BackgroundLayer`, `TerritoryLayer`, `BaronyLayer`, `DecorationsLayer`, `InteractionLayer`, `ProjectionContext`, `lib/projection.ts`, `useZoomPan`, `useKeyboardShortcuts`, `useCanvasArtifacts`, `FitToViewButton`, `LayerTogglePanel`, `LegendCard`, `InspectorSidebar`) — only data hydration changes (URL prefix swap). Existing `__tests__/` carry over for read-only behavior.
- **D-10:** Delete edit-only — `EditToolbar`, `SplitTool`, `VertexHandlesLayer`, `SelectionFloatingToolbar`, `ValidationBadgesLayer`, `useRubberBandSelection`, `useEditKeyboardMap`, `useUndoShortcut`, `useBeforeUnloadGuard`, `services/validation.ts`, `services/persistence.ts`, `useValidationStore`, `useEditorStore`, `pages/TerritoryEditor.tsx` (+ route), `components/research/AssignmentEditor.tsx`. ~1500 LOC + tests deleted.

**V1 deletion**
- **D-11:** Frontend purge — `components/pipeline/`, `components/ingest/BaronyGranularitySlider.tsx`, `usePipelineStore`, `api/useTerrainStepStream.ts`, `api/edit.ts`. `App.tsx` route to new ProjectDetail.
- **D-12:** Backend purge — `api/ingest.py`, `services/ingest_runner.py`, `services/ingest_wikidata.py`. Remove v1 router from `main.py`. **If Phase 02 v3 SSE adapter still imports `_write_geojson_atomic`, lift it to `services/paths.py` first** (planning task).
- **D-13:** LLM purge — `components/research/`, `components/codex/`, `useResearchStore`, `useResearchStream`, `useCodexStream`, `api/research.ts`, `api/codex.ts`. Backend: `services/research_runner.py`, `services/research_cache.py`, `services/llm/`, `api/research.py`, `api/codex.py`, `api/llm.py`. **Audit `api/auth.py` + `services/credential_store.py`** — delete if no surviving consumer.

**Inspector + interaction**
- **D-14:** Inspector renders full condado metadata (id, name, kingdom name, duchy name, capital_name with sentinel "No capital assigned", pixel_count, lon/lat, baronies list, neighbors list).
- **D-15:** Hover paints 1 px light-grey outline + tooltip with condado name. Click promotes to gold `InteractionLayer` outline.
- **D-16:** Click on water clears selection; inspector returns to placeholder "Clique num território para ver detalhes".
- **D-17:** `Shift+click` adds/removes from selection set. Inspector aggregate view: count, listed names, summed `pixel_count`, union of duchies + kingdoms. Click without shift = single (replaces). Gold outline applies to all selected.

**Artifact serving**
- **D-18:** FastAPI serves `/api/v3/projects/{id}/artifacts/*` from `projects/<uuid>/output/`. Native HTTP cache; no schema validation at serve boundary.
- **D-19:** Frontend appends `?v={project.updated_at}`. `run_pipeline` updates `project.updated_at`.
- **D-20:** No auth. Local-only.
- **D-21:** New `GET /api/v3/projects/{id}/status` returns `{ status, has_artifacts: { ... }, last_generated_at }`.

**Backend pipeline endpoint**
- **D-22:** `POST /api/v3/projects/{id}/generate` (returns 202 + run_id) + `GET /api/v3/projects/{id}/generate/stream` (SSE). Mirrors Phase 02 D-14 pattern (`asyncio.Queue` + `StreamingResponse` + terminal `None` + per-(project, step) `stop_event`). Wraps `run_pipeline(cfg)`. Status: `generated` on success, `error_generating` on failure.

**Routing**
- **D-23:** Keep `/projects` + `/projects/:id`. ProjectList + ProjectNew unchanged. Toolbar back uses `<Link to="/projects">`.

### Claude's Discretion

(Verbatim from CONTEXT.md.)

- Tailwind v4 vs Radix Themes split for the workspace shell.
- Tooltip implementation for D-15: Radix `Tooltip` vs custom Konva `Text` overlay. Probably a `<div>` overlay positioned via `Stage.getPointerPosition`.
- Status badge animation/format (pulse, percent bar, text-only).
- SSE event envelope shape — mirror Phase 02 verbatim or define stricter `{stage, event_type, message, progress?}`.
- Where the run state lives — new `useRunStore` Zustand vs derived from TanStack Query `/status` polling + SSE.
- Empty-state visual icon (Lucide vs Radix vs custom SVG).
- How much of `useCanvasArtifacts` changes beyond URL prefix swap.
- Whether `api/auth.py` + `services/credential_store.py` survive D-13.
- Run-id generation strategy (uuid4 vs project_id+timestamp).

### Deferred Ideas (OUT OF SCOPE)

- Cancel of in-flight runs (Phase 04).
- Partial render of intermediate stages (Phase 04).
- Param studio sliders + live re-render (Phase 04).
- Compound undo for slider changes (Phase 04).
- DEM/HydroSHEDS terrain wire-up (Phase 06 / v3.1).
- Region YAML loader (Phase 05).
- Schema validation on artifact serve (Phase 06).
- LLM research dialog rewrite (Phase 07).
- Edit territory geometry / paint-brush mountains (out of v3).
- Auth + remote hosting (backlog v3.1).
- Multi-language UI (out of v3).
- Manifest dedicated endpoint (Phase 06).
- Map switcher / multi-project sidebar (v3.1).
- Visual refresh of ProjectList / ProjectNew (v3.1).

</user_constraints>

---

<phase_requirements>
## Phase Requirements

INIT reported `phase_req_ids = null`. Requirements are derived from `ROADMAP.md` Phase 03 success criteria + CONTEXT decisions:

| ID | Description | Research Support |
|----|-------------|------------------|
| SC-1 | v3 user opens Phase-01 project and pans/zooms/clicks territories | §Standard Stack (Konva 10.2.5 + react-konva 19.2.x reused); §Code Examples (CanvasViewer reuse plan + URL switch) |
| SC-2 | Inspector populates on click; layer toggles work | §Architecture Patterns §Multi-select state shape; §Don't Hand-Roll (use existing `InspectorSidebar`) |
| SC-3 | Old stepper invisible; no console errors | §Don't Hand-Roll (delete graph below); §Common Pitfalls Pitfall 1 (dangling-import sweep) |
| SC-4 | Runs against Phase 01 artifacts directly | §Architecture Patterns §Artifact-serving route handler; §Validation Architecture (Phase 01 parity 10/10 stays green) |
| D-22 | POST `/generate` + SSE stream | §Code Examples §SSE generator (mirrors Phase 02 `_v3_sse_generator`) |
| D-21 | `GET /status` manifest | §Code Examples §Status manifest |
| D-12 | Lift `_write_geojson_atomic` to `paths.py` (gates v1 ingest delete) | §Runtime State Inventory + §Common Pitfalls Pitfall 2 |
| D-13 | LLM purge audit | §Don't Hand-Roll §LLM consumer graph (FULL delete recommended) |

</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

`./CLAUDE.md` exists and binds this phase. Lifted verbatim authority items:

1. **Stack**: Python 3.11+ / FastAPI / SQLite (backend); React 19 + TypeScript + Vite 6 + Konva.js (frontend); Zustand v5 + zundo 2.3.0 `temporal`; TanStack Query v5; Tailwind v4 + Radix UI Themes 3.x. **No alternatives may be introduced this phase.**
2. **No LLM in the geometric path**: pipeline must produce a valid 12-file export with zero LLM calls. Phase 03 deletes the v1 LLM stack entirely (D-13).
3. **Single mutable input — `RegionConfig`**: no `importlib.reload`, no `sys.modules` patching, no global state. Phase 03's `/generate` endpoint constructs `cfg` exactly as Phase 01's `iberia_config()` does.
4. **Deployed wins (D-09 carry-forward)**: canvas displays exactly what the pipeline emitted. No client-side reinterpretation, no re-projection, no smoothing or re-coloring at the StaticFiles boundary.
5. **NEAREST upscale only**: lookup PNGs read by the canvas use `<img>` tags with `image-rendering: crisp-edges` (or `pixelated`). Never call `BICUBIC` / `BILINEAR` on lookup PNGs.
6. **Atomic commits per task**: each task ≤ 1 commit; messages `type(03-NN): subject`. Deletion commits use `chore(03-NN): delete v1 ...`.
7. **Three-layer test pyramid**: every phase delivers (1) `tests/unit/` pytest + vitest, (2) `tests/parity/` non-skippable parity vs. Reconquista, (3) `tests/uat/playwright/` Playwright UAT for any UI surface. Frontend ≥ 80 % coverage in `v3/`, backend ≥ 85 %.
8. **Rejected designs (must push back if a plan suggests them)**: stepper UI (Phase 03 anti-target), `sys.modules` patching, upscale interpolation, global Voronoi, hand-rolled compound undo, LLM-mandatory pipeline.
9. **Determinism**: `np.random.default_rng(42)` is locked in `RegionConfig`. Seed changes break parity tests.
10. **PT-BR responses**: any UI text Phase 03 introduces is Portuguese; code/identifiers/commits stay English. Existing English `COPY` constants in `InspectorSidebar.tsx` are test-asserted and MUST NOT be translated.

---

## Summary

Phase 03 is a **read-only frontend rewrite** + **three small backend endpoints** + a **wide v1 deletion sweep**. The mechanical risk is small (Phase 02 already provides the SSE template, Phase 01 already provides `run_pipeline(cfg)`, and the 5-layer Konva stack is read-only-friendly). The cognitive risk concentrates in three places: (1) the **artifact-serving primitive** is misnamed in CONTEXT D-18 — `StaticFiles` cannot rewrite the URL segment `{id}/artifacts/*` to disk path `{id}/output/*`, so a `FileResponse`-based route handler with `is_valid_uuid` + filename allowlist is the correct primitive; (2) the **delete-graph fan-out** is large enough that one missed import breaks SC-3 ("no console errors"), so a **grep-based dangling-import sweep is the gate before merge**; (3) the **`_write_geojson_atomic` lift** is a pre-flight task because both `services/pipeline/adapters/base.py` AND `services/ingest_terrain/runner.py` (3 callsites) import it from the to-be-deleted `services/ingest_runner.py`.

**Primary recommendation:** Adopt the 4-wave plan in §Architecture Patterns. Wave 0 lifts `_write_geojson_atomic` and removes the `terrain` LayerName. Wave 1 builds the new endpoints in parallel with the frontend rewrite. Wave 2 deletes v1 (gated on Wave 1 green). Wave 3 ships the Playwright UAT. Use **`FileResponse` route + UUID + filename allowlist**, **uuid4 run-ids**, **structured SSE envelope** (`{stage, event_type, message, progress?}`), **single Zustand `useRunStore`** for run state, and **HTML `<div>` overlay positioned via `Stage.getPointerPosition()`** for hover tooltips. Delete `api/auth.py` + `services/credential_store.py` + `models.LLMCredential` + `models.ResearchCache` + `models.CodexCache` — the entire LLM consumer graph is in the deletion set.

---

## Standard Stack

### Core (already locked by `package.json` / `pyproject.toml` — no install needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `react` | 19.2.0 | UI | Locked by CLAUDE.md `[VERIFIED: package.json:21]` |
| `react-konva` | 19.2.3 | Canvas reconciler | Read-only Konva stack reuse — only data hydration changes (D-09) `[VERIFIED: package.json:24]` |
| `konva` | 10.2.5 | Canvas runtime | Underlies react-konva; `getPointerPosition()` used for tooltip math `[VERIFIED: package.json:20]` |
| `@radix-ui/themes` | 3.3.0 | Component library (Card, Flex, Button, Callout, Badge, ScrollArea, Heading, Text) | Used by InspectorSidebar + LayerTogglePanel; UI-SPEC §Design System locks Radix Themes `[VERIFIED: package.json:18]` |
| `@radix-ui/react-icons` | 1.3.2 | Icons (ChevronRight/Left, ExclamationTriangleIcon, MagicWandIcon) | Already installed; UI-SPEC §Component Inventory uses these `[VERIFIED: package.json:16]` |
| `zustand` | 5.0.12 | State (selection, run state, layer visibility) | Locked by CLAUDE.md; existing `uiStore.ts` already uses v5 syntax `[VERIFIED: package.json:29]` |
| `@tanstack/react-query` | 5.99.0 | Artifact + status fetching | Locked by CLAUDE.md; `useCanvasArtifacts` already uses v5 `useQueries` `[VERIFIED: package.json:19]` |
| `react-router-dom` | 7.14.0 | Routing | Already installed; D-23 reuses `<Route path="/projects/:id">` `[VERIFIED: package.json:26]` |
| `react-error-boundary` | 4.1.2 | Error boundary around inspector + canvas | Already used in v1 `ProjectDetail.tsx`; reusable `[VERIFIED: package.json:23]` |
| `fastapi` | (existing) | HTTP + SSE | Phase 02 `_v3_sse_generator` template `[VERIFIED: api/v3/ingest.py]` |

> **No new dependencies required.** Phase 03 ships zero `npm install` / `pip install` commands. This is a deliberate Karpathy "use what's there" outcome.

### Supporting (already installed)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `@playwright/test` | 1.59.1 | UAT smoke per CLAUDE.md three-layer pyramid | New `tests/uat/playwright/03-canvas-workspace.spec.ts` `[VERIFIED: package.json:32]` |
| `vitest` | 3.2.4 | Frontend unit + RTL | New `useRunStore.test.ts`, `WorkspaceToolbar.test.tsx`, etc. `[VERIFIED: package.json:47]` |
| `pytest` | (existing) | Backend unit + parity | New `test_v3_generate.py`, `test_v3_status.py`, `test_v3_artifacts.py` `[CITED: pyproject.toml]` |

### Alternatives Considered (REJECTED — do NOT introduce)

| Instead of | Could Use | Tradeoff (REJECTED reason) |
|------------|-----------|----------|
| FastAPI route handler + `FileResponse` | `app.mount(StaticFiles)` directly | StaticFiles cannot URL-rewrite `{id}/artifacts/*` → disk `{id}/output/*` (see Pitfall 3) `[VERIFIED: WebSearch — fastapi.tiangolo.com/reference/staticfiles/]` |
| `useRunStore` Zustand | Derive from TanStack Query `/status` polling | TanStack Query has no natural place for SSE log accumulator; re-mount survival is automatic with Zustand `[ASSUMED — see A1 in §Assumptions Log]` |
| Structured SSE envelope `{stage, event_type, ...}` | Plain text stream (Phase 02 style) | Phase 02 stream is one OSM step; Phase 03 needs to drive an 11-stage checklist. Structured envelope avoids regex parsing on the frontend `[ASSUMED — see A2 in §Assumptions Log]` |
| HTML `<div>` tooltip overlay | Radix `Tooltip` | Radix Tooltip needs a DOM anchor; Konva nodes are not DOM. Radix-on-Konva requires portal dance `[CITED: konvajs.org/docs/sandbox/Relative_Pointer_Position.html]` |
| `uuid4` run-ids | `project_id+timestamp` | timestamp collides on fast retry within the same millisecond; `uuid4` is what `paths.is_valid_uuid` already validates |
| Native HTTP cache (no ETag) | Custom `If-None-Match` | `?v={updated_at}` query string already triggers a fresh URL → fresh cache entry. ETag adds complexity without benefit |

**Version verification:** Versions above were lifted directly from `package.json` (not `npm view`) because Phase 03 is forbidden from upgrading dependencies (CLAUDE.md "no new deps"). The package.json was last touched 2026-04-22 (260422-f6f); within 30-day staleness window.

---

## Architecture Patterns

### Recommended Project Structure (changes only)

```
backend/medieval_forge/
├── api/
│   ├── v3/
│   │   ├── __init__.py        # exists (Phase 02)
│   │   ├── ingest.py          # exists (Phase 02 — keep)
│   │   ├── generate.py        # NEW — POST /generate + GET /generate/stream
│   │   ├── status.py          # NEW — GET /status (manifest)
│   │   └── artifacts.py       # NEW — GET /artifacts/{file_path:path}
│   ├── auth.py                # DELETE (D-13 audit conclusion)
│   ├── codex.py               # DELETE (D-13)
│   ├── ingest.py              # DELETE (D-12)
│   ├── llm.py                 # DELETE (D-13)
│   ├── research.py            # DELETE (D-13)
│   ├── edit.py                # DELETE (frontend api/edit.ts is gone — confirm no other consumers in Wave 0)
│   └── terrain.py             # KEEP (Phase 02 D-13 stub — terrain ingestion still wired through this)
├── services/
│   ├── ingest_runner.py       # DELETE (D-12) — but lift _write_geojson_atomic FIRST
│   ├── ingest_wikidata.py     # DELETE (D-12)
│   ├── credential_store.py    # DELETE (D-13 audit conclusion)
│   ├── research_runner.py     # DELETE (D-13)
│   ├── research_cache.py      # DELETE (D-13)
│   ├── codex_runner.py        # DELETE (D-13)
│   ├── codex_cache.py         # DELETE (D-13)
│   ├── llm/                   # DELETE entire subpackage (D-13)
│   ├── territory_builder.py   # DELETE (LLM consumer)
│   ├── territories_geojson.py # AUDIT (Wave 0 grep) — likely unused after deletes
│   ├── voronoi.py             # AUDIT — v1 leftover; pipeline/voronoi.py is the real one
│   ├── baronies_builder.py    # AUDIT — v1 leftover
│   ├── render_modern.py       # AUDIT (referenced by ProjectDetail.tsx renderModern)
│   ├── project_meta.py        # AUDIT
│   └── paths.py               # KEEP + EXTEND (gain `_write_geojson_atomic`)
├── main.py                    # SHRINK (delete LLM imports + lifespan body)
└── models.py                  # SHRINK (delete LLMCredential, ResearchCache, CodexCache classes)

frontend/src/
├── pages/
│   ├── ProjectDetail.tsx      # REWRITE (697 → ~250 LOC)
│   └── TerritoryEditor.tsx    # DELETE (D-10)
├── components/
│   ├── workspace/             # NEW SUBDIR
│   │   ├── WorkspaceToolbar.tsx
│   │   ├── GenerateStatusBadge.tsx
│   │   ├── RunLogPanel.tsx
│   │   ├── EmptyCanvasState.tsx
│   │   ├── GeneratingCanvasState.tsx
│   │   └── ErrorCanvasCallout.tsx
│   ├── canvas/
│   │   ├── CanvasViewer.tsx           # STRIP (delete edit imports + paint/split/rubber-band/vertex)
│   │   ├── TerritoryLayer.tsx         # STRIP (delete useEditorStore + useProjectStore + terrain branch)
│   │   ├── InteractionLayer.tsx       # EXTEND (selectedTerritoryIds: string[])
│   │   ├── HoverTooltip.tsx           # NEW (D-15 — DOM div overlay)
│   │   ├── MultiSelectInspector.tsx   # NEW (D-17)
│   │   ├── EditToolbar.tsx            # DELETE
│   │   ├── SplitTool.tsx              # DELETE
│   │   ├── VertexHandlesLayer.tsx     # DELETE
│   │   ├── SelectionFloatingToolbar.tsx # DELETE
│   │   ├── ValidationBadgesLayer.tsx  # DELETE
│   │   ├── TerrainBadgesLayer.tsx     # DELETE (LayerName 'terrain' goes; tied to useProjectStore)
│   │   ├── SettingsPanel.tsx          # AUDIT (Wave 0)
│   │   └── SaveStatusIndicator.tsx    # DELETE (no save in read-only)
│   ├── pipeline/              # DELETE entire subdir (D-11)
│   ├── research/              # DELETE entire subdir (D-13)
│   ├── codex/                 # DELETE entire subdir (D-13)
│   └── ingest/
│       └── BaronyGranularitySlider.tsx # DELETE (D-11)
├── stores/
│   ├── uiStore.ts             # MODIFY (selectedTerritoryIds: string[]; remove 'terrain' from LayerName)
│   ├── useRunStore.ts         # NEW (run state machine + log lines)
│   ├── usePipelineStore.ts    # DELETE
│   ├── useProjectStore.ts     # DELETE
│   ├── useResearchStore.ts    # DELETE
│   ├── useEditorStore.ts      # DELETE
│   └── useValidationStore.ts  # DELETE
├── hooks/
│   ├── useCanvasArtifacts.ts  # MODIFY (URL prefix swap /preview/ → /api/v3/projects/{id}/artifacts/)
│   ├── useRubberBandSelection.ts # DELETE
│   ├── useUndoShortcut.ts     # DELETE
│   ├── useEditKeyboardMap.ts  # DELETE
│   ├── useBeforeUnloadGuard.ts # DELETE
│   ├── useResearchStream.ts   # DELETE
│   └── useCodexStream.ts      # DELETE
├── api/
│   ├── client.ts              # SHRINK (remove useIngestStream/useGenerate/useExport/useTerritoryTemplate/useRenderModern hooks that are v1-only)
│   ├── edit.ts                # DELETE
│   ├── research.ts            # DELETE
│   ├── codex.ts               # DELETE
│   └── useTerrainStepStream.ts # DELETE
└── services/
    ├── persistence.ts         # DELETE (D-10)
    └── validation.ts          # DELETE (D-10)
```

### Pattern 1: SSE pair endpoint (D-22)

**What:** `POST /generate` schedules the run + returns 202; `GET /generate/stream` returns the SSE event stream.

**Why this shape (vs single GET-with-side-effect):** Phase 02's v3 ingest is a single GET that doubles as schedule + stream. CONTEXT D-22 explicitly asks for the POST-then-GET pair to mirror the canonical "command/event" split. The advisor flagged this as the right move — it lets multiple browser tabs subscribe to the same run via separate streams.

**When to use:** any pipeline trigger longer than ~3 s where the user might re-mount during the run.

**Example (sketch — full code in §Code Examples):**
```python
# api/v3/generate.py
_RUN_QUEUES: dict[str, asyncio.Queue[str | None]] = {}
_RUN_TASKS: dict[str, asyncio.Task] = {}
_STOP_EVENTS: dict[tuple[str, str], asyncio.Event] = {}  # symmetry with v3 ingest

@router.post("/{project_id}/generate", status_code=202)
async def trigger_generate(project_id: str, db: AsyncSession = Depends(get_db)):
    if not is_valid_uuid(project_id): raise HTTPException(400, ...)
    # 409 if already running. Construct cfg via iberia_config()-equivalent.
    # asyncio.create_task wraps run_pipeline in to_thread.
    return {"run_id": uuid4(), "status": "scheduled"}

@router.get("/{project_id}/generate/stream")
async def stream_generate(project_id: str): ...
```

### Pattern 2: Artifact-serving route handler (D-18 — corrects CONTEXT wording)

**What:** A `FileResponse`-based route handler with UUID validation + filename allowlist + path containment check.

**Why not `app.mount(StaticFiles(...))`:**
- The required URL is `/api/v3/projects/{id}/artifacts/{file}` and the disk path is `projects/{id}/output/{file}`. `StaticFiles` mounts at a **fixed** prefix and serves files **relative** to that prefix; it cannot rewrite a `{id}` URL segment to insert `output/` `[CITED: fastapi.tiangolo.com/reference/staticfiles/]`.
- Two technically-possible mount alternatives both have problems:
  1. Mount at `/api/v3/projects` rooted at `PROJECTS_ROOT` → URL becomes `/api/v3/projects/{id}/output/{file}` — diverges from CONTEXT D-18 + UI-SPEC notes.
  2. Mount per-project at app startup → impossible (projects are created at runtime).
- `FileResponse` gives explicit control over `Cache-Control`, `ETag`, and 404 vs 422 errors `[CITED: fastapi.tiangolo.com docs]`.

**When to use:** any per-tenant / per-project file serving where the URL contains a tenant id segment.

**Example (sketch — full code in §Code Examples).**

### Pattern 3: Multi-select state shape (D-17)

**What:** Promote `useUIStore.selectedTerritoryId: string | null` → `useUIStore.selectedTerritoryIds: string[]`. Single selection = `[id]`; cleared = `[]`. Derive a `selectedTerritoryId` getter (`ids[0] ?? null`) for backward compatibility with `panToGeoCenter`'s "center on the new selection" effect.

**Why one store, not two:** `useEditorStore.rubberBandSelectionIds` was the v1 multi-select home and is being deleted. Adding a new `useSelectionStore` would re-fragment selection state; consolidating in `useUIStore` keeps the read-only mental model "selection is UI-state."

**When to use:** any time the existing single-id selection contract bleeds into shift+click behavior.

**`InteractionLayer` extension:**
```tsx
// BEFORE (read this verbatim from InteractionLayer.tsx:23)
const selectedPolygons = selectedTerritoryId
  ? territories.filter((t) => t.id === selectedTerritoryId)
  : []

// AFTER
const idsSet = new Set(selectedTerritoryIds)
const selectedPolygons = territories.filter((t) => idsSet.has(t.id))
```
The "InteractionLayer already supports multi-outline rendering" claim from CONTEXT/UI-SPEC is **half-true**: it iterates `<Line>`s for the multi-polygon case of *one* selected id, but does NOT iterate over a set of ids. The above 3-line change is required (advisor flagged this).

### Pattern 4: Run state machine in Zustand (Claude's Discretion → recommended)

**What:** A new `useRunStore` Zustand store owns:
```ts
type RunState = 'idle' | 'ingesting' | 'generating' | 'generated' | 'error'
interface RunStoreState {
  state: RunState
  runId: string | null
  currentStage: string | null              // e.g. 'voronoi'
  completedStages: string[]                // ['landmask', 'border', 'voronoi']
  logLines: string[]                       // raw SSE messages (capped at ~500)
  errorMessage: string | null
  errorStage: string | null
  // actions
  start: (runId: string, kind: 'ingest' | 'generate') => void
  appendLog: (line: string) => void
  markStageComplete: (stage: string) => void
  finish: (state: 'generated' | 'error', errorMessage?: string) => void
  reset: () => void
}
```

**Why Zustand vs derived TanStack:** TanStack Query is great at request/response cache, awkward at streaming-log accumulation. Zustand survives `<ProjectDetail>` unmount/remount (StrictMode double-mount, route quirks), giving naturally-stable run state. The advisor confirmed this choice.

### Pattern 5: SSE event envelope (Claude's Discretion → recommended)

**What:** Phase 03 sends structured JSON in each `data:` line:
```
data: {"event_type":"stage_start","stage":"voronoi","message":"Setting up baronies...","progress":null}\n\n
data: {"event_type":"stage_done","stage":"voronoi","message":"OK","progress":0.27}\n\n
data: {"event_type":"error","stage":"voronoi","message":"<exception class>","progress":null}\n\n
data: {"event_type":"done","stage":null,"message":"OK","progress":1.0}\n\n
```

**Why structured (not Phase 02's plain text):** Phase 02's stream is a single OSM step → free text fits. Phase 03 needs to drive an 11-stage checklist UI; structured envelope avoids regex parsing on the frontend.

**Stages enumerated (11 — matches `run_pipeline` order):**
`landmask → border → voronoi → cleanup → smooth → merge → hierarchy → render → lookup → metadata → export`

The first three (`landmask`, `border`, `voronoi`) sit in `run_pipeline` Steps 3-7 in the source `[VERIFIED: services/pipeline/__init__.py:78-100]`. To emit per-stage events the orchestrator needs SSE hooks added (not in scope per D-04 reservation — but see "Lighter Implementation" below).

**Lighter implementation (avoids modifying `run_pipeline`):**
The producer task wraps `asyncio.to_thread(run_pipeline, cfg)` in a single call. Stage progress markers come from **a callback hook injected via `RegionConfig` (a new optional `cfg.on_stage: Callable[[str, str], None] | None = None`)**. `run_pipeline` calls `cfg.on_stage("voronoi", "start")` / `cfg.on_stage("voronoi", "done")` at each Step boundary. The producer task wires `on_stage = lambda stage, evt: queue.put_nowait(json.dumps({...}))`. **This change is one-line per stage in `run_pipeline.__init__.py`** — and Karpathy-pure since the slot is `None` for Phase 01 parity (no behavior change, no parity break).

**Backward-compat alternative (no `run_pipeline` changes):** stream a single `{"event_type":"running","message":"..."}` heartbeat every 500 ms while `to_thread` runs, then emit `done` on completion. Frontend log panel just shows "Running…" instead of stage checkmarks. **D-03 explicitly demands per-stage checkmarks**, so the callback-hook approach is required.

### Pattern 6: Hover tooltip via DOM overlay (Claude's Discretion → recommended)

**What:** A `HoverTooltip.tsx` component renders a `position: absolute; pointer-events: none; z-index: 50` `<div>` outside the Konva `<Stage>` but inside the same workspace container.

**Position math:**
```ts
// On TerritoryPolygon mouseover:
const stage = stageRef.current
const pos = stage?.getPointerPosition()  // returns stage-absolute coords (top-left of canvas DOM)
if (pos) setTooltipPos({ x: pos.x, y: pos.y })  // offset by container offsetTop/Left if nested
```
`getPointerPosition()` returns coordinates relative to the top-left of the Stage's container `[CITED: konvajs.org/api/Konva.Node.html]`. For a tooltip positioned in the same parent container as `<Stage>`, no further math is needed.

**Why not `getRelativePointerPosition()`:** that returns coordinates **inside the Konva coordinate system** (after stage scale + position transforms), which is what you want for **placing Konva shapes** at the cursor — wrong for DOM overlays `[CITED: konvajs.org/docs/sandbox/Relative_Pointer_Position.html]`.

**Performance:** mousemove fires hundreds of times per second. Debounce/throttle is **not** needed if the tooltip only updates `setTooltipPos` state at one DOM `<div>` (React 19 auto-batches; the canvas itself does not re-render — it's a sibling). Throttle to ~16 ms (one frame) only if the InspectorSidebar starts laggy. The hover outline (Konva) is on a dedicated layer so changing it doesn't re-render `TerritoryLayer`.

**Hover layer placement:** add a new Konva `<Layer listening={false}>` between `BaronyLayer` and `InteractionLayer` (or share `InteractionLayer` if the gold-on-grey overlap looks fine — design call during plan check).

### Anti-Patterns to Avoid

- **`StaticFiles` for `/api/v3/projects/{id}/artifacts/*`** — see Pattern 2 above. CONTEXT D-18 wording is imprecise; use `FileResponse` route handler.
- **Modifying `run_pipeline` signature for SSE hooks** — only ADD an optional `cfg.on_stage` callback; never change positional args. Phase 01 parity tests do not pass a callback → behavior unchanged → parity stays 10/10.
- **Polling `/status` instead of subscribing to the SSE stream during a run** — wastes Q/s and races the stream. Poll `/status` on **mount only** to decide which UI state to show; switch to SSE for live updates.
- **Reusing the v1 `/preview/*` endpoint shape** — D-18 explicit. Do not partially migrate.
- **Multi-select via two stores** — see Pattern 3.
- **`Konva.clearCache()` in read-only** — v1-archive lists this for **post-mutation** cleanup. Phase 03 has no mutations, so `clearCache()` is unneeded. (Phase 04 will need it.)
- **BICUBIC/BILINEAR upscale** — CLAUDE.md non-negotiable rule #1. The 12 files come pre-rendered from `run_pipeline`; the canvas displays them via `<Image>` with `image-rendering: crisp-edges`. The pipeline already does NEAREST upscale per Phase 01 parity.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-project static-file serving | A custom file-iteration loop | `FileResponse` + `is_valid_uuid` + filename allowlist (existing `paths.py` helpers) | Path traversal protection + Cache-Control are first-class on FileResponse `[CITED: fastapi.tiangolo.com — A Practical Guide to FastAPI Security]` |
| SSE producer/consumer | A new pattern | Verbatim copy of `api/v3/ingest.py:_v3_sse_generator` + `_adapter_producer` | Phase 02 already proved the shape; tests already exist as patterns `[VERIFIED: api/v3/ingest.py]` |
| UUID validation + path containment | A regex | `services/paths.is_valid_uuid` + `services/paths.project_dir` (raises on escape) | Already implemented + tested `[VERIFIED: services/paths.py:23-50]` |
| Run state machine | A class with enums + transitions | Zustand store with discriminated union | React 19 + Zustand 5 + 5 states is the simpler shape |
| Konva selection outline | Re-rendering `TerritoryLayer` on selection change | Existing `InteractionLayer` (with `selectedTerritoryIds: string[]` extension) | O(1) selection per RESEARCH §Pattern 7 from v1; sibling polygons don't re-render |
| Project status manifest | A new schema crate | A pydantic `ResponseModel` returning `{status, has_artifacts: dict[str, bool], last_generated_at}` | Existing `ProjectResponse` is the precedent; Phase 06 will tighten |
| Hover tooltip lib | `react-tooltip` / `floating-ui` | Plain `<div>` overlay positioned via `Stage.getPointerPosition()` | Konva can't be a Radix Tooltip anchor (DOM-only); installing a lib violates CLAUDE.md "no new deps" |
| Run-id generator | Custom counter + monotonic clock | `uuid4()` (already imported by `models._new_uuid`) | One-line, collision-resistant, validates via `is_valid_uuid` |
| Cache-busting | Filename hashing + manifest | `?v={project.updated_at}` query string | Already proven in v1 `cacheVersion` prop; CONTEXT D-19 locks this `[VERIFIED: useCanvasArtifacts.ts:111]` |
| Ingest+generate ordering | A new orchestrator | Two SSE streams (Phase 02 `/ingest` followed by Phase 03 `/generate`) | Each step has its own status transitions and error handling |

**Key insight:** Phase 03 is **assembly, not invention**. Every problem the planner needs to solve has either an existing FastAPI primitive (`FileResponse`, `StreamingResponse`, `Depends`) or an existing intra-repo pattern (`_v3_sse_generator`, `useCanvasArtifacts`, `paths.is_valid_uuid`). The planner's job is to spell out the assembly order — not to design new abstractions.

### LLM consumer graph — D-13 audit conclusion

**Recommendation: DELETE everything in the LLM graph including `api/auth.py`, `services/credential_store.py`, `models.LLMCredential`, `models.ResearchCache`, `models.CodexCache`.**

**Evidence (`grep` results saved into research):**
- `api/auth.py` line 27: `from ..services.llm.registry import PROVIDERS` — depends on deleted `services/llm/`.
- `api/auth.py` line 28: `from ..services import credential_store` — surviving consumer is `api/auth.py` itself + `api/llm.py` (deleted) + `main.py` lifespan body (must shrink) + `services/research_runner.py` (deleted).
- `services/credential_store.py` line 18: `from ..models import LLMCredential` — `LLMCredential` is referenced ONLY in `credential_store.py` (5 callsites) `[VERIFIED: grep LLMCredential backend]`.
- `main.py` lines 30-37 (lifespan body): preloads credentials into `app.state.credentials` and sets `app.state.oauth_states = {}`. Both die when LLM is gone.
- `models.LLMCredential` (lines 44-66), `models.ResearchCache` (lines 69-80), `models.CodexCache` (lines 83-100): only referenced by `services/credential_store.py`, `services/research_cache.py`, `services/codex_cache.py` — all deleted.
- Tests: `test_auth_session.py`, `test_oauth_flow.py`, `test_research_cache.py`, `test_research_runner_map_path.py`, `test_codex_*.py`, `test_llm_*.py`, `test_assignment_edit.py`, `test_research_sse.py`, `test_codex_endpoints.py`, `test_providers_endpoint.py`, `test_territory_builder*.py`, `test_condado_assignment.py`, `test_oauth_flow.py`, `test_cli_piggyback.py`, `test_llm_routing.py`, `test_codex_runner.py`, `test_codex_schema.py`, `test_codex_prompt.py`, `test_llamacpp_provider.py`, `test_map_research_prompt.py`, `test_llm_schemas.py`, `test_llm_retry.py`, `test_llm_registry.py`, `test_llm_providers.py`, `test_barony_assignments_validation.py` — **all delete with their production code** per CLAUDE.md "tests delete alongside their production".

**Side-effects requiring planner attention:**
1. `main.py` lifespan body shrinks to just `Base.metadata.create_all` for the surviving `Project` table.
2. `Base.metadata.create_all` will silently no-op for the deleted ORM tables in existing user DBs — **acceptable** (orphan tables don't break v3, and v3 is local single-user). If the planner is paranoid, ship a one-shot Alembic 0004 that drops `llm_credentials`, `research_cache`, `codex_cache`. Karpathy-defer unless a real user reports it.
3. `pyproject.toml` LLM dependencies (`anthropic`, `google-genai`, `ollama`, `openai`, `google-auth-oauthlib`) become orphan installs but stay safe in the lockfile. Trim only if the plan reaches a "clean dependency tree" task — not required by SC-1..SC-4.

### Frontend consumer graph — D-10/D-11/D-13 audit conclusion

**Files to delete (full list, gathered via `grep` for the deleted-store imports):**

Stores (5): `usePipelineStore`, `useResearchStore`, `useEditorStore`, `useValidationStore`, `useProjectStore` (the last one was used by `TerritoryLayer.tsx` for terrain mode + capital edits — strip).

Hooks (6): `useResearchStream`, `useCodexStream`, `useUndoShortcut`, `useBeforeUnloadGuard`, `useEditKeyboardMap`, `useRubberBandSelection`.

API modules (4): `api/edit.ts`, `api/research.ts`, `api/codex.ts`, `api/useTerrainStepStream.ts`. **`api/client.ts` survives** but loses several v1-only hooks (`useIngestStream`, `useGenerate`, `useExport`, `useTerritoryTemplate`, `useRenderModern`, `useIngestStatus` — confirm during planning grep).

Services (2): `services/persistence.ts`, `services/validation.ts`.

Components (deleted, ~24 files):
- `components/pipeline/Stepper.tsx`, `StepCard.tsx`, `ProviderEffortPicker.tsx`, `TerrainDataSection.tsx` (+ tests)
- `components/research/AssignmentEditor.tsx`, `ResearchDialog.tsx`, `ProviderSelector.tsx`, `AuthSetupSheet.tsx` (+ tests)
- `components/codex/CodexViewer.tsx`
- `components/ingest/BaronyGranularitySlider.tsx`
- `components/canvas/EditToolbar.tsx`, `SplitTool.tsx`, `VertexHandlesLayer.tsx`, `SelectionFloatingToolbar.tsx`, `ValidationBadgesLayer.tsx`, `TerrainBadgesLayer.tsx`, `SaveStatusIndicator.tsx`, `SettingsPanel.tsx` (+ their tests, and the SplitTool/CapitalDrag/shiftClick canvas tests)

Pages (1): `pages/TerritoryEditor.tsx`.

**Components to STRIP (keep file, surgically remove deleted-import references):**
- `CanvasViewer.tsx` (697 LOC → ~400 LOC) — UI-SPEC #1 explicitly admits "reused as-is" is impossible.
- `TerritoryLayer.tsx` — drops `useEditorStore`, `useProjectStore`, terrain-color branch. New click handler is shift+click multi-select per D-17.
- `LayerTogglePanel.tsx` — remove `'terrain'` row + `LayerName` member.
- `uiStore.ts` — `selectedTerritoryId` → `selectedTerritoryIds: string[]`; remove `'terrain'` from `LayerName`; remove `overlayImageUrl`/`overlayOpacity` (Phase 5 reference overlay, no longer needed).

**Backend route registrations to remove from `main.py`:**
```python
# DELETE these imports + include_router calls:
from .api.ingest import router as ingest_router
from .api.export import router as export_router  # CHECK — export may survive for v3.1 ZIP button
from .api.auth import router as auth_router
from .api.research import router as research_router
from .api.codex import router as codex_router
from .api.llm import router as llm_router
from .api import edit as edit_api
# Phase 02's `from .api import terrain as terrain_api` STAYS.
```

> **Note on `api/export.py`:** UI-SPEC mentions an "Exportar ZIP" button on the toolbar. CONTEXT does not delete `api/export.py`. Audit during planning whether the existing `/api/projects/{id}/export` works against the new artifact layout (`projects/{id}/output/`) or needs a v3 wrapper. **This is a deferred-to-planning question**, not a research blocker.

---

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** (DB) | (1) `llm_credentials` table — orphan after D-13. (2) `research_cache` table — orphan. (3) `codex_cache` table — orphan. (4) `projects` table — surviving; **`Project.generator_config` may carry stale v1 stepper state**. | (1)(2)(3) optional Alembic drop migration — Karpathy-defer unless reported. (4) audit `Project.generator_config` consumers; if v1-only, set to `None` on first /generate. |
| **Live service config** | None. Phase 03 introduces no external services (no Datadog, no Tailscale, no Cloudflare, no n8n). All state is local. | None — verified by grep "Datadog|Cloudflare|Tailscale|n8n" → 0 hits. |
| **OS-registered state** | (1) `medieval-forge start` is a Click CLI shipped via `pyproject.toml` `[project.scripts]`. (2) No Windows Task Scheduler, no launchd, no systemd. | None — verified by grep "[project.scripts]" `pyproject.toml`. |
| **Secrets / env vars** | (1) **LLM API keys** persisted in `~/.medieval-forge/medieval_forge.db` `llm_credentials` table — go orphan with the table. No env-var rename needed. (2) `GOOGLE_CLIENT_CONFIG` placeholders in `auth.py` — die with the file. (3) No `.env` files in repo (confirmed by glob). | None — keys are user-local; D-13 deletes the consumer code. Privacy-aware users can `DELETE FROM llm_credentials` after upgrade. |
| **Build artifacts** | (1) `frontend/dist/` (Vite build) — must rebuild after frontend rewrite, but auto-rebuilds on next `npm run build`. (2) Python `__pycache__` dirs — auto-rebuild. (3) `pyproject.toml` LLM dependencies (anthropic, openai, google-genai, ollama, google-auth-oauthlib) — orphan but harmless; trim during a separate cleanup task if scope allows. | (1) Run `npm run build` post-rewrite. (2) None. (3) Optional `chore(03-NN): trim orphan LLM deps` task at end of phase. |
| **Browser state (NEW category — frontend SPA)** | (1) **TanStack Query cache** keys with `'preview'` substring (`['territories-geojson', id, v]`, etc.) — go stale after URL switch. Cache lives in tab memory; gone on hard refresh. (2) `localStorage` — `zundo`'s `temporal` middleware does NOT persist by default in this project (no `persist` middleware wrap detected `[VERIFIED: grep "persist\|persist" frontend/src/stores/]` — 0 hits). (3) Browser back-forward cache may have `/preview/*` URLs cached — first hit on new URL fetches fresh. | (1) Acceptable churn — `?v={updated_at}` query bust on first load makes new URLs cache-distinct. Document in user release notes if a release is shipped. (2) None. (3) None. |

**The canonical question — answered:** *After every file in the repo is updated, what runtime systems still have the old string cached, stored, or registered?* → SQLite `llm_credentials` / `research_cache` / `codex_cache` tables (orphan, harmless), and **TanStack Query memory cache for `/preview/*` URLs** (cleared on tab close). Both are non-blocking.

---

## Common Pitfalls

### Pitfall 1: SC-3 "no console errors" requires a dangling-import sweep

**What goes wrong:** A delete-task forgets one consumer of a removed module. ProjectDetail rewrite ships green; a flag-day later a developer hits `/projects/:id` for the first time and gets `Cannot find module './stores/useEditorStore'` in console — SC-3 fail at the worst possible time.

**Why it happens:** D-10/D-11/D-13 delete ~30+ frontend files with cross-cutting imports. `tsc -b` catches type errors at build time, but **dynamic imports** + `useResearchStore.tsx` with state-only access (string literals on stores) escape strict checks.

**How to avoid:**
1. After Wave 2, run `grep -r "components/pipeline\|usePipelineStore\|useResearchStore\|useEditorStore\|useValidationStore\|useProjectStore\|useResearchStream\|useCodexStream\|useRubberBandSelection\|useUndoShortcut\|useEditKeyboardMap\|useBeforeUnloadGuard\|api/edit\|api/research\|api/codex\|EditApiError\|TerritoryEditor\|EditToolbar\|SplitTool\|VertexHandlesLayer\|SelectionFloatingToolbar\|ValidationBadgesLayer\|TerrainBadgesLayer\|SaveStatusIndicator\|persistence\|services/validation\|TerrainDataSection\|AssignmentEditor\|ResearchDialog\|ProviderEffortPicker\|BaronyGranularitySlider\|CodexViewer\|AuthSetupSheet\|ProviderSelector\|Stepper\|StepCard" frontend/src/` → **expect zero results**.
2. Run `grep -rn "from.*\.\.\(.*\)\(api\|services\|stores\|hooks\|components\)" frontend/src/` and audit the import graph manually.
3. `npm run build` must complete without warnings.
4. `npm run test` must pass — vitest catches runtime imports the bundler skipped.
5. **Playwright UAT walks the read-only path end-to-end** — anything broken at runtime in JSX surfaces as a console error in the Playwright runner.

**Warning signs:** "Module not found" warnings during `vite build`; React DevTools showing "<UnknownComponent>" hierarchy; production bundle size unexpectedly large (deleted code still bundled).

### Pitfall 2: `_write_geojson_atomic` lift is gating

**What goes wrong:** D-12 deletes `services/ingest_runner.py`. But `services/ingest_terrain/runner.py` lines 20, 143, 222, 289 + `services/pipeline/adapters/base.py` line 6 still import `_write_geojson_atomic` from it. The delete breaks Phase 02 ingest **and** terrain ingestion.

**Why it happens:** advisor flagged this. The grep was incomplete — D-12 wording "Phase 02 v3 SSE adapter may import this" understated the blast radius.

**How to avoid:**
1. **Wave 0 task: Lift `_write_geojson_atomic` to `services/paths.py`.** It's 4 lines (`def _write_geojson_atomic(path, payload)`). One commit: `refactor(03-00): lift _write_geojson_atomic to paths.py`.
2. Update import sites: `services/pipeline/adapters/base.py` AND `services/ingest_terrain/runner.py` (3 callsites in one file).
3. Pytest passes BEFORE D-12 deletes `services/ingest_runner.py`.

**Warning signs:** running `pytest backend/tests/parity/` after the D-12 commit — if Phase 01 parity 10/10 fails on import error, the lift was skipped.

### Pitfall 3: StaticFiles vs FileResponse confusion (D-18 wording)

**What goes wrong:** Planner reads CONTEXT D-18 "FastAPI mounts `/api/v3/projects/{id}/artifacts/*`" literally and tries `app.mount("/api/v3/projects/{id}/artifacts", StaticFiles(directory=...))`. FastAPI does not interpret `{id}` in a mount path; the `{id}` becomes a literal directory.

**Why it happens:** "StaticFiles mount" sounds like the right primitive when the URL is `/api/.../artifacts/*`. It's wrong here because the disk path embeds the project id.

**How to avoid:** use Pattern 2 (FileResponse route handler). UI-SPEC + CONTEXT wording is shorthand for "natively cached read-only file serving" — Pattern 2 satisfies that intent without the mount mechanics.

**Warning signs:** 404 responses with "directory does not exist" log message at startup; tests that assert on 200 for `/api/v3/projects/{uuid}/artifacts/territory_metadata.json` fail with "no route matches".

### Pitfall 4: Konva ResizeObserver callback-ref + StrictMode double-mount

**What goes wrong:** A naive `useEffect(() => { ref.current ... }, [])` captures the loading-div once at first mount; React 19 StrictMode (or fast route navigation) remounts and the observer never reattaches. Stage stays at 800×600 forever.

**Why it happens:** v1-archive STATE.md GAP-05; v1's CanvasViewer was patched. The Phase 03 stripped CanvasViewer must preserve the **callback-ref ResizeObserver** pattern verbatim.

**How to avoid:** copy the callback-ref pattern from `CanvasViewer.tsx` lines 96-145 verbatim into the stripped version. Specifically:
- `setContainerRef = useCallback((el) => { ... }, [])` runs on every DOM (un)mount.
- Inside, disconnect the previous observer + create a new one + sync-read `getBoundingClientRect()` to handle the case where the ResizeObserver entry never fires.
- Also wire `useEffect(() => { return () => roRef.current?.disconnect() }, [])` for unmount safety.

**Warning signs:** Stage prop passes `width={800} height={600}` to the Konva runtime; the `<div>` parent has 100% width but the Stage stays at default. Tests `CanvasViewer.resize.test.tsx` should catch regressions.

### Pitfall 5: empty-Stage click deselect under StrictMode

**What goes wrong:** `if (e.target === stageRef.current) select(null)` works in dev but fails in StrictMode where the Stage is remounted between passes — the captured `stageRef.current` no longer matches the live stage.

**How to avoid:** use the v1-archive proven canonical pattern:
```ts
if (e.target === e.target.getStage()) select(null)
```
This reads "did the click bubble up to the Stage with no shape intercepting?" without referencing the closure-captured ref. Copy verbatim from `CanvasViewer.tsx:601-608`.

### Pitfall 6: Test fixture URL mismatch after switch

**What goes wrong:** `useCanvasArtifacts` switches from `/preview/*` → `/api/v3/projects/{id}/artifacts/*`, but `__tests__/CanvasViewer.test.tsx` mocks `/preview/*` URLs. Tests pass against MSW but production fetches 404.

**How to avoid:** every existing canvas test that mocks fetch must be updated in lock-step with the URL switch. Reference table:

| Test file | Mocked URLs (v1) | Required URLs (v3) |
|-----------|------------------|---------------------|
| `CanvasViewer.test.tsx` | `/preview/territory_metadata.json`, `/preview/territories.geojson`, `/preview/baronies.geojson`, `/preview/condado_colors.json`, `/preview/barony_colors.json` | Same suffix; prefix becomes `/api/v3/projects/${id}/artifacts/` |
| `CanvasViewer.hydrate.test.tsx` | same | same |
| `CanvasViewer.resize.test.tsx` | same | same |
| `CanvasViewer.panOnSelect.test.tsx` | same | same |
| `useCanvasArtifacts.cacheVersion.test.ts` | same + `?v=` | same + `?v=` |

### Pitfall 7: Aggregate inspector pixel→km² uses metadata.bounds

**What goes wrong:** Multi-select aggregate "Área total" sums `pixel_count` then converts to km². Reusing `pixelsToKm2` from `InspectorSidebar.tsx:12` requires `metadata.bounds` — the multi-select view must be a child of `<InspectorSidebar>` (which has metadata) OR receive metadata as a prop.

**How to avoid:** wrap the new `MultiSelectInspector` in the same `InspectorSidebarWrapper` data path. Pass `metadata.bounds + map_size` as props, not as global state.

### Pitfall 8: TerritoryLayer click handler reads deleted stores

**What goes wrong:** TerritoryLayer.tsx:42-65 reads `useEditorStore.getState()` for shift-click multi-select-in-edit-mode. After D-10 deletes `useEditorStore`, this throws `Cannot read property of undefined`.

**How to avoid:** rewrite the click handler to read from `useUIStore` only:
```ts
const handleClick = useCallback((id: string, shift: boolean) => {
  const ui = useUIStore.getState()
  if (shift) {
    const current = ui.selectedTerritoryIds
    ui.selectIds(current.includes(id)
      ? current.filter(x => x !== id)
      : [...current, id])
  } else {
    ui.selectIds([id])
  }
}, [])
```
Note: `selectIds(string[])` replaces `select(string | null)` — both are needed during the rewrite for the wrapper components that still call `select(neighborId)` (single-select neighbor chip).

### Pitfall 9: SSE reconnect on browser refresh during a run

**What goes wrong:** User clicks Generate, refreshes the tab mid-run. Frontend re-mounts → `useRunStore` resets to `idle` → user sees empty state — but the backend pipeline is still running, and 60 s later a stale `projects/{id}/output/` is half-written.

**Why it happens:** Phase 03 doesn't track run-id continuity across remounts.

**How to avoid:**
1. On `<ProjectDetail>` mount, fetch `/status` first.
2. If `status === 'generating'`, hydrate `useRunStore` from the response (`{state: 'generating', stage: '<unknown>'}`) and **subscribe to `/generate/stream`** — but the v3 endpoint must be **reentrant** (subsequent GETs to `/generate/stream` should hook into the existing run via `_RUN_QUEUES[project_id]`).
3. Or accept the limitation and treat refresh-mid-run as cosmetic: status badge stays "Gerando…" but log panel is empty until next event.

**Recommendation:** option (3) is Karpathy-correct for Phase 03 (~10 s pipeline; refresh-mid-run is rare). Document the rough edge in a comment in `useRunStore`. Phase 04 handles re-mount survival when sliders make runs frequent.

---

## Code Examples

Verified patterns from official sources + intra-repo references.

### Generate endpoint (POST + GET-SSE pair) — D-22

```python
# backend/medieval_forge/api/v3/generate.py
"""v3 SSE generate endpoint — wraps services/pipeline.run_pipeline (D-22)."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import AsyncIterator, Callable

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...database import AsyncSessionLocal, get_db
from ...models import Project
from ...services.paths import is_valid_uuid, project_dir
from ...services.pipeline import run_pipeline
from ...services.pipeline.regions import iberia_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v3/projects", tags=["v3-generate"])

# Per-project queue of SSE events (single in-flight run per project enforced via 409).
_RUN_QUEUES: dict[str, asyncio.Queue[str | None]] = {}
_RUN_TASKS: dict[str, asyncio.Task] = {}
_STOP_EVENTS: dict[tuple[str, str], asyncio.Event] = {}  # symmetry with v3 ingest


def _emit(queue: asyncio.Queue[str | None], event_type: str, stage: str | None,
          message: str = "", progress: float | None = None) -> None:
    """Structured SSE envelope per Pattern 5."""
    payload = {"event_type": event_type, "stage": stage, "message": message, "progress": progress}
    queue.put_nowait(f"data: {json.dumps(payload)}\n\n")


async def _set_status(project_id: str, status: str, sf: async_sessionmaker) -> None:
    async with sf() as session:
        proj = await session.get(Project, project_id)
        if proj is not None:
            proj.status = status
            await session.commit()


def _make_on_stage(queue: asyncio.Queue[str | None], loop: asyncio.AbstractEventLoop) -> Callable[[str, str], None]:
    """Sync callback bridged to the asyncio queue. Called from run_pipeline's worker thread."""
    def on_stage(stage: str, evt: str) -> None:
        # asyncio.run_coroutine_threadsafe — but Queue.put_nowait is sync-safe for the producer side.
        # We use call_soon_threadsafe so the event loop processes the queue write without blocking.
        loop.call_soon_threadsafe(_emit, queue, f"stage_{evt}", stage, "OK", None)
    return on_stage


async def _generate_producer(project_id: str, queue: asyncio.Queue[str | None],
                              sf: async_sessionmaker) -> None:
    try:
        _emit(queue, "started", None, f"Iniciando geração para projeto {project_id}", 0.0)

        # Build cfg using iberia_config()-equivalent + override dataset paths to project dir
        # (per-project; Phase 02 ingest already wrote inputs/ files there).
        cfg = iberia_config()
        cfg.output_dir = str(project_dir(project_id) / "output")
        # Wire on_stage callback through cfg
        cfg.on_stage = _make_on_stage(queue, asyncio.get_running_loop())

        await asyncio.to_thread(run_pipeline, cfg)

        await _set_status(project_id, "generated", sf)
        _emit(queue, "done", None, "OK", 1.0)
    except Exception as exc:
        logger.exception("v3 generate failed for project %s", project_id)
        # T-03-NN-NN (mirrors Phase 02 T-02-04-05): only emit class name in SSE.
        _emit(queue, "error", None, exc.__class__.__name__, None)
        try:
            await _set_status(project_id, "error_generating", sf)
        except Exception:
            logger.exception("failed to update status to error_generating")
    finally:
        await queue.put(None)  # terminal sentinel


@router.post("/{project_id}/generate", status_code=202)
async def trigger_generate(project_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    if not is_valid_uuid(project_id):
        raise HTTPException(400, "project_id must be a valid UUID")
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    if project.status == "generating" and project_id in _RUN_TASKS and not _RUN_TASKS[project_id].done():
        raise HTTPException(409, "project is already generating; subscribe to /stream to follow")

    project.status = "generating"
    await db.commit()

    queue: asyncio.Queue[str | None] = asyncio.Queue()
    _RUN_QUEUES[project_id] = queue
    task = asyncio.create_task(_generate_producer(project_id, queue, AsyncSessionLocal))
    _RUN_TASKS[project_id] = task
    return {"run_id": str(uuid.uuid4()), "status": "scheduled"}


@router.get("/{project_id}/generate/stream")
async def stream_generate(project_id: str) -> StreamingResponse:
    if not is_valid_uuid(project_id):
        raise HTTPException(400, "project_id must be a valid UUID")
    queue = _RUN_QUEUES.get(project_id)
    if queue is None:
        raise HTTPException(404, "no active generate run for this project; POST /generate first")

    async def gen() -> AsyncIterator[str]:
        while True:
            msg = await queue.get()
            if msg is None:
                break
            yield msg

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                                      "Connection": "keep-alive"})


__all__ = ["router"]
```

> **`run_pipeline` change required:** add an optional `cfg.on_stage: Callable[[str, str], None] | None = None` field on `RegionConfig`, then sprinkle `if cfg.on_stage: cfg.on_stage("voronoi", "start")` at the start of each numbered step in `services/pipeline/__init__.py`. The default `None` keeps Phase 01 parity untouched.

### Status manifest endpoint — D-21

```python
# backend/medieval_forge/api/v3/status.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models import Project
from ...services.paths import is_valid_uuid, project_dir

router = APIRouter(prefix="/v3/projects", tags=["v3-status"])

# 12 contract files; 10 produced by Phase 01 (terrain_lookup.png + terrain_types.json deferred to Phase 06).
ARTIFACT_FILES = [
    "lookup_barony.png", "lookup_condado.png",
    "lookup_barony_colors.json", "lookup_condado_colors.json",
    "territory_metadata.json",
    "visual_condado.png", "visual_barony.png",
    "mountains_mask.png", "rivers_overlay.png",
    "mountain_river_data.json",
    # Phase 06 owners (omit from has_artifacts in Phase 03):
    # "terrain_lookup.png", "terrain_types.json",
]


class StatusResponse(BaseModel):
    status: str
    has_artifacts: dict[str, bool]
    last_generated_at: str | None


@router.get("/{project_id}/status", response_model=StatusResponse)
async def get_status(project_id: str, db: AsyncSession = Depends(get_db)) -> StatusResponse:
    if not is_valid_uuid(project_id):
        raise HTTPException(400, "project_id must be a valid UUID")
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    out = project_dir(project_id) / "output"
    has = {f: (out / f).is_file() for f in ARTIFACT_FILES}
    return StatusResponse(
        status=project.status,
        has_artifacts=has,
        last_generated_at=project.updated_at.isoformat() if project.status == "generated" else None,
    )


__all__ = ["router"]
```

### Artifact serving endpoint — D-18

```python
# backend/medieval_forge/api/v3/artifacts.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ...services.paths import is_valid_uuid, project_dir

router = APIRouter(prefix="/v3/projects", tags=["v3-artifacts"])

# Allowlist mirrors ARTIFACT_FILES from status.py (single source of truth recommended:
# move to services/pipeline/contracts.py during planning).
_ALLOWED_FILES = {
    "lookup_barony.png", "lookup_condado.png",
    "lookup_barony_colors.json", "lookup_condado_colors.json",
    "territory_metadata.json",
    "visual_condado.png", "visual_barony.png",
    "mountains_mask.png", "rivers_overlay.png",
    "mountain_river_data.json",
    # Phase 02 ingestion sidecars (consumed by useCanvasArtifacts):
    "territories.geojson", "baronies.geojson",
    "condado_colors.json", "barony_colors.json",
}


@router.get("/{project_id}/artifacts/{file_name}")
async def serve_artifact(project_id: str, file_name: str) -> FileResponse:
    if not is_valid_uuid(project_id):
        raise HTTPException(400, "project_id must be a valid UUID")
    if file_name not in _ALLOWED_FILES:
        raise HTTPException(404, f"file '{file_name}' is not a serveable artifact")

    root = project_dir(project_id)  # raises ValueError if escapes PROJECTS_ROOT — safe
    target = (root / "output" / file_name).resolve()
    # Defense-in-depth: ensure target is still inside the project's output dir
    if not str(target).startswith(str((root / "output").resolve())):
        raise HTTPException(404, "file not found")
    if not target.is_file():
        raise HTTPException(404, f"artifact '{file_name}' not generated yet")
    # Native HTTP cache; ?v={updated_at} on the URL is what makes regen invalidate.
    return FileResponse(target, headers={"Cache-Control": "public, max-age=31536000, immutable"})


__all__ = ["router"]
```

> The `Cache-Control: immutable` directive is safe because the `?v={updated_at}` query string makes every regenerated set of artifacts a new URL. Browsers + intermediate caches treat the URL as immutable and never revalidate `[CITED: web.dev — A Practical Guide to FastAPI Security]`.

### `useCanvasArtifacts` URL switch (the only line-level change)

```ts
// frontend/src/hooks/useCanvasArtifacts.ts — change the prefix in 5 places.
// BEFORE: `/api/projects/${projectId}/preview/territories.geojson${v}`
// AFTER:  `/api/v3/projects/${projectId}/artifacts/territories.geojson${v}`
//
// All 5 URL templates change identically. No other behavior changes —
// data shapes, queryKeys (still keyed by [name, projectId, cacheVersion]),
// and select() transforms are unchanged. Existing tests update fetch mocks
// in lock-step.
```

### `useRunStore` skeleton

```ts
// frontend/src/stores/useRunStore.ts
import { create } from 'zustand'

export type RunState = 'idle' | 'ingesting' | 'generating' | 'generated' | 'error'

const PIPELINE_STAGES = [
  'landmask', 'border', 'voronoi', 'cleanup', 'smooth', 'merge',
  'hierarchy', 'render', 'lookup', 'metadata', 'export',
] as const
export type PipelineStage = typeof PIPELINE_STAGES[number]

interface RunStoreState {
  state: RunState
  runId: string | null
  currentStage: PipelineStage | null
  completedStages: PipelineStage[]
  logLines: string[]
  errorMessage: string | null
  errorStage: PipelineStage | null

  start: (runId: string, kind: 'ingesting' | 'generating') => void
  appendLog: (line: string) => void
  startStage: (stage: PipelineStage) => void
  finishStage: (stage: PipelineStage) => void
  finish: (state: 'generated' | 'error', errorMessage?: string, errorStage?: PipelineStage) => void
  reset: () => void
}

const LOG_CAP = 500

export const useRunStore = create<RunStoreState>((set) => ({
  state: 'idle', runId: null, currentStage: null, completedStages: [],
  logLines: [], errorMessage: null, errorStage: null,

  start: (runId, kind) => set({
    state: kind, runId, currentStage: null, completedStages: [], logLines: [],
    errorMessage: null, errorStage: null,
  }),

  appendLog: (line) => set((s) => ({
    logLines: [...s.logLines, line].slice(-LOG_CAP),
  })),

  startStage: (stage) => set({ currentStage: stage }),

  finishStage: (stage) => set((s) => ({
    completedStages: s.completedStages.includes(stage) ? s.completedStages : [...s.completedStages, stage],
    currentStage: null,
  })),

  finish: (state, errorMessage, errorStage) => set({
    state, errorMessage: errorMessage ?? null, errorStage: errorStage ?? null,
  }),

  reset: () => set({
    state: 'idle', runId: null, currentStage: null, completedStages: [],
    logLines: [], errorMessage: null, errorStage: null,
  }),
}))

export { PIPELINE_STAGES }
```

### `InteractionLayer` multi-select extension

```tsx
// frontend/src/components/canvas/InteractionLayer.tsx
import { Layer, Line } from 'react-konva'
import { useUIStore } from '../../stores/uiStore'
import type { TerritoryRender } from '../../hooks/useCanvasArtifacts'

interface Props { territories: TerritoryRender[] }

export function InteractionLayer({ territories }: Props) {
  const selectedIds = useUIStore((s) => s.selectedTerritoryIds)
  const idsSet = new Set(selectedIds)
  const selectedPolygons = territories.filter((t) => idsSet.has(t.id))

  return (
    <Layer listening={false}>
      {selectedPolygons.map((t, i) => (
        <Line key={`${t.id}-${i}`} points={t.points} closed
              stroke="#f0c040" strokeWidth={3} listening={false} />
      ))}
    </Layer>
  )
}
```

---

## State of the Art

| Old Approach (v1 stepper) | Current Approach (v3 read-only) | When Changed | Impact |
|--------------------------|--------------------------------|--------------|--------|
| 5-step Stepper UI driving ingest+research+map+codex+export | Single-canvas Mapbox-like workspace; one CTA | Phase 03 (this) | -697 LOC ProjectDetail; +~250 LOC across 6 new components |
| LLM mandatory before generate | LLM opt-in metadata sidecar (deferred) | Phase 03 deletes v1 LLM stack outright | -~3000 LOC deletion; Phase 07 rewrites from scratch |
| `/api/projects/{id}/preview/*` v1 URL | `/api/v3/projects/{id}/artifacts/*` | Phase 03 | URL prefix swap in `useCanvasArtifacts`; native HTTP cache |
| Compound undo for territory edit | No undo (read-only) | Phase 03 | -`useUndoShortcut`, -`zundo temporal` use; Phase 04 reintroduces for sliders |
| `usePipelineStore` orchestrating step state | `useRunStore` for SSE run state machine | Phase 03 | Simpler state — no per-step provider/effort/status fields |
| `useEditorStore.rubberBandSelectionIds: string[]` | `useUIStore.selectedTerritoryIds: string[]` | Phase 03 | One store owns selection; rubber-band UX gone |
| `services/ingest_runner.py` `_write_geojson_atomic` | `services/paths.py` `_write_geojson_atomic` | Phase 03 Wave 0 | Lift required to gate D-12 deletion |

**Deprecated/outdated:**
- v1 Stepper UI (697-line ProjectDetail) — explicit anti-target per CLAUDE.md.
- LLM credentials persisted in SQLite — table goes orphan; safe to ignore.
- `usePipelineStore`, `useResearchStore`, `useEditorStore`, `useValidationStore`, `useProjectStore` — all delete.
- `services/llm/` subpackage (8+ provider files) — Phase 07 rewrites from scratch.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | New `useRunStore` Zustand store is preferred over derived TanStack Query state | §Standard Stack §Alternatives Considered + §Architecture Patterns Pattern 4 | Wrong choice forces a refactor in Phase 04. Mitigation: store boundary is small (~80 LOC); refactor is cheap. |
| A2 | Structured SSE envelope `{event_type, stage, message, progress?}` (vs Phase 02 plain text) is the right choice | §Architecture Patterns Pattern 5 | Wrong choice forces frontend log-line regex parsing. Mitigation: envelope is one helper function; can revert to plain text in a Wave 1 task. |
| A3 | Adding `cfg.on_stage` callback to `RegionConfig` is parity-safe | §Code Examples §Generate endpoint | Wrong → Phase 01 parity 10/10 breaks. Mitigation: default `None` keeps existing behavior; add a unit test that confirms `cfg.on_stage = None` changes nothing. |
| A4 | `Project.generator_config` is v1-only and can be ignored in Phase 03 | §Runtime State Inventory + §Don't Hand-Roll | Wrong if a v3 surface reads it later. Mitigation: planner audits during Wave 0 and either documents it or sets to `None` on /generate. |
| A5 | Deleting `models.LLMCredential` / `models.ResearchCache` / `models.CodexCache` from `models.py` doesn't break existing local DBs | §Don't Hand-Roll §LLM consumer graph | `Base.metadata.create_all` no-ops on missing classes. ORM tables are orphan but harmless in user-local SQLite. Mitigation: ship optional Alembic 0004 drop migration if a user reports concern. |
| A6 | `api/export.py` survives unchanged for the Toolbar "Exportar ZIP" button | §Architecture Patterns §Project Structure note | If `/api/projects/{id}/export` v1 endpoint reads from `projects/{id}/raw/` (v1 layout) instead of `projects/{id}/output/` (v3), the button 404s. Mitigation: planning-task audit during Wave 0 (one grep). |
| A7 | Two callsites of `_write_geojson_atomic` outside Phase 02 (`ingest_terrain/runner.py` is the survivor) — confirmed by grep | §Common Pitfalls Pitfall 2 | Wrong → fewer tasks needed (smaller win). Mitigation: planner re-greps to confirm. |
| A8 | UI-SPEC's "1 px hover outline + tooltip" can share `InteractionLayer` (gold 3 px) without visual conflict | §Architecture Patterns Pattern 6 | If gold-on-grey looks awful, separate hover layer needed (1 extra Konva Layer; cheap). Mitigation: design call during planning, not blocking research. |

If this table is empty: all claims in this research were verified or cited — no user confirmation needed.

---

## Open Questions

1. **Does `/api/projects/{id}/export` (v1) read from the new `projects/{id}/output/` layout?**
   - What we know: UI-SPEC mentions a working "Exportar ZIP" button on the toolbar. CONTEXT does not delete `api/export.py`.
   - What's unclear: whether the v1 export endpoint hard-codes the v1 path layout (`projects/{id}/raw/...`) or already reads from a configurable `output_dir`.
   - Recommendation: planning-task Wave 0 grep `api/export.py` for path constants. If v1-coupled, ship a v3 wrapper `api/v3/export.py` (~30 LOC, FileResponse on a ZIP built from `output/`). Phase-01 already produces the 12 files; ZIP'ing is trivial.

2. **Should we ship the optional Alembic 0004 migration to drop orphan `llm_credentials` / `research_cache` / `codex_cache` tables?**
   - What we know: Tables are harmless after their consumer code is gone. v3 is local single-user.
   - What's unclear: whether downstream Phase 06 export-gate validation has any opinion on schema cleanliness.
   - Recommendation: defer to Phase 06 unless a user reports the orphan tables. Karpathy: don't build for hypothetical use.

3. **`services/territories_geojson.py`, `services/voronoi.py`, `services/baronies_builder.py`, `services/render_modern.py`, `services/project_meta.py`, `services/territory_builder.py` — are any of them imported by surviving code?**
   - What we know: They're v1-stack leftovers; their main consumers (`api/generate.py`, `api/edit.py`) are deleted.
   - What's unclear: whether `api/projects.py:territory_template` (line 35-47) reads `services/territory_iberia.json` — needs a grep audit.
   - Recommendation: Wave 0 grep + audit. Likely all delete, but confirm before shipping.

4. **Should `RegionConfig.on_stage` ship in Phase 03 or be skipped (heartbeat-only Phase 03, real per-stage events Phase 04)?**
   - What we know: D-03 explicitly demands per-stage checkmarks; heartbeat-only doesn't satisfy it.
   - What's unclear: is the planner okay editing `services/pipeline/__init__.py` for stage hooks while staying parity-safe?
   - Recommendation: ship `on_stage` (Pattern 5 + A3). Add one parity unit test that `cfg.on_stage = None` produces byte-identical output to the existing parity baseline.

---

## Environment Availability

> Phase 03 runs entirely against tools already in `pyproject.toml` + `package.json`. No new external services.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| FastAPI | New v3 endpoints | ✓ (already installed) | (existing) | — |
| `asyncio` | SSE producer/consumer | ✓ (Python stdlib) | 3.11+ | — |
| `uuid` | Run-id generation | ✓ (Python stdlib) | 3.11+ | — |
| Konva 10.2.5 + react-konva 19.2.3 | Read-only canvas | ✓ | 10.2.5 / 19.2.3 | — |
| Radix UI Themes 3.3.0 | Workspace shell | ✓ | 3.3.0 | — |
| Zustand 5.0.12 | `useRunStore` + `useUIStore` mods | ✓ | 5.0.12 | — |
| TanStack Query 5.99 | Status + artifacts polling | ✓ | 5.99.0 | — |
| Playwright 1.59 | UAT smoke | ✓ | 1.59.1 | — |
| Vitest 3.2.4 | Frontend unit | ✓ | 3.2.4 | — |
| pytest + pytest-asyncio | Backend unit + parity | ✓ (existing) | (existing) | — |
| `D:\Projetos_Jogo\Reconquista\Assets\StreamingAssets\Maps\` | Phase 01 parity gate (must stay green) | ✓ | snapshotted in `tests/fixtures/iberia_868/golden/` | — (already in-repo) |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

**Note:** Phase 03 is deliberately a **zero-install phase**. CLAUDE.md tech stack is already locked; introducing new libraries is forbidden. If the planner identifies a need (e.g., an SSE client lib for the frontend), use plain `EventSource` from the Web Platform — it's the same API Phase 02's frontend used (now deleted, but the pattern survives in `useResearchStream.ts:1-40` for reference before deletion).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Backend framework | pytest + pytest-asyncio (existing) |
| Backend config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` (existing — `parity` + `unit` + `integration` markers registered) |
| Frontend framework | vitest 3.2.4 + Testing Library + jsdom (existing) |
| Frontend config file | `frontend/vite.config.ts` + `vitest.config.ts` (existing) |
| UAT framework | Playwright 1.59.1 (existing) |
| UAT config file | `frontend/playwright.config.ts` (assumed — confirm Wave 0) |
| Quick run command (backend unit) | `pytest backend/tests/unit/ -m unit -x` |
| Quick run command (frontend unit) | `cd frontend && npm test -- --run` |
| Full suite (backend) | `pytest backend/tests/ -m "unit or parity" --no-header -q` |
| Full suite (frontend) | `cd frontend && npm run build && npm test -- --run` |
| Phase parity gate | `pytest backend/tests/parity/test_iberia_868.py -m parity -q` (must be 10/10 green every commit) |
| Playwright UAT | `cd frontend && npx playwright test tests/uat/playwright/03-canvas-workspace.spec.ts` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| SC-1 | User pans/zooms/clicks territories on a Phase-01-generated project | UAT (Playwright) | `npx playwright test 03-canvas-workspace.spec.ts -g "pan zoom click"` | ❌ Wave 3 |
| SC-2 | Inspector populates on click; layer toggles update visibility | UAT + unit (vitest) | `npm test -- InspectorSidebar` + Playwright `-g "inspector populates"` | ⚠️ partial — `InspectorSidebar.test.tsx` exists; new Playwright case Wave 3 |
| SC-3 | No console errors; old stepper invisible | UAT (Playwright) | `npx playwright test -g "no console errors"` (assert `page.on('pageerror')` count == 0) | ❌ Wave 3 |
| SC-4 | Runs against Phase 01 artifacts directly | parity (pytest) | `pytest backend/tests/parity/test_iberia_868.py` (must stay 10/10 GREEN every commit) | ✅ Phase 01 owns |
| D-22 (POST /generate) | 202 + run_id; status flips generating | unit (pytest) | `pytest backend/tests/unit/api/test_v3_generate.py` | ❌ Wave 1 |
| D-22 (GET /generate/stream) | SSE stream emits start + 11 stages + done | unit (pytest) | `pytest backend/tests/unit/api/test_v3_generate_stream.py` | ❌ Wave 1 |
| D-22 (error path) | Pipeline raise → SSE error event + status `error_generating` | unit (pytest) | `pytest backend/tests/unit/api/test_v3_generate_stream.py::test_error_path` | ❌ Wave 1 |
| D-21 (GET /status) | Returns `{status, has_artifacts, last_generated_at}` | unit (pytest) | `pytest backend/tests/unit/api/test_v3_status.py` | ❌ Wave 1 |
| D-18 (artifact serving) | Path traversal rejected; allowlist enforced; 404 on missing; cache headers set | unit (pytest) | `pytest backend/tests/unit/api/test_v3_artifacts.py` | ❌ Wave 1 |
| D-17 (multi-select) | shift-click toggles; aggregate inspector renders | unit (vitest) | `npm test -- MultiSelectInspector` | ❌ Wave 1 |
| D-15 (hover) | mouseover paints outline + tooltip | unit (vitest) | `npm test -- HoverTooltip` | ❌ Wave 1 |
| D-08 (error state) | Error callout + Retry button re-dispatches POST | unit (vitest) | `npm test -- ErrorCanvasCallout` | ❌ Wave 1 |
| `useRunStore` state machine | Transitions idle → ingesting → generating → generated/error | unit (vitest) | `npm test -- useRunStore` | ❌ Wave 1 |
| `useCanvasArtifacts` URL switch | All 5 fetches go to `/api/v3/projects/.../artifacts/` | unit (vitest) | `npm test -- useCanvasArtifacts` | ⚠️ exists; update Wave 1 |
| Wave 0: `_write_geojson_atomic` lift | Lifted symbol callable from `paths` | unit (pytest) | `pytest backend/tests/unit/test_paths.py::test_write_geojson_atomic` | ❌ Wave 0 |
| Wave 0: `cfg.on_stage = None` parity-safe | Phase 01 parity 10/10 stays green with explicit None | parity (pytest) | `pytest backend/tests/parity/test_iberia_868.py -k "on_stage"` (new test) | ❌ Wave 0 |
| LayerTogglePanel terrain-row removal | `'terrain'` no longer rendered | unit (vitest) | `npm test -- LayerTogglePanel` (update existing) | ⚠️ exists; update Wave 1 |

### Sampling Rate

- **Per task commit:** quick backend unit (`pytest backend/tests/unit/ -m unit -x`) + quick frontend unit (`npm test -- --run --watch=false [touched_file]`).
- **Per wave merge:** full backend `pytest -m "unit or parity"` + full frontend `npm test`.
- **Phase gate:** full suite green + Playwright UAT green + Phase 01 parity 10/10 green BEFORE `/gsd-verify-work`.

### Wave 0 Gaps

- [ ] `backend/tests/unit/test_paths.py::test_write_geojson_atomic` — covers the lift refactor.
- [ ] `backend/tests/parity/test_iberia_868.py::test_on_stage_none_is_parity_safe` — adds A3 mitigation.
- [ ] `backend/tests/unit/api/test_v3_generate.py` + `test_v3_generate_stream.py` + `test_v3_status.py` + `test_v3_artifacts.py` — new endpoints.
- [ ] `frontend/src/stores/__tests__/useRunStore.test.ts` — new state machine.
- [ ] `frontend/src/components/canvas/__tests__/MultiSelectInspector.test.tsx` — new aggregate view.
- [ ] `frontend/src/components/canvas/__tests__/HoverTooltip.test.tsx` — new hover overlay.
- [ ] `frontend/src/components/workspace/__tests__/WorkspaceToolbar.test.tsx` — new toolbar.
- [ ] `frontend/src/components/workspace/__tests__/RunLogPanel.test.tsx` — new log panel.
- [ ] `frontend/src/components/workspace/__tests__/EmptyCanvasState.test.tsx` — new empty state.
- [ ] `frontend/src/components/workspace/__tests__/GeneratingCanvasState.test.tsx` — new generating state.
- [ ] `frontend/src/components/workspace/__tests__/ErrorCanvasCallout.test.tsx` — new error state.
- [ ] `frontend/src/components/workspace/__tests__/GenerateStatusBadge.test.tsx` — new status badge.
- [ ] `frontend/tests/uat/playwright/03-canvas-workspace.spec.ts` — single-scenario E2E (open project → click Generate → wait done → click territory → inspector populates → toggle layer → verify SC-1..4).
- [ ] Update `frontend/src/components/canvas/__tests__/CanvasViewer.test.tsx` (+ `hydrate`, `resize`, `panOnSelect`) — URL prefix swap mocks.
- [ ] Update `frontend/src/hooks/useCanvasArtifacts.cacheVersion.test.ts` — URL prefix swap.
- [ ] Update `frontend/src/components/canvas/__tests__/LayerTogglePanel.test.tsx` — terrain row removed.

### Wave/Dependency Plan

The advisor's sketch confirmed by §Common Pitfalls and §Don't Hand-Roll graph analysis:

**Wave 0 — pre-flight refactors (gates everything else):**
1. Lift `_write_geojson_atomic` → `services/paths.py`. Update `services/pipeline/adapters/base.py` + `services/ingest_terrain/runner.py` (3 callsites).
2. Add `cfg.on_stage: Callable[[str, str], None] | None = None` to `RegionConfig`. Sprinkle hook calls in `services/pipeline/__init__.py` Steps 3-12. Add parity unit test.
3. Audit `Project.generator_config` consumers (Open Q1).
4. Audit `services/{territories_geojson, voronoi, baronies_builder, render_modern, project_meta, territory_builder}.py` consumers (Open Q3) — set delete list.
5. Audit `api/export.py` path layout (Open Q1) — decide v3 wrapper vs reuse.
6. Decide `api/auth.py` + `services/credential_store.py` + ORM cleanup tasks (D-13 audit).

**Wave 1 — backend endpoints || frontend rewrite (run in parallel):**
- Backend track: `api/v3/{generate,status,artifacts}.py` + register in `main.py` + 4 unit test files.
- Frontend track A (rewrite): `pages/ProjectDetail.tsx` + `components/workspace/*` + `useRunStore` + URL switch in `useCanvasArtifacts`.
- Frontend track B (canvas mods): strip `CanvasViewer.tsx` + `TerritoryLayer.tsx`; extend `InteractionLayer.tsx`; add `HoverTooltip.tsx` + `MultiSelectInspector.tsx`; modify `useUIStore`.

**Wave 2 — v1 deletes (gated on Wave 1 green):**
- Frontend deletes (D-10/D-11/D-13) — components, stores, hooks, api modules, services.
- Backend deletes (D-12/D-13) — api modules + services + LLM subpkg + tests + lifespan body shrink + models shrink.
- Pre-merge: run §Common Pitfalls Pitfall 1 grep checklist; expect zero hits.

**Wave 3 — UAT + final parity:**
- Playwright spec.
- Final parity test run.
- `/gsd-verify-work` invocation.

---

## Security Domain

`security_enforcement` is enabled by default (config absent → enabled). Phase 03 stack is FastAPI backend + React/Konva frontend; ASVS L1 applies.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (D-20 — local-only) | — |
| V3 Session Management | no | — |
| V4 Access Control | no (single-user local tool) | — |
| V5 Input Validation | yes | UUID regex + filename allowlist (existing `paths.is_valid_uuid` + new `_ALLOWED_FILES` set) |
| V6 Cryptography | no (no secrets in v3 after D-13) | — |
| V12 File / Resource | yes | Path containment check via `project_dir().resolve()` + `is_relative_to` (existing) |
| V13 API + Web Service | yes | Pydantic response models + 4xx error categories |

### Known Threat Patterns for FastAPI + per-project file serving

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via `project_id` segment in `/artifacts/` URL | Tampering / IDOR | `is_valid_uuid(project_id)` + `project_dir(project_id)` (already raises on escape `[VERIFIED: services/paths.py:46-49]`) |
| Path traversal via filename | Tampering | Filename **allowlist** `_ALLOWED_FILES` (Code Examples §artifacts.py); never accept arbitrary `{file_path:path}` |
| Symlink escape from `output/` | Tampering | `target.resolve()` + `str(target).startswith(str(output_dir.resolve()))` defense-in-depth (Code Examples §artifacts.py) |
| SSE channel hijack (cross-tab) | Information Disclosure | Local-only (D-20) — no auth needed; SSE is plaintext over loopback |
| `/generate` DoS via repeated POST | DoS | 409 if already generating (Code Examples §generate.py) — pipeline runs ~10 s, single-user tool |
| Stale credentials post-D-13 | Information Disclosure | Audit conclusion: DELETE `api/auth.py` + `credential_store.py` + `LLMCredential` model + persistent table. User can `DELETE FROM llm_credentials` if paranoid (documented in release notes). |
| `Cache-Control: immutable` cache poisoning | Tampering | Safe because `?v={updated_at}` URL changes per regen → never serve a different file at the same URL |
| run_pipeline thread blocks event loop | DoS | `asyncio.to_thread(run_pipeline, cfg)` (Code Examples §generate.py) — runs on thread pool, doesn't block FastAPI workers |
| SSE error message leaks stack traces | Information Disclosure | Phase 02 T-02-04-05 mitigation reused: only emit `exc.__class__.__name__` in SSE; full repr to logger only |

---

## Sources

### Primary (HIGH confidence)

- `.planning/phases/03-read-only-canvas-redesign/03-CONTEXT.md` — D-01..D-23 verbatim source (read).
- `.planning/phases/03-read-only-canvas-redesign/03-UI-SPEC.md` — visual + interaction contract (read).
- `.planning/phases/03-read-only-canvas-redesign/03-DISCUSSION-LOG.md` — alternatives considered (read).
- `backend/medieval_forge/api/v3/ingest.py` — concrete Phase 02 SSE template (read; `_v3_sse_generator` + `_adapter_producer` shape).
- `backend/medieval_forge/services/pipeline/__init__.py` — `run_pipeline(cfg)` entry point + 14 numbered steps (read).
- `backend/medieval_forge/services/pipeline/contracts.py` — `RegionConfig` dataclass (read; verifies `cfg.on_stage` extension feasibility).
- `backend/medieval_forge/services/paths.py` — `is_valid_uuid` + `project_dir` (read; verified path containment).
- `backend/medieval_forge/main.py` — router registration + lifespan body (read; verified shrink scope).
- `backend/medieval_forge/api/auth.py` + `services/credential_store.py` + `models.py` — D-13 audit evidence (read).
- `frontend/src/components/canvas/{CanvasViewer,InteractionLayer,InspectorSidebar,LayerTogglePanel,TerritoryLayer}.tsx` — read for strip vs extend planning.
- `frontend/src/hooks/useCanvasArtifacts.ts` — URL switch scope (read; 5 URL templates).
- `frontend/src/pages/ProjectDetail.tsx` — 697-line v1 stepper (read; rewrite scope).
- `frontend/src/stores/uiStore.ts` — `selectedTerritoryId` → `selectedTerritoryIds` migration source (read).
- `frontend/package.json` — verified library versions; no installs needed (read).
- `.planning/phases/02-ingestion-adapter/02-VERIFICATION.md` — parity 10/10 must stay green (read).
- `CLAUDE.md` — v3 contract + non-negotiables (read).
- `grep` results across `backend/` and `frontend/` for: `_write_geojson_atomic` (3 callsites), `LLMCredential` (5 sites in credential_store + models), `useResearchStore`/`useEditorStore`/etc. (41 frontend files in delete graph).

### Secondary (MEDIUM confidence)

- `[CITED: fastapi.tiangolo.com/reference/staticfiles/]` (WebSearch) — confirms StaticFiles fixed-prefix mount semantics; cannot URL-rewrite `{id}/artifacts/*` → disk `{id}/output/*`.
- `[CITED: fastapi.tiangolo.com — A Practical Guide to FastAPI Security]` (WebSearch via davidmuraya.com/blog/fastapi-security-guide/) — FileResponse + path validation is the recommended pattern for user-scoped per-project files.
- `[CITED: konvajs.org/api/Konva.Node.html]` (WebSearch) — `getPointerPosition()` returns coords relative to top-left of Stage's container DOM.
- `[CITED: konvajs.org/docs/sandbox/Relative_Pointer_Position.html]` (WebSearch) — `getRelativePointerPosition()` accounts for stage transforms; wrong primitive for DOM tooltip overlay.

### Tertiary (LOW confidence)

- None. All claims trace to either intra-repo grep evidence or to a webfetched FastAPI/Konva doc.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every version confirmed by `package.json` + `pyproject.toml`; no installs.
- Architecture: HIGH — all 6 patterns either reuse Phase 02 (SSE) or have a verified primary source (FastAPI FileResponse, Konva pointer methods).
- Pitfalls: HIGH — Pitfalls 1, 2, 6, 8 are intra-repo grep evidence; Pitfall 3 is advisor-flagged + WebSearch-confirmed; Pitfalls 4, 5 are v1-archive proven patterns.
- Test architecture: HIGH — vitest + pytest + Playwright are existing infra; Wave 0/1/2/3 ordering is gated by §Common Pitfalls.
- Security: HIGH — leverage existing `paths.is_valid_uuid` + `project_dir`; ASVS L1 reasoning is shallow on purpose for a local single-user tool.

**Research date:** 2026-05-09
**Valid until:** 2026-06-09 (30 days — stack is stable; CLAUDE.md locked)

---

## RESEARCH COMPLETE
