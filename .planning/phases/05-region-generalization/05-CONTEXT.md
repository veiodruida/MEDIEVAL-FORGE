# Phase 05: Region generalization - Context

**Gathered:** 2026-05-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Externalize the Iberia configuration (currently hard-coded across
`services/pipeline/regions.py` + `data/regions/iberia_868/territory_data.py`)
into per-region YAML packs loadable by a single `load_region(key)` API.
Ship two additional templates — `france_1066.yaml` and `england_1216.yaml` —
proving the pipeline is region-agnostic. France 1066 with a committed toy
synthetic dataset must run ingest → generate → export end-to-end and emit
the 12-file Unity contract (parity against Reconquista NOT required for
France; the *contract* is). England 1216 ships YAML-only (no inputs).

Deliverables:
- Backend: new `services/pipeline/region_loader.py` exposing
  `load_region(key: str) -> RegionConfig`. Reads `data/regions/{key}.yaml`,
  validates via pydantic schema, resolves input paths relative to repo
  root, returns a populated `RegionConfig` dataclass. In-memory cache
  keyed by `(key, file_mtime)`. Replaces the `REGIONS = {"iberia_868":
  iberia_config}` registry in `regions.py`.
- Backend: new `GET /api/v3/regions` endpoint lists available regions
  with `{key, name, bounds, has_dataset}`. Backs the create-project modal.
- Backend: Alembic migration adds `region_key VARCHAR(64) NOT NULL
  DEFAULT 'iberia_868'` to the `projects` table; backfills existing rows.
  `api/v3/generate.py:130` and `api/v3/render.py:128` swap their
  hard-coded `iberia_config()` calls for `load_region(project.region_key)`.
- Migration tooling: `scripts/migrate_iberia_to_yaml.py` (one-shot;
  reads KINGDOMS/DUCHIES/CONDADOS from `territory_data.py` and emits
  `data/regions/iberia_868.yaml`) + `scripts/gen_toy_france.py` (one-shot;
  generates ~50 Voronoi-from-grid municipalities and a stub
  `mountain_river_data.json`, writes them into
  `data/regions/france_1066/inputs/`). Both scripts committed for
  reproducibility; their outputs (the YAML, the GeoJSON) committed too.
- Cleanup: after the migration script generates `iberia_868.yaml`,
  delete `services/pipeline/regions.py:iberia_config()` + `REGIONS` dict +
  `backend/medieval_forge/data/regions/iberia_868/territory_data.py`
  (per D-V3-04 — delete dead v1-equivalent code, do not namespace).
- Pipeline graceful degradation: when `kingdoms`/`duchies`/`condados`
  are empty (France/England templates), the pipeline autogenerates
  N synthetic condados from dataset centroids (1 default "unnamed"
  kingdom, deterministic colors via `rng_seed=42`). Iberia's populated
  YAML continues to use real territory data.
- Frontend: new "New project" modal with `<select>` (Radix `Select.Root`)
  showing the regions returned by `GET /api/v3/regions`. Default
  selection = Iberia 868. Submit posts to `POST /api/v3/projects`
  carrying `region_key`.
- Tests: hard parity gate `tests/parity/test_iberia_868_yaml.py` —
  loads via `load_region('iberia_868')`, runs full pipeline, asserts
  byte-equal lookup PNGs + SSIM ≥ 0.98 visuals vs. the Phase 01 golden
  set. France 1066 SC-3 test runs the toy ingest → generate → export
  chain and asserts the 12-file contract is well-formed (file presence,
  PNG dimensions, JSON schema), NOT pixel-equal to anything.

Out of scope for Phase 05:
- Pixel parity for France/England (SC-3 says contract only)
- England 1216 toy inputs — only the YAML ships; generate aborts with
  a clear "inputs missing for england_1216" error
- Historical research data (names, owners, notes) for France/England —
  deferred to v3.1 (PROJECT.md "Out of Scope")
- Multi-country routing generalization (PT/ES KD-tree pattern stays
  Iberia-specific; new regions get a single global KD-tree path
  because `border_polygon` defaults to empty)
- User-uploaded region YAMLs at runtime (v3.1+)
- DEM raster ingestion (slot already reserved in `ProjectDataset`)
- Bounds auto-detection from dataset (bounds explicit in each YAML)
- LLM-assisted region creation (Phase 07)

</domain>

<decisions>
## Implementation Decisions

### YAML schema + region pack layout

- **D-01 (single-file region.yaml):** Each region is one YAML file at
  `data/regions/{key}.yaml` carrying ALL config (map_w/map_h, lon/lat
  bounds, kingdom_colors, all cleanup thresholds, border_polygon inline
  as a list of `[lon, lat]` pairs, kingdoms/duchies/condados arrays).
  Geometry inputs (PT/ES GeoJSON, mountain_river_data.json) stay under
  `data/regions/{key}/inputs/` — same layout Iberia already uses. One
  file = one region = easy to copy/template. No split files.

- **D-02 (pydantic schema validation):** New `RegionConfigSchema(BaseModel)`
  in `services/pipeline/region_loader.py` mirrors the `RegionConfig`
  dataclass. Load order: `yaml.safe_load` → `RegionConfigSchema.model_validate`
  → convert to `RegionConfig(**model.model_dump())`. Validation errors
  surface structured (field path + reason). Enforces hard constraints
  from CLAUDE.md (e.g., `smooth_sigma ∈ [3.0, 4.5]` via `Field(ge=3.0, le=4.5)`).
  Pydantic v2 (already used elsewhere in backend).

- **D-03 (territory data — empty templates + autogenerate):** France
  1066 and England 1216 YAML templates ship with `kingdoms: []`,
  `duchies: []`, `condados: []`. When the pipeline detects empty
  territory arrays at the `voronoi`/`hierarchy` stage, it autogenerates
  N synthetic condados from dataset feature centroids: `Condado_001`..`Condado_NNN`,
  assigned to a single default kingdom `unnamed` with a gray color,
  deterministic via `rng_seed`. Iberia's populated YAML bypasses this
  path (non-empty arrays). The autogen path is a new branch — not a
  retrofit; planner picks the cleanest insertion point (`voronoi.py`
  or upstream in the loader).

- **D-04 (border_polygon optional, default empty):** `border_polygon`
  is `field(default_factory=list)` already in `RegionConfig`. France/England
  YAMLs simply omit it (or set `border_polygon: []`). Behavior to verify
  in `voronoi.py`: empty list → single global KD-tree across the whole
  region (no PT/ES routing). Planner verifies; likely already works
  because Iberia's 40-point polygon is what enables routing; absence
  falls through to single-tree. Multi-country routing schema NOT
  generalized in Phase 05.

### Region selection wire

- **D-05 (Project.region_key column):** Alembic migration adds
  `region_key VARCHAR(64) NOT NULL DEFAULT 'iberia_868'` to `projects`.
  Migration's `op.execute("UPDATE projects SET region_key='iberia_868'
  WHERE region_key IS NULL")` backfills any pre-existing rows (the
  DEFAULT covers new rows). First-class column, not stuffed into
  `generator_config` JSON. Future migrations can ALTER without YAML
  schema games.

- **D-06 (GET /api/v3/regions endpoint):** New `api/v3/regions.py`
  module. Lists `data/regions/*.yaml` (the YAML files at the top level,
  not the inputs subdirectories). For each, returns
  `{key, display_name, bounds: {lon_min, lon_max, lat_min, lat_max},
  has_dataset: bool}`. `has_dataset` is true iff the YAML's `dataset.*`
  paths all exist on disk (so frontend can disable England's
  "Create project" button or warn). Discoverable, extensible without
  redeploy if a YAML is dropped in.

- **D-07 (create-project modal with region dropdown):** New frontend
  modal `NewProjectModal.tsx` (or extension of existing project create
  flow — planner picks). Field: project name (text) + region (Radix
  `Select.Root` populated by `GET /api/v3/regions`). Default selected =
  `iberia_868`. Submit calls `POST /api/v3/projects` with
  `{name, region_key}`. The 'has_dataset: false' regions render
  disabled or with a warning tooltip. Default region keeps existing
  workflows working.

- **D-08 (bounds 100% per YAML):** Each region YAML declares
  `lon_min`/`lon_max`/`lat_min`/`lat_max` explicitly. France 1066:
  approx `lon: [-5, 8], lat: [42, 51]`. England 1216: approx
  `lon: [-6, 2], lat: [49.5, 56]`. `lon_scale` still derived in
  `RegionConfig.__post_init__`. No bounds auto-detect.

### France toy synthetic dataset

- **D-09 (Voronoi-from-grid geometry):** Toy France municipalities
  generated as Voronoi cells from N=50 jittered grid points seeded
  with `rng_seed=42`. Cells clipped to the France bbox. Polygons are
  irregular (closer to real municipalities than uniform squares would be),
  exercising the same `voronoi.py` / KD-tree code paths Iberia exercises.
  Generator script `scripts/gen_toy_france.py` uses `scipy.spatial.Voronoi`
  + `shapely` (both already available).

- **D-10 (~50 feature count):** N=50 grid points. Balance: enough for
  hierarchy clustering to yield ~10-15 condados after cleanup; pipeline
  runs in <5 s; CI cost negligible. (Iberia has ~3000 real municipalities
  — orders of magnitude more.) Plan tunes if 50 trips edge cases in
  median/cleanup.

- **D-11 (toy committed in inputs/):** Generator script
  `scripts/gen_toy_france.py` and its outputs
  `data/regions/france_1066/inputs/france_municipalities_toy.geojson` +
  `data/regions/france_1066/inputs/mountain_river_data.json` (stub —
  empty `mountains`/`rivers` arrays) are all committed to the repo.
  Script runs once during Phase 05; outputs are version-controlled
  fixtures from then on. Reproducible (anyone can re-run the script
  and get byte-equal output thanks to `rng_seed`).

- **D-12 (England 1216 YAML-only):** `data/regions/england_1216.yaml`
  ships with bounds + empty territory arrays. No
  `data/regions/england_1216/inputs/` directory. `GET /api/v3/regions`
  returns `has_dataset: false` for England. If a user creates an England
  project and clicks generate, pipeline raises a clear FileNotFoundError
  with message "inputs missing for england_1216 — see CLAUDE.md for the
  v3 pipeline contract". Future v3.1 work adds inputs.

### Iberia migration + loader API

- **D-13 (delete `iberia_config()` + `REGIONS` + `territory_data.py`):**
  After Plan 05-XX (migration script) generates `data/regions/iberia_868.yaml`,
  `services/pipeline/regions.py` is **deleted** (callable + REGIONS dict
  + module-level helpers), and `backend/medieval_forge/data/regions/iberia_868/territory_data.py`
  is **deleted** (no longer the source of truth). All callsites
  (`api/v3/generate.py:39,130`; `api/v3/render.py:42,128,198`; any tests
  importing `iberia_config`) migrate to `load_region(project.region_key)`
  or `load_region('iberia_868')` for unit-test fixtures. Per D-V3-04
  ("Delete obsolete v1 routes/stores rather than namespace them") —
  there is no transitional wrapper.

- **D-14 (hard parity gate test):** New
  `tests/parity/test_iberia_868_yaml.py` is non-skippable, marked
  `@pytest.mark.parity`. Body: `cfg = load_region('iberia_868')`, run
  `run_pipeline(cfg)` into a tmp output dir, compare every one of the
  Phase 01 golden files (lookup PNGs byte-equal + visual PNGs SSIM ≥ 0.98
  + JSON files structural equal). Same criteria as `test_iberia_868.py`.
  Both tests live side-by-side until the legacy `iberia_config()` is
  deleted (D-13); after deletion, `test_iberia_868.py` is rewritten to
  use `load_region` too (becomes redundant with the YAML test — planner
  may merge or keep both for defense in depth).

- **D-15 (load_region API):** New module
  `services/pipeline/region_loader.py` exports:
  ```python
  def load_region(key: str, regions_dir: Path | None = None) -> RegionConfig
  ```
  - `key`: e.g., `'iberia_868'`, `'france_1066'`, `'england_1216'`
  - `regions_dir`: defaults to `<repo_root>/data/regions/` (anchored via
    `Path(__file__).resolve().parents[4]` like `regions.py` already does)
  - Behavior: open `{regions_dir}/{key}.yaml`, `yaml.safe_load`, validate
    via `RegionConfigSchema`, resolve input paths in the YAML's `dataset`
    block to absolute `Path` objects, construct + return `RegionConfig`.
  - Cache: module-level dict `_REGION_CACHE: dict[str, tuple[float,
    RegionConfig]]` keyed by `key`, holding `(file_mtime, cfg)`. Cache
    hit when YAML's mtime hasn't changed. Cleared on explicit
    `clear_region_cache()` call (called from test fixtures + a future
    /admin reload endpoint if needed).
  - Error contract: `FileNotFoundError` for missing YAML;
    `pydantic.ValidationError` for schema violations; `FileNotFoundError`
    with explicit message for missing dataset paths.

- **D-16 (Alembic backfill):** Migration revision adds the `region_key`
  column with `server_default='iberia_868'` and `nullable=False`.
  Explicit UPDATE ensures any rows created between migration start and
  end (transactional, unlikely) carry the default. Single-user local
  tool, low concurrency risk. `models.py:Project` gains the
  `region_key: Mapped[str]` field.

- **D-17 (script ordering — Plan sequencing constraint):** Plans
  execute in this order so the parity gate can stay green throughout:
  1. Plan 05-01: introduce `region_loader.py` + pydantic schema + tests
     (still reading from a hand-rolled inline fixture, NOT from a real
     YAML on disk yet)
  2. Plan 05-02: run `scripts/migrate_iberia_to_yaml.py` once →
     `data/regions/iberia_868.yaml` committed
  3. Plan 05-03: hard parity gate test `test_iberia_868_yaml.py`
     committed + green
  4. Plan 05-04: swap `api/v3/generate.py` + `api/v3/render.py`
     callsites to `load_region(project.region_key)` + Alembic migration
     + Project model field
  5. Plan 05-05: delete `regions.py:iberia_config()` + `REGIONS` dict
     + `territory_data.py`; rewrite any remaining tests
  6. Plan 05-06: `scripts/gen_toy_france.py` + commit toy inputs +
     `france_1066.yaml`
  7. Plan 05-07: `GET /api/v3/regions` endpoint + tests
  8. Plan 05-08: frontend create-project modal + region dropdown
  9. Plan 05-09: `england_1216.yaml` template + error-path test
  10. Plan 05-10: France 1066 SC-3 end-to-end test (ingest → generate
      → export → assert 12-file contract well-formed)

  Planner may merge/split as long as the invariant holds: **Iberia
  parity gate must be green at every commit**. Plan 05-05 (deletion of
  `iberia_config()`) cannot land before Plan 05-03 (YAML parity gate).

### Folded Todos

None — `gsd-tools todo match-phase 05` returned `todo_count=0`.

### Claude's Discretion

- **Behavior of `voronoi.py` with empty `border_polygon`.** Recommended
  D-04 path assumes empty list falls through to a single global KD-tree
  (no PT/ES routing). Planner verifies in the current code; if not
  already true, planner adds the guard (cheap conditional) without
  changing Iberia parity.
- **Loader cache invalidation policy.** D-15 says mtime-based. Planner
  may switch to explicit `clear_region_cache()`-only (no mtime check)
  if mtime adds overhead or causes flake on Windows file timestamps
  (1-second resolution can mask back-to-back edits in tests).
- **YAML structure for `kingdoms`/`duchies`/`condados`.** Current
  Python source uses dict-of-dicts in some places, list-of-dicts in
  others (`territory_data.py` mixed). YAML form should be consistent —
  planner picks the cleaner shape (recommendation: list-of-dicts for
  ordered iteration; ID fields explicit).
- **Autogenerate insertion point (D-03).** In the loader (synthesize
  arrays before returning cfg) vs in `voronoi.py` (detect empty + branch).
  Loader is cleaner separation; pipeline branch is closer to where
  data is needed. Planner picks.
- **France toy mountain_river_data.json shape.** Empty arrays
  (`{"mountains": [], "rivers": []}`) probably enough — the rasterizer
  emits an empty mask layer. Verify rendering pipeline survives empty
  mountains/rivers (Iberia always has content).
- **`api/v3/regions.py` HTTP shape.** Whether `bounds` is nested
  (`{lon_min, ...}`) or flat (`lon_min, lon_max, ...`). Planner picks
  matching FastAPI conventions already in the codebase.
- **Create-project modal location in code.** Could extend existing
  ProjectList page with an inline modal, or new `NewProjectModal`
  component. Reuse Radix `Dialog.Root` pattern from elsewhere if used.
- **Path resolution: YAML-relative vs repo-root-relative.** D-15 says
  relative to `regions_dir`. But the YAML itself might write
  `dataset.pt_geojson: inputs/pt.geojson` (region-relative) vs
  `data/regions/iberia_868/inputs/pt.geojson` (repo-relative). Planner
  picks; YAML-relative is more portable.
- **migrate script idempotency.** `scripts/migrate_iberia_to_yaml.py`
  may be re-run (e.g., if `territory_data.py` is touched before
  deletion). Should it bail when `iberia_868.yaml` already exists,
  or overwrite? Idempotent overwrite is friendlier for development.
- **Frontend coverage threshold for `NewProjectModal`.** CLAUDE.md
  requires ≥80% in v3/. Modal is light logic + Radix primitives;
  planner targets representative tests, not 100%.
- **`test_iberia_868.py` retirement strategy.** After D-13 deletes
  `iberia_config()`, the legacy test loses its symbol. Planner picks:
  retire it (D-14's YAML test covers everything) or rewrite to use
  `load_region`. Recommendation: retire — defense in depth has a cost.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract & success criteria
- `.planning/ROADMAP.md` §"Phase 05: Region generalization" — three
  success criteria; SC-3 is the France end-to-end gate
- `.planning/PROJECT.md` §"Out of Scope (v3)" — historical research
  for non-Iberian regions deferred to v3.1 (drives D-03 autogenerate)
- `.planning/PROJECT.md` §"Key Decisions" — D-V3-04 (delete v1 dead
  code, no namespacing — drives D-13 hard-delete of `iberia_config()`),
  D-V3-05 (`RegionConfig` is the only mutable input — loader returns
  this type, nothing else), D-V3-07 (zero LLM in geometric path —
  Phase 05 stays geometry-only)

### Pipeline contract (algorithm + data shapes)
- `CLAUDE.md` §"v3 Pipeline Contract" — 12-file Unity output; SC-3
  France end-to-end test asserts this contract is well-formed
- `CLAUDE.md` §"Conventions" — `services/pipeline/` submodule layout
  (region_loader.py lands here); "atomic commits per task" rule
- `CLAUDE.md` §"What v3 explicitly is NOT" — no `sys.modules` patching
  (loader keeps a module-level cache dict, never re-imports);
  `RegionConfig` mutability rules drive D-15 contract
- `CLAUDE.md` §"Project / Constraints" — `smooth_sigma ∈ [3.0, 4.5]`
  rule #2 is the validation constraint baked into the pydantic schema
  (D-02)
- `CLAUDE.md` §"Project / Conventions" — three-layer test pyramid:
  unit (loader, schema, autogen) + parity (D-14) + UAT (France
  create-project modal end-to-end via Playwright)

### Pipeline implementation (refactor targets)
- `backend/medieval_forge/services/pipeline/regions.py` — file is
  DELETED in Plan 05-05 after migration completes; `_INPUTS_DIR`
  pattern (parents[4] anchor) migrates into `region_loader.py`
- `backend/medieval_forge/services/pipeline/contracts.py` —
  `RegionConfig` + `ProjectDataset` dataclasses stay; new pydantic
  `RegionConfigSchema` mirrors them; `__post_init__`'s `lon_scale`
  derivation still runs after schema → dataclass conversion
- `backend/medieval_forge/services/pipeline/voronoi.py` — verify
  empty `border_polygon` behavior (D-04); maybe wire D-03 autogen
  if loader-side insertion doesn't fit
- `backend/medieval_forge/data/regions/iberia_868/territory_data.py`
  — DELETED in Plan 05-05; its KINGDOMS/DUCHIES/CONDADOS are migrated
  to `data/regions/iberia_868.yaml` by `scripts/migrate_iberia_to_yaml.py`

### Backend HTTP layer (template + extension targets)
- `backend/medieval_forge/api/v3/generate.py:39,130` — `from
  ...services.pipeline.regions import iberia_config` and
  `cfg = iberia_config()` migrate to `from ...services.pipeline.region_loader
  import load_region` + `cfg = load_region(project.region_key)`
- `backend/medieval_forge/api/v3/render.py:42,128,198` — same swap
- `backend/medieval_forge/api/v3/__init__.py` (or `main.py`) — register
  the new `regions.router` for `GET /api/v3/regions`
- `backend/medieval_forge/models.py:23-41` — `Project` gains
  `region_key: Mapped[str] = mapped_column(String(64), nullable=False,
  default="iberia_868")`
- `backend/medieval_forge/api/v3/projects.py` (if exists) or
  `api/projects.py` — `POST /api/v3/projects` accepts `region_key`
  in body (planner finds the route)

### Frontend reuse (template + extension targets)
- Existing create-project flow (planner locates; current Phase 03/04
  contexts don't mention it explicitly — likely in `frontend/src/pages/`
  or `frontend/src/components/`)
- Radix `Select.Root` from `@radix-ui/themes` is the dropdown primitive;
  `Dialog.Root` for the modal shell
- TanStack Query: a `useRegions` hook fetches `GET /api/v3/regions`
  with caching (regions list rarely changes within a session)

### Phase carry-forward
- `.planning/phases/01-pipeline-parity-port-harness-together/01-CONTEXT.md`
  — D-04 (`REGIONS` registry pattern Phase 05 swaps); D-08 (vendored
  ProjectDataset structure carries to other regions' inputs/); D-13/D-14
  (KINGDOMS/DUCHIES/CONDADOS live on cfg — migration script extracts
  them verbatim into YAML)
- `.planning/phases/02-ingestion-adapter/02-CONTEXT.md` — D-13 stub
  pattern for mountain_river_json (France toy uses same stub shape);
  D-09-LIVE-WAIVER applies only to Iberia (France's toy is a different
  upstream path so no waiver inheritance)
- `.planning/phases/03-read-only-canvas-redesign/03-CONTEXT.md` — D-19
  (`updated_at` bump on full generate); region creation is a new
  project, not an update — touches `created_at` only
- `.planning/phases/04-parameter-studio-live-re-render/04-CONTEXT.md`
  — D-18 (`/render` rebuilds cfg fresh per call — Phase 05 swap to
  `load_region(project.region_key)` preserves this); D-01 cache
  topology (`_STAGE_CACHE` keyed by project_id) is unaffected — Phase
  05 only changes the *source* of the cfg, not the *lifetime*
- `tests/parity/test_iberia_868.py` — survives Phase 05 in some form;
  D-14's `test_iberia_868_yaml.py` is the new canonical parity test

### Determinism + Reconquista contract
- `inicio/map_generator.py` — gold reference; the migration script
  must produce a YAML that, when loaded, gives an identical RegionConfig
  to `iberia_config()` (verified via D-14 parity test)
- `inicio/territory_data_v3.py` — original Iberia 868 territory data
  (read-only reference; KINGDOMS/DUCHIES/CONDADOS in
  `territory_data.py` was ported from here in Phase 01)
- `D:\Projetos_Jogo\Reconquista\Assets\StreamingAssets\Maps\*` — Iberia
  parity gold standard (France/England NOT compared against this)

### v1-archive lessons (caveats)
- `.planning/v1-archive/STATE.md` — `Konva.clearCache()` discipline
  carries (frontend modal close → form reset); deterministic seed rule
  (rng_seed=42) carries — France toy generator uses it
- `inicio/licoes/JORNADA_CRIACAO_MAPA.md` — historical rationale for
  σ ∈ [3.0, 4.5] (drives D-02 pydantic schema constraint) and KD-tree
  per country (drives D-04: empty border_polygon = single tree is OK
  for single-country regions like France/England toy)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`_INPUTS_DIR` anchor pattern** in `regions.py:33-36` — `Path(__file__).resolve().parents[4]
  / "data" / "regions" / "iberia_868" / "inputs"`. Migrates into
  `region_loader.py` as the default `regions_dir` resolution; same
  anchor (`parents[4]` from `services/pipeline/region_loader.py`).
- **`RegionConfig` + `ProjectDataset` dataclasses** in `contracts.py`
  — schema-side is what pydantic mirrors. Field defaults already match
  what the YAML should encode (e.g., `island_min_px=300`).
- **Alembic migrations** — existing migration infrastructure in
  `backend/medieval_forge/migrations/` (assume present; planner
  verifies). Phase 05 adds one new revision.
- **FastAPI `api/v3/*` modules** — pattern: thin module file, single
  `router = APIRouter(prefix=...)`, registered in `main.py`.
  `regions.py` follows this pattern.
- **TanStack Query in frontend** — `useRegions` hook follows the
  `useArtifacts`/`useStatus` pattern from Phase 03/04.
- **Radix `Select.Root` + `Dialog.Root`** — already used in Phase 03/04
  components.
- **`scripts/` directory** — convention for one-shot tooling (planner
  verifies; if missing, this phase creates it).
- **scipy.spatial.Voronoi + shapely** — already in backend deps
  (`pipeline/voronoi.py` uses them); reused by `gen_toy_france.py`.

### Established Patterns

- **`services/pipeline/` submodule layout** — `region_loader.py` is
  a sibling of `regions.py` until `regions.py` is deleted.
- **pytest markers**: Phase 05 adds `tests/unit/test_region_loader.py`
  (unit) + `tests/parity/test_iberia_868_yaml.py` (parity) + extends
  the France SC-3 test in `tests/uat/` or `tests/e2e/`.
- **Atomic commits per task**: `feat(05-NN): ...` / `chore(05-NN): ...`
  / `test(05-NN): ...`.
- **Vitest in `__tests__/` co-located** with components — Phase 05's
  `NewProjectModal.tsx` + tests live together.
- **Playwright UAT**: one new scenario (create France 1066 project,
  trigger generate, await export, assert 12 files exist with correct
  names + non-zero sizes).
- **Pydantic v2** — `BaseModel`, `Field(ge=..., le=...)`, `model_validate`,
  `model_dump`. Already used elsewhere in backend.

### Integration Points

- **Backend new files** (likely):
  - `services/pipeline/region_loader.py` (loader + schema + cache)
  - `api/v3/regions.py` (GET endpoint)
  - `migrations/versions/<rev>_add_project_region_key.py` (Alembic)
  - `scripts/migrate_iberia_to_yaml.py` (one-shot)
  - `scripts/gen_toy_france.py` (one-shot)
  - `data/regions/iberia_868.yaml` (migrated)
  - `data/regions/france_1066.yaml` (new)
  - `data/regions/france_1066/inputs/france_municipalities_toy.geojson` (new)
  - `data/regions/france_1066/inputs/mountain_river_data.json` (stub)
  - `data/regions/england_1216.yaml` (new)
- **Backend deletions** (after migration confirmed green):
  - `services/pipeline/regions.py`
  - `backend/medieval_forge/data/regions/iberia_868/territory_data.py`
- **Backend modifications**:
  - `models.py` (add `region_key` field)
  - `api/v3/generate.py:39,130`
  - `api/v3/render.py:42,128,198`
  - `main.py` (register `regions.router`)
  - `api/projects.py` (POST accepts `region_key`)
- **Frontend new files** (likely):
  - `components/projects/NewProjectModal.tsx` (or similar)
  - `api/useRegions.ts`
  - `__tests__/NewProjectModal.test.tsx`
- **Frontend modifications**:
  - Project list / dashboard page (entry point for the modal)
  - Type definitions for `RegionInfo` + `Project.region_key`
- **Test additions**:
  - `tests/unit/test_region_loader.py` (schema validation, cache,
    missing-file, autogen-when-empty)
  - `tests/parity/test_iberia_868_yaml.py` (the hard gate)
  - `tests/uat/` or `tests/e2e/` (France 1066 SC-3 end-to-end)

</code_context>

<specifics>
## Specific Ideas

- **"`iberia_868.yaml` externalizes the config currently in code"** —
  ROADMAP SC-1 is the literal Iberia migration; D-01/D-13 carry it.
  Single-file YAML keeps templates as easy to copy as a single file.
- **"France 1066 with toy synthetic dataset → ingest → generate →
  export produces 12 well-formed files (parity to Reconquista NOT
  required; file contract IS)"** — ROADMAP SC-3 spells the gate. D-09
  (Voronoi-from-grid) + D-11 (committed inputs) + D-17 step 10 (the
  end-to-end test) cover it.
- **"Historical research deferred to v3.1"** — PROJECT.md Out of Scope.
  D-03 autogen + D-12 England YAML-only honor this — geometry only.
- **"D-V3-04: delete obsolete v1 code rather than namespace it"** —
  drives D-13 hard-delete of `iberia_config()` + `REGIONS` +
  `territory_data.py`. No backward-compat wrapper.
- **"Parity stays green during the swap"** — D-17 plan sequencing
  enforces this. The YAML parity test (D-14) lands BEFORE the legacy
  `iberia_config()` deletion (D-13). Karpathy: structure → migrate →
  delete, never delete first.
- **"User-referenced docs during discussion"** — `CLAUDE.md` rule #2
  (σ range), rule #3 (KD-trees per country), rule #6 (independent 2×
  masks); `ROADMAP.md` Phase 05 SC list. No additional docs cited
  beyond what's already in the canonical_refs list.

</specifics>

<deferred>
## Deferred Ideas

- **Historical research for France/England** — names, kingdom_owners,
  historical_notes. PROJECT.md "Out of Scope" → v3.1. Phase 05 ships
  empty arrays + autogen condados.
- **England 1216 toy dataset** — only YAML this phase. v3.1 adds
  inputs/ for England.
- **Multi-country routing schema** — generalizing PT/ES border KD-tree
  routing for arbitrary country boundaries. Phase 05 keeps it
  Iberia-specific; new regions use single global KD-tree (empty
  `border_polygon`).
- **User-uploaded region YAMLs at runtime** — `POST /api/v3/regions`
  to upload custom YAML. Out of scope; v3.1+ if a Game Designer asks.
- **DEM raster ingestion** — `ProjectDataset.dem_raster` slot already
  reserved (Phase 01 D-13); Phase 05 does not consume it.
- **Bounds auto-detect from dataset** — D-08 picks explicit YAML
  bounds. Auto-detect later if templating gets repetitive.
- **`POST /api/v3/regions/validate`** — a dry-run endpoint that loads
  a YAML and reports schema errors without creating a project. Useful
  for region authors; not needed Phase 05.
- **Region YAML hot-reload in dev** — file-watcher invalidates the
  loader cache automatically. D-15's mtime check approximates this;
  full file watcher is overkill for single-user local.
- **Internationalized region display_name** — `GET /api/v3/regions`
  returns a single string; PT-BR vs EN-US localization not in scope.
  PROJECT.md "PT-BR only" applies.
- **France toy dataset richness** — climate biomes, elevation, river
  networks beyond the empty stub. v3.1.
- **Compound validation: cross-field constraints** — pydantic schema
  could enforce, e.g., `kingdom_colors` keys match `kingdoms[*].id`.
  Phase 05 keeps validation field-local; cross-field can land in v3.1.
- **Region versioning / migration when YAML schema evolves** —
  schema_version field, migration scripts. Not needed Phase 05; one
  schema version.

### Reviewed Todos (not folded)

None — `gsd-tools todo match-phase 05` returned `todo_count=0` at
gathering time.

</deferred>

---

*Phase: 05-region-generalization*
*Context gathered: 2026-05-11*
