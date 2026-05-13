# Phase 06: Export contract + validation gate - Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Harden the 12-file Unity export. The pipeline already emits all 12 files
(Phase 05 Plan 05-11 closed the terrain pair). Phase 06 adds:

- Strict pydantic schemas for every JSON output (5 contract JSONs +
  MANIFEST), validated at export time.
- A pre-zip validation gate that blocks export on five hard failures:
  territory <200px, lookup color collision, ocean leak, missing
  `original_idx`, and `pixel_center` Y-axis range failure.
- A new `POST /api/v3/projects/{id}/export` endpoint that:
  - Returns 201 + zip + structured MANIFEST when the gate passes.
  - Returns 422 + structured error envelope when the gate fails (no zip
    written).
  - Supports `?dry_run=true` — runs the gate, returns the report, never
    creates a zip.
- A MANIFEST.json carrying a `validation_report` section (passed,
  errors[], warnings[], sha256 per file, source, region_key,
  schema_version, generated_at).
- A backend-only delivery: existing v1 `api/export.py` is deleted; the
  frontend swap from v1 → v3 endpoint is deferred to a follow-up phase
  (06.1 or 07).

Deliverables:
- Backend: new `services/export/` subpackage:
  - `services/export/schemas.py` — pydantic models for all 5 contract
    JSONs + MANIFEST.
  - `services/export/validator.py` — pure function
    `validate_export(generated_dir: Path, cfg: RegionConfig) ->
    ValidationReport` callable from the endpoint and the zip builder.
    No HTTP coupling.
- Backend: new `api/v3/export.py` with `POST /{project_id}/export` +
  `GET /{project_id}/export/download`. Replaces `api/export.py`.
- Backend: refactor `services/export.py:build_unity_zip` to call
  `validate_export()` first; surface `ValidationReport` to caller; on
  failure raise a structured exception that the endpoint maps to 422.
- Backend: MANIFEST.json grows: `schema_version`, `region_key`,
  `generated_at_utc`, `validation_report: {passed: bool, errors: [...],
  warnings: [...]}`, and per-file `sha256` (alongside existing
  `source`, `size_bytes`).
- Tests:
  - `tests/unit/test_validator_<check>.py` (5 files) — each check in
    isolation with explicit numeric fixtures.
  - `tests/unit/test_export_schemas.py` — pydantic schema validation.
  - `tests/e2e/test_export_gate_iberia.py` — Iberia passes gate, 201,
    MANIFEST.validation_report.passed == true.
  - `tests/e2e/test_export_gate_france.py` — France passes gate, 201.
  - `tests/e2e/test_export_gate_broken.py` — fixture mutates
    France-generated/ to trigger every check; assert 422 + complete
    error list.
  - `tests/parity/test_iberia_868_yaml.py` extends with manifest
    assertion (Iberia parity now also gates).

Out of scope for Phase 06:
- Frontend UI swap from v1 `/api/projects/{id}/export` to v3
  endpoint — deferred to Phase 06.1 / Phase 07.
- Frontend error UI (toast, modal, dry-run preview) — deferred.
- Re-bake of Reconquista Iberia gold with `original_idx` populated on
  baronies — deferred to v3.1. Phase 06's MISSING_ORIGINAL_IDX gate
  is condados-only (D-11 revised); no per-region opt-out flag needed
  because Iberia passes the gate cleanly today.
- Pixel_center coordinate conversion (numpy Y-down → Unity Y-up).
  Unity loader already handles inversion on load; flipping at export
  would break byte-parity with Reconquista gold. Documented as a Y-down
  invariant in the schema field comment.
- Cross-field pydantic constraints (e.g., `kingdom_colors` keys match
  `kingdoms[*].id`). Phase 06 keeps validation field-local + check-local.
- Configurable per-region `min_territory_px`. Uses the existing
  `RegionConfig.blob_merge_px = 200` as the threshold.
- Hashing algorithm choices beyond SHA-256 (MANIFEST stores sha256
  only).
- RFC 7807 problem+json envelope. Custom structured-list envelope is
  the contract.

</domain>

<decisions>
## Implementation Decisions

### Gate architecture + endpoint

- **D-01 (validator in `services/export/validator.py`):** New subpackage
  `services/export/` houses `validator.py` exposing
  `validate_export(generated_dir: Path, cfg: RegionConfig) ->
  ValidationReport`. Pure function; reads files, no side effects, no
  HTTP coupling. The existing `services/export.py:build_unity_zip`
  calls it before assembling the zip. Reusable from CLI / dry-run / UI
  preview without dragging FastAPI deps. Pattern mirrors Phase 02
  `services/pipeline/adapters/` subpackage flat layout.

- **D-02 (hard-fail only — no `?force` override):** Endpoint returns
  422 with the structured error list. No override knob. Karpathy:
  don't design for hypothetical future requirements. SC #4 says
  "broken is blocked" — an override would let broken zips reach Unity.
  If a future dev workflow ever needs an override, that's its own
  decision in its own phase.

- **D-03 (`POST /export?dry_run=true` runs gate only):** Same endpoint,
  query parameter. `dry_run=true`: validator runs, response body is
  the `ValidationReport` (passed, errors[], warnings[], files_checked),
  no zip written, status 200 if passed / 422 if failed. `dry_run=false`
  (default): validator + zip. Single endpoint keeps the surface flat;
  UI can prefetch the report before triggering a real export.

- **D-04 (delete v1 `api/export.py`):** Per D-V3-04 (PROJECT.md key
  decision: delete v1 obsolete code, no namespace transitional shims).
  `api/export.py` and `backend/tests/test_export.py` are deleted in
  the same plan that registers `api/v3/export.py`. Tests rewritten
  under `tests/e2e/` per the new endpoint contract. v1 has zero
  callers in v3 frontend (Phase 03 stripped them); no migration
  hop needed.

### Schema validation + manifest shape

- **D-05 (pydantic models for all 5 contract JSONs + MANIFEST):**
  `services/export/schemas.py` exports six `BaseModel` classes:
  `LookupBaronyColorsSchema`, `LookupCondadoColorsSchema`,
  `TerrainTypesSchema`, `TerritoryMetadataSchema`,
  `MountainRiverDataSchema`, `ManifestSchema`. Each is `model_validate`-d
  by the validator before any rule check runs. Schema errors short-circuit
  the gate (rule checks don't see malformed JSON). Defense-in-depth:
  drift in pipeline output is caught at the file level before the
  semantic level.

- **D-06 (`services/export/` is the subpackage; not `contracts.py`):**
  Schemas live with the validator that consumes them. Mirrors Phase
  02 `services/pipeline/adapters/` flat-split. `contracts.py` stays
  focused on input contracts (`RegionConfig`, `ProjectDataset`,
  `EXPORT_FILE_CONTRACT`). Output validation = output package.

- **D-07 (MANIFEST stays forge-specific, gains fields):** Reconquista's
  `StreamingAssets/Maps/` ships PNGs and JSONs directly — no MANIFEST
  today. SC #3 "manifest matches Reconquista structure" is interpreted
  as "the *file set* matches", which is already enforced by
  `EXPORT_FILE_CONTRACT` (Phase 05 Plan 05-15). MANIFEST.json stays
  as a Forge-specific top-level entry inside the zip and grows:
  ```
  {
    "schema_version": 2,
    "region_key": "iberia_868",
    "project_id": "<uuid>",
    "generated_at_utc": "2026-05-13T...",
    "exported_at_utc": "20260513-...",
    "spec_version": 1,
    "phase": 6,
    "validation_report": {
      "passed": true,
      "errors": [],
      "warnings": [...]
    },
    "files": [
      {"name": "lookup_barony.png", "source": "generated",
       "size_bytes": 12345, "sha256": "..."}
    ]
  }
  ```
  `schema_version: 2` is bumped from `1` so consumers can detect the
  change. Unity loader can ignore MANIFEST entirely if it wants
  byte-parity equivalent semantics; the file set is canonical.

- **D-08 (custom structured-list error envelope):** 422 body:
  ```json
  {
    "detail": {
      "summary": "4 errors blocked export",
      "errors": [
        {
          "code": "COLOR_COLLISION",
          "severity": "error",
          "file": "lookup_condado.png",
          "context": {"rgb": [124, 179, 66], "territories": ["c003", "c047"]},
          "message": "Color (124,179,66) maps to 2 condados"
        }
      ],
      "warnings": []
    }
  }
  ```
  Stable codes: `SCHEMA_INVALID`, `COLOR_COLLISION`, `OCEAN_LEAK`,
  `MISSING_ORIGINAL_IDX`, `TERRITORY_TOO_SMALL`, `PIXEL_CENTER_OUT_OF_RANGE`.
  `severity`: `"error"` or `"warning"`. Phase 06 emits only errors —
  warnings slot is wired but unused (future use, e.g., territories
  near the 200px floor). Codes are i18n-stable; UI can localize per
  code without parsing English messages. Not RFC 7807 problem+json —
  overkill for a single-user local tool.

### Definitions of the 5 gate checks

- **D-09 (OCEAN_LEAK = territory color in landmask-ocean pixel):**
  For each of `lookup_barony.png` and `lookup_condado.png`: read RGB
  raster + the landmask numpy array from the run (re-derived from the
  GeoJSON / cached). Compute `mask_ocean = ~landmask` (Pitfall:
  landmask is bool, not the ocean color). For every pixel where
  `mask_ocean == True`, the RGB must equal ocean's canonical color
  (the sentinel ocean cell, derived per CLAUDE.md rule 5 sentinel
  values + the cfg's `ocean_near` / `ocean_far` gradient). Any other
  RGB = ocean leak; record the territory id (look up via lookup colors
  JSON) + the pixel count. One-way (leak from land to ocean only);
  the bidirectional "ocean inside polygon" check is out of scope —
  legitimate enclosed lakes/lagoons would false-positive.

- **D-10 (PIXEL_CENTER_OUT_OF_RANGE = bounds check; numpy Y-down
  preserved):** For every condado/barony entry in
  `territory_metadata.json`, validate `0 <= pixel_center[0] < map_w`
  and `0 <= pixel_center[1] < map_h`. No orientation conversion.
  `pixel_center` ships as `[col, row]` (numpy convention from Phase 01
  PREFLIGHT Q9 + v1 archive ARCHITECTURE.md:252). Unity loader handles
  Y-up inversion on load (Reconquista already does this). The schema
  field comment documents the convention explicitly:
  ```
  pixel_center: tuple[int, int]  # [col, row] numpy Y-down; Unity flips on load
  ```
  The v1-archive PROJECT.md "convert on export" idea is rejected: it
  would break byte-parity with Reconquista gold and force a re-bake.

- **D-11 (MISSING_ORIGINAL_IDX = condados-only; baronies exempt by
  canonical shape):** Gate requires every CONDADO to carry
  `original_idx`. Baronies are EXEMPT — the canonical barony shape is
  `{name, condado_idx, duchy, pixel_count}` (verified in
  `tests/fixtures/iberia_868/golden/territory_metadata.json` lines
  1838+; `services/pipeline/export.py:37-82` writer never emits
  `original_idx` on baronies). The Unity `byOriginalIdx` lookup
  (CLAUDE.md rule 7) is condado-keyed; baronies use positional
  `condado_idx`. No `enforce_original_idx` YAML flag is added; no
  RegionConfig field is added; no per-region opt-out exists. Iberia
  passes the gate cleanly (golden has `original_idx: 1..92` on all 92
  condados, 91 emitted after `npx == 0` compaction). France / England
  / autogen enforce the same condados-only rule. CLAUDE.md rule 4
  (Nájera bug — indices > 44) stays covered: every condado that exists
  must carry `original_idx`. Phase 06 RESEARCH (Risk Register
  BLOCKER) reconciled the stale "0/92 original_idx" rationale from
  CONTEXT initial draft against verified repo state (2026-05-13).

- **D-12 (TERRITORY_TOO_SMALL threshold = 200px = `blob_merge_px`):**
  Gate computes pixel count per condado_id from `lookup_condado.png`.
  Any condado with count < 200 fails. Uses the existing
  `RegionConfig.blob_merge_px = 200` (Phase 01 default; Phase 05
  preserved). ROADMAP literal "<200px" matches this constant. No new
  config field needed. Same check at barony level uses
  `blob_merge_px` too (single threshold; baronies that survive cleanup
  can be smaller than condados but cannot be < 200 in the final
  lookup). Future per-territory-tier thresholds: deferred.

- **D-13 (COLOR_COLLISION scope = within-file + cross-layer terrain):**
  For each of `lookup_barony.png` and `lookup_condado.png`: count
  unique RGB values; each must map to exactly one territory id per
  the matching `lookup_*_colors.json`. Cross-file collision (barony
  color == condado color) is intentional and allowed (different
  layers, different lookups). Cross-layer with terrain: `terrain.py`
  already enforces no collision between PLAINS_RGB/OCEAN_RGB and any
  cfg color via `assert_palette_no_collision` (Phase 05 Plan 05-11);
  Phase 06 promotes that check into the gate (collision → error code,
  not exception). Order: SCHEMA_INVALID first, then per-file checks,
  then cross-layer terrain check.

### Fixtures + test pyramid

- **D-14 (broken project as test fixture, not committed YAML):**
  `tests/e2e/test_export_gate_broken.py` defines pytest fixtures that
  run France 1066 pipeline OK, then mutate `generated/`:
  - One fixture drops `original_idx` from a single condado.
  - One fixture paints 100 ocean-mask pixels with a condado's RGB in
    `lookup_condado.png` (writes back via PIL).
  - One fixture rewrites `lookup_condado_colors.json` to map two ids
    to the same RGB.
  - One fixture shrinks a single territory to 150 pixels in
    `lookup_condado.png`.
  - One fixture sets `pixel_center: [-1, 0]` in `territory_metadata.json`.
  - One fixture combines all five for an aggregate "every error code
    fires once" test.
  Each fixture invokes `POST /api/v3/projects/{id}/export`, asserts
  422, and asserts the expected `code` + `severity` + `file` + the
  presence of the relevant territory id in `context`. No
  `data/regions/broken_test.yaml` is committed — fixtures keep the
  data dir clean and bind broken-cases to test source.

- **D-15 (three-layer test pyramid):** Layered coverage per CLAUDE.md
  conventions:
  - **Unit:** `tests/unit/test_validator_color_collision.py`,
    `test_validator_ocean_leak.py`,
    `test_validator_original_idx.py`,
    `test_validator_territory_size.py`,
    `test_validator_pixel_center.py`. Each test file exercises the
    check function with minimal numpy arrays + dict fixtures. Tests
    named descriptively with explicit numeric fixtures (per user
    preference). `tests/unit/test_export_schemas.py` exercises every
    pydantic schema with valid + structurally-invalid payloads.
  - **Parity:** `tests/parity/test_iberia_868_yaml.py` extends with
    `assertExport(Iberia)` returning 201, MANIFEST.validation_report.passed
    == true, AND continues to assert byte-equal lookups + SSIM
    visuals. Gate failure on Iberia = parity regression.
  - **E2E:** `tests/e2e/test_export_gate_iberia.py`,
    `tests/e2e/test_export_gate_france.py`,
    `tests/e2e/test_export_gate_broken.py` (described in D-14).
  No frontend tests in Phase 06 (D-19).

- **D-16 (Iberia parity test asserts gate passes):**
  `tests/parity/test_iberia_868_yaml.py` adds a final assertion: post
  `run_pipeline(cfg)`, invoke the endpoint via TestClient (or call
  `build_unity_zip` directly + read the manifest from the resulting
  zip), assert `manifest["validation_report"]["passed"] == true`.
  Iberia must satisfy the gate WITH the `original_idx` exemption
  active (D-11). Any regression that breaks Iberia's gate-pass is a
  parity break; CI catches it the same as a byte-mismatch.

- **D-17 (per-check structured error assertions):** Each broken
  fixture test asserts EXACTLY the expected error codes (no more, no
  fewer). Example: the "ocean leak only" fixture asserts
  `errors == [{code: OCEAN_LEAK, ...}]`. The aggregate fixture
  asserts the full set of 5 codes are all present. This forces the
  validator to be exhaustive (not short-circuit) — it must report
  every failing check, not stop at the first.

- **D-18 (validator runs every check; collects all errors):** No
  fail-fast. `validate_export` runs all 5 checks even if check #1
  found errors. The endpoint maps the aggregated `ValidationReport`
  to 422 only if `len(errors) > 0`. Schema-invalid still
  short-circuits (a malformed JSON cannot meaningfully feed downstream
  semantic checks).

- **D-19 (frontend UI deferred):** Phase 06 ships zero frontend code.
  The frontend Export button (Phase 03/04 UI) still calls the v1
  endpoint until a follow-up phase (06.1 or 07) swaps it to v3 +
  renders the structured error envelope. Karpathy:
  surgical changes, no scope creep. Phase 06 ships backend gate
  + tests; UI is its own work.

### Folded Todos

None — `gsd-tools todo match-phase 06` returned `todo_count=0`.

### Claude's Discretion

- **Sentinel ocean color in OCEAN_LEAK (D-09).** Exact RGB value
  treated as "ocean" in the lookup PNGs — the lookup PNGs paint ocean
  with a specific color; planner reads the existing render code
  (`render.py`) and codifies the canonical "ocean RGB in lookup_*.png"
  as a single constant in `services/export/validator.py` or imports
  it from `render.py` if already exposed.
- **MANIFEST `sha256` computation point.** Hashing files at zip-write
  time vs. at validator time. Planner picks; validator-time is more
  natural (validator already reads every file).
- **Subpackage layout: `services/export/` vs `services/pipeline/export/`.**
  Recommendation: top-level `services/export/` (sibling of
  `services/pipeline/`) because the export gate operates on pipeline
  outputs but is not part of the geometric pipeline. Planner verifies
  import graph cleanliness.
- **Exception type from `validate_export` failure.** Custom
  `ValidationFailedError(report: ValidationReport)` vs returning the
  report and letting the caller branch. Planner picks; returning
  the report keeps validator pure.
- **Schema versioning of MANIFEST.** D-07 sets `schema_version: 2`.
  Planner decides whether to keep the bump as a constant in
  `schemas.py` or compute from a `__version__`-style module field.
- **Test file split: 5 files vs 1 file with TestCase classes.**
  Recommendation: 5 files (one per check) for descriptive names per
  user preference + faster `pytest -k` filtering. Planner may merge
  if 5 files cause `__init__.py` noise.
- **Endpoint mount order.** Whether `api/v3/export.py` is registered
  before or after `api/export.py` deletion lands. Same plan or
  sequenced plans? Planner picks; doing both in one plan keeps the
  parity gate green (no period where two routes coexist).
- **Iberia `enforce_original_idx: false` location.** Set in
  `data/regions/iberia_868.yaml` or hard-coded in
  `RegionConfig.__post_init__`? Recommendation: YAML flag —
  explicit per-region, no special-case code branches.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract & success criteria
- `.planning/ROADMAP.md` §"Phase 06: Export contract + validation gate
  (merged)" — four success criteria; SC #4 is the broken-project gate.
- `.planning/PROJECT.md` §"Key Decisions" — D-V3-04 (delete v1 dead
  code, no namespace; drives D-04 deletion of `api/export.py`),
  D-V3-05 (`RegionConfig` is the only mutable input; validator
  consumes but does not mutate).

### Pipeline contract (algorithm + data shapes)
- `CLAUDE.md` §"v3 Pipeline Contract" — 12-file Unity output; gate
  enforces all 12 present + schema-valid.
- `CLAUDE.md` §"Non-negotiable rules" — rule 4 (`original_idx` in
  every territory; Nájera bug) drives D-11; rule 5 (`ocean=-1`,
  `ignore=9999` sentinels) drives D-09 ocean leak definition; rule
  7 (`byOriginalIdx` Unity-side) ties to D-11 enforcement.
- `CLAUDE.md` §"Conventions" — `services/pipeline/` submodule layout
  (Phase 06 adds sibling `services/export/`); three-layer test pyramid
  (drives D-15).
- `CLAUDE.md` §"What v3 explicitly is NOT" — no upscale interpolation
  (gate doesn't introduce one); no global Voronoi (irrelevant here
  but referenced for consistency).

### Pipeline implementation (extension + refactor targets)
- `backend/medieval_forge/services/pipeline/contracts.py` —
  `EXPORT_FILE_CONTRACT` is the canonical 12-file tuple (Phase 05
  Plan 05-15). Phase 06 reads it; never duplicates.
- `backend/medieval_forge/services/pipeline/terrain.py` —
  `assert_palette_no_collision` (Phase 05 Plan 05-11) becomes a
  validator-callable check. Promoted from `ValueError` to a
  COLOR_COLLISION report entry.
- `backend/medieval_forge/services/pipeline/render.py` — source of
  truth for "ocean RGB" in lookup PNGs; validator imports or mirrors.
- `backend/medieval_forge/services/pipeline/lookup.py` — produces
  `lookup_*_colors.json`; validator reads to detect within-file
  collisions.
- `backend/medieval_forge/services/pipeline/__init__.py` —
  `EXPORT_FILE_CONTRACT` re-export pattern; Phase 06 may add
  `validate_export` re-export here.
- `backend/medieval_forge/services/export.py` — current
  `build_unity_zip`. Phase 06 refactors to call `validate_export()`
  before assembly; raises on failure.

### Backend HTTP layer (delete + replace targets)
- `backend/medieval_forge/api/export.py` — **DELETED** in Phase 06.
  Replaced by `api/v3/export.py`.
- `backend/medieval_forge/main.py` — registers `api/v3/export.py`
  router; removes legacy `api/export.py` mount.
- `backend/medieval_forge/api/v3/__init__.py` — registers the new
  export router alongside `generate`, `render`, `ingest`, `regions`,
  `projects`.

### Frontend (no changes in Phase 06)
- Existing Export button (Phase 03/04 UI) — continues to call v1
  `/api/projects/{id}/export` until Phase 06.1 / Phase 07 swaps it.
  No frontend tasks in Phase 06 per D-19.

### Phase carry-forward
- `.planning/phases/01-pipeline-parity-port-harness-together/01-CONTEXT.md`
  — PREFLIGHT Q8 (Iberia deployed has 0/92 `original_idx`; drives
  D-11 Iberia exemption); PREFLIGHT Q9 (`pixel_center` is numpy Y-down;
  drives D-10 no-conversion).
- `.planning/phases/05-region-generalization/05-CONTEXT.md` — D-02
  (pydantic schema validation pattern; reused for output schemas),
  D-15 (region_loader.load_region API; validator receives
  `cfg = load_region(project.region_key)`), D-17 plan sequencing
  (parity stays green; Phase 06 sequencing follows the same
  pattern — gate lands before legacy deletion if both are in same
  wave).
- `.planning/phases/05-region-generalization/05-11-PLAN.md` (and its
  summary) — terrain pair landing; `assert_palette_no_collision`
  promotion target.

### Reconquista contract (read-only ground truth)
- `D:\Projetos_Jogo\Reconquista\Assets\StreamingAssets\Maps\*` — file
  set (not a MANIFEST.json) is the SC #3 reference. Phase 06's
  MANIFEST is Forge-specific and additive.
- `inicio/map_generator.py` — gold reference; never modified.
- `inicio/licoes/JORNADA_CRIACAO_MAPA.md` — historical rationale for
  rule 4 (Nájera) + rule 5 (sentinel values).

### v1-archive (caveats only)
- `.planning/v1-archive/PROJECT.md` line 74 — note "pixel_center is
  Y-down (numpy); Unity is Y-up — convert on export". Phase 06
  REJECTS the conversion approach per D-10 (would break byte-parity
  with Reconquista gold; Unity already inverts on load).
- `.planning/v1-archive/ROADMAP.md` line 211 — same conversion note.
  Same rejection.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`EXPORT_FILE_CONTRACT`** in `pipeline/contracts.py:193-206` —
  authoritative 12-file tuple. Validator iterates this for presence
  + sha256.
- **`assert_palette_no_collision(cfg)`** in `pipeline/terrain.py:47-75`
  — collision check between `PLAINS_RGB`/`OCEAN_RGB` and cfg colors.
  Phase 06 generalizes: instead of `raise ValueError`, return
  structured error; check covers cross-layer terrain + within-file
  lookup_*_colors.json collisions.
- **`build_unity_zip(project_id)`** in `services/export.py:60-117` —
  existing zip assembler with MANIFEST. Phase 06 refactors to call
  validator first; expands MANIFEST shape per D-07.
- **Pydantic v2** — already used by `services/pipeline/region_loader.py`
  for `RegionConfigSchema`. Same `BaseModel` + `Field(...)` patterns
  reused for Phase 06 output schemas.
- **FastAPI `api/v3/*` modules** — pattern: thin file, single
  `router = APIRouter(prefix=...)`, registered in `main.py`. New
  `api/v3/export.py` follows the pattern.
- **`is_valid_uuid` + `project_dir` + `ensure_project_dirs`** in
  `services/paths.py` — reuse in the new endpoint.
- **`_ALLOWED_PRE_EXPORT_STATUSES = {"generated", "exported"}`** in
  `api/export.py:18` — status gate carries to v3 endpoint.
- **Pytest fixtures pattern** — `tests/e2e/test_france_1066_export_contract.py`
  session-scoped `france_output` fixture is the template for the
  broken-project fixtures (run pipeline once, mutate copies in-place).
- **`tests/parity/test_iberia_868_yaml.py`** — extended with one
  additional assertion (D-16).

### Established Patterns

- **`services/pipeline/<submodule>.py` layout** — flat split. Phase
  06 introduces sibling `services/export/` subpackage with
  `validator.py` + `schemas.py` + (later) `__init__.py` re-exports.
- **Atomic commits per task**: `feat(06-NN): ...`, `chore(06-NN): ...`,
  `test(06-NN): ...`.
- **Pydantic v2 schema → validate → convert**: `yaml.safe_load → Schema.model_validate
  → cfg = RegionConfig(**model.model_dump())` from
  `region_loader.py`. Phase 06 mirrors for output:
  `json.loads(path.read_bytes()) → Schema.model_validate → ...`.
- **Tests with descriptive names + explicit numeric fixtures** — user
  preference; carries to validator unit tests (e.g.,
  `test_ocean_leak_reports_exact_pixel_count_and_territory_id`).
- **Status state machine**: `created → ingested → generating →
  generated → exporting → exported`. Phase 06 keeps; gate-fail
  returns 422 without flipping status.
- **Server restart before UAT** — user preference; not applicable
  Phase 06 (backend-only, no UI).

### Integration Points

- **Backend new files (Phase 06):**
  - `backend/medieval_forge/services/export/__init__.py`
  - `backend/medieval_forge/services/export/schemas.py`
  - `backend/medieval_forge/services/export/validator.py`
  - `backend/medieval_forge/api/v3/export.py`
  - `backend/tests/unit/test_export_schemas.py`
  - `backend/tests/unit/test_validator_color_collision.py`
  - `backend/tests/unit/test_validator_ocean_leak.py`
  - `backend/tests/unit/test_validator_original_idx.py`
  - `backend/tests/unit/test_validator_territory_size.py`
  - `backend/tests/unit/test_validator_pixel_center.py`
  - `backend/tests/e2e/test_export_gate_iberia.py`
  - `backend/tests/e2e/test_export_gate_france.py`
  - `backend/tests/e2e/test_export_gate_broken.py`

- **Backend deletions:**
  - `backend/medieval_forge/api/export.py`
  - `backend/tests/test_export.py` (rewritten under tests/e2e)

- **Backend modifications:**
  - `backend/medieval_forge/services/export.py` (call validator first,
    new MANIFEST shape; refactored to `services/export/zip.py` per
    RESEARCH §Per-Discretion #4 layout)
  - `backend/medieval_forge/main.py` (mount v3 export router; drop v1)
  - No `enforce_original_idx` field added to `RegionConfig`,
    `RegionConfigSchema`, or `data/regions/iberia_868.yaml` — D-11
    revised to condados-only; Iberia passes the gate without any
    per-region flag
  - `backend/tests/parity/test_iberia_868_yaml.py` (asserts MANIFEST
    validation_report.passed == true)
  - `backend/tests/e2e/test_france_1066_export_contract.py` (may
    consolidate with `test_export_gate_france.py` or stay separate
    — planner picks)

- **Frontend modifications:** NONE in Phase 06.

</code_context>

<specifics>
## Specific Ideas

- **"Five hard checks, no override"** — D-02 keeps the gate strict;
  SC #4 explicitly says "broken is blocked". No `?force=true`,
  no severity laundering.
- **"Dry-run on the same endpoint"** — D-03 ?dry_run=true; UI can
  preflight before paying the zip cost.
- **"Delete v1, don't bridge"** — D-04 + D-V3-04 (PROJECT.md).
  `api/export.py` goes away; frontend swap deferred to its own phase.
- **"Gate scope is condados-only"** — D-11 revised. Iberia passes
  without a flag (all 92 condados carry `original_idx`); baronies
  exempt by canonical shape. France / England / autogen follow the
  same rule. CLAUDE.md rule 4 (Nájera bug, indices > 44) still
  covered for every condado.
- **"No Y-axis conversion at export"** — D-10. The v1-archive note
  about "convert on export" is explicitly rejected. Reconquista
  Unity loader already inverts; flipping at export breaks byte-parity
  with gold.
- **"MANIFEST is Forge-specific"** — D-07. Reconquista has no
  MANIFEST today; SC #3 is about file *set* matching, which
  `EXPORT_FILE_CONTRACT` already enforces.
- **"Stable error codes for i18n"** — D-08. `COLOR_COLLISION`,
  `OCEAN_LEAK`, etc. UI (future phase) localizes per code, never
  parses the English message.
- **"Tests with descriptive names + explicit numeric fixtures"** —
  user preference (memory: feedback-tests-descriptive.md). Validator
  unit tests use explicit small numpy arrays + dict fixtures, not
  fuzzed inputs.
- **"Each broken fixture asserts exact codes"** — D-17 forces the
  validator to be exhaustive (not short-circuit). Aggregate fixture
  proves all 5 codes co-exist in one report.

</specifics>

<deferred>
## Deferred Ideas

- **Frontend UI swap to v3 export endpoint** — Phase 06.1 or 07.
  Today's Export button still calls v1; v1 is deleted in Phase 06,
  which means the button is temporarily broken between Phase 06
  merge and the UI swap. Acceptable — UI is not under SC in v3
  PROJECT.md; tools-first delivery (PROJECT.md Constraints).
  Mitigation: the UI swap PR is the very next thing after Phase 06.
- **Frontend rich error UI** (modal, dry-run preview, per-code
  i18n) — Phase 06.1+. Stable codes from D-08 make this
  straightforward later.
- **Re-bake of Reconquista Iberia gold with `original_idx` populated**
  — v3.1. Requires coordinated Unity-side update; current gold has
  0/92 (PREFLIGHT Q8). Phase 06 exempts Iberia explicitly (D-11)
  rather than re-bake.
- **`pixel_center` Y-up conversion at export** — rejected by D-10.
  Would require re-baking Reconquista gold and changing Unity
  loader assumptions. Stays deferred indefinitely; could resurface
  if Unity loader spec changes.
- **Cross-field pydantic constraints** (e.g., `kingdom_colors` keys
  match `kingdoms[*].id`) — Phase 05 deferred similar constraint;
  Phase 06 keeps validation field-local + check-local. v3.1.
- **`POST /api/v3/regions/validate`** — dry-run endpoint for region
  YAMLs (Phase 05 deferred). Phase 06's `?dry_run=true` is the
  export-side equivalent; region-side validation lives with the
  region_loader, separate work.
- **Configurable per-region `min_territory_px`** — Phase 06 uses
  `blob_merge_px` (200). If a region needs a different floor, add
  `export_min_territory_px` to `RegionConfig` later.
- **Per-territory-tier thresholds** (different minimum for baronies
  vs condados) — same floor today; can split if data demands.
- **MANIFEST `schema_version` migration tooling** — D-07 bumps to 2.
  If schema evolves further, a small forward-compat dict-to-dict
  migration in the consumer is straightforward. Not Phase 06.
- **Bidirectional ocean leak (water inside polygon)** — D-09 one-way
  only. Lakes/lagoons would false-positive. If a use case emerges,
  treat as new check code `OCEAN_INSIDE_POLYGON`.
- **RFC 7807 problem+json** — D-08 rejects. If Forge ever exposes
  the API externally, revisit.
- **CLI dry-run command** (`medieval-forge validate-export <project>`)
  — pure-function `validate_export` is CLI-friendly today. A wrapper
  command is a small follow-up; not Phase 06.
- **Hashing algorithm beyond SHA-256** — D-07 fixes sha256. BLAKE3 /
  xxhash would be faster on large zips; sha256 is fine for the
  default <50MB output.
- **Validation report streaming via SSE for very large regions** —
  validator is fast enough for 1920×1080; SSE overhead not worth it.
  If a region grows, revisit.

### Reviewed Todos (not folded)

None — `gsd-tools todo match-phase 06` returned `todo_count=0`.

</deferred>

---

*Phase: 06-export-contract-validation-gate*
*Context gathered: 2026-05-13*
