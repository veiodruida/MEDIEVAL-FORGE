---
phase: quick-260426-pcy
plan: 01
subsystem: backend/services
tags: [bugfix, territories-geojson, orphan-condados, regression-test]
requires:
  - .planning/phases/04-canvas-editing-basic/04-HUMAN-UAT.md (UAT bug source)
provides:
  - "scripts/diagnose_orphans.py — one-shot diagnostic for metadata↔geojson divergence"
  - "Fail-loud contract: emit_territories_from_disk raises ValueError on out-of-range orig_idx in legacy fallback"
  - "Soft-assertion log: build_territories_geojson ERROR-logs missing metadata ids"
  - "Regression test suite asserting set(metadata ids) == set(geojson ids)"
affects:
  - backend/medieval_forge/services/territories_geojson.py
  - backend/tests/test_territories_geojson.py (existing test updated to fail-loud contract)
tech-stack:
  added: []
  patterns:
    - "Centroid-match heuristic to infer orig_idx → metadata id without DB access"
    - "Fail-loud over silent-skip in fallback paths that previously masked Problem B"
key-files:
  created:
    - scripts/diagnose_orphans.py
    - backend/tests/services/test_territories_geojson_consistency.py
  modified:
    - backend/medieval_forge/services/territories_geojson.py
    - backend/tests/test_territories_geojson.py
decisions:
  - "Branch H1 selected (pc/lookup mismatch) — diagnostic shows 12/12 orphans have orig_idx ≠ meta_ci"
  - "Fail loud (raise ValueError) instead of repair-by-inference — silent skip is the antipattern that hid the bug"
  - "Stale project repaired via one-shot centroid-match script (in-session); production fix prevents recurrence"
metrics:
  duration: "~45m"
  completed: "2026-04-26"
  tasks: 4
  commits:
    - 7707fd0  # diagnostic script
    - 21e6614  # fix
    - 3095107  # regression tests
---

# Quick Task 260426-pcy: Fix Orphan Bug — 13 Condados Missing from territories.geojson

**One-liner:** Identified the silent-skip path in `emit_territories_from_disk`'s legacy fallback as the root cause of 12 orphan condados (UAT bug source: `04-HUMAN-UAT.md` line 176); converted the silent skip into a hard `ValueError`, added a soft-assertion ERROR log inside `build_territories_geojson`, and locked the invariant `set(metadata.condados.id) == set(geojson.features.id)` behind four regression tests.

## Root Cause (Hypothesis Selected: H1 — pc/lookup mismatch)

The diagnostic script (`scripts/diagnose_orphans.py`) was run against the user-confirmed bug-repro project `2d402c81-0b72-4cbb-8b61-21d72eff2a44`:

```
project=2d402c81-0b72-4cbb-8b61-21d72eff2a44
n_metadata=19  n_geojson=7  orphans=12

            id   orig_idx                   rgb    png_px  in_colors  meta_px  ocean_far?
----------------------------------------------------------------------------------------------------
       alcacer         62          (40,254,124)      3853       True     3853  -
          beja         64          (114,144,94)      5867       True     5867  -
         braga         10          (164,42,136)      1825       True     1825  -
      braganca         13            (19,5,219)      3802       True     3802  -
        chaves         12         (238,188,106)      3564       True     3564  -
         evora         63           (77,71,237)      6236       True     6236  -
        lamego         27              (25,3,9)      3250       True     3250  -
         porto          9          (127,225,23)       649       True      649  -
     salamanca         18          (204,114,16)       491       True      491  -
      santarem         61            (3,181,11)      5973       True     5973  -
           tui          8          (90,152,166)       445       True      445  -
         viana         11         (201,115,249)      1333       True     1333  -

H2 ocean_far collisions: 0
H1 pc/lookup mismatch  : 12
H3 degenerate geometry : 0
H4 manual mismatch     : 0

ROOT_CAUSE_HYPOTHESIS: H1
```

**Mechanism:** every orphan has both an entry in `lookup_condado_colors.json` AND a matching block of pixels in `lookup_condado.png` (px count == metadata `pixel_count`). But each orphan's `orig_idx` (e.g. tui=8, lamego=27, beja=64) does NOT equal its metadata position (`tui meta_ci=0, lamego meta_ci=7, beja meta_ci=17`). The legacy identity-fallback path inside `emit_territories_from_disk` (territories_geojson.py lines 230–239, taken when `original_condados is None`) writes `pc[mask] = orig_idx`; `build_territories_geojson` then enumerates `condados[0..n_meta-1]` and only matches features where `orig_idx == meta_ci`. Whenever they differ:

1. The orphan is silently dropped (no feature emitted for its id).
2. A different metadata entry "steals" its pixels via the identity collision (e.g. `viseu`/`coimbra`/`leiria`/`idanha`/`badajoz`/`lisboa`/`silves` survive in geojson but actually carry the geometry of `tui`/`porto`/`braga`/`viana`/`chaves`/`braganca`/`salamanca`).

The current production call site (`services/generator.py:361`) DOES pass `original_condados` — but this stale project was generated through a path that did not. The latent bug is the **silent drop** inside the fallback: any future call site or fixture that omits `original_condados` would recreate the same symptom unnoticed.

## Fix Implemented

### File modified for the fix
**`backend/medieval_forge/services/territories_geojson.py`**

1. **`emit_territories_from_disk` legacy fallback (lines ~245–267):** the previous `logger.warning(...) + continue` for `idx >= len(condados)` is now a `raise ValueError(...)` with an actionable message instructing callers to pass `original_condados`. Production behaviour unchanged — only callers that omit the parameter AND have out-of-range indices are affected.

2. **`build_territories_geojson` (after the neighbours loop):** added a soft-assertion log:
   ```python
   meta_ids = {c[0] for c in condados}
   feat_ids = {f["id"] for f in features}
   missing = meta_ids - feat_ids
   if missing:
       logger.error(
           "territories.geojson MISSING %d condados from metadata: %s",
           len(missing), sorted(missing)[:10],
       )
   ```
   Soft (no raise) so legitimate generation failures still write a usable file, but the orphan list shows up loudly in the server log.

### Existing test updated
**`backend/tests/test_territories_geojson.py`** — `test_emit_territories_from_disk_out_of_range_idx_skipped_not_crashed` renamed to `..._raises` and now asserts `pytest.raises(ValueError, match="out of range")` instead of asserting silent skip.

## Regression Tests

**File:** `backend/tests/services/test_territories_geojson_consistency.py` (4 tests, all PASS post-fix; tests 1 and 3 would FAIL on the pre-fix code at `21e6614^`):

| # | Test | Asserts |
|---|------|---------|
| 1 | `test_metadata_and_geojson_have_matching_condado_ids_when_original_condados_passed` | `set(meta_ids) == set(feature_ids)` for the exact bug pattern (orig_idx 27, 28 > len(meta)=3) when `original_condados` is passed |
| 2 | `test_metadata_and_geojson_have_matching_condado_ids_via_build_geojson_directly` | Direct `build_territories_geojson` invariant, no PNG roundtrip |
| 3 | `test_legacy_fallback_raises_on_out_of_range_orig_idx` | `ValueError("...out of range...")` raised when `original_condados` omitted and an orig_idx exceeds `len(condados)` |
| 4 | `test_orphan_invariant_logs_when_metadata_condado_has_no_pixels` | `caplog` captures ERROR with "MISSING" and the orphan id when a metadata entry has no pixels in pc |

## Verification

1. **Diagnostic script before/after:** Run against `2d402c81-0b72-4cbb-8b61-21d72eff2a44`:
   - Before fix + repair: `n_metadata=19  n_geojson=7  orphans=12  ROOT_CAUSE_HYPOTHESIS: H1`
   - After re-running `emit_territories_from_disk` with the centroid-inferred `original_condados` list (in-session repair): `n_metadata=19  n_geojson=19  orphans=0  no orphans`
2. **Test suite:** `pytest backend/tests/test_territories_geojson.py backend/tests/services/test_territories_geojson_consistency.py -v` → 14/14 pass.
3. **Manual capital-drag verification on previously-orphaned condados (braganca, lamego, etc.):** Not run end-to-end in this session — requires a fresh full generation through the FastAPI background task to populate the new geojson with all 19 features. The repair script above demonstrated the fix works on the existing on-disk artifacts; a fresh project regenerated through the production path (`services/generator.py:_run_pipeline_sync`) will hit the corrected code path on first emission.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Updated existing test to match new fail-loud contract**
- **Found during:** Task 3 (implementing the H1 fix)
- **Issue:** `test_emit_territories_from_disk_out_of_range_idx_skipped_not_crashed` asserted the silent-skip behaviour that the fix explicitly removes — leaving it would either (a) keep the silent-skip behaviour the bug requires us to delete, or (b) be a permanent test failure.
- **Fix:** Renamed to `test_emit_territories_from_disk_out_of_range_idx_raises` and switched to `pytest.raises(ValueError, match="out of range")` with a docstring explaining the contract change.
- **Files modified:** `backend/tests/test_territories_geojson.py`
- **Commit:** `21e6614`

**2. [Rule 3 — Blocking] Diagnostic-script classification refinement**
- **Found during:** Task 1
- **Issue:** First-pass diagnostic classified the orphans as `MIXED (H1=5, H3=7)` because the H1 bucket only checked `orig_idx >= n_meta`. In reality, even orphans whose `orig_idx < n_meta` are still H1 (the legacy fallback maps `orig_idx` → wrong meta_ci position; their pixels get assigned to whichever condado happens to sit at that meta_ci slot).
- **Fix:** Refined the H1 classifier to check `orig_idx != meta_ci` (the orphan's own position in metadata) rather than just out-of-range.
- **Files modified:** `scripts/diagnose_orphans.py`
- **Commit:** `7707fd0`

### Decision Deviation from PLAN's H1 Branch Description

The PLAN's H1 branch said "identify the mutation in map_generator.py lines 1027–1033 and either move metadata export BEFORE the mutation or compute pc snapshot." That description assumed an in-process pc mutation between the lookup-PNG write and metadata export — but the diagnostic showed the mutation is actually an INDEX-SPACE mismatch in the read-back path (`emit_territories_from_disk`), not in `map_generator`. The real fix lives in the wrapper module, not `lib/map_generator.py`. `lib/map_generator.py` was NOT modified — preserving the D-04 "vendored black box" constraint.

## Follow-ups

1. **Stale project repair:** the repaired `territories.geojson` for project `2d402c81` is in place on disk (in-session repair). Other projects generated before commit `acb85bc` (the original Problem B fix) may have the same orphan pattern — the user can run `diagnose_orphans.py <uuid>` against any project to check, and a regeneration via the API will produce a clean geojson with the new code.
2. **UAT bug #4 (manual-provider stale research):** the diagnostic intentionally has an `H4` bucket. None of the 12 orphans in the test project hit it, so this quick task does NOT touch UAT bug #4. If a future project shows `H4 manual mismatch > 0`, that becomes a separate task targeting the manual-provider `condados_assignment` parsing path.
3. **Soft-assertion log monitoring:** the new `logger.error("territories.geojson MISSING %d condados ...")` line should be watched in production logs after the next few generations. Any non-empty hit is a regression even if no user complains.

## Self-Check: PASSED

- `scripts/diagnose_orphans.py` exists ✓
- `backend/tests/services/test_territories_geojson_consistency.py` exists ✓
- Commit `7707fd0` (diagnostic) ✓
- Commit `21e6614` (fix) ✓
- Commit `3095107` (regression tests) ✓
- 14/14 territories_geojson tests pass ✓
- Diagnostic prints `no orphans` after in-session repair ✓
