---
status: awaiting_human_verify
trigger: "Port reference pipeline geographic terrain: replace synthetic noise in generate_terrain_lookup() with polygon-based mountain rasterization from mountain_river_data.json"
created: 2026-04-17T04:00:00Z
updated: 2026-04-17T04:30:00Z
symptoms_prefilled: true
---

## Current Focus

hypothesis: CONFIRMED AND FIXED — synthetic noise removed, 4-type palette implemented, mountain_river_data_iberia.json bundled and wired.

test: 5 new unit tests + updated existing tests. All pass. 3 commits made.

expecting: Human visual verify — terrain_lookup.png for Iberia shows mountains at Pyrenees / Cantábrica / Sistema Central geographic positions.

next_action: CHECKPOINT — await human visual verification of terrain_lookup.png

## Symptoms

expected: terrain_lookup.png shows mountains in real geographic locations (Pyrenees, Cordillera Cantábrica, Sistema Central). Rivers in rivers_overlay.png. Plain/coast derived from land mask geometry. No synthetic noise.
actual: generate_terrain_lookup() uses sine-wave spatial hash (xs * 0.031, ys * 0.017) to paint forest/hill/plain. Patterns are deterministic but geographically wrong. Mountain mask exists but terrain lookup paints noise UNDER the mountains, not just where the polygon data says.
errors: None — output is visually plausible but geographically wrong.
reproduction: Run Iberia generator → open terrain_lookup.png → forest/hill blobs don't follow Iberian geography.
started: Previous debug session (terrain-lookup-stub) implemented the stub using noise as placeholder.

## Eliminated

- hypothesis: mountain_river_data.json is not loaded at all
  evidence: render_mountains() in backend map_generator reads cfg.mountain_river_json — BUT RegionConfig.mountain_river_json is None by default in the backend. The backend service never sets it. So mountains are rendered correctly (mountains_mask.png) only when cfg.mountain_river_json is set. The terrain_lookup also uses whatever mtn_mask is passed in.
  timestamp: 2026-04-17T04:00:00Z

- hypothesis: render_mountains/render_rivers are missing from backend
  evidence: They ARE present in backend/medieval_forge/lib/map_generator.py (copied from reference). What's missing is (a) bundled JSON data, (b) cfg wiring to the bundled data, (c) terrain_lookup dropping noise + hill/forest.
  timestamp: 2026-04-17T04:00:00Z

## Evidence

- timestamp: 2026-04-17T04:00:00Z
  checked: backend/medieval_forge/lib/map_generator.py SECTION 13 (lines 797-920)
  found: generate_terrain_lookup() uses sine-wave noise (xs*0.031+ys*0.017, xs*0.073-ys*0.059, etc.) to partition land into hill (~20%), forest (~25%), plain (~55%). Mountains override on top. Hill and forest types are in _TERRAIN_TYPES.
  implication: Synthetic noise must be removed. Hill/forest types must be dropped. Palette must be ocean/coast/plain/mountain only.

- timestamp: 2026-04-17T04:00:00Z
  checked: inicio/mountain_river_data.json
  found: Contains 7 mountain ranges (pyrenees, picos_europa, gredos, guadarrama, sierra_nevada, moncayo + cantabrica implied by picos_europa location) and rivers (douro, tajo, etc.) as lon/lat polygons/polylines. Format matches reference render_mountains() exactly.
  implication: File can be bundled as-is to backend/medieval_forge/services/mountain_river_data_iberia.json.

- timestamp: 2026-04-17T04:00:00Z
  checked: backend/medieval_forge/services/generator.py _build_region_config()
  found: mountain_river_json is never set in kwargs. RegionConfig.__dataclass_fields__ includes mountain_river_json but the service never resolves the bundled data path.
  implication: Must add logic to set mountain_river_json to bundled file path when building Iberia config (or any config where the template has it).

- timestamp: 2026-04-17T04:00:00Z
  checked: backend/tests/test_generate.py lines 339-357
  found: test_terrain_types_json_structure checks len(terrain_types) >= 4 and expects forest/hill. Must update to exactly 4 types (ocean/coast/plain/mountain) and remove hill/forest check.
  implication: Tests need updating alongside implementation.

## Resolution

root_cause: generate_terrain_lookup() used sine-wave spatial hash (xs*0.031+ys*0.017, etc.) to produce geographically meaningless forest/hill/plain terrain. mountain_river_data.json was not bundled in the backend package. The service layer never wired mountain_river_json into RegionConfig. Together these caused terrain_lookup.png to show synthetic noise patterns instead of real Iberian mountain geography.

fix: Three commits (954c3fe, 7c1bee6, a72c171):
  1. Bundled inicio/mountain_river_data.json → backend/medieval_forge/services/mountain_river_data_iberia.json
  2. Rewrote generate_terrain_lookup(): dropped sine noise, dropped hill/forest types, reduced to 4-type palette (ocean/coast/plain/mountain). Coast = land within 8px EDT of ocean. Mountains = polygon mask clipped to land, downscaled via NEAREST stride.
  3. Added render_mountains_from_data() — testable core that accepts pre-loaded JSON data (no filesystem I/O in tests).
  4. Wired mountain_river_json in _build_region_config() to auto-resolve bundled file path.
  5. Added 5 unit tests in test_terrain.py (all pass).
  6. Updated test_generate.py terrain assertions: exactly 4 types, named {ocean,coast,plain,mountain}.

verification: 14/14 relevant tests pass. Pre-existing failures (test_png_outputs, test_generation_time, test_sse_stream, test_country_qid_validation) confirmed pre-existing via git stash. Awaiting human visual verification.

files_changed:
  - backend/medieval_forge/services/mountain_river_data_iberia.json (new)
  - backend/medieval_forge/lib/map_generator.py
  - backend/medieval_forge/services/generator.py
  - backend/tests/test_terrain.py (new)
  - backend/tests/test_generate.py
