---
phase: quick-260417-hpt
plan: 01
subsystem: map-pipeline
tags: [rivers, pipeline, disconnect, reversible]
dependency_graph:
  requires: []
  provides: [rivers-disconnected-from-pipeline]
  affects: [map_generator, generator-service, export-service]
tech_stack:
  added: []
  patterns: []
key_files:
  modified:
    - backend/medieval_forge/lib/map_generator.py
    - backend/medieval_forge/services/generator.py
    - backend/medieval_forge/services/export.py
  created:
    - .planning/debug/resolved/terrain-real-geography.md
  deleted:
    - .planning/debug/terrain-real-geography.md
decisions:
  - "Rivers disconnected from pipeline (not deleted) — reversible by restoring one call site and two whitelist entries"
metrics:
  duration: ~10 min
  completed: 2026-04-17
  tasks_completed: 2
  files_changed: 4
---

# Quick Task 260417-hpt: Remove Rivers Generation from Pipeline — Summary

**One-liner:** Removed rivers_overlay.png from the generate_maps() pipeline and output whitelists while retaining render_rivers() function and JSON data intact for future reactivation.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Disconnect rivers from pipeline + remove from output whitelists | 79987b0 | map_generator.py, generator.py, export.py |
| 2 | Archive debug note to resolved/ with rivers-disconnect addendum | 4ea6444 | .planning/debug/resolved/terrain-real-geography.md |

## What Changed

**map_generator.py** — The "# 13. Rivers" block in `generate_maps()` (which called `render_rivers(cfg)`, saved `rivers_overlay.png`, and composited rivers onto visual maps) was replaced with `rivers_img = None`. The `render_rivers()` function at line 766 is untouched. Module docstring and print summary no longer advertise `rivers_overlay.png`.

**generator.py** — `"rivers_overlay.png"` removed from `_GENERATOR_OUTPUTS` tuple. Comment updated to clarify `render_rivers` is disconnected but preserved.

**export.py** — `"rivers_overlay.png"` removed from `UNITY_ZIP_SPEC`. Unity zip now contains 11 files instead of 12; intentional until rivers are reactivated.

**resolved/terrain-real-geography.md** — Original debug note moved from `debug/` to `debug/resolved/`, status updated to `resolved`, rivers-disconnect addendum appended.

## Reversibility

To re-enable rivers: restore the "# 13. Rivers" block in `generate_maps()` and re-add `"rivers_overlay.png"` to `_GENERATOR_OUTPUTS` (generator.py) and `UNITY_ZIP_SPEC` (export.py). No data or function changes needed.

## Deviations from Plan

None — plan executed exactly as written.

## Verification Results

- render_rivers importable: PASS
- No call to render_rivers inside generate_maps(): PASS
- rivers_overlay.png absent from _GENERATOR_OUTPUTS: PASS
- rivers_overlay.png absent from UNITY_ZIP_SPEC: PASS
- mountain_river_data_iberia.json untouched: PASS
- All 5 tests in test_terrain.py: PASS
- resolved/ debug note exists with addendum: PASS
- Original debug note deleted (moved): PASS

## Self-Check: PASSED

- backend/medieval_forge/lib/map_generator.py: FOUND
- backend/medieval_forge/services/generator.py: FOUND
- backend/medieval_forge/services/export.py: FOUND
- .planning/debug/resolved/terrain-real-geography.md: FOUND
- Commit 79987b0: FOUND
- Commit 4ea6444: FOUND
