---
phase: 05
plan: 13
subsystem: region-loader
tags: [region-loader, dedupe, autogen, wr-01, regression-guard]
requirements: [SC-2, SC-3]
requirements_addressed: [SC-2, SC-3]
gap_closure: true
replan_source: 05-REVIEWS.md (WR-01 consensus 3/3 reviewers)
dependency_graph:
  requires: [05-12]
  provides:
    - "_autogen_territories dedupes by resolved Path (single-country YAMLs no longer double-read)"
    - "test_gen_toy_france bound 40..55 (tight regression catcher)"
    - "test_load_region_autogen_deterministic (cross-call identity guard)"
  affects:
    - backend/medieval_forge/services/pipeline/region_loader.py
    - backend/tests/unit/test_gen_toy_france.py
tech_stack:
  added: []
  patterns:
    - "seen_paths: set[Path] dedupe inside loop iterating (dataset.pt_geojson, dataset.es_input)"
    - "Cross-call snapshot equality as determinism regression guard"
key_files:
  created: []
  modified:
    - backend/medieval_forge/services/pipeline/region_loader.py
    - backend/tests/unit/test_gen_toy_france.py
decisions:
  - "Dedupe placed BEFORE existence check so None never enters seen_paths (adapted reviewer snippet by 2 lines)"
  - "Upper bound 55 gives 15-feature headroom for future toy enrichment without re-tightening"
  - "Snapshot rounded to 6 decimals on (lon, lat) to avoid float jitter while still catching reordering"
metrics:
  duration: ~6m
  completed: 2026-05-13
  tasks: 2
  files_modified: 2
commits:
  - 1a0e1b1 fix(05-13): dedupe _autogen_territories paths — single-country YAMLs no longer double-read (WR-01)
  - dcc826e test(05-13): tighten autogen bound to 40..55 + determinism regression guard (WR-01)
---

# Phase 05 Plan 13: WR-01 — Dedupe `_autogen_territories` paths Summary

WR-01 (cross-AI review consensus 3/3 reviewers — Gemini, Codex, OpenCode) closed: `_autogen_territories` now dedupes by resolved `Path` so single-country YAMLs (France 1066, England 1216) that intentionally point both `dataset.pt_geojson` and `dataset.es_input` at the same file are read exactly once. Pre-fix `load_region('france_1066').condados` was producing ~80 condados from a 40-feature toy dataset; post-fix it produces exactly 40 condados. Iberia parity stays green because its YAML uses dual-country routing (`pt_geojson != es_input`), so `seen_paths` never elides either input.

## Objective Recap

1. **Dedupe** — Add `seen_paths: set[Path]` inside `_autogen_territories` so duplicate paths are read once.
2. **Tighten** — Replace `>= 40` with inclusive `40 <= n <= 55` so any future double-read regression fails immediately.
3. **Guard** — Add `test_load_region_autogen_deterministic` asserting cross-call identity of `original_idx` ordering, `(lon, lat)` per condado, ids/names tuples, and kingdom keys.

## Implementation Trace

### Task 1 — `_autogen_territories` dedupe (commit `1a0e1b1`)

File: `backend/medieval_forge/services/pipeline/region_loader.py` (lines 387-401).

Diff size: **+10 lines / -0 lines** (8 lines comment + 2 lines logic + 1 blank). The reviewer's snippet was adapted by placing the dedupe **before** the existence check so a `None` value (from `dataset.es_input=None` cases) never enters `seen_paths`.

Insertion structure:

```python
features: list[dict] = []
# WR-01 fix (Plan 05-13): single-country YAMLs ...
seen_paths: set[Path] = set()

for geojson_path in (dataset.pt_geojson, dataset.es_input):
    if geojson_path is None or not geojson_path.exists():
        continue
    if geojson_path in seen_paths:
        continue
    seen_paths.add(geojson_path)
    try:
        data = json.loads(geojson_path.read_text(encoding="utf-8"))
    ...
```

`Path` was already imported at `region_loader.py:27` — no new imports needed.

### Task 2 — Tighten bound + determinism test (commit `dcc826e`)

File: `backend/tests/unit/test_gen_toy_france.py`.

- Replaced `assert len(cfg.condados) >= 40` with `assert 40 <= n <= 55` (plus a diagnostic error message naming the WR-01 regression pattern).
- Appended a new test `test_load_region_autogen_deterministic` that runs `clear_region_cache() + load_region("france_1066")` twice and asserts dict-equality of a 7-field snapshot (`n_condados`, `original_idx`, `ids`, `names`, `lons`, `lats`, `kingdoms`). `(lon, lat)` are rounded to 6 decimals to avoid float jitter while still catching any reordering.

Diff size: **+58 lines / -1 line**.

## Verification

| Check | Result |
|-------|--------|
| `pytest tests/unit/test_gen_toy_france.py -q` | 6 passed |
| `pytest tests/unit/test_region_loader.py -q` | 31 passed |
| `pytest tests/parity/test_iberia_868_yaml.py -q` | 11 passed (Iberia parity gate preserved) |
| `pytest tests/unit -q` | 135 passed |
| `pytest tests/parity -q` | 12 passed + 6 xfailed + 4 xpassed (live-ingest D-09 waiver unchanged) |
| `pytest tests/e2e -q` | 8 passed |
| Smoke: `load_region('france_1066')` | `condados=40` (pre-fix: ~80) |

### Acceptance Criteria Receipts

- `seen_paths: set[Path] = set()` count = **1** ✓
- `if geojson_path in seen_paths:` count = **1** ✓
- `seen_paths.add(geojson_path)` count = **1** ✓
- `WR-01 fix (Plan 05-13)` count = **1** ✓
- `40 <= n <= 55` count = **2** (assertion + error msg) ✓ (≥1 required)
- `def test_load_region_autogen_deterministic` count = **1** ✓
- `snapshot_a == snapshot_b` count = **1** ✓

## Pre-fix vs Post-fix Condado Count

| Region | Pre-fix | Post-fix | Path equality? |
|--------|---------|----------|----------------|
| `france_1066` | ~80 | **40** | `pt_geojson == es_input` (single-country fallthrough — D-04) |
| `england_1216` | n/a (template-only on disk) | n/a | Same YAML pattern — fix applies when dataset present |
| `iberia_868` | 92 | **92** | `pt_geojson != es_input` (dual-country routing — dedupe is no-op) |

## Deviations from Plan

None — plan executed exactly as written.

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-05-13-01 | Place `if geojson_path in seen_paths` BEFORE `seen_paths.add` AND BEFORE the existence check that already guards `None` | Keeps `None` out of `seen_paths` (sets accept `None`, but it would conflate two distinct "skip" reasons in the trace) |
| D-05-13-02 | Upper bound at 55 (not 50, not 45) | 15-feature headroom matches Phase 05 plan future-toy enrichment ceiling; staying tight enough to catch ~80 regression |
| D-05-13-03 | Round `(lon, lat)` to 6 decimals in determinism snapshot | 6 decimals = ~11cm at equator; well below any meaningful drift, while immune to float-repr jitter across Python versions |

## Threat Surface Scan

No new trust boundaries introduced. Existing `_resolve` path-traversal guard (T-05-01-03) handles adversarial YAML paths; dedupe is a pure correctness fix on top.

## Self-Check: PASSED

- File `backend/medieval_forge/services/pipeline/region_loader.py` exists ✓
- File `backend/tests/unit/test_gen_toy_france.py` exists ✓
- Commit `1a0e1b1` exists in git log ✓
- Commit `dcc826e` exists in git log ✓
- All acceptance grep counts match plan ✓
- Live smoke `load_region('france_1066')` → `condados=40` ✓
- Iberia parity gate green (11 passed) ✓
- Full backend suite green (unit 135 + parity 12+6xf+4xp + e2e 8) ✓
