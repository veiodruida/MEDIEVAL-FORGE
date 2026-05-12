# Phase 05: Region generalization - Research

**Researched:** 2026-05-12
**Domain:** Config externalization (Python @dataclass → YAML), pydantic v2 schema mirroring, Alembic column add, FastAPI listing endpoint, Radix modal/select, scipy Voronoi-from-grid
**Confidence:** HIGH (most claims verified directly against repo source; PyYAML dep gap + missing v3 projects route are the only material gotchas)

## Summary

Phase 05 externalizes the hard-coded `iberia_config()` factory into per-region YAML packs loaded by a single `load_region(key)` API, then ships two template regions (France 1066 with toy synthetic data; England 1216 YAML-only). 17 implementation decisions (D-01..D-17) are locked in CONTEXT.md and constrain the entire phase — research is therefore prescriptive, not exploratory.

The pipeline already tolerates the two riskiest empty-input paths cleanly: empty `border_polygon` short-circuits to an all-False mask in `border.py:21-22`, and empty `mountains`/`rivers` dicts are guarded with early returns in `render.py:207,248`. Combined with empty `pt_duchies`, France/England fall through to a single global KD-tree on the ES branch without any code changes to `voronoi.py` / `border.py` / `render.py` — D-04's "verify or add a guard" verification resolves to "verify only."

Two material gotchas the planner must surface:

1. **`PyYAML` is missing from `pyproject.toml` dependencies** — must be added in Plan 05-01.
2. **`POST /api/v3/projects` does not exist.** Only the v1 route `POST /projects` (in `api/projects.py:58`) exists, which uses `ProjectCreate` (in `schemas.py:32`). CONTEXT.md D-07 mentions the v3 route as if it existed; planner must decide between extending the v1 route or introducing a v3 projects router (Open Question 1 below).

**Primary recommendation:** Execute the 10-plan sequence in CONTEXT.md D-17 verbatim. The parity-gate-stays-green invariant is enforced by ordering, not by branching; planner may merge adjacent plans (05-09+05-10 are a natural pair) but cannot reorder.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**YAML schema + region pack layout**

- **D-01 (single-file region.yaml):** Each region is one YAML file at `data/regions/{key}.yaml` carrying ALL config (map_w/map_h, lon/lat bounds, kingdom_colors, all cleanup thresholds, border_polygon inline as `[lon, lat]` pairs, kingdoms/duchies/condados arrays). Geometry inputs (PT/ES GeoJSON, mountain_river_data.json) stay under `data/regions/{key}/inputs/`. One file = one region. No split files.
- **D-02 (pydantic schema validation):** New `RegionConfigSchema(BaseModel)` in `services/pipeline/region_loader.py` mirrors `RegionConfig` dataclass. Load order: `yaml.safe_load` → `RegionConfigSchema.model_validate` → convert to `RegionConfig(**model.model_dump())`. Pydantic v2 (already used elsewhere). Enforces `smooth_sigma ∈ [3.0, 4.5]` via `Field(ge=3.0, le=4.5)`.
- **D-03 (territory data — empty templates + autogenerate):** France/England YAML templates ship with `kingdoms: []`, `duchies: []`, `condados: []`. Pipeline detects empty arrays at the `voronoi`/`hierarchy` stage and autogenerates N synthetic condados from dataset feature centroids: `Condado_001`..`Condado_NNN`, assigned to a single default kingdom `unnamed` with gray color, deterministic via `rng_seed`. Iberia's populated YAML bypasses this path.
- **D-04 (border_polygon optional, default empty):** France/England YAMLs omit it (or set `border_polygon: []`). Empty list → single global KD-tree (no PT/ES routing). Multi-country routing schema NOT generalized in Phase 05.

**Region selection wire**

- **D-05 (Project.region_key column):** Alembic migration adds `region_key VARCHAR(64) NOT NULL DEFAULT 'iberia_868'` to `projects`. First-class column, not stuffed into `generator_config` JSON.
- **D-06 (GET /api/v3/regions endpoint):** New `api/v3/regions.py` module. Lists `data/regions/*.yaml`. Returns `{key, display_name, bounds: {lon_min, lon_max, lat_min, lat_max}, has_dataset: bool}` per entry. `has_dataset` true iff all dataset paths in the YAML resolve to existing files on disk.
- **D-07 (create-project modal with region dropdown):** New `NewProjectModal.tsx` with project name (text) + region (Radix `Select.Root` populated by `GET /api/v3/regions`). Default = `iberia_868`. Submit calls `POST /api/v3/projects` with `{name, region_key}`. `has_dataset: false` regions render disabled.
- **D-08 (bounds 100% per YAML):** Each YAML declares `lon_min`/`lon_max`/`lat_min`/`lat_max` explicitly. `lon_scale` still derived in `RegionConfig.__post_init__`. No auto-detect.

**France toy synthetic dataset**

- **D-09 (Voronoi-from-grid geometry):** Toy France municipalities = Voronoi cells from N=50 jittered grid points seeded with `rng_seed=42`. Clipped to France bbox. Uses `scipy.spatial.Voronoi` + `shapely`.
- **D-10 (~50 feature count):** N=50 → ~10-15 condados after cleanup; <5 s runtime.
- **D-11 (toy committed in inputs/):** Generator script `scripts/gen_toy_france.py` and its outputs (`france_municipalities_toy.geojson`, `mountain_river_data.json` stub) all committed.
- **D-12 (England 1216 YAML-only):** `england_1216.yaml` ships with bounds + empty territory arrays. No `inputs/` directory. `has_dataset: false`. Generate raises clear FileNotFoundError.

**Iberia migration + loader API**

- **D-13 (delete `iberia_config()` + `REGIONS` + `territory_data.py`):** After Plan 05-02 generates `iberia_868.yaml`, `regions.py` is **deleted**, and `territory_data.py` is **deleted**. All callsites (`api/v3/generate.py:39,130`; `api/v3/render.py:42,128,198`) migrate to `load_region(...)`. No transitional wrapper (per D-V3-04).
- **D-14 (hard parity gate test):** New `tests/parity/test_iberia_868_yaml.py` is non-skippable. `cfg = load_region('iberia_868')`, run `run_pipeline(cfg)`, compare every Phase 01 golden file (byte-equal lookup + SSIM ≥ 0.98 visual + structural-equal JSON).
- **D-15 (load_region API):** Module-level dict `_REGION_CACHE: dict[str, tuple[float, RegionConfig]]` keyed by `key`, holding `(file_mtime, cfg)`. Cache hit when YAML mtime unchanged. Cleared on explicit `clear_region_cache()`. Errors: `FileNotFoundError` for missing YAML; `pydantic.ValidationError` for schema violations; `FileNotFoundError` with explicit message for missing dataset paths.
- **D-16 (Alembic backfill):** Migration revision adds `region_key` with `server_default='iberia_868'` and `nullable=False`. Explicit UPDATE covers race rows. `models.py:Project` gains `region_key: Mapped[str]` field.
- **D-17 (script ordering — Plan sequencing constraint):** 10 plans in this order. **Plan 05-05 (deletion of iberia_config) cannot land before Plan 05-03 (YAML parity gate).** Parity gate must be green at every commit.

### Claude's Discretion

- voronoi.py empty `border_polygon` behavior (verify or add guard) — **RESOLVED: empty list falls through cleanly, no guard needed.** See "Empty-input behavior verification" below.
- Loader cache invalidation policy (mtime vs explicit-only) — **RECOMMENDATION: explicit-only.** Windows mtime resolution is 1s on FAT-derived FS / 100ns on NTFS but with caching that masks back-to-back edits in tests; mtime adds flake without value for a single-user local tool. See "Cache invalidation strategy" below.
- YAML structure for kingdoms/duchies/condados — **RECOMMENDATION: list-of-dicts with explicit `id` field** (matches CONTEXT.md hint; preserves order; reads cleanly).
- Autogenerate insertion point (D-03) — **RECOMMENDATION: loader-side synthesis.** Cleaner separation; pipeline branch stays Iberia-agnostic.
- France toy `mountain_river_data.json` shape — **CORRECTED: `{"mountains": {}, "rivers": {}}` (dict-of-dicts, not lists).** See "mountain_river_data.json shape correction" below.
- `api/v3/regions.py` HTTP shape — **RECOMMENDATION: nested bounds object** (cleaner JSON; matches other v3 responses' nested style).
- Create-project modal location — **RECOMMENDATION: new `NewProjectModal.tsx`.** Current `ProjectNew.tsx` (254 lines) entangles country/QID/period autocomplete logic; a new modal keeps Phase 05 scope contained.
- Path resolution — **RECOMMENDATION: YAML-relative.** `dataset.pt_geojson: inputs/pt.geojson` resolves against `{regions_dir}/{key}/`. Portable; one-line `(regions_dir / key / value).resolve()` in the loader.
- migrate script idempotency — **RECOMMENDATION: idempotent overwrite.** Development-friendly.
- Frontend coverage threshold — **RECOMMENDATION: representative tests** (≥80% in v3/ rule applies but isn't the same as 100%).
- `test_iberia_868.py` retirement — **RECOMMENDATION: retire after D-13 deletion.** D-14's YAML test covers everything.

### Deferred Ideas (OUT OF SCOPE)

- Historical research for France/England (names, kingdom_owners, historical_notes) → v3.1
- England 1216 toy dataset → v3.1
- Multi-country routing schema generalization → v3.1+
- User-uploaded region YAMLs at runtime → v3.1+
- DEM raster ingestion (slot reserved only)
- Bounds auto-detection
- LLM-assisted region creation → Phase 07
- `POST /api/v3/regions/validate` dry-run
- File-watcher hot-reload
- i18n region display_name
- France toy richness (climate, elevation, rivers)
- Cross-field pydantic validation
- Region schema versioning / migration

</user_constraints>

## Project Constraints (from CLAUDE.md)

Directives the planner MUST honor (extracted from `./CLAUDE.md`):

- **Determinism:** `np.random.default_rng(42)` is locked in `RegionConfig`. France toy generator MUST use `rng_seed=42` (D-09 + CLAUDE.md determinism rule).
- **Non-negotiable rule #2 (σ ∈ [3.0, 4.5]):** Pydantic schema MUST enforce `Field(ge=3.0, le=4.5)` on `smooth_sigma` (D-02).
- **Non-negotiable rule #3 (KD-trees per country):** Phase 05 does NOT generalize this; new regions get single global KD-tree via empty `border_polygon` (D-04).
- **Non-negotiable rule #4 (`original_idx` in every territory):** Autogen condados (D-03) must each carry `original_idx`. The Nájera bug surfaces if any synthesized condado lacks it.
- **No `sys.modules` patching / no `importlib.reload`:** Module-level `_REGION_CACHE` dict is the cache; loader never re-imports anything.
- **`RegionConfig` is the only mutable input:** Loader MUST return `RegionConfig`, nothing else. No new shape.
- **No LLM in the geometric path:** Phase 05 is geometry-only. Autogen uses deterministic colors + `rng_seed`.
- **Atomic commits per task:** Each plan ≤ 1 commit; `type(05-NN): subject` convention.
- **Three-layer test pyramid:** Unit (loader/schema/autogen) + parity (D-14) + UAT (Playwright France create-project). Backend ≥85% in v3/, frontend ≥80% in v3/.

<phase_requirements>
## Phase Requirements

No `REQ-IDs` were mapped to this phase. ROADMAP Phase 05 success criteria are SC-1/SC-2/SC-3:

| ID | Description | Research Support |
|----|-------------|------------------|
| SC-1 | `data/regions/iberia_868.yaml` externalizes the config currently in code | Plans 05-01..05-05 — migration script (Plan 05-02) generates the YAML; D-14 parity test (Plan 05-03) proves equivalence; deletion (Plan 05-05) removes the legacy path. Source schema: `regions.py:iberia_config()` (lines 39-82). |
| SC-2 | `france_1066.yaml` + `england_1216.yaml` ship as templates (geometry only) | Plans 05-06 (France toy) + 05-09 (England YAML-only). Bounds verified per CONTEXT.md D-08 (France ≈ `lon: [-5, 8], lat: [42, 51]`; England ≈ `lon: [-6, 2], lat: [49.5, 56]`). |
| SC-3 | France 1066 with toy synthetic dataset → ingest → generate → export produces 12 well-formed files (contract, NOT pixel parity) | Plan 05-10 — full pipeline E2E test. Pipeline already produces 14 outputs in Iberia; 12 of these are the Unity contract (`CLAUDE.md §v3 Pipeline Contract`). Assert file presence + dimensions + JSON schema, NOT pixel content. |

</phase_requirements>

## Standard Stack

### Core

| Library | Version (verified in pyproject.toml) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | `>=2.7,<3.0` | YAML schema validation via `BaseModel` + `Field(ge=, le=)` | Already used in `api/v3/render.py:55-71` (CfgOverrides), `schemas.py` (ProjectCreate); same pattern. |
| **PyYAML** | **NOT IN pyproject.toml — MUST BE ADDED** | YAML parsing via `yaml.safe_load` | Standard for human-edited config; `safe_load` rejects arbitrary tags (no `!!python/object` RCE). Recommended pin: `PyYAML>=6.0,<7.0`. |
| Alembic | `>=1.13,<2.0` | DB migration for `region_key` column | Already in use; existing pattern in `alembic/versions/0002_widen_country_qid_multi_country.py`. |
| SQLAlchemy | `>=2.0,<2.1` | ORM column add via `Mapped[str]` | Existing `models.py:Project` style. |
| scipy.spatial.Voronoi | `>=1.13,<2.0` | France toy: Voronoi cells from jittered grid | Already used in `voronoi.py:18` (cKDTree); pattern reused for the toy generator. |
| shapely | `>=2.0,<3.0` | Clip Voronoi cells to France bbox | Already in deps; `shapely.geometry.Polygon.intersection(bbox)` is the canonical clip. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| FastAPI | `>=0.115,<0.140` | `GET /api/v3/regions` endpoint | Existing v3 router pattern (`api/v3/__init__.py` exports routers). |
| React 19 + Radix Themes 3.x | (frontend) | Modal (`Dialog.Root`) + dropdown (`Select.Root`) | Already used in canvas components per Phase 03/04 context. |
| TanStack Query v5 | (frontend) | `useRegions` hook — caches `GET /api/v3/regions` per session | Existing pattern: `useArtifacts`/`useStatus` in frontend. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyYAML | `ruamel.yaml` | Preserves comments + round-trips. Useful if pipeline ever writes YAML back; not needed Phase 05. |
| pydantic mirror | Convert dataclass to pydantic outright | Larger blast radius — `RegionConfig` is consumed in 11 pipeline submodules + multiple tests. CONTEXT.md D-02 mirroring path is correct. |
| Voronoi-from-grid | Hex grid / uniform squares | Less realistic; exercises fewer code paths. D-09 picks Voronoi for fidelity to the real Iberia path. |
| Module-level cache dict | `functools.lru_cache` | Can't invalidate by key easily; mtime check requires manual logic anyway. D-15 dict is cleaner. |

**Installation (planner must run in Plan 05-01):**
```bash
# Add to pyproject.toml dependencies:
#   "PyYAML>=6.0,<7.0",
pip install -e .
```

**Version verification:** PyYAML 6.0.2 is current as of late 2024 [ASSUMED — verify via `pip index versions pyyaml` before pinning]. Pydantic 2.7+ is locked in repo and supports all needed features (`Field(ge=, le=)`, `model_validate`, `model_dump`, `model_config = {"extra": "forbid"}`).

## Architecture Patterns

### Recommended Project Structure

```
data/regions/
├── iberia_868.yaml                       # ✅ NEW — migrated from regions.py + territory_data.py
├── iberia_868/inputs/                    # unchanged
│   ├── pt_concelhos_wgs84.geojson
│   ├── es-atlas-pkg/...
│   └── mountain_river_data.json
├── france_1066.yaml                      # ✅ NEW — toy template
├── france_1066/inputs/                   # ✅ NEW
│   ├── france_municipalities_toy.geojson # generated by scripts/gen_toy_france.py
│   └── mountain_river_data.json          # stub: {"mountains": {}, "rivers": {}}
└── england_1216.yaml                     # ✅ NEW — YAML-only, no inputs/

backend/medieval_forge/services/pipeline/
├── region_loader.py                      # ✅ NEW
├── regions.py                            # ❌ DELETED in Plan 05-05
├── contracts.py                          # unchanged (RegionConfig + ProjectDataset)
├── voronoi.py                            # unchanged (empty border_polygon already works)
├── border.py                             # unchanged
├── render.py                             # unchanged (already guards empty dicts)
└── ...

backend/medieval_forge/data/regions/iberia_868/
└── territory_data.py                     # ❌ DELETED in Plan 05-05

backend/medieval_forge/api/v3/
├── regions.py                            # ✅ NEW — GET /api/v3/regions
├── generate.py                           # MODIFIED: line 39 import + line 130 call
└── render.py                             # MODIFIED: lines 42, 128, 198

alembic/versions/
└── 0004_add_project_region_key.py        # ✅ NEW

scripts/
├── migrate_iberia_to_yaml.py             # ✅ NEW — one-shot
└── gen_toy_france.py                     # ✅ NEW — one-shot, deterministic

frontend/src/components/projects/
├── NewProjectModal.tsx                   # ✅ NEW
└── __tests__/NewProjectModal.test.tsx
frontend/src/api/
└── useRegions.ts                         # ✅ NEW

tests/
├── unit/test_region_loader.py            # ✅ NEW
├── parity/test_iberia_868_yaml.py        # ✅ NEW (hard gate)
└── e2e/test_france_1066_export.py        # ✅ NEW (SC-3)
```

### Pattern 1: Pydantic v2 mirror of a dataclass

`RegionConfig` stays a `@dataclass` (CLAUDE.md / Phase 01 decision). Pydantic `RegionConfigSchema` mirrors the *shape* for validation only, then we round-trip into the dataclass.

```python
# region_loader.py
from pydantic import BaseModel, Field
from typing import Optional
import yaml

class BoundsBlock(BaseModel):
    lon_min: float
    lon_max: float
    lat_min: float
    lat_max: float

class DatasetBlock(BaseModel):
    pt_geojson: Optional[str] = None
    es_input: Optional[str] = None
    mountain_river_json: Optional[str] = None
    dem_raster: Optional[str] = None
    # Note: paths are strings in YAML, resolved to Path objects after model_dump

class CondadoBlock(BaseModel):
    id: str
    name: str
    lon: float
    lat: float
    duchy: str
    baronies: list[dict]   # [{name, lon, lat}, ...]

class DuchyBlock(BaseModel):
    id: str
    kingdom: str
    name: str

class KingdomBlock(BaseModel):
    id: str
    name: str
    color: list[int] = Field(min_length=3, max_length=3)  # RGB triplet

class RegionConfigSchema(BaseModel):
    model_config = {"extra": "forbid"}  # ASVS V5

    # Identification
    key: str
    display_name: str
    name: str   # internal "iberia" / "france" — maps to RegionConfig.name

    # Dimensions
    map_w: int = 1920
    map_h: int = 1080
    upscale: int = 2

    # Bounds (flat for direct mapping to RegionConfig fields)
    lon_min: float
    lon_max: float
    lat_min: float
    lat_max: float

    # Dataset (paths YAML-relative; resolved post-validation)
    dataset: DatasetBlock = Field(default_factory=DatasetBlock)

    # PT/ES routing (Iberia only; empty elsewhere)
    border_polygon: list[list[float]] = Field(default_factory=list)
    pt_duchies: list[str] = Field(default_factory=list)

    # Rendering / cleanup thresholds
    kingdom_colors: dict[int, list[int]] = Field(default_factory=dict)
    island_min_px: int = 300
    fragment_min_px: int = 600
    blob_merge_px: int = 200
    median_passes: int = 8
    smooth_sigma: float = Field(default=3.0, ge=3.0, le=4.5)  # CLAUDE.md rule #2

    # Territory data (empty = autogen — D-03)
    kingdoms: list[KingdomBlock] = Field(default_factory=list)
    duchies: list[DuchyBlock] = Field(default_factory=list)
    condados: list[CondadoBlock] = Field(default_factory=list)

    # Determinism + draw control
    rng_seed: int = 42
    draw_names: bool = False
```

```python
# Loader entry point
_REGION_CACHE: dict[str, tuple[float, RegionConfig]] = {}

def load_region(key: str, regions_dir: Path | None = None) -> RegionConfig:
    """Load and validate a region YAML; cache by key.

    Errors:
      FileNotFoundError       — missing YAML or missing dataset path
      pydantic.ValidationError — schema violation (field path + reason)
    """
    if regions_dir is None:
        # Mirror regions.py:_INPUTS_DIR anchor — parents[4] from this file.
        regions_dir = Path(__file__).resolve().parents[4] / "data" / "regions"

    yaml_path = regions_dir / f"{key}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"region YAML not found: {yaml_path}")

    # Cache check — recommended: explicit-only (no mtime).
    # See "Cache invalidation strategy" for rationale.
    if key in _REGION_CACHE:
        return _REGION_CACHE[key][1]

    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    schema = RegionConfigSchema.model_validate(raw)

    # Resolve dataset paths YAML-relative to {regions_dir}/{key}/
    region_root = regions_dir / key
    dataset = _build_dataset(schema.dataset, region_root)

    # Convert kingdoms/duchies/condados from list-of-dicts → the in-memory
    # shapes expected by voronoi.py / build_hierarchy_maps:
    #   KINGDOMS: dict[id, display_name]
    #   DUCHIES:  dict[id, (kingdom_id, display_name)]
    #   CONDADOS: list[tuple(id, name, lon, lat, duchy_id, [(barony, lon, lat)])]
    kingdoms, duchies, condados, kingdom_colors = _convert_territory_data(schema)

    # Autogen if empty (D-03) — loader-side per recommendation
    if not condados:
        kingdoms, duchies, condados, kingdom_colors = _autogen_from_dataset(
            dataset, schema.rng_seed
        )

    cfg = RegionConfig(
        name=schema.name,
        map_w=schema.map_w, map_h=schema.map_h, upscale=schema.upscale,
        lon_min=schema.lon_min, lon_max=schema.lon_max,
        lat_min=schema.lat_min, lat_max=schema.lat_max,
        border_polygon=[(p[0], p[1]) for p in schema.border_polygon],
        pt_duchies=set(schema.pt_duchies),
        kingdom_colors={int(k): tuple(v) for k, v in (kingdom_colors or schema.kingdom_colors).items()},
        island_min_px=schema.island_min_px,
        fragment_min_px=schema.fragment_min_px,
        blob_merge_px=schema.blob_merge_px,
        median_passes=schema.median_passes,
        smooth_sigma=schema.smooth_sigma,
        kingdoms=kingdoms,
        duchies=duchies,
        condados=condados,
        rng_seed=schema.rng_seed,
        draw_names=schema.draw_names,
        dataset=dataset,
    )
    # __post_init__ fires here and computes lon_scale — verified by reading
    # contracts.py:133-136 (standard dataclass behavior).

    _REGION_CACHE[key] = (yaml_path.stat().st_mtime, cfg)
    return cfg


def clear_region_cache() -> None:
    """Used by tests (fixtures) and a future /admin reload endpoint."""
    _REGION_CACHE.clear()
```

### Pattern 2: Alembic column add (SQLite-compatible)

Follow `alembic/versions/0002_widen_country_qid_multi_country.py` — uses `op.batch_alter_table` (required for SQLite `ALTER` operations).

```python
# alembic/versions/0004_add_project_region_key.py
"""add region_key to projects (Phase 05 D-05/D-16)"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"  # current head per existing files (0003_create_codex_cache)
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.add_column(
            sa.Column(
                "region_key",
                sa.String(length=64),
                nullable=False,
                server_default="iberia_868",
            )
        )
    # Explicit backfill — covers any rows inserted between column-add and now.
    op.execute("UPDATE projects SET region_key = 'iberia_868' WHERE region_key IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("region_key")
```

Add to `models.py:Project`:
```python
region_key: Mapped[str] = mapped_column(
    String(64), nullable=False, default="iberia_868", server_default="iberia_868"
)
```

### Pattern 3: FastAPI listing endpoint

```python
# api/v3/regions.py
from fastapi import APIRouter
from pathlib import Path
import yaml

router = APIRouter(prefix="/v3/regions", tags=["v3-regions"])

_REGIONS_DIR = Path(__file__).resolve().parents[3] / "data" / "regions"
# Anchor: api/v3/regions.py → parents[3] = repo root. Verify in plan.


@router.get("")
async def list_regions() -> list[dict]:
    """List available region YAMLs with bounds and dataset availability."""
    results: list[dict] = []
    for yaml_path in sorted(_REGIONS_DIR.glob("*.yaml")):
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        key = yaml_path.stem
        region_root = _REGIONS_DIR / key

        has_dataset = True
        for field in ("pt_geojson", "es_input", "mountain_river_json"):
            rel = (raw.get("dataset") or {}).get(field)
            if rel is None:
                has_dataset = False
                break
            if not (region_root / rel).exists():
                has_dataset = False
                break

        results.append({
            "key": key,
            "display_name": raw.get("display_name", key),
            "bounds": {
                "lon_min": raw["lon_min"],
                "lon_max": raw["lon_max"],
                "lat_min": raw["lat_min"],
                "lat_max": raw["lat_max"],
            },
            "has_dataset": has_dataset,
        })
    return results
```

### Pattern 4: Voronoi-from-grid (France toy)

```python
# scripts/gen_toy_france.py
import json
import numpy as np
from pathlib import Path
from scipy.spatial import Voronoi
from shapely.geometry import Polygon, box

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "regions" / "france_1066" / "inputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

LON_MIN, LON_MAX = -5.0, 8.0
LAT_MIN, LAT_MAX = 42.0, 51.0
N = 50
SEED = 42

rng = np.random.default_rng(SEED)
# Jittered grid: roughly sqrt(N) per axis, then jitter into the cell
n_side = int(np.ceil(np.sqrt(N)))
xs = np.linspace(LON_MIN, LON_MAX, n_side + 2)[1:-1]
ys = np.linspace(LAT_MIN, LAT_MAX, n_side + 2)[1:-1]
xx, yy = np.meshgrid(xs, ys)
points = np.column_stack([xx.ravel(), yy.ravel()])[:N]
jitter_x = (LON_MAX - LON_MIN) / n_side * 0.3
jitter_y = (LAT_MAX - LAT_MIN) / n_side * 0.3
points += rng.uniform(-1, 1, size=points.shape) * np.array([jitter_x, jitter_y])

# Voronoi + clip to France bbox
vor = Voronoi(points)
bbox = box(LON_MIN, LAT_MIN, LON_MAX, LAT_MAX)

features = []
for i, region_idx in enumerate(vor.point_region):
    region = vor.regions[region_idx]
    if -1 in region or not region:
        # Edge cells are infinite — clip the convex hull of the seed point
        # against bbox using a large neighborhood polygon. Simpler approach:
        # build polygon from nearby seeds. For determinism, use voronoi_finite
        # helper or skip and rely on bbox clipping of an over-sized polygon.
        continue   # planner can extend with the infinite-region handler
    poly_coords = [vor.vertices[v].tolist() for v in region]
    poly = Polygon(poly_coords)
    clipped = poly.intersection(bbox)
    if clipped.is_empty or clipped.geom_type not in ("Polygon", "MultiPolygon"):
        continue
    geom = clipped if clipped.geom_type == "MultiPolygon" else clipped
    coords = [list(geom.exterior.coords)] if geom.geom_type == "Polygon" else [list(p.exterior.coords) for p in geom.geoms]
    features.append({
        "type": "Feature",
        "id": f"fr_toy_{i:03d}",
        "properties": {"name": f"Municipality_{i:03d}"},
        "geometry": {"type": "Polygon", "coordinates": coords[:1]}   # single ring
    })

(OUT_DIR / "france_municipalities_toy.geojson").write_text(
    json.dumps({"type": "FeatureCollection", "features": features}, indent=2),
    encoding="utf-8"
)
(OUT_DIR / "mountain_river_data.json").write_text(
    json.dumps({"mountains": {}, "rivers": {}}, indent=2),
    encoding="utf-8"
)
print(f"Generated {len(features)} features")
```

**Note on infinite Voronoi regions:** `scipy.spatial.Voronoi` returns `-1` for unbounded regions at the convex hull. Edge cells will be dropped under the naive `continue` above (~6-10 of 50). For the toy SC-3 contract test (file presence + dimensions), this is acceptable. If the planner wants all 50 cells, use the standard `voronoi_finite_polygons_2d` helper (well-known scipy cookbook recipe).

### Anti-Patterns to Avoid

- **Mutating cached `RegionConfig`:** Loader returns a *shared* object via cache. Render endpoint already builds fresh per call (`api/v3/render.py:128` does `cfg = iberia_config(); cfg.output_dir = ...`). Phase 05 must preserve this — set `cfg.output_dir` / `cfg.stop_event` / `cfg.on_stage` on the loaded object knowing it's the cached singleton. *Recommendation: shallow-copy in the consumer (`render.py`/`generate.py`) via `dataclasses.replace(cfg, ...)`* — flag for planner to confirm.
- **YAML-relative input paths assumed but documented otherwise:** Pick YAML-relative consistently. Don't allow both styles.
- **`yaml.load` without `safe_load`:** Allows arbitrary Python object construction (RCE). Always `yaml.safe_load`.
- **Pydantic `extra="allow"`:** Set `model_config = {"extra": "forbid"}` to catch typos in YAML keys early.
- **Backfilling via `default=` only on the Mapped column:** SQLite needs `server_default` for the migration to populate existing rows in the same transaction.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML parsing | Custom parser | `yaml.safe_load` (PyYAML) | Quoting rules, anchors, !!tags, multi-doc edge cases — PyYAML handles all. |
| Schema validation | Manual `isinstance` checks | `pydantic.BaseModel` + `Field(ge=, le=)` | Structured error paths, JSON schema export, free coercion. Already used elsewhere. |
| Path resolution | Manual string concat | `pathlib.Path.resolve()` | Cross-platform; symlink handling. |
| Voronoi clipping | Manual polygon intersection | `shapely.Polygon.intersection(bbox)` | Handles MultiPolygon, degenerate cases, holes. Already in deps. |
| DB migration | Raw SQL in app startup | Alembic revision | Reversible; tracked in version table; existing pattern (0001-0003). |
| List file in directory + filter | Manual `os.listdir` + extension check | `Path.glob("*.yaml")` | Simpler; consistent with rest of codebase. |
| Frontend modal | Custom div + portal | Radix `Dialog.Root` | Already used in canvas; ARIA-correct; focus trap. |
| Frontend dropdown | Custom `<select>` | Radix `Select.Root` | Keyboard nav; styled consistently with rest of app. |

**Key insight:** Phase 05 is almost entirely composition of existing well-supported libraries. The custom code (autogen condados, France Voronoi generator) is small, one-shot, and isolated.

## Common Pitfalls

### Pitfall 1: PyYAML missing from dependencies [VERIFIED]
**What goes wrong:** `import yaml` fails at runtime. Plan 05-01 tests pass in dev environments where PyYAML is incidentally installed, fail on fresh CI.
**Why it happens:** PyYAML not in `pyproject.toml` deps list (verified by grepping the file).
**How to avoid:** Add `"PyYAML>=6.0,<7.0"` to `pyproject.toml` deps in Plan 05-01's FIRST commit, BEFORE writing the loader.
**Warning signs:** `ModuleNotFoundError: No module named 'yaml'` in CI but not locally.

### Pitfall 2: `mountain_river_data.json` shape is dict-of-dicts, not lists [VERIFIED]
**What goes wrong:** Stubbing with `{"mountains": [], "rivers": []}` causes `data.get('mountains', {}).items()` (in `render.py:214,257`) to raise `AttributeError: 'list' object has no attribute 'items'`.
**Why it happens:** CONTEXT.md Discretion mentioned empty-array stub; actual shape (verified by reading `data/regions/iberia_868/inputs/mountain_river_data.json` and `render.py`) is dict-of-dicts: `{"mountains": {key: {name, peak, polygon}}, "rivers": {key: {...}}}`.
**How to avoid:** France stub must be `{"mountains": {}, "rivers": {}}`. The `if not mountains: return` guard at `render.py:207` makes empty dict safe.
**Warning signs:** AttributeError on `.items()` in `render_mountains`/`render_rivers`.

### Pitfall 3: `CONDADOS` are positional tuples, not dicts [VERIFIED]
**What goes wrong:** Migration script writes YAML as if `CONDADOS` were dicts; downstream `voronoi.py:setup_baronies` (line 46-55) expects positional tuples (`c[4]` = duchy_id, `c[5]` = barony list).
**Why it happens:** `territory_data.py:53` defines: `(condado_id, display_name, lon, lat, duchy_id, [(barony_name, lon, lat), ...])`. Mixed shape vs other registries.
**How to avoid:**
  - YAML target shape (canonical, list-of-dicts):
    ```yaml
    condados:
      - id: oviedo
        name: Oviedo
        lon: -5.84
        lat: 43.36
        duchy: d_asturias
        baronies:
          - {name: Oviedo, lon: -5.84, lat: 43.36}
          - {name: Grado, lon: -6.07, lat: 43.39}
    ```
  - Loader converts back to positional tuples for `voronoi.py`'s consumer signature.
**Warning signs:** `TypeError: tuple indices must be integers, not str` in `setup_baronies`.

### Pitfall 4: `POST /api/v3/projects` doesn't exist [VERIFIED]
**What goes wrong:** Frontend modal posts to non-existent route → 404.
**Why it happens:** Only `POST /projects` (v1) exists in `api/projects.py:58`, taking `ProjectCreate` (`schemas.py:32`). CONTEXT.md D-07 mentions v3 route as if it existed.
**How to avoid:** Planner must decide (see Open Question 1):
  - **Option A:** Extend v1 `ProjectCreate` schema to accept optional `region_key: str = "iberia_868"`, keep current route, frontend posts to `POST /projects`.
  - **Option B:** Introduce new v3 router `api/v3/projects.py` with a `POST /v3/projects` route. More code; cleaner separation.
**Recommendation:** Option A (cheaper; pre-existing route; `country_qid`+bbox legacy fields stay valid backstops while `region_key` becomes the new pivot).
**Warning signs:** Frontend submit → 404; Playwright UAT failing on project creation step.

### Pitfall 5: PT/ES routing accidentally re-engaged for non-Iberia regions [VERIFIED]
**What goes wrong:** A France YAML accidentally sets `pt_duchies: [d_foo]` → `bpt[i]` becomes True for some baronies → PT KD-tree built → routing assumes PT/ES split that doesn't exist → garbage assignments.
**Why it happens:** Schema doesn't enforce that `pt_duchies` is empty when `border_polygon` is empty.
**How to avoid:** Either (a) document the invariant in the schema docstring and trust YAML authors, or (b) add a pydantic `model_validator` enforcing `len(pt_duchies) == 0` when `len(border_polygon) == 0`. Recommend (a) for Phase 05 (CONTEXT.md defers cross-field validation to v3.1).
**Warning signs:** Non-Iberia region with weird half-empty barony assignments.

### Pitfall 6: Cache stale after YAML edit on Windows
**What goes wrong:** Edit `iberia_868.yaml`, server doesn't pick up change.
**Why it happens:** Module-level dict persists across requests; no auto-invalidate.
**How to avoid:** Explicit `clear_region_cache()` from test fixtures; document the limitation; add an admin reload endpoint if Game Designers need it (deferred).
**Warning signs:** Test author updates YAML but tests still see old cfg.

### Pitfall 7: Alembic env.py async lifecycle
**What goes wrong:** New migration revision id conflicts with existing chain.
**Why it happens:** Revisions 0001-0003 already exist (verified via `Glob`); new revision is `0004`.
**How to avoid:** `down_revision: str | None = "0003"`. `revision: str = "0004"`.
**Warning signs:** Alembic complaint about multiple heads or unreachable revision.

### Pitfall 8: `regions_dir` anchor wrong from new module
**What goes wrong:** `region_loader.py` uses `parents[4]` (correct from `services/pipeline/`); `api/v3/regions.py` would need `parents[3]` (from `api/v3/`).
**Why it happens:** Path anchor depends on file location.
**How to avoid:** Each module computes its own anchor; the `regions.py` pattern is the template.
**Warning signs:** FileNotFoundError on YAML at server start.

### Pitfall 9: `RegionConfig` is mutable singleton from cache
**What goes wrong:** `render.py:130` does `cfg.output_dir = ...` after `iberia_config()` returns a fresh object — *currently safe* because `iberia_config()` rebuilds every call. After Phase 05, `load_region('iberia_868')` returns the *cached* singleton; mutating `cfg.output_dir` would affect all subsequent callers.
**Why it happens:** Cache hit returns shared reference.
**How to avoid:**
  - **Option A (recommended):** Use `dataclasses.replace(cfg, output_dir=..., on_stage=..., stop_event=...)` in `render.py` / `generate.py` producers to make a shallow copy.
  - **Option B:** Loader returns a deep copy on every call (defeats most of the cache benefit; only schema-validation work is cached).
  - **Option C:** Loader returns the cached cfg AND a `lambda` to construct fresh overrides. More machinery.
**Warning signs:** Concurrent /render calls overwriting each other's `output_dir`; parity test passes single-threaded but fails under pytest-xdist.

### Pitfall 10: France toy Voronoi edge cells dropped
**What goes wrong:** ~6-10 of N=50 seeds land at the convex hull → infinite Voronoi region → naive `continue` drops them. Total feature count is ~40-44, not 50.
**Why it happens:** Standard scipy behavior; documented.
**How to avoid:** Acceptable for SC-3 (contract test, not pixel parity). If feature count matters, use the well-known `voronoi_finite_polygons_2d` cookbook helper.
**Warning signs:** Generator prints "Generated 42 features" instead of 50.

## Runtime State Inventory

This is a refactor + migration phase. Each category is answered explicitly:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `projects` rows in `medieval_forge.db` (SQLite, single-user local) lack `region_key` column. | Alembic migration `0004_add_project_region_key.py` adds column with `server_default='iberia_868'` + explicit UPDATE backfill (Plan 05-04). |
| Live service config | None — Medieval Forge has no n8n / Datadog / Tailscale / Cloudflare service config. Single-user local app. | None. |
| OS-registered state | None — `medieval-forge start` is a CLI; no Task Scheduler / launchd / systemd / pm2 registrations. | None. |
| Secrets/env vars | None — Phase 05 introduces no new env vars; no secrets reference the renamed thing. Existing LLM API keys (`ANTHROPIC_API_KEY` etc.) untouched. | None. |
| Build artifacts | After deleting `regions.py` + `territory_data.py`, `medieval_forge.egg-info/` and `__pycache__/` directories still reference them. | `pip install -e .` after deletion (Plan 05-05) refreshes egg-info; `__pycache__` auto-rebuilds. CI runs from clean checkout — no action there. |

**Test fixtures referencing `iberia_config`:** Verified via Grep — only `backend/tests/parity/test_iberia_868_live.py` + `backend/tests/integration/test_pipeline_cli_e2e.py` import from `regions.py`. Both must be migrated to `load_region('iberia_868')` in Plan 05-05.

## Code Examples

### Empty-input behavior verification [VERIFIED via reading source]

```python
# border.py:21-22
if not cfg.border_polygon:
    return mask   # all-False (h, w) bool array
```
→ Empty `border_polygon` → all-False border_mask.

```python
# voronoi.py:55, 65-68
bpt.append(did in cfg.pt_duchies)
# ...
pi = [i for i in range(nb) if bpt[i]]
ei = [i for i in range(nb) if not bpt[i]]
tp = cKDTree(bpx[pi]) if pi else None
te = cKDTree(bpx[ei]) if ei else None
```
→ Empty `pt_duchies` → all `bpt` are False → `pi=[]`, `tp=None`, all baronies in `ei` with `te` as the single global KD-tree.

```python
# voronoi.py:132-138 (fallback for unassigned land pixels)
ipt = border_mask[ys, xs]              # all False
if tp and np.any(ipt):                 # tp is None → skipped
    ...
if te and np.any(~ipt):                # ~ipt is all True → all pixels routed here
    _, idx = te.query(coords[~ipt])
    raw[ys[~ipt], xs[~ipt]] = np.array(ei)[idx].astype(np.int16)
```
→ All land pixels routed to the single global tree. **D-04 verified: no code change needed.**

### mountain_river_data.json shape correction [VERIFIED]

```python
# render.py:206-214
mountains = data.get('mountains', {})
if not mountains:
    return img   # empty dict safe — early return
# ...
for key, mtn in mountains.items():     # iterates dict
    polygon = mtn['polygon']
```
→ Stub MUST be `{"mountains": {}, "rivers": {}}` (empty dicts), NOT `{"mountains": [], "rivers": []}`.

### Iberia YAML target shape (Plan 05-02 migration script output)

```yaml
key: iberia_868
display_name: Iberia 868 AD
name: iberia

map_w: 1920
map_h: 1080
upscale: 2

lon_min: -13.2
lon_max: 8.2
lat_min: 35.4
lat_max: 44.6

dataset:
  pt_geojson: inputs/pt_concelhos_wgs84.geojson
  es_input: inputs/es-atlas-pkg/package/es/municipalities.json
  mountain_river_json: inputs/mountain_river_data.json

border_polygon:
  - [-9.50, 42.20]
  - [-8.85, 41.88]
  # ... 40 points total (verbatim from regions.py:62-72)

pt_duchies: [d_portucale, d_gharb, d_fronteira]

kingdom_colors:
  0: [190, 158, 82]    # Astúrias — gold
  1: [148, 88, 168]    # Pamplona — purple
  2: [198, 108, 128]   # Marca Hispânica — pink
  3: [68, 158, 62]     # Emirato — green

island_min_px: 300
fragment_min_px: 600
blob_merge_px: 200
median_passes: 8
smooth_sigma: 3.0

rng_seed: 42
draw_names: false

kingdoms:
  - {id: asturias, name: "Reino das Astúrias"}
  - {id: pamplona, name: "Reino de Pamplona"}
  - {id: marca_hispanica, name: "Marca Hispânica"}
  - {id: emirato, name: "Emirato de Córdoba"}

duchies:
  - {id: d_asturias, kingdom: asturias, name: "Ducado de Astúrias"}
  - {id: d_galiza, kingdom: asturias, name: "Ducado de Galiza"}
  # ... 26 duchies total

condados:
  - id: oviedo
    name: Oviedo
    lon: -5.84
    lat: 43.36
    duchy: d_asturias
    baronies:
      - {name: Oviedo, lon: -5.84, lat: 43.36}
      - {name: Grado, lon: -6.07, lat: 43.39}
      - {name: Siero, lon: -5.66, lat: 43.39}
      - {name: Mieres, lon: -5.77, lat: 43.25}
  # ... 92 condados total
```

### Callsite swap (Plan 05-04)

```python
# api/v3/generate.py — BEFORE
from ...services.pipeline.regions import iberia_config  # line 39
# ...
cfg = iberia_config()                                    # line 130

# AFTER
from ...services.pipeline.region_loader import load_region
from dataclasses import replace
# ...
project = await db.get(Project, project_id)             # already loaded above
base_cfg = load_region(project.region_key)
cfg = replace(
    base_cfg,
    output_dir=str(project_dir(project_id) / "output"),
    on_stage=_make_on_stage(queue, asyncio.get_running_loop()),
)
```

```python
# api/v3/render.py — BEFORE (lines 42, 128)
from ...services.pipeline.regions import iberia_config
# ...
cfg = iberia_config()
cfg.output_dir = str(project_dir(project_id) / "output")
cfg.stop_event = stop_event

# AFTER
from ...services.pipeline.region_loader import load_region
from dataclasses import replace
# Need project_id → project.region_key lookup; producer task currently doesn't
# pull the project row. Planner: either pass region_key into producer at scheduling
# time, or query the DB inside _render_producer.
base_cfg = load_region(region_key)  # resolved at endpoint, passed to producer
cfg = replace(
    base_cfg,
    output_dir=str(project_dir(project_id) / "output"),
    stop_event=stop_event,
)
# Subsequent override application (lines 133-135) stays identical:
for k, v in overrides.items():
    if v is not None:
        setattr(cfg, k, v)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `iberia_config()` factory + `REGIONS = {'iberia_868': iberia_config}` dict | `load_region(key)` reading YAML + `_REGION_CACHE` dict | Phase 05 | Single-region hard-code → N-region config-driven. |
| `territory_data.py` Python module | `data/regions/{key}.yaml` | Phase 05 | Code → data; editable without redeploy. |
| Implicit pydantic dependency in v3 routes | Explicit pydantic schema for region config | Phase 05 | Validates `smooth_sigma` etc. at load time, not at first pipeline use. |
| `POST /projects` (v1) with `country_qid` + bbox | TBD — extend with `region_key` or add v3 route (Open Q1) | Phase 05 | Decoupling region from country/period/bbox. |

**Deprecated/outdated:**
- `regions.py:iberia_config()` — deleted in Plan 05-05.
- `territory_data.py:KINGDOMS/DUCHIES/CONDADOS` — deleted in Plan 05-05.
- Sentinel pattern `REGIONS = {"iberia_868": iberia_config}` — replaced by directory listing.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | PyYAML 6.0.x is the current major version (planner verifies before pinning). | Standard Stack | Low — Plan 05-01 will `pip install` and lock the actual version. |
| A2 | England 1216 bounds `lon: [-6, 2], lat: [49.5, 56]` and France 1066 bounds `lon: [-5, 8], lat: [42, 51]` are accurate enough for a "geometry only" template. | Phase Requirements | Low — CONTEXT.md D-08 marks these as approximate; the contract test only asserts file presence + dimensions, not geographic accuracy. |
| A3 | `scripts/` is the right home for one-shot tooling. | Architecture | None — verified directory exists (`scripts/sync_territory_iberia.py`, `scripts/refresh_live_snapshot.py`). |
| A4 | The v3 router prefix convention `/v3/regions` (no trailing `/projects/`) is acceptable. | Pattern 3 | Low — existing v3 routers use `/v3/projects/{id}/...`; the new `regions` listing isn't project-scoped, so a different prefix is natural. Planner confirms in Plan 05-07. |

**All other claims** are verified against repo source files (regions.py, contracts.py, voronoi.py, border.py, render.py, schemas.py, projects.py, models.py, pyproject.toml, alembic/versions/, data/regions/iberia_868/inputs/mountain_river_data.json).

## Open Questions

1. **`POST /api/v3/projects` route — extend v1 or introduce v3?**
   - What we know: only `POST /projects` (v1) exists in `api/projects.py:58`; `ProjectCreate` (`schemas.py:32`) takes `country_qid`, period, bbox, generator_config — none of these are `region_key`.
   - What's unclear: CONTEXT.md D-07 says "Submit calls `POST /api/v3/projects` with `{name, region_key}`" — but no such v3 route exists.
   - Recommendation: extend `ProjectCreate` to accept optional `region_key: str = "iberia_868"`; keep `POST /projects`; document that legacy fields (`country_qid`, bbox) remain valid backstops. Cheaper than a new router; consistent with the gradual v3 migration pattern.
   - Decider: Planner with one ASK clarifying which path the user prefers.

2. **`dataclasses.replace` vs deep copy in render/generate producers.**
   - What we know: After Phase 05, `load_region(...)` returns a cached singleton; mutating fields (`output_dir`, `stop_event`, `on_stage`) on it is unsafe under concurrency.
   - Recommendation: use `dataclasses.replace(base_cfg, ...)` in producers. One-line, shallow, idiomatic.
   - Decider: Planner can pick at task-design time.

3. **Cancel `test_iberia_868.py` after Plan 05-05 — retire, rewrite, or keep both?**
   - What we know: `test_iberia_868.py` imports nothing from `regions.py` (verified — it uses fixtures `pipeline_output` and `golden_dir` from conftest); the conftest is what builds the pipeline.
   - Recommendation: rewrite the conftest to use `load_region('iberia_868')` (Plan 05-04), then `test_iberia_868.py` and `test_iberia_868_yaml.py` both pass through the YAML path. Keep both (defense in depth) OR retire `test_iberia_868.py` since they'd be functionally identical. Recommendation: retire after one CI cycle confirms equivalence.
   - Decider: Planner during Plan 05-05.

4. **Voronoi edge cell handling in France toy.**
   - What we know: scipy's `Voronoi` returns `-1` for unbounded regions; ~6-10 of 50 seeds will hit edges.
   - Recommendation: Drop edge cells (naive `continue`). SC-3 doesn't require exactly 50 features; "well-formed 12-file contract" only needs the pipeline to run.
   - Decider: Planner during Plan 05-06; can defer to a follow-up if needed.

## Environment Availability

Phase 05 introduces one new external dependency (PyYAML); everything else is already in deps.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PyYAML | Loader, regions endpoint, generators | ✗ | — | None — must be added to `pyproject.toml` |
| pydantic | Schema validation | ✓ | `>=2.7,<3.0` | — |
| scipy | France Voronoi generator | ✓ | `>=1.13,<2.0` | — |
| shapely | France bbox clipping | ✓ | `>=2.0,<3.0` | — |
| Alembic | DB migration | ✓ | `>=1.13,<2.0` | — |
| SQLAlchemy | ORM column add | ✓ | `>=2.0,<2.1` | — |
| FastAPI | New endpoint | ✓ | `>=0.115,<0.140` | — |
| Radix Themes (`Select.Root`, `Dialog.Root`) | New modal | ✓ | 3.x (per CLAUDE.md) | — |

**Missing dependencies with no fallback:**
- **PyYAML** — Plan 05-01 must add it to `pyproject.toml` before writing the loader. `pip install -e .` to install.

**Missing dependencies with fallback:**
- None.

## Validation Architecture

Per `.planning/config.json` workflow.nyquist_validation enabled (treated as true by default; no explicit `false`).

### Test Framework

| Property | Value |
|----------|-------|
| Backend framework | pytest 8.x + pytest-asyncio 0.23.x (per pyproject.toml dev extras) |
| Frontend framework | vitest (per existing `__tests__/*.test.tsx` files in frontend/src/components/) |
| E2E framework | Playwright (per existing UAT specs from Phase 04) |
| Config files | `pyproject.toml` (`[tool.pytest.ini_options]`), `vitest.config.ts`, `playwright.config.ts` |
| Quick run command | `pytest tests/unit/ -x --no-cov` (backend); `npm test -- --run` (frontend) |
| Full suite command | `pytest && npm test && npm run e2e` |

### Phase Requirements → Test Map

| SC | Behavior | Test Type | Automated Command | File Exists? |
|----|----------|-----------|-------------------|--------------|
| SC-1 (Iberia YAML) | `load_region('iberia_868')` produces identical RegionConfig to `iberia_config()` | unit | `pytest tests/unit/test_region_loader.py::test_iberia_load_equivalence -x` | ❌ Wave 0 |
| SC-1 (Iberia YAML) | Byte-equal lookup PNGs + SSIM ≥ 0.98 visuals vs golden | parity | `pytest tests/parity/test_iberia_868_yaml.py -x` | ❌ Wave 0 |
| SC-1 | Pydantic schema rejects `smooth_sigma=5.0` | unit | `pytest tests/unit/test_region_loader.py::test_smooth_sigma_out_of_range -x` | ❌ Wave 0 |
| SC-1 | Pydantic schema rejects unknown YAML key | unit | `pytest tests/unit/test_region_loader.py::test_extra_forbid -x` | ❌ Wave 0 |
| SC-1 | Loader cache returns same object on second call (no re-parse) | unit | `pytest tests/unit/test_region_loader.py::test_cache_hit -x` | ❌ Wave 0 |
| SC-1 | `clear_region_cache()` forces re-parse | unit | `pytest tests/unit/test_region_loader.py::test_cache_clear -x` | ❌ Wave 0 |
| SC-1 | `FileNotFoundError` raised for missing YAML | unit | `pytest tests/unit/test_region_loader.py::test_missing_yaml -x` | ❌ Wave 0 |
| SC-1 | `FileNotFoundError` raised for missing dataset path | unit | `pytest tests/unit/test_region_loader.py::test_missing_dataset_file -x` | ❌ Wave 0 |
| SC-1 | Autogen produces N condados from dataset centroids when condados=[] | unit | `pytest tests/unit/test_region_loader.py::test_autogen_when_empty -x` | ❌ Wave 0 |
| SC-2 | `GET /api/v3/regions` returns all three (iberia, france, england) with correct has_dataset | integration | `pytest tests/integration/test_regions_endpoint.py -x` | ❌ Wave 0 |
| SC-2 | England 1216 has `has_dataset: false`; generate raises clear error | integration + unit | `pytest tests/integration/test_england_1216_no_inputs.py -x` | ❌ Wave 0 |
| SC-3 | France 1066 ingest → generate → export produces 12 well-formed files | e2e (backend) | `pytest tests/e2e/test_france_1066_export.py -x` | ❌ Wave 0 |
| SC-3 | Project creation modal posts `region_key`; row persists with value | UAT (Playwright) | `npm run e2e -- tests/e2e/new-project-region.spec.ts` | ❌ Wave 0 |
| SC-3 | Alembic migration 0004 upgrades + downgrades cleanly | unit | `pytest tests/unit/test_migrations.py::test_0004_round_trip -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/unit/test_region_loader.py -x --no-cov` (loader unit tests) — runs in <2 s.
- **Per wave merge:** Full backend `pytest` + parity suite. Parity test `test_iberia_868_yaml.py` is the gate; if it fails, the wave does not merge.
- **Phase gate:** `pytest && npm test && npm run e2e` — all three layers green before `/gsd-verify-work`.

### Wave 0 Gaps

- [ ] `tests/unit/test_region_loader.py` — covers all loader unit tests above (9 cases).
- [ ] `tests/parity/test_iberia_868_yaml.py` — the hard gate (D-14). Copy structure from `backend/tests/parity/test_iberia_868.py`.
- [ ] `tests/integration/test_regions_endpoint.py` — GET /api/v3/regions integration test.
- [ ] `tests/integration/test_england_1216_no_inputs.py` — error path.
- [ ] `tests/e2e/test_france_1066_export.py` — SC-3 contract test.
- [ ] `tests/unit/test_migrations.py` — Alembic upgrade/downgrade round-trip (use existing patterns).
- [ ] `frontend/src/components/projects/__tests__/NewProjectModal.test.tsx` — Radix modal unit tests.
- [ ] `frontend/src/api/__tests__/useRegions.test.ts` — TanStack hook unit test.
- [ ] `tests/e2e/new-project-region.spec.ts` — Playwright UAT (D-07 modal).
- [ ] Add PyYAML to `pyproject.toml` deps + reinstall (Plan 05-01 first commit).

*(Existing infrastructure: pytest + vitest + Playwright already wired from Phase 04. Adding files only.)*

## Security Domain

`security_enforcement` is not explicitly set to false in config; treating as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Single-user local tool; no auth surface. |
| V3 Session Management | no | No sessions. |
| V4 Access Control | no | No user model. |
| V5 Input Validation | **yes** | Pydantic `BaseModel` + `Field(ge=, le=)` + `model_config = {"extra": "forbid"}` on `RegionConfigSchema`, on the new `POST /v3/projects` (or extension to `ProjectCreate`), and on `region_key` (regex `^[a-z0-9_]+$` to prevent path traversal in `data/regions/{key}.yaml` resolution). |
| V6 Cryptography | no | No new crypto surface. |
| V12 File Handling | **yes** | YAML loaded via `yaml.safe_load` (not `yaml.load`); region key validated against allowlist (or strict regex) before being concatenated into a path. |

### Known Threat Patterns for Phase 05 stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| YAML deserialization RCE (`!!python/object`) | Tampering / EoP | `yaml.safe_load` only. Never `yaml.load`. |
| Path traversal via region_key | Tampering | Strict allowlist regex `^[a-z][a-z0-9_]{0,63}$` on `region_key` before path resolution. Reject `../` etc. Also: `region_key` flows from a closed dropdown populated by `GET /api/v3/regions` (server-controlled list) — so the path traversal vector requires bypassing the API contract. Defense in depth. |
| Pydantic ValidationError leaking internal paths to client | Information disclosure | Surface validation errors structured but redact filesystem paths (`pydantic.ValidationError.errors()` may include input data — sanitize before logging or returning). |
| SQL injection via region_key in migration UPDATE | Tampering | Migration uses parameterized SQL via Alembic / SQLAlchemy `op.execute(sa.text("UPDATE ...").bindparams(key='iberia_868'))`. Hardcoded literal is acceptable here (no user input). |
| Dataset file existence side-channel (`has_dataset`) | Information disclosure | Low risk — single-user local tool. No remediation needed. |
| `original_idx` collision in autogen | Tampering (data integrity) | Autogen assigns monotonically increasing indices; uniqueness guaranteed by single-source generation (CLAUDE.md rule #4 + #7). |

## Sources

### Primary (HIGH confidence — verified by reading repo source)

- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/backend/medieval_forge/services/pipeline/regions.py` — current `iberia_config()` factory (lines 39-82); `_INPUTS_DIR` anchor pattern (lines 33-36); `REGIONS` dict (line 86).
- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/backend/medieval_forge/services/pipeline/contracts.py` — `RegionConfig` + `ProjectDataset` dataclasses; `__post_init__` (lines 133-136) derives `lon_scale`.
- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/backend/medieval_forge/services/pipeline/voronoi.py` — empty `pt_duchies` → single-tree behavior (lines 55, 65-68, 132-138).
- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/backend/medieval_forge/services/pipeline/border.py` — empty `border_polygon` → all-False mask (lines 21-22).
- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/backend/medieval_forge/services/pipeline/render.py` — `mountains`/`rivers` are dicts, guarded with `if not ...: return` (lines 206-214, 247-257).
- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/backend/medieval_forge/data/regions/iberia_868/territory_data.py` — `KINGDOMS` (lines 12-17), `DUCHIES` (lines 19-50), `CONDADOS` positional tuples (lines 53-289).
- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/backend/medieval_forge/api/v3/generate.py` — callsites (lines 39, 130); producer pattern.
- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/backend/medieval_forge/api/v3/render.py` — callsites (lines 42, 128, 198); fresh-cfg-per-call pattern (D-18).
- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/backend/medieval_forge/models.py` — `Project` ORM model; add `region_key` here.
- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/backend/medieval_forge/schemas.py` — `ProjectCreate` (lines 32-50); to extend with `region_key`.
- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/backend/medieval_forge/api/projects.py` — `POST /projects` (line 58); the v1 route that does/doesn't get extended (Open Q1).
- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/alembic/versions/0002_widen_country_qid_multi_country.py` — `op.batch_alter_table` pattern.
- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/alembic/env.py` — async env (asyncio.run + run_sync).
- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/pyproject.toml` — dep list; **PyYAML absent**.
- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/data/regions/iberia_868/inputs/mountain_river_data.json` — dict-of-dicts shape confirmed.
- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/backend/tests/parity/test_iberia_868.py` — parity test pattern (byte-equal + SSIM + JSON deep-equal). Model for `test_iberia_868_yaml.py`.
- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/frontend/src/pages/ProjectNew.tsx` — current 254-line create flow; entangles country/QID/period logic.
- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/.planning/phases/05-region-generalization/05-CONTEXT.md` — locked decisions.
- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/CLAUDE.md` — Pipeline Contract, σ rule, KD-tree rule, no-LLM rule, atomic-commit rule.
- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/.planning/ROADMAP.md` — Phase 05 SC-1/SC-2/SC-3.
- `c:/Users/veio_/Documents/Unity_Projects/MEDIEVAL-FORGE/.planning/PROJECT.md` — D-V3-04, D-V3-05, D-V3-07.

### Secondary (MEDIUM confidence — established library/framework patterns)

- pydantic v2 docs (training knowledge confirmed by repo usage in `api/v3/render.py:55-71`) — `BaseModel`, `Field`, `model_validate`, `model_dump`, `model_config = {"extra": "forbid"}`.
- Alembic async env pattern (verified in `alembic/env.py`).
- scipy.spatial.Voronoi cookbook — `voronoi_finite_polygons_2d` helper for infinite regions (well-known recipe).
- shapely `Polygon.intersection(box)` for clipping (standard library).

### Tertiary (LOW confidence — flagged for validation)

- PyYAML 6.0.2 as current — planner verifies pin via `pip index versions pyyaml` in Plan 05-01.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all libraries verified in pyproject.toml or confirmed missing (PyYAML).
- Architecture (loader + schema): HIGH — pydantic v2 patterns verified by existing in-repo usage; dataclass round-trip is standard Python.
- Empty-input behavior: HIGH — verified by reading source line-by-line.
- Mountain/river JSON shape: HIGH — verified by reading the actual file + render.py code.
- POST /v3/projects existence: HIGH (it doesn't exist — verified by reading api/projects.py + api/v3/__init__.py).
- Alembic pattern: HIGH — copying from existing revision.
- France Voronoi-from-grid: MEDIUM — scipy.spatial.Voronoi + shapely.intersection are well-established; infinite-region handling depends on cookbook code.
- Pitfalls: HIGH — most are anchored to verified repo state.

**Research date:** 2026-05-12
**Valid until:** 2026-06-12 (30 days; library APIs stable, no version churn expected).
