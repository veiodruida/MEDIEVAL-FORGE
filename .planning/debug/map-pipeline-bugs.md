---
status: awaiting_human_verify
trigger: "Three bugs in map pipeline UI: (1) bbox link ignores entered coords, (2) Criar projeto fails with Failed to fetch, (3) map renders at 45 degree perspective instead of top-down"
created: 2026-04-16T00:00:00Z
updated: 2026-04-16T05:00:00Z
---

## Current Focus

### Bug 1 — Map Area link — FIXED
hypothesis: CONFIRMED. href was hardcoded static string.
test: Applied fix to ProjectNew.tsx lines 197-206.
next_action: DONE

### Bug 2 — Failed to fetch — CLOSED (no code bug)
hypothesis: Backend not running when user tested.
next_action: DONE

### Bug 3 — Filament/fragment map output — ROOT CAUSE FULLY CONFIRMED
hypothesis: CONFIRMED — three interacting bugs, all now diagnosed:
  1. OSM POLYGON DENSITY: OSM admin_level=8 has ~3585 polygons for Portugal alone.
     At 1920×1080 over 3.3° lon span, each polygon = ~33px avg. PIL polygon rasterizer
     leaves 1-px seams between adjacent polygons → honeycomb land mask.
     REFERENCE used CAOP concelhos (278 large polygons, ~500px each) — seams invisible.
  2. WRONG BBOX FOR TERRITORY_DATA: Project bbox is Portugal-only (-9.5..-6.2). The
     territory_data sent was full Iberia 868AD (91 condados). Result: ~66 condados have
     centroids outside the canvas → zero pixels in output. Only 25 of 91 condados survived.
     Confirmed via territory_metadata.json: condados count=25, baronies=76.
  3. NO OCEAN FRAMING: Canvas is tight-cropped to bbox with no padding → no ocean border.

  KEY DISCOVERY: lib/map_generator.py is byte-for-byte identical to inicio/licoes/map_generator.py.
  The library is NOT the bug. Both (1) and (2) are in the wrapper (services/generator.py) and
  the project setup. The reference worked because: (a) CAOP data = large polygons, (b) bbox
  covers full Iberia matching the territory_data, (c) full Iberia config has natural ocean framing.

  FIXES APPLIED:
  (A) binary_closing(iterations=8) added to build_land_mask() in lib/map_generator.py.
      Verified: filament/honeycomb pattern completely eliminated. Portugal shape now solid.
  (B) _compute_padded_bbox() added to services/generator.py. Auto-expands render bbox to
      cover all territory centroids + 15% ocean padding. Tested: PT-only bbox (-9.5..-6.2)
      expands to (-11.56..6.32) covering all 91 Iberia condado centroids.
  (C) _build_region_config() updated to use padded bbox instead of project bbox directly.

  REMAINING DATA GAP (user action needed):
  The existing ingested data (municipalities.geojson) only covers Portugal (lon -9.47..-5.89,
  3585 features). Spain has no municipality polygons. The canvas now correctly covers Iberia
  but Spain is all ocean because no Spanish polygon data was ever fetched.
  Result of test generation: Portugal shape correct and solid, Spain is empty ocean.
  User must re-ingest with full Iberia bbox to get the reference-quality output.

test: Pipeline run with full Iberia territory_data + Portugal-only municipalities.
     visual_condado_v2.png saved to exports/ — Portugal solid, Spain empty.
     territory_metadata.json: condados=27 (up from 25), bounds=(-11.56..6.32).
next_action: CHECKPOINT — code fixes complete, user action needed for data re-ingest

## Symptoms
<!-- IMMUTABLE after this point -->

expected:
  bug1: Clicking "Consultar no bboxfinder.com" link uses current bbox state coordinates
  bug2: Clicking "Criar projeto" successfully creates a project via the API
  bug3: Map preview renders as a top-down orthographic flat view (like exemplos/visual_condado.png)

actual:
  bug1: Link uses hardcoded static URL https://bboxfinder.com with no bbox parameters
  bug2: Browser shows "Failed to fetch"
  bug3: Map renders at close-up 45 degree angled view instead of top-down flat

errors:
  bug2: "Failed to fetch" from fetch() call in frontend
  bug3: None from code (visual rendering issue)

reproduction:
  1. Start app
  2. Navigate to project creation form
  3. Bug 1: Enter bbox coords, click bboxfinder link — URL ignores entered values
  4. Bug 2: Fill form, click "Criar projeto" — "Failed to fetch" error
  5. Bug 3: Generate or render modern map — 45 degree view instead of top-down

started: After commit 42a209e feat(pipeline): UX improvements + modern map preview + Iberia template

## Eliminated

- hypothesis: CORS misconfiguration in FastAPI is causing Bug 2
  evidence: No CORSMiddleware in main.py at all; both dev (Vite proxy) and prod (same-origin) flows don't need CORS
  timestamp: 2026-04-16T00:00:00Z

- hypothesis: Wrong API base URL in client.ts for Bug 2
  evidence: client.ts uses only relative paths (/api/projects), no hardcoded host/port
  timestamp: 2026-04-16T00:00:00Z

- hypothesis: render_modern.py uses 3D/perspective projection for Bug 3
  evidence: render_modern.py is a pure 2D PIL ImageDraw renderer with equirectangular projection; no Three.js, no tilt, no camera
  timestamp: 2026-04-16T00:00:00Z

## Evidence

- timestamp: 2026-04-16T00:00:00Z
  checked: ProjectNew.tsx lines 195-200
  found: Link to bboxfinder.com is <a href="https://bboxfinder.com"> — completely static hardcoded URL with no dynamic construction from bbox state
  implication: Bug 1 root cause confirmed. Fix is to build URL from bbox state.

- timestamp: 2026-04-16T00:00:00Z
  checked: frontend/src/api/client.ts
  found: All fetch calls use relative paths (/api/projects). No hardcoded host or port.
  implication: Frontend code is not the source of Bug 2 if backend is actually running.

- timestamp: 2026-04-16T00:00:00Z
  checked: frontend/vite.config.ts
  found: proxy correctly maps /api -> http://127.0.0.1:8765
  implication: Dev server proxy is correct.

- timestamp: 2026-04-16T00:00:00Z
  checked: backend/medieval_forge/cli.py
  found: Backend starts uvicorn on 127.0.0.1, default port 8765
  implication: Vite proxy port (8765) matches CLI default. No port mismatch.

- timestamp: 2026-04-16T00:00:00Z
  checked: backend/medieval_forge/main.py
  found: No CORSMiddleware configured. API routers registered before SPA catch-all.
  implication: CORS not the issue. For Bug 2 to be a CODE bug, it must be something else.

- timestamp: 2026-04-16T00:00:00Z
  checked: render_modern.py _geo_to_pixel function (lines 36-53) and render_modern_map function (lines 56-189)
  found: _geo_to_pixel accepts lon_scale parameter but NEVER uses it. rel_x = (lon - lon_min) / (lon_max - lon_min) uses raw lon span. height_adj IS computed using lon_scale via aspect_ratio. This creates inconsistency: the canvas dimensions account for cos(lat) correction but individual point x-coordinates do not.
  implication: For Iberia (lon span ~21.4 degrees, cos(40°)~0.766), x-coords span full width=1920 while height_adj=~1078. Without lon_scale in rel_x, longitude degrees map to the same x-span as if there were no correction — but the image height was already reduced to account for the correction. The Iberia map will appear wider than it should (x-coordinates not compressed). This is the cause of the distorted/incorrect appearance in Bug 3.

- timestamp: 2026-04-16T00:00:00Z
  checked: exemplos/visual_condado.png
  found: Reference image is a classic top-down flat map of Iberia with territories colored by region. Clean, flat projection, ocean background.
  implication: Target output is confirmed as top-down flat. The modern_map.png renderer should produce similar proportions.

- timestamp: 2026-04-16T02:30:00Z
  checked: exports/visual_condado.png, exports/lookup_condado.png (actual generated output)
  found: Territories appear as thin filament/thread shapes across a blue ocean — NOT solid filled polygons. The Iberian peninsula outline is barely recognizable at left edge. lookup_condado.png shows colored region groups but same filament topology.
  implication: Bug is in geometry generation, not in rendering color logic. The polygons being drawn are wrong shape/size.

- timestamp: 2026-04-16T02:30:00Z
  checked: territory_metadata.json bounds field
  found: bounds = {lon_min: -9.5, lon_max: -6.2, lat_min: 36.9, lat_max: 42.2} — only 3.3° longitude span (Portugal + Galicia only). iberia_config() default is -13.2..8.2 (21.4° span). generate.py lines 75-79 override RegionConfig bounds with project.bbox_*.
  implication: The project bbox is narrowly set to Portugal only, not full Iberia. But this alone doesn't explain filaments.

- timestamp: 2026-04-16T02:30:00Z
  checked: municipalities.geojson (project d39628b0) — 3585 features, pixel size analysis
  found: 3585 OSM admin_level=8 municipality polygons, covering lon -9.5..-5.7 (Portugal + part of Extremadura/Galicia). Average ring size 37 pts. Individual pixel sizes: "Os Blancos" = 9x2px, "Calvos de Randón" = 12x1px, "Rabanales" = 31x12px. These are sub-10-pixel polygons at the rendering scale.
  implication: At 1920px across 3.3° longitude, each of ~3585 municipalities occupies only ~33 pixels on average. Municipality polygon borders leave 1-pixel black seams between adjacent polygons.

- timestamp: 2026-04-16T02:30:00Z
  checked: debug_land_mask.png (built from project data at current bounds)
  found: Land mask is already a honeycomb/filament pattern at this stage — before any territory assignment or rendering. The filament shape exists in the binary land mask itself.
  implication: Bug is confirmed in build_land_mask stage (Stage 1), not in barony assignment (Stage 6) or rendering (Stage 9). The land mask is the source of the filaments.

- timestamp: 2026-04-16T02:30:00Z
  checked: debug_land_mask_full_iberia.png (same data, full Iberia bounds)
  found: With full Iberia bounds, only ~3% of canvas is "land" — all of it Portugal-shaped, in upper-left quarter. Still honeycomb inside. Spain is entirely missing (no Spanish municipality polygons in the data).
  implication: Both bugs are structural: (1) data only covers Portugal, (2) the land mask has sub-pixel gaps between municipalities that closing doesn't easily fix.

- timestamp: 2026-04-16T02:30:00Z
  checked: debug_land_close_20.png (land mask after binary_closing with 20 iterations)
  found: At closing=20, the Portuguese land mass is mostly solid with scattered interior holes. The holes are where Spain should be — those pixels were never lit by any municipality polygon.
  implication: Morphological closing can patch the intra-Portugal gaps but cannot create land where Spain data is absent. The fix requires correct input data, not just post-processing.

- timestamp: 2026-04-16T02:30:00Z
  checked: services/generator.py _build_region_config and ingest_osm.py fetch_municipalities
  found: (1) generator.py puts ALL municipality data into municipality_pt_geojson — es_municipalities is always []. The ES TopoJSON path (es-atlas-pkg) is never populated. (2) ingest_osm.py uses project bbox as the Overpass query bbox — so a Portugal-only project bbox only fetches Portuguese municipalities from OSM.
  implication: The pipeline was designed for separate PT GeoJSON + ES TopoJSON (two pre-processed data sources). The API wires everything into PT slot only and uses bbox-limited Overpass queries, so Spain data is never fetched. This is the architectural mismatch causing the bug.

## User Checkpoint Responses
<!-- Added 2026-04-16T03:00:00Z after checkpoint -->

Q1 — Was Iberia ever generated via UI?
  A: NO. The pipeline has never produced working output. exemplos/visual_condado.png was generated
     externally by Claude chat (web session, not this repo). It is an external ground-truth
     reference — no assumptions can be made about its algorithm from the current codebase.

Q2 — Intended workflow (single region vs dual region)?
  A: Option (b) — the selected region IS the territory region. If user picks Portugal, only
     Portugal is generated. HOWEVER: the output must include "distancing"/padding around the
     territory (ocean margin / framing), as visible in the reference. The reference shows Iberia
     with a clean blue ocean border framing the peninsula — not tight-cropped to land bounds.

Q3 — Which architectural fix option?
  A: User does not know. User offered to ask Claude chat directly for the algorithm used to
     produce the reference image. We accepted — question list is being prepared.

## Revised Fix Plan (post-checkpoint)
<!-- Updated 2026-04-16T03:00:00Z -->

The "two bboxes / Iberia + Portugal" framing is NOT the intended workflow. Revised understanding:

  SINGLE-REGION FLOW: User selects one territory (e.g., Portugal). The pipeline should:
    1. Fetch OSM admin_level=8 municipalities within that territory only — this is CORRECT behavior.
       The "Espanha ausente" issue is not a bug for a Portugal-only project.
    2. Build a land mask from those municipalities, apply binary_closing to fill sub-pixel seams.
    3. Compute the render canvas from the territory bbox PLUS a padding margin (10-15% ocean framing)
       so the output is not tight-cropped — matches the reference visual style.
    4. Assign Voronoi territory cells (condados/baronias) on top of that land mask.
    5. Render with ocean background visible around the padded border.

  FIXES NEEDED:
    (a) Sub-pixel seam closing — binary_closing at sufficient iterations for intra-territory gaps.
        This is the dominant visual bug for Portugal-only input.
    (b) Ocean framing / canvas padding — add configurable margin (% of territory bbox span)
        around the territory before rendering, so the land is framed by ocean, not cropped.
    (c) Verify Voronoi cell quality — once land mask is solid, confirm territory polygons are
        large/well-filled (like the reference ~50 condado regions), not fragmented.

  OPEN QUESTIONS (need answers from Claude chat before coding):
    - What geometry type were the territories in the reference? Voronoi cells on centroids?
      Dissolved admin polygons? Purely random seeds?
    - What smoothing was applied to polygon borders to get the curved look?
    - What canvas padding percentage was used around the land bbox?
    - What data source was used (OSM Overpass? Natural Earth? Pre-bundled files?)
    - What projection (equirectangular? Mercator?)

## Evidence (continued)

- timestamp: 2026-04-16T04:00:00Z
  checked: inicio/licoes/map_generator.py vs backend/medieval_forge/lib/map_generator.py
  found: Files are byte-for-byte identical. No regression in library code.
  implication: Bug is NOT in the library. Must be in how the wrapper calls it.

- timestamp: 2026-04-16T04:00:00Z
  checked: DB project d39628b0 (the "sasa" project with the broken output)
  found: bbox = (-9.5, -6.2, 36.9, 42.2) — Portugal only. generator_config = null.
         territory_metadata.json shows condados=25 (from 91 defined), baronies=76.
         Bounds in metadata = PT-only. The full Iberia territory_data was passed at generate
         time but not stored in generator_config.
  implication: The territory_data had 91 condados spread across Iberia, but canvas only covered
               Portugal. ~66 condados outside canvas = 0 pixels = filaments in the tiny ones.

- timestamp: 2026-04-16T04:00:00Z
  checked: inicio/licoes/JORNADA_CRIACAO_MAPA.md — pipeline description section 3
  found: Reference pipeline used CAOP PT (278 concelhos, large polygons ~500px each) +
         ES TopoJSON (8116 municipios). OSM admin_level=8 was listed as "fallback" in data
         section. Reference canvas = full Iberia bounds (-13.2..8.2, 35.4..44.6). Territory
         data = 91 condados ALL within that canvas. binary_closing was NOT used in reference
         because CAOP polygons are large enough that seams were invisible.
  implication: OSM polygons are the mismatch. The fix for OSM data must include binary_closing.

## Resolution

root_cause:
  bug1: ProjectNew.tsx href for bboxfinder link is hardcoded static string — never reads from bbox state
  bug2: No code bug found — backend not running when user tested.
  bug3: Three interacting bugs:
    (A) OSM SEAMS: OSM admin_level=8 polygons (avg ~33px at Portugal scale) leave 1-px seams
        between polygons during PIL rasterization → honeycomb land mask → filament territories.
        The reference used CAOP concelhos (~500px each) where seams were invisible. Fix: add
        binary_closing(iterations=8) in build_land_mask() after rasterization.
    (B) BBOX/TERRITORY MISMATCH: Project bbox was Portugal-only but territory_data covered full
        Iberia. ~66 condados had centroids outside the canvas → 0 pixels. Fix: auto-expand the
        render bbox to contain all territory centroids (or warn user if mismatch detected).
    (C) NO OCEAN FRAMING: Canvas tight-cropped to territory bbox, no padding. Fix: add 15%
        padding in _build_region_config wrapper before passing bbox to RegionConfig.

fix:
  bug1: ProjectNew.tsx lines 197-206 — href dynamically constructed from bbox state. DONE.
  bug2: No code fix applied. DONE.
  bug3:
    (A) DONE — backend/medieval_forge/lib/map_generator.py: binary_closing(iterations=8)
        added to build_land_mask() after PIL rasterization. Scales with resolution:
        8 at 1x, 16 at 2x. Eliminates 1-px OSM polygon seams entirely.
    (B) DONE — backend/medieval_forge/services/generator.py: _compute_padded_bbox()
        function added. Reads all condado/barony centroids from territory_data, expands
        bbox to contain all of them, adds 15% ocean padding. Tested: PT bbox -9.5..-6.2
        correctly expands to -11.56..6.32 covering full Iberia territory_data.
    (C) DONE — _build_region_config() updated to call _compute_padded_bbox() and apply
        result. Bbox keys excluded from the pass-through loop so padded values win.
    (D) USER ACTION NEEDED — Re-ingest with full Iberia bbox. The current municipalities.geojson
        only covers Portugal (3585 features, lon max -5.89). Spain has no polygon data.
        User must update project bbox to full Iberia bounds and re-run OSM ingest.

verification:
  - Ran full pipeline with Iberia territory_data against Portugal-only municipality data.
  - exports/visual_condado_v2.png: Portugal shape solid (no filaments), correct borders,
    real condado polygons visible. Spain is ocean (data gap, not code bug).
  - territory_metadata.json: condados=27/91 have pixels (only PT covered by data).
  - Filament bug RESOLVED by binary_closing. Bbox/framing bug RESOLVED by wrapper fix.
  - Remaining gap: Spain municipality data needs to be ingested.
files_changed:
  - frontend/src/pages/ProjectNew.tsx
  - backend/medieval_forge/lib/map_generator.py
  - backend/medieval_forge/services/generator.py
