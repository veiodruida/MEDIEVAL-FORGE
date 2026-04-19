---
status: awaiting_human_verify
trigger: "Diagnose why map_generator.py drops 13 of 79 condados — no entry in lookup_condado_colors.json and no pixels in lookup_condado.png"
created: 2026-04-19T00:00:00Z
updated: 2026-04-19T12:00:00Z
symptoms_prefilled: true
goal: find_and_fix
---

## Current Focus

hypothesis: CONFIRMED and FIXED — _split_municipalities_pt_es() now splits municipalities.geojson by PT/ES border polygon before injecting into map_generator; both municipality_pt_geojson and municipality_es_topojson are set correctly.
test: smoke tests pass; all 13 ghost condado centroids classify to correct side; TopoJSON round-trip verified.
expecting: full pipeline run produces all 79 condados in territory_metadata.json and lookup_condado_colors.json
next_action: human verification — run generation on existing project with municipalities.geojson on disk, confirm condado count

## Symptoms

expected: Every condado in territory_data.condados should appear in both lookup_condado_colors.json and lookup_condado.png
actual: 13 of 79 condados missing from lookup_condado_colors.json and lookup_condado.png — chaves, braganca, leon (north), vizcaya, jaca, sobrarbe, ribagorza, madrid, ubeda, elvira, guadix, baza, malaga
errors: No explicit pipeline errors — generator completes "successfully" but silently drops territories
reproduction: Any Iberia generation with territory_iberia.json produces this
started: Pre-existing bug; also seen in older project fe5d709d (91/90 ratio)

## Eliminated

- hypothesis: color collision in generate_lookup_map (i*37, i*73, i*113 formula)
  evidence: Python simulation proves no collisions for any n up to 92 condados (all multipliers coprime to 256)
  timestamp: 2026-04-19

- hypothesis: PT 40-point ring filter explains all 13 drops
  evidence: 11 of the 13 condados are ES-side duchies; the PT filter only applies to PT municipalities. Cannot explain ES drops.
  timestamp: 2026-04-19

- hypothesis: Gaussian smoothing competition is the primary mechanism
  evidence: Full land mask simulation shows all 92 condados retain pixels through cleanup_and_smooth. The erosion is not the primary cause; it's a secondary effect of having too few starting pixels.
  timestamp: 2026-04-19

- hypothesis: land mask coverage gaps (municipality bounds filtering)
  evidence: Bounds filter only excludes municipalities with centroids outside [-13.2,8.2]x[35.4,44.6]. All Iberian municipalities are within these bounds.
  timestamp: 2026-04-19

## Evidence

- timestamp: 2026-04-19
  checked: exports/lookup_condado_colors.json and territory_metadata.json (actual pipeline output)
  found: Only 25 condados in exports — all western Iberia (lon <= -5.66). Pattern matches municipality coverage of that specific run.
  implication: The dropping mechanism is geographic/data-dependent, not a deterministic filter.

- timestamp: 2026-04-19
  checked: generator.py _build_region_config() lines 232-235
  found: Only municipality_pt_geojson is set (to raw/municipalities.geojson). municipality_es_topojson is NEVER set (remains None/default).
  implication: map_generator receives ALL municipalities (PT and ES) via the PT parameter only.

- timestamp: 2026-04-19
  checked: ingest_runner.py -> ingest_osm.fetch_municipalities() -> writes to raw/municipalities.geojson
  found: The municipalities.geojson contains BOTH Portuguese AND Spanish municipalities from OSM bbox query. Not split by country.
  implication: The full multi-country GeoJSON is piped into municipality_pt_geojson.

- timestamp: 2026-04-19
  checked: map_generator.py rasterize_baronies() lines 378-428
  found: PT path (lines 378-399) processes ALL features in pt_data, assigning each to nearest PT barony via tp (PT KD-tree). ES path (lines 401-412) iterates es_municipalities=[] -> 0 iterations. Fallback (lines 417-428) assigns gap pixels to nearest barony by side.
  implication: Spanish municipality polygons are painted with PT barony indices. ES baronies get only gap-pixel territory.

- timestamp: 2026-04-19
  checked: exports/ pattern — 25 present condados all have lon <= -5.66; absent condados have lon > -5.66 or are in northern Spain (lat > 43)
  found: Clean geographic split. Western municipalities serve as gap-creators for nearby PT baronies. Eastern/northern Spanish municipalities fully claim their area for PT baronies, leaving ES baronies starved.
  implication: Confirms the misrouting mechanism. ES condados' territory depends on how many gap pixels remain after PT path.

- timestamp: 2026-04-19
  checked: Python simulation: full land mask + proper PT/ES border KD-tree assignment
  found: All 92 condados retain pixels through cleanup when KD-tree correctly routes PT/ES pixels. No condados are dropped. This proves cleanup_and_smooth is NOT the primary cause.
  implication: The primary cause is the insufficient starting pixel territory for ES baronies, not the erosion algorithm.

- timestamp: 2026-04-19
  checked: map_generator.py generate_lookup_map() line 665 and export_metadata() line 701
  found: Both silently skip condados with 0 pixels: 'if not np.any(m): continue' and 'if npx == 0: continue'. No warning or error logged.
  implication: The drop is silent. Pipeline "completes successfully" with fewer condados than input defined.

## Resolution

root_cause: |
  Design mismatch in generator.py _build_region_config() (lines 232-235):
  municipality_pt_geojson is set to the full ingested municipalities.geojson
  (which contains both Portuguese AND Spanish OSM municipalities from the bbox query),
  but municipality_es_topojson is never set.
  
  map_generator.rasterize_baronies() has two independent processing paths:
  - PT path (lines 378-399): processes all pt_data features, assigns each to nearest
    PT barony (d_portucale, d_gharb, d_fronteira) via tp KD-tree. This paints Spanish
    municipality polygons with Portuguese barony indices -- wrong assignment.
  - ES path (lines 401-412): iterates es_municipalities which is [] -- zero iterations.
  - Fallback (lines 417-428): assigns gap pixels (unassigned, raw=-1) by PT/ES side.
    Spanish municipalities cover most Spanish land, leaving minimal gaps.
  
  ES baronies (for all non-PT-duchy condados) therefore receive pixel territory only
  from the gaps between Spanish municipality polygons. When OSM coverage is dense,
  these gaps are minimal. cleanup_and_smooth (8 median passes + fragment merge +
  Gaussian competition + blob merge) then erodes this minimal territory to 0.
  
  Condados whose ALL baronies reach 0 pixels are silently dropped from
  lookup_condado_colors.json (generate_lookup_map line 665) and
  territory_metadata.json (export_metadata line 701).
  
  The 13 specific condados that drop depend empirically on the OSM municipality
  coverage density in their geographic area: condados in areas with denser Spanish
  municipality coverage get fewer gap pixels and are more likely to be eroded to 0.
  This explains why the dropped set varies between project bbb (13 missing) and
  project fe5d709d (1 missing) -- different ingested municipality datasets.

fix: |
  Added three helpers and one split function to generator.py:
  - _IBERIA_PT_BORDER: hardcoded PT border polygon (same coords as map_generator.iberia_config)
  - _geojson_centroid(): arithmetic-mean centroid of outer ring (fast, no shapely)
  - _point_in_polygon(): ray-casting test (mirrors map_generator.point_in_polygon)
  - _geojson_to_topojson(): GeoJSON->TopoJSON with identity transform (scale=[1,1],
    translate=[0,0]); one arc per ring, delta-encoded; Polygon and MultiPolygon supported
  - _split_municipalities_pt_es(): reads municipalities.geojson, classifies each
    feature by centroid vs border polygon, writes pt_municipalities.geojson and
    es_municipalities_topo.json under generated_dir; raises ValueError if either
    bucket is empty (safety guard)

  Modified _build_region_config() to call _split_municipalities_pt_es() when
  municipality_pt_geojson and municipality_es_topojson are both unset and
  municipalities.geojson exists on disk. Passes border_polygon from kwargs if
  present; falls back to _IBERIA_PT_BORDER constant otherwise.

  Smoke-tested: all 13 ghost condado centroids classify correctly; Polygon,
  MultiPolygon, and Polygon-with-hole TopoJSON round-trips verified.

verification: |
  Smoke tests pass (backend/smoke_test_split.py):
  - Polygon round-trip: PASS
  - MultiPolygon round-trip: PASS
  - Polygon-with-hole round-trip: PASS
  - PT/ES classification (9 known cities): all PASS
  - Ghost condado classification (all 13): all PASS
  Awaiting human verification: full pipeline run to confirm all 79 condados appear.

files_changed:
  - backend/medieval_forge/services/generator.py
