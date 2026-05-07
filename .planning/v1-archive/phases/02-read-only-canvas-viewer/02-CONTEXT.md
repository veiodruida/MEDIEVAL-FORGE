# Phase 2: Read-Only Canvas Viewer - Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 adds a Konva-based read-only canvas to the project detail route (`/projects/:id`). The user can pan/zoom the generated map, click any territory to inspect its properties, and toggle five layers (terrain, territories, borders, capitals, labels). No editing primitives (drag, paint, merge, split) land here — those are Phase 4/5. The canvas consumes artifacts already produced by Phase 1 (GeoJSON in `raw/`, generator PNG outputs in `generated/`, color lookup JSONs) and does not run any geometry regeneration.

</domain>

<decisions>
## Implementation Decisions

### Visual Style & Color Coding
- **D-01:** Territory fill colors are read from `lookup_condado_colors.json` and `lookup_barony_colors.json` (produced by `map_generator.py` in Phase 1). The canvas never generates its own palette — guarantees pixel-parity with the PNG previews so there is no drift between Konva render and exported Unity assets.
- **D-02:** Condados are the primary fill level by default. Baronies render only when their layer toggle is ON (stacked above condados at reduced opacity or via thinner internal borders — planner's call within this constraint).
- **D-03:** Selection highlight is a thicker bright-stroke border (2–3 px gold/yellow) drawn on top of the existing fill. The selected territory's fill color stays unchanged so hierarchy context remains readable at all zoom levels. No dimming of non-selected polygons.
- **D-04:** Capitals render as filled circles (6–8 px) using the owning territory's color, with a white/dark ring outline for contrast against both light and dark backgrounds. No SVG icons, no persistent city-name text (labels are separate layer).

### Inspector Panel Layout & Content
- **D-05:** The inspector is a **fixed, always-visible right sidebar** (320–360 px wide) on `/projects/:id`. No drawer animations, no floating popover. Canvas area fills the remaining viewport width.
- **D-06:** When a territory is selected, the inspector shows **all four property groups**:
  1. **Core identity** — name, hierarchy level (kingdom / duchy / condado / barony), full parent path (e.g., `León › Galicia › Coruña`)
  2. **Geometry stats** — approximate area in km², polygon vertex count, centroid (lat / lng)
  3. **Capital info** — capital city name + lat/lng, or `"No capital"` placeholder when missing (this placeholder anticipates VALIDATE-03 in Phase 6)
  4. **Neighbors list** — adjacent territories as clickable chips; clicking a chip selects that neighbor and updates the inspector
- **D-07:** When nothing is selected, the inspector shows a **project summary**: project name, country, period, and hierarchy totals (N kingdoms / M duchies / K condados / L baronies). Layer toggles are NOT merged into the inspector.

### Layer Toggle UX & Label Behavior
- **D-08:** Layer toggles live in a **floating Radix Card pinned to the top-left corner of the canvas**, overlaid with a subtle shadow. Five checkboxes in fixed order: Terrain, Territories, Borders, Capitals, Labels.
- **D-09:** Default layer state on first open: **Terrain + Territories + Borders + Capitals = ON; Labels = OFF.** Prevents label collisions on the initial fit-to-view.
- **D-10:** Labels appear via a **single hard zoom threshold** (all condado labels show together once `scale >= threshold`, e.g. ~1.5x — exact value chosen by the planner based on Iberia fit-to-view math). No hierarchy tiering, no per-polygon-size smart filtering.
- **D-11:** Label text shows the **territory name only** (e.g. `Coruña`). No hierarchy suffix, no capital city concatenation. Text should fit inside polygons; planner chooses font-size and anti-collision approach.

### Navigation & Viewport Behavior
- **D-12:** On project open, the canvas **auto-fits the territory bounding box to the viewport with small padding** (~5%). No persistence of last viewport per project in Phase 2 (can be added in a later phase if users ask for it).
- **D-13:** Zoom limits: **min = fit-to-view scale** (user cannot zoom out past whole-map view), **max = 4× native**. Pan is **clamped to map bounds** so the map cannot leave the viewport interior — no "lost in empty space" state.
- **D-14:** Phase 2 ships **two keyboard shortcuts only**: `Esc` = deselect current territory, `Ctrl+0` = fit-to-view. A "Fit to view" button is also present in the UI (success criterion 5 requires the button). All other shortcuts (zoom keys, arrow-key pan, Ctrl+Z/Y) are **deferred to Phase 4** to avoid collision with editing shortcuts.
- **D-15:** Wheel zoom **anchors on the mouse cursor position** (standard map UX). Each wheel event transforms the cursor position through the current projection so the geographic point under the cursor stays under the cursor after zoom.

### Claude's Discretion
- Exact threshold value for the label zoom cutoff (D-10) — derive from the Iberia test dataset
- Exact zoom-in max multiplier (nominally 4×, can be tuned to 3–6×) and fit-to-view padding percentage
- Font family and font-size for labels; anti-collision strategy (first-come-first-rendered, clip-by-polygon, or none if label budget allows)
- Baronies rendering style when their toggle is ON (overlay at reduced opacity vs. thinner internal borders vs. replace condados)
- Right-sidebar exact width within the 320–360 px band; collapse behavior for narrow viewports (desktop-only target — ignore mobile)
- `react-konva`/`konva` exact version pin within the 19.x line noted in CLAUDE.md; `--legacy-peer-deps` usage
- Internal layer architecture of the Konva Stage (3 layers as roadmap hints, or 4–5 if needed for perf — planner investigates via research)
- GeoJSON loading/caching pattern (TanStack Query config, error-on-missing handling)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & Requirements
- `.planning/ROADMAP.md` Phase 2 section — goal, plans (2.1/2.2/2.3), UI hint flag, success criteria
- `.planning/REQUIREMENTS.md` — CANVAS-01..06 requirement IDs
- `.planning/PROJECT.md` Constraints section — stack, state management (Zustand + zundo), styling, performance targets

### Stack & Constraints (from CLAUDE.md)
- `CLAUDE.md` Technology Stack section — React 19 + react-konva 19.2.x, Vite 6, Tailwind v4 CSS-first + `@tailwindcss/vite`, Radix UI Themes (watch transparency bug #17137), TanStack Query v5
- `CLAUDE.md` Potential Issues §1 — react-konva peer-dep note (React 19 already chosen in Phase 1)
- `CLAUDE.md` Potential Issues §3 — Radix UI CSS must import before `@import "tailwindcss"` in `frontend/src/index.css`

### Phase 1 Foundation (already built)
- `.planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md` — Phase 1 decisions: flat monorepo (`backend/` + `frontend/`), `~/.medieval-forge/projects/{uuid}/` layout, SPA routes `/projects`, `/projects/new`, `/projects/:id`
- `.planning/phases/01-data-pipeline-backend-scaffold/01-SUMMARY.md` (via linked per-plan summaries) — what actually shipped for Phase 1; reuse existing TanStack Query setup, Radix theming, and project detail route shell

### Reference Data & Lookup Files (consumed by canvas)
- `inicio/territory_data_v3.py` — hierarchy structure reference (kingdoms → duchies → condados → baronies) for Iberia 868 AD test dataset
- Per-project artifacts produced by `map_generator.py` in the project folder:
  - `generated/terrain.png` — Konva Image on background layer
  - `generated/territories.png`, `generated/borders.png` — visual references (not necessarily rendered directly; polygons come from GeoJSON)
  - `lookup_condado_colors.json`, `lookup_barony_colors.json` — fill colors (D-01)
  - `raw/municipalities.geojson` (source) and the generator's output GeoJSON if emitted — polygon geometry for Konva Line/Polygon nodes
  - `territory_metadata.json` — hierarchy + capital + centroid metadata for inspector (D-06)

### STATE.md flagged concerns for Phase 2
- Tailwind v4 + Radix UI transparency bug (#17137) — plan a UI component smoke test early in this phase (inspector sidebar + floating card panel + checkboxes are Radix-heavy)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (from Phase 1)
- React 19 + Vite 6 app at `frontend/` with Tailwind v4 (`@tailwindcss/vite`) and Radix Themes already configured
- `/projects/:id` route and project detail page — canvas mounts inside this page (sidebar + canvas area layout to be added)
- TanStack Query v5 already set up for backend calls (reuse for GeoJSON + metadata fetches)
- Backend serves project files through FastAPI static routes under the project UUID; GeoJSON, PNGs, and lookup JSONs are already reachable

### Dependencies To Add in Phase 2
- `konva` (9.x core) + `react-konva` (19.2.x) — not yet in `frontend/package.json`
- No new backend deps (canvas is purely frontend; backend endpoints from Phase 1 already expose the needed project artifacts)

### Established Patterns to Follow
- Per Phase 1 D-08: routes add incrementally — Phase 2 does NOT add placeholder routes for edit/research; it extends the existing `/projects/:id` view
- Per Phase 1 D-02: Vite `outDir` is `../backend/medieval_forge/static/` — canvas code ships inside that build, no separate deploy
- Zustand is the state pattern; zundo middleware is wired but unused in read-only Phase 2 (first real use is Phase 4)

### Integration Points
- Canvas view becomes the main content region of `/projects/:id`; project manager CRUD (already done) sits above / in app shell
- Selection state lives in a Zustand slice; inspector + canvas both subscribe to it
- Fit-to-view button lives in the floating layer card header OR the top-left of the canvas (planner's call) so success criterion 5 is visible

</code_context>

<specifics>
## Specific Ideas

- Test dataset for all visual tuning: Iberia 868 AD, ~91 condados — matches `territory_data_v3.py` and the Phase 1 generator fixture.
- Selection flow to validate during UAT: click territory → bright border appears → inspector fills all 4 property groups → click neighbor chip → selection moves → `Esc` clears selection → inspector shows project summary.
- Early smoke test: mount an empty Konva Stage inside a Radix-themed page with a Radix Card overlay to confirm the Tailwind v4 + Radix transparency bug (#17137) is not biting before sinking plan-work into it.
- Zoom anchor-on-cursor math reference: standard Konva recipe — `newPos = cursorPos - (cursorPos - oldPos) * (newScale / oldScale)`; planner should confirm against Konva 9.x docs.
- Clamp logic for pan bounds: compute `viewport - scaled_map_bounds` each frame; prevent translation past edges.

</specifics>

<deferred>
## Deferred Ideas

- **Persist last viewport per project** — deferred (Phase 2 always auto-fits on open). Reconsider if users complain about losing zoom after navigation.
- **Full keyboard navigation set** (Ctrl+/- zoom, arrow-key pan) — deferred to Phase 4 so it can be designed alongside edit shortcuts (Ctrl+Z/Y) without collisions.
- **Multi-select** — out of scope for read-only viewer; revisit when merge/split editing lands in Phase 4.
- **Minimap** — v2 Requirement per REQUIREMENTS.md; not a Phase 2 concern.
- **Tiered label zoom (kingdoms early, baronies late)** and **smart-by-polygon-size label filtering** — considered and rejected in favor of single hard threshold (D-10). Can revisit if label clutter is a real problem at UAT.
- **Crown/star capital icons** — considered and rejected for simple dot+ring (D-04). Could revisit in a future UI polish phase.
- **Mobile/small-screen responsive layout** — explicitly out of scope; tool is desktop-only per PROJECT.md Out of Scope.

</deferred>

---

*Phase: 02-read-only-canvas-viewer*
*Context gathered: 2026-04-17*
