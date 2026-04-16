# Project Research Summary

**Project:** Medieval Forge
**Domain:** Local web map generation tool -- historical strategy game asset pipeline
**Researched:** 2026-04-16
**Confidence:** MEDIUM-HIGH

---

## Executive Summary

Medieval Forge is a pip-installable local web tool built on a FastAPI + React/Konva stack that takes a country and historical period as input, ingests real geographic data from Wikidata/OSM, applies LLM-assisted historical research to build a political hierarchy, generates Voronoi-based territory maps, and exports a Unity-ready asset package. The architecture is conventional (React SPA served by FastAPI, SQLite persistence, scipy for geometry), and every major component has well-documented patterns in 2025-era sources. The tool differentiation is not technical novelty but the combination: no existing free tool does historically-grounded hierarchy research + real municipality shapes + automated Unity export in one pipeline.

The recommended stack is mostly correct as briefed, with four concrete corrections: Vite should be v6 (not v5, which is two majors behind), zundo is v2.3.0 (v3 does not exist on npm), react-konva 19.x targets React 19 (a peer-dep conflict if pinned to React 18), and rasterio 1.5+ requires Python 3.12 (pin to 1.4.x or bump Python). The architecture decisions are confirmed sound -- scipy full Voronoi recompute (~50ms for 500 points) is fast enough that true incremental mode is unnecessary; SSE over HTTP is the right transport for LLM streaming (not WebSocket); affine equirectangular projection is sufficient at country scale with no need for proj4js.

The highest-risk areas are the packaging seam (Vite build must be present in the wheel, base must be "./" not "/"), SQLite async transaction semantics (aiosqlite SAVEPOINT behavior is surprising and affects merge/split correctness), and zundo memory growth (full-state snapshots at 800 territories = 100-250MB -- partialize and diff options are required, not optional). Phase 1 must address all three of these before any canvas work begins; they are not solvable as retrofits.

---

## Key Findings

### Recommended Stack

See [STACK.md](./STACK.md) for the full version table and rationale.

The briefing stack is 80% correct. Key corrections from research:

**Core technologies:**
- **React 19 + react-konva 19.2.x**: react-konva versioning mirrors React major version. React 18 + react-konva 19.x requires `--legacy-peer-deps`. Greenfield choice: upgrade to React 19 (stable Dec 2024).
- **Vite 6** (not 5): Vite 5 is two majors behind. Vite 6 (Nov 2024) is well-settled; migration from 5 is smooth. Start on 6.
- **zundo 2.3.0** (not 3.x): zundo 3.x does not exist on npm. v2 is a complete API rewrite -- middleware is `temporal`, config uses `partialize`/`limit`/`handleSet`.
- **rasterio >=1.4,<1.5**: rasterio 1.5+ requires Python 3.12 and NumPy 2. If staying on Python 3.11 as briefed, pin rasterio to 1.4.x.
- **Tailwind CSS v4 + `@tailwindcss/vite` plugin**: v4 is correct but configuration is now CSS-first (`@theme` in CSS, no `tailwind.config.js`). Use the Vite plugin, not PostCSS. Known Radix UI transparency bug after v4 upgrade -- import Radix CSS before Tailwind `@import`.
- **FastAPI 0.115+ + SQLAlchemy async 2.0 + aiosqlite 0.21.x**: Fully supported. Critical: `expire_on_commit=False` on session factory; Alembic needs custom async `env.py`.
- **Anthropic SDK 0.94.1 + Ollama REST**: Both confirmed. Ollama: use `stream: false` + `format: "json"` for structured output; JSON mode does not enforce schema -- system prompt must specify structure.

### Expected Features

See [FEATURES.md](./FEATURES.md) for the full feature list with complexity estimates.

**Must have (table stakes) -- absence makes the tool feel broken:**
- Mouse-wheel zoom + click-drag pan
- Territory labels on canvas (toggle-able)
- Layer toggle panel (terrain, borders, hierarchy, labels)
- Undo/redo Ctrl+Z/Y -- 50 steps
- Territory properties panel (name, type, hierarchy)
- Minimap / overview navigator
- Fit-to-view / reset zoom button
- Export to PNG
- Project save/load (SQLite backend)

**Should have (competitive differentiators -- Medieval Forge moat):**
- LLM-assisted historical research (Claude + Ollama) -- unique positioning
- Wikidata/OSM ingestion for real municipality shapes
- Voronoi recalc scoped to affected neighbors (<500ms)
- Unity-ready ZIP export (12 files, lookup PNG + JSON metadata)
- Pre-export validation gate with specific errors (orphan baronies, dark pixels, missing capitals, small territories, hierarchy integrity)
- Merge/split territories with topology preservation
- Terrain paint with land mask awareness

**Defer to v2+:**
- Fantasy name/lore generation (not the positioning)
- Multi-user/cloud sync (out of scope per PROJECT.md)
- SVG export (not useful in the Unity pipeline)
- GPU/WebGL rendering (1000 Konva shapes hits 60fps without it)
- Direct Unity plugin (user copies files manually)

**Critical implementation note on undo granularity:** Moving a capital that triggers 6 neighbor Voronoi recalcs must register as ONE undo step, not 7. Semantic grouping in zundo via `handleSet` batching is required from day one of undo implementation.

### Architecture Approach

See [ARCHITECTURE.md](./ARCHITECTURE.md) for full component map, code patterns, and integration details.

The architecture is a standard thin-router / fat-service FastAPI monolith with a React SPA served from the same process. Three integration points need explicit attention in Phase 1:

1. **Vite to Python wheel:** `vite build` outputs to `src/medieval_forge/static/`. `pyproject.toml` must declare `medieval_forge = ["static/**/*"]` in `package-data`. Vite `base` must be `"./"` (relative). FastAPI serves the SPA via a catch-all route registered after all `/api` routes. Use `importlib.resources.files()` to locate the static dir -- works inside zip wheels; `__file__` does not.

2. **Geo to canvas projection:** Affine linear transform. One `ProjectionConfig` object (bbox + canvas dimensions) lives in a React context and is never recomputed on zoom -- Konva stage scale handles zoom. GeoJSON (lon/lat) is the canonical storage format; pixel coordinates are never written to the database.

3. **Voronoi:** scipy `Voronoi` runs a full recompute on all ~500 points (~50ms). Neighbor identification uses `ridge_points` to find adjacent cells. Only the ~5-10 affected polygons are returned to the frontend. The `incremental=True` scipy flag does not help for point-move operations (it is for adding new points only).

**Major components:**
1. `services/voronoi.py` -- full scipy recompute + neighbor filter, Shapely land-mask clip
2. `services/llm.py` -- Claude async streaming + Ollama adapter (unified interface)
3. `services/generator.py` -- thin wrapper around `vendor/map_generator.py`
4. `frontend/src/lib/projection.ts` -- `geoToCanvas` / `canvasToGeo` / `geoRingToKonvaPoints`
5. `frontend/src/store/` -- three Zustand slices: `useProjectStore` (zundo-tracked), `useEditorStore` (tool state, not tracked), `useUIStore` (panels, not tracked)

### Critical Pitfalls

See [PITFALLS.md](./PITFALLS.md) for the full list with prevention code.

**Phase 1 must resolve these before any canvas work:**

1. **Vite `base: "./"` required for pip packaging** -- Default `base: "/"` produces absolute asset URLs that break when FastAPI serves the app. Set in `vite.config.ts` at scaffold. Add CLI startup assertion: if `static/index.html` is missing, fail with a clear message.

2. **aiosqlite SAVEPOINT semantics break merge/split** -- `session.begin_nested()` inside `async with session.begin()` may silently not create the savepoint due to deferred BEGIN emission. Use a single top-level transaction and application-level rollback logic for merge/split. Set `isolation_level = None` on the DBAPI connection and emit BEGIN explicitly via event listener.

3. **zundo `partialize` + `diff` are required, not optional** -- Default full-state snapshots at 800 territories = 2-5 MB per step x 50 steps = 100-250 MB in browser. Exclude all transient UI state via `partialize`. Use `diff` to store only changed keys. Must be designed in at undo implementation time.

4. **Alembic + async engine: `env.py` needs custom setup** -- Default Alembic `env.py` uses sync `engine_from_config()`. With `aiosqlite://` URLs this silently generates empty migrations. Wrap with `asyncio.run()` + `run_sync(do_migrations)` from the start; import all model modules explicitly before `target_metadata = Base.metadata`.

5. **Wikidata 60s hard timeout kills large-country ingestion** -- A single SPARQL query for Spain (8000+ municipalities) will time out. Paginate at 500-1000 items max, fetch labels in a separate pass, set a descriptive `User-Agent` header, cache raw SPARQL results to SQLite immediately on success.

**Canvas-phase pitfalls to address in Phase 2:**

6. **Voronoi adjacency breaks after merge** -- After a merge removes a seed point, all `ridge_points` indices shift. Always rebuild the full neighbor lookup from scratch after any merge/split; maintain a uuid-to-index map rebuilt fresh per Voronoi computation.

7. **Konva full layer redraw on every state update** -- Wrap each territory polygon component in `React.memo` with geometry-only comparator. Separate into at minimum 3 layers: static background (listening=false), territories, interaction handles.

8. **`shapely.set_precision()` reverses winding order** -- Always call `shapely.orient(geom, sign=1.0)` after any `set_precision()` call to restore RFC 7946 counter-clockwise exterior rings. `Shapely.is_valid` does not catch this.

---

## Implications for Roadmap

### Suggested Phase Order

The research strongly supports this sequence. Each phase creates a dependency for the next.

---

### Phase 1: Data Pipeline + Backend Scaffold

**Rationale:** Database schema must be stable before any other layer. Generation and export can be validated with curl before any UI exists. The Vite/pip packaging seam and aiosqlite transaction semantics must be resolved here -- they are not solvable retrofits.

**Delivers:** Working `medieval-forge start` CLI, Wikidata/OSM ingestion, headless map generation, SQLite persistence, PNG preview serving, Unity ZIP export (headless). Most of the core value with no UI risk.

**Key features:** Project CRUD, Wikidata ingestion (paginated), OSM fallback, `map_generator.py` wrapper, BackgroundTask generation, preview FileResponse, validation service, export ZIP assembly.

**Must avoid:**
- Vite `base: "/"` (set `"./"` at scaffold)
- aiosqlite SAVEPOINT in merge/split (explicit transaction pattern from day one)
- Alembic empty migrations (async env.py from day one)
- Wikidata timeout on large countries (pagination + caching from day one)

**Research flag:** Standard patterns. No phase research needed.

---

### Phase 2: Read-Only Canvas Viewer

**Rationale:** Validate the coordinate projection and Konva layer architecture before adding mutation. A broken projection is caught immediately when polygons do not align, before drag mechanics are built on top of it.

**Delivers:** Interactive canvas with pan/zoom, territory polygons, click-to-inspect sidebar, layer toggles (terrain, borders, hierarchy, labels), minimap, fit-to-view button, reference overlay. No editing yet.

**Key features:** Projection module + round-trip unit test, Konva Stage + wheel handler, territory/border layers, capitals layer (static), hierarchy color-coding, territory properties panel.

**Must avoid:**
- Re-projecting coordinates on zoom (project once; let stage scale handle zoom)
- Missing memoization on territory polygon components

**Research flag:** Standard patterns for read-only canvas. No phase research needed.

---

### Phase 3: LLM Research Integration

**Rationale:** Can proceed in parallel with Phase 2 canvas work. The LLM service has no canvas dependency. Placing it here keeps it from blocking the editing phases.

**Delivers:** Claude API streaming + Ollama adapter, SSE token stream to frontend, schema validation + retry, research cache per project, hierarchy assignment to territories.

**Key features:** `services/llm.py` unified adapter, `api/research.py` SSE endpoint, Pydantic schema with extra=forbid, post-validation leaf-count sanity check, QID normalization, temporal pause/resume wrapping of LLM state updates.

**Must avoid:**
- Ollama naive response.json() on NDJSON stream (use stream=false + format=json)
- Pydantic schema without extra=forbid (phantom fields pass silently)
- zundo recording LLM polling updates as undo steps

**Research flag:** Low-risk. Anthropic SDK and Ollama patterns are confirmed.

---

### Phase 4: Canvas Editing -- Basic

**Rationale:** Capital drag + Voronoi recalc is the highest-value edit and establishes the undo transaction model. Merge must precede split. The adjacency rebuild logic must be solid before adding split topology changes.

**Delivers:** Capital drag with sub-500ms Voronoi recalc, territory merge with topology preservation, undo/redo (50-step, partialize+diff configured).

**Key features:** `POST /api/edit/move-capital`, `services/voronoi.py` neighbor recalc, Zustand `useProjectStore` with zundo `temporal` (partialize, diff, limit:50), merge endpoint with Shapely `unary_union`, compound undo step grouping for Voronoi side effects.

**Must avoid:**
- zundo without partialize and diff (100-250MB memory at 800 territories)
- Voronoi adjacency not rebuilt after merge
- Undo step per Voronoi recalc rather than per user action

**Research flag:** zundo v2 partialize+diff API at real scale warrants a spike with real Iberia GeoJSON data (~91 territories).

---

### Phase 5: Canvas Editing -- Advanced

**Rationale:** Territory split requires Phase 4 Shapely + undo infrastructure in place. Must not begin until Phase 4 undo model is stable.

**Delivers:** Territory split by drawn cut line, border vertex drag, terrain paint brush with land mask check.

**Key features:** Cut line hit-test against polygon edges, Shapely boolean partition into two new polygons, `shapely.orient()` post-split, terrain brush with land mask guard.

**Must avoid:**
- `set_precision()` without `orient(sign=1.0)` (winding order reversal)
- Split without full adjacency rebuild
- Hit canvas desync after `shape.cache()` without `clearCache()` on geometry change

**Research flag:** Split topology is 2-3x more complex than merge. Plan extra time. No external research needed.

---

### Phase 6: Validation Gate + Export Polish

**Rationale:** Phase 1 has headless export. Phase 6 productizes it with the pre-export safety net that is Medieval Forge competitive differentiation. Validation must come last because it can only be fully specified once the data model and edit operations are stable.

**Delivers:** Pre-export validation with error/warning classification, blocked export on errors, full Unity ZIP with all 12 standardized files, lookup PNG with unique RGB per territory, NEAREST upscale enforced.

**Key features:** `services/validator.py` schema-driven checks, 422 response with structured error list, final PNG generation with land mask at 2x resolution, NEAREST upscale, unique RGB assignment, Unity Y-up coordinate conversion.

**Must avoid:**
- Anti-aliasing on lookup PNG export (BICUBIC spreads border colors, breaks Unity shader)
- `visual_*.png` PPU mismatch (3840x2160 requires PPU=200, not 100)
- Loose validation heuristics (use typed schema per CK3/EU4 wiki requirements)

**Research flag:** Unity import documentation should be verified during planning to confirm all 12 file expectations are current. Low research burden.

---

### Phase Ordering Rationale

- **Data before canvas:** Voronoi geometry, GeoJSON format, and SQLite schema must be stable before the canvas layer. Retroactively changing geometry storage format after canvas is built is expensive.
- **Read-only canvas before editable canvas:** Projection errors and layer architecture problems are caught earlier without the complexity of mutation and undo.
- **LLM parallel to canvas (Phase 3 alongside Phase 2-4):** The LLM service has no canvas dependency and can be developed against Phase 1 API contracts independently.
- **Basic editing before advanced editing:** The undo transaction model and adjacency rebuild patterns in Phase 4 are prerequisites for Phase 5 split operation.
- **Validation last:** Validation logic depends on the complete data model. Phase 1 provides a partial validator for export unblocking; Phase 6 completes it.

### Research Flags

Needs deeper research during planning:
- **Phase 4** (zundo partialize+diff at scale): Spike with real Iberia GeoJSON data (~91 territories) to measure actual snapshot size before committing to the diff strategy.
- **Phase 6** (Unity file expectations): Verify the 12-file spec against current Unity 6 grand strategy community practice.

Standard patterns (no additional research needed):
- **Phase 1:** FastAPI + SQLAlchemy async + Alembic -- extensively documented, HIGH confidence.
- **Phase 2:** Konva read-only canvas -- official docs cover all patterns needed.
- **Phase 3:** Anthropic streaming + Ollama adapter -- SDK confirmed, patterns clear.
- **Phase 5:** Shapely boolean ops -- library is stable, patterns are standard.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Core stack confirmed. Four corrections applied (Vite 6, zundo 2.3.0, react-konva 19.x/React 19, rasterio 1.4.x pin). Tailwind v4 + Radix integration needs empirical testing for transparency bug. |
| Features | HIGH | Primary sources: Azgaar source, CK3/EU4 wiki, Konva.js official docs. Feature set is well-scoped with clear rationale. Anti-features well-reasoned. |
| Architecture | HIGH | All major patterns verified against official docs. Voronoi strategy confirmed against scipy 1.17 docs. SSE via FastAPI 0.115 native support confirmed. SPA serving pattern confirmed. |
| Pitfalls | HIGH | 8 new pitfalls identified beyond PROJECT.md known lessons. All have confirmed sources (GitHub issues, PyPI changelogs, official docs). Three Phase 1 pitfalls are the highest-priority pre-canvas concerns. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Tailwind v4 + Radix UI transparency bug:** Confirmed in GitHub issue #17137 but full integration requires empirical testing. Plan a UI component smoke-test early in Phase 2.
- **zundo snapshot size at real scale:** The 100-250MB estimate is calculated from territory count x GeoJSON size. Actual behavior with partialize+diff configured needs a spike test against real Iberia data.
- **`map_generator.py` importability:** Must be importable as a module and may need a thin wrapper if it lacks `if __name__ == "__main__"` guards. First thing to verify in Phase 1.
- **aiosqlite version pin:** A regression in aiosqlite v0.22.0 causes hanging threads on shutdown. Pin `aiosqlite>=0.20,<0.22` until the patch release fixing issue #13039 is confirmed.

---

## Sources

### Primary (HIGH confidence)
- [scipy.spatial.Voronoi docs v1.17](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.Voronoi.html)
- [FastAPI SSE docs v0.115](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- [FastAPI Static Files docs](https://fastapi.tiangolo.com/tutorial/static-files/)
- [zundo GitHub + npm](https://github.com/charkour/zundo) -- confirmed v2.3.0 latest, no v3
- [TanStack Query v5 npm](https://www.npmjs.com/package/@tanstack/react-query) -- confirmed 5.99.0
- [Zustand v5 + npm](https://www.npmjs.com/package/zustand) -- confirmed 5.0.12
- [Tailwind CSS v4.0 blog](https://tailwindcss.com/blog/tailwindcss-v4)
- [CK3 Map Modding wiki](https://ck3.paradoxwikis.com/Map_modding) -- sequential ID CTD requirement
- [EU4 Map Modding wiki](https://eu4.paradoxwikis.com/Map_modding) -- definition.csv integrity
- [Konva.js Performance docs](https://konvajs.org/docs/performance/All_Performance_Tips.html)
- [Anthropic Python SDK PyPI](https://pypi.org/project/anthropic/) -- confirmed 0.94.1
- [rasterio PyPI](https://pypi.org/project/rasterio/) -- confirmed 1.4.x/1.5+ version split

### Secondary (MEDIUM confidence)
- [Tailwind v4 + Radix transparency bug GitHub #17137](https://github.com/tailwindlabs/tailwindcss/discussions/17137)
- [Embedding React in FastAPI package (Medium)](https://medium.com/@asafshakarzy/embedding-a-react-frontend-inside-a-fastapi-python-package-in-a-monorepo-c00f99e90471)
- [Async SQLAlchemy + FastAPI pattern (Medium)](https://medium.com/@tclaitken/setting-up-a-fastapi-app-with-async-sqlalchemy-2-0-pydantic-v2-e6c540be4308)
- [Wolfire Games undo semantic grouping](http://blog.wolfire.com/2009/02/how-we-implement-undo/)
- [Unity province bitmap/color lookup forum](https://discussions.unity.com/t/how-to-make-a-paradox-style-grand-strategy-map-with-selectable-provinces-using-bitmap/785792)
- [Vite 6 migration guide](https://v6.vite.dev/guide/migration)
- [react-konva npm](https://www.npmjs.com/package/react-konva) -- confirmed 19.2.3 latest

---
*Research completed: 2026-04-16*
*Ready for roadmap: yes*