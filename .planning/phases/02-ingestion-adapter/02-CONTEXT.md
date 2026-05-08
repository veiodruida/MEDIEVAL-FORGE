# Phase 02: Ingestion adapter - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Wrap the existing v1 ingestion services (`ingest_osm`, `overpass_client`,
`ingest_terrain`) in adapters that emit a `ProjectDataset` consumed unchanged
by the Phase 01 pipeline. Define `ProjectDataset` in
`services/pipeline/contracts.py`. Prove `tests/parity/test_iberia_868.py`
stays green when the input is "live ingestion" instead of the vendored
fixture snapshot — without introducing network calls in CI.

Out of scope for Phase 02:
- DEM / HydroSHEDS / ridges → mountain_river_data.json automation
  (stub passthrough only; full wire-up deferred — Phase 06 or v3.1)
- Wikidata as a v3-supported source (legacy v1 path stays intact for the
  v1 SSE endpoint; deletion deferred to Phase 03 with the stepper)
- Region YAML loader (Phase 05)
- New CLI `medieval-forge ingest` (Phase 03 once UI invokes it)
- Frontend wiring of the new `/api/v3/projects/{id}/ingest` endpoint
  (Phase 03 single-canvas workspace)
- Schema validation gate on dataset (Phase 06)

</domain>

<decisions>
## Implementation Decisions

### ProjectDataset contract

- **D-01 (cfg integration):** `ProjectDataset` replaces the three path
  fields (`municipality_pt_geojson`, `municipality_es_topojson`,
  `mountain_river_json`) on `RegionConfig`. The dataset hangs off cfg as
  `cfg.dataset: ProjectDataset`. Reinforces D-V3-05 — `cfg` remains the
  single mutable input. Phase 01's `iberia_config()` factory builds a
  vendored-pointing `ProjectDataset` so the parity test path is unchanged
  semantically (the three legacy fields die, the data they pointed to
  lives on `cfg.dataset` instead).

- **D-02 (in-memory vs paths):** `ProjectDataset` carries `Path` objects
  (not parsed FeatureCollections). The pipeline opens/parses internally,
  preserving inicio's behavior. Adapters write to disk; pipeline reads
  from disk. Determinism + debuggability win over the marginal Phase 04
  re-render cost (revisit when sliders prove the I/O actually matters).

- **D-03 (type):** `ProjectDataset` is a stdlib `@dataclass`, mirroring
  `RegionConfig` (Phase 01 D-01). Pydantic validation is deferred to the
  Phase 06 export gate; phase 02 keeps drift from inicio at zero.

- **D-04 (required vs optional fields):** Required: `pt_geojson: Path`,
  `es_input: Path`, `mountain_river_json: Path`. Optional: `dem_raster:
  Path | None = None` (slot reserved; not consumed by inicio yet).
  Pipeline asserts the three required paths exist at the top of
  `landmask.py`; missing → fail fast with a structured error.

### Format reconciliation

- **D-05 (adapter output shape):** Adapters emit the **three vendored-shape
  files** (`pt_concelhos_wgs84.geojson`, `es_municipalities.geojson`,
  `mountain_river_data.json`). Live OSM `municipalities.geojson` is split
  by ISO using the existing `clip_iso_codes` mechanism in
  `services/ingest_osm.py` + `services/country_boundaries.py`. Adapters
  wrap (do not rewrite) the existing fetchers per ROADMAP success #3.

- **D-06 (ES live format):** Live ES is emitted as **GeoJSON, not
  TopoJSON** — v1 OSM never produces TopoJSON and the conversion would
  require a new dependency. `landmask.py` loader gains a GeoJSON branch
  (detect by extension or peek at top-level keys); the existing TopoJSON
  branch stays for Phase 01 vendored-fixture parity. Both branches feed
  the same downstream KD-tree builder.

- **D-07 (output dir):** Adapters write to
  `projects/<uuid>/inputs/{pt_concelhos.geojson, es_municipalities.geojson,
  mountain_river_data.json}` — same per-project pattern as v1 (already
  scaffolded in `services/paths.py` via `project_dir` +
  `ensure_project_dirs`). `cfg.dataset` points at these three paths.

- **D-08 (vendored fallback):** The vendored `es-atlas-pkg/` TopoJSON
  (npm `es-atlas@0.6.0`, shasum `4c926d9cba`, Phase 01 D-11) is **kept as
  fallback**. `iberia_config()` factory still returns a `ProjectDataset`
  pointing at the vendored files for the Phase 01 parity test. Adapters
  add a NEW path (live → projects/<uuid>/inputs/); they do not delete or
  override the existing vendored path. Two paths coexist.

### Live-ingestion parity strategy

- **D-09 (replay strategy):** Snapshot-and-replay, **no network in CI**.
  Adapter is invoked once locally against real OSM/Overpass; output
  GeoJSON files are committed under
  `tests/fixtures/iberia_868/live-ingestion/`. CI test substitutes the
  adapter's HTTP layer (or, simpler, reads directly from the snapshot
  files). Refresh is an explicit
  `docs(parity): refresh live snapshot` commit, visible in PR review —
  matches the D-10 baseline-refresh ritual from Phase 01.

- **D-10 (snapshot location):** `tests/fixtures/iberia_868/live-ingestion/`
  (co-located with `golden/`). Files mirror adapter output:
  `pt_concelhos_live.geojson`, `es_municipalities_live.geojson`,
  optionally `mountain_river_data_live.json` (or symlink to vendored
  per D-13). Refresh via `scripts/refresh_live_snapshot.py` (manual).

- **D-11 (test separation):** New `tests/parity/test_iberia_868_live.py`
  alongside the existing `tests/parity/test_iberia_868.py`. Both gated
  by `@pytest.mark.parity`, both non-skippable. The fixture-path test
  is unchanged (D-09/D-10/D-11 from Phase 01 immutable). The live-path
  test builds the dataset via the adapter (reading the snapshot), runs
  the pipeline, and asserts vs the **same** `golden/` outputs. Two
  tests, two input paths, one expected output → if the live snapshot
  diverges from vendored, the live test fails and the snapshot must be
  refreshed.

- **D-12 (snapshot level):** Snapshot is **post-adapter GeoJSON**, not
  raw OSM Overpass JSON. The adapter logic (split-by-ISO, clipping,
  field normalization) is exercised by a separate adapter unit test
  using a tiny synthetic Overpass response. Keeping the parity snapshot
  at GeoJSON-level isolates pipeline determinism from OSM payload
  format drift.

### Scope (terrain / endpoint / Wikidata / CLI)

- **D-13 (terrain — stub passthrough):** `terrain_adapter.build_terrain()`
  returns a `Path` to the vendored `mountain_river_data.json` as-is.
  Phase 02 reserves the dataset slot but does not compute it from
  DEM/HydroSHEDS/ridges. The full wire-up (DEM heightmap →
  mountain_threshold pixels, HydroSHEDS → river polylines) is deferred
  to Phase 06 or v3.1. The 851-line existing `services/ingest_terrain/`
  package stays untouched in Phase 02 — the legacy v1 SSE endpoint that
  drives it remains live until Phase 03.

- **D-14 (new HTTP endpoint):** New `/api/v3/projects/{id}/ingest`
  endpoint mounted under a v3 router. It invokes the adapters → writes
  to `projects/<uuid>/inputs/` → streams progress via SSE (mirroring the
  existing `_sse_generator` pattern in `api/ingest.py`). The legacy
  `/api/projects/{id}/ingest` endpoint stays alive — the v1 stepper
  still uses it. Both coexist until Phase 03 deletes the stepper +
  the v1 endpoint together.

- **D-15 (Wikidata — drop wrapper):** No Phase 02 adapter wraps
  `ingest_wikidata.py`. The OSM-only path is the v3 contract.
  `ingest_wikidata.py` itself stays in the repo, untouched, used by the
  legacy v1 SSE endpoint. Phase 03 deletes both together
  (per D-V3-04 — dead code is regression risk). The Wikidata
  points-only fallback that produces all-blue maps is explicitly NOT a
  v3 capability.

- **D-16 (no new CLI):** Phase 02 ships adapters as a Python library
  only (`from medieval_forge.services.pipeline.adapters import
  build_dataset_from_osm`). No `medieval-forge ingest` subcommand, no
  `python -m ...adapters` shim. The live-parity test imports the
  adapter functions directly. CLI ergonomics for Game Designers come
  in Phase 03 (UI button) and are not the v3 critical path.

### Claude's Discretion

- Exact `pipeline/adapters/` subpackage layout: `osm.py` + `terrain.py`
  + `base.py` (with shared types) vs flat module — picked during
  planning based on file-size pressure. CLAUDE.md `Conventions` already
  specifies `adapters/` exists, but not its internal split.
- Snapshot file naming + fingerprint convention (e.g., embed bbox or
  date in filename, sidecar `.fingerprint` with sha256). Decide during
  Plan 01 fixture wiring.
- How `landmask.py` detects ES GeoJSON vs TopoJSON (extension sniffing
  vs peek-at-top-level-key vs explicit `cfg.dataset.es_format` enum).
  Pick the option that minimizes branching in the loader.
- Adapter unit test fixture size + format (in-line synthetic Overpass
  JSON vs tiny captured snippet under `tests/fixtures/adapters/`).
- Exact SSE event payload schema for the `/api/v3/.../ingest` endpoint
  (mirror v1 messages or define a stricter v3 envelope). Payload shape
  is invisible to Phase 01 parity gate; Phase 03 will revisit when the
  canvas consumes the stream.
- Whether `iberia_config()` builds the vendored `ProjectDataset` inline
  or delegates to a `vendored_dataset()` helper next to the adapters.
- Whether `pt_geojson` accepts `.geojson` only or also `.json` (npm
  pkg uses `.json` for ES TopoJSON). Suggest extension-agnostic.

### Folded Todos

None — `gsd-tools todo match-phase 2` returned `todo_count=0`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract & success criteria
- `.planning/ROADMAP.md` §"Phase 02: Ingestion adapter" — three success
  criteria are the acceptance gate; #3 ("wrap, don't rewrite") is a
  hard constraint
- `.planning/REQUIREMENTS.md` (if/when written — currently absent;
  ROADMAP success criteria are the requirement source)
- `.planning/PROJECT.md` §"Key Decisions" — D-V3-04 (delete v1 dead
  code), D-V3-05 (RegionConfig is the only mutable input), D-V3-07
  (LLM opt-in only — adapters never call LLMs)
- `CLAUDE.md` §"v3 Pipeline Contract" — 12-file output table; the seven
  non-negotiable rules still apply (adapters MUST NOT introduce a
  global Voronoi or violate per-country KD-trees)
- `CLAUDE.md` §"Conventions" — `services/pipeline/adapters/` is the
  declared home for ingestion translation
- `CLAUDE.md` §"Architecture" — Phase 02 wires the live path of
  `services/pipeline/contracts.py: ProjectDataset`

### Pipeline contract (consumer of ProjectDataset)
- `backend/medieval_forge/services/pipeline/contracts.py` —
  `RegionConfig` definition; Phase 02 adds `ProjectDataset` and removes
  `municipality_pt_geojson` / `municipality_es_topojson` /
  `mountain_river_json` (replaced by `cfg.dataset`)
- `backend/medieval_forge/services/pipeline/regions.py` —
  `iberia_config()` factory; Phase 02 modifies it to build a vendored
  `ProjectDataset`
- `backend/medieval_forge/services/pipeline/landmask.py` — current
  consumer of the three path fields; Phase 02 updates to read
  `cfg.dataset.*` and adds GeoJSON ES branch (D-06)
- `backend/medieval_forge/services/pipeline/__init__.py` — `run_pipeline`
  signature stays `run_pipeline(cfg)` (cfg.dataset is just an attribute)

### Existing v1 ingestion (to be wrapped — DO NOT rewrite)
- `backend/medieval_forge/services/ingest_osm.py` (344 lines) —
  Overpass admin_level=6 fetcher with bbox/ISO query strategies, retry,
  ISO clipping via `country_boundaries`. Adapter wraps `fetch_osm_*`
  functions
- `backend/medieval_forge/services/overpass_client.py` (104 lines) —
  3-endpoint retry shim used by `ingest_osm.py`. Wrapped transitively
- `backend/medieval_forge/services/ingest_terrain/runner.py` (301 lines) —
  DEM/HydroSHEDS/ridges orchestrator. Phase 02 stub-passthrough only
  (D-13). Module stays as-is
- `backend/medieval_forge/services/ingest_terrain/{dem,hydrosheds,
  overpass_terrain,ridges}.py` — terrain submodules; untouched in
  Phase 02
- `backend/medieval_forge/services/ingest_wikidata.py` (133 lines) —
  legacy v1 path; **NOT wrapped** by Phase 02 (D-15). Module stays for
  v1 SSE endpoint; Phase 03 deletes
- `backend/medieval_forge/services/ingest_runner.py` (137 lines) —
  legacy v1 SSE orchestrator (`run_ingest`). Reference for the v3 SSE
  pattern; v3 endpoint reuses `_write_geojson_atomic` + `paths.py`
- `backend/medieval_forge/services/country_boundaries.py` — Natural
  Earth Admin 0 ISO clipping; reused by adapter for split-by-ISO (D-05)
- `backend/medieval_forge/services/paths.py` — `project_dir`,
  `ensure_project_dirs`, `is_valid_uuid`. v3 endpoint uses these
- `backend/medieval_forge/services/countries.py` — `qid_to_iso`,
  `clip_iso_codes_for_qid`. Adapter calls `clip_iso_codes_for_qid` to
  split Iberia OSM by PT/ES

### HTTP API references
- `backend/medieval_forge/api/ingest.py` — current v1 SSE endpoint
  pattern (`_sse_generator` + `asyncio.Queue` + `StreamingResponse`).
  Template for the new `/api/v3/projects/{id}/ingest` (D-14)
- `backend/medieval_forge/main.py` — FastAPI app loader; Phase 02 adds
  the v3 router registration

### Phase 01 carry-forward
- `.planning/phases/01-pipeline-parity-port-harness-together/01-CONTEXT.md`
  — D-09 (deployed wins), D-10 (golden fixture in
  `tests/fixtures/iberia_868/golden/`), D-11 (vendored inputs at
  `data/regions/iberia_868/inputs/`), D-12 (parity comparison rules)
- `.planning/phases/01-pipeline-parity-port-harness-together/01-VERIFICATION.md`
  — Phase 01 acceptance state; Phase 02 must keep this green
- `tests/parity/test_iberia_868.py` — template for
  `tests/parity/test_iberia_868_live.py` (D-11 above is **about Phase 01
  fixture inputs**; the new live test is D-11 in this phase's decision
  list — disambiguate during planning)
- `tests/fixtures/iberia_868/golden/` — same `golden/` is asserted
  against by both fixture-path and live-path tests (D-12 of Phase 01
  comparison rules apply unchanged)

### v1-archive lessons
- `.planning/v1-archive/STATE.md` — 30+ pitfalls; ingest-relevant:
  Wikidata points-only produces all-blue maps (driver of D-15);
  per-country clipping is mandatory at adapter boundary (driver of D-05)
- `inicio/licoes/JORNADA_CRIACAO_MAPA.md` — algorithm-side rationale
  for PT/ES separation (driver of per-country adapters)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`ingest_osm.fetch_osm_municipalities`** — async, validates ISO,
  supports bbox + clip_iso_codes; the centerpiece adapter wraps. Returns
  a single GeoJSON FeatureCollection that needs splitting by ISO
  (`country_boundaries` + `clip_iso_codes_for_qid` already implement the
  split filter)
- **`overpass_client`** — 3-endpoint retry already abstracted from
  `ingest_osm`; adapter inherits retry behavior for free
- **`country_boundaries`** — Natural Earth Admin 0 polygons; the
  per-country split (PT vs ES) is one `unary_union` + spatial filter
- **`paths.py`** (`project_dir`, `ensure_project_dirs`, `is_valid_uuid`,
  `_write_geojson_atomic`) — v3 endpoint reuses verbatim
- **`api/ingest.py:_sse_generator`** — `asyncio.Queue` producer +
  `StreamingResponse` consumer pattern; v3 endpoint copies the shape
- **`models.Project` + `database.AsyncSessionLocal`** — project CRUD
  exists; v3 endpoint reuses for status updates
- **`countries.qid_to_iso` / `clip_iso_codes_for_qid`** — existing
  qid→ISO map; adapter uses `clip_iso_codes_for_qid` to derive PT+ES
  for Iberia from `project.country_qid`

### Established Patterns

- Per-project filesystem at `projects/<uuid>/raw/...` (v1) →
  Phase 02 adopts `projects/<uuid>/inputs/` for adapter outputs
  (D-07). `paths.ensure_project_dirs` already creates both
- SSE via `asyncio.Queue` + `StreamingResponse` with explicit `None`
  sentinel; T-01-04 mitigation (per-step stop_events) is in
  `ingest_terrain/runner.py` and worth replicating in v3 endpoint
- httpx async with retry + structured timeout (`_PAGE_TIMEOUT_S`,
  `_TIMEOUT_S`); adapter inherits
- UTF-8 encoding for GeoJSON I/O — Phase 01 already locked this
  (`feat(01)`: encoding='utf-8' fix in `landmask.py`)
- Atomic file write via `_write_geojson_atomic` (write + rename);
  required for crash-safe concurrent reads
- pytest markers: `unit`, `parity`, `integration`. New live test
  uses `@pytest.mark.parity` (gating) — not `@integration`
- Phase 01 baseline-refresh ritual: explicit
  `docs(parity): refresh iberia_868 baseline` commit. Phase 02
  mirrors with `docs(parity): refresh live snapshot`

### Integration Points

- `cfg.dataset: ProjectDataset` becomes the single port through which
  geometry data flows; `landmask.py` is the only consumer that touches
  the path fields today (audit during planning)
- New `/api/v3/projects/{id}/ingest` endpoint requires registering a
  router in `main.py`; the v1 router stays mounted
- Adapter unit tests live under `tests/unit/adapters/`; live-parity
  test under `tests/parity/test_iberia_868_live.py`
- `iberia_config()` becomes the boundary between vendored-fixture
  ProjectDataset (Phase 01 parity path) and live-adapter
  ProjectDataset (Phase 02 live path); both produce the same
  `golden/` outputs

</code_context>

<specifics>
## Specific Ideas

- **"Wrap, don't rewrite"** — ROADMAP success #3 is the explicit
  constraint. Adapters call existing `ingest_*` functions; they do
  not change those functions' bodies. Any change to existing ingest
  code is a separate quick task with its own justification.
- **"Deployed wins"** — Phase 01 D-09 carries forward: if the live
  adapter snapshot ever produces a pipeline output that differs from
  `tests/fixtures/iberia_868/golden/` (which mirrors deployed
  Reconquista assets), the **snapshot is wrong**, not the golden.
- **"No network in CI"** — D-09 is non-negotiable. Live OSM drift is
  not allowed to break PRs. Refresh is a deliberate, reviewed commit.
- **"Karpathy: stub the unused"** — terrain (D-13) and Wikidata
  (D-15) are not on the v3 critical path; Phase 02 does not build
  the wire-up. The slots exist (`dem_raster: Path | None`); the
  population is deferred until a real consumer needs them.
- **"Two paths, one output"** — fixture-path test and live-path
  test both assert against `golden/`. Divergence is a bug, not a
  feature; the dataset contract is the seam.

</specifics>

<deferred>
## Deferred Ideas

- **DEM → mountain_threshold + HydroSHEDS → rivers wire-up.**
  `ingest_terrain/{dem, hydrosheds, ridges}.py` already exist; full
  pipeline integration is Phase 06 (export-gate validates terrain
  bounds) or v3.1.
- **Region YAML loader (`data/regions/<region>/*.yaml`).** Phase 05
  generalizes Iberia → config; Phase 02 keeps `iberia_config()`
  hardcoded.
- **Per-region cache at `data/regions/<region>/cache/<bbox-hash>/`.**
  Phase 04 may need it for re-render perf; not required by Phase 02.
- **VCR cassettes (vcrpy/respx) for HTTP-level recording.**
  GeoJSON-level snapshot (D-12) is sufficient; cassette overlay is
  premature complexity.
- **`medieval-forge ingest ...` CLI subcommand.** Phase 03 introduces
  it when the canvas needs a one-click ingest button.
- **Wikidata wrapper as v3 fallback.** Explicitly dropped (D-15);
  not revisited.
- **Replacing the vendored `es-atlas-pkg/` TopoJSON with live-only.**
  Vendored fallback stays (D-08); npm pkg removal is its own decision
  (likely never).
- **TopoJSON conversion of live OSM ES output.** Adapter emits
  GeoJSON only (D-06). TopoJSON is vendored-only.
- **Pydantic validation of `ProjectDataset`.** Phase 06 export gate
  owns schema validation; Phase 02 keeps `@dataclass` (D-03).
- **Frontend wiring of `/api/v3/projects/{id}/ingest`.** Phase 03
  consumes; Phase 02 ships endpoint + dataset only.

### Reviewed Todos (not folded)

None — backlog had no matches for Phase 02 scope at gathering time.

</deferred>

---

*Phase: 02-ingestion-adapter*
*Context gathered: 2026-05-08*
