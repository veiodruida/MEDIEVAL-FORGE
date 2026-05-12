---
phase: "05"
plan: "03"
subsystem: "backend/pipeline"
tags: [parity, region-loader, yaml, tdd, bug-fix]
dependency_graph:
  requires:
    - phase: "05-01"
      provides: "load_region API, clear_region_cache"
    - phase: "05-02"
      provides: "data/regions/iberia_868.yaml"
  provides:
    - "D-14 parity gate: test_iberia_868_yaml.py (11 non-skippable tests)"
    - "_convert_territory_data in region_loader.py"
  affects:
    - "backend/medieval_forge/services/pipeline/region_loader.py"
    - "backend/tests/parity/test_iberia_868_yaml.py"
tech_stack:
  added: []
  patterns:
    - "Session-scoped pipeline_output_yaml fixture (mirrors legacy pipeline_output)"
    - "list[dict] → tuple/dict pipeline conversion in region_loader"
key_files:
  created: []
  modified:
    - "backend/tests/parity/test_iberia_868_yaml.py (scaffold → 11 parity tests)"
    - "backend/medieval_forge/services/pipeline/region_loader.py (_convert_territory_data + kingdom_colors int key fix)"
decisions:
  - "_convert_territory_data added to region_loader.py (not deferred): load_region must produce voronoi-compatible shapes before any parity test can pass"
  - "kingdom_colors keys converted int(k) (str→int): render.py indexes with integer ki; YAML emits str keys by pydantic contract"
  - "pipeline_output_yaml fixture is module-level override (session-scoped), not conftest — mirrors legacy pattern with distinct mktemp name"
metrics:
  duration: "~30 minutes"
  completed: "2026-05-12"
  tasks_completed: 1
  tasks_total: 1
  files_created: 0
  files_modified: 2
  tests_added: 11
requirements-completed: [SC-1]
---

# Phase 05 Plan 03: YAML Parity Gate Summary

**One-liner:** D-14 hard parity gate (`test_iberia_868_yaml.py`, 11 tests) proving YAML-loaded cfg produces byte-equal lookup PNGs + SSIM≥0.98 visual PNGs + deep-equal JSONs vs the Phase 01 golden set.

## What Was Built

### Task 1: Implement test_iberia_868_yaml.py + fix region_loader (fa139d0)

**test_iberia_868_yaml.py** — 11 non-skippable `@pytest.mark.parity` tests:
- `test_lookup_png_byte_equal_yaml` (×2): `lookup_barony.png`, `lookup_condado.png` — `numpy.array_equal` byte comparison
- `test_visual_png_ssim_yaml` (×4): `visual_condado.png`, `visual_barony.png`, `mountains_mask.png`, `rivers_overlay.png` — SSIM ≥ 0.98
- `test_json_deep_equal_yaml` (×4): all four contract JSONs — recursive key-sort + deep equality
- `test_canvas_sidecars_exist_yaml` (×1): canvas sidecars present and non-empty

Session-scoped `pipeline_output_yaml` fixture defined inline (module-level override of conftest's `pipeline_output`):
- calls `clear_region_cache()` + `load_region("iberia_868")` + `cfg.output_dir = str(out)` + `run_pipeline(cfg)`

**region_loader.py** — two bugs fixed (Rule 1 deviations):

1. `_convert_territory_data`: new function converting `list[dict]` territory data from YAML/pydantic into the `dict/tuple` shapes `voronoi.py:setup_baronies` expects (`c[4]`/`c[5]` positional access, `duchies.keys()`, etc.)
2. `kingdom_colors` key conversion: `int(k)` instead of passthrough `k` — `render.py` indexes with integer `ki`; YAML/pydantic emits str keys; str-keyed dict caused all kingdoms to use fallback grey `(128,128,128)` color → SSIM 0.954 failure

## Verification

```
pytest backend/tests/parity/test_iberia_868_yaml.py -q
→ 11 passed in 34.73s

pytest backend/tests/parity/test_iberia_868.py -q
→ 11 passed in 34.56s  (D-17 invariant: both gates green simultaneously)

pytest backend/tests/unit/ -q
→ 130 passed, 1 skipped  (no regressions)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Missing `_convert_territory_data` in region_loader.py**
- **Found during:** Task 1 (probe before writing test)
- **Issue:** `load_region('iberia_868')` returned `cfg.condados` as `list[dict]` and `cfg.duchies`/`cfg.kingdoms` as `list[dict]`; `voronoi.py:setup_baronies` calls `duchies.keys()` and indexes `c[4]`/`c[5]` positionally — would raise `AttributeError` / `TypeError` and pipeline would produce different output
- **Root cause:** Plan 05-01 left conversion deferred to "Plan 05-04", but RESEARCH Pitfall 3 explicitly required it in the loader; the test couldn't pass without it
- **Fix:** Added `_convert_territory_data(kingdoms_raw, duchies_raw, condados_raw)` that converts `list[dict]` → `dict[str,str]` / `dict[str,tuple]` / `list[tuple]` matching voronoi.py's expectations
- **Files modified:** `backend/medieval_forge/services/pipeline/region_loader.py`
- **Commit:** fa139d0

**2. [Rule 1 - Bug] `kingdom_colors` string keys instead of int keys**
- **Found during:** Task 1 (SSIM 0.954 failure, `visual_condado.png` and `visual_barony.png`)
- **Issue:** YAML/pydantic `dict[str, list[int]]` contract emits string keys (`"0"`, `"1"`, ...); `render.py:66,79` calls `cfg.kingdom_colors.get(ki, ...)` with integer `ki` (kingdom index from numpy array); string-keyed lookup always misses → all kingdoms rendered grey `(128,128,128)` → visible color difference
- **Fix:** Changed `kingdom_colors` conversion from `{k: tuple(v) ...}` to `{int(k): tuple(v) ...}`
- **Files modified:** `backend/medieval_forge/services/pipeline/region_loader.py`
- **Commit:** fa139d0 (same commit — both fixes are in region_loader.py)

## Known Stubs

None — 11 tests all exercise the real pipeline end-to-end with no mocks.

## Threat Surface

T-05-03-01 (accept): test-only code, no production attack surface added.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| test_iberia_868_yaml.py exists | FOUND |
| grep load_region → ≥1 match | FOUND (lines 28, 42) |
| grep skip\|xfail → 0 matches | CONFIRMED 0 matches |
| grep pytest.mark.parity → ≥1 match | FOUND (line 30) |
| pytest test_iberia_868_yaml.py -q → 11 passed | PASSED |
| pytest test_iberia_868.py -q → 11 passed | PASSED |
| pytest tests/unit/ -q → 130 passed | PASSED |
| Commit fa139d0 exists | FOUND |
