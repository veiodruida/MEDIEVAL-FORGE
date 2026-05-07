# Phase 01: Pipeline parity (port + harness together) - Context

**Gathered:** 2026-05-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Port `inicio/map_generator.py` (620 lines, gold-standard reference) into
`backend/medieval_forge/services/pipeline/` as a deterministic, parametrized
library AND build the parity test harness comparing against
`D:\Projetos_Jogo\Reconquista\Assets\StreamingAssets\Maps\` for Iberia 868.

Both deliverables ship together so the algorithm and its parity gate evolve
in lockstep — never one without the other. CI flips the parity job to
non-skippable as the closing act.

Out of scope for Phase 01:
- Live ingestion (Phase 02 — wraps existing v1 ingest_* services in adapters)
- UI redesign (Phase 03 — single-canvas read-only workspace)
- Parameter studio + sliders (Phase 04 — incremental DAG re-render)
- Region YAML / multi-region templates (Phase 05)
- Strict 12-file schema validation gate (Phase 06)
- LLM research (Phase 07 — opt-in sidecar)

</domain>

<decisions>
## Implementation Decisions

### Port strategy

- **D-01 (Port mode):** Verbatim 1:1 first, refactor later. Each section of
  `inicio/map_generator.py` becomes a submodule with the same function names,
  signatures, and bodies (only imports + dataclass field names may change).
  Line-by-line audit must remain possible. Refactor only after the parity
  test goes green. Rationale: Phase 01's whole point is parity; refactor +
  port at once makes failure attribution impossible.

- **D-02 (Stage/version_token DAG):** Defer to Phase 04. Phase 01 keeps the
  pipeline as plain functions returning numpy arrays. Phase 04 wraps them in
  Stage objects with `version_token` and cache hooks when sliders need
  incremental re-render. Karpathy: don't build infra for hypothetical use.

- **D-03 (Orchestrator location):** `pipeline/__init__.py` exports
  `run_pipeline(cfg: RegionConfig) -> None` as the single library entry
  point. Submodules (`landmask.py`, `border.py`, `voronoi.py`, `cleanup.py`,
  `render.py`, `lookup.py`, `export.py`, `contracts.py`) are implementation
  detail. `pipeline/__main__.py` provides the CLI surface for
  `python -m medieval_forge.services.pipeline ...`.

- **D-04 (CLI region resolution):** Hard-coded registry
  `pipeline/regions.py: REGIONS = {"iberia_868": iberia_config}` (factory
  callables, not pre-built configs). Phase 05 swaps this for YAML loading.
  Phase 01 ships only `iberia_868` and parity needs the exact config from
  `inicio/iberia_config()`.

### V1 code disposition

- **D-05 (v1 generator stack):** Clean delete in Phase 01 (per D-V3-04).
  Removed in this phase:
  - `backend/medieval_forge/lib/map_generator.py` (vendored v1 copy)
  - `backend/medieval_forge/services/generator.py` (uses banned
    `sys.modules` patching + `importlib.reload` workaround)
  - `backend/medieval_forge/api/generate.py` (the only consumer of the above)
  - any v1 stepper-adjacent backend file reachable from those three by
    import graph (e.g. `services/voronoi.py`, `services/baronies_builder.py`,
    `services/baronies_geojson.py`, `services/render_modern.py`,
    `services/territory_builder.py`, `services/territories_geojson.py` —
    final list traced during planning)
  - Tests for deleted code: `test_generator_e2e.py`,
    `test_baronies_geojson.py`, `test_voronoi.py`,
    `test_territory_iberia_parity.py`, `test_territory_builder*.py`,
    `test_terrain.py`, plus any API test of `/api/generate`

- **D-06 (deletion scope):** Surgical, import-graph-driven. Follow imports
  backwards from `services/generator.py` and `api/generate.py`. Files only
  reachable from those two get deleted. Files used by survivors (ingest_*,
  llm/, research_*, models, db, paths.py if used by ingest) stay. Planning
  task #1 of Phase 01 is to produce the exact deletion list.

- **D-07 (test cleanup):** Delete the test files alongside their production
  code. Do not skip-mark; do not archive. The new
  `tests/parity/test_iberia_868.py` is the replacement and lives at a
  different path under a new pytest marker (`@pytest.mark.parity`).

- **D-08 (frontend stance):** Leave the v1 stepper frontend untouched in
  Phase 01. After `/api/generate` is deleted, `ProjectDetail.tsx` and
  friends will throw 404s — accepted because Phase 03 owns the frontend
  rewrite per `V1_DELETION_CANDIDATES.md`. Server still boots; root route
  still returns 200; UI is non-functional but contained.

### Parity fixtures

- **D-09 (Source of truth):** Reconquista's deployed files at
  `D:\Projetos_Jogo\Reconquista\Assets\StreamingAssets\Maps\` are the
  parity gold standard — they are what Unity actually reads in the shipping
  game. `inicio/map_generator.py` is the *algorithm reference*; the deployed
  files are the *contract*. If they ever diverge, deployed wins.

- **D-10 (Fixture location):** Commit a frozen snapshot into
  `tests/fixtures/iberia_868/golden/` (~3-10 MB total: 7 PNGs + 5 JSONs).
  CI on any runner reads them with no setup. Updating the baseline is an
  explicit `docs(parity): refresh iberia_868 baseline` commit, visible in
  PR review.

- **D-11 (Inputs location):** Commit pipeline inputs alongside fixtures
  under `data/regions/iberia_868/inputs/`:
  - `pt_concelhos_wgs84.geojson`
  - `es-atlas-pkg/...municipalities.json` (TopoJSON)
  - `mountain_river_data.json`

  `iberia_config()` points at these in-repo paths, replacing inicio's
  `../Assets/StreamingAssets/Maps/` references. Repo becomes self-contained:
  clone → install → `pytest tests/parity/`.

- **D-12 (Comparison rules):** Exactly the success criterion from
  ROADMAP.md, no extras:
  - **Lookup PNGs** (`lookup_barony.png`, `lookup_condado.png`,
    `terrain_lookup.png`): `numpy.array_equal` — any byte diff = fail
  - **Visual PNGs + masks** (`visual_condado.png`, `visual_barony.png`,
    `mountains_mask.png`, `rivers_overlay.png`):
    `skimage.metrics.structural_similarity ≥ 0.98`
  - **JSONs** (`lookup_*_colors.json`, `terrain_types.json`,
    `territory_metadata.json`, `mountain_river_data.json`):
    `json.loads(actual) == json.loads(expected)` after recursive key-sort

  Per-file tolerance YAML (Phase 06+ shape) is deferred — keep the assertion
  hardcoded in `tests/parity/test_iberia_868.py` for now.

### Territory data loading

- **D-13 (Loader):** Static Python import from in-repo module — no
  `importlib.reload`, no `sys.modules` patching. Move
  `inicio/territory_data_v3.py` to
  `backend/medieval_forge/data/regions/iberia_868/territory_data.py` (path
  to confirm during planning). `iberia_config()` does
  `from ...data.regions.iberia_868.territory_data import KINGDOMS, DUCHIES, CONDADOS`
  and returns a `RegionConfig` carrying them. Phase 05 converts to YAML when
  other regions ship.

- **D-14 (Storage on RegionConfig):** Territory data lives directly on
  RegionConfig as fields: `cfg.kingdoms`, `cfg.duchies`, `cfg.condados`.
  Pipeline stages take a single argument (`cfg`); no separate
  `setup_baronies(condados, duchies, kingdoms, cfg)` shape. Reinforces
  D-V3-05 (RegionConfig is the only mutable input). Phase 04 sliders mutate
  cfg fields in-place / via shallow copy.

### Claude's Discretion

- RegionConfig as `@dataclass` (mirror inicio) vs pydantic `BaseModel` —
  Claude picks during planning. pydantic gives validation + JSON serialize
  for free (Phase 04 sliders), dataclass minimizes drift from inicio.
- Exact submodule split inside `cleanup.py` (median + fragment + smooth +
  merge are 4 sub-stages in one section of inicio) — keep all four in
  cleanup.py or split.
- Where the territory-data path lives precisely
  (`backend/medieval_forge/data/regions/iberia_868/territory_data.py` vs
  `data/regions/iberia_868/territory_data.py` at repo root) — planning
  task to resolve.
- conftest.py fixture wiring (session-scoped vs function-scoped, tmp_path
  layout for output diff inspection on failure).
- Whether `tests/parity/test_iberia_868.py` runs the full pipeline once and
  asserts 12 files in one test, or splits into 12 narrow tests with shared
  pipeline output via session fixture (preference: shared session fixture).
- CI parity-gate flip mechanics — when in the phase the
  `pytest-parity` job becomes non-skippable (likely the final commit so
  earlier parity-failing commits in the phase don't block themselves).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Pipeline algorithm (gold standard)
- `inicio/map_generator.py` — 620-line reference, all 13 sections; the port
  must mirror function names + signatures verbatim per D-01
- `inicio/territory_data_v3.py` — KINGDOMS/DUCHIES/CONDADOS source; moved
  into the package per D-13
- `inicio/licoes/JORNADA_CRIACAO_MAPA.md` — every algorithm decision and bug
  documented during the 25-iteration build; consult when port behavior is
  ambiguous
- `inicio/licoes/MAPA_V3_PIXEL_LOOKUP_BRIEFING.md` — pixel-lookup contract
  for Unity (color → ID mapping)

### Parity gold standard (ground truth)
- `D:\Projetos_Jogo\Reconquista\Assets\StreamingAssets\Maps\` — Reconquista's
  deployed 12-file output; snapshot copied into
  `tests/fixtures/iberia_868/golden/` per D-09 + D-10

### Project contract & non-negotiables
- `CLAUDE.md` §"v3 Pipeline Contract" — 12-file output table + 7
  non-negotiable rules (NEAREST upscale, σ ∈ [3.0, 4.5], KD-trees per
  country, original_idx, sentinels, 2x mask independence, byOriginalIdx)
- `CLAUDE.md` §"Conventions" — locks the 9-submodule layout under
  `pipeline/` and the "RegionConfig is the only mutable input" rule
- `CLAUDE.md` §"What v3 explicitly is NOT" — rejected designs (no LLM
  mandatory, no stepper, no `sys.modules` patching, no upscale interpolation,
  no global Voronoi, no hand-rolled compound undo)
- `.planning/PROJECT.md` — D-V3-01 through D-V3-07 decisions table
- `.planning/ROADMAP.md` §"Phase 01" — success criteria 1-3 are the
  acceptance gate

### V1 cleanup map
- `.planning/quick/260507-g1v-phase-00-v3-archive-milestone-reset/V1_DELETION_CANDIDATES.md`
  — confirmed-vs-possible-vs-keep table; Phase 01 implements the
  generator-stack deletes per D-05/D-06
- `.planning/v1-archive/STATE.md` — 30+ pitfalls discovered during v1.0
  (per `.planning/STATE.md` blocker note); re-read before planning to avoid
  re-learning

### CI gate
- `.github/workflows/ci.yml` — `pytest-parity` job already scaffolded in
  Phase 00; Phase 01 flips it to non-skippable

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets
- **`inicio/map_generator.py`** — gold-standard algorithm. Source for the
  port; do not modify during Phase 01 even if a bug is suspected. Bug fixes
  go through a separate quick task that updates inicio first, then refreshes
  the parity baseline.
- **`inicio/territory_data_v3.py`** — moved into the package per D-13;
  contents unchanged.
- **`backend/medieval_forge/cli.py`** — existing `medieval-forge start` CLI
  stays untouched; `python -m medieval_forge.services.pipeline` is a
  separate sub-tool.
- **`backend/medieval_forge/services/paths.py`** — currently used by both
  v1 generator and ingest. Survives Phase 01 *iff* ingest still uses it
  after the import-graph trace; otherwise dies.
- **`backend/medieval_forge/main.py`** — FastAPI app loader; must stay
  importable after `api/generate` is deleted (registration line gets
  removed in the same commit as the file delete).
- **`backend/medieval_forge/{database,models,schemas}.py`** — project CRUD
  foundation; survives.
- **`pyproject.toml` `[tool.pytest.ini_options]`** — `parity` marker
  already registered in Phase 00. New `tests/parity/test_iberia_868.py`
  uses `@pytest.mark.parity`.

### Established patterns
- **CI 4-job split** (`pytest-unit`, `pytest-parity`, `vitest`,
  `playwright-uat`) lives in `.github/workflows/ci.yml`. Parity job already
  reads `pytest -m parity`; Phase 01's contribution is making the test
  exist + non-skippable.
- **Atomic commits per task** — convention from Phase 00 quick task is
  `type(scope): subject`. Phase 01 uses `feat(01): ...` / `chore(01): ...`
  / `test(01): ...` per task.
- **Pydantic models** are used for project CRUD schemas (`schemas.py`).
  RegionConfig may follow that pattern (Claude's discretion).

### Integration points
- `medieval_forge.services.pipeline` is a *new* sub-package; nothing
  outside it imports from it during Phase 01. Phase 02 wires its
  `contracts.ProjectDataset` consumer; Phase 03 imports `run_pipeline` from
  the canvas hydration path.
- `medieval_forge.main` keeps booting HTTP 200 on `/` (Phase 00 success
  criterion 6 must remain green).
- CI's `pytest-parity` job becomes the gate: any PR that breaks parity
  (intentional or not) blocks merge; intentional baseline updates ship as
  a separate `docs(parity): refresh iberia_868 baseline` commit.

</code_context>

<specifics>
## Specific Ideas

- "The port should be auditable line-by-line against `inicio/map_generator.py`"
  — verbatim translation is the explicit ask; refactor is a Phase 04+ concern.
- "Reconquista's deployed files are what Unity actually reads — those are
  the contract" — gold standard chosen with eyes open: if `inicio` ever
  drifts from deployed, deployed wins.
- "Repo should be self-contained for parity" — inputs + golden outputs both
  in-tree under `data/regions/iberia_868/{inputs,...}` and
  `tests/fixtures/iberia_868/golden/`; no absolute paths, no LFS.
- "Karpathy: don't build for hypothetical use" — Stage/version_token DAG
  deferred to Phase 04 even though Phase 04 is the next planning iteration.

</specifics>

<deferred>
## Deferred Ideas

- **Stage abstraction with `version_token` + in-memory stage cache** —
  Phase 04 builds it as part of the parameter studio. Phase 01 keeps
  pipeline as plain functions.
- **Region YAML loader + Pydantic territory schemas** — Phase 05
  generalization; Phase 01 ships hard-coded `REGIONS["iberia_868"]`.
- **Per-file tolerance YAML for parity** (`tests/parity/tolerances.yaml`)
  — Phase 06 export-validation gate; Phase 01 hardcodes the comparison
  rules from D-12.
- **Frontend stepper UI cleanup** (ProjectDetail.tsx, Stepper, StepCard,
  usePipelineStore) — Phase 03 owns the frontend rewrite; Phase 01 leaves
  them untouched even though they 404 after `/api/generate` deletes.
- **Mid-port refactor of cleanup.py sub-stages** (median + fragment +
  smooth + merge) — Phase 01 keeps them in one file mirroring inicio's
  Section 7; further split is Claude's discretion later.
- **Migrating RegionConfig from `@dataclass` to pydantic `BaseModel`** —
  Claude's discretion during planning; pydantic gives validation + JSON
  serialize for Phase 04 sliders, dataclass minimizes drift from inicio.
- **CI parity baseline-refresh tooling** (e.g.
  `scripts/refresh_parity_baseline.py`) — nice-to-have; Phase 01 ships a
  manual rsync command in the README, scripted refresh deferred.
- **inicio sync watchdog** — automated check that `inicio/map_generator.py`
  and `pipeline/` stay in lockstep. Manual diff for Phase 01; could become
  a Phase 06 lint job.

</deferred>

---

*Phase: 01-pipeline-parity-port-harness-together*
*Context gathered: 2026-05-07*
