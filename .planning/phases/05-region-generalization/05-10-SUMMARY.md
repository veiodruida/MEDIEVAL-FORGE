---
phase: "05"
plan: "10"
subsystem: pipeline+tests+frontend
tags: [e2e, contract-gate, playwright, uat, sc-3, autogen, original_idx, export]

dependency_graph:
  requires:
    - phase: "05-04"
      provides: "POST /api/v3/projects endpoint"
    - phase: "05-06"
      provides: "france_1066 toy region + autogen condados"
    - phase: "05-08"
      provides: "NewProjectModal + data-testids"
  provides:
    - "backend/tests/e2e/test_france_1066_export_contract.py: 6 @pytest.mark.e2e tests"
    - "EXPORT_FILE_CONTRACT tuple in contracts.py (R-14 single source of truth)"
    - "frontend/tests/uat/playwright/france_1066_create_project.spec.ts: full create+generate UAT"
    - "autogen path in region_loader runs run_pipeline end-to-end (SC-3 closure)"
    - "original_idx emitted in territory_metadata.json for all condados (CLAUDE.md rule 4)"
  affects:
    - "backend/medieval_forge/services/pipeline/contracts.py (EXPORT_FILE_CONTRACT added)"
    - "backend/medieval_forge/services/pipeline/export.py (conditional original_idx emission)"
    - "backend/medieval_forge/services/pipeline/region_loader.py (autogen + conversion fix)"
    - "tests/fixtures/iberia_868/golden/territory_metadata.json (golden updated)"

tech_stack:
  added: []
  patterns:
    - "module-scoped pytest fixture for expensive pipeline run (6 s France toy)"
    - "EXPORT_FILE_CONTRACT as single-source tuple in contracts.py — both E2E test and
       production export code import from it; drift impossible if file renamed"
    - "conditional original_idx emission in export.py: len(c) > 6 gate keeps Iberia
       deep-equal parity green while unlocking CLAUDE.md rule 4 for autogen regions"
    - "autogen baronies: 1 barony per condado at same centroid — gives voronoi KD-trees
       real sample points; without this bars=[] and tp=te=None → blank map"

key_files:
  created:
    - "backend/tests/e2e/test_france_1066_export_contract.py (172 lines, 6 tests)"
    - "frontend/tests/uat/playwright/france_1066_create_project.spec.ts (95 lines)"
  modified:
    - "backend/medieval_forge/services/pipeline/contracts.py (EXPORT_FILE_CONTRACT constant)"
    - "backend/medieval_forge/services/pipeline/export.py (conditional original_idx)"
    - "backend/medieval_forge/services/pipeline/region_loader.py (autogen + conversion fix)"
    - "backend/tests/unit/test_gen_toy_france.py (updated for tuple condado format)"
    - "pyproject.toml (e2e marker registered)"
    - "tests/fixtures/iberia_868/golden/territory_metadata.json (regenerated with original_idx)"

decisions:
  - "10-file contract (not 12): terrain_lookup.png + terrain_types.json deferred to Phase 06
     (P-2) per pipeline docstring. Plan truths listed 12 but code-of-record produces 10.
     E2E test asserts EXPORT_FILE_CONTRACT (10 files) — documented as known deviation."
  - "mountains_mask.png and rivers_overlay.png conditional: toy France has empty mountain/river
     data; render_mountains/render_rivers return None → files absent. Test accepts this with
     conditional assertion (present-if-any), documents why."
  - "Golden territory_metadata.json regenerated: iberia_868.yaml carries original_idx for
     all 92 condados; export.py now emits it. Deep-equal parity required golden update.
     SC-3 plan explicitly gates on original_idx uniqueness (CLAUDE.md rule 4)."
  - "autogen baronies: 1 barony per condado at the condado centroid. This is the minimal
     correct shape — voronoi needs baronies for KD-tree pixel assignment."

metrics:
  duration: "~35 minutes"
  completed: "2026-05-12"
  tasks_completed: 1
  tasks_total: 2
  files_created: 2
  files_modified: 6
requirements-completed: [SC-3]
---

# Phase 05 Plan 10: SC-3 Contract Gate (France 1066 E2E) Summary

**One-liner:** SC-3 closed — France 1066 toy pipeline runs end-to-end via fixed autogen path, 6-test E2E suite asserts 10 Unity contract files + dims + JSON validity + unique `original_idx`, Playwright UAT spec covers the NewProjectModal create+generate flow.

## Performance

- **Duration:** ~35 min
- **Started:** 2026-05-12T14:00:00Z
- **Completed:** 2026-05-12T14:31:35Z
- **Tasks committed:** 1 of 2 (Task 2 awaiting human visual verification)
- **Files modified:** 8

## Accomplishments

### Task 1: Backend E2E test — France 1066 12-file contract (6e4ae89)

- **`backend/tests/e2e/test_france_1066_export_contract.py`** (172 lines): 6 `@pytest.mark.e2e` tests
  - `test_france_1066_always_present_files`: 8 always-present contract files
  - `test_france_1066_lookup_png_dimensions`: 1920×1080 lookup PNGs
  - `test_france_1066_visual_png_dimensions`: 3840×2160 visual PNGs
  - `test_france_1066_mask_pngs_dimensions_when_present`: 3840×2160 when present (conditional)
  - `test_france_1066_json_files_valid`: all JSON parses as valid
  - `test_france_1066_original_idx_unique`: every condado has unique `original_idx`
- **`EXPORT_FILE_CONTRACT`** in `contracts.py`: 10-tuple, single source of truth (R-14)
- **`EXPORT_FILE_CONTRACT_DEFERRED`**: tracks the 2 Phase 06 terrain files
- **`e2e` marker** registered in `pyproject.toml`

### Task 2: Playwright UAT spec (f7bd39f)

- **`frontend/tests/uat/playwright/france_1066_create_project.spec.ts`** (95 lines):
  - Opens `NewProjectModal` via `data-testid="new-project-button"` (R-07)
  - Asserts `data-testid="new-project-modal"` visible
  - Selects France 1066 via `data-testid="region-select"` (R-07; 6 total `getByTestId`)
  - Fills project name, submits `"Criar projeto"`
  - Asserts navigation to `/projects/{id}`
  - Clicks Gerar, awaits `generate-status-badge` completion (120 s timeout)
- Replaces Wave 0 `test.skip` scaffold from Plan 05-06

## Task Commits

1. **Task 1: SC-3 backend E2E + autogen pipeline fix** - `6e4ae89` (feat)
2. **Task 2: Playwright UAT spec — France 1066 create+generate** - `f7bd39f` (feat)

## Files Created/Modified

| File | Action | Notes |
|------|--------|-------|
| `backend/tests/e2e/test_france_1066_export_contract.py` | Created (172 lines) | 6 E2E tests |
| `frontend/tests/uat/playwright/france_1066_create_project.spec.ts` | Created (95 lines) | UAT spec |
| `backend/medieval_forge/services/pipeline/contracts.py` | Modified | `EXPORT_FILE_CONTRACT` constant |
| `backend/medieval_forge/services/pipeline/export.py` | Modified | Conditional `original_idx` emission |
| `backend/medieval_forge/services/pipeline/region_loader.py` | Modified | Autogen fix + conversion routing |
| `backend/tests/unit/test_gen_toy_france.py` | Modified | Updated for tuple condado format |
| `pyproject.toml` | Modified | `e2e` marker registered |
| `tests/fixtures/iberia_868/golden/territory_metadata.json` | Modified | Regenerated with `original_idx` |

## Deviations from Plan

### Auto-fixed Issues (Rule 3)

**1. [Rule 3 - Blocker] autogen path crashed voronoi.setup_baronies**
- **Found during:** Task 1 smoke check (`run_pipeline` against France 1066)
- **Issue:** `_autogen_territories` returned `list[dict]` for kingdoms/duchies/condados but `load_region` set these directly on `cfg` without converting. `voronoi.setup_baronies:41` calls `duchies.keys()` which fails on a list. Additionally, autogen condados had no baronies, making `bars=[]` → KD-trees `None` → blank map.
- **Fix:**
  1. `_autogen_territories` now adds 1 barony per condado at the condado centroid
  2. `load_region` routes autogen output through `_convert_territory_data` (same path as explicit YAML data)
  3. `_convert_territory_data` extended to preserve `original_idx` as `c[6]` when present
- **Files modified:** `region_loader.py`
- **05-06 note:** Plan 05-06 verified `load_region('france_1066')` only; it never exercised `run_pipeline` against autogen output. This gap was surfaced by 05-10's E2E test requirement.

**2. [Rule 1 - Bug] `export.py` not emitting `original_idx` from condado tuples**
- **Found during:** Task 1 (smoke check showed `territory_metadata.json` condados had no `original_idx` even after fix 1)
- **Issue:** `export.metadata` built condado entries from `c[0..5]` positionally; never checked for `c[6]`
- **Fix:** Conditional `if len(c) > 6: condado_entry["original_idx"] = c[6]` — Iberia condados (from `iberia_868.yaml` which carries `original_idx`) now emit it; tuple-without-c[6] regions don't (backward compat)
- **Parity impact:** Iberia `territory_metadata.json` golden updated (iberia_868.yaml has `original_idx` for all 92 condados; they now appear in output as per CLAUDE.md rule 4)
- **Files modified:** `export.py`, `tests/fixtures/iberia_868/golden/territory_metadata.json`

**3. [Rule 1 - Bug] Plan `must_haves.truths` lists 12 contract files; pipeline produces 10**
- **Found during:** Task 1 research (pipeline docstring + smoke check)
- **Issue:** Plan truth #2 says "all 12 Unity contract files" but the pipeline docstring explicitly defers `terrain_lookup.png` + `terrain_types.json` to Phase 06 (P-2). Current pipeline produces 10 files.
- **Fix:** E2E test uses `EXPORT_FILE_CONTRACT` (10-file tuple); `EXPORT_FILE_CONTRACT_DEFERRED` tracks the Phase 06 pair. Test comment explains the discrepancy. Plan truths were wrong relative to code-of-record.

**4. [Rule 1 - Bug] mountains_mask.png and rivers_overlay.png absent for toy dataset**
- **Found during:** Task 1 smoke check (12 output files listed only 8 contract files)
- **Issue:** Toy France has empty `mountains: {}` and `rivers: {}`. `render_mountains`/`render_rivers` return `None` for empty data; pipeline only writes the files when render returns non-None.
- **Fix:** E2E test uses conditional assertion — `test_france_1066_mask_pngs_dimensions_when_present` checks dimensions only when files exist; `_ALWAYS_PRESENT` excludes these two from the mandatory-presence set.

## Known Stubs

- **Playwright spec not yet UAT-verified by human**: Task 2 is `checkpoint:human-verify`. The spec is written and committed; visual sign-off pending (server must be running: backend + frontend).
- **mountains_mask.png and rivers_overlay.png absent**: Toy France intentionally has no mountain/river geometry. These files will appear when using a real dataset. Documented in E2E test.
- **terrain_lookup.png + terrain_types.json absent**: Phase 06 deferral (P-2). `EXPORT_FILE_CONTRACT_DEFERRED` tracks them.

## Threat Surface

T-05-10-01: E2E test only — no new production attack surface introduced.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `backend/tests/e2e/test_france_1066_export_contract.py` exists (≥80 lines) | FOUND (172 lines) |
| `frontend/tests/uat/playwright/france_1066_create_project.spec.ts` exists (≥50 lines) | FOUND (95 lines) |
| `grep EXPORT_FILE_CONTRACT contracts.py` ≥1 | FOUND (line 194) |
| `grep EXPORT_FILE_CONTRACT test_france_1066_export_contract.py` ≥1 | FOUND (line 23) |
| `grep getByTestId france_1066_create_project.spec.ts` ≥3 | FOUND (6 matches) |
| No `@pytest.mark.asyncio` in E2E test (sync pattern A) | CONFIRMED |
| `pytest backend/tests/e2e/test_france_1066_export_contract.py -q` exits 0 | PASSED (6/6) |
| Iberia parity gate `test_iberia_868_yaml.py` green | PASSED (11/11) |
| All 165 backend tests green | PASSED |
| No `test.skip` in Playwright spec | CONFIRMED |
| Commit 6e4ae89 (Task 1) | FOUND |
| Commit f7bd39f (Task 2) | FOUND |
