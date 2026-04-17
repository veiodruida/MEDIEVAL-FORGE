---
status: resolved
trigger: "osm-multipolygon-stitching — OSM relation parser treats each outer way as independent polygon instead of stitching ways into closed rings"
created: 2026-04-17T00:00:00Z
updated: 2026-04-17T02:00:00Z
---

## Current Focus

hypothesis: CONFIRMED — _relation_to_geojson_feature force-closed each individual outer way as an independent ring, producing shattered MultiPolygons
test: Fix implemented using shapely.ops.linemerge + polygonize; 5 new unit tests all pass
expecting: User re-runs Iberia ingest in UI and confirms filled pastel territories in modern map
next_action: Await human visual verification of Iberia ingest output

## Symptoms

expected: ~485 clean administrative polygons, one closed outer ring per département/provincia (minus holes for enclaves). Modern map renders as filled pastel territories.
actual: All 485 features are MultiPolygon with hundreds of sub-parts (Dordogne: 252, Landes: 261). Rendered map shows solid ocean-blue with only black outlines — slivers are sub-pixel.
errors: No exceptions. Pipeline completes "successfully" but produces visually broken output. No log warnings.
reproduction: Create project with Iberia bbox, run Ingerir via OSM, run Gerar mapa moderno — solid blue with outlines only.
started: Latent bug in Phase 1, discovered 2026-04-17 during manual testing of Iberia template.

## Eliminated

- hypothesis: Runtime crash or exception in parser
  evidence: Pipeline completes successfully, 485 features are produced — the geometry data is wrong, not missing
  timestamp: 2026-04-17T00:00:00Z

- hypothesis: linemerge(unary_union(lines)) is safe for single-LineString input
  evidence: unary_union([single_line]) returns bare LineString; linemerge(LineString) raises ValueError "Cannot linemerge LINESTRING ...". Must pass list directly: linemerge(lines).
  timestamp: 2026-04-17T01:00:00Z

## Evidence

- timestamp: 2026-04-17T00:00:00Z
  checked: backend/medieval_forge/services/ingest_osm.py lines 70-106 (original)
  found: Lines 82-86 force-close each OSM way with ring.append(ring[0]) then push each way as an independent outer ring. Line 96 emits MultiPolygon([[o] for o in outers]) — one polygon per way segment.
  implication: Dordogne's boundary is defined by 252 way members → 252 fake rings → 252-part MultiPolygon.

- timestamp: 2026-04-17T00:00:00Z
  checked: Shapely version
  found: shapely 2.1.2 is installed in the backend Python environment
  implication: shapely.ops.linemerge and shapely.ops.polygonize are available — the correct approach

- timestamp: 2026-04-17T00:00:00Z
  checked: backend/tests/test_ingest.py baseline run
  found: 1 pre-existing failure (test_sse_stream — Portuguese string mismatch), 6 other tests pass
  implication: Pre-existing failure is unrelated; our fix must not break the 6 passing tests

- timestamp: 2026-04-17T01:00:00Z
  checked: shapely.ops.linemerge behaviour on single vs multiple LineStrings
  found: linemerge(list_of_lines) works for 1 or N lines; linemerge(unary_union(lines)) fails when N=1 because unary_union collapses to bare LineString which linemerge rejects
  implication: Implementation must pass list directly to linemerge, not via unary_union

- timestamp: 2026-04-17T01:00:00Z
  checked: Full test run after fix (py -m pytest tests/ -v)
  found: 37 pass, 4 fail — all 4 failures are pre-existing (test_sse_stream Portuguese string, 2 test_generate.py geo data errors, 1 test_projects.py validation). Zero regressions from our change.
  implication: Fix is clean; 5 new unit tests (simple square, hole, multi-island, malformed, no-outer) all pass

## Resolution

root_cause: _relation_to_geojson_feature treated each OSM way member (a LineString segment) as an independent closed ring by force-closing it with ring.append(ring[0]). Multiple ways forming one outer boundary were emitted as separate polygons — one per way — producing Dordogne with 252 parts instead of 1.

fix: Rewrote _relation_to_geojson_feature to collect outer/inner members as shapely LineString objects, use linemerge(list) + polygonize() to assemble closed rings, pair inner rings to containing outers via op.contains(ip.representative_point()), and emit Polygon (single outer) or MultiPolygon (multiple disjoint outers). Added logging.warning for malformed relations where polygonize yields no polygons.

verification: 5 new unit tests pass (test_relation_simple_square, test_relation_with_hole, test_relation_multi_island, test_relation_malformed_returns_none, test_relation_no_outer_returns_none). Full suite: 37 pass, 4 pre-existing failures, 0 regressions. Human confirmed 2026-04-17: "Ok parece bem melhor" — territories now render as filled pastel polygons instead of black outlines on solid ocean.

files_changed:
  - backend/medieval_forge/services/ingest_osm.py
  - backend/tests/test_ingest.py
