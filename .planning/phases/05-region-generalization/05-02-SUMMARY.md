---
phase: "05"
plan: "02"
subsystem: backend/pipeline
tags: [region-loader, yaml, migration, territory-data, iberia]
dependency_graph:
  requires:
    - phase: "05-01"
      provides: "load_region API, RegionConfigSchema, clear_region_cache"
  provides:
    - "data/regions/iberia_868.yaml — complete Iberia 868 AD region config (1748 lines)"
    - "scripts/migrate_iberia_to_yaml.py — idempotent one-shot migration script"
    - "5 unit tests (idempotent, loader_roundtrip, dataset_is_plain_dict, condados_carry_original_idx, yaml_keyset_matches_schema)"
  affects:
    - "backend/tests/parity/test_iberia_868_yaml.py (Plan 05-03 parity gate reads this YAML)"
    - "backend/medieval_forge/services/pipeline/region_loader.py (loads this YAML in production)"
tech_stack:
  added: []
  patterns:
    - "Migration script: tuple/dict source data converted to list[dict] matching RegionConfigSchema"
    - "kingdom_colors: int keys emitted as str keys (pydantic v2 dict[str, list[int]] contract)"
    - "CONDADOS tuples unpacked field-by-field; original_idx injected sequentially starting at 1"
    - "idempotency verified via sha256 of emitted file before/after re-run"
key_files:
  created:
    - "scripts/migrate_iberia_to_yaml.py"
    - "data/regions/iberia_868.yaml"
  modified:
    - "backend/tests/unit/test_migrate_iberia_to_yaml.py (scaffold → 5 real tests)"
key_decisions:
  - "KINGDOMS/DUCHIES/CONDADOS converted from native dict/tuple formats to list[dict] matching RegionConfigSchema (plan's dict(raw_condado) literal would crash on tuple input — Rule 1 deviation)"
  - "kingdom_colors int keys (0..3) emitted as str keys because pydantic v2 rejects int keys in dict[str, list[int]]"
  - "roundtrip comparison compares lengths for kingdoms/duchies/condados (tuple-format pipeline adapter is Plan 05-04's concern)"
  - "REPO resolved via parents[3] from backend/tests/unit/ file path (parents[4] in plan comment was off-by-one for this project layout)"
requirements-completed: [SC-1]
duration: ~20min
completed: "2026-05-12"
---

# Phase 05 Plan 02: Iberia 868 YAML Migration Summary

**One-shot idempotent migration of iberia_config()+territory_data → data/regions/iberia_868.yaml (1748 lines, 92 condados all with original_idx) validated by 5 unit tests and 11/11 parity.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-12T12:10:00Z
- **Completed:** 2026-05-12T12:30:00Z
- **Tasks:** 1 of 1
- **Files modified:** 3

## Accomplishments

- `scripts/migrate_iberia_to_yaml.py` — one-shot reproducible migration, idempotent (sha256 stable across re-runs)
- `data/regions/iberia_868.yaml` — 1748-line YAML with all 92 condados carrying `original_idx` (CLAUDE.md rule 4), `display_name: Iberia 868 AD`, all 34 schema fields present
- 5 unit tests: idempotent, loader_roundtrip, dataset_is_plain_dict (R-01), condados_carry_original_idx (R-01/CLAUDE.md rule 4), yaml_keyset_matches_schema (R-11) — all green
- Phase 01 parity (11/11) unchanged

## Task Commits

Each task was committed atomically:

1. **Task 1: migrate_iberia_to_yaml.py + iberia_868.yaml + 5 unit tests** - `b3011d4` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `scripts/migrate_iberia_to_yaml.py` — one-shot migration: extracts iberia_config()+territory_data, emits YAML
- `data/regions/iberia_868.yaml` — generated region config (1748 lines, 29948 bytes)
- `backend/tests/unit/test_migrate_iberia_to_yaml.py` — 5 unit tests replacing Wave-0 scaffold placeholder

## Decisions Made

- **KINGDOMS/DUCHIES/CONDADOS format conversion:** Plan's literal `dict(raw_condado)` would crash on tuple input. KINGDOMS is `dict[str, str]` → emitted as `list[dict]`. DUCHIES is `dict[str, tuple[str, str]]` → emitted as `list[dict]`. CONDADOS is `list[tuple(id, name, lon, lat, duchy_id, baronies)]` → each tuple unpacked field-by-field into dict. This matches RegionConfigSchema's `list[dict]` expectation.
- **kingdom_colors int → str keys:** pydantic v2 rejects int keys in `dict[str, list[int]]` (confirmed empirically). Script emits `{str(k): list(v) for k, v in cfg.kingdom_colors.items()}`. Roundtrip comparison validates values (not keys).
- **Roundtrip comparison:** For kingdoms/duchies/condados, only counts are compared (len equality). The tuple-format pipeline adapter (Plan 05-04) owns the full structural equivalence.
- **REPO path:** `parents[3]` from `backend/tests/unit/` reaches the repo root; plan comment said `parents[4]` which was off-by-one.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan literal `dict(raw_condado)` would crash on tuple input**
- **Found during:** Task 1 (inspecting territory_data.py data shapes before writing)
- **Issue:** `CONDADOS` is `list[tuple]` where each tuple is `(id, name, lon, lat, duchy_id, baronies)`. `dict(tuple_of_6)` raises `ValueError: dictionary update sequence element #0 has length 6; 2 is required`. Plan's code assumed dicts but territory_data.py uses tuples.
- **Fix:** Unpacked each tuple positionally into a proper dict with all 8 fields (id, name, lon, lat, duchy_id, kingdom_id, original_idx, baronies).
- **Files modified:** scripts/migrate_iberia_to_yaml.py
- **Verification:** `load_region('iberia_868')` returns cfg with 92 condados; test_loader_roundtrip passes
- **Committed in:** b3011d4

**2. [Rule 1 - Bug] KINGDOMS dict → list[dict] conversion (plan emitted dict directly)**
- **Found during:** Task 1
- **Issue:** Plan wrote `kingdoms: KINGDOMS` which would emit a raw `dict[str, str]` into YAML; RegionConfigSchema expects `list[dict]`. Would cause pydantic ValidationError on load.
- **Fix:** `kingdoms_out = [{"id": k, "name": v} for k, v in KINGDOMS.items()]`
- **Committed in:** b3011d4

**3. [Rule 1 - Bug] DUCHIES dict → list[dict] conversion**
- **Found during:** Task 1
- **Issue:** Same problem as KINGDOMS — dict of tuples would serialize as YAML mapping, not list[dict].
- **Fix:** `duchies_out = [{"id": did, "kingdom_id": kid, "name": dname} for did, (kid, dname) in DUCHIES.items()]`
- **Committed in:** b3011d4

**4. [Rule 1 - Bug] kingdom_colors int keys → str keys**
- **Found during:** Task 1 (confirmed empirically: pydantic v2 raises ValidationError for int keys in dict[str, list[int]])
- **Issue:** iberia_config() returns `{0: (190,158,82), ...}`. yaml.safe_dump serializes int keys as YAML int; pydantic v2 rejects them at model_validate time.
- **Fix:** `{str(k): list(v) for k, v in cfg.kingdom_colors.items()}`
- **Committed in:** b3011d4

**5. [Rule 1 - Bug] REPO path: parents[4] → parents[3]**
- **Found during:** Task 1 (4 tests failing with "YAML not found at ...Users/Unity_Projects/...")
- **Issue:** Plan comment `parents[4]` was off-by-one. From `backend/tests/unit/test_*.py`, parents[3] is the repo root.
- **Fix:** Changed `parents[4]` to `parents[3]` in test file.
- **Files modified:** backend/tests/unit/test_migrate_iberia_to_yaml.py
- **Committed in:** b3011d4

---

**Total deviations:** 5 auto-fixed (all Rule 1 — bugs in plan's literal code vs actual data shapes)
**Impact on plan:** All fixes necessary for correctness; plan intent was clear throughout. No scope creep.

## Known Stubs

None — YAML is fully wired with real data from iberia_config() + territory_data.py.

## Threat Surface

Threat model mitigations confirmed:
- T-05-02-01: Script is dev-only one-shot; not importable at runtime; no attack surface.
- T-05-02-02: `yaml.safe_dump(doc, ...)` serialises the plain `doc` dict. No `!!python/object` tags verified via `test_dataset_is_plain_dict` byte-scan. Idempotency test catches drift.

## Issues Encountered

None — all five deviations were straightforward data-shape fixes. Script ran in one pass; tests green on first full run after path fix.

## Next Phase Readiness

- `data/regions/iberia_868.yaml` is committed and ready for Plan 05-03's parity gate (`test_iberia_868_yaml.py`)
- `load_region('iberia_868')` roundtrip confirmed working (test_loader_roundtrip passes)
- Phase 01 parity 11/11 unchanged — legacy `iberia_config()` path untouched

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| scripts/migrate_iberia_to_yaml.py exists | FOUND |
| data/regions/iberia_868.yaml exists (≥50 lines) | FOUND (1748 lines) |
| test_migrate_iberia_to_yaml.py exists | FOUND |
| Commit b3011d4 exists | FOUND |
| 5 tests passing | PASSED |
| Parity 11/11 green | PASSED |

---
*Phase: 05-region-generalization*
*Completed: 2026-05-12*
