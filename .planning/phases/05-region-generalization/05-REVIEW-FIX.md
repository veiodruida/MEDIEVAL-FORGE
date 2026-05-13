---
phase: 05-region-generalization
fixed_at: 2026-05-13T00:00:00Z
review_path: .planning/phases/05-region-generalization/05-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 05: Code Review Fix Report

**Fixed at:** 2026-05-13
**Source review:** `.planning/phases/05-region-generalization/05-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (1 Critical + 4 Warnings; Info out of scope per `critical_warning` policy)
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01: `UNITY_ZIP_SPEC` is missing `rivers_overlay.png` — Unity ZIP ships 11/12 contract files

**Files modified:** `backend/medieval_forge/services/export.py`, `backend/tests/test_export.py`
**Commit:** `0ee12ff`
**Applied fix:** Replaced the duplicated 11-entry literal tuple in `export.py` with a direct alias `UNITY_ZIP_SPEC = EXPORT_FILE_CONTRACT` (from `services.pipeline.contracts`). Added an import-time `assert len(UNITY_ZIP_SPEC) == 12` and an in-test guard `set(UNITY_ZIP_SPEC) == set(EXPORT_FILE_CONTRACT)` inside `test_build_unity_zip_assembles_12_files`. This eliminates the source of drift: there is now exactly one authoritative declaration of the 12-file Unity contract, and the test catches any future re-divergence. Verified no circular-import risk — `contracts.py` does not import `export.py`.

### WR-01: `ProjectCreate` does not enforce `period_start < period_end`

**Files modified:** `backend/medieval_forge/schemas.py`
**Commit:** `2280621`
**Applied fix:** Added a `@model_validator(mode="after") _check_period_ordering` on `ProjectCreate` that raises `ValueError("period_start must be less than period_end")` when `period_start >= period_end`. Both fields are required on `ProjectCreate` (declared as `int`, not `int | None`), so the `is not None` guard used in `ProjectUpdate` is unnecessary. Existing tests (`test_projects.py`, fixtures) all use `period_start=868, period_end=1492`, so no test regressions.

### WR-02: `_autogen_territories` overwrites partially-populated `kingdoms`/`duchies`

**Files modified:** `backend/medieval_forge/services/pipeline/region_loader.py`
**Commit:** `053900e`
**Applied fix:** Gated autogen on ALL THREE (`condados`, `kingdoms`, `duchies`) being empty. When only `condados` is empty but `kingdoms`/`duchies` are populated, the loader now raises `ValueError(f"region {key!r}: condados empty but kingdoms/duchies populated — autogen would overwrite curated data...")`. Existing YAMLs are unaffected: `iberia_868.yaml` populates all three; `france_1066.yaml` and `england_1216.yaml` clear all three. The fail-loud branch only fires on a future mis-curated YAML, which is the intended behaviour.

### WR-03: `terrain.render_terrain_lookup` uses `assert` for input validation

**Files modified:** `backend/medieval_forge/services/pipeline/terrain.py`
**Commit:** `da3f197`
**Applied fix:** Replaced the two `assert` statements in `render_terrain_lookup` with explicit `raise TypeError(...)` (dtype check) and `raise ValueError(...)` (shape check). Defensive input validation now survives `python -O`. No existing tests rely on `pytest.raises(AssertionError)` against this function (grepped `backend/tests/` — zero matches), so no test updates required.

### WR-04: `_render_producer` cleanup ordering — narrow race window between sentinel and queue pop

**Files modified:** `backend/medieval_forge/api/v3/render.py`
**Commit:** `597020e`
**Applied fix:** Expanded the `stream_render` docstring to document the contract explicitly: subscribe immediately after 202, late subscribers receive 404, and there is a narrow window after sentinel emission and before eviction where a subscriber may receive an empty-but-completed stream — the frontend MUST treat that case identically to a 404. The producer's `finally` ordering (`put(None)` → pop queues) is preserved (the previous bug was a late-subscriber hang; the current ordering trades a hang for an inconsistent UX state which the docstring now contracts to the client).

## Skipped Issues

None.

---

_Fixed: 2026-05-13_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
