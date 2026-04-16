# FEATURES.md — Medieval Forge

**Domain:** Local web map generation tool for historical strategy games
**Researched:** 2026-04-16
**Overall confidence:** HIGH (primary sources: Azgaar wiki/source, CK3 wiki, EU4 wiki, Konva.js docs, Unity community discussions)

---

## Table Stakes (users expect these)

Features whose absence makes the tool feel broken or unusable. Sourced by comparing Azgaar FMG, Inkarnate, CK3/EU4 modding tools.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Mouse-wheel zoom + click-drag pan | Universal in every map tool; Azgaar, Inkarnate, all GIS tools have it | Low | Konva.js `Stage.draggable()` + wheel listener covers this |
| Selection feedback on click (highlight territory) | Users need to know what they clicked; Paradox editors show province info on click | Low | Hover and click state styling |
| Visible territory labels (names on canvas) | Without labels users cannot orient themselves; all comparators show this | Medium | Konva `Text` per centroid; toggle-able for clean view |
| Layer toggle panel | Azgaar has it; EU4 modding has map mode switching; users expect to hide/show terrain, borders, hierarchy, labels | Medium | Each visual concern = its own Konva Layer |
| Undo / Redo (Ctrl+Z / Ctrl+Y) | Fundamental editing expectation; The Forts editor has unlimited depth; most tools have at least 20-50 steps | Low-Med | Already in scope: `zundo` middleware on Zustand; 50-step target is appropriate — below 20 feels punishing |
| Export to PNG | Every single comparator exports PNG; it's the universal format for game assets | Low | Already in scope |
| Territory properties panel | EU4 and CK3 both show province stats on selection; users need to read/edit name, type, hierarchy assignments | Medium | Side panel with form fields |
| Hierarchy visualization | CK3 has kingdoms/duchies/counties; EU4 has tags/areas/regions; users building grand strategy maps expect this | High | Color-coding by tier (kingdom/duchy/county/barony); Azgaar does cultures+states layered |
| Reference image overlay with opacity | Both CK3 modders and Azgaar users import reference images (historical maps, SRTM elevation) to trace | Medium | Already in scope; standard Konva image layer |
| Minimap / overview | Azgaar has it; large maps (Iberian Peninsula at 500+ territories) need it to navigate | Medium | A secondary reduced Stage fixed in corner |
| Project save / load | Any multi-session tool must persist state; Azgaar saves to .map JSON; EU4 mods save files | Low | SQLite backend already in scope |
| Canvas fit-to-view / reset zoom | "I got lost" is a common failure mode in map editors; every tool has a Home/Reset button | Low | One button; Konva `stage.scale(1).position({x:0,y:0})` |

---

## Differentiators (competitive advantage)

Features that no existing free tool offers this combination of; this is Medieval Forge's moat.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| LLM-assisted historical research (kingdom/duchy/county hierarchy for a real country+period) | Azgaar generates fantasy names; Inkarnate is pure canvas with no data; no tool auto-populates a historically grounded hierarchy from a real date | High | Already in scope; Claude API + Ollama fallback |
| Wikidata/OSM ingestion as seed data | Fantasy tools make up geography; this tool starts from real municipalities (868 AD Iberia) providing authentic province shapes as input to Voronoi | High | Already in scope; the core differentiation |
| Voronoi recalculation scoped to affected neighbors only (<500ms) | Azgaar regenerates the whole map; interactive border editing with sub-second feedback is a UX breakthrough for modders who currently use GIMP pixel-editing workflows | High | Already in scope; scipy incremental recalc |
| Unity-ready ZIP export (12 standardized files including lookup PNG + JSON metadata) | No free tool exports a game-engine-ready package; EU4 modders manually maintain definition.csv and province bitmaps; this automates the full pipeline | High | Already in scope; the core value delivery |
| Validation gate before export (with specific error messages) | EU4/CK3 mods crash silently on bad data (sequential ID gaps cause CTDs per CK3 wiki); a pre-export validator with human-readable errors is rare | Medium | Already in scope; orphan barony, dark pixel, missing capital, small territory, hierarchy integrity checks |
| Merge / split territories with topology preservation | Azgaar has no territory split; EU4 modders use GIMP to manually redraw province bitmaps; automated split by drawing a cut line is a significant workflow improvement | High | Already in scope |
| Terrain paint with land mask awareness | A brush that refuses to paint ocean pixels (`if land[y,x]` check) prevents the dark-pixel corruption bug that plagued the original workflow — no other tool handles this constraint at all | Medium | Already in scope; the lesson from 25 iterations |
| Historical accuracy constraints (period-specific data, not fantasy generation) | Inkarnate and Azgaar produce fantasy; modders building historical games (like Reconquista, a Crusader Kings clone) have no tool that accepts "Iberian Peninsula, 868 AD" as input and returns real polities | High | The unique positioning of this tool |

---

## Anti-Features (deliberately NOT building)

Features that competitors have, that would be a mistake to add to Medieval Forge.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Fantasy name/lore generation | Azgaar and Inkarnate own this space; adding it dilutes the historical accuracy positioning | Rely on LLM for historically attested names only |
| Procedural terrain generation (noise-based heightmaps) | Users are importing SRTM / real elevation data; generated terrain would undermine the accuracy value prop | Accept reference image overlays; use OSM terrain data |
| Multi-user collaboration / cloud sync | Out of scope per PROJECT.md; adds auth, CRDT complexity; this is a single-designer local tool | Local SQLite; one user per install |
| GPU-accelerated rendering (WebGL shaders) | 500-1000 Konva shapes achieves 60fps without WebGL per benchmark; GPU adds shader complexity with no benefit at this scale | Konva DOM canvas with layer management and shape caching |
| Built-in tileset/asset library (stamps, icons, brushes) | Inkarnate's moat; requires art assets, licensing, significant UX work; not the value proposition here | Allow reference overlay import; terrain type is semantic, not visual |
| SVG export | The Unity workflow uses PNG lookup textures (unique RGB per province) and JSON metadata — SVG is not useful in this pipeline; adds complexity for no gain | PNG + JSON is the correct Unity integration pattern |
| Direct Unity plugin / Editor integration | Tauren/Editor SDK integration scope-crept and ships slowly; user copies files manually and this is fine | Export ZIP; document the Unity import steps |
| Undo history beyond 50 steps | Memory cost grows; 50 steps covers any reasonable editing session; unlimited undo (like The Forts) is expensive with polygon geometry data | 50-step `zundo` history; document the limit |
| Online hosting / SaaS | Puts LLM API keys in a shared service, adds auth, billing; the tool is a pip-installable local app | `medieval-forge start` CLI remains local |

---

## Feature Complexity Notes

These are implementation risks or non-obvious complexity traps based on comparator analysis and domain research.

### Territory Split is the Hardest Canvas Feature
Splitting a Voronoi region by drawing a cut line requires: (1) hit-testing the drawn line against all polygon edges, (2) computing the intersection points, (3) partitioning the polygon vertices into two new polygons using Shapely boolean ops, (4) triggering Voronoi recalc for affected neighbors, (5) pushing the compound operation as a single undo step. This is meaningfully more complex than merge. Plan 2–3x the time of merge.

### Lookup PNG Constraints (Unity-specific)
The standard Unity grand strategy pattern (confirmed across multiple Unity forum discussions) is: one PNG where each province has a unique solid RGB color, used as a texture sampled in a shader to determine which province the player clicked. This means: (1) RGB values must be 100% unique per province, (2) anti-aliasing must be off on export (NEAREST upscale only — BICUBIC spreads border colors and breaks the lookup), (3) the PNG must match exact pixel dimensions the Unity shader expects. These are non-negotiable constraints, not stylistic choices.

### Undo Step Granularity Matters More than Depth
Based on Wolfire Games' undo research: semantic grouping is critical. Moving a capital and watching 6 neighbors recalculate should be ONE undo step (capital move), not 7 steps (1 move + 6 Voronoi recalcs). Users think "undo the move," not "undo each polygon update." `zundo` middleware must group Voronoi side effects with the triggering action using transaction batching.

### Konva.js Performance Target: 1000 Shapes at 60fps is Achievable With Discipline
Konva's own documentation confirms 60fps at 1000+ interactive objects, but requires: (1) layer separation (static background, interactive territories, labels — minimum 3 layers), (2) shape caching for complex polygon renders, (3) `listening(false)` on non-interactive layers (terrain overlay, reference image), (4) no oversized Stage dimensions. The 500ms Voronoi recalc target is backend-bound (scipy), not frontend-bound; the canvas redraw for neighbor polygons is fast.

### Validation Must Be Schema-Driven, Not Ad Hoc
CK3's map modding wiki documents that sequential ID gaps cause CTDs (crash to desktop). EU4 has `definition.csv` integrity requirements. These are examples of "data that looks fine but breaks the engine silently." Medieval Forge's validation gate should be a typed schema with specific checks, not a loose "looks okay" heuristic. The PROJECT.md already defines 5 validation categories (orphan baronies, dark ocean pixels, missing capitals, small territories, hierarchy integrity) — this is the right level of specificity.

### Historical vs Fantasy: Two Different Mental Models
Fantasy tools (Azgaar, Inkarnate) treat the map as the source of truth — you draw, then invent names/lore to match. Historical tools must treat external sources (Wikidata, OSM, LLM historical research) as the source of truth — the map must conform to the evidence, not the reverse. This affects UX decisions: Medieval Forge should warn (not silently allow) when a user manually moves a capital far from the historical municipality centroid, or when a territory name doesn't match the LLM-researched name for that region. The tool should feel like a validator of history, not a blank canvas.

---

## Phase Mapping Suggestions

Based on feature complexity and dependency chains, here is a recommended build order:

### Phase 1: Data Pipeline + Headless Generation
Wikidata/OSM ingestion → `map_generator.py` integration → PNG preview → JSON metadata generation. No canvas yet. Validates the data model before building UI on top of it. This is table stakes infrastructure; everything else depends on it.

**Key features unlocked:** project creation, backend ingestion, headless PNG export, Unity ZIP export (most of the value with no UI risk)

### Phase 2: Read-Only Canvas Viewer
Konva stage with territory polygons from the backend data → pan/zoom → click-to-inspect sidebar → layer toggles (terrain, borders, hierarchy) → labels → minimap. No editing yet. Validates the canvas architecture before adding mutation.

**Key features unlocked:** interactive canvas, hierarchy visualization, reference overlay, territory properties panel

### Phase 3: LLM Research Integration
Claude API + Ollama adapter → schema validation + retry → research cache per project → hierarchy assignment from research to territories. Can be done before or after canvas; parallel with Phase 2 is viable.

**Key features unlocked:** historical accuracy differentiator, hierarchy population

### Phase 4: Canvas Editing — Basic
Capital drag (→ Voronoi recalc for neighbors) → territory merge → undo/redo. These are the highest-value edits with moderate implementation complexity. Establishes the undo transaction model for all subsequent edits.

**Key features unlocked:** iterative refinement, undo/redo (50-step), sub-500ms Voronoi recalc

### Phase 5: Canvas Editing — Advanced
Territory split by cut line → border vertex drag → terrain paint brush. These are the most complex canvas features. Split especially needs Phase 4's Shapely + undo infrastructure in place first.

**Key features unlocked:** full vector editing workflow, terrain type assignment

### Phase 6: Validation Gate + Export Polish
Pre-export validation with error/warning classification → blocked export on errors → full Unity ZIP with all 12 files. This phase productizes the tool — Phase 1 has headless export but Phase 6 adds the safety net.

**Key features unlocked:** production-quality export, orphan/dark-pixel/hierarchy validation

---

## Sources

- [Azgaar Fantasy Map Generator — wiki and export features](https://azgaar.github.io/Fantasy-Map-Generator/)
- [Azgaar GitHub — source and feature list](https://github.com/Azgaar/Fantasy-Map-Generator)
- [CK3 Map Modding — validation constraints, sequential ID requirement, river pixel rules](https://ck3.paradoxwikis.com/Map_modding)
- [CK3 Modding Tools wiki](https://ck3.paradoxwikis.com/Modding_tools)
- [EU4 Map Modding — definition.csv, adjacencies, province requirements](https://eu4.paradoxwikis.com/Map_modding)
- [MagellanEU4 — community map editing tool for EU4](https://github.com/Graapefruit/MagellanEU4)
- [Konva.js All Performance Tips](https://konvajs.org/docs/konvajs.org/docs/performance/All_Performance_Tips.html)
- [Konva.js Layer Management Performance](https://konvajs.org/docs/performance/Layer_Management.html)
- [Konva.js vs Fabric.js benchmark — 1000+ objects, 60fps](https://medium.com/@www.blog4j.com/konva-js-vs-fabric-js-in-depth-technical-comparison-and-use-case-analysis-9c247968dd0f)
- [How We Implement Undo — Wolfire Games (semantic grouping)](http://blog.wolfire.com/2009/02/how-we-implement-undo/)
- [Unity discussion: Paradox-style province bitmap/color lookup](https://discussions.unity.com/t/how-to-make-a-paradox-style-grand-strategy-map-with-selectable-provinces-using-bitmap/785792)
- [Map UI UX standards — UXPin](https://www.uxpin.com/studio/blog/map-ui/)
- [Inkarnate feature review — standard canvas tool expectations](https://dungeongoblin.com/blog/inkarnate-pro-review-2021)
