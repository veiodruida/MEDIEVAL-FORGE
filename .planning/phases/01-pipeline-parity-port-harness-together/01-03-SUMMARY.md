---
phase: 01-pipeline-parity-port-harness-together
plan: 03
subsystem: testing
tags: [pytest, parity, ssim, fixtures, ci, golden-baseline, refresh-tool]

# Dependency graph
requires:
  - phase: 01-pipeline-parity-port-harness-together (Plan 01-01, Plan 01-02)
    provides: "verbatim run_pipeline + RegionConfig + REGIONS['iberia_868']; in-tree input fixtures + initial golden snapshot"
provides:
  - "Parity test harness (10/10 green) at backend/tests/parity/test_iberia_868.py"
  - "Session-scoped pipeline_output / golden_dir fixtures (single ~35 s pipeline run per test session)"
  - "Refreshed iberia_868 golden baseline (verbatim port output, deterministic)"
  - "User-facing baseline-refresh tool: pytest plugin --refresh-baseline / --confirm flags"
  - "13 unit tests for the refresh tool (1.7 s, never touches real golden)"
  - "Non-skippable CI parity job — any parity failure now blocks merge"
  - "D-09 waiver: deployed Reconquista baseline abandoned, verbatim port adopted"
  - "v1 generator stack fully deleted (5 production files + 7 tests + main.py register edit)"
affects:
  - "Phase 02 (ingest adapter): inherits run_pipeline signature, RegionConfig contract, and parity gate"
  - "Phase 03 (canvas UI): inherits FastAPI / 503 SPA placeholder until npm run build emits static/"
  - "Phase 06 (export validation gate): owns terrain_lookup.png + terrain_types.json (deferred per P-2)"
  - "Reconquista game (D:\\Unity_Projects\\Reconquista\\Assets\\StreamingAssets\\Maps\\): MUST re-bake from fresh pipeline before next build (D-09 waiver downstream impact)"
  - "Future coverage-restoration plan: 60% gate currently broken at ~30%, deferred from this plan"

# Tech tracking
tech-stack:
  added:
    - "pytest plugin pattern (pytest_addoption + pytest_collection_modifyitems for the refresh tool)"
    - "scikit-image SSIM comparator for visual PNG parity"
  patterns:
    - "session-scoped pipeline_output fixture (single ~35 s run per test session)"
    - "diff-on-failure: writes DIFF_*.png next to pipeline_output for byte-mismatch triage"
    - "two-flag refresh policy: --refresh-baseline (dry-run by default) + --confirm (write)"
    - "synthetic 4×4 PNG / 1-key JSON fixtures for unit-testing PNG/JSON diff helpers without running the real pipeline"

key-files:
  created:
    - ".planning/phases/01-pipeline-parity-port-harness-together/D-09-WAIVER.md"
    - "backend/tests/unit/test_parity_refresh_tool.py (13 unit tests, 1.7 s)"
    - "backend/tests/parity/__init__.py (empty package marker)"
    - "backend/tests/parity/conftest.py (session fixtures + refresh plugin)"
    - "backend/tests/parity/test_iberia_868.py (10 parametrised parity tests)"
    - "backend/tests/unit/test_pipeline_module.py"
    - "backend/tests/unit/test_pipeline_cli.py"
    - "backend/tests/integration/test_app_boot.py"
  modified:
    - "tests/fixtures/iberia_868/golden/* (10 files refreshed from verbatim port)"
    - "tests/fixtures/iberia_868/golden/README.md (refresh policy + D-09 waiver pointer)"
    - ".github/workflows/ci.yml (parity non-skippable; coverage gate kept at 60% with TODO)"
    - ".gitignore (.coverage / .coverage.* / htmlcov/)"
    - "backend/medieval_forge/main.py (api.generate import + include_router removed)"
    - "backend/tests/integration/test_app_boot.py (relaxed to accept 503 SPA placeholder)"

key-decisions:
  - "D-09 waived: deployed Reconquista baseline abandoned because mtime-inconsistent (lookup_barony 15/04 vs lookup_condado 17/04); verbatim port output adopted as new golden"
  - "Refresh tool implemented as pytest plugin (Option 1) instead of standalone backend/scripts/ script — leverages existing session fixture, idiomatic, no new dir"
  - "Coverage gate kept at 60% (NOT raised to 85% as plan specified) — empirical 30% post-v1-deletion would block all future PRs; bump deferred to a follow-up plan"
  - "test_app_boot.py relaxed to accept 503 (frontend-not-built) — fresh checkout has no static/ dir; original 200-only assertion was unrunnable in CI"

patterns-established:
  - "Parity baselines refreshed only via the in-repo plugin tool, never by hand (D-10 + waiver requirement)"
  - "Every parity refresh ships with a justification doc under .planning/phases/.../D-09-WAIVER-*.md"
  - "Determinism MUST be verified before any refresh: run pipeline twice, diff -rq, get zero differences"
  - "Synthetic small-fixture unit tests for slow-pipeline tools — never invoke real pipeline in unit suite"

requirements-completed:
  - V3-PIPELINE-PARITY

# Metrics
duration: ~140min (initial Tasks 1+2 from agent a92ff13d; Tasks 3a/3b/4/5 from this resume)
completed: 2026-05-08
---

# Phase 01 Plan 03: Pipeline parity harness + v1 deletion + CI flip + golden refresh + refresh tool

**10/10 parity green against verbatim-port golden baseline (deployed Reconquista abandoned via D-09 waiver), plus user-facing pytest plugin (`--refresh-baseline --confirm`) for future controlled refreshes, plus non-skippable CI parity gate.**

## Performance

- **Duration:** ~140 min total (Tasks 1+2 from prior agent session ~90 min; Tasks 3a/3b/4/5 + integration fix this session ~50 min)
- **Started:** 2026-05-07 (Tasks 1+2 by agent a92ff13d58fff0123)
- **Completed:** 2026-05-08T09:31:47Z (this resume)
- **Tasks:** 4 plan tasks + 1 auto-fix (integration test) = 5 commits beyond the orchestrator prefix
- **Files modified:** 14 (10 golden + ci.yml + .gitignore + 2 test files) + 4 created (D-09-WAIVER, refresh-tool unit test, this SUMMARY, plus the existing parity files from 04a6e83)

## Accomplishments

- Plan tasks 1 & 2 (already committed before this session): v1 generator stack deleted, parity harness created.
- D-09 waiver: deployed Reconquista baseline proven mutually-inconsistent (mtime 15/04 vs 17/04 across barony/condado groups); verbatim port output adopted as new golden after determinism check (pipeline run twice, `diff -rq` = zero).
- 10 golden fixtures refreshed atomically with comprehensive evidence-based waiver doc.
- User-controllable baseline-refresh tool shipped as pytest plugin: `--refresh-baseline` (dry-run, default) + `--confirm` (write). Replaces parity test bodies on a per-parametrize basis so each file's diff is reported individually.
- 13-test unit suite for the refresh tool runs in 1.7 s without ever touching the real golden dir — explicit safety guard test asserts `_resolve_golden_dir` falls back to in-tree path only when no override is set.
- CI parity job flipped to non-skippable (`|| (echo …; exit 0)` tail removed); ROADMAP success criterion 3 met.
- Phase 00 SC-6 invariant restored: `test_app_boot` now passes on a fresh checkout (was failing because frontend `static/` dir is `npm run build` output, not git-tracked).

## Task Commits

1. **Task 1 — Delete v1 generator stack + main.py register edit** — `a9c2032` (chore) — pre-existing from agent a92ff13d
2. **Task 2 — Parity harness + unit + integration tests** — `04a6e83` (test) — pre-existing from agent a92ff13d
3. **Task 3a — Refresh iberia_868 golden baseline (D-09 waiver)** — `8dc0ae6` (fix)
4. **Task 3b — Add refresh_parity_baseline tool + 13 unit tests** — `d648dc0` (feat)
5. **Task 4 — Flip parity CI to non-skippable** — `a42c4c7` (feat)
6. **Auto-fix [Rule 1] — Relax test_app_boot for missing static/** — `89cd4b5` (fix)

**Plan metadata commit (this SUMMARY):** see final docs commit below.

## Files Created/Modified

### Created
- `.planning/phases/01-pipeline-parity-port-harness-together/D-09-WAIVER.md` — full evidence package + future refresh policy
- `backend/tests/unit/test_parity_refresh_tool.py` — 13 unit tests (PNG diff, JSON diff, refresh dry-run/confirm semantics, plugin smoke test, real-golden safety guard)
- (Pre-existing from 04a6e83) `backend/tests/parity/__init__.py`, `conftest.py`, `test_iberia_868.py`, `backend/tests/unit/test_pipeline_module.py`, `test_pipeline_cli.py`, `backend/tests/integration/test_app_boot.py`

### Modified
- `tests/fixtures/iberia_868/golden/lookup_barony.png` — refreshed (port output, sha `D557E8E6`)
- `tests/fixtures/iberia_868/golden/lookup_condado.png` — refreshed (sha `DD4EF02F`)
- `tests/fixtures/iberia_868/golden/lookup_condado_colors.json` — refreshed: 91 entries (was 92; lost manual-override `255,128,0` for Aveiro id 92)
- `tests/fixtures/iberia_868/golden/territory_metadata.json` — refreshed: 91 condados (was 92; Aveiro absent, current territory_data.py doesn't define it)
- `tests/fixtures/iberia_868/golden/visual_barony.png`, `visual_condado.png`, `mountains_mask.png`, `rivers_overlay.png` — refreshed (PNG headers vary; pixel content matches new pipeline output)
- `tests/fixtures/iberia_868/golden/lookup_barony_colors.json`, `mountain_river_data.json` — re-saved during refresh; SHA-256 unchanged (port output deep-equal to old golden)
- `tests/fixtures/iberia_868/golden/README.md` — points at D-09 waiver, documents the new refresh tool, lists updated file sizes
- `backend/tests/parity/conftest.py` — added refresh plugin (pytest_addoption + pytest_collection_modifyitems + helper functions), kept session fixtures unchanged
- `.github/workflows/ci.yml` — dropped `|| (echo …; exit 0)` placeholder tail from parity job; added TODO comment above coverage gate (kept at 60%)
- `.gitignore` — added `.coverage`, `.coverage.*`, `htmlcov/` (pytest-cov runtime artifacts)
- `backend/tests/integration/test_app_boot.py` — accept 200 OR 503 (frontend-not-built); validate 503 body is the SPA placeholder

## Decisions Made

- **Refresh tool design (Option 1: pytest plugin).** `backend/scripts/` doesn't exist yet; creating it just for this would be infrastructure-for-hypothetical-use. The pytest plugin approach piggybacks the existing session fixture (no duplicate pipeline runner), is the idiomatic snapshot-test convention, and is invoked with the same pytest command flow developers already use.
- **`--confirm` as a hard requirement.** Refresh dry-run is the default; `--confirm` is required for any actual write. Prevents typos / stale shell history from clobbering committed fixtures. Documented as a real UX requirement in the conftest module docstring and README.
- **Coverage gate left at 60% (not raised to 85% as plan specified).** Empirical post-v1-deletion coverage is 30%. Both 85% (planned) and 60% (existing) gates currently fail. Shipping either as part of this plan would block all future PRs on a known-broken metric. Surfaced in CI as a TODO comment + flagged here for a follow-up coverage-restoration plan.
- **`test_app_boot` relaxed to accept 503.** Fresh checkout has no `backend/medieval_forge/static/` dir (frontend bundle is `npm run build` output, not git-tracked). The Phase 00 SC-6 contract is "FastAPI BOOTS"; both 200 (built) and 503 (not built) prove the boot succeeded. The previous 200-only assertion was unrunnable on any clean clone.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 4 — Architectural] Coverage-gate bump from 60% → 85% deferred**
- **Found during:** Pre-Task-4 verification (manual run of `pytest backend/tests/unit/ --cov=medieval_forge --cov-fail-under=85`)
- **Issue:** Plan must_haves required raising the coverage gate to 85% in the same Task 4 commit as the CI flip. Empirical post-v1-deletion coverage is 30% (the deleted v1 unit tests covered surviving code paths in `paths.py`, `voronoi.py`, `ingest_*` services). Both the planned 85% gate AND the existing 60% gate currently fail.
- **Fix:** Left coverage gate at 60%; added a multi-line TODO comment in `.github/workflows/ci.yml` above the gate, citing this SUMMARY for rationale. The `|| (echo …; exit 0)` tail was still removed from the parity job per Task 4's primary deliverable.
- **Files modified:** `.github/workflows/ci.yml`
- **Verification:** `! grep -q "exit 0" .github/workflows/ci.yml` passes; `grep -q "Non-skippable from Phase 01" .github/workflows/ci.yml` passes; `grep -q "TODO(01-03 deviation)" .github/workflows/ci.yml` confirms the deferred-state visibility.
- **Committed in:** `a42c4c7` (Task 4 commit)
- **Recommendation:** A follow-up coverage-restoration plan is needed. The gap is bigger than this plan's scope and must address surviving-code coverage holistically (paths.py, voronoi.py, ingest services).

**2. [Rule 1 — Bug] test_app_boot.py asserted 200 unconditionally; fresh checkout returns 503**
- **Found during:** Final parity+integration verification run (after Task 4 CI flip commit)
- **Issue:** The integration test added in `04a6e83` (Plan 01-03 Task 2) asserted `r.status_code == 200` on `GET /`. On a fresh checkout, `backend/medieval_forge/static/` does not exist (it's `npm run build` output, not git-tracked), so the SPA catch-all in `main.py` returns 503 with a `"Frontend not built yet"` JSON body — by design. The test was passing in the prior agent's working tree because that tree happened to have a built `static/` dir; it would have failed in CI from day one.
- **Fix:** Relaxed assertion to `r.status_code in (200, 503)` and validated the 503 body matches the SPA-not-built placeholder (rules out generic 500 server errors masquerading as a "boot" success). Renamed test to `test_app_boots_and_root_returns_known_status` to match the new contract; updated the module docstring with the rationale.
- **Files modified:** `backend/tests/integration/test_app_boot.py`
- **Verification:** `pytest backend/tests/integration/test_app_boot.py -v` → 1 passed; full `pytest backend/tests/parity/ backend/tests/integration/ -m "parity or integration"` (the exact CI command) → 11 passed / 0 failed.
- **Committed in:** `89cd4b5`

**3. [Rule 2 — Missing critical] `.coverage` runtime artifact wasn't gitignored**
- **Found during:** Task 3b commit prep
- **Issue:** Running `pytest --cov=medieval_forge` (which we did to verify the 85% gate decision) creates a `.coverage` SQLite file in the repo root. It was untracked but at risk of being committed.
- **Fix:** Added `.coverage`, `.coverage.*`, `htmlcov/` to `.gitignore`. Removed any stray file before committing.
- **Files modified:** `.gitignore`
- **Verification:** `git status --short` shows `.coverage` no longer listed as untracked.
- **Committed in:** `d648dc0` (bundled with Task 3b refresh tool)

**4. [Rule 4 — Architectural] D-09 ("deployed wins") waived in favour of verbatim-port output**
- **Found during:** Task 3 checkpoint (prior agent session)
- **Issue:** Premise of D-09 fails because the deployed Reconquista files at `D:\Unity_Projects\Reconquista\Assets\StreamingAssets\Maps\` are mutually inconsistent (lookup_barony group from 15/04, lookup_condado group + territory_metadata from 17/04 — never re-baked together; intermediate generator state unrecoverable; id 92 color `(255,128,0)` is a manual paint, not algorithm output).
- **Fix:** Refreshed `tests/fixtures/iberia_868/golden/*` from a fresh, deterministic run of the verbatim Phase 01 port. Determinism verified by running pipeline twice and `diff -rq` (zero byte differences). Wrote `D-09-WAIVER.md` with full evidence package + future refresh policy.
- **Files modified:** all 10 files under `tests/fixtures/iberia_868/golden/` + `README.md` + new `D-09-WAIVER.md`
- **Verification:** `pytest backend/tests/parity/ -m parity` → 10/10 passed.
- **Committed in:** `8dc0ae6`
- **Downstream impact:** Reconquista's Unity-side `Assets/StreamingAssets/Maps/` MUST be re-baked from the fresh pipeline before the next game build. CLAUDE.md's "v3 reset" milestone already plans for this; this is the formal record.

**5. [Plan-scope addition] User-requested baseline-refresh tool**
- **Found during:** User decision at the Task 3 re-checkpoint ("quero poder controlar isto no futuro")
- **Issue:** Original plan deferred refresh tooling to a `.planning/quick/` task (CONTEXT §"Deferred Ideas"). User explicitly requested controllable mechanism in the same plan as the D-09 waiver.
- **Fix:** Added Task 3b — pytest plugin in `backend/tests/parity/conftest.py` with `--refresh-baseline` + `--confirm` flags, plus 13 unit tests in `backend/tests/unit/test_parity_refresh_tool.py`. Documented in `golden/README.md`.
- **Files modified:** `backend/tests/parity/conftest.py` (added plugin), `backend/tests/unit/test_parity_refresh_tool.py` (created), `tests/fixtures/iberia_868/golden/README.md` (already updated for D-09 waiver — the same edit also documents the tool)
- **Verification:** `pytest backend/tests/unit/test_parity_refresh_tool.py -v` → 13 passed (1.7 s); manual smoke test `pytest backend/tests/parity/ -m parity --refresh-baseline -s` shows per-file diff reports; `pytest backend/tests/parity/ -m parity` (no flag) still shows 10/10 green (no regression).
- **Committed in:** `d648dc0`

---

**Total deviations:** 5 (1 auto-fixed bug + 1 auto-fixed missing critical + 2 architectural decisions + 1 user-requested scope addition)

**Impact on plan:** The plan as written would have shipped a broken CI (85% gate vs 30% empirical) and an unrunnable integration test. Deferring the coverage bump and relaxing the integration test were necessary for correctness; the user-requested refresh tool extends the plan's scope but is squarely within Phase 01's responsibility (parity discipline). The D-09 waiver is the most material architectural change — it formally accepts that the v3 reset milestone breaks compatibility with the manually-edited shipping Unity artifacts; the in-tree golden is now the source of truth.

## Issues Encountered

- **Pipeline ran on Python 3.14, not 3.12.** `pip` and `python` on this Windows machine point at different interpreters; the package was installed in py3.14 but `python` resolves to py3.12. Used `py -3.14` explicitly throughout. Documented in `golden/README.md` invocation examples; no source-level fix needed (pyproject.toml's `requires-python = ">=3.11"` accepts both).

- **First refresh-tool implementation broke parity test signature.** The `_make_refresh._runner` closure originally took only `(pipeline_output, golden_dir)`, but pytest still passes the parametrize argument `name` because the original test signature includes it. Fixed by accepting a `name` parameter (ignored — `target_name` is captured in the closure). Caught immediately by re-running parity with `--refresh-baseline`.

- **Frontend bundle absent on fresh checkout.** Found via the integration-test failure above. Not a regression; documented as the expected state (frontend is built by `npm run build` as a separate step). Fix is the relaxed assertion in `test_app_boot.py`.

## User Setup Required

None for this plan.

**Downstream user setup (Phase 02+ or pre-next-game-build):** The Reconquista game's `D:\Unity_Projects\Reconquista\Assets\StreamingAssets\Maps\` directory must be re-baked from the fresh v3 pipeline before the next game build. Until then, the shipping Unity client renders Aveiro using a manual-override color the pipeline no longer emits. See `D-09-WAIVER.md` §"Downstream impact".

## Next Phase Readiness

- **Parity gate locked.** Any PR (Phase 02+ included) that breaks the 10-file parity contract blocks merge automatically.
- **Refresh path documented.** Future Game Designer changes to `territory_data.py` (e.g. re-adding Aveiro with correct barony composition) flow through the same `--refresh-baseline --confirm` mechanism with a fresh waiver doc.
- **v3 pipeline package is stable.** `run_pipeline(cfg)` + `RegionConfig` + `REGIONS["iberia_868"]` are the public surface Phase 02's ingestion adapter wraps. Verified deterministic (two runs `diff -rq` clean).
- **Coverage debt:** the 60% gate is broken at 30%. Phase 02 should NOT block on this — it's separate work. A coverage-restoration plan is the recommended next quick task before any further unit-coverage gating.
- **Phase 00 SC-6 (FastAPI boots) holds.** Test passes on fresh checkout in both built and unbuilt states.

---

## Self-Check: PASSED

**Verified files exist:**
- `.planning/phases/01-pipeline-parity-port-harness-together/D-09-WAIVER.md` — FOUND
- `backend/tests/unit/test_parity_refresh_tool.py` — FOUND
- `backend/tests/parity/conftest.py` — FOUND (modified)
- `backend/tests/parity/test_iberia_868.py` — FOUND
- `tests/fixtures/iberia_868/golden/README.md` — FOUND (modified)
- All 10 golden files — FOUND (refreshed)

**Verified commits exist on `main`:**
- `a9c2032` chore(01-03) — FOUND
- `04a6e83` test(01-03) — FOUND
- `8dc0ae6` fix(01-03) golden refresh — FOUND
- `d648dc0` feat(01-03) refresh tool — FOUND
- `a42c4c7` feat(01-03) CI flip — FOUND
- `89cd4b5` fix(01-03) test_app_boot — FOUND

**Verified test outcomes:**
- `pytest backend/tests/parity/ -m parity` → 10 passed (35.24 s)
- `pytest backend/tests/integration/ -m integration` → 1 passed
- `pytest backend/tests/parity/ backend/tests/integration/ -m "parity or integration" --no-header` (exact CI command) → 11 passed
- `pytest backend/tests/unit/test_parity_refresh_tool.py` → 13 passed (1.7 s)
- `pytest backend/tests/unit/` → 73 passed
- `pytest backend/tests/parity/ -m parity --refresh-baseline -s` (dry-run smoke) → 10 passed; per-file `WOULD WRITE` reports printed; no fixture mutation.

**Verified CI workflow:**
- `! grep -q "exit 0" .github/workflows/ci.yml` — passes
- `grep -q "Non-skippable from Phase 01" .github/workflows/ci.yml` — passes
- `grep -q "TODO(01-03 deviation)" .github/workflows/ci.yml` — passes (broken-state visibility)

**Verified deletions intact (Task 1):**
- `! test -f backend/medieval_forge/api/generate.py` — passes
- `! test -f backend/medieval_forge/services/generator.py` — passes
- `! test -f backend/medieval_forge/lib/map_generator.py` — passes
- `! grep -rn "from .api.generate" backend/medieval_forge/` — empty

---

*Phase: 01-pipeline-parity-port-harness-together*
*Plan: 01-03*
*Completed: 2026-05-08*
