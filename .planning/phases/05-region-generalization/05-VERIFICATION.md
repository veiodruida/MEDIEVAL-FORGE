---
phase: 05-region-generalization
verified: 2026-05-13T12:00:00Z
status: passed
score: 14/14 must-haves verified
must_haves_total: 14
must_haves_passed: 14
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 7/9
  gaps_closed:
    - "SC-3 12-file contract — terrain_lookup.png + terrain_types.json now emitted; EXPORT_FILE_CONTRACT has 12 entries; EXPORT_FILE_CONTRACT_DEFERRED is empty tuple (Plan 05-11, commits 637f5e8 / 2689e4a / 2e366e4)"
    - "Playwright UAT live sign-off — user approved Plan 05-12 Task 2 via Option A scope acceptance (France 1066 toy output is per-spec D-09/D-10/D-11, not a bug); universal toy-region rule recorded in user memory"
  gaps_remaining: []
  regressions: []
  additional_fixes_landed:
    - "CR-01 — UNITY_ZIP_SPEC was missing rivers_overlay.png (shipped 11/12 files in Unity ZIP); fixed by aliasing UNITY_ZIP_SPEC = EXPORT_FILE_CONTRACT (commit 0ee12ff)"
    - "WR-01 — ProjectCreate now enforces period_start < period_end (commit 2280621)"
    - "WR-02 — _autogen_territories fails loudly when condados empty but kingdoms/duchies populated (commit 053900e)"
    - "WR-03 — render_terrain_lookup uses TypeError/ValueError instead of assert (survives python -O) (commit da3f197)"
    - "WR-04 — stream_render sentinel-vs-eviction race contract documented (commit 597020e)"
    - "Hotfix 5daa563 — ProjectResponse v1 fields (country_qid/period_start/period_end) now Optional; unblocks GET /projects when v3 project rows exist (migration 0005 made DB columns nullable)"
    - "Plan 05-13 — _autogen_territories dedupes by resolved Path; france_1066 now produces exactly 40 condados (was ~80 via double-read)"
    - "Plan 05-14 — test_iberia_868_yaml.py fixture uses dataclasses.replace(load_region(...)) instead of direct singleton mutation (Pitfall 9 / T-05-04-04 closure)"
    - "Plan 05-14 — NewProjectModal a11y: htmlFor↔id label pairs, finite Toast duration (24h), dropped dead defaultValue on controlled Select"
    - "Plan 05-15 — dead _make_on_stage helper deleted from render.py (generate.py copy preserved — LIVE); dead test helper deleted; no-op try/except flattened; england YAML carries template-only header comment; frontend test:uat:ci npm script added"
---

# Phase 05: Region Generalization Verification Report

**Phase Goal:** Iberia is a config, not a hard-coded path. Other regions/periods supported.
**Verified:** 2026-05-13T12:00:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure via Plans 05-11..05-15 + CR-01/WR-01..WR-04 fixes + hotfix 5daa563

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `data/regions/iberia_868.yaml` externalizes the config currently in code (SC-1) | VERIFIED | YAML present (1748 lines); `load_region('iberia_868')` returns `map_w=1920 map_h=1080 condados=92`; `iberia_config()` absent from production code (0 grep matches in `backend/medieval_forge/`); `regions.py` deleted in Plan 05-05. |
| 2 | `france_1066.yaml` + `england_1216.yaml` ship as templates (SC-2) | VERIFIED | Both YAMLs exist (56 + 60 lines); `display_name` present in both; england lacks `inputs/` dir (template-only contract); `GET /api/v3/regions` returns 3 regions alphabetically with correct `has_dataset` flags (france:true, england:false, iberia:true). |
| 3 | France 1066 toy dataset → ingest → generate → export produces 12 well-formed files (SC-3) | VERIFIED | `EXPORT_FILE_CONTRACT` has 12 entries (live: `len=12`); `EXPORT_FILE_CONTRACT_DEFERRED = ()`; `terrain_lookup.png` + `terrain_types.json` now emitted via `services/pipeline/terrain.py` (121 lines); `test_france_1066_export_contract.py` asserts presence + dimensions + JSON schema for all 12 files. |

**Score:** 3/3 Success Criteria fully satisfied.

### Plan-Level Must-Haves (aggregated across all 15 plans)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| P1 | `load_region('iberia_868')` returns populated `RegionConfig` byte-equivalent to legacy | VERIFIED | Live: `map_w=1920 condados=92`. Parity gate `test_iberia_868_yaml.py` green (11 passed; uses `replace(load_region(...))` after Plan 05-14). |
| P2 | `iberia_config()` does not exist in any production code | VERIFIED | 0 grep matches in `backend/medieval_forge/`. Plan 05-05 deleted `regions.py` + `territory_data.py`. |
| P3 | `POST /api/v3/projects {name, region_key}` validates enum membership server-side | VERIFIED | Migration 0004 + 0005 applied; pydantic `Field(pattern=r"^[a-z0-9_]+$")` + server-side set check. Hotfix 5daa563 keeps ProjectResponse compatible after migration 0005. |
| P4 | `GET /api/v3/regions` returns JSON array with `has_dataset` flag, alphabetical order | VERIFIED | Live TestClient response: 3 regions alphabetically `[england_1216, france_1066, iberia_868]`; `has_dataset` correct per region; reads YAML directly (display_name does not require RegionConfig field). |
| P5 | `generate.py` / `render.py` use `replace(load_region(region_key), ...)` — never mutate cached singleton | VERIFIED | Both files contain the pattern; `cfg.output_dir = ...` direct mutation absent in production paths. All test fixtures also migrated to `replace()` (Plan 05-14). |
| P6 | `england_1216.yaml` has no inputs directory; `load_region('england_1216')` raises `FileNotFoundError` carrying "template-only" | VERIFIED | Live: `FileNotFoundError` raised; message contains "template-only". YAML now carries explicit D-12 header comment (Plan 05-15). |
| P7 | France 1066 pipeline produces well-formed 12-file contract | VERIFIED | Was previously FAILED; closed by Plan 05-11. `EXPORT_FILE_CONTRACT` has 12 entries; both terrain files emitted; E2E test asserts all 12. |
| P8 | `NewProjectModal` renders region Select populated from `GET /api/v3/regions`, defaults to `iberia_868`, disables entries with `has_dataset:false` | VERIFIED | 233 lines; all 3 required `data-testid` attributes; `htmlFor`/`id` label pairs (Plan 05-14); finite Toast duration; PT-BR copy; wired to `useRegions` + `useCreateV3Project`. |
| P9 | Playwright UAT — France 1066 create + generate flow produces 12 artifacts | VERIFIED (user approval) | Spec exists (98 lines, no `test.skip`, 5 `getByTestId` calls); discoverable via new `npm run test:uat:ci -- --list` (Plan 05-15); user approved Plan 05-12 Task 2 via Option A scope acceptance ("France 1066 toy output is per-spec D-09/D-10/D-11, not a bug" — universal rule recorded). |
| P10 | Pipeline writes terrain_lookup.png (1920×1080) + terrain_types.json for every region with land | VERIFIED | Plan 05-11 wired via `_write_outputs_to_disk` lookup block; 9 unit tests + 2 new E2E tests green. PLAINS_RGB=(124,179,66), OCEAN_RGB=(0,0,0); no palette collision with any YAML color field. |
| P11 | `_autogen_territories` dedupes by resolved Path — single-country YAMLs read once | VERIFIED | Plan 05-13: `seen_paths: set[Path]` dedupe; live `load_region('france_1066').condados` returns 40 (was 80 via double-read); bound test tightened to `40 ≤ n ≤ 55`; determinism test added. |
| P12 | Iberia parity fixture is Pitfall 9-clean (no singleton mutation) | VERIFIED | Plan 05-14: `cfg = replace(load_region("iberia_868"), output_dir=str(out))`; pytest-xdist safe. 0 grep matches for `cfg\.output_dir\s*=` in parity tests. |
| P13 | NewProjectModal a11y — htmlFor labels, finite Toast duration, no dead defaultValue | VERIFIED | Plan 05-14: `htmlFor="project-name-input"` + `htmlFor="region-select-trigger"` confirmed at modal lines 120 + 141; `Toast.Root duration={1000 * 60 * 60 * 24}` at line 212; defaultValue removed. |
| P14 | Dead helpers deleted; `test:uat:ci` npm script available; england YAML carries template-only comment | VERIFIED | Plan 05-15: `_make_on_stage` absent from `render.py` (0 grep) but present in `generate.py` (LIVE, untouched); test helper deleted; no-op try/except flattened; YAML header comment present (lines 1-4); `package.json` line 13: `"test:uat:ci": "playwright test --reporter=line"`. |

**Score:** 14/14 plan-level must-haves verified.

### Required Artifacts (Levels 1-3: exists + substantive + wired)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/medieval_forge/services/pipeline/region_loader.py` | Loader + schema + autogen + cache + security guards | VERIFIED | 474 lines; `yaml.safe_load` only (2 occurrences; 0 `yaml.load\b`); `smooth_sigma` clamped `ge=3.0, le=4.5`; `extra='forbid'`; template-only error path; `seen_paths` dedupe present. |
| `backend/medieval_forge/services/pipeline/terrain.py` | Terrain palette + raster generator | VERIFIED | 125 lines; `PLAINS_RGB=(124,179,66)`, `OCEAN_RGB=(0,0,0)`; `render_terrain_lookup`, `build_terrain_types_json`, `assert_palette_no_collision` exported; module docstring marks "Phase 05 contract placeholder". |
| `backend/medieval_forge/services/pipeline/contracts.py` | `EXPORT_FILE_CONTRACT` 12 entries; `EXPORT_FILE_CONTRACT_DEFERRED = ()` | VERIFIED | Live: `len(EXPORT_FILE_CONTRACT)=12; EXPORT_FILE_CONTRACT_DEFERRED=()`. |
| `backend/medieval_forge/services/export.py` | UNITY_ZIP_SPEC matches 12-file contract | VERIFIED | CR-01 fix: `UNITY_ZIP_SPEC = EXPORT_FILE_CONTRACT` (alias); `assert len(UNITY_ZIP_SPEC) == 12` at import time. Single source of truth. |
| `backend/medieval_forge/schemas.py` (ProjectCreate validator) | `period_start < period_end` enforced | VERIFIED | WR-01 fix: `_check_period_ordering` model_validator on ProjectCreate. ProjectResponse fields Optional (hotfix 5daa563). |
| `data/regions/iberia_868.yaml` | Migrated Iberia config | VERIFIED | 1748 lines; `display_name: "Iberia 868 AD"`; `original_idx` present on condados. |
| `data/regions/france_1066.yaml` | France template (geometry-only) | VERIFIED | 56 lines; bounds lon=[-5,8] lat=[42,51]; `display_name: "France 1066 AD"`; empty kingdoms/duchies/condados (autogen path). |
| `data/regions/france_1066/inputs/france_municipalities_toy.geojson` | ~40-50 Voronoi polygon features | VERIFIED | Present on disk; 40 features after Plan 05-13 dedupe. |
| `data/regions/france_1066/inputs/mountain_river_data.json` | Empty mountain/river stub | VERIFIED | Present on disk. |
| `data/regions/england_1216.yaml` | England template (template-only, no inputs) | VERIFIED | 60 lines; `display_name: "England 1216 AD"`; D-12 header comment present (lines 1-4); no `england_1216/inputs/` directory. |
| `backend/medieval_forge/api/v3/regions.py` | GET /api/v3/regions endpoint | VERIFIED | 72 lines; registered in main.py; reads YAML directly via `yaml.safe_load`; alphabetical sort; `has_dataset` from disk check. |
| `backend/medieval_forge/api/v3/projects.py` | POST /api/v3/projects with region_key enum | VERIFIED | 69 lines; pydantic regex + server-side set check. |
| `backend/medieval_forge/api/v3/render.py` | render endpoints; dead `_make_on_stage` removed | VERIFIED | 374 lines; 0 grep matches for `_make_on_stage` in this file; `_on_stage_tracking` closure intact (2 matches). |
| `backend/medieval_forge/services/pipeline/__init__.py` | Pipeline writes terrain files | VERIFIED | 658 lines; `from .terrain import` present; `terrain_lookup.png` / `terrain_types.json` written via `_write_outputs_to_disk` lookup block. |
| `frontend/src/components/projects/NewProjectModal.tsx` | Radix Dialog + Select modal | VERIFIED | 233 lines; `htmlFor` labels present; finite Toast duration; no dead defaultValue. |
| `frontend/src/api/useRegions.ts` | TanStack Query hook | VERIFIED | 13 lines; queryKey `['v3','regions']`; fetches `/api/v3/regions`. |
| `frontend/tests/uat/playwright/france_1066_create_project.spec.ts` | Playwright UAT spec | VERIFIED | 98 lines; no `test.skip`; 5 `getByTestId` calls; discoverable via `npm run test:uat:ci -- --list`. |
| `backend/tests/e2e/test_france_1066_export_contract.py` | E2E SC-3 12-file gate | VERIFIED | 208 lines; asserts presence + dimensions + JSON validity for all 12 files including `terrain_lookup.png` + `terrain_types.json`. |
| `scripts/run_france_uat.sh` + `scripts/run_france_uat.ps1` | Dual-shell UAT runners | VERIFIED | 67 + 74 lines; bash `-n` validated; both reference `france_1066_create_project`, `npm run build`, kill-prior-servers, `/api/v3/regions` probe. |
| `frontend/package.json` | `test:uat:ci` npm script | VERIFIED | Line 13: `"test:uat:ci": "playwright test --reporter=line"`. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `region_loader.py` | `contracts.py` | `RegionConfig(**model.model_dump())` | VERIFIED | Wired |
| `region_loader.py` | `yaml.safe_load` | import + call | VERIFIED | 2 occurrences; 0 `yaml.load\b` |
| `region_loader._autogen_territories` | dedupe | `seen_paths: set[Path]` | VERIFIED | Plan 05-13; france 80→40 confirmed live |
| `api/v3/generate.py` | `region_loader.py` | `replace(load_region(region_key), ...)` | VERIFIED | Pattern present |
| `api/v3/render.py` | `region_loader.py` | `replace(load_region(region_key), ...)` | VERIFIED | Pattern present at line 109 docstring + body |
| `pipeline/__init__.py` | `terrain.py` | `from .terrain import render_terrain_lookup, build_terrain_types_json` | VERIFIED | Import present |
| `services/export.py` | `contracts.EXPORT_FILE_CONTRACT` | `UNITY_ZIP_SPEC = EXPORT_FILE_CONTRACT` | VERIFIED | CR-01 fix; single source of truth |
| `main.py` | `api/v3/regions.py` | `app.include_router(v3_regions.router)` | VERIFIED | Registered |
| `main.py` | `api/v3/projects.py` | `app.include_router(v3_projects.router)` | VERIFIED | Registered |
| `NewProjectModal.tsx` | `useRegions.ts` + `useCreateV3Project` | hook imports | VERIFIED | Both imported and used |
| `NewProjectModal.tsx` | label↔input | `htmlFor` / `id` pairs | VERIFIED | Plan 05-14 |
| `ProjectList.tsx` | `NewProjectModal.tsx` | `<NewProjectModal />` | VERIFIED | Imported and used |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `NewProjectModal.tsx` | `regions` (from `useRegions`) | `GET /api/v3/regions` → YAML discovery + disk check | Yes — live test returned 3 real regions | FLOWING |
| `api/v3/regions.py` | region list | `_REGIONS_DIR.glob("*.yaml")` on disk | Yes — 3 YAMLs found | FLOWING |
| `api/v3/generate.py` | `cfg` (pipeline config) | `load_region(project.region_key)` → YAML parse → `RegionConfig` | Yes — round-trip tested; produces 12-file output | FLOWING |
| `terrain.render_terrain_lookup` | `arr` (uint8 RGB[H,W,3]) | `land: bool[H,W]` mask + RegionConfig palette | Yes — palette real, no collision | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `load_region('iberia_868')` returns populated cfg | Python direct call | `map_w=1920, condados=92` | PASS |
| `load_region('france_1066')` returns 40 condados (post-dedupe) | Python direct call | `condados=40` | PASS |
| `load_region('england_1216')` raises FileNotFoundError with "template-only" | Python direct call | Raised; message contains "template-only" | PASS |
| `GET /api/v3/regions` returns 3 regions alphabetically | TestClient | `[england_1216, france_1066, iberia_868]`; correct has_dataset | PASS |
| `EXPORT_FILE_CONTRACT` length is 12; DEFERRED empty | Python direct call | `len=12; DEFERRED=()` | PASS |
| `iberia_config()` absent from production code | grep | 0 matches in `backend/medieval_forge/` | PASS |
| `UNITY_ZIP_SPEC == EXPORT_FILE_CONTRACT` (CR-01 fix) | grep + import-time assert | `UNITY_ZIP_SPEC = EXPORT_FILE_CONTRACT`; `assert len == 12` | PASS |
| Full backend test suite | `pytest tests/unit tests/parity tests/e2e -q` | 155 passed, 6 xfailed (pre-existing D-09 waivers), 4 xpassed | PASS |
| `_make_on_stage` removed from render.py but live in generate.py | grep | render.py: 0 matches; generate.py: 3 matches (def + call site) | PASS |
| France spec discoverable via `npm run test:uat:ci -- --list` | npm script | France spec listed as item #7 | PASS |

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|--------------|-------------|--------|----------|
| SC-1 (V3-REGION-CONFIG) | Plans 01-05, 14 | iberia_868.yaml externalizes the config | SATISFIED | YAML exists; loader works; production code uses `load_region`; `iberia_config()` deleted; parity fixture Pitfall 9-clean |
| SC-2 (V3-REGION-CONFIG) | Plans 04, 06-09, 13-15 | france_1066.yaml + england_1216.yaml ship | SATISFIED | Both YAMLs exist with display_name; england template-only; france autogen dedupe produces 40 condados |
| SC-3 (V3-REGION-CONFIG) | Plans 06, 10-13, 15 | France toy → export produces 12 well-formed files | SATISFIED | EXPORT_FILE_CONTRACT=12; terrain files emitted; E2E test asserts all 12; UNITY_ZIP_SPEC aligned (CR-01 fix) |

### Anti-Patterns — Resolution of Prior Findings

| Prior Finding | Severity (then) | Status (now) | Resolution |
|---------------|-----------------|--------------|------------|
| `test_iberia_868_yaml.py:43` direct `cfg.output_dir` mutation (Pitfall 9) | Warning | RESOLVED | Plan 05-14 commit `74cffb7`: `cfg = replace(load_region("iberia_868"), output_dir=str(out))` |
| `_autogen_territories` produces 80 condados for france_1066 (double-read) | Warning | RESOLVED | Plan 05-13 commit `1a0e1b1`: `seen_paths` dedupe; live verified `len=40` |
| `api/v3/render.py:94-99` dead `_make_on_stage` helper | Info | RESOLVED | Plan 05-15 commit `818d939`: deleted from render.py (generate.py copy preserved — LIVE) |
| `region_loader.py:350-360` no-op try/except | Info | RESOLVED | Plan 05-15 commit `818d939`: flattened to direct return |
| CR-01: `UNITY_ZIP_SPEC` missing rivers_overlay.png (new finding) | Critical | RESOLVED | Commit `0ee12ff`: aliased to `EXPORT_FILE_CONTRACT` |
| WR-01: ProjectCreate missing period_start/end validator (new finding) | Warning | RESOLVED | Commit `2280621`: `_check_period_ordering` added |
| WR-02: autogen overwrites curated kingdoms/duchies (new finding) | Warning | RESOLVED | Commit `053900e`: fail-loud guard added |
| WR-03: `render_terrain_lookup` uses `assert` (new finding) | Warning | RESOLVED | Commit `da3f197`: TypeError/ValueError replace asserts |
| WR-04: `_render_producer` cleanup race (new finding) | Warning | RESOLVED | Commit `597020e`: contract documented |
| ProjectResponse rejects v1 nullable rows (latent post-migration 0005) | Blocker (latent) | RESOLVED | Hotfix `5daa563`: country_qid/period_start/period_end Optional |

No new anti-patterns surfaced in this re-verification pass.

### Human Verification

The prior human-verification item ("Playwright UAT — France 1066 create + generate visual sign-off") was **closed by the user** in Plan 05-12 Task 2 via Option A scope acceptance. The user's rationale (recorded in `05-12-SUMMARY.md` and in user memory as the universal toy-region rule): France 1066 toy output is per-spec D-09/D-10/D-11 (rectangular Voronoi tessellation), NOT a bug. Running the live runner would only confirm what code review already established.

The runner scripts ship (`scripts/run_france_uat.sh` + `.ps1`, plus `npm run test:uat:ci`) so any user can re-run the live UAT at will, but the verification gate is closed.

No new human-verification items identified in this pass.

### Gaps Summary

**No gaps blocking goal achievement.**

All three ROADMAP Success Criteria are satisfied; all 14 plan-level must-haves are verified; all code review findings (CR-01 + WR-01..WR-04) are fixed with named commits in git history; backend test suite is green (155 passed); the prior human-verification gap was closed by the user via Option A scope acceptance.

The phase is ready to hand off to Phase 06 (Export contract + validation gate).

---

_Verified: 2026-05-13T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification iteration: 2 (initial 2026-05-12 found 2 gaps; both now closed)_
