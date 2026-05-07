---
phase: 01-pipeline-parity-port-harness-together
plan: 01
subsystem: pipeline-scaffold
tags: [pipeline, regionconfig, dataclass, lfs, golden-fixtures, preflight, iberia_868]

# Dependency graph
requires:
  - phase: 00-archive-v1-bootstrap-v3
    provides: pyproject (parity marker, packages.find), inicio reference, CI scaffold
provides:
  - PREFLIGHT.md verdicts (P-1 original_idx ABSENT; Q10 draw_names False)
  - 11-file golden fixture snapshot at tests/fixtures/iberia_868/golden/
  - 3 pipeline inputs at data/regions/iberia_868/inputs/ with LFS for the 28 MB PT GeoJSON
  - In-package territory data at backend/medieval_forge/data/regions/iberia_868/territory_data.py
  - 9-submodule pipeline package skeleton with RegionConfig + iberia_config + REGIONS + CLI shim
affects: [01-02-PLAN, 01-03-PLAN, Plan 02 verbatim port]

# Tech tracking
tech-stack:
  added: [git-lfs (3.7.1), es-atlas npm 0.6.0]
  patterns:
    - "RegionConfig as @dataclass (not pydantic) — drift-from-inicio is the hard cost"
    - "REGIONS = {region_id: factory_callable} — D-04 factory pattern, swappable to YAML in Phase 05"
    - "Territory data lives on cfg (kingdoms/duchies/condados) — D-14 single-mutable-input invariant"
    - "rng_seed promoted from hardcoded 42 to cfg.rng_seed — CLAUDE.md determinism rule"
    - "Pipeline inputs at repo-root data/, golden fixtures at tests/fixtures/, territory code in-package — clean separation of large data, ground truth, and importable code"

key-files:
  created:
    - .planning/phases/01-pipeline-parity-port-harness-together/PREFLIGHT.md
    - .gitattributes (LFS rule for PT GeoJSON)
    - data/regions/iberia_868/inputs/pt_concelhos_wgs84.geojson (LFS, 29 705 375 B)
    - data/regions/iberia_868/inputs/mountain_river_data.json (19 307 B)
    - data/regions/iberia_868/inputs/es-atlas-pkg/package/es/municipalities.json (1 821 999 B)
    - tests/fixtures/iberia_868/golden/{lookup_barony,lookup_condado,visual_condado,visual_barony,mountains_mask,rivers_overlay}.png (~1.18 MB total)
    - tests/fixtures/iberia_868/golden/{lookup_barony_colors,lookup_condado_colors,territory_metadata,mountain_river_data}.json
    - tests/fixtures/iberia_868/golden/README.md
    - backend/medieval_forge/data/__init__.py
    - backend/medieval_forge/data/regions/__init__.py
    - backend/medieval_forge/data/regions/iberia_868/__init__.py
    - backend/medieval_forge/data/regions/iberia_868/territory_data.py (byte-identical copy of inicio/territory_data_v3.py)
    - backend/medieval_forge/services/pipeline/__init__.py
    - backend/medieval_forge/services/pipeline/__main__.py
    - backend/medieval_forge/services/pipeline/contracts.py (RegionConfig dataclass + §2 transform stubs)
    - backend/medieval_forge/services/pipeline/regions.py (REGIONS + iberia_config)
    - backend/medieval_forge/services/pipeline/{landmask,border,voronoi,cleanup,render,lookup,export}.py (stubs)
  modified:
    - .gitattributes (added LFS rule for the PT GeoJSON)

key-decisions:
  - "PREFLIGHT.md Q8 (P-1): original_idx is ABSENT in deployed territory_metadata.json (0/92 condados, 0/251 baronies) — port reproduces inicio verbatim; Nájera-bug fix deferred per D-09 (deployed wins)"
  - "PREFLIGHT.md Q10: draw_names = False — deployed visual_condado.png has no labels; matches v1 wrapper call-site, not inicio's __main__"
  - "PREFLIGHT.md Q11: ES TopoJSON sourced via 'npm pack es-atlas' v0.6.0 (shasum 4c926d9cba69bb129a148ad251adcd6c73ff01de) — Method A preferred for reproducibility"
  - "PREFLIGHT.md Q12: LFS configured (git-lfs 3.7.1 available) — PT GeoJSON tracked, regular pack stays light"
  - "RegionConfig border_polygon has 40 points (not 38 as plan claimed) — verbatim from inicio lines 132-143; both the plan acceptance criteria AND CLAUDE.md non-negotiable rule #3 mis-counted; verbatim port wins per D-01"

patterns-established:
  - "Git LFS for >5 MB binary inputs that survive verbatim through the pipeline"
  - "PREFLIGHT.md as the artefact for one-time external-source-of-truth inspections that gate downstream plans"
  - "Stub submodules (2 lines: docstring + __all__=[]) signal Plan 02 ownership without locking implementation details"

requirements-completed: [V3-PIPELINE-PARITY]

# Metrics
duration: 11min
completed: 2026-05-07
---

# Phase 01 Plan 01: Wave 0 Preflight + Scaffold Summary

**Resolved P-1 (`original_idx` ABSENT) and Q10 (`draw_names = False`), committed 11 golden fixtures + 3 LFS-backed inputs + in-package territory data, and laid down the 9-submodule pipeline skeleton with `@dataclass` RegionConfig + REGIONS factory registry — Plan 02's verbatim port can now start with every import path resolved.**

## Performance

- **Duration:** ~11 min
- **Started:** 2026-05-07T14:54:51Z
- **Completed:** 2026-05-07T15:06:15Z
- **Tasks:** 5/5
- **Files created:** 28 (1 PREFLIGHT.md + 11 fixtures + 3 inputs + 4 territory module + 11 pipeline submodules)
- **Files modified:** 1 (.gitattributes)

## Accomplishments

- **PREFLIGHT.md verdicts recorded** unambiguously: P-1 (`original_idx`) ABSENT — port reproduces inicio; Q10 (`draw_names`) False — explicit. Plan 02 has no remaining "is the deployed file shape X or Y?" doubt.
- **11-file golden snapshot** of `D:/Projetos_Jogo/Reconquista/Assets/StreamingAssets/Maps/` committed to `tests/fixtures/iberia_868/golden/` (~1.18 MB total). README documents the deferral of `terrain_lookup.png` + `terrain_types.json` to Phase 06 per Pitfall P-2.
- **3 pipeline inputs in-tree** under `data/regions/iberia_868/inputs/`: PT GeoJSON via Git LFS (29.7 MB), ES TopoJSON via `npm pack es-atlas@0.6.0` (1.74 MB), mountain_river_data.json (19 KB). Repo is now self-contained: clone + `pip install -e .` yields everything Plan 03's parity test needs.
- **Territory data moved into the package** at `backend/medieval_forge/data/regions/iberia_868/territory_data.py` — byte-identical copy of `inicio/territory_data_v3.py`. Importable via `from medieval_forge.data.regions.iberia_868.territory_data import KINGDOMS, DUCHIES, CONDADOS`. inicio source preserved (read-only gold standard).
- **9-submodule pipeline skeleton** wired: `RegionConfig` `@dataclass` (26 inicio fields + 5 new), `iberia_config()` populated from the static territory import, `REGIONS = {"iberia_868": iberia_config}` factory registry, `python -m medieval_forge.services.pipeline --help` works, `run_pipeline()` and the §2 transforms raise `NotImplementedError` until Plan 02.
- **FastAPI app still boots** (Phase 00 SC-6 invariant): `GET / → 200`, all 49 routes register; 57 unit tests still green; no regression from the scaffold.

## Task Commits

Each task was committed atomically:

1. **Task 1: Preflight verification (P-1 + Q10)** — `13864fa` (docs)
2. **Task 2: Source ES TopoJSON + commit pipeline inputs + LFS for PT GeoJSON** — `11fad14` (chore)
3. **Task 3: Snapshot Iberia 868 golden fixtures (10/12 files; terrain_lookup deferred)** — `e652281` (chore)
4. **Task 4: Move territory data into package (D-13)** — `513c353` (feat)
5. **Task 5: Scaffold pipeline package skeleton + RegionConfig + iberia_config** — `078bf1c` (feat)

## Files Created/Modified

### PREFLIGHT
- `.planning/phases/01-pipeline-parity-port-harness-together/PREFLIGHT.md` — Q8/Q10/Q11/Q12 verdicts with literal jq-equivalent output, npm package SHA, LFS configuration

### Inputs (D-11)
- `.gitattributes` — added LFS tracking line for PT GeoJSON
- `data/regions/iberia_868/inputs/pt_concelhos_wgs84.geojson` — 29 705 375 B, Git LFS
- `data/regions/iberia_868/inputs/mountain_river_data.json` — 19 307 B
- `data/regions/iberia_868/inputs/es-atlas-pkg/package/es/municipalities.json` — 1 821 999 B (npm `es-atlas@0.6.0`)

### Golden fixtures (D-10)
- `tests/fixtures/iberia_868/golden/lookup_barony.png` — 55 142 B
- `tests/fixtures/iberia_868/golden/lookup_condado.png` — 37 974 B
- `tests/fixtures/iberia_868/golden/lookup_barony_colors.json` — 5 094 B
- `tests/fixtures/iberia_868/golden/lookup_condado_colors.json` — 1 893 B
- `tests/fixtures/iberia_868/golden/territory_metadata.json` — 65 445 B
- `tests/fixtures/iberia_868/golden/visual_condado.png` — 465 894 B
- `tests/fixtures/iberia_868/golden/visual_barony.png` — 505 303 B
- `tests/fixtures/iberia_868/golden/mountains_mask.png` — 12 232 B
- `tests/fixtures/iberia_868/golden/rivers_overlay.png` — 47 324 B
- `tests/fixtures/iberia_868/golden/mountain_river_data.json` — 19 307 B (byte-identical to inputs/)
- `tests/fixtures/iberia_868/golden/README.md` — refresh policy + Phase 06 deferral note

### Territory data (D-13)
- `backend/medieval_forge/data/__init__.py` (empty package marker)
- `backend/medieval_forge/data/regions/__init__.py` (empty)
- `backend/medieval_forge/data/regions/iberia_868/__init__.py` (empty)
- `backend/medieval_forge/data/regions/iberia_868/territory_data.py` — byte-identical to `inicio/territory_data_v3.py` (4 KINGDOMS, 26 DUCHIES, 92 CONDADOS)

### Pipeline package skeleton (D-03 / D-04)
- `backend/medieval_forge/services/pipeline/__init__.py` — exports `run_pipeline` (raises NotImplementedError) + `RegionConfig`
- `backend/medieval_forge/services/pipeline/__main__.py` — argparse CLI: `--region {iberia_868}` `--out`
- `backend/medieval_forge/services/pipeline/contracts.py` — RegionConfig `@dataclass` with 26 inicio fields + 5 new (kingdoms, duchies, condados, rng_seed, draw_names) + §2 transform stubs
- `backend/medieval_forge/services/pipeline/regions.py` — REGIONS registry + `iberia_config()` factory loaded from in-package territory data
- `backend/medieval_forge/services/pipeline/{landmask,border,voronoi,cleanup,render,lookup,export}.py` — 7 stubs (docstring + `__all__ = []`)

## iberia_config() runtime values (Plan 02 reference)

| Field | Value |
|-------|------:|
| `name` | `"iberia"` |
| `map_w × map_h × upscale` | `1920 × 1080 × 2` |
| `lon_min, lon_max, lat_min, lat_max` | `-13.2, 8.2, 35.4, 44.6` |
| `lon_scale` (cos derivative) | `0.766044443118978` |
| `smooth_sigma` | `3.0` (range [3.0, 4.5]) |
| `median_passes` | `8` (kernel sequence 11,11,9,9,7,7,5,5 hardcoded inside cleanup_and_smooth) |
| `rng_seed` | `42` |
| `draw_names` | `False` (PREFLIGHT.md Q10) |
| `kingdoms / duchies / condados` | `4 / 26 / 92` (from in-package territory_data) |
| `border_polygon` | 40 points (verbatim from inicio:132-143) |
| `kingdom_colors` | 4 entries (Astúrias gold / Pamplona purple / Marca Hispânica pink / Emirato green) |
| `pt_duchies` | `{"d_portucale", "d_gharb", "d_fronteira"}` |
| `municipality_pt_geojson` | `data/regions/iberia_868/inputs/pt_concelhos_wgs84.geojson` |
| `municipality_es_topojson` | `data/regions/iberia_868/inputs/es-atlas-pkg/package/es/municipalities.json` |
| `mountain_river_json` | `data/regions/iberia_868/inputs/mountain_river_data.json` |

## Decisions Made

- **`@dataclass` (not pydantic) for RegionConfig** — confirms RESEARCH §2.b recommendation. Drift from inicio is the hard cost; pydantic earns nothing Phase 01 needs.
- **Q11 sourcing via `npm pack`** — preferred for reproducibility (npm pinning + shasum) over raw GitHub URL fetch. Recorded SHA in PREFLIGHT.md.
- **LFS over direct commit for PT GeoJSON** — git-lfs available locally; keeps regular pack light without forcing re-clones if the 29 MB blob ever rotates.
- **Defer terrain_lookup.png + terrain_types.json to Phase 06** — README in golden/ explicitly documents this; both files are in the 12-file Unity contract but inicio's pipeline never produces them. Reproducing them requires code beyond inicio's 944 lines (D-01 violation). Phase 06's export-validation gate is the right home.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] border_polygon length: plan claims 38 points, inicio source has 40**
- **Found during:** Task 5 (RegionConfig + iberia_config implementation)
- **Issue:** Plan acceptance criterion in 01-01-PLAN.md says `len(cfg.border_polygon) == 38`, and CLAUDE.md non-negotiable rule #3 references "the PT/ES border polygon (38 points)". Inspection of `inicio/map_generator.py:132-143` shows 40 tuples (10 lines × 4 entries). The verbatim port (D-01 mandate) requires 40 — the plan / CLAUDE.md count was incorrect.
- **Fix:** Copied all 40 tuples verbatim from inicio. Verified with `python -c "...assert len(cfg.border_polygon) == 40"`. Documented in this SUMMARY so Plan 02 doesn't trip the same expectation.
- **Files modified:** `backend/medieval_forge/services/pipeline/regions.py`
- **Verification:** `iberia_config().border_polygon[0] == (-9.50, 42.20)` and `[-1] == (-9.50, 42.20)` (closing point matches opening, polygon closed correctly).
- **Committed in:** `078bf1c` (Task 5 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in plan/CLAUDE.md acceptance criterion)
**Impact on plan:** No scope change. Plan 02's `voronoi.py` ray-cast (`point_in_polygon` against `cfg.border_polygon`) sees 40 points instead of 38 — pure inicio behavior. CLAUDE.md and the plan's acceptance criteria should be corrected upstream (suggested as a Phase 01 closing chore commit).

## Issues Encountered

- **`jq` not available in environment.** Workaround: used Python `json` module to perform the equivalent key inspection on the deployed `territory_metadata.json` and recorded the literal output in PREFLIGHT.md. The verdicts (Q8 + Q10) are reproducible via the `python -c "import json; ..."` snippet recorded in PREFLIGHT.md.
- **Visual inspection of `visual_condado.png`** completed via the multimodal `Read` tool (equivalent to opening in Windows Photos): the image showed kingdom-colour shading with thin condado borders and zero text overlay → `draw_names = False` confirmed.
- **CRLF warnings** for text files committed under `.gitattributes:* text=auto`. Benign for parity (JSONs are compared post-parse via `json.loads`); flagged here as a future-proofing note in case Plan 03 ever switches to byte-equal JSON comparison (it doesn't per D-12).
- **Existing `backend/medieval_forge/data/`** already housed `ne_50m_admin_0_countries.geojson` + `hydrosheds/` (used as a namespace package via `importlib.resources.files("medieval_forge.data.hydrosheds")` in `services/ingest_terrain/hydrosheds.py:38`). Adding `__init__.py` to `data/` was checked — `importlib.resources.files()` still resolves both `data.hydrosheds` and the new `data.regions.iberia_868.territory_data` after the addition. No regression.

## Next Plan Readiness

- **Plan 02 (verbatim port)** has every prerequisite locked:
  - PREFLIGHT.md verdicts unambiguously route the port (no `original_idx`, `draw_names=False`).
  - Inputs in-tree at the paths `iberia_config()` already advertises.
  - Golden fixtures ready for Plan 03's parity harness — Plan 02 itself doesn't run parity (that's Plan 03), but smoke runs against the inputs will work.
  - 11 import paths are resolved: Plan 02 only fills algorithm bodies, no new wiring.
- **Plan 03 (delete v1 + parity harness + CI flip)** — not blocked by this plan; Plan 03's parity test reads `tests/fixtures/iberia_868/golden/*` which now exists.

## Self-Check: PASSED

Verified files exist:
- `.planning/phases/01-pipeline-parity-port-harness-together/PREFLIGHT.md` — FOUND
- `data/regions/iberia_868/inputs/pt_concelhos_wgs84.geojson` — FOUND (LFS, 70a86a2b4b pointer)
- `data/regions/iberia_868/inputs/mountain_river_data.json` — FOUND (19 307 B)
- `data/regions/iberia_868/inputs/es-atlas-pkg/package/es/municipalities.json` — FOUND (1 821 999 B)
- `tests/fixtures/iberia_868/golden/` — FOUND, 11 entries
- `backend/medieval_forge/data/regions/iberia_868/territory_data.py` — FOUND, byte-identical to inicio
- `backend/medieval_forge/services/pipeline/{__init__,__main__,contracts,regions,landmask,border,voronoi,cleanup,render,lookup,export}.py` — FOUND (11/11)

Verified commits exist (git log --oneline shows hashes 13864fa / 11fad14 / e652281 / 513c353 / 078bf1c on branch `main`):
- `13864fa` — FOUND
- `11fad14` — FOUND
- `e652281` — FOUND
- `513c353` — FOUND
- `078bf1c` — FOUND

Verified runtime smoke:
- `python -c "from medieval_forge.services.pipeline.regions import iberia_config; cfg = iberia_config()"` → exit 0
- `python -m medieval_forge.services.pipeline --help` → exit 0; shows `--region {iberia_868}`
- `pytest backend/tests/unit/ -v` → 57 passed
- `GET /` on FastAPI app → 200 (Phase 00 SC-6 invariant holds)

---
*Phase: 01-pipeline-parity-port-harness-together*
*Plan: 01 — Wave 0 preflight + scaffold*
*Completed: 2026-05-07*
