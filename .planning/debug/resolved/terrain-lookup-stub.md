---
status: resolved
trigger: "terrain-lookup-stub — generated/terrain.png is entirely black; no terrain_lookup.png or terrain_types.json produced"
created: 2026-04-17T02:00:00Z
updated: 2026-04-17T03:00:00Z
symptoms_prefilled: true
---

## Current Focus

hypothesis: CONFIRMED — terrain.png was alias for mountains_mask.png (always black when no mountain data). terrain_lookup.png feature was entirely unimplemented. Fix implemented: generate_terrain_lookup() added to lib/map_generator.py and wired into pipeline. All 4 unit tests pass.
test: test_terrain_lookup_files_produced confirms terrain_lookup.png has >= 2 unique colors in full pipeline run.
expecting: Human verify terrain_lookup.png shows varied terrain colors (green forest, gray hills, teal coast, tan plain)
next_action: Await human visual verification

## Symptoms

expected: terrain_lookup.png = per-pixel RGB encoding terrain type; terrain_types.json = RGB -> {movement, defense, attack}
actual: generated/terrain.png is 100% black (all pixels 0,0,0). No terrain_lookup.png. No terrain_types.json.
errors: None in logs — black placeholder was intentional fallback
reproduction: Generate any map → inspect generated/terrain.png → all black
started: Since Phase 1

## Eliminated

- hypothesis: terrain generation function exists but writes to wrong filename
  evidence: grep confirmed no terrain_lookup anywhere in original backend code
  timestamp: 2026-04-17T02:00:00Z

- hypothesis: terrain types computed but color table all zeros
  evidence: No terrain type computation existed at all — genuine unimplemented stub
  timestamp: 2026-04-17T02:00:00Z

## Evidence

- timestamp: 2026-04-17T02:00:00Z
  checked: generator.py _PREVIEW_ALIASES dict
  found: terrain.png → mountains_mask.png (binary impassable mask, not terrain type lookup)
  implication: Fundamental wrong mapping — not a terrain type image at all

- timestamp: 2026-04-17T02:00:00Z
  checked: generator.py _materialise_aliases
  found: When mountains_mask.png missing, creates black placeholder. This was source of all-black output.
  implication: Black image was intentional code, not a path bug

- timestamp: 2026-04-17T02:00:00Z
  checked: lib/map_generator.py entire file
  found: No terrain_lookup generation function anywhere. Feature was 100% absent.
  implication: Must implement from scratch

- timestamp: 2026-04-17T03:00:00Z
  checked: generate_terrain_lookup implementation + 4 unit tests
  found: test_terrain_lookup_has_multiple_types PASS, test_terrain_lookup_mountain_mask_applied PASS, test_terrain_types_json_structure PASS, test_terrain_lookup_files_produced PASS
  implication: Implementation is correct. Full suite: 44 pass, 4 pre-existing failures. Zero regressions.

## Resolution

root_cause: terrain.png was aliased to mountains_mask.png (binary impassable mask, all-black without mountain data). The reference-specified terrain_lookup.png + terrain_types.json was never implemented — the pipeline had no terrain type classification at all.

fix: Added generate_terrain_lookup() to lib/map_generator.py (Section 13). Classification: ocean (pixels outside land mask), mountain (pixels in mtn_mask), coast (land within 8px of ocean boundary via distance_transform_edt), hill/forest/plain (deterministic spatial noise function). Added _TERRAIN_TYPES dict with RGB colors + {movement, defense, attack} per type. Wired into generate_maps() pipeline as step 15. Updated generator.py: added terrain_lookup.png + terrain_types.json to _GENERATOR_OUTPUTS and GENERATED_FILE_WHITELIST. Changed _PREVIEW_ALIASES terrain.png → terrain_lookup.png. Removed black placeholder fallback from _materialise_aliases (no longer needed).

verification: 4 unit tests pass covering: multi-color output, mountain mask priority, terrain_types.json structure, full pipeline integration producing non-trivial terrain_lookup.png with >= 2 unique colors and matching terrain.png alias.

files_changed:
  - backend/medieval_forge/lib/map_generator.py
  - backend/medieval_forge/services/generator.py
  - backend/tests/test_generate.py
