# Medieval Forge

## What This Is

Medieval Forge is a local web tool for Game Designers that automates the creation of historically-accurate medieval maps for strategy games. It replaces manual, error-prone iteration workflows by providing a full pipeline: ingest modern geographic data (Wikidata/OSM), apply LLM-assisted historical research, generate Voronoi-based territory maps, and export Unity-ready asset packages — all with a real-time canvas editor for iterative refinement.

## Core Value

A Game Designer can go from "country + historical period" to a validated, Unity-ready map package without manual pixel editing or blind iteration.

## Requirements

### Validated

(None yet — ship to validate)

### Active

**Backend & Generation**
- [ ] User can create a project (country, period, bounding box, config)
- [ ] User can ingest municipalities via Wikidata SPARQL
- [ ] User can ingest municipalities via OSM Overpass (fallback)
- [ ] System generates territory map using map_generator.py pipeline
- [ ] User can view PNG previews (terrain, territories, borders)
- [ ] User can export a Unity-ready ZIP with 12 standardized files

**Canvas Editor**
- [ ] User can view all territories on an interactive canvas (pan/zoom)
- [ ] User can move a capital/centroid and watch neighbors recalculate Voronoi in <500ms
- [ ] User can edit border vertices (drag individual polygon nodes)
- [ ] User can merge two or more adjacent territories into one
- [ ] User can split a territory by drawing a cut line
- [ ] User can paint terrain types (mountain, river, forest, plains, arid) with a brush
- [ ] User can upload a reference overlay (SRTM/custom) with opacity slider
- [ ] User can undo/redo all edit operations (Ctrl+Z / Ctrl+Y, 50-step history)

**Historical Research**
- [ ] User can trigger LLM research (Claude API) to get kingdoms/duchies/counties for a country+period
- [ ] User can use Ollama (local LLM) as alternative provider
- [ ] System validates LLM responses against schema and retries on invalid JSON
- [ ] Research results are cached per project (no re-querying same country)

**Validation & Export**
- [ ] System validates project before export (orphan baronies, dark ocean pixels, missing capitals, small territories, hierarchy integrity)
- [ ] Export is blocked on errors, warns on warnings
- [ ] Export ZIP contains all 12 Unity-ready files in correct format

### Out of Scope

- Tauri/Electron packaging — webapp + localhost is sufficient
- SSR/Next.js — Vite SPA is enough for a local tool
- Direct Unity integration — user copies files manually
- GPU rendering — Konva (DOM-based canvas) handles up to 1000 territories
- Persisting LLM API keys to disk — session memory only
- Rewriting map_generator.py — used as an imported library

## Context

This tool was born from a game designer's experience generating medieval Iberian Peninsula maps (868 AD) for the Reconquista project (grand strategy Unity 6 game). ~25 chat iterations exposed the pain points: blind iteration without preview, no vectorial editor for borders inherited from modern municipality polygons, no structured historical research workflow, no automatic validation.

**Reference files in `inicio/`:**
- `map_generator.py` — existing pipeline to reuse as library (not rewrite)
- `territory_data_v3.py` — example territory data (Ibéria 868 AD, 91 condados)
- `mountain_river_data.json` — example geographic data format
- `BRIEFING_MEDIEVAL_FORGE.md` — full project specification

**Known technical lessons (from original workflow):**
- Land mask must be applied at 2x resolution AFTER upscale to avoid black pixels in ocean
- Use NEAREST upscale (not BICUBIC) — interpolation spreads dark pixels to ocean
- Border painting must check `if land[y,x]` before painting
- Smoothing σ=4.5 (σ=3.0 leaves borders too straight)
- Merge threshold 200px — below this, small territories disappear
- Lookup index → metadata array must use `*ByOriginalIdx` dict (not direct access)
- `pixel_center` in metadata is Y-down (numpy); Unity is Y-up — convert
- `visual_*.png` is 3840×2160 → PPU=200 in Unity (not 100)
- Wikidata QIDs: PT=Q45, ES=Q29, GB=Q145, FR=Q142, IT=Q38, DE=Q183

## Constraints

- **Tech Stack**: Python 3.11+ / FastAPI / SQLite — backend; React 18 + TypeScript + Vite + Konva.js — frontend
- **State**: Zustand with `zundo` middleware for undo/redo; TanStack Query v5 for cache
- **Styling**: Tailwind CSS v4 + Radix UI primitives
- **Packaging**: pip-installable Python package; `medieval-forge start` CLI entry point
- **LLM**: Claude API (`claude-sonnet-4-6`) + Ollama adapter (local fallback)
- **Geometry**: scipy Voronoi + Shapely for boolean ops; GeoJSON storage
- **Performance**: Voronoi recalc for affected neighbors only (not full regen) — target <500ms
- **Validation**: Must pass before export is allowed (errors block, warnings warn)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| React + Konva.js (not plain canvas) | Hit detection, layer system, React bindings, offscreen canvas performance | — Pending |
| SQLite (not JSON plain files) | Fast queries on 500+ territories, atomic transactions for merge/split, async via aiosqlite | — Pending |
| Zustand + zundo (not Redux) | Simpler API, free undo/redo middleware, better TS inference, no boilerplate | — Pending |
| FastAPI (not Flask) | Async native for LLM calls + ingestion, Pydantic validation, OpenAPI docs auto | — Pending |
| Python backend (not pure frontend) | Voronoi in 500+ points: JS ~2s vs Python+scipy ~0.1s; CORS for Wikidata; LLM keys not in browser | — Pending |
| Reuse map_generator.py as library | Avoid regression risk; existing pipeline generates correct output | — Pending |
| pip package with bundled frontend | Single install (`pip install medieval-forge`), `medieval-forge start` opens browser | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-16 after initialization*
