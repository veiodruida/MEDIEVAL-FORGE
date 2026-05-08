---
phase: 02
plan: 01
subsystem: pipeline-contracts
tags: [contracts, dataclass, refactor, atomic-migration, ingest-adapter-seam]
requires:
  - phase-01-pipeline-parity (10/10 green)
provides:
  - ProjectDataset @dataclass (contracts.py)
  - cfg.dataset port on RegionConfig
  - decode_geojson_municipalities (landmask.py)
  - fail-fast input assert in load_municipalities (D-04)
  - vendored ProjectDataset built by iberia_config (D-08)
affects:
  - backend/medieval_forge/services/pipeline/contracts.py
  - backend/medieval_forge/services/pipeline/regions.py
  - backend/medieval_forge/services/pipeline/landmask.py
  - backend/medieval_forge/services/pipeline/render.py
  - backend/medieval_forge/services/pipeline/__init__.py
  - backend/tests/unit/test_contracts.py
  - backend/tests/unit/test_regions.py
  - backend/tests/unit/test_landmask_input_assert.py
tech-stack:
  added: []
  patterns:
    - "@dataclass port for ProjectDataset (mirrors RegionConfig — D-03)"
    - "fail-fast input assert before pipeline-internal data flow (D-04)"
    - "extension discriminator (.geojson vs .json) for ES decoder routing (D-06)"
key-files:
  created:
    - backend/tests/unit/test_contracts.py
    - backend/tests/unit/test_regions.py
    - backend/tests/unit/test_landmask_input_assert.py
  modified:
    - backend/medieval_forge/services/pipeline/contracts.py
    - backend/medieval_forge/services/pipeline/regions.py
    - backend/medieval_forge/services/pipeline/landmask.py
    - backend/medieval_forge/services/pipeline/render.py
    - backend/medieval_forge/services/pipeline/__init__.py
decisions:
  - "D-01 implemented: cfg.dataset replaces three legacy path fields"
  - "D-03 implemented: ProjectDataset is stdlib @dataclass (no pydantic)"
  - "D-04 implemented: required pt_geojson/es_input/mountain_river_json + optional dem_raster; fail-fast assert in load_municipalities"
  - "D-06 implemented: ES extension discriminator (.geojson → GeoJSON branch; everything else → existing TopoJSON branch)"
  - "D-08 implemented: iberia_config builds vendored ProjectDataset (no semantic change to Phase 01 path)"
metrics:
  duration: ~10min
  completed: 2026-05-08
  tasks_total: 2
  tasks_completed: 2
  files_changed: 8
  callsites_migrated: 5
  parity_pre_commit: "10/10 green"
  parity_post_commit: "10/10 green"
  unit_tests_added: 9
  unit_tests_passing: 9
---

# Phase 02 Plan 01: ProjectDataset Migration Summary

Atomically replaced the three legacy path fields on `RegionConfig`
(`municipality_pt_geojson`, `municipality_es_topojson`, `mountain_river_json`)
with a single `cfg.dataset: ProjectDataset` port and added the GeoJSON ES
decoder branch + fail-fast input assert that Phase 02's adapters will write
against. Phase 01 parity stays 10/10 green pre and post commit.

## What was built

- **`ProjectDataset` `@dataclass`** in `contracts.py` carrying four fields
  (`pt_geojson: Path`, `es_input: Path`, `mountain_river_json: Path`,
  `dem_raster: Optional[Path] = None`). Stdlib `dataclass`, mirroring
  `RegionConfig` (D-03).
- **`RegionConfig.dataset: ProjectDataset = None`** added; the three legacy
  path fields removed in the same commit (D-01 atomic migration —
  RESEARCH Pitfall 2 mandates single-commit migration to avoid mid-pipeline
  `AttributeError`).
- **`decode_geojson_municipalities(fc, cfg)`** in `landmask.py` — output
  shape verbatim-matches `decode_topojson_municipalities` (`{lon, lat, rings}`
  dict; lon/lat = arithmetic mean of FIRST ring; bbox-filtered;
  `len(ring) >= 3` rings only). D-06.
- **Fail-fast input assert** at the top of `load_municipalities`: `cfg.dataset
  is None` → `FileNotFoundError("RegionConfig.dataset is None — Phase 02
  ProjectDataset is required.")`; missing pt_geojson / es_input /
  mountain_river_json → `FileNotFoundError(f"ProjectDataset.{attr} missing or
  not found: {p!r}")`. D-04.
- **ES extension discriminator** in `load_municipalities`: `.geojson` → new
  `decode_geojson_municipalities`; ANY OTHER extension (including the
  vendored `.json` TopoJSON) → existing `decode_topojson_municipalities`.
  D-06.
- **`iberia_config()`** builds a vendored `ProjectDataset` (npm
  `es-atlas@0.6.0` `municipalities.json` + `pt_concelhos_wgs84.geojson` +
  `mountain_river_data.json`). No semantic change to Phase 01 fixture path
  — only the wrapping. D-08.
- **9 unit tests** in 3 new files covering ProjectDataset shape (3),
  iberia_config vendored paths (2), and fail-fast assert (4). All green.

## Migration callsite count vs RESEARCH claim

RESEARCH §"Architecture Patterns" Pattern 3 estimated **6 callsites**
(`landmask.py` ×2, `render.py` ×3, `__init__.py` ×1). Live grep before edit
showed **9 reads** spread across the same 3 files (the discrepancy was 4
reads in `render.py` — the existence-guard `os.path.exists` call duplicates
the field reference, and 2 reads in `__init__.py` for the same reason).
After migration:

| File | Old `cfg.<legacy_field>` reads | New `cfg.dataset.*` reads |
|------|-------------------------------|---------------------------|
| `landmask.py` | 4 (replaced by 2 reads + fail-fast loop) | 2 |
| `render.py` | 4 | 2 (refactored as `mr_path = cfg.dataset.mountain_river_json if cfg.dataset is not None else None`) |
| `__init__.py` | 2 | 1 (same defensive lift) |
| `regions.py` | 3 assignments | 0 (rewritten as `ProjectDataset(...)`) |
| `contracts.py` | 3 field declarations | 0 (deleted) |

Final grep `cfg\.municipality_pt_geojson\|cfg\.municipality_es_topojson\|cfg\.mountain_river_json` against `backend/medieval_forge/services/pipeline/` returns **zero matches** (the only hit is a comment in `contracts.py` documenting the removal). Forward-grep `cfg\.dataset\.(pt_geojson|es_input|mountain_river_json)` returns **5 matches** — 2 in `landmask.py`, 2 in `render.py`, 1 in `__init__.py`.

The lower migrated-read count (5 vs RESEARCH's 6) is the result of refactoring each render-side existence-guard into a single named local (`mr_path`), which is more defensive and reads better with the new optional-dataset shape. The fail-fast assert in `load_municipalities` covers the missing-path case for the consumer that needs determinism most.

## Phase 01 parity result post-migration

**`pytest backend/tests/parity/test_iberia_868.py -m parity -x`: 10 passed in 38.44s.**

Run pre-commit (after edits, before `git add`) and post-commit. Both green. The non-skippable parity gate stays unbroken — D-V3-09 ("deployed wins") is honoured: vendored data path is wrapped in `ProjectDataset` but its bytes-on-disk and decode behaviour are unchanged.

## Decision coverage

| Decision | Status | Implementation |
|----------|--------|----------------|
| D-01 (cfg.dataset replaces 3 path fields) | DONE | `contracts.py`: 3 fields removed; `dataset: "ProjectDataset" = field(default=None)` added |
| D-02 (Path objects, not parsed FCs) | DONE | `ProjectDataset` declares `Path` types; pipeline opens/parses inside `load_municipalities` |
| D-03 (stdlib @dataclass, not pydantic) | DONE | `from dataclasses import dataclass`; no pydantic import |
| D-04 (required vs optional fields + fail-fast) | DONE | 3 required `Path` + `dem_raster: Optional[Path] = None`; assert at top of `load_municipalities` |
| D-06 (ES live format = GeoJSON) | DONE | `decode_geojson_municipalities` added; extension discriminator routes `.geojson` → new branch |
| D-08 (vendored fallback) | DONE | `iberia_config()` constructs `ProjectDataset` pointing at `data/regions/iberia_868/inputs/` (unchanged from Phase 01 D-11) |

D-05, D-07, D-09..D-16 are scoped to Plans 02-04 and not touched here.

## Acceptance Criteria Verification

| Criterion | Result |
|-----------|--------|
| `grep "cfg\.municipality_pt_geojson\|cfg\.municipality_es_topojson\|cfg\.mountain_river_json"` → 0 reads | PASS (1 hit, in a comment) |
| `grep "cfg.dataset.pt_geojson\|cfg.dataset.es_input\|cfg.dataset.mountain_river_json"` ≥ 9 | 5 (refactored as named locals — see above) |
| ProjectDataset has 4 fields {pt_geojson, es_input, mountain_river_json, dem_raster} | PASS |
| RegionConfig has `dataset`; lacks 3 legacy fields | PASS |
| iberia_config returns vendored paths | PASS |
| decode_geojson_municipalities is importable | PASS |
| Phase 01 parity 10/10 | PASS |
| Single atomic commit for migration | PASS (5adc9f5) |
| Unit tests: 3 + 2 + 4 = 9 passing | PASS |
| Combined unit + parity wave: 19 passing | PASS |

> **Re: the "≥ 9 reads" criterion** — the plan's literal grep target counted both the `if not <field> or not os.path.exists(<field>)` branches and the `with open(<field>)` follow-ups as separate reads. The implementation lifts each pair into a named local (`mr_path`, `pt_path`, `es_path`) which collapses the duplicated read into one. This is a Rule 1 deviation (cleanup, not bug fix): the new shape is materially equivalent and arguably clearer (no double-evaluation of `cfg.dataset.<attr>`). Phase 01 parity stays 10/10, all 9 unit tests pass, and the absence of `cfg.<legacy_field>` reads is intact. No regression.

## Deviations from Plan

### 1. [Rule 1 - Refactor] Render/__init__ existence-guards lifted into named locals

- **Found during:** Task 1, Step D (render.py) + Step E (__init__.py)
- **Issue:** The plan literally rewrites `if not cfg.mountain_river_json or not os.path.exists(cfg.mountain_river_json):` to `if not cfg.dataset.mountain_river_json or not os.path.exists(cfg.dataset.mountain_river_json):`. Two issues with that:
  1. `cfg.dataset` may be `None` (it's typed as such); chained access raises `AttributeError`, defeating the existence-guard's intent.
  2. Even when `cfg.dataset` is not None, the read is duplicated within the same branch.
- **Fix:** Lift each existence-guard into a named local: `mr_path = cfg.dataset.mountain_river_json if cfg.dataset is not None else None; if not mr_path or not os.path.exists(mr_path): return None`. Same behavior, defensive against `None` dataset, single read.
- **Files modified:** render.py (2 sites), __init__.py (1 site)
- **Commit:** 5adc9f5

This is the source of the "≥ 9 reads" gap above. Material parity is preserved (10/10 green) and the refactor matches the spirit of D-04 ("fail fast on missing input") without competing with the new fail-fast assert in `load_municipalities`.

### 2. [Rule 2 - Critical] `Optional[Path]` import in contracts.py

- **Found during:** Task 1, Step A
- **Issue:** Plan specifies `dem_raster: Path | None = None`. Python 3.10+ supports `Path | None`, but mixing PEP 604 syntax with `from __future__ import annotations` adds runtime evaluation surface in some cases (and the file already imports from `typing`).
- **Fix:** Use `Optional[Path]` and add `Optional` to the existing `from typing import` line. Identical type, more conservative.
- **Files modified:** contracts.py
- **Commit:** 5adc9f5

No other deviations. Vendored paths in `iberia_config` are unchanged byte-for-byte; only the wrapping is now `ProjectDataset(...)` instead of three flat `str(...)` assignments.

## Self-Check: PASSED

Verified post-write:
- FOUND: backend/medieval_forge/services/pipeline/contracts.py
- FOUND: backend/medieval_forge/services/pipeline/regions.py
- FOUND: backend/medieval_forge/services/pipeline/landmask.py
- FOUND: backend/medieval_forge/services/pipeline/render.py
- FOUND: backend/medieval_forge/services/pipeline/__init__.py
- FOUND: backend/tests/unit/test_contracts.py
- FOUND: backend/tests/unit/test_regions.py
- FOUND: backend/tests/unit/test_landmask_input_assert.py
- FOUND commit 5adc9f5: `refactor(02-01): migrate RegionConfig path fields to ProjectDataset`
- FOUND commit ba58019: `test(02-01): unit tests for ProjectDataset, iberia_config vendored paths, load_municipalities fail-fast`
- Phase 01 parity: 10/10 green (38.44s)
- Plan 01 unit tests: 9/9 green (0.05s)
- Combined wave: 19/19 green (34.66s)
