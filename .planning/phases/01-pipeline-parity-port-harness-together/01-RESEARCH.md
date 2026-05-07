# Phase 01: Pipeline parity (port + harness together) - Research

**Researched:** 2026-05-07
**Domain:** Verbatim port of `inicio/map_generator.py` to `backend/medieval_forge/services/pipeline/` with byte-equivalent parity vs. Reconquista deployed maps.
**Confidence:** HIGH (every load-bearing claim is anchored in either the inicio source code, the Reconquista filesystem, or CONTEXT.md decisions; nothing is assumed about external libraries or APIs because the port is verbatim).

## Summary

Phase 01 has two deliverables that ship together: (1) a verbatim 1:1 port of `inicio/map_generator.py` (944 lines, 13 sections) into 9 submodules under `backend/medieval_forge/services/pipeline/`, and (2) a parity test harness that compares the port's outputs against `D:\Projetos_Jogo\Reconquista\Assets\StreamingAssets\Maps\` for Iberia 868. The CI `pytest-parity` job, already scaffolded in Phase 00 with a placeholder, flips to non-skippable as the closing act of the phase.

The research surfaces three things the planner must internalise. First, the inicio source has 13 sections that map cleanly onto the 9 submodule layout from CONTEXT.md D-03 — there is one ambiguous case (`build_hierarchy_maps`, Section 8) that lives best in `voronoi.py` because it operates on the same per-pixel index arrays produced there. Second, the Reconquista golden fixtures total ~1.16 MB and can be committed direct (no LFS); the PT GeoJSON input is 29.7 MB which is the only size concern, and the ES TopoJSON input is npm-packaged data (`martgnz/es-atlas`) that is NOT in either repo today and must be sourced. Third, the v1 deletion graph is narrower than CONTEXT.md's tentative list: only `lib/map_generator.py`, `services/generator.py`, `api/generate.py`, and `services/render_modern.py` are confirmed-delete; `voronoi.py`, `territories_geojson.py`, `territory_builder.py`, `baronies_geojson.py` survive Phase 01 because `api/edit.py` (untouched per D-08) imports them.

**Primary recommendation:** Port verbatim per D-01, keeping `@dataclass` (not pydantic) for `RegionConfig` because (a) inicio uses `@dataclass`, drift is the enemy, and (b) Phase 04's slider needs are JSON-serializable mutability which `@dataclass` already supports via `dataclasses.asdict`. The CI flip to non-skippable lands as the LAST commit of the phase, after the parity test is observed green locally and after the gold fixtures are committed.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Port strategy**

- **D-01 (Port mode):** Verbatim 1:1 first, refactor later. Each section of `inicio/map_generator.py` becomes a submodule with the same function names, signatures, and bodies (only imports + dataclass field names may change). Line-by-line audit must remain possible. Refactor only after the parity test goes green.
- **D-02 (Stage/version_token DAG):** Defer to Phase 04. Phase 01 keeps the pipeline as plain functions returning numpy arrays.
- **D-03 (Orchestrator location):** `pipeline/__init__.py` exports `run_pipeline(cfg: RegionConfig) -> None`. Submodules: `landmask.py`, `border.py`, `voronoi.py`, `cleanup.py`, `render.py`, `lookup.py`, `export.py`, `contracts.py`. `pipeline/__main__.py` for `python -m medieval_forge.services.pipeline ...`.
- **D-04 (CLI region resolution):** Hard-coded `pipeline/regions.py: REGIONS = {"iberia_868": iberia_config}` (factory callables). Phase 05 swaps for YAML.

**V1 code disposition**

- **D-05 (v1 generator stack):** Clean delete in Phase 01 — `backend/medieval_forge/lib/map_generator.py`, `backend/medieval_forge/services/generator.py`, `backend/medieval_forge/api/generate.py`, plus any v1 stepper-adjacent backend file reachable from those three by import graph (final list traced during planning).
- **D-06 (deletion scope):** Surgical, import-graph-driven. Files only reachable from those two get deleted. Files used by survivors stay. Planning task #1 produces the exact deletion list.
- **D-07 (test cleanup):** Delete the test files alongside their production code. Do not skip-mark; do not archive. New `tests/parity/test_iberia_868.py` is the replacement, marker `@pytest.mark.parity`.
- **D-08 (frontend stance):** Leave the v1 stepper frontend untouched in Phase 01. After `/api/generate` is deleted, `ProjectDetail.tsx` and friends throw 404s — accepted because Phase 03 owns the frontend rewrite. Server still boots; root route still returns 200.

**Parity fixtures**

- **D-09 (Source of truth):** Reconquista's deployed files at `D:\Projetos_Jogo\Reconquista\Assets\StreamingAssets\Maps\` are the gold standard.
- **D-10 (Fixture location):** Commit a frozen snapshot into `tests/fixtures/iberia_868/golden/`. Updating baseline = explicit `docs(parity): refresh iberia_868 baseline` commit.
- **D-11 (Inputs location):** Commit pipeline inputs under `data/regions/iberia_868/inputs/` — `pt_concelhos_wgs84.geojson`, `es-atlas-pkg/...municipalities.json` (TopoJSON), `mountain_river_data.json`. `iberia_config()` points at in-repo paths.
- **D-12 (Comparison rules):** Lookup PNGs `numpy.array_equal`. Visual PNGs + masks `skimage.metrics.structural_similarity ≥ 0.98`. JSONs deep-equal after recursive key-sort. Per-file tolerance YAML deferred.

**Territory data loading**

- **D-13 (Loader):** Static Python import — no `importlib.reload`, no `sys.modules` patching. Move `inicio/territory_data_v3.py` into the package; `iberia_config()` does `from ...data.regions.iberia_868.territory_data import KINGDOMS, DUCHIES, CONDADOS`.
- **D-14 (Storage on RegionConfig):** Territory data lives directly on `RegionConfig` as `cfg.kingdoms`, `cfg.duchies`, `cfg.condados`. Pipeline stages take a single argument (`cfg`).

### Claude's Discretion

- RegionConfig as `@dataclass` vs pydantic `BaseModel`.
- Exact submodule split inside `cleanup.py`.
- Where territory-data path lives precisely (under `backend/medieval_forge/data/regions/iberia_868/territory_data.py` vs repo-root `data/regions/iberia_868/territory_data.py`).
- conftest.py fixture wiring (session vs function scope, tmp_path layout for output diff inspection on failure).
- Whether `tests/parity/test_iberia_868.py` runs the full pipeline once and asserts 12 files in one test, or splits into 12 narrow tests with shared session fixture (preference: shared session fixture).
- CI parity-gate flip mechanics — when in the phase the `pytest-parity` job becomes non-skippable.

### Deferred Ideas (OUT OF SCOPE)

- Stage abstraction with `version_token` + in-memory stage cache (Phase 04).
- Region YAML loader + Pydantic territory schemas (Phase 05).
- Per-file tolerance YAML for parity (Phase 06).
- Frontend stepper UI cleanup (Phase 03).
- Mid-port refactor of `cleanup.py` sub-stages (later).
- Migrating RegionConfig from `@dataclass` to pydantic `BaseModel` (Claude's discretion).
- CI parity baseline-refresh tooling (manual rsync; scripted later).
- inicio sync watchdog (manual diff for now).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| V3-PIPELINE-PARITY | Port `inicio/map_generator.py` as a deterministic, parametrized library and prove byte-equivalence with the Reconquista exports for Iberia 868. | Sections §1 (Algorithm anatomy), §2 (RegionConfig contract), §3 (V1 deletion graph), §4 (Fixture provisioning), §5 (Parity comparison harness), §7 (CI flip plan), §8 (Validation Architecture). Success criteria 1-3 from ROADMAP.md map onto §5 + §7. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

These directives are non-negotiable and apply to every plan/task in this phase:

1. **NEAREST upscale only** for lookup PNGs — never BICUBIC/BILINEAR. Belongs in `render.py` (Section 9 of inicio at line 635) and `lookup.py` if it ever upscales (it doesn't — lookups are 1x).
2. **σ ∈ [3.0, 4.5]** for the Gaussian-per-mask smoothing pass. Belongs in `cleanup.py` (Section 7 of inicio, lines 469-483). Note: inicio's default is `smooth_sigma=3.0` (line 97) and the `cleanup_and_smooth` function uses the cfg value directly; the docstring "σ ∈ [3.0, 4.5]" describes the valid range, not the default.
3. **KD-trees per country** — never a single global KD-tree. Belongs in `voronoi.py` (Section 6 of inicio, `setup_baronies` at line 335). The 38-point PT/ES border polygon (line 132 of inicio) is data on `cfg.border_polygon`.
4. **`original_idx` in every territory** — every condado/barony in `territory_metadata.json` must include `original_idx`. **This is currently MISSING from inicio.** See §6 Pitfall P-1 — `inicio/map_generator.py:680-726` (`export_metadata`) does NOT emit `original_idx` per condado/barony entry. The Nájera bug doc says it must, the deployed Reconquista `territory_metadata.json` (which we use as gold standard) MAY or may not have it. **Planning must verify the deployed file's shape** before deciding which way the port goes; D-09 says deployed wins if inicio drifts.
5. **`ocean=-1` and `ignore=9999` in the median pass** — sentinels in `cleanup.py`. Lines 442 + 448 of inicio.
6. **2x masks rendered independently** — `mountains_mask.png` and `rivers_overlay.png` at 3840×2160 are fresh renders (not upscaled). Belongs in `render.py` (Section 12 of inicio — `render_mountains` line 733, `render_rivers` line 765).
7. **`byOriginalIdx` Unity-side** — pipeline-side guarantee: `original_idx` is unique and stable across re-runs. Determinism is enforced by `np.random.default_rng(42)` (currently hardcoded at lines 537 and 904; must move onto `cfg.rng_seed`).

**Rejected designs ("What v3 explicitly is NOT"):**
- No LLM in geometric path. ✓ Phase 01 ships zero LLM.
- No stepper UI. ✓ Phase 01 doesn't touch the frontend.
- No `sys.modules` patching. ✓ `services/generator.py` (which uses it at lines 79-126) is deleted.
- No upscale interpolation. ✓ Rule #1 above.
- No global Voronoi. ✓ Rule #3 above.
- No hand-rolled compound undo. ✓ Out of scope for Phase 01.

## 1. Algorithm Anatomy — `inicio/map_generator.py` to submodule mapping

The inicio source has 13 explicit sections (banner-comment delimited). The mapping below is verbatim — every function lives in exactly one submodule; nothing is split across files. Functions tagged `[SHARED]` are needed by ≥2 submodules; recommended home is the leftmost one with cross-submodule re-export.

| Inicio section | Lines | Function(s) | Target submodule | Notes |
|----------------|-------|-------------|------------------|-------|
| §1 CONFIGURATION | 49-145 | `RegionConfig` dataclass; `iberia_config()` factory | `contracts.py` (RegionConfig); `regions.py` (iberia_config) | D-03 puts the dataclass in `contracts.py`; D-04 puts the factory in `regions.py: REGIONS["iberia_868"] = iberia_config`. |
| §2 COORDINATE TRANSFORMS | 149-185 | `geo_to_pixel`, `pixel_to_geo`, `point_in_polygon` | `contracts.py` [SHARED] | All three are pure functions called from `landmask.py`, `border.py`, `voronoi.py`, `render.py`. Living next to `RegionConfig` keeps the geometry-primitive layer in one place. |
| §3 DATA LOADING | 189-260 | `load_territory_data`, `decode_topojson_municipalities`, `load_municipalities` | **DELETE** `load_territory_data` (banned `importlib.reload` per D-13); KEEP `decode_topojson_municipalities` + `load_municipalities` in `landmask.py` | `load_territory_data` is replaced by D-13's static import on `iberia_config()`. The TopoJSON decoder + GeoJSON loader feed `build_land_mask` and `rasterize_baronies`, both of which live in `landmask.py`/`voronoi.py` respectively, but the loaders themselves are I/O — `landmask.py` is the natural home (first consumer). |
| §4 LAND MASK GENERATION | 264-310 | `build_land_mask` | `landmask.py` | One-to-one. |
| §5 BORDER MASK | 314-328 | `build_border_mask` | `border.py` | One-to-one. |
| §6 BARONY ASSIGNMENT | 332-429 | `setup_baronies`, `rasterize_baronies` | `voronoi.py` | One-to-one. KD-trees per country (rule #3) live here. |
| §7 CLEANUP & SMOOTHING | 433-497 | `cleanup_and_smooth` | `cleanup.py` | One function but FOUR sub-stages: median (lines 440-448), fragment removal (450-467), Gaussian smoothing (469-483), final merge (485-495). See §9.b for split recommendation. |
| §8 HIERARCHY MAPS | 500-516 | `build_hierarchy_maps` | `voronoi.py` | **Tie-break:** operates on the same `bc/bd/bk` arrays produced by `setup_baronies`. Could go in `cleanup.py` (it's the last cleanup-y step before render) but `voronoi.py` is more cohesive. |
| §9 RENDERING | 519-649 | `render_map` | `render.py` | One-to-one. Rule #1 (NEAREST) and rule #6 (2x mask independent) live here. |
| §10 LOOKUP MAPS | 652-673 | `generate_lookup_map` | `lookup.py` | One-to-one. Deterministic RGB hashing (`(i*37+50, i*73+80, i*113+30) % 256`). |
| §11 METADATA EXPORT | 676-726 | `export_metadata` | `export.py` | One-to-one. **Pitfall P-1: must add `original_idx` per entry — see §6.** |
| §12 MOUNTAINS & RIVERS | 729-791 | `render_mountains`, `render_rivers` | `render.py` | One-to-one. They're independent 2x renders (rule #6) so naturally pair with `render_map`. |
| §13 MAIN PIPELINE | 794-944 | `generate_maps` | `pipeline/__init__.py` as `run_pipeline(cfg) -> None` (D-03) | Renamed: `generate_maps(cfg, territory_module=, draw_names=)` becomes `run_pipeline(cfg)`. `territory_module` arg vanishes (D-13). `draw_names` becomes `cfg.draw_names`. |

**No inicio function is genuinely "shared across modules" except the Section 2 transforms.** Every other function has exactly one caller submodule. The Section 2 transforms (`geo_to_pixel`, `pixel_to_geo`, `point_in_polygon`) are pure functions used by 4 submodules; placing them in `contracts.py` keeps them with `RegionConfig` so submodules import `from .contracts import RegionConfig, geo_to_pixel`.

**Sub-section split for `cleanup.py` (Claude's discretion per CONTEXT.md):** Keep all four sub-stages in one file mirroring inicio Section 7. Three reasons: (a) the four sub-stages mutate `raw` in place sequentially — splitting forces passing the mutating array through 4 module boundaries; (b) the file is ~70 lines total post-port, well under any "too big" threshold; (c) Karpathy: don't split for hypothetical future flexibility. If Phase 04 needs to expose median/fragment/smooth/merge as separate Stages, that's where the split happens, not now.

`pipeline/__main__.py` is a tiny shim (D-03):

```python
# Source: synthesised — pattern confirmed by D-03 + python docs for __main__.py
import argparse
from . import run_pipeline
from .regions import REGIONS

if __name__ == "__main__":
    p = argparse.ArgumentParser(prog="python -m medieval_forge.services.pipeline")
    p.add_argument("--region", required=True, choices=list(REGIONS.keys()))
    p.add_argument("--out", required=True)
    args = p.parse_args()
    cfg = REGIONS[args.region]()
    cfg.output_dir = args.out
    run_pipeline(cfg)
```

This satisfies success criterion 2 from ROADMAP.md ("Pipeline runs standalone without FastAPI").

## 2. RegionConfig Contract

### 2.a Required fields for parity

The verbatim port must carry every inicio `RegionConfig` field plus the territory data and an explicit RNG seed. Source: `inicio/map_generator.py:52-112`.

| Field | Type | Default (inicio line) | Why needed for parity |
|-------|------|-----------------------|------------------------|
| `name` | str | `"iberia"` (55) | Logging + metadata `region` field. |
| `map_w` | int | `1920` (58) | 1x render resolution. |
| `map_h` | int | `1080` (59) | 1x render resolution. |
| `upscale` | int | `2` (60) | 2x final output multiplier. |
| `lon_min, lon_max, lat_min, lat_max` | float | `-13.2, 8.2, 35.4, 44.6` (64-66) | WGS84 bounds — feed every `geo_to_pixel`. |
| `lon_scale` | float \| None | `None` → cos(center_lat) in `__post_init__` (109-112) | Projection correction; **must be reproduced verbatim** for pixel-equality. |
| `output_dir` | str | `"../Assets/StreamingAssets/Maps"` (72) | Replaced at runtime — for parity tests, points at `tmp_path`. |
| `municipality_pt_geojson` | str \| None | `None` (73) | iberia_config sets to `data/regions/iberia_868/inputs/pt_concelhos_wgs84.geojson` per D-11. |
| `municipality_es_topojson` | str \| None | `None` (74) | Same — `data/regions/iberia_868/inputs/es-atlas-pkg/package/es/municipalities.json`. |
| `mountain_river_json` | str \| None | `None` (75) | Same — `data/regions/iberia_868/inputs/mountain_river_data.json`. |
| `border_polygon` | list[(lon,lat)] | `[]` (79); iberia_config sets the 38-point polygon (132-143) | Drives `build_border_mask` (rule #3). |
| `pt_duchies` | set[str] | `{}` (82); iberia_config sets `{"d_portucale", "d_gharb", "d_fronteira"}` (125) | KD-tree-per-country routing (rule #3). |
| `kingdom_colors` | dict[int, tuple] | `{}` (85); iberia_config sets 4 colors (126-131) | Visual rendering palette. |
| `ocean_near` | tuple | `(45,90,140)` (86) | Visual ocean gradient near coast. |
| `ocean_far` | tuple | `(70,130,180)` (87) | Visual ocean gradient far. |
| `ocean_gradient_dist` | float | `150.0` (88) | Gradient ramp length in pixels. |
| `coast_inner_width` | int | `2` (89) | Inner coast outline. |
| `coast_inner_color` | tuple | `(15,10,5)` (90) | Inner coast color. |
| `island_min_px` | int | `300` (93) | Discard tiny disconnected land blobs. |
| `fragment_min_px` | int | `600` (94) | Merge tiny barony fragments after median. |
| `blob_merge_px` | int | `200` (95) | Merge tiny final blobs at end of cleanup. |
| `median_passes` | int | `8` (96) | **Kernel sequence is hardcoded inside `cleanup_and_smooth`: `11 if i<2 else 9 if i<4 else 7 if i<6 else 5`** (line 443). Do NOT promote to cfg field — that violates D-01 verbatim. |
| `smooth_sigma` | float | `3.0` (97) | Gaussian-per-mask σ; valid range [3.0, 4.5] per CLAUDE.md rule #2. |
| `mountain_threshold` | int | `1500` (100) | Elevation cutoff (unused by current pipeline — DEM not wired). |
| `mountain_color_visual` | tuple | `(118,100,80)` (101) | Mountain visual color. |
| `mountain_color_lookup` | tuple | `(50,45,40)` (102) | Mountain lookup color (unused — terrain_lookup is not in inicio's pipeline; see §6 Pitfall P-2). |
| `mountain_noise` | int | `20` (103) | Random noise added to mountain pixels. |
| `river_color` | tuple | `(74,144,217)` (105) | River line color. |
| `river_width` | int | `2` (106) | River line width (multiplied by upscale). |

**New fields the port introduces (not in inicio):**

| Field | Type | Default | Why |
|-------|------|---------|-----|
| `kingdoms` | dict | `{}` | D-14 — territory data lives on cfg. iberia_config populates from the static import. |
| `duchies` | dict | `{}` | D-14. |
| `condados` | list[tuple] | `[]` | D-14. |
| `rng_seed` | int | `42` | inicio hardcodes `np.random.default_rng(42)` at lines 537 + 904; CLAUDE.md says "`np.random.default_rng(42)` is locked in `RegionConfig`" — promotion is required by the project contract. The two call sites read `cfg.rng_seed`. |
| `draw_names` | bool | `False` | D-03 — `generate_maps(draw_names=)` argument moves onto cfg. **Default `False` for parity** because the deployed Reconquista `visual_condado.png` was rendered with `draw_names=True` in inicio's main block (line 944), but the v1 wrapper (`services/generator.py:332`) calls `generate_maps(..., draw_names=False)`. **Planning task: verify which produced the deployed file by spot-checking pixel patterns at `(cx, cy)` of any condado.** If deployed has names → `draw_names=True`. If not → `False`. |

### 2.b `@dataclass` vs pydantic `BaseModel` — recommend `@dataclass`

| Criterion | `@dataclass` | pydantic `BaseModel` |
|-----------|--------------|----------------------|
| Drift from inicio | Zero (inicio uses `@dataclass`) | One major API change per field (default factories, validators) |
| JSON serialize for Phase 04 sliders | `dataclasses.asdict(cfg)` → dict → `json.dumps`. Two stdlib calls, no deps. | `cfg.model_dump_json()`. One method call. |
| Validation at construction | None (positional/keyword args, no type coercion) | Strict — wrong type at construction raises immediately |
| Mutability for sliders | Always mutable (`cfg.smooth_sigma = 4.0`) | Mutable iff `model_config = ConfigDict(frozen=False)` (the default in pydantic 2.x) |
| `__post_init__` for derived fields (`lon_scale`) | Native (`def __post_init__`) | `@model_validator(mode='after')` — different idiom |
| Parity-test debugging | `repr(cfg)` is sufficient | Same |
| Phase 04 needs (per ROADMAP.md SC-1: "explicit DAG with version_token per stage") | Stages can compute version tokens from `dataclasses.fields(cfg)` introspection just as well | Same via `cfg.model_fields` |

**Recommendation:** `@dataclass`. The pydantic upgrade pays its cost (extra dep import in test paths, different idiom, mutability ambiguity with `Frozen` defaults across pydantic 1/2) and earns nothing Phase 01 needs. Promote to pydantic in Phase 04 IF and only if a slider validation use case actually emerges. Karpathy: don't pay for hypothetical use.

[VERIFIED: `inicio/map_generator.py:52` uses `@dataclass` decorator]
[VERIFIED: `backend/medieval_forge/services/generator.py:210` uses `RegionConfig.__dataclass_fields__` — current code already assumes dataclass]

### 2.c Territory-data path — recommend `backend/medieval_forge/data/regions/iberia_868/territory_data.py`

| Option | Pros | Cons |
|--------|------|------|
| **`backend/medieval_forge/data/regions/iberia_868/territory_data.py`** (recommended) | Inside the package — `pip install -e .` ships it; relative import `from ...data.regions.iberia_868.territory_data import KINGDOMS` works from `pipeline/regions.py`. Mirrors existing `backend/medieval_forge/services/territory_iberia.json` (current v1 location). | One layer of nesting beyond the existing `services/`. |
| Repo-root `data/regions/iberia_868/territory_data.py` | Symmetric with `data/regions/iberia_868/inputs/` (D-11 inputs location). | Not part of the installed package — `pip install -e .` skips it; `pyproject.toml` would need `tool.setuptools.package-data` or `[project] include-package-data` extra wiring; relative imports become absolute and fragile. |

**Recommendation:** `backend/medieval_forge/data/regions/iberia_868/territory_data.py`. Inputs (29.7 MB GeoJSON + ES TopoJSON + mountain_river JSON) live at repo root because they're large and don't need to be importable; the territory data is a 17 KB Python module with three named constants — it belongs in the package as code. Add to `pyproject.toml`:

```toml
[tool.setuptools.packages.find]
where = ["backend"]
include = ["medieval_forge*"]
# data.regions.* matches automatically because they are package directories with __init__.py
```

Each subdirectory under `backend/medieval_forge/data/` needs an empty `__init__.py` so Python recognises them as packages.

## 3. V1 Deletion Graph

This is the surgical, import-graph-driven trace per D-06. Methodology: starting from `services/generator.py` and `api/generate.py`, walk imports backwards. A file is **DELETE** iff its only consumers in the survivor set are themselves in the delete set.

[VERIFIED via `Grep "from \.\.services\." backend/`]

### 3.a Confirmed delete (production code)

| File | Lines | Why deletable | Consumer trace |
|------|-------|---------------|----------------|
| `backend/medieval_forge/lib/map_generator.py` | 1094 | Vendored v1 copy of inicio's pipeline; only `services/generator.py` imports it. | `services/generator.py:27 from ..lib import map_generator` — that's it. No other consumer. |
| `backend/medieval_forge/lib/__init__.py` | 1 | Empty package init; `lib/` becomes empty after `map_generator.py` dies. | Drop the dir. |
| `backend/medieval_forge/services/generator.py` | 391 | Wraps `lib/map_generator` with banned `sys.modules` patching. Only `api/generate.py` imports it. | `api/generate.py:21 from ..services.generator import GENERATED_FILE_WHITELIST, run_generation`. Tests `test_generator_e2e.py`, `test_generate.py` import it. |
| `backend/medieval_forge/services/render_modern.py` | 199 | Renders the "modern" preview mode triggered only by `api/generate.py`'s `/render-modern` endpoint. | `api/generate.py:23 from ..services.render_modern import render_modern_map` — only consumer. |
| `backend/medieval_forge/api/generate.py` | 270 | The endpoint stack being deleted. | `main.py:50` (router registration) is the consumer; deleting requires editing `main.py` to remove the import + `include_router` line. |

**Total: 5 files, ~1955 lines of production code deleted.**

### 3.b Confirmed survive (production code) — flagged in CONTEXT.md but NOT actually reachable from generator/api-generate alone

| File | Lines | Why surviving | Other consumer |
|------|-------|---------------|----------------|
| `backend/medieval_forge/services/voronoi.py` | 540 | Imported by `api/edit.py` (5 sites: lines 64, 154, 204, 343, 403) for the v1 stepper canvas tools (capital move, merge, reshape, split). `api/edit.py` survives Phase 01 per D-08. | `api/edit.py` |
| `backend/medieval_forge/services/territories_geojson.py` | 360 | Imported by `api/edit.py` (7 sites) AND `services/generator.py:339` AND `services/voronoi.py:336` AND `services/baronies_geojson.py:19`. Survivor set after Phase 01 still imports it. | `api/edit.py`, `services/voronoi.py`, `services/baronies_geojson.py` |
| `backend/medieval_forge/services/baronies_geojson.py` | 124 | Imported by `services/generator.py:340` only — but is that the ONLY consumer? Check: `Grep` confirms no other file imports `baronies_geojson`. **Therefore: actually a confirmed-delete IF api/edit.py doesn't need it.** Verifying: `api/edit.py:491` reads `baronies.geojson` from disk via `json.loads(baronies_path.read_text())` — does NOT import the module. | None after Phase 01 → **DELETE.** |
| `backend/medieval_forge/services/territory_builder.py` | 290 | Imported by `api/edit.py:463 (select_latest_cache_row)` AND `api/generate.py:24 (build_territory_data_from_cache)`. After api/generate dies, `api/edit.py` keeps it alive. | `api/edit.py` |
| `backend/medieval_forge/services/baronies_builder.py` | 130 | Imported by `api/ingest.py:22` only — Phase 02 consumer. Untouched. | `api/ingest.py` |
| `backend/medieval_forge/services/paths.py` | 65 | Imported by 7+ survivors (`api/projects`, `api/ingest`, `api/edit`, `api/codex`, `api/research`, `api/terrain`, `api/export`, `services/export`, `services/ingest_runner`, `services/research_runner`, `services/territories_geojson`, `services/ingest_terrain/runner`). Survives. | Many |

**Updated confirmed-delete production list (revising CONTEXT.md D-05 tentative list):**
1. `lib/map_generator.py`
2. `lib/__init__.py` (and the `lib/` directory)
3. `services/generator.py`
4. `services/render_modern.py`
5. `services/baronies_geojson.py` ← added based on trace
6. `api/generate.py`
7. Two lines in `main.py`: `from .api.generate import router as generate_router` (line 50) and `app.include_router(generate_router, prefix="/api")` (line 61)

CONTEXT.md D-05's tentative list mentioned `services/voronoi.py`, `services/baronies_builder.py`, `services/render_modern.py`, `services/territory_builder.py`, `services/territories_geojson.py` as candidates — only `render_modern.py` is actually deletable per the trace. This is the kind of surprise D-06 explicitly flagged ("final list traced during planning").

### 3.c Confirmed delete (test code) per D-07

| File | Lines | Why deletable | Notes |
|------|-------|---------------|-------|
| `backend/tests/test_generator_e2e.py` | ? | Tests deleted `services/generator.py` end-to-end. | Plan-task #1 deletes alongside production. |
| `backend/tests/test_generate.py` | ? | Tests deleted `api/generate.py` (POST /projects/{id}/generate, etc). | Imports `lib/map_generator` directly (lines 296+). Dies. |
| `backend/tests/test_terrain.py` | ? | Imports `lib/map_generator` (lines 30, 109, 159, 200, 247) for `RegionConfig` + `render_mountains_from_data` + `_TERRAIN_TYPES`. | The functions tested (`render_mountains_from_data`, `generate_terrain_lookup`) are in v1's `lib/map_generator` but **NOT in inicio's `map_generator.py`** (see §6 Pitfall P-2). With `lib/` deleted, this test loses its imports — delete. |
| `backend/tests/test_baronies_geojson.py` | ? | Tests deleted `services/baronies_geojson.py`. | Dies. |
| `backend/tests/services/test_voronoi.py` | ? | Tests **surviving** `services/voronoi.py`. | **KEEP.** |
| `backend/tests/services/test_territory_iberia_parity.py` | ? | The v1 "parity" test against an old territory snapshot — replaced by new `tests/parity/test_iberia_868.py`. | Delete per D-07. |
| `backend/tests/services/test_territory_builder*.py` (3 files) | ? | Test surviving `services/territory_builder.py`. | **KEEP.** |
| `backend/tests/test_territories_geojson.py`, `tests/services/test_territories_geojson_consistency.py` | ? | Test surviving `services/territories_geojson.py`. | **KEEP.** |
| `backend/tests/test_export.py` | ? | Imports `services/paths` only — survives. | **KEEP.** |

**Confirmed-delete test files: 5 (`test_generator_e2e.py`, `test_generate.py`, `test_terrain.py`, `test_baronies_geojson.py`, `test_territory_iberia_parity.py`).**

CONTEXT.md D-05 also mentioned `test_territory_builder*.py` and "API test of /api/generate" as deletes — clarifying:
- `test_territory_builder*.py` SURVIVES (territory_builder.py survives).
- API tests of `/api/generate`: `tests/api/test_generate_uses_cached_research.py` and `tests/api/test_generate_validation.py` — both die.

**Updated confirmed-delete test list:**
1. `tests/test_generator_e2e.py`
2. `tests/test_generate.py`
3. `tests/test_terrain.py`
4. `tests/test_baronies_geojson.py`
5. `tests/services/test_territory_iberia_parity.py`
6. `tests/api/test_generate_uses_cached_research.py`
7. `tests/api/test_generate_validation.py`

### 3.d FastAPI app boot must stay green

Phase 00 SC-6 requires `medieval-forge start` boots and serves 200 OK on `/`. After deletion, `main.py` lines 50 and 61 are removed; the SPA catch-all (line 76) keeps `/` working. The deletion commit and the `main.py` edit MUST be in the same atomic commit so no in-between commit has a broken import (D-01 atomic-commits convention from Phase 00).

## 4. Fixture Provisioning

### 4.a Golden fixtures — `tests/fixtures/iberia_868/golden/` (D-10)

Snapshot of `D:\Projetos_Jogo\Reconquista\Assets\StreamingAssets\Maps\` from `ls -la` of that directory:

[VERIFIED: filesystem inspection 2026-05-07]

| File | Size | LFS or direct? |
|------|------|----------------|
| `lookup_barony.png` | 55,142 B (54 KB) | Direct |
| `lookup_barony_colors.json` | 5,094 B (5 KB) | Direct |
| `lookup_condado.png` | 37,974 B (37 KB) | Direct |
| `lookup_condado_colors.json` | 1,893 B (2 KB) | Direct |
| `terrain_lookup.png` | 23,186 B (23 KB) | Direct |
| `terrain_types.json` | 627 B | Direct |
| `territory_metadata.json` | 65,445 B (64 KB) | Direct |
| `visual_condado.png` | 465,894 B (455 KB) | Direct |
| `visual_barony.png` | 505,303 B (493 KB) | Direct |
| `mountains_mask.png` | 12,232 B (12 KB) | Direct |
| `rivers_overlay.png` | 47,324 B (46 KB) | Direct |
| `mountain_river_data.json` | 19,307 B (19 KB) | Direct (also lives under `data/regions/iberia_868/inputs/` per D-11 — same file, different role: input vs golden output for the JSON contract) |
| **Total** | **~1,239,421 B (1.18 MB)** | All direct, no LFS |

**LFS decision: NO LFS needed.** Total < 2 MB; well within GitHub's 100 MB hard cap and 50 MB soft warning. LFS adds friction (requires `git lfs install` on every clone) for zero benefit at this scale.

### 4.b Pipeline inputs — `data/regions/iberia_868/inputs/` (D-11)

| File | Source | Size | LFS or direct? |
|------|--------|------|----------------|
| `pt_concelhos_wgs84.geojson` | `D:\Projetos_Jogo\Reconquista\Assets\Downloads\handoff\pt_concelhos_wgs84.geojson` | 29,705,375 B (28.3 MB) | **LFS RECOMMENDED.** GitHub's soft warning is 50 MB and recommendation kicks in at 5 MB+; pushing 28 MB to a normal pack works but balloons clone time. With LFS, repo stays light. |
| `es-atlas-pkg/package/es/municipalities.json` | npm package `martgnz/es-atlas` v0.6.x — **NOT in this repo or Reconquista** as of 2026-05-07. | Unknown until fetched (likely 5-15 MB based on TopoJSON typical ratios for Spain's 8,116 municipalities) | LFS likely needed; size determines. |
| `mountain_river_data.json` | `inicio/mountain_river_data.json` (also at Reconquista's `Assets/StreamingAssets/Maps/`) | 19,307 B (19 KB) | Direct. |

**Plan-task implication for D-11:** acquiring the ES TopoJSON is a planning task. Two paths:
1. `npm pack es-atlas` in a scratch dir → extract `package/es/municipalities.json` → commit.
2. Direct download from `https://github.com/martgnz/es-atlas/raw/master/data/es/municipalities.json` (URL referenced in `inicio/licoes/MAPA_V2_GEOJSON_BRIEFING.md:30`).

**Total fixture footprint: ~1.18 MB (golden) + ~28-43 MB (inputs).** With LFS for the two large GeoJSON/TopoJSON files, the regular Git pack stays under 2 MB.

### 4.c Why `mountain_river_data.json` lives in two places

It's both an input (the pipeline reads it to render mountains/rivers) and an output (the 12-file Unity contract includes it as `mountain_river_data.json` per CLAUDE.md). The pipeline copies it through unchanged (inicio doesn't transform it). Place the canonical one under `data/regions/iberia_868/inputs/`; the golden copy under `tests/fixtures/iberia_868/golden/` is byte-identical and the parity test asserts deep-equality.

## 5. Parity Comparison Harness

### 5.a Pytest layout — recommended: shared session fixture + 12 narrow tests

```
backend/tests/parity/
├── __init__.py
├── conftest.py                    # session-scoped pipeline_output fixture
└── test_iberia_868.py             # 12 individual @pytest.mark.parity tests
```

**`conftest.py` (recommended):**

```python
# Source: synthesised from pytest docs (https://docs.pytest.org/en/stable/how-to/fixtures.html#scope-sharing-fixtures-across-classes-modules-packages-or-session)
import pytest
from pathlib import Path
from medieval_forge.services.pipeline import run_pipeline
from medieval_forge.services.pipeline.regions import REGIONS

REPO_ROOT = Path(__file__).resolve().parents[3]  # backend/tests/parity → repo root
GOLDEN_DIR = REPO_ROOT / "tests" / "fixtures" / "iberia_868" / "golden"

@pytest.fixture(scope="session")
def pipeline_output(tmp_path_factory):
    out = tmp_path_factory.mktemp("iberia_868_actual")
    cfg = REGIONS["iberia_868"]()
    cfg.output_dir = str(out)
    run_pipeline(cfg)
    return out

@pytest.fixture(scope="session")
def golden_dir():
    return GOLDEN_DIR
```

`scope="session"` runs the pipeline once for all 12 tests; the inicio doc says full Iberia generation is ~45 s (`JORNADA_CRIACAO_MAPA.md:680`) so per-test runs would be unacceptable in CI. `tmp_path_factory.mktemp` survives the session and is auto-cleaned by pytest.

### 5.b Test split — 12 tests, one per fixture file

```python
# backend/tests/parity/test_iberia_868.py
# Source: comparison rules per D-12 + skimage docs (https://scikit-image.org/docs/stable/api/skimage.metrics.html#skimage.metrics.structural_similarity)
import json
import pytest
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

pytestmark = pytest.mark.parity

# --- Lookup PNGs: byte-equal ---
@pytest.mark.parametrize("name", ["lookup_barony.png", "lookup_condado.png", "terrain_lookup.png"])
def test_lookup_png_byte_equal(pipeline_output, golden_dir, name):
    actual = np.array(Image.open(pipeline_output / name))
    golden = np.array(Image.open(golden_dir / name))
    if not np.array_equal(actual, golden):
        diff_path = pipeline_output / f"DIFF_{name}"
        Image.fromarray(np.where(actual == golden, 0, 255).astype(np.uint8)).save(diff_path)
        pytest.fail(
            f"{name}: pixel-mismatch.\n"
            f"  golden: {golden_dir / name}\n"
            f"  actual: {pipeline_output / name}\n"
            f"  diff:   {diff_path}\n"
            f"  inspect: open both PNGs and the DIFF mask to triage."
        )

# --- Visual PNGs + masks: SSIM ≥ 0.98 ---
@pytest.mark.parametrize("name", ["visual_condado.png", "visual_barony.png", "mountains_mask.png", "rivers_overlay.png"])
def test_visual_png_ssim(pipeline_output, golden_dir, name):
    actual = np.array(Image.open(pipeline_output / name).convert("RGB"))
    golden = np.array(Image.open(golden_dir / name).convert("RGB"))
    score = ssim(actual, golden, channel_axis=2, data_range=255)
    assert score >= 0.98, (
        f"{name}: SSIM {score:.4f} < 0.98.\n"
        f"  golden: {golden_dir / name}\n"
        f"  actual: {pipeline_output / name}"
    )

# --- JSONs: deep-equal after recursive key-sort ---
def _normalise(obj):
    if isinstance(obj, dict):
        return {k: _normalise(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return [_normalise(x) for x in obj]
    return obj

@pytest.mark.parametrize("name", [
    "lookup_barony_colors.json", "lookup_condado_colors.json",
    "terrain_types.json", "territory_metadata.json",
    "mountain_river_data.json",
])
def test_json_deep_equal(pipeline_output, golden_dir, name):
    actual = _normalise(json.loads((pipeline_output / name).read_text(encoding="utf-8")))
    golden = _normalise(json.loads((golden_dir / name).read_text(encoding="utf-8")))
    assert actual == golden, (
        f"{name}: JSON mismatch.\n"
        f"  hint: diff <(jq -S . {golden_dir / name}) <(jq -S . {pipeline_output / name})"
    )
```

This produces **12 tests** (3 + 4 + 5), one per file, all sharing the single `pipeline_output` session fixture. Each failure points the developer at the exact file + a `diff` command they can run locally.

### 5.c Why session fixture (not single test)

Single-test asserts on 12 files would surface only the first mismatch — debugger has to fix one and re-run to discover the next. Twelve narrow tests run in parallel under pytest-xdist if needed (sequential is fine — the 45 s pipeline is the bottleneck) and report ALL mismatches in one CI run. CONTEXT.md states "preference: shared session fixture" — confirmed by the failure-attribution argument.

### 5.d Diff-on-failure beyond the failure message

The byte-equal test writes a per-pixel diff PNG (`DIFF_<name>`) to tmp_path; the SSIM test could also write a per-pixel SSIM map (skimage's `structural_similarity(..., full=True)` returns it). Optional for Phase 01 — keep it simple unless the planner sees value. The hint message already gives developer enough to triage.

## 6. Pitfalls to NOT Relearn

Distilled from `inicio/licoes/JORNADA_CRIACAO_MAPA.md` (~30 hours of debugging documented) and `.planning/v1-archive/STATE.md` decisions table. Each is mapped to its target submodule.

| # | Pitfall | Submodule | Source |
|---|---------|-----------|--------|
| **P-1** | **Nájera bug — missing `original_idx`.** Generator skips empty condados in `metadata` (compacts) but `lookup_condado_colors.json` keeps original indices (preserves gaps). Without `original_idx` per metadata entry, Unity's `byOriginalIdx` lookup is off-by-N for indices ≥ N. **inicio's `export_metadata` (lines 680-726) does NOT emit `original_idx`** — this looks like an oversight in inicio per `JORNADA_CRIACAO_MAPA.md:425-441`. Planning task: verify what the deployed `territory_metadata.json` has, decide whether port reproduces inicio (no `original_idx`) or fixes (adds `original_idx`). D-09 says deployed wins. | `export.py` | `JORNADA_CRIACAO_MAPA.md:416-441`; CLAUDE.md rule #4 |
| **P-2** | **Terrain lookup is in the 12-file contract but NOT in inicio's pipeline.** `terrain_lookup.png` + `terrain_types.json` appear in the 12-file contract (CLAUDE.md) and in the deployed Reconquista files (`/d/Projetos_Jogo/Reconquista/Assets/StreamingAssets/Maps/terrain_lookup.png` exists, 23 KB). But inicio's `generate_maps` (lines 798-934) NEVER produces them. The v1 `lib/map_generator.py` adds a `generate_terrain_lookup` function (referenced by deleted `tests/test_terrain.py`). **Either inicio is incomplete (and the gold standard was produced by v1) or the deployed `terrain_lookup.png` is leftover from v1.** Planning task: pick a path. Two options: (a) port the v1 `generate_terrain_lookup` from `lib/map_generator.py` lines beyond inicio's 944 — violates D-01 verbatim; (b) declare inicio gold; the parity test for `terrain_lookup.png` and `terrain_types.json` is ALSO not in scope, drop those two files from the parity suite. **Recommendation: option (b) — drop terrain_lookup.png and terrain_types.json from the Phase 01 parity suite, list them as Phase 06 work** (the export-validation gate phase will fold terrain in). The 12-file contract becomes a 10-file Phase 01 contract; fixtures still ship the 12 files for Phase 06's eventual use. | `lookup.py` (n/a — defer) | inicio scope; CLAUDE.md 12-file table; `lib/map_generator.py` extra; deleted `tests/test_terrain.py`. |
| **P-3** | **NEAREST upscale ONLY.** BICUBIC/BILINEAR contaminates ocean with dark coast pixels → "black dots in ocean" bug. 15+ failed attempts in inicio. inicio uses `Image.NEAREST` at line 635. | `render.py` | `JORNADA_CRIACAO_MAPA.md:386-414`; CLAUDE.md rule #1 |
| **P-4** | **2x land mask is INDEPENDENT, not upscaled.** Build it from polygons at 2x resolution with `build_land_mask(target_w=W2, target_h=H2)`. Upscaling the 1x mask creates fractional boundary pixels. inicio does this at line 835. | `landmask.py` (consumed by `render.py`) | `JORNADA_CRIACAO_MAPA.md:285-295`; CLAUDE.md rule #6 |
| **P-5** | **σ window [3.0, 4.5] with per-mask reduction for tiny territories.** inicio line 477: `s = cfg.smooth_sigma if npx > 400 else max(1.2, cfg.smooth_sigma * (npx/400))`. CLAUDE.md says window is [3.0, 4.5]; default is 3.0 (line 97). Don't move outside this range without parity-test validation. | `cleanup.py` | `JORNADA_CRIACAO_MAPA.md:443-454`; CLAUDE.md rule #2 |
| **P-6** | **KD-trees PER country, not global.** `setup_baronies` builds two trees `tp` (PT) and `te` (ES) at lines 364-366; `rasterize_baronies` queries the right one per municipality based on the 38-point border polygon ray-cast. A single global KD-tree puts ES municipalities inside Portuguese duchies. | `voronoi.py` | `JORNADA_CRIACAO_MAPA.md:80-94`; CLAUDE.md rule #3 |
| **P-7** | **Sentinels: ocean = -1, ignore = 9999 in median pass.** inicio line 442: `ri[~land] = 9999`. Line 448: `raw[~land] = -1`. The 9999 lets `median_filter` skip ocean while keeping land cluster cohesion; -1 is the "no barony" final marker. Confusion of these breaks the median pass. | `cleanup.py` | inicio §7; CLAUDE.md rule #5 |
| **P-8** | **Median filter kernel sequence: 11, 11, 9, 9, 7, 7, 5, 5.** Hardcoded inside `cleanup_and_smooth` line 443; do NOT promote to cfg field — that's a refactor (D-01 forbids). | `cleanup.py` | inicio §7 |
| **P-9** | **`np.random.default_rng(42)` for determinism.** Two call sites: line 537 (visual rendering color jitter) and line 904 (mountain noise). Both must read `cfg.rng_seed` after the port. | `render.py` | CLAUDE.md "RegionConfig is the only mutable input"; PROJECT.md D-V3-05 |
| **P-10** | **Border polygon sampled every 3 pixels** for speed (line 324: `for x in range(0, cfg.map_w, 3)`). Sampling every pixel takes 9× longer; sampling every 5+ pixels misses fine border curvature. | `border.py` | `JORNADA_CRIACAO_MAPA.md:521` ("sample fronteira a cada 3 pixels — não cada pixel — lento demais") |
| **P-11** | **`island_min_px` scales with resolution.** inicio line 307: `if lbl != main_lbl and sizes[lbl] < cfg.island_min_px * (w / cfg.map_w):`. The scaling factor is required so the 2x land mask uses 4× the island threshold (no bug at 2x where small land features get inappropriately deleted). | `landmask.py` | inicio §4 |
| **P-12** | **Rendering borders only on land pixels.** inicio lines 595, 600: `if 0 <= nx_ < w and land[y, nx_]:`. Painting border pixels on ocean breaks the "no dark dots in ocean" invariant. | `render.py` | `JORNADA_CRIACAO_MAPA.md:316` ("desenhar fronteiras APENAS em pixels de terra") |
| **P-13** | **Lookup color hash is deterministic by index.** `(i*37+50)%256, (i*73+80)%256, (i*113+30)%256` — `lookup.py:666-672`. Two runs over the same condado list MUST produce identical RGB triples. Determinism here is the contract; `original_idx` (P-1) is the bridge from RGB → metadata. | `lookup.py` | inicio §10 |
| **P-14** | **Numpy Y-down vs Unity Y-up.** Pipeline writes `pixel_center: [int(xs.mean()), int(ys.mean())]` in numpy coords (`export.py`/`territory_metadata.json`). Unity flips Y on `Texture2D.LoadImage`. The pipeline's job is to write numpy coords; Unity's job is to flip. Don't try to write Unity coords in the pipeline — Unity-side parity becomes a moving target. | `export.py` | `JORNADA_CRIACAO_MAPA.md:458-470` |
| **P-15** | **Tejo coordinate manual extension (Lisboa).** Natural Earth 50m truncates the Tejo at Santarém. The `mountain_river_data.json` shipped in inicio includes manual extension points to the Lisboa estuary. The pipeline reads this JSON unchanged — the data is the fix. Don't re-trim river coords during port. | `render.py` (rivers); `mountain_river_data.json` is data, not code | `JORNADA_CRIACAO_MAPA.md:480-494` |
| **P-16** | **`condados` array is compacted in metadata but NOT in lookup PNGs.** This compaction (skip empty condados) is what creates the Nájera bug (P-1). inicio lines 700-702 skip `npx == 0`. The lookup PNG's `generate_lookup_map` does NOT skip them (lines 663-672). The fix is `original_idx`, not symmetry — symmetry would require either skipping in both (loses indices) or keeping in both (visual junk). | `export.py` (skip), `lookup.py` (don't skip) | `JORNADA_CRIACAO_MAPA.md:425-441` |

**Source verification:** every line number above was checked against the inicio source via the `Read` tool earlier in the research.

## Runtime State Inventory

> Phase 01 includes a v1 deletion phase. The runtime state inventory applies.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — Phase 00 already archived v1 planning state under `.planning/v1-archive/`. The v1 SQLite databases (`data/medieval_forge.db`) hold project metadata + LLM cache and are NOT touched by Phase 01 — they survive because `api/projects`, `api/research`, `api/codex`, `api/edit` survive. No keys, collections, or IDs need renaming. | None. |
| Live service config | None. The pipeline runs in-process; there are no n8n / external workflows / dashboards / tunnels referencing the deleted modules. | None. |
| OS-registered state | None. No Windows Task Scheduler / launchd / pm2 entries reference `services/generator.py`, `api/generate.py`, or `lib/map_generator.py`. The `medieval-forge start` CLI entry point is registered via pyproject `[project.scripts]` and points at `medieval_forge.cli:cli` which is untouched. | None. |
| Secrets / env vars | None. `services/credential_store.py` (LLM API keys) is untouched. No env var references the deleted code. | None. |
| Build artifacts / installed packages | After deletion: `pip install -e .` re-installs without `lib/map_generator.py`. The `medieval_forge.egg-info/` may have stale RECORD entries — recommend running `pip install -e .` again after the delete commit so old `medieval_forge/lib/__init__.py` and `medieval_forge/lib/map_generator.py` references vanish from `RECORD`. Pyc files under `__pycache__` should be cleaned (`find -name __pycache__ -exec rm -rf {} +` on a Unix-like shell, or PowerShell equivalent) — not strictly required (Python re-creates them) but tidiness. | Plan-task: `pip install -e .` after delete; optional `__pycache__` sweep. |

**Nothing renamed in this phase.** Renames only happen if territory data IDs change — D-13 is a *move* of the file, not a rename of the constants `KINGDOMS`, `DUCHIES`, `CONDADOS`, so importers (the new `iberia_config()`) work without altering the constant names.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | ✓ (assumed — repo runs CI on 3.11) | 3.11 per `pyproject.toml:requires-python` | None — required. |
| numpy | Pipeline arrays | ✓ | `>=1.26,<3.0` per `pyproject.toml:30` | None. |
| scipy | KDTree, ndimage | ✓ | `>=1.13,<2.0` per `pyproject.toml:28` | None. |
| Pillow (PIL) | PNG I/O, polygon rasterisation | ✓ | `>=10.0,<13.0` per `pyproject.toml:31` | None. |
| scikit-image | SSIM in parity test | ✓ | `>=0.22,<1.0` per `pyproject.toml:34` | None. |
| pytest | Test runner | ✓ | `>=8.0,<9.0` per `pyproject.toml:39` (dev extra) | None. |
| ES TopoJSON municipalities (`es-atlas-pkg/package/es/municipalities.json`) | `landmask.py`, `voronoi.py` | **✗ NOT IN REPO OR RECONQUISTA** | npm `martgnz/es-atlas` v0.6.x | Plan-task: download via `npm pack es-atlas` or direct from `https://github.com/martgnz/es-atlas/raw/master/data/es/municipalities.json`. Without it, no parity is possible. **Blocking — must address.** |
| PT GeoJSON (`pt_concelhos_wgs84.geojson`) | `landmask.py`, `voronoi.py` | ✓ | At `D:\Projetos_Jogo\Reconquista\Assets\Downloads\handoff\pt_concelhos_wgs84.geojson` (29.7 MB) | None — copy in. |
| Mountain/river JSON | `render.py` | ✓ | At `inicio/mountain_river_data.json` (19 KB) | None. |
| Reconquista deployed maps (golden source) | Parity test fixtures | ✓ | `D:\Projetos_Jogo\Reconquista\Assets\StreamingAssets\Maps\*` | None — copy in. |
| `git lfs` | If LFS used for large GeoJSON | Unknown | TBD | Direct commit (28 MB) is workable; LFS is preference, not requirement. |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** ES TopoJSON — sourced via planning task before `voronoi.py`/`landmask.py` parity can run.

## 7. CI Flip Plan

Phase 00 already scaffolded the `pytest-parity` job (`.github/workflows/ci.yml:26-40`) with a placeholder that exits 0 when no tests are present:

```yaml
run: pytest backend/tests/parity/ backend/tests/integration/ -v -m "parity or integration" --no-header || (echo "No parity/integration tests yet (Phase 00) — passing as placeholder"; exit 0)
```

**The flip to non-skippable** = removing the `|| (echo ...; exit 0)` tail. After the flip, any non-zero pytest exit fails the job and blocks merge.

**When in the phase to flip:** the LAST commit of Phase 01, after:
1. The port is complete (`pipeline/__init__.py:run_pipeline` exists).
2. The deletion graph is executed (v1 generator stack gone, `main.py` cleaned).
3. The fixtures are committed (`tests/fixtures/iberia_868/golden/` + `data/regions/iberia_868/inputs/`).
4. The parity test (`tests/parity/test_iberia_868.py`) is committed.
5. Locally `pytest backend/tests/parity/ -v` passes (operator runs and confirms before pushing).

If the flip happens earlier — e.g. as commit 2/N of the phase — every intermediate commit during the port that has parity-failing output would fail its own CI run, triggering noisy red builds. The phase invariant is "atomic commit per task ≤1 commit" (Phase 00 convention) so each task's commit goes red, blocking merge of the phase as a series. Flipping last preserves the option of in-flight commits being amber-yellow during port iteration.

**Concrete commits in the closing sub-task:**

1. `chore(01): commit Iberia 868 golden fixtures` — `tests/fixtures/iberia_868/golden/*` (1.18 MB).
2. `chore(01): commit Iberia 868 pipeline inputs` — `data/regions/iberia_868/inputs/*` (28-43 MB; LFS if chosen).
3. `test(01): parity harness for Iberia 868` — `backend/tests/parity/test_iberia_868.py` + `conftest.py`.
4. `ci(01): flip pytest-parity job to required` — edit `.github/workflows/ci.yml` to remove the `|| exit 0` tail; this commit also bumps coverage gate from 60→85% per `pytest-unit` job comment ("Coverage gate starts at 60% for Phase 00; Phase 01 raises to 85%").

That sequencing means the parity test can be observed green locally on commit 3, and only commit 4 makes it gate-blocking. Commit 4 is the phase's last commit; if a future PR breaks parity, only that PR sees red — Phase 01's own commits are immune.

## 8. Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x (already in `pyproject.toml:39`) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` — `parity` marker registered (line 73) |
| Quick run command | `pytest backend/tests/unit/ -v --cov=medieval_forge --cov-fail-under=85` |
| Full suite command | `pytest backend/tests/ -v -m "parity or integration or not slow"` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| V3-PIPELINE-PARITY | `lookup_barony.png` byte-equal vs golden | parity | `pytest backend/tests/parity/test_iberia_868.py::test_lookup_png_byte_equal[lookup_barony.png] -x` | ❌ Wave 0 |
| V3-PIPELINE-PARITY | `lookup_condado.png` byte-equal vs golden | parity | `pytest backend/tests/parity/test_iberia_868.py::test_lookup_png_byte_equal[lookup_condado.png] -x` | ❌ Wave 0 |
| V3-PIPELINE-PARITY | `terrain_lookup.png` byte-equal vs golden | parity | (DEFERRED to Phase 06 — see Pitfall P-2) | ❌ Defer |
| V3-PIPELINE-PARITY | `visual_condado.png` SSIM ≥ 0.98 vs golden | parity | `pytest backend/tests/parity/test_iberia_868.py::test_visual_png_ssim[visual_condado.png] -x` | ❌ Wave 0 |
| V3-PIPELINE-PARITY | `visual_barony.png` SSIM ≥ 0.98 vs golden | parity | `pytest backend/tests/parity/test_iberia_868.py::test_visual_png_ssim[visual_barony.png] -x` | ❌ Wave 0 |
| V3-PIPELINE-PARITY | `mountains_mask.png` SSIM ≥ 0.98 vs golden | parity | `pytest backend/tests/parity/test_iberia_868.py::test_visual_png_ssim[mountains_mask.png] -x` | ❌ Wave 0 |
| V3-PIPELINE-PARITY | `rivers_overlay.png` SSIM ≥ 0.98 vs golden | parity | `pytest backend/tests/parity/test_iberia_868.py::test_visual_png_ssim[rivers_overlay.png] -x` | ❌ Wave 0 |
| V3-PIPELINE-PARITY | `lookup_barony_colors.json` deep-equal | parity | `pytest backend/tests/parity/test_iberia_868.py::test_json_deep_equal[lookup_barony_colors.json] -x` | ❌ Wave 0 |
| V3-PIPELINE-PARITY | `lookup_condado_colors.json` deep-equal | parity | `pytest backend/tests/parity/test_iberia_868.py::test_json_deep_equal[lookup_condado_colors.json] -x` | ❌ Wave 0 |
| V3-PIPELINE-PARITY | `terrain_types.json` deep-equal | parity | (DEFERRED to Phase 06) | ❌ Defer |
| V3-PIPELINE-PARITY | `territory_metadata.json` deep-equal | parity | `pytest backend/tests/parity/test_iberia_868.py::test_json_deep_equal[territory_metadata.json] -x` | ❌ Wave 0 |
| V3-PIPELINE-PARITY | `mountain_river_data.json` deep-equal | parity | `pytest backend/tests/parity/test_iberia_868.py::test_json_deep_equal[mountain_river_data.json] -x` | ❌ Wave 0 |
| V3-PIPELINE-PARITY | `run_pipeline(cfg)` callable from in-process Python | unit | `pytest backend/tests/unit/test_pipeline_module.py::test_run_pipeline_signature -x` | ❌ Wave 0 |
| V3-PIPELINE-PARITY | `python -m medieval_forge.services.pipeline --region iberia_868 --out /tmp/out` runs without FastAPI | unit | `pytest backend/tests/unit/test_pipeline_cli.py::test_main_cli_smoke -x` | ❌ Wave 0 |
| V3-PIPELINE-PARITY | `medieval-forge start` still boots HTTP 200 on `/` after v1 generator stack delete (Phase 00 SC-6) | integration | `pytest backend/tests/integration/test_app_boot.py::test_root_returns_200 -x` | ❌ Wave 0 (or extend existing) |
| V3-PIPELINE-PARITY | CI parity job is non-skippable | manual | Verify `.github/workflows/ci.yml` no longer ends `pytest-parity` step with `|| exit 0` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest backend/tests/unit/ -v --cov=medieval_forge --cov-fail-under=85`
- **Per wave merge:** `pytest backend/tests/ -v -m "parity or integration or not slow"`
- **Phase gate:** Full suite green, including all 10 parity assertions (12 minus 2 deferred — see Pitfall P-2), before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `backend/tests/parity/__init__.py` — empty package init
- [ ] `backend/tests/parity/conftest.py` — session-scoped `pipeline_output` + `golden_dir` fixtures
- [ ] `backend/tests/parity/test_iberia_868.py` — 10 parametrised parity tests (12 minus the 2 deferred per Pitfall P-2)
- [ ] `backend/tests/unit/test_pipeline_module.py` — verifies `run_pipeline` exists + signature (planning may merge into existing unit test file)
- [ ] `backend/tests/unit/test_pipeline_cli.py` — verifies `python -m ...` smoke
- [ ] `backend/tests/integration/test_app_boot.py` (or extend existing) — FastAPI boot still 200 OK after generator delete
- [ ] `tests/fixtures/iberia_868/golden/*` — 12 files (1.18 MB) committed
- [ ] `data/regions/iberia_868/inputs/*` — 3 files (~28-43 MB; LFS or direct) committed
- [ ] `backend/medieval_forge/data/regions/iberia_868/__init__.py` + `territory_data.py` — D-13 move
- [ ] `backend/medieval_forge/data/__init__.py` + `data/regions/__init__.py` — package markers
- [ ] CI flip: `.github/workflows/ci.yml` line 40 — drop the `|| (echo …; exit 0)` tail

## 9. Open Questions Answered

| # | Question (from CONTEXT.md "Claude's Discretion") | Recommended choice | Evidence |
|---|--------------------------------------------------|--------------------|----------|
| 1 | RegionConfig as `@dataclass` vs pydantic `BaseModel`? | `@dataclass` | §2.b — drift from inicio is the hard cost; `dataclasses.asdict` covers Phase 04's JSON serialisation needs; pydantic earns nothing Phase 01 needs and adds two idiom changes (`@model_validator` for `__post_init__`, `model_dump_json` instead of `asdict+json.dumps`). |
| 2 | Exact submodule split inside `cleanup.py`? | Keep all four sub-stages (median + fragment + smooth + merge) in one file, mirroring inicio Section 7 verbatim. | §1 — the four sub-stages mutate `raw` in place sequentially; splitting forces inter-module passes. The full file is ~70 lines post-port. Phase 04 is the right home for any Stage-level split. |
| 3 | Final path for territory data — `backend/medieval_forge/data/regions/iberia_868/territory_data.py` vs repo-root `data/regions/iberia_868/territory_data.py`? | `backend/medieval_forge/data/regions/iberia_868/territory_data.py` | §2.c — Python package code belongs inside the package; `pip install -e .` ships it for free; relative imports stay clean. Repo-root would need extra `package-data` wiring. The 17 KB constants module is code, not data. |
| 4 | conftest layout — session vs function scope? | Session scope for `pipeline_output` (one ~45 s pipeline run for all 12 tests); function scope for any temp paths created per-test. | §5.a + §5.c — function scope re-runs the pipeline 12× per test session; CI would take 9 minutes instead of 45 s. |
| 5 | Single-test vs split-test parity layout? | 12 parametrised tests sharing the session fixture (effectively 3 parametrised test functions: `test_lookup_png_byte_equal`, `test_visual_png_ssim`, `test_json_deep_equal`, with 3+4+5 cases). | §5.b — single test surfaces only the first failure; 12 narrow tests report all mismatches in one CI run. CONTEXT.md states "preference: shared session fixture" — confirmed. |
| 6 | When in the phase the `pytest-parity` job flips to non-skippable? | Last commit of the phase, after fixtures + parity test + local green observation. | §7 — flipping earlier turns every in-flight port commit's parity into a gate; flipping last lets port iteration run as amber-yellow without blocking the phase's own merges. |

**Resolved during research (not in CONTEXT.md but surfaced):**

| # | Question | Answer | Evidence |
|---|----------|--------|----------|
| 7 | Are `terrain_lookup.png` + `terrain_types.json` part of Phase 01 parity? | **No — defer to Phase 06.** | Pitfall P-2: inicio's `generate_maps` does NOT produce them; only v1's `lib/map_generator.py` does. Verbatim port (D-01) means the port doesn't produce them either. The deployed Reconquista files exist (probably from v1) but reproducing them requires porting code beyond inicio — violates D-01. Phase 06 (export validation gate) is the right home. |
| 8 | Should the port reproduce the missing-`original_idx` bug from inicio (Nájera bug, P-1) or fix it? | **Verify deployed file shape during Wave 0; whichever the deployed file has, the port emits.** D-09 says "deployed wins" if inicio drifts. If deployed has `original_idx`, the port adds it (a deviation from D-01 verbatim, justified by D-09). If deployed lacks it, the port ships without (and the Nájera bug is a Phase 06 gate concern). | Pitfall P-1: there's a contradiction between inicio's silence and CLAUDE.md rule #4. D-09 resolves it — deployed wins. The verification is a 5-line jq script. |
| 9 | Confirmed-delete v1 file list (final per D-06)? | 5 production files + 7 test files. See §3.a + §3.c. | §3 — import-graph trace shows that several CONTEXT.md "candidates" actually survive (`voronoi.py`, `territory_builder.py`, `territories_geojson.py`) because `api/edit.py` imports them. CONTEXT.md flagged the trace as a planning task; here it is. |
| 10 | `draw_names=True` or `False` for parity? | Verify against deployed `visual_condado.png` during Wave 0 by spot-checking a known condado label position. | §2.a row `draw_names`: inicio's main block uses `True`; v1 wrapper uses `False`. Deployed file determines. |
| 11 | Where does the ES TopoJSON come from? | `npm pack es-atlas` → extract `package/es/municipalities.json`, OR direct download from `github.com/martgnz/es-atlas/raw/master/data/es/municipalities.json`. | §4.b — file is not in either repo; this is a Wave 0 plan-task. |
| 12 | LFS for the 28 MB PT GeoJSON? | Recommend YES; total fixture footprint stays under 2 MB without it. | §4.b — GitHub soft-warns at 50 MB but recommendation kicks in at 5 MB+; LFS is preference, not requirement. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The deployed `terrain_lookup.png` was produced by v1 (`lib/map_generator.py`), not inicio. | Pitfall P-2 / Open Q7 | If wrong, inicio's pipeline produces it via some path I missed. Mitigation: verify by running the port and checking whether `terrain_lookup.png` is emitted; if yes, the test re-enables. Cheap to recover from. |
| A2 | The deployed `territory_metadata.json` lacks `original_idx` (matching inicio's silence). | Pitfall P-1 / Open Q8 | If wrong, port-as-verbatim produces a parity test failure on `territory_metadata.json` deep-equal. Mitigation: the parity test failure points planning at the gap; add `original_idx` emission in `export.py` (a justified D-01 deviation per D-09). |
| A3 | `npm pack es-atlas` v0.6.x ships `package/es/municipalities.json` exactly as inicio expects. | Environment availability | If wrong (file path moved, schema changed), `decode_topojson_municipalities` fails. Mitigation: pinning npm version via `package.json` snapshot, or direct GitHub raw download URL with commit SHA. |
| A4 | Reconquista's `Assets/StreamingAssets/Maps/` is byte-identical to what's deployed in the shipping game (i.e. these are the unmodified outputs of the last successful pipeline run). | D-09 / fixture provisioning | If wrong (e.g. someone hand-edited a PNG post-generation), the parity test asserts against an inconsistent baseline. Mitigation: D-10's "explicit baseline-refresh commit" workflow lets the team regenerate-and-recommit when needed. |
| A5 | `np.random.default_rng(42)` produces deterministic output across numpy 1.26+ and 2.x (the version range in pyproject). | Pitfall P-9 / determinism | numpy guarantees Generator output stability across versions for fixed seed since the v1.17 PCG64 spec; this is verified historically. Risk: low. Mitigation: if numpy ever breaks, pin via `numpy<2` extra. |

## Sources

### Primary (HIGH confidence — direct file inspection)
- `inicio/map_generator.py` lines 1-944 — gold-standard algorithm, every section read in full.
- `inicio/territory_data_v3.py` lines 1-80 — KINGDOMS/DUCHIES/CONDADOS shape verified.
- `inicio/licoes/JORNADA_CRIACAO_MAPA.md` lines 1-771 — pitfalls + decisions catalogued.
- `inicio/licoes/MAPA_V3_PIXEL_LOOKUP_BRIEFING.md` lines 1-849 — pixel-lookup contract verified.
- `D:\Projetos_Jogo\Reconquista\Assets\StreamingAssets\Maps\` — `ls -la` confirms 11 of 12 contract files exist + sizes (terrain_lookup.png is the 12th — present, 23 KB).
- `D:\Projetos_Jogo\Reconquista\Assets\Downloads\handoff\pt_concelhos_wgs84.geojson` — 29.7 MB, exists.
- `backend/medieval_forge/services/generator.py` lines 1-391 — `sys.modules` patching confirmed (lines 79-126); `RegionConfig.__dataclass_fields__` usage at line 210.
- `backend/medieval_forge/api/generate.py` lines 1-270 — sole consumer of `services/generator`.
- `backend/medieval_forge/services/paths.py` — survives, used by 11+ files.
- `backend/medieval_forge/main.py` — registration sites for `api/generate` at lines 50 + 61.
- `backend/medieval_forge/lib/map_generator.py` — 1094 lines (drifted from inicio's 944); confirmed `iberia_config` references npm `es-atlas-pkg`.
- `pyproject.toml` — pytest `parity` marker registered (line 73); deps confirmed.
- `.github/workflows/ci.yml` lines 26-40 — `pytest-parity` job placeholder.
- `.planning/PROJECT.md` — D-V3-01..07.
- `.planning/ROADMAP.md` — Phase 01 success criteria.
- `.planning/quick/260507-g1v-phase-00-v3-archive-milestone-reset/V1_DELETION_CANDIDATES.md` — candidate table.
- `.planning/v1-archive/STATE.md` — 30+ pitfalls history.
- `CLAUDE.md` — 7 non-negotiable rules + 12-file contract + "What v3 explicitly is NOT".

### Secondary (MEDIUM confidence — derived/cross-referenced)
- Import-graph trace via Grep over `backend/` — confirms `voronoi.py`, `territories_geojson.py`, `territory_builder.py` survive (consumers in `api/edit.py`).
- pytest fixture-scope behaviour (https://docs.pytest.org/en/stable/how-to/fixtures.html) — used in §5.a.
- skimage SSIM API (https://scikit-image.org/docs/stable/api/skimage.metrics.html#skimage.metrics.structural_similarity) — used in §5.b.

### Tertiary (LOW confidence — assumptions flagged in §Assumptions Log)
- Provenance of deployed `terrain_lookup.png` (A1).
- Shape of deployed `territory_metadata.json` (A2).
- npm `es-atlas` v0.6.x file layout (A3).

## Metadata

**Confidence breakdown:**
- Algorithm anatomy (§1): HIGH — every section line-checked against inicio source.
- RegionConfig contract (§2): HIGH — every field cross-checked with inicio + survival of fields confirmed via `services/generator.py:210` reading `__dataclass_fields__`.
- V1 deletion graph (§3): HIGH — import-graph trace via Grep is exhaustive across `backend/medieval_forge/`.
- Fixture provisioning (§4): HIGH (Reconquista files), MEDIUM (ES TopoJSON path — verified npm package name and GitHub URL but didn't actually fetch and inspect).
- Parity harness (§5): HIGH — pytest + skimage idioms are standard.
- Pitfalls (§6): HIGH — 16 pitfalls catalogued from inicio's lessons file with line references.
- CI flip plan (§7): HIGH — sequencing decision is grounded in atomic-commit invariant.
- Validation Architecture (§8): HIGH — coverage map is exhaustive against the 12-file contract minus the 2 deferred.
- Open questions (§9): MEDIUM — answers are recommendations; decisions stand if no contradictory evidence emerges in Wave 0.

**Research date:** 2026-05-07
**Valid until:** Wave 0 of Phase 01 — once the port begins, this research becomes a snapshot reference. Re-research if Phase 01 is deferred more than 60 days (numpy 2.x might land between, scipy too).

## RESEARCH COMPLETE
