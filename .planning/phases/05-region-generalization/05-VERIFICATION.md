---
phase: 05-region-generalization
verified: 2026-05-12T15:30:00Z
status: gaps_found
score: 7/9 must-haves verified
overrides_applied: 0
gaps:
  - truth: "France 1066 with toy synthetic dataset → ingest → generate → export produces 12 well-formed files (ROADMAP SC-3: 'file contract IS')"
    status: failed
    reason: "Pipeline currently produces 10 files. terrain_lookup.png and terrain_types.json are absent — deferred to Phase 06 per pipeline docstring comment. EXPORT_FILE_CONTRACT = 10 entries; EXPORT_FILE_CONTRACT_DEFERRED tracks the 2 missing files. The ROADMAP SC-3 text is unambiguous: 'parity to Reconquista NOT required; file contract IS'. The file contract table in CLAUDE.md lists all 12 files including terrain_lookup.png (#5) and terrain_types.json (#6). The deferral is documented in code but was not approved as a ROADMAP deviation."
    artifacts:
      - path: "backend/medieval_forge/services/pipeline/contracts.py"
        issue: "EXPORT_FILE_CONTRACT has 10 entries; terrain_lookup.png and terrain_types.json placed in EXPORT_FILE_CONTRACT_DEFERRED (lines 208-210)"
      - path: "backend/tests/e2e/test_france_1066_export_contract.py"
        issue: "Test asserts _ALWAYS_PRESENT (8 files) — deliberately excludes terrain files and the two conditional mask files"
    missing:
      - "terrain_lookup.png (1920x1080) — CLAUDE.md contract file #5"
      - "terrain_types.json — CLAUDE.md contract file #6"
      - "ROADMAP SC-3 deferral override or Phase 06 explicit scope assignment"

human_verification:
  - test: "Playwright UAT: France 1066 create + generate flow visual sign-off"
    expected: "User opens the resulting Playwright HTML report after running 'npx playwright test france_1066_create_project --reporter=line'; the test passes. User also opens the visual output from a fresh France generate in the workspace canvas and confirms maps look like a map — contiguous regions, no fragmenting, colors stable across re-run."
    why_human: "The Task 2 checkpoint in Plan 05-10 was marked approved by the user without running a live browser session. 05-10-SUMMARY line 199 states: 'No browser session was run against a live server — spec correctness validated via code review + selector analysis only.' The plan's resume-signal required visual confirmation that France render looks contiguous (no fragmenting; deterministic re-run shows same colors). This is the only unverified behavioral outcome in Phase 05."
---

# Phase 05: Region Generalization Verification Report

**Phase Goal:** Iberia is a config, not a hard-coded path. Other regions/periods supported.
**Verified:** 2026-05-12T15:30:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `data/regions/iberia_868.yaml` externalizes the config currently in code (SC-1) | VERIFIED | File exists (1748 lines), `load_region('iberia_868')` returns cfg with map_w=1920 map_h=1080 condados=92. `regions.py` deleted; `iberia_config` absent from all production code. |
| 2 | `france_1066.yaml` + `england_1216.yaml` ship as templates (SC-2) | VERIFIED | Both YAML files exist (56 lines each), `display_name` present in both, `england_1216` has no inputs dir. `GET /api/v3/regions` returns france_1066 with `has_dataset:true` and england_1216 with `has_dataset:false`. |
| 3 | France 1066 toy dataset → ingest → generate → export produces 12 well-formed files (SC-3) | FAILED | Pipeline produces 10 files. `EXPORT_FILE_CONTRACT` has 10 entries; `terrain_lookup.png` and `terrain_types.json` deferred to Phase 06 per code comment. ROADMAP SC-3 text: "parity to Reconquista NOT required; file contract IS." |

**Score:** 7/9 individual must-haves verified (see below), 2/3 Success Criteria fully satisfied.

**Derived plan-level truths (from PLAN frontmatter, all plans):**

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| P1 | `load_region('iberia_868')` returns populated `RegionConfig` byte-equivalent to legacy | VERIFIED | Live test: `load_region('iberia_868')` returns map_w=1920 condados=92. Legacy `iberia_config()` deleted. |
| P2 | `iberia_config()` does not exist in any production code | VERIFIED | `grep -rn "iberia_config" backend/medieval_forge/ --include="*.py"` returns 0 matches. Only appears in docstrings/comments in test files. |
| P3 | `POST /api/v3/projects {name, region_key}` validates enum membership server-side | VERIFIED | Live: 201 for `iberia_868`, 400 for `no_such_region`, 422 for `../escape`. |
| P4 | `GET /api/v3/regions` returns JSON array with `has_dataset` flag, alphabetical order | VERIFIED | Live: 3 regions returned, alphabetical, iberia/france `has_dataset:true`, england `has_dataset:false`. |
| P5 | `generate.py` and `render.py` use `replace(load_region(project.region_key), ...)` — never mutate cached singleton | VERIFIED | Both files import `load_region`; grep confirms `replace(load_region(region_key)` pattern. `iberia_config` import removed from both. |
| P6 | `data/regions/england_1216.yaml` has no inputs directory; `load_region('england_1216')` raises `FileNotFoundError` naming missing path and "template-only" | VERIFIED | `england_1216/inputs/` absent; loader raises `FileNotFoundError` with message containing "template-only" and path info. |
| P7 | France 1066 pipeline produces well-formed contract files (12-file count) | FAILED | Only 10 files produced. See gap above. |
| P8 | `NewProjectModal` renders region Select populated from `GET /api/v3/regions`, defaults to `iberia_868`, disables entries with `has_dataset:false` | VERIFIED | Modal file (231 lines) has all 3 required `data-testid` attributes, `defaultValue="iberia_868"`, `(sem dataset)` suffix for disabled items, wired to `useRegions` and `useCreateV3Project`. |
| P9 | Playwright UAT: user creates France 1066 project via modal and observes successful generate + 12 artifacts | HUMAN NEEDED | Spec exists (95 lines, 6 `getByTestId` calls, no `test.skip`). User approved the checkpoint via code review only — no live browser session was run. |

### Deferred Items

No items explicitly deferred by Step 9b analysis. The `terrain_lookup.png` + `terrain_types.json` deferral appears in a code comment but Phase 06's ROADMAP success criteria do not explicitly name these files. Conservative ruling: real gap, not deferred.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/medieval_forge/services/pipeline/region_loader.py` | Loader + schema + autogen + cache + security guards (≥150 lines) | VERIFIED | 457 lines; exports `load_region`, `clear_region_cache`, `RegionConfigSchema`; `yaml.safe_load` only; `smooth_sigma` field has `ge=3.0, le=4.5`; `extra='forbid'` on schema; `template-only` error path present |
| `data/regions/iberia_868.yaml` | Migrated Iberia config (≥50 lines) | VERIFIED | 1748 lines; `display_name` present; `original_idx` present on condados; `load_region` returns functional cfg |
| `data/regions/france_1066.yaml` | France template (geometry-only, ≥30 lines) | VERIFIED | 56 lines; bounds lon=[-5,8] lat=[42,51]; display_name "France 1066 AD"; empty kingdoms/duchies/condados |
| `data/regions/france_1066/inputs/france_municipalities_toy.geojson` | ~50 Voronoi polygon features | VERIFIED | 40 FeatureCollection features (Voronoi infinite-region drop documented) |
| `data/regions/france_1066/inputs/mountain_river_data.json` | Empty mountain/river stub (dict-of-dicts) | VERIFIED | `{"mountains": {}, "rivers": {}}` confirmed |
| `data/regions/england_1216.yaml` | England template (YAML-only, no inputs, ≥25 lines) | VERIFIED | 56 lines; `display_name` "England 1216 AD"; no `england_1216/inputs/` directory |
| `backend/medieval_forge/api/v3/projects.py` | POST /api/v3/projects with region_key enum validation | VERIFIED | `parents[4]` anchor present; pydantic `Field(pattern=r"^[a-z0-9_]+$")` rejects injection; server-side set check rejects unknown regions with 400 |
| `backend/medieval_forge/api/v3/regions.py` | GET /api/v3/regions endpoint (≥60 lines) | VERIFIED | Registered in main.py; `parents[4]` anchor; alphabetical sort; `has_dataset` logic correct |
| `alembic/versions/0004_add_region_key_to_projects.py` | Alembic migration with `batch_alter_table` | VERIFIED | `batch_alter_table` present; region_key column + backfill; downgrade implemented |
| `backend/medieval_forge/models.py` (Project.region_key) | `region_key: Mapped[str]` field | VERIFIED | Line 37: `region_key: Mapped[str] = mapped_column(String(64), nullable=False, default="iberia_868")` |
| `frontend/src/components/projects/NewProjectModal.tsx` | Radix Dialog + Select modal (≥120 lines) | VERIFIED | 231 lines; `data-testid="new-project-button"`, `"new-project-modal"`, `"region-select"` all present; PT-BR copy per UI-SPEC |
| `frontend/src/api/useRegions.ts` | TanStack Query hook for /api/v3/regions | VERIFIED | queryKey `['v3', 'regions']`; fetches `/api/v3/regions` |
| `backend/tests/e2e/test_france_1066_export_contract.py` | E2E SC-3 gate (≥80 lines) | VERIFIED (partial) | 172 lines; 6 tests; asserts 10-file contract, dimensions, JSON validity, original_idx uniqueness. Missing: terrain_lookup.png + terrain_types.json assertions. |
| `frontend/tests/uat/playwright/france_1066_create_project.spec.ts` | Playwright UAT spec (≥50 lines) | VERIFIED (code only) | 95 lines; no `test.skip`; 6 `getByTestId` calls; but no live browser run confirmed |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `region_loader.py` | `contracts.py` | `RegionConfig(**model.model_dump())` | VERIFIED | Import and `RegionConfig(` call confirmed |
| `region_loader.py` | `yaml.safe_load` | import + call | VERIFIED | 2 occurrences of `yaml.safe_load`; 0 occurrences of `yaml.load\b` |
| `api/v3/generate.py` | `region_loader.py` | `replace(load_region(region_key), ...)` | VERIFIED | Import confirmed; `replace(load_region(region_key)` pattern at line 139 |
| `api/v3/render.py` | `region_loader.py` | `replace(load_region(region_key), ...)` | VERIFIED | Import confirmed; `replace(load_region(region_key)` pattern at line 138 |
| `api/v3/projects.py` | `data/regions/*.yaml` | `_available_region_keys()` glob | VERIFIED | `_REGIONS_DIR = parents[4]` confirmed; glob + set membership check in POST handler |
| `main.py` | `api/v3/regions.py` | `app.include_router(v3_regions.router)` | VERIFIED | Lines 47 and 58 confirm import and registration |
| `main.py` | `api/v3/projects.py` | `app.include_router(v3_projects.router)` | VERIFIED | Lines 48 and 59 confirm import and registration |
| `NewProjectModal.tsx` | `useRegions.ts` | `useRegions()` call | VERIFIED | Import on line 13; usage on line 32 |
| `NewProjectModal.tsx` | `/api/v3/projects` | `useCreateV3Project` mutation | VERIFIED | Import on line 14; mutation `create` used on submit |
| `ProjectList.tsx` | `NewProjectModal.tsx` | `<NewProjectModal />` | VERIFIED | Import on line 4; used on line 24; `to="/projects/new"` link removed |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `NewProjectModal.tsx` | `regions` (from `useRegions`) | `GET /api/v3/regions` → YAML discovery + `has_dataset` disk check | Yes — live test returned 3 real regions | FLOWING |
| `api/v3/regions.py` | region list | `_REGIONS_DIR.glob("*.yaml")` on disk | Yes — 3 YAMLs found in `data/regions/` | FLOWING |
| `api/v3/generate.py` | `cfg` (pipeline config) | `load_region(project.region_key)` → YAML parse → `RegionConfig` | Yes — round-trip tested | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `load_region('iberia_868')` returns populated cfg | Python direct call | map_w=1920, condados=92 | PASS |
| `load_region('england_1216')` raises `FileNotFoundError` with "template-only" | Python direct call | Raised; message contains "template-only" and missing path | PASS |
| `POST /api/v3/projects` accepts valid region_key | TestClient | 201 returned | PASS |
| `POST /api/v3/projects` rejects unknown region_key | TestClient | 400 returned | PASS |
| `POST /api/v3/projects` rejects path injection | TestClient | 422 returned (pydantic regex) | PASS |
| `GET /api/v3/regions` returns 3 regions alphabetically with has_dataset | TestClient | `['england_1216', 'france_1066', 'iberia_868']`; correct has_dataset values | PASS |
| `iberia_config()` absent from production code | grep | 0 matches in `backend/medieval_forge/` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SC-1 (V3-REGION-CONFIG) | Plans 01-05 | `data/regions/iberia_868.yaml` externalizes the config currently in code | SATISFIED | YAML exists, loader works, production code uses `load_region`, `iberia_config()` deleted |
| SC-2 (V3-REGION-CONFIG) | Plans 06-09 | france_1066.yaml + england_1216.yaml ship as templates | SATISFIED | Both YAMLs exist with display_name, correct has_dataset in endpoint |
| SC-3 (V3-REGION-CONFIG) | Plan 10 | France 1066 toy → export produces 12 well-formed files | BLOCKED | Only 10 files produced; terrain_lookup.png + terrain_types.json absent |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/tests/parity/test_iberia_868_yaml.py` | 43 | `cfg.output_dir = str(out)` — direct mutation of `load_region()` singleton | Warning | Test-only blast radius; `clear_region_cache_between_tests` autouse mitigates in CI. Violates Pitfall 9 / T-05-04-04 focus-area mandate. Fix: `cfg = replace(load_region("iberia_868"), output_dir=str(out))` |
| `backend/medieval_forge/services/pipeline/region_loader.py` | ~389-411 | `_autogen_territories` reads `pt_geojson` and `es_input` unconditionally when they point at the same file (france_1066 single-country fallthrough) — produces 80 condados instead of ~40 | Warning | Voronoi seed collision; 2x intended density. Live observation: france_1066 returns 80 condados. Unit test bound `>= 40` masks this. No CLAUDE.md rule violation (original_idx uniqueness preserved). |
| `backend/medieval_forge/api/v3/render.py` | ~94-99 | `_make_on_stage` dead helper — defined at module scope, never referenced | Info | Dead code; maintainer confusion risk |
| `backend/medieval_forge/services/pipeline/region_loader.py` | ~350-360 | No-op try/except re-raises same exceptions unchanged | Info | Harmless; misleading code structure |

### Human Verification Required

#### 1. Playwright UAT — France 1066 create + generate visual sign-off

**Test:** Start both backend (`medieval-forge start`) and frontend dev server. Run `npx playwright test france_1066_create_project --reporter=line`. After the test passes, open the generated map artifacts and visually confirm the France 1066 render shows contiguous regions (no fragmenting), correct region colors, and deterministic re-run produces identical colors.

**Expected:** Playwright test exits 0; France map shows ~40 Voronoi cells rendered as distinct colored regions with no visual fragmentation.

**Why human:** The Plan 05-10 Task 2 checkpoint (`checkpoint:human-verify`) was marked approved by the user without a live browser session. 05-10-SUMMARY line 199 states explicitly: "No browser session was run against a live server — spec correctness validated via code review + selector analysis only." The spec is syntactically correct and uses the right selectors, but the actual render quality (contiguous regions, no fragmenting) and correct generate flow through the UI are unverified behaviors that cannot be confirmed without running the application.

### Gaps Summary

**1 gap blocking full goal achievement:**

**SC-3: 12-file export contract not met.** The ROADMAP states "file contract IS" required for France 1066 — this language is unambiguous. The pipeline currently produces 10 files; `terrain_lookup.png` and `terrain_types.json` are present in CLAUDE.md's 12-file table but absent from `EXPORT_FILE_CONTRACT` (deferred to Phase 06 per a pipeline code comment). Phase 06's ROADMAP success criteria do not explicitly mention adding these two files — they focus on validation gates. This is a real gap, not a provably deferred item.

**To accept this deviation,** add to this file's frontmatter:

```yaml
overrides:
  - must_have: "France 1066 with toy synthetic dataset → ingest → generate → export produces 12 well-formed files (ROADMAP SC-3: 'file contract IS')"
    reason: "terrain_lookup.png and terrain_types.json are deferred to Phase 06 per pipeline docstring and EXPORT_FILE_CONTRACT_DEFERRED constant. Phase 06 will complete the full 12-file contract."
    accepted_by: "{your-name}"
    accepted_at: "{ISO timestamp}"
```

Or open Phase 05 with this gap for a plan to implement `terrain_lookup.png` and `terrain_types.json` generation.

**1 human verification item:**

**Playwright UAT visual sign-off** was bypassed at the user approval checkpoint. The spec file exists and is well-formed; the missing check is running it against a live server and confirming France render quality visually.

---

_Verified: 2026-05-12T15:30:00Z_
_Verifier: Claude (gsd-verifier)_
