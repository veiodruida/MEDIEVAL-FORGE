---
phase: 02
plan: 03
subsystem: live-ingestion-parity
tags: [parity, live-osm, snapshot, xfail, deferred, waiver, phase-02.1]
requires:
  - phase-02-plan-01 (ProjectDataset contract + cfg.dataset migration)
  - phase-02-plan-02 (build_dataset_from_osm + split-by-ISO + terrain stub)
provides:
  - backend/tests/parity/test_iberia_868_live.py (xfail-marked, 10 tests intact)
  - scripts/refresh_live_snapshot.py (manual refresh entrypoint)
  - tests/fixtures/iberia_868/live-ingestion/ (committed post-adapter snapshot)
  - .planning/phases/02-ingestion-adapter/D-09-LIVE-WAIVER.md (4-option waiver doc)
  - Phase 02.1 backlog entry (ROADMAP.md)
affects:
  - backend/tests/parity/test_iberia_868_live.py
  - backend/medieval_forge/services/pipeline/adapters/osm.py
  - scripts/refresh_live_snapshot.py
  - tests/fixtures/iberia_868/live-ingestion/{pt_concelhos_live.geojson, es_municipalities_live.geojson, README.md}
  - .planning/phases/02-ingestion-adapter/D-09-LIVE-WAIVER.md
  - .planning/ROADMAP.md
tech-stack:
  added: []
  patterns:
    - "module-level pytestmark = [pytest.mark.parity, pytest.mark.xfail(strict=False, reason=...)] — preserves the green-when-fixed signal across all 10 parametrized entries without skipping"
    - "snapshot is dormant evidence: tests/fixtures/iberia_868/live-ingestion/ stays in tree to make Phase 02.1 immediately re-runnable when the parity contract is re-opened"
    - "structural-divergence waiver pattern (D-09-LIVE-WAIVER.md): when an empirical reality contradicts a planning premise, document evidence + options + decision in a phase-local waiver doc and defer to a follow-up phase rather than mutate the assertion"
key-files:
  created:
    - .planning/phases/02-ingestion-adapter/02-03-SUMMARY.md
    - .planning/phases/02-ingestion-adapter/D-09-LIVE-WAIVER.md (commit d908e1d, written during checkpoint)
    - backend/tests/parity/test_iberia_868_live.py (commit e254b97, plus xfail in f124d06)
    - scripts/refresh_live_snapshot.py (commit e254b97, plus cp1252 fix in 0943dfc)
    - tests/fixtures/iberia_868/live-ingestion/pt_concelhos_live.geojson (commit ccc947b)
    - tests/fixtures/iberia_868/live-ingestion/es_municipalities_live.geojson (commit ccc947b)
    - tests/fixtures/iberia_868/live-ingestion/README.md (commit e254b97)
  modified:
    - backend/medieval_forge/services/pipeline/adapters/osm.py (commit 2044bac, per-ISO admin_level fix)
    - .planning/ROADMAP.md (commit d61785d, Phase 02.1 backlog entry)
    - .planning/STATE.md (this run, advance past Plan 02-03 + record Phase 02 closeout with SC-1 deferred)
decisions:
  - "Plan 02-03 closed with Option C (defer + xfail) — user-approved decision after the waiver-loop premise was empirically falsified (see D-09-LIVE-WAIVER.md §Recommendation: planner recommended Option B; user picked Option C)"
  - "ROADMAP-02#1 NOT marked complete — explicitly deferred to Phase 02.1 (status: backlog in ROADMAP.md)"
  - "Phase 02 closes with SC-2 + SC-3 met (Plans 01, 02, 04) and SC-1 deferred to Phase 02.1; the deferral is recorded in ROADMAP.md and not silently absorbed into 'Phase 02 complete'"
  - "xfail strictness: strict=False — mountains_mask / rivers_overlay / pass-through JSONs already pass (terrain D-13 stub) and would XPASS; strict=True would fail the suite on those, defeating the green-when-fixed contract"
  - "10 tests preserved (no skip, no delete) so Phase 02.1's first task can simply remove the xfail marker and observe a true green/red signal under the chosen contract"
  - "D-09..D-12 implementation status: D-09 (no-network in CI) and D-10 (snapshot location) honored; D-11 (one golden, two paths) and D-12 (post-adapter GeoJSON snapshot) honored *as built*, but the assertion itself (vendored-golden as live's expected output) is the premise that did not survive contact with reality, hence the deferral"
metrics:
  duration: ~total Plan 02-03 (Tasks 1-2-3 + closeout this session)
  completed: 2026-05-08
  tasks_total: 3
  tasks_completed: 3
  files_created: 6
  files_modified: 3
  parity_phase01_pre_close: "10/10 green (commit f124d06 immediate predecessor)"
  parity_phase01_post_close: "10/10 green (verified this session)"
  parity_live_pre_xfail: "4/10 passed, 6/10 failed"
  parity_live_post_xfail: "4 xpassed, 6 xfailed (strict=False); 0 failed; suite exit 0"
requirements:
  - ROADMAP-02#1 (DEFERRED to Phase 02.1)
---

# Phase 02 Plan 03: Live-Ingestion Parity (Defer + xfail) Summary

Closed with Option C — defer + xfail — after Plan 02-03's locked waiver-loop strategy
was empirically falsified. Vendored fixture (`es-atlas@0.6.0` ES + IGE PT concelhos)
and live OSM (`admin_level=8/ES`, `admin_level=7/PT`) are different upstream sources,
not different snapshots of the same source. Live cardinality (PT 348, ES 8179)
structurally exceeds vendored cardinality (PT ~278, ES ~3000) at every admin tier
and no number of refreshes can converge them to byte-equality vs `golden/`.
ROADMAP-02#1 is therefore unverified (not failed) and deferred to a follow-up
Phase 02.1 ("Resolve live-ingestion parity contract") whose first task will pick
one of the rejected options (split golden, curate snapshot, in-pipeline cardinality
match, or another) once the v3 vision on "what live should match" is sharper.

## What was built across the plan

| Task | Output | Commit |
|------|--------|--------|
| Task 1 (auto) | `backend/tests/parity/test_iberia_868_live.py` (10 parametrized entries mirroring `test_iberia_868.py`'s assertions); `scripts/refresh_live_snapshot.py` (manual entrypoint, no auto-commit, prints `git add`/`git commit` hints); `tests/fixtures/iberia_868/live-ingestion/README.md` (D-09/D-10/D-12 + waiver-loop ritual) | `e254b97` |
| Task 2 (checkpoint:human-action) | Initial OSM Overpass refresh — surfaced two correctness defects requiring auto-fix; landed snapshot files | `2044bac` (adapter fix), `0943dfc` (refresh script fix), `ccc947b` (snapshot bytes), `d908e1d` (waiver doc), `d2be218` (state blocker recorded) |
| Task 3 (auto, this session) | `xfail` markers on the live parity test (`f124d06`); Phase 02.1 backlog entry in ROADMAP.md (`d61785d`); this SUMMARY (`docs(02-03)` commit below); STATE/ROADMAP advance | `f124d06`, `d61785d`, plus this commit |

## Verification (this session, post-xfail)

| Check | Command | Result |
|-------|---------|--------|
| Live parity reports xfail/xpass cleanly (no `failed`) | `py -3.14 -m pytest backend/tests/parity/test_iberia_868_live.py -m parity --no-header -v` | **6 xfailed, 4 xpassed, 2 warnings in 36.40s** — exit 0 |
| Phase 01 parity unaffected | `py -3.14 -m pytest backend/tests/parity/test_iberia_868.py -m parity --no-header -x` | **10 passed, 2 warnings in 33.73s** |
| Per-test breakdown | (from above run) | XFAIL: lookup_barony.png, lookup_condado.png, visual_condado.png, visual_barony.png, lookup_barony_colors.json, territory_metadata.json. XPASS: mountains_mask.png, rivers_overlay.png (terrain D-13 pass-through), lookup_condado_colors.json (incidental hash collision space match), mountain_river_data.json (terrain pass-through). |
| ROADMAP.md Phase 02.1 entry exists | `grep "Phase 02.1" .planning/ROADMAP.md` | 1 match (status: backlog) |

The XPASS distribution is the expected signature from D-09-LIVE-WAIVER.md §3 and §4
(terrain layers are vendored pass-through; cardinality-derived layers diverge).
Anything else would have indicated a marker-application bug; this matches the
documented evidence exactly.

## Decision coverage

| Decision | Status | Implementation / Note |
|----------|--------|----------------------|
| D-09 (no network in CI) | DONE | Live test reads only the committed snapshot; no httpx/Overpass call in CI. The xfail does not change this. |
| D-10 (snapshot location) | DONE | `tests/fixtures/iberia_868/live-ingestion/` populated; README.md ships there. |
| D-11 (two paths, one expected output) | **PARTIAL — DEFERRED** | Implementation built (live test asserts vs same `golden/` as `test_iberia_868.py`), but the *expectation* that vendored-golden is reachable from live OSM is the premise that did not survive contact with reality. Phase 02.1 re-opens the assertion target. |
| D-12 (snapshot is post-adapter GeoJSON) | DONE | Snapshot files are post-`_split_by_iso` GeoJSON FeatureCollections, not raw Overpass JSON. |
| D-13 (terrain stub passthrough) | DONE (Plan 02-02 carry-forward) | Live test consumes vendored `mountain_river_data.json` — confirmed by the 4 XPASS results (terrain layers pass byte-equality precisely because they ARE pass-through). |
| Waiver-loop strategy (option (d) in plan `<approach>`) | **OVERRIDDEN** | See D-09-LIVE-WAIVER.md. Replaced by Option C (defer + xfail). |
| ROADMAP-02#1 ("Phase 01 parity stays green when input is live ingestion") | **DEFERRED** | Phase 02.1, not marked complete in REQUIREMENTS/ROADMAP. |

## Deviations from Plan

### 1. [Rule 1 - Bug] Per-ISO admin_level was wrong in OSM adapter
- **Found during:** Task 2 initial Overpass call (refresh script's first invocation).
- **Issue:** Adapter defaulted to `admin_level=6` for both ISOs. In Iberia, `admin_level=6` is `distrito` (PT) / `provincia` (ES) — too coarse. Vendored fixture is concelho (PT, ~278 features) / municipio (ES, ~3000 in `es-atlas@0.6.0` curation). Adapter cardinality was orders of magnitude off.
- **Fix:** Per-ISO `admin_level`: PT=7 (concelho), ES=8 (municipio). Matches the vendored tier even though raw OSM ES `admin_level=8` produces ~8179 (the cardinality delta is the structural divergence below; the *tier choice* is now correct).
- **Files modified:** `backend/medieval_forge/services/pipeline/adapters/osm.py`.
- **Commit:** `2044bac`.

### 2. [Rule 3 - Blocking] Refresh script crashed on Windows cp1252 stdout
- **Found during:** Task 2 Overpass call on Windows shell.
- **Issue:** `build_dataset_from_osm`'s SSE-style queue messages contained non-ASCII characters (em-dash, accented Portuguese names). Default Windows console encoding is `cp1252`; bare `sys.stdout.write(msg)` raised `UnicodeEncodeError` mid-stream and aborted the refresh.
- **Fix:** `_drain` writes via `sys.stdout.buffer.write(msg.encode("utf-8", errors="replace"))` (bytes path bypasses the cp1252 codec). Documented in the refresh script's docstring.
- **Files modified:** `scripts/refresh_live_snapshot.py`.
- **Commit:** `0943dfc`.

### 3. [Rule 1 - Plan ambiguity] Waiver-loop strategy empirically falsified — escalated via D-09-style waiver doc
- **Found during:** Task 2 verification (live parity ran 6/10 fail after the corrected adapter).
- **Issue:** Plan 02-03 `<approach>` locked the waiver-loop strategy ("if test fails, snapshot is wrong, refresh until green; never relax SSIM"). Empirical reality from a clean post-fix Overpass fetch (PT 348, ES 8179) showed live OSM is **structurally larger** than the vendored fixture (`es-atlas@0.6.0` ES ~3000 + IGE PT ~278) regardless of when fetched. They are different curations of the same domain, not different snapshots of the same source. A second clean fetch cannot converge them.
- **Fix:** Filed `.planning/phases/02-ingestion-adapter/D-09-LIVE-WAIVER.md` (Plan 02-03 `<approach>` premise + 4 evidence points + 4 options re-opened from the rejected list). Paused execution and surfaced the decision to the user. User chose Option C (defer + xfail) over the planner's Option B recommendation (split golden) — Option C carries the smallest immediate footprint and unblocks Phase 03/04 work without committing to a parity-contract redesign before the v3 vision is sharper.
- **Implementation (this session):** Module-level `pytest.mark.xfail(strict=False, reason=...)` on `test_iberia_868_live.py` + Phase 02.1 backlog entry in ROADMAP.md + this SUMMARY closing Plan 02-03 with explicit SC-1 deferral.
- **Files modified:** `backend/tests/parity/test_iberia_868_live.py`, `.planning/ROADMAP.md`, this SUMMARY.
- **Commits:** `d908e1d` (waiver doc), `d2be218` (state blocker), `f124d06` (xfail markers), `d61785d` (ROADMAP Phase 02.1), plus the SUMMARY commit below.

## Phase 02 closeout — ROADMAP-02 success criteria

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Phase 01 parity test stays green when input is "live ingestion" instead of fixture snapshot | **DEFERRED to Phase 02.1** | Premise empirically falsified — see D-09-LIVE-WAIVER.md. Test xfail-marked (`f124d06`); ROADMAP-02#1 NOT marked complete; Phase 02.1 backlog entry registered in ROADMAP.md (`d61785d`). Phase 01 fixture-path parity 10/10 green throughout. |
| 2 | `services/pipeline/contracts.py` defines `ProjectDataset` consumed by both fixture and live paths | **DONE** (Plan 02-01) | `ProjectDataset` `@dataclass`; `cfg.dataset` consumed by `landmask.py`, `render.py`, `__init__.py`; `iberia_config()` builds vendored variant. |
| 3 | Adapter functions wrap (don't rewrite) `ingest_wikidata`, `ingest_osm`, `overpass_client`, `ingest_terrain` | **DONE** (Plan 02-02 + 02-04) | `services/pipeline/adapters/osm.py` wraps `fetch_municipalities` (D-05); `terrain.py` returns vendored Path stub (D-13); `ingest_wikidata.py` deliberately not wrapped (D-15); v3 SSE endpoint wires the adapter into HTTP (Plan 02-04). |

**Phase 02 closeout call:** SC-2 and SC-3 are met. SC-1 is deferred to Phase 02.1
with the deferral explicitly recorded in ROADMAP.md (Phase 02.1 backlog entry,
status: `backlog`) and in this SUMMARY. ROADMAP-02#1 is **not** marked complete
in REQUIREMENTS — Phase 02.1 carries the resolution forward.

## All commits in Plan 02-03 (chronological)

| Commit | Subject |
|--------|---------|
| `e254b97` | `test(02-03): add live-ingestion parity test + refresh script` |
| `2044bac` | `fix(02-02): per-ISO admin_level in OSM adapter (PT=7, ES=8)` |
| `0943dfc` | `fix(02-03): refresh script tolerates Windows cp1252 stdout` |
| `ccc947b` | `docs(parity): refresh live snapshot — fix admin_level per ISO` |
| `d908e1d` | `docs(02-03): D-09-style waiver — live OSM cardinality structural divergence` |
| `d2be218` | `docs(state): record D-09 live-waiver blocker for Plan 02-03` |
| `f124d06` | `test(02-03): xfail live parity test pending Phase 02.1` |
| `d61785d` | `docs(roadmap): add Phase 02.1 backlog — resolve live-ingestion parity contract` |
| (this) | `docs(02-03): close plan with Option C summary (defer + xfail)` |

## Self-Check: PASSED

Verified post-write:
- FOUND: backend/tests/parity/test_iberia_868_live.py (xfail-marked at module level)
- FOUND: scripts/refresh_live_snapshot.py
- FOUND: tests/fixtures/iberia_868/live-ingestion/pt_concelhos_live.geojson
- FOUND: tests/fixtures/iberia_868/live-ingestion/es_municipalities_live.geojson
- FOUND: tests/fixtures/iberia_868/live-ingestion/README.md
- FOUND: .planning/phases/02-ingestion-adapter/D-09-LIVE-WAIVER.md
- FOUND: ROADMAP.md Phase 02.1 entry (status: backlog)
- FOUND commit e254b97, 2044bac, 0943dfc, ccc947b, d908e1d, d2be218, f124d06, d61785d
- Live parity: 6 xfailed + 4 xpassed (suite exit 0; no `failed`)
- Phase 01 parity: 10/10 green (33.73s, post-xfail)
- ROADMAP-02#1 NOT marked complete (deferred to Phase 02.1, per user decision)
