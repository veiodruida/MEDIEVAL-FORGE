---
phase: quick-260417-jq1
plan: 01
subsystem: data-pipeline
tags: [territory-data, sync, parity-test, iberia]
key-files:
  created:
    - scripts/sync_territory_iberia.py
    - backend/tests/services/test_territory_iberia_parity.py
    - backend/tests/services/__init__.py
  modified:
    - backend/medieval_forge/services/territory_iberia.json
decisions:
  - Sync script uses importlib.util to load v3 without permanently modifying sys.modules
  - JSON written with newline="\n" + trailing newline for byte-stable idempotency
metrics:
  duration: 15min
  completed: 2026-04-17
  tasks: 2
  files: 3
---

# Quick Task 260417-jq1: Carregar centroids curados de territory_data_v3 — Summary

**One-liner:** Deterministic sync script + 3-test parity guard locking territory_iberia.json to inicio/territory_data_v3.py as its single source of truth.

## Planning-Time Finding: Pipeline Already Uses Curated Centroids

During planning it was confirmed that `backend/medieval_forge/lib/map_generator.py`'s `setup_baronies()` already iterates `c[5]` (baronies) from the territory template JSON, builds `geo_to_pixel(blo, bla, cfg)` for each barony, and feeds those pixels into `cKDTree`. The frontend obtains the template via `GET /api/projects/territory-template/iberia` and passes it as `territory_data` in the generate request body.

**No pipeline, generator, or API code was changed.** The task delivered the supply chain (sync script + drift guard) that was missing.

## Confirmed Counts

| Entity | Count |
|--------|-------|
| Kingdoms | 4 |
| Duchies | 26 |
| Condados | 92 |
| Total baronies | 257 |

Source: `inicio/territory_data_v3.py` and `backend/medieval_forge/services/territory_iberia.json` (now locked to it).

## What Was Delivered

### Task 1 — scripts/sync_territory_iberia.py

Deterministic exporter: reads `KINGDOMS`, `DUCHIES`, `CONDADOS` from `territory_data_v3.py` via `importlib.util` and writes `territory_iberia.json` with `json.dump(..., ensure_ascii=False, indent=2)` + trailing newline. Running it a second time produces byte-identical output (idempotent).

The only change to the existing JSON was adding a trailing newline (the original had no `\n` at EOF). The parsed structure was byte-identical in all other respects.

### Task 2 — backend/tests/services/test_territory_iberia_parity.py

Three pytest tests:

1. `test_counts_match` — asserts 4/26/92/257 counts in JSON.
2. `test_v3_matches_json` — loads both v3 and JSON, asserts structural equality for every kingdom, duchy, condado (id/name/lon/lat/duchy_id), and barony (name/lon/lat) in order. Fails with a message pinpointing the first differing entry if drift occurs.
3. `test_sync_script_is_idempotent` — runs the sync script via `subprocess`, compares bytes before/after, fails if they differ.

All three passed on first run.

## Float Formatting

No lon/lat formatting surprises. All values in v3 have ≤2 decimal places; Python's `json.dump` round-trips them identically (e.g., `-5.84` stays `-5.84`).

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `scripts/sync_territory_iberia.py`: FOUND
- `backend/tests/services/test_territory_iberia_parity.py`: FOUND
- `backend/medieval_forge/services/territory_iberia.json`: FOUND
- Commit 42788ee: feat(260417-jq1): add deterministic sync script
- Commit 2eec56e: test(260417-jq1): add parity tests
