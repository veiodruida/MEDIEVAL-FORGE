# Phase 05: Region generalization - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-11
**Phase:** 05-region-generalization
**Areas discussed:** YAML schema + territory data, Region selection wire, Toy synthetic dataset France, Iberia migration + loader API

---

## Initial gray-area selection

| Area | Selected |
|------|----------|
| YAML schema + territory data | ✓ |
| Region selection wire | ✓ |
| Toy synthetic dataset France | ✓ |
| Iberia migration + loader API | ✓ |

User selected all four.

---

## Area 1: YAML schema + territory data

### Q1.1 — File layout

| Option | Description | Selected |
|--------|-------------|----------|
| Single-file region.yaml (Recommended) | All config + border + territories in `data/regions/{key}.yaml`; inputs in `data/regions/{key}/inputs/` | ✓ |
| Split: region.yaml + territories.yaml + border.geojson | Config separate from territories, border as standalone GeoJSON | |
| Single-file + territories as nested sub-block | Single YAML, `territories:` sub-key | |

### Q1.2 — Validation

| Option | Description | Selected |
|--------|-------------|----------|
| Pydantic schema (Recommended) | `RegionConfigSchema(BaseModel)`; structured errors; pydantic v2 | ✓ |
| Manual dict → dataclass | `yaml.safe_load` → `RegionConfig(**data)`; generic TypeErrors | |
| Pydantic only for critical fields | Compromise: validate critical only | |

### Q1.3 — Territory data in templates (no historical research)

| Option | Description | Selected |
|--------|-------------|----------|
| Empty + autogenerate `Condado_001..N` (Recommended) | Pipeline detects empty arrays → autogen synthetic condados from dataset centroids | ✓ |
| Stub minimal (1 kingdom + 1 duchy + N placeholder condados) | Less pipeline magic, more boilerplate per template | |
| Require non-empty territory data + block export | Forces user editing; breaks SC-3 | |

### Q1.4 — border_polygon for new regions

| Option | Description | Selected |
|--------|-------------|----------|
| Optional, default empty list (Recommended) | Empty → single global KD-tree; verify voronoi.py behavior | ✓ |
| Required + multi-country routing generic schema | Generalize PT/ES routing; large refactor; out of scope SC-3 | |

---

## Area 2: Region selection wire

### Q2.1 — DB column

| Option | Description | Selected |
|--------|-------------|----------|
| New `region_key: str` column (Recommended) | Alembic migration; NOT NULL DEFAULT 'iberia_868'; backfill existing | ✓ |
| Reuse `generator_config['region']` JSON | No migration; less rigid; no query-by-region | |
| Path/slug-routed without persistence | Lost on reload; rejected | |

### Q2.2 — Region API

| Option | Description | Selected |
|--------|-------------|----------|
| `GET /api/v3/regions` endpoint (Recommended) | Lists YAMLs in `data/regions/`; discoverable; extensible | ✓ |
| Hard-coded REGIONS dict in backend | No dedicated endpoint; adding a region needs redeploy | |

### Q2.3 — UI flow

| Option | Description | Selected |
|--------|-------------|----------|
| Dropdown in create-project modal (Recommended) | Pop-up: name + region dropdown; default Iberia 868 | ✓ |
| Pre-selected quick-start cards | 3 cards per region; faster, more opinionated | |
| No UI Phase 05 — backend only | Defers to v3.1; risks SC-3 UAT | |

### Q2.4 — Bounds

| Option | Description | Selected |
|--------|-------------|----------|
| Bounds 100% per YAML (Recommended) | Each region declares lon_min/max/lat_min/max explicitly | ✓ |
| Auto-detect bounds from dataset | Loader inspects GeoJSON; risk of bad inputs producing bad bounds | |

---

## Area 3: Toy synthetic dataset France

### Q3.1 — Geometry

| Option | Description | Selected |
|--------|-------------|----------|
| Voronoi-from-grid points (Recommended) | N jittered grid points → Voronoi cells; deterministic via rng_seed=42 | ✓ |
| Square grid | Predictable; less realistic; may hide irregular-polygon bugs | |
| Hex grid | More code; no win over Voronoi | |

### Q3.2 — Size

| Option | Description | Selected |
|--------|-------------|----------|
| ~50 (Recommended) | Balance: <5s generate, ~10-15 condados after clustering | ✓ |
| ~200 | More realistic; ~15s generate; overkill | |
| ~10 | Risk: too few for median/cleanup to produce valid output | |

### Q3.3 — Fixture location

| Option | Description | Selected |
|--------|-------------|----------|
| Committed in `data/regions/france_1066/inputs/` (Recommended) | Generator script + outputs all committed; reproducible | ✓ |
| Generated at runtime first generate | Risk of non-determinism cross-OS | |
| Script only, gitignored geojson | Dev must run script before tests; CI step | |

### Q3.4 — England 1216

| Option | Description | Selected |
|--------|-------------|----------|
| YAML only, no inputs (Recommended) | Template; pipeline aborts on generate with clear error | ✓ |
| Toy like France | Doubles scope; SC-3 doesn't require | |

---

## Area 4: Iberia migration + loader API

### Q4.1 — `iberia_config()` fate

| Option | Description | Selected |
|--------|-------------|----------|
| Delete (Recommended D-V3-04) | Loader replaces; callsites migrate; no wrapper | ✓ |
| Thin wrapper backward-compat | Leaves dead code D-V3-04 wants gone | |
| Delete + keep territory_data.py as migration source | Hybrid; mostly subsumed by Q4-followup | |

### Q4.2 — Parity gate

| Option | Description | Selected |
|--------|-------------|----------|
| Hard parity test (Recommended) | `test_iberia_868_yaml.py` byte-equal vs golden; non-skippable | ✓ |
| Diff test — RegionConfig equals | Faster; weaker (pipeline divergence not caught) | |
| Both | More coverage, more test code | |

### Q4.3 — Loader API

| Option | Description | Selected |
|--------|-------------|----------|
| `load_region(key: str) -> RegionConfig` (Recommended) | Free function in new `region_loader.py` module; mtime cache | ✓ |
| `RegionConfig.load(key)` classmethod | Mixes I/O into contracts.py | |
| Factory injectable | Overkill for single-user local tool | |

### Q4.4 — Existing DB rows

| Option | Description | Selected |
|--------|-------------|----------|
| Alembic backfill 'iberia_868' (Recommended) | Migration NOT NULL DEFAULT + explicit UPDATE | ✓ |
| Nullable column + fail-soft None | Leaves inconsistent state | |

---

## Area 4 follow-ups

### Q4.5 — Migration of `territory_data.py` (280 lines) to YAML

| Option | Description | Selected |
|--------|-------------|----------|
| Script one-shot committed + delete territory_data.py (Recommended) | `scripts/migrate_iberia_to_yaml.py` reads in-memory → dumps YAML; both committed; territory_data.py deleted after | ✓ |
| Hand-write iberia_868.yaml directly | Risk of human error; not reproducible | |
| Keep territory_data.py as source + load YAML from it | Breaks symmetry; Iberia special-cased | |

### Q4.6 — France toy generation

| Option | Description | Selected |
|--------|-------------|----------|
| `scripts/gen_toy_france.py` committed (Recommended) | Deterministic Voronoi; YAML hand-written (~30 lines); outputs committed | ✓ |
| All hand-rolled (no script) | Not reproducible | |

---

## Closing check

| Option | Description | Selected |
|--------|-------------|----------|
| Ready for CONTEXT.md | Sufficient decisions; proceed to plan-phase | ✓ |
| Explore more gray areas | Continue discussion | |

---

## Claude's Discretion

Items where user delegated to Claude / planner:
- `voronoi.py` empty `border_polygon` behavior verification
- Loader cache invalidation policy (mtime vs explicit only)
- YAML structure for kingdoms/duchies/condados (list vs dict)
- Autogenerate insertion point (loader vs voronoi.py)
- France toy mountain_river_data.json shape (empty stub)
- `api/v3/regions.py` HTTP response shape (nested vs flat bounds)
- Create-project modal location/structure in frontend code
- Path resolution in YAML (region-relative vs repo-relative)
- Migration script idempotency (overwrite vs bail)
- Frontend coverage threshold for the new modal
- `test_iberia_868.py` retirement strategy after D-13 deletes `iberia_config()`

## Deferred Ideas

Captured in CONTEXT.md `<deferred>` section.
