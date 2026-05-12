---
phase: "05"
plan: "09"
subsystem: "backend/pipeline+api"
tags: [region-template, yaml, england, missing-inputs, has_dataset, endpoint-test]
dependency_graph:
  requires:
    - phase: 05-01
      provides: "load_region API, FileNotFoundError contract, clear_region_cache"
    - phase: 05-06
      provides: "france_1066.yaml template structure (mirror)"
    - phase: 05-07
      provides: "GET /api/v3/regions endpoint (has_dataset flag)"
  provides:
    - "data/regions/england_1216.yaml — YAML-only template (no inputs dir)"
    - "test_england_1216_missing_inputs.py — 2 tests: loader error + endpoint has_dataset=false"
  affects:
    - "GET /api/v3/regions now includes england_1216 with has_dataset=false"
tech_stack:
  added: []
  patterns:
    - "Template-only YAML: dataset paths declared but inputs dir absent — loader raises FileNotFoundError (D-12)"
    - "Wave-4 test depends on 05-01 (loader) + 05-07 (endpoint) — both confirmed green"
key_files:
  created:
    - "data/regions/england_1216.yaml"
  modified:
    - "backend/tests/unit/test_england_1216_missing_inputs.py (replaced Wave-0 placeholder)"
decisions:
  - "england_1216.yaml mirrors france_1066.yaml field-for-field including ocean/coast/mountain/river defaults for schema consistency"
  - "dataset paths reference inputs/england_municipalities.geojson (absent by design, D-12) — loader raises FileNotFoundError with 'england_1216' + 'missing' in message"
  - "No data/regions/england_1216/ directory created — verified absent with test -d check"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-12"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 1
  tests_added: 2
requirements-completed: [SC-2]
---

# Phase 05 Plan 09: England 1216 Template + Missing-Inputs Error Test Summary

**One-liner:** `england_1216.yaml` YAML-only template (no inputs dir) with two unit tests proving FileNotFoundError carries an actionable message and the `/api/v3/regions` endpoint reports `has_dataset: false`.

## What Was Built

### Task 1: england_1216.yaml + missing-inputs tests (0f9e695)

- `data/regions/england_1216.yaml`: 45-line template, bounds `lon_min=-6.0, lon_max=2.0, lat_min=49.5, lat_max=56.0`, `display_name: "England 1216 AD"` (R-06), dataset referencing `inputs/england_municipalities.geojson` (intentionally absent per D-12). No `data/regions/england_1216/` directory created.
- `backend/tests/unit/test_england_1216_missing_inputs.py`: replaced Wave-0 `pytest.skip` placeholder with two tests:
  - `test_load_region_england_raises_filenotfound`: calls `load_region('england_1216')`, asserts `FileNotFoundError` message contains region key + missing-path hint
  - `test_regions_endpoint_marks_england_no_dataset`: exercises `GET /api/v3/regions` (Plan 05-07), asserts `england_1216` present with `has_dataset: false`

## Verification

```
pytest backend/tests/unit/test_england_1216_missing_inputs.py -q
→ 2 passed in 0.06s

pytest backend/tests/parity/test_iberia_868_yaml.py -q
→ 11 passed in 34.70s (parity gate unchanged)

python -c "import yaml; doc=yaml.safe_load(open('data/regions/england_1216.yaml')); assert doc['lon_min']==-6.0 and doc['lat_max']==56.0; print('OK')"
→ OK

test -d data/regions/england_1216 && echo EXISTS || echo OK_ABSENT
→ OK_ABSENT

grep -nE "^display_name:" data/regions/england_1216.yaml data/regions/france_1066.yaml
→ 2 matches (R-06 combined grep green)
```

## Deviations from Plan

None — plan executed exactly as written.

The plan's terse YAML snippet omitted `ocean_*`, `coast_*`, `mountain_*`, `river_*` blocks. These were included explicitly (mirroring `france_1066.yaml`) for schema completeness and consistency with the established template pattern. Pydantic schema has defaults so technically optional, but explicit is better.

## Known Stubs

None — YAML-only template is intentional by design (D-12). The missing inputs are not a stub; they are the feature being tested.

## Threat Surface

T-05-09-01: YAML-only template — no new attack surface. The loader's path-traversal guard (Plan 05-01 T-05-01-03) protects against any future edits that add malicious dataset paths.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `data/regions/england_1216.yaml` exists | FOUND |
| `test -d data/regions/england_1216` prints `OK_ABSENT` | CONFIRMED |
| YAML `lon_min==-6.0 and lat_max==56.0` assertion | PASSED |
| `grep display_name` both YAMLs ≥2 matches | FOUND (2 matches) |
| 2 unit tests passing | PASSED |
| Parity gate 11/11 green | PASSED |
| Commit 0f9e695 | FOUND |
