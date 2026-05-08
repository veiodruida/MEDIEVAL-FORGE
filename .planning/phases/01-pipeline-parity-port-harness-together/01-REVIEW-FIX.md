---
phase: 01-pipeline-parity-port-harness-together
fixed_at: 2026-05-08T00:00:00Z
review_path: .planning/phases/01-pipeline-parity-port-harness-together/01-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 01: Code Review Fix Report

**Fixed at:** 2026-05-08
**Source review:** `.planning/phases/01-pipeline-parity-port-harness-together/01-REVIEW.md`
**Iteration:** 1
**Fix scope:** `critical_warning` (CR-* + WR-*; IN-* deferred)

**Summary:**
- Findings in scope: 4 (1 Critical, 3 Warnings)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### CR-01: Parity CI job will fail because checkout does not fetch LFS

**Files modified:** `.github/workflows/ci.yml`
**Commit:** `e7a1f8c`
**Applied fix:** Added `with: lfs: true` to the `pytest-parity` job's `actions/checkout@v4` step. The unit job intentionally remains LFS-free (it does not need the input GeoJSON). On a fresh CI runner the parity job will now fetch the real `pt_concelhos_wgs84.geojson` content rather than its 130-byte LFS pointer, preventing the JSONDecodeError that REVIEW.md flagged. Optional hardening sanity-check from the review (early `head -c 100 ... | grep git-lfs` step) was NOT added — the YAML change alone resolves the underlying defect, and adding noise-only diagnostics would expand scope.

### WR-01: Pipeline input paths in `regions.py` are cwd-dependent and fail silently

**Files modified:** `backend/medieval_forge/services/pipeline/regions.py`
**Commit:** `9959cc2`
**Applied fix:** Anchored the three input paths (`pt_concelhos_wgs84.geojson`, `es-atlas-pkg/.../municipalities.json`, `mountain_river_data.json`) to the repo root using a module-level `_INPUTS_DIR = Path(__file__).resolve().parents[4] / "data" / "regions" / "iberia_868" / "inputs"`. Crucial deviation from REVIEW.md's suggested fix: the inputs ship at the **repo root** under `data/regions/iberia_868/inputs/`, NOT inside the package's `backend/medieval_forge/data/` (which only contains `territory_data.py`). REVIEW.md's `parents[2]` would have anchored to `backend/medieval_forge/`, producing a still-broken path. `parents[4]` matches the convention already used at `backend/tests/parity/conftest.py:55`. Verified empirically by running `iberia_config()` from both repo root and `backend/` cwd — all three paths resolve in both cases.

### WR-02: `__main__.py` end-to-end CLI flow is not exercised by any test

**Files modified:** `backend/tests/integration/test_pipeline_cli_e2e.py` (new file)
**Commit:** `2e8bf34`
**Applied fix:** Added a new integration test that runs `python -m medieval_forge.services.pipeline --region iberia_868 --out <tmp_path>` as a subprocess and asserts (a) exit code 0 and (b) the 10 expected output files (per the v3 12-file contract minus the deferred terrain pair) land on disk. Marker choice deviates from REVIEW.md: REVIEW.md suggested `@pytest.mark.slow`, but Phase 01 CI runs with `pytest -m "parity or integration"` — `slow` would be excluded. Used `@pytest.mark.integration` instead so the test actually executes on every CI run, exercising the three substantive lines of `__main__.py` (`REGIONS[args.region]()`, `cfg.output_dir = args.out`, `run_pipeline(cfg)`) that the existing `--help` smoke test never reaches. Byte-equality assertions are intentionally omitted — the parity suite already covers that. Trade-off: this adds ~45 s to CI runtime (one full pipeline run); REVIEW-FIX heads-up to maintainers.

### WR-03: `lookup.py` ignores `level_map` for `label == "barony"` despite accepting it

**Files modified:** `backend/medieval_forge/services/pipeline/lookup.py`
**Commit:** `e924d27`
**Applied fix:** Added an inline block comment immediately above the `m = level_map == i if label != "barony" else result == i` line, explaining that the `level_map` argument is intentionally ignored when `label=='barony'`, citing inicio:660 as the verbatim source, noting today's call site equivalence in `__init__.py:127`, and explicitly forbidding refactor under D-01. Algorithm is unchanged. Took the comment-only path (REVIEW.md's fallback) rather than the parameter-removal refactor (REVIEW.md's "preferable" suggestion) because the prompt is explicit: "do NOT change the algorithm" — the verbatim-port contract under D-01 outranks API ergonomics in Phase 01.

---

_Fixed: 2026-05-08_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
