---
phase: 02
plan: 02
subsystem: pipeline-ingestion-adapters
tags: [adapters, osm, terrain, ingestion, wrap-not-rewrite, split-by-iso]
requires:
  - phase-02-plan-01 (ProjectDataset @dataclass + cfg.dataset migration)
provides:
  - services/pipeline/adapters/ subpackage (__init__, base, osm, terrain)
  - build_dataset_from_osm (live OSM → ProjectDataset)
  - build_terrain (D-13 stub passthrough)
  - _split_by_iso (representative-point partition helper)
  - _validate_bbox (T-DOS guard, ≤30°/axis)
  - project_inputs_dir (D-07 self-contained inputs/ creation)
affects:
  - backend/medieval_forge/services/pipeline/adapters/__init__.py
  - backend/medieval_forge/services/pipeline/adapters/base.py
  - backend/medieval_forge/services/pipeline/adapters/osm.py
  - backend/medieval_forge/services/pipeline/adapters/terrain.py
  - backend/tests/unit/adapters/__init__.py
  - backend/tests/unit/adapters/conftest.py
  - backend/tests/unit/adapters/test_osm_split.py
  - backend/tests/unit/adapters/test_terrain_passthrough.py
tech-stack:
  added: []
  patterns:
    - "wrap-not-rewrite (D-05 / ROADMAP-02#3) — adapter imports fetch_municipalities, never modifies it"
    - "representative_point partition (Pitfall A3 — concave-safe vs centroid)"
    - "self-contained inputs/ creation (D-07 — adapter owns its dir, paths.py untouched)"
    - "stub passthrough (D-13 — slot reserved, not computed)"
    - "source-level forbidden-import guard via inspect.getsource (test_terrain_passthrough)"
key-files:
  created:
    - backend/medieval_forge/services/pipeline/adapters/__init__.py
    - backend/medieval_forge/services/pipeline/adapters/base.py
    - backend/medieval_forge/services/pipeline/adapters/osm.py
    - backend/medieval_forge/services/pipeline/adapters/terrain.py
    - backend/tests/unit/adapters/__init__.py
    - backend/tests/unit/adapters/conftest.py
    - backend/tests/unit/adapters/test_osm_split.py
    - backend/tests/unit/adapters/test_terrain_passthrough.py
  modified: []
decisions:
  - "D-05 implemented: adapters/osm.py imports fetch_municipalities — wraps, doesn't rewrite"
  - "D-07 implemented: build_dataset_from_osm writes to projects/<uuid>/inputs/; adapter creates the dir self-contained"
  - "D-13 implemented: build_terrain returns vendored mountain_river_data.json Path; ingest_terrain/ untouched"
  - "D-15 honored by absence: no ingest_wikidata import in any adapter file"
  - "D-16 honored by absence: no CLI subcommand introduced"
  - "Subpackage layout: 4-file flat split (osm.py + terrain.py + base.py + __init__.py)"
  - "representative_point chosen over centroid (Pitfall A3 — concave coastline safety)"
metrics:
  duration: ~12min
  completed: 2026-05-08
  tasks_total: 2
  tasks_completed: 2
  files_created: 8
  files_modified: 0
  unit_tests_added: 11
  unit_tests_passing: 11
  parity_pre_commit: "10/10 green"
  parity_post_commit: "10/10 green"
  combined_wave_merge: "21/21 green (11 unit adapters + 10 parity)"
requirements:
  - ROADMAP-02#3
---

# Phase 02 Plan 02: Ingestion Adapters Summary

Built the `services/pipeline/adapters/` subpackage that converts live OSM
ingestion (and a stub terrain pass) into a `ProjectDataset` the v3 pipeline
can consume. Implements ROADMAP-02#3 ("wrap, don't rewrite") with two atomic
commits (one per task) and zero modifications to the existing v1 ingestion
modules.

## What was built

### Subpackage layout (4-file flat split)

- **`adapters/__init__.py`** — public surface: `build_dataset_from_osm`,
  `build_terrain`. Two-line import block that exposes the OSM and terrain
  entry points.
- **`adapters/base.py`** — shared helpers: `project_inputs_dir(project_id)`
  creates `projects/<uuid>/inputs/` self-contained (T-PATH validation +
  `mkdir(parents=True, exist_ok=True)`) and re-exports `_write_geojson_atomic`
  from `services/ingest_runner.py`.
- **`adapters/osm.py`** — `build_dataset_from_osm` wraps
  `ingest_osm.fetch_municipalities` (D-05); `_split_by_iso` partitions a
  combined PT+ES FC by representative-point-in-buffered-country-polygon (NEW
  logic — `_clip_features_to_countries` is a union filter, not a partition);
  `_validate_bbox` enforces 4-tuple shape, numeric type, valid lat/lon order,
  and ≤30°/axis span (T-DOS). 158 lines.
- **`adapters/terrain.py`** — `build_terrain(project_id)` returns the vendored
  `data/regions/iberia_868/inputs/mountain_river_data.json` Path. No
  DEM/HydroSHEDS/ridges work; `services/ingest_terrain/` is untouched (D-13).
  31 lines.

### Decision coverage

| Decision | Status | Implementation |
|----------|--------|----------------|
| D-01 (cfg.dataset → ProjectDataset port) | DONE (Plan 01) | `build_dataset_from_osm` returns `ProjectDataset` with the two written `.geojson` paths + vendored `mountain_river_data.json` |
| D-05 (wrap, don't rewrite) | DONE | `osm.py` imports `fetch_municipalities`; grep for `from medieval_forge.services.ingest_osm import fetch_municipalities` returns 1; `git diff HEAD -- ingest_osm.py overpass_client.py ingest_terrain/ ingest_wikidata.py` returns empty |
| D-07 (output dir = projects/<uuid>/inputs/) | DONE | `project_inputs_dir(project_id)` validates UUID, creates dir, returns `Path` |
| D-12 (post-adapter snapshot, not raw Overpass) | HONORED | Unit tests use synthetic FeatureCollection in `conftest.py`, NOT a captured Overpass JSON |
| D-13 (terrain stub passthrough) | DONE | `build_terrain` returns vendored `Path`; source contains zero `ingest_terrain` imports (verified by grep AND `inspect.getsource` test) |
| D-15 (no Wikidata wrapper) | HONORED BY ABSENCE | `grep -r "ingest_wikidata" backend/medieval_forge/services/pipeline/adapters/` returns 0 |
| D-16 (no new CLI) | HONORED BY ABSENCE | No `argparse`/`click`/`@cli.command` calls in any adapter file; no entry point registered |

D-02..D-04, D-06, D-08 (Plan 01); D-09..D-11, D-14 (Plans 03+) are scoped
elsewhere and not touched here.

## Why representative_point not centroid (Pitfall A3)

The OSM adapter routes each feature to its country by testing whether a
representative point of the polygon falls inside the buffered Natural Earth
country polygon. **Shapely's `representative_point()` is guaranteed to lie
inside the geometry**, even for concave shapes (think: an L-shaped or
peninsular municipality). `centroid` can fall outside the polygon when the
shape is non-convex. Using `centroid` for partition would silently misroute
coastal/peninsular concelhos at the PT/ES border.

The 0.025° buffer matches `ingest_osm._COUNTRY_BUFFER_DEG` — absorbs the ~1-2
km Natural Earth coastline imprecision so coastal municipalities (Lisboa,
Funchal) are not dropped.

## Live wave-merge result

**`pytest backend/tests/unit/adapters/ backend/tests/parity/`: 21 passed in
34.69s.**

- 7 OSM split tests (split routes PT-only / drops Atlantic / handles
  MultiPolygon / unknown ISO returns empty / writes 2 .geojson files / bbox
  validation 3-shape + non-numeric + >30° / UUID guard).
- 4 terrain stub tests (returns vendored Path / Path exists on disk /
  source-level guard against ingest_terrain imports / UUID validation).
- 10 Phase 01 parity tests — UNCHANGED, all green pre and post commits
  (verified twice: before Task 1 and after Task 2).

## Acceptance Criteria Verification

### Task 1 (OSM adapter)

| Criterion | Result |
|-----------|--------|
| `adapters/{__init__.py, base.py, osm.py}` exist | PASS |
| `from ...adapters import build_dataset_from_osm; from ...adapters.osm import _split_by_iso` works | PASS (`OK` printed) |
| `grep "from medieval_forge.services.ingest_osm import fetch_municipalities" osm.py` ≥1 | PASS (1) |
| `grep "ingest_wikidata\|ingest_terrain" osm.py` = 0 | PASS (0) |
| `pytest backend/tests/unit/adapters/test_osm_split.py -v` reports 7 passed | PASS |
| Phase 01 parity 10/10 unchanged | PASS |
| No new entries in `requirements.txt`/`pyproject.toml` | PASS |

### Task 2 (terrain stub)

| Criterion | Result |
|-----------|--------|
| `adapters/terrain.py` exists with `build_terrain` | PASS |
| `build_terrain.__module__` = `medieval_forge.services.pipeline.adapters.terrain` | PASS |
| `grep "ingest_terrain\|dem\.\|hydrosheds\|ridges" terrain.py` = 0 | PASS (0) |
| `pytest backend/tests/unit/adapters/test_terrain_passthrough.py -v` reports 4 passed | PASS |
| `git diff HEAD -- services/ingest_terrain/` empty | PASS |
| Wave-merge gate (adapters + parity) all green | PASS (21/21) |

## Deviations from Plan

### 1. [Rule 1 - Bug] Task 1 `__init__.py` cannot import `build_terrain` before Task 2 lands

- **Found during:** Task 1, post-write — Task 1 unit test collection failed with
  `ModuleNotFoundError: No module named '...adapters.terrain'`.
- **Issue:** The plan's Task 1 `__init__.py` literal imports `from .terrain
  import build_terrain`, but `terrain.py` is created in Task 2. As written,
  Task 1's atomic commit would land a broken package (any consumer of
  `services.pipeline.adapters` would `ImportError`).
- **Fix:** Task 1 `__init__.py` exports only `build_dataset_from_osm`. Task 2
  edits the `__init__.py` to add the `from .terrain import build_terrain`
  import + extend `__all__` (a 2-line diff committed alongside `terrain.py`
  in `b6f1c12`).
- **Files modified:** `adapters/__init__.py` in both commits (additive
  one-line edit in Task 2).
- **Commits:** `81cdcc2` (Task 1 — single export); `b6f1c12` (Task 2 — added
  the second export).

This keeps each commit individually green and preserves the spirit of the
plan's "atomic commit per task" rule. Final post-Task-2 `__init__.py` matches
the plan's literal target verbatim.

### 2. [Rule 1 - Plan ambiguity] Wave-merge gate marker `-m "unit or parity"` deselects the new tests

- **Found during:** Task 2, wave-merge gate verification.
- **Issue:** Plan's verify command is `pytest backend/tests/unit/adapters/
  backend/tests/parity/ -m "unit or parity"`. The pyproject.toml registers
  only `slow`, `parity`, `integration`, `uat` markers — there is no `unit`
  marker. Running with `-m "unit or parity"` selects only the 10 parity tests
  (the new 11 unit tests have no marker and are deselected). Running without
  the marker filter selects all 21 expected tests (11 + 10) and reports them
  all green.
- **Fix:** Reported the wave-merge result without the marker filter (21/21).
  Did NOT add a `unit` marker to pyproject.toml — that's outside this plan's
  scope and could affect other test files. Suggesting Phase 02 Plan 03 (live
  parity) is a more natural place for marker registration if needed.
- **Files modified:** None.
- **Commits:** N/A (verification-only deviation).

The substantive criterion (combined unit adapters + parity all green) is
satisfied; only the literal command in the plan was suboptimal.

## Self-Check: PASSED

Verified post-write:
- FOUND: backend/medieval_forge/services/pipeline/adapters/__init__.py
- FOUND: backend/medieval_forge/services/pipeline/adapters/base.py
- FOUND: backend/medieval_forge/services/pipeline/adapters/osm.py
- FOUND: backend/medieval_forge/services/pipeline/adapters/terrain.py
- FOUND: backend/tests/unit/adapters/__init__.py
- FOUND: backend/tests/unit/adapters/conftest.py
- FOUND: backend/tests/unit/adapters/test_osm_split.py
- FOUND: backend/tests/unit/adapters/test_terrain_passthrough.py
- FOUND commit 81cdcc2: `feat(02-02): add OSM adapter (build_dataset_from_osm + split-by-ISO)`
- FOUND commit b6f1c12: `feat(02-02): add terrain stub adapter (D-13 passthrough)`
- Phase 01 parity: 10/10 green (37.59s)
- Plan 02 unit tests: 11/11 green (Task 1: 7; Task 2: 4)
- Combined wave: 21/21 green
