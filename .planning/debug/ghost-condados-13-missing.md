---
status: awaiting_human_verify
trigger: "Diagnose why map_generator.py drops 13 of 79 condados — no entry in lookup_condado_colors.json and no pixels in lookup_condado.png"
created: 2026-04-19T00:00:00Z
updated: 2026-04-19T17:00:00Z
symptoms_prefilled: true
goal: find_and_fix
---

## Current Focus

hypothesis: TWO ROOT CAUSES CONFIRMED AND FIXED.
  Problem B fixed (commit acb85bc): emit_territories_from_disk now accepts
    original_condados and remaps orig_idx → meta_ci via condado id join, so
    survivors at original index >= n_survivors are correctly emitted.
  Problem A fixed (commit 46499ed):
    A1: _split_municipalities_pt_es densifies PT outer rings to >= 40 vertices
        before writing pt_municipalities.geojson — prevents map_generator's
        40-vertex filter from silently dropping OSM-simplified municipalities.
    A2: _build_region_config expands render bbox to include all municipality
        centroids (+ 0.1 deg epsilon) after the PT/ES split, so decode_topojson_
        municipalities never drops an ES municipality at the bbox edge.
test: 21 unit tests pass (10 territories_geojson + 11 generator); 0 new regressions.
expecting: full pipeline re-run on asa project produces >= 85/92 condados in
  territory_metadata.json and all of them in territories.geojson.
next_action: human verification — re-trigger generation on asa project, confirm condado counts.

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

- hypothesis: Problem B caused by missing colors_raw entries
  evidence: colors_raw has exactly as many entries as there are surviving condados (59 entries for 59 survivors). Entry count is not the issue. The issue is index-space mismatch between colors_raw values (original indices) and the condados list (metadata re-indexed positions).
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

- timestamp: 2026-04-19
  checked: map_generator.py rasterize_baronies() lines 386-387: PT path 40-vertex filter
  found: 'if not rings or len(rings[0]) < 40: continue' — any PT municipality feature whose outer ring has fewer than 40 coordinate points is entirely skipped. OSM municipality polygons in remote/rural PT areas can be simplified to fewer vertices.
  implication: PT municipalities with simple geometry contribute 0 pixels to any barony. If all municipalities of a given PT condado's baronies are under 40 vertices, that condado gets 0 pixels purely from the PT path, relying only on the fallback gap-pixel assignment.

- timestamp: 2026-04-19
  checked: map_generator.py decode_topojson_municipalities() line 238: ES centroid bbox filter
  found: 'if cfg.lon_min <= cl <= cfg.lon_max and cfg.lat_min <= cla <= cfg.lat_max' — any ES municipality whose computed centroid (mean of first ring vertices) falls outside the render bbox is silently excluded from es_municipalities list. The bbox after _compute_padded_bbox is centroid-driven, not polygon-envelope-driven, so polygons that straddle the edge can have their centroid inside the bbox but polygon bodies partially clipped.
  implication: ES municipalities near the bbox boundary may have centroids just inside or just outside. Those outside are excluded → their baronies get 0 direct pixels.

- timestamp: 2026-04-19
  checked: territories_geojson.py emit_territories_from_disk() + map_generator.py generate_lookup_map()
  found: CRITICAL INDEX MISMATCH.
    generate_lookup_map (lib/map_generator.py line 663-672):
      for i in range(n_items):  # n_items = nc = 92 (full count)
          m = level_map == i    # level_map = pc (condado pixel map)
          if not np.any(m): continue
          color_map[f"{r},{g},{b}"] = i  # i = ORIGINAL index 0..91
    export_metadata (lib/map_generator.py line 700-714):
      for ci, c in enumerate(condados):  # iterates all 92
          if npx == 0: continue          # skips 33 zero-pixel condados
          metadata["condados"].append(...)  # writes ONLY survivors → 59 entries
    emit_territories_from_disk (services/territories_geojson.py line 149-185):
      condados_meta = meta["condados"]  # 59 entries, re-indexed 0..58
      condados = [... for c in condados_meta]  # positions 0..58
      for rgb_key, idx_val in colors_raw.items():
          idx = int(idx_val)  # ORIGINAL index, e.g., 0,3,5,...,85,89,91
          pc[mask] = idx      # pc stores ORIGINAL indices
    build_territories_geojson (services/territories_geojson.py line 91-98):
      for geom, idx in rasterio.features.shapes(pc32, ...):
          shapes_per_idx[int(idx)] = ...  # keyed by ORIGINAL index
      for ci, c in enumerate(condados):   # ci = 0..58 (METADATA position)
          geoms = shapes_per_idx.get(ci)  # looks up METADATA position as if it were ORIGINAL index
  implication: Any surviving condado whose original position in the CONDADOS list
    is >= 59 has pixels in pc at value >= 59, but build_territories_geojson only
    checks ci values 0..58. Those survivors have METADATA entries (correctly
    written by export_metadata) but NO geojson feature. This explains exactly
    20 condados present in metadata but absent from territories.geojson.

## Resolution

root_cause: |
  TWO INDEPENDENT ROOT CAUSES producing two separate losses.

  PROBLEM A (92 condados defined → 59 in territory_metadata.json, 33 lost):

  Sub-cause A1 — PT 40-vertex filter in rasterize_baronies() line 386:
    The PT rasterization path skips any feature whose outer ring has < 40
    vertices: 'if not rings or len(rings[0]) < 40: continue'. OSM-sourced
    Portuguese municipalities in rural/simplified areas may have fewer than
    40 vertices. These features contribute 0 direct pixels. If all
    municipalities serving a condado's baronies fail this filter, those
    baronies receive only fallback gap-pixel territory, which cleanup_and_smooth
    subsequently erodes to 0.

  Sub-cause A2 — ES centroid bbox filter in decode_topojson_municipalities() line 238:
    After _split_municipalities_pt_es(), ES municipalities are decoded from
    TopoJSON. The decoder filters by centroid position:
    'if cfg.lon_min <= cl <= cfg.lon_max and cfg.lat_min <= cla <= cfg.lat_max'.
    The render bbox is padded 5% beyond condado centroids but is still a
    tight envelope. ES municipalities near the bbox edge (coastal, border)
    whose polygon centroid (computed as mean of ring[0] vertices) falls just
    outside are silently dropped. Their baronies receive only fallback coverage,
    which erodes to 0.

  Sub-cause A3 — Cleanup erosion of sparse pixels:
    Both A1 and A2 cause baronies to start with fewer pixels. The 8-pass
    median filter (kernels 11→5) + Gaussian competition then erodes these
    small territories to 0. This is the mechanism of death, not the root cause,
    but it amplifies A1 and A2 from "partial loss" to "complete loss."

  PROBLEM B (59 condados in metadata → 39 in territories.geojson, 20 lost):

  Index-space mismatch in emit_territories_from_disk (territories_geojson.py):

  generate_lookup_map() in map_generator.py writes:
    color_map[rgb] = i   where i = ORIGINAL condado index (range 0..91)
  lookup_condado.png pixels are painted with the same ORIGINAL index i.

  export_metadata() writes only surviving condados (those with > 0 pixels).
  The metadata condados list is 59 entries long, re-indexed 0..58.

  emit_territories_from_disk() loads condados from metadata (59 entries,
  positions 0..58), then sets pc[mask] = int(idx_val) where idx_val is the
  ORIGINAL index from lookup_condado_colors.json. The pc array therefore
  contains ORIGINAL indices as pixel values.

  build_territories_geojson() calls rasterio.features.shapes() which yields
  (geom, pixel_value) pairs — pixel values are ORIGINAL indices. It stores
  them in shapes_per_idx[original_index]. Then it iterates:
    for ci, c in enumerate(condados):  # ci = 0..58 (METADATA position)
        geoms = shapes_per_idx.get(ci)
  This conflates metadata position with original index. Any condado whose
  original position in territory_iberia.json is >= 59 has shapes keyed at
  original_index >= 59, but ci never reaches that value (max 58).
  Result: those condados have valid metadata entries and real pixels in
  lookup_condado.png, but emit_territories_from_disk produces no geojson
  feature for them. Exactly 20 such condados exist given 33 dropped (those
  33 zero-pixel condados occupy original positions scattered across 0..91;
  the survivors whose original position is >= 59 are the 20 missing).

fix: |
  APPLIED — two atomic commits.

  Commit 1 — Fix B (acb85bc): territories_geojson.py + generator.py
    emit_territories_from_disk gains optional original_condados parameter.
    When provided, builds orig_idx→meta_ci mapping via condado id join:
      id_to_meta_ci = {c["id"]: ci for ci, c in enumerate(condados_meta)}
      orig_to_meta  = {orig_idx: id_to_meta_ci[orig_c[0]] for ...}
    pc[mask] = meta_ci (not orig_idx) → shapes_per_idx keys align with
    build_territories_geojson's 0..n_survivors enumeration.
    Dropped condados (not in metadata) are silently skipped at debug level.
    _run_pipeline_sync passes territory_data["condados"] as original_condados.
    Legacy callers (tests) without original_condados use identity fallback.
    New test: test_emit_territories_orig_idx_remapped_to_meta_ci exercises
    3 survivors at original indices 5, 7, 99 in a 100-condado universe.

  Commit 2 — Fix A (46499ed): generator.py + test_generator.py (new)
    A1: Added _densify_ring() + _densify_feature() helpers.
    _split_municipalities_pt_es now densifies all PT features to >= 40
    outer-ring vertices before writing pt_municipalities.geojson.
    Uses linear midpoint insertion; idempotent; area preserved within 1e-4.
    A2: Added _municipality_centroids() helper (reads raw_geojson, same
    arithmetic-mean formula as decode_topojson_municipalities).
    _build_region_config expands render bbox after the PT/ES split to
    include all municipality centroids ± 0.1 deg epsilon, ensuring the
    black-box centroid filter never drops an ES municipality at the edge.
    11 unit tests covering all new helpers + integration paths.

verification: |
  Unit tests: 10/10 territories_geojson + 11/11 generator = 21 total passing.
  No new regressions introduced (6 pre-existing failures confirmed unchanged
  by git stash + re-run before/after).
  Empirical verification pending: user must re-trigger generation on asa
  project and confirm condado count >= 85/92 in territory_metadata.json
  and all survivors present in territories.geojson.

files_changed:
  - backend/medieval_forge/services/territories_geojson.py
  - backend/medieval_forge/services/generator.py
  - backend/tests/test_territories_geojson.py
  - backend/tests/test_generator.py (new)
