---
phase: 02-ingestion-adapter
verified: 2026-05-08T00:00:00Z
status: passed
score: 2/2 verifiable must-haves verified; 1 deferred to Phase 02.1
overrides_applied: 0
deferred:
  - truth: "Phase 01 parity test stays green when input is 'live ingestion' instead of fixture snapshot (ROADMAP-02 SC-1)"
    addressed_in: "Phase 02.1 (Resolve live-ingestion parity contract)"
    evidence: |
      Premise empirically falsified — see `.planning/phases/02-ingestion-adapter/D-09-LIVE-WAIVER.md`.
      Vendored fixture (`es-atlas@0.6.0` ES + IGE PT concelhos) and live OSM (admin_level=7/PT, 8/ES) are
      different upstream sources (cardinality: PT 348 vs ~278; ES 8179 vs ~3000), so byte-equality vs
      `golden/` is structurally unreachable. User chose Option C (defer + xfail) over Option B (split
      golden). Live test is xfail-marked at module level (commit `f124d06`, strict=False; observed
      6 xfailed + 4 xpassed, suite exit 0). Phase 02.1 backlog entry registered in ROADMAP.md
      (commit `d61785d`, status: backlog) with three specific success criteria:
      (1) pick + document a live-parity contract option; (2) remove xfail markers and report passed;
      (3) mark ROADMAP-02#1 complete or formally retire it.
---

# Phase 02: Ingestion Adapter — Verification Report

**Phase Goal:** "The existing v1 ingestion (Wikidata/OSM/Overpass/DEM/HydroSHEDS) produces inputs that the v3 pipeline accepts unchanged."
**Verified:** 2026-05-08
**Status:** passed (with 1 success criterion explicitly deferred to Phase 02.1)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP-02 Success Criteria)

| #   | Truth (Roadmap Success Criterion) | Status     | Evidence       |
| --- | --------------------------------- | ---------- | -------------- |
| 1   | Phase 01 parity test stays green when input is "live ingestion" instead of fixture snapshot | DEFERRED to Phase 02.1 | Empirical premise falsified (see D-09-LIVE-WAIVER.md). Live test xfail-marked (`f124d06`, strict=False); observed 6 xfailed + 4 xpassed (suite exit 0, no failures). Phase 01 fixture-path test stays 10/10 green. ROADMAP.md Phase 02.1 entry exists (status: backlog, commit `d61785d`). User-approved Option C carries forward as a backlog phase, not a failed gate. |
| 2   | `services/pipeline/contracts.py` defines `ProjectDataset` consumed by both fixture and live paths | VERIFIED | `contracts.py:27-42` declares `@dataclass ProjectDataset` with the 4 D-04 fields (`pt_geojson: Path`, `es_input: Path`, `mountain_river_json: Path`, `dem_raster: Optional[Path] = None`). Fixture path: `regions.py:45-49` constructs vendored ProjectDataset; consumed in `landmask.py:156` (`cfg.dataset.pt_geojson`), `landmask.py:162` (`cfg.dataset.es_input`), `render.py:181`, `render.py:229`, `__init__.py:174` (all `cfg.dataset.mountain_river_json`). Live path: `adapters/osm.py:185-189` constructs ProjectDataset from OSM, consumed by the same 5 sites. Phase 01 parity 10/10 green confirms the contract works end-to-end. |
| 3   | Adapter functions wrap (don't rewrite) `ingest_wikidata`, `ingest_osm`, `overpass_client`, `ingest_terrain` | VERIFIED (with documented D-13 / D-15 carve-outs) | `adapters/osm.py:18` imports `from medieval_forge.services.ingest_osm import fetch_municipalities` (D-05 wrap evidence). `overpass_client` wrapped transitively through `ingest_osm`. `ingest_terrain`: D-13 stub passthrough — `adapters/terrain.py:18-29` returns vendored `mountain_river_data.json` Path; zero `ingest_terrain` imports in `adapters/` (only the docstring mention). `ingest_wikidata`: D-15 user-approved carve-out — deliberately NOT wrapped in v3; legacy v1 path remains alive until Phase 03 deletes the stepper. Both v1 modules are unchanged (`git diff` empty for `services/ingest_osm.py`, `overpass_client.py`, `ingest_terrain/`, `ingest_wikidata.py`). |

**Score:** 2/2 verifiable must-haves verified; 1 deferred to Phase 02.1 (not a gap)

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|--------------|----------|
| 1 | Phase 01 parity test stays green when input is live ingestion (ROADMAP-02 SC-1) | Phase 02.1 | ROADMAP.md Phase 02.1 entry, status: backlog (commit `d61785d`). Three success criteria listed, including "remove xfail markers and report passed under the new contract". D-09-LIVE-WAIVER.md documents 4 options re-opened from RESEARCH Open Q1; user picked Option C (defer + xfail) on 2026-05-08. |

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `backend/medieval_forge/services/pipeline/contracts.py` | `ProjectDataset` @dataclass + updated RegionConfig | VERIFIED | Exists (181 lines); declares `ProjectDataset` (lines 27-42) with 4 D-04 fields; `RegionConfig.dataset` field present (line 70); 3 legacy path fields removed (verified by grep — 0 matches). |
| `backend/medieval_forge/services/pipeline/regions.py` | `iberia_config()` returning ProjectDataset-bearing RegionConfig | VERIFIED | Exists (90 lines); constructs `ProjectDataset(pt_geojson=…, es_input=…, mountain_river_json=…)` at lines 45-49; passes `dataset=dataset` to `RegionConfig(...)` at line 80. WR-01 fix anchors paths to repo root. |
| `backend/medieval_forge/services/pipeline/landmask.py` | `decode_geojson_municipalities` + extension-discriminated `load_municipalities` + fail-fast assert | VERIFIED | `cfg.dataset.pt_geojson` and `cfg.dataset.es_input` reads confirmed at lines 156 + 162. |
| `backend/medieval_forge/services/pipeline/adapters/__init__.py` | Public exports: `build_dataset_from_osm`, `build_terrain` | VERIFIED | 306 bytes; both exports importable per Plan 02 SUMMARY. |
| `backend/medieval_forge/services/pipeline/adapters/osm.py` | OSM-wrapping adapter with split-by-ISO partition | VERIFIED | 8332 bytes; imports `fetch_municipalities` (D-05 wrap, line 18); `_split_by_iso` uses `representative_point` (line 97); `_validate_bbox` enforces ≤30°/axis (lines 50-61); writes to `projects/<uuid>/inputs/` via `project_inputs_dir` (D-07); returns `ProjectDataset` with vendored `mountain_river_json` (D-13). |
| `backend/medieval_forge/services/pipeline/adapters/terrain.py` | Stub passthrough returning vendored `mountain_river_data.json` | VERIFIED | 1195 bytes; returns vendored Path (line 29); UUID validation on input; zero `ingest_terrain` imports. |
| `backend/medieval_forge/services/pipeline/adapters/base.py` | `project_inputs_dir` + atomic write re-export | VERIFIED | 753 bytes (per ls); per Plan 02 SUMMARY: `project_inputs_dir` validates UUID and creates `projects/<uuid>/inputs/`. |
| `backend/medieval_forge/api/v3/__init__.py` | v3 API package marker | VERIFIED | 74 bytes. |
| `backend/medieval_forge/api/v3/ingest.py` | v3 SSE ingest endpoint mirroring v1 `_sse_generator` | VERIFIED | 6920 bytes (188 lines); `router = APIRouter(prefix="/v3/projects", ...)` at line 29; `@router.get("/{project_id}/ingest")` at line 123; `_v3_sse_generator` with terminal None sentinel (line 109); `_adapter_producer` calls `build_dataset_from_osm` (line 71). UUID guard at line 140; 404/409/400 guards at lines 144-160. |
| `backend/medieval_forge/main.py` | v3 router registration | VERIFIED | `from .api.v3.ingest import router as v3_ingest_router` at line 57; `app.include_router(v3_ingest_router, prefix="/api")` at line 68. v1 router still mounted (line 60). |
| `backend/tests/unit/test_contracts.py` | ProjectDataset shape tests | VERIFIED | 1888 bytes; 3 tests passing per Plan 01 SUMMARY (verified empirically below). |
| `backend/tests/unit/test_regions.py` | iberia_config vendored-path tests | VERIFIED | 1693 bytes; 2 tests passing. |
| `backend/tests/unit/test_landmask_input_assert.py` | Missing-path FileNotFoundError tests | VERIFIED | 2583 bytes; 4 tests passing. |
| `backend/tests/unit/adapters/conftest.py` + `test_osm_split.py` + `test_terrain_passthrough.py` | Adapter unit tests | VERIFIED | 7 OSM split + 4 terrain stub tests passing. |
| `backend/tests/unit/api/test_v3_ingest.py` | v3 endpoint contract tests | VERIFIED | 6844 bytes; 6 tests passing (UUID guard, 404, 409, 400-no-bbox, happy-path, error-path). |
| `backend/tests/parity/test_iberia_868_live.py` | Live-input parity test (D-11) | VERIFIED-AS-XFAIL | 6913 bytes; module-level `pytestmark = [pytest.mark.parity, pytest.mark.xfail(strict=False, reason=...)]` (lines 49-59); references `golden_dir` fixture from conftest (9 occurrences); empirical run reports 6 xfailed + 4 xpassed (no `failed`). |
| `tests/fixtures/iberia_868/live-ingestion/{pt_concelhos_live.geojson, es_municipalities_live.geojson, README.md}` | Committed post-adapter snapshot | VERIFIED | 12 MB PT + 72 MB ES geojson tracked in git (`git ls-files` confirms 3 files); README.md documents D-09/D-10/D-12 + waiver-loop ritual. |
| `scripts/refresh_live_snapshot.py` | Manual snapshot refresh entrypoint | VERIFIED | 5002 bytes; cp1252-tolerant stdout (commit `0943dfc`); does not auto-commit per Plan 03 contract. |

### Key Link Verification

| From | To  | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `regions.py` | `contracts.py:ProjectDataset` | `from .contracts import ProjectDataset` | WIRED | Import at `regions.py:17`; ProjectDataset constructed at lines 45-49. |
| `landmask.py` | `cfg.dataset.pt_geojson` + `cfg.dataset.es_input` | direct attribute access | WIRED | `pt_path = cfg.dataset.pt_geojson` (line 156); `es_path = cfg.dataset.es_input` (line 162). |
| `render.py` + `__init__.py` | `cfg.dataset.mountain_river_json` | defensive named local (`mr_path = cfg.dataset.mountain_river_json if cfg.dataset is not None else None`) | WIRED | `render.py:181` + `render.py:229` + `__init__.py:174`. Plan 01 SUMMARY documents the named-local refactor. |
| `adapters/osm.py` | `ingest_osm.fetch_municipalities` | `from medieval_forge.services.ingest_osm import fetch_municipalities` | WIRED | Line 18 (D-05 wrap evidence); invoked once per ISO at line 149 with per-ISO admin_level. |
| `adapters/osm.py` | `country_boundaries.get_country_polygon` | `from medieval_forge.services.country_boundaries import get_country_polygon` | WIRED | Line 17; used in `_split_by_iso` at line 81. |
| `adapters/osm.py` | `paths.project_dir` (via `project_inputs_dir`) | `project_inputs_dir(project_id)` from `.base` | WIRED | Line 21 (`from .base import project_inputs_dir`); invoked at line 131. |
| `adapters/osm.py` | `contracts.ProjectDataset` | `from medieval_forge.services.pipeline.contracts import ProjectDataset` | WIRED | Line 19; returned at lines 185-189. |
| `api/v3/ingest.py` | `adapters/osm.py:build_dataset_from_osm` | `from ...services.pipeline.adapters.osm import build_dataset_from_osm` | WIRED | Line 26; invoked in `_adapter_producer` at line 71. |
| `api/v3/ingest.py` | `paths.is_valid_uuid` | `from ...services.paths import is_valid_uuid` | WIRED | Line 25; UUID guard at line 140. |
| `api/v3/ingest.py` | `countries.clip_iso_codes_for_qid` | `from ...services.countries import clip_iso_codes_for_qid` | WIRED | Line 24; invoked at line 169. |
| `main.py` | `api/v3/ingest.py:router` | `app.include_router(v3_ingest_router, prefix='/api')` | WIRED | Import at line 57; mount at line 68. |
| `tests/parity/test_iberia_868_live.py` | `tests/fixtures/iberia_868/live-ingestion/` | `LIVE_SNAPSHOT_DIR / "pt_concelhos_live.geojson"` | WIRED | Snapshot files exist (12 MB + 72 MB) and are tracked in git. |
| `tests/parity/test_iberia_868_live.py` | `tests/fixtures/iberia_868/golden/` | `golden_dir` fixture from `conftest.py` | WIRED | 9 grep references to `golden_dir`; same fixture as `test_iberia_868.py`. |
| `scripts/refresh_live_snapshot.py` | `adapters/osm.py:build_dataset_from_osm` | direct import | WIRED | Per Plan 03 SUMMARY; cp1252-tolerant stdout. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `contracts.py:ProjectDataset` | n/a (port type) | n/a | n/a — type, not consumer | n/a |
| `regions.py:iberia_config()` | `dataset` (ProjectDataset) | constructed from `_INPUTS_DIR` (vendored data tree) | YES — vendored files exist on disk; Phase 01 parity 10/10 confirms decode succeeds | FLOWING |
| `adapters/osm.py:build_dataset_from_osm` | `combined_features` → `by_iso` → `ProjectDataset` | wraps `fetch_municipalities` (real OSM Overpass when invoked) + writes via `_write_geojson_atomic` | YES — refresh script confirmed by Plan 03 Task 2 (PT 348 + ES 8179 features written) | FLOWING |
| `api/v3/ingest.py:trigger_v3_ingest` | `bbox`, `iso_codes` | `project.bbox_*` columns + `clip_iso_codes_for_qid(project.country_qid)` | YES — happy-path test verifies status transitions and stream content | FLOWING |
| `tests/parity/test_iberia_868_live.py:live_pipeline_output` | pipeline outputs (PNGs/JSONs) | `run_pipeline(cfg)` with `cfg.dataset` from snapshot | YES — pipeline runs and produces 12-file output; assertions reveal cardinality divergence (xfail expected per D-09 waiver) | FLOWING (but diverges from `golden/` per documented D-09 waiver) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Phase 01 parity (vendored path) stays 10/10 green | `pytest backend/tests/parity/test_iberia_868.py -m parity --no-header -q` | `10 passed, 2 warnings in 34.03s` | PASS |
| Phase 02 unit tests pass (contracts + regions + landmask + adapters + v3 ingest = 26 tests) | `pytest backend/tests/unit/test_contracts.py backend/tests/unit/test_regions.py backend/tests/unit/test_landmask_input_assert.py backend/tests/unit/adapters/ backend/tests/unit/api/test_v3_ingest.py --no-header -q` | `26 passed, 56 warnings in 0.18s` | PASS |
| Live parity reports xfail/xpass cleanly (no `failed`) | `pytest backend/tests/parity/test_iberia_868_live.py -m parity --no-header -q` | `6 xfailed, 4 xpassed, 2 warnings in 36.02s` (suite exit 0) | PASS |
| Legacy `cfg.<legacy_field>` reads fully removed | `grep -rn "cfg\.municipality_pt_geojson\|cfg\.municipality_es_topojson\|cfg\.mountain_river_json" backend/medieval_forge/services/pipeline/` | No matches | PASS |
| New `cfg.dataset.*` reads present (≥5) | `grep -rn "cfg\.dataset\.(pt_geojson\|es_input\|mountain_river_json)" backend/medieval_forge/services/pipeline/` | 5 matches across landmask.py (2) + render.py (2) + __init__.py (1) | PASS |
| v3 router registered alongside v1 | `grep` for `v3_ingest_router` and `ingest_router` in `main.py` | Both imports + both `include_router` calls present (lines 49/57/60/68) | PASS |
| No D-13/D-15 violations in adapters | `grep -rn "ingest_terrain\|ingest_wikidata" backend/medieval_forge/services/pipeline/adapters/` | 1 match (docstring comment in `terrain.py`, not an import) | PASS |
| Phase 02.1 backlog entry registered | `grep -c "Phase 02\.1" .planning/ROADMAP.md` | 1 match (status: backlog) | PASS |
| Live snapshot tracked in git | `git ls-files tests/fixtures/iberia_868/live-ingestion/` | 3 files: README.md + pt_concelhos_live.geojson + es_municipalities_live.geojson | PASS |

### Requirements Coverage

`.planning/REQUIREMENTS.md` does not exist in this repository (the ROADMAP.md "Requirement coverage (v3)" table at lines 110-122 plays its role). The PLAN frontmatter declares:

| Plan | `requirements` field | Mapping | Status |
| ---- | -------------------- | ------- | ------ |
| 02-01-PLAN | `ROADMAP-02#2` | SC-2 (`ProjectDataset` in `contracts.py`) | SATISFIED — verified above. |
| 02-02-PLAN | `ROADMAP-02#3` | SC-3 (adapter wrap-not-rewrite) | SATISFIED — `osm.py:18` wraps `fetch_municipalities`; `terrain.py` D-13 stub; D-15 carve-out (Wikidata) per CONTEXT.md. |
| 02-03-PLAN | `ROADMAP-02#1` | SC-1 (live parity) | DEFERRED to Phase 02.1 — see deferred items above. |
| 02-04-PLAN | `ROADMAP-02#3` | SC-3 (HTTP surface for the wrapped adapter) | SATISFIED — endpoint mounted, 6/6 unit tests pass. |

No orphaned requirements detected. The ROADMAP `V3-INGEST-ADAPTER` row maps to Phase 02 and is satisfied by SC-2 + SC-3 with SC-1 explicitly deferred to Phase 02.1.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `adapters/terrain.py` | 3 | "STAYS UNTOUCHED" comment mentions `ingest_terrain` (docstring only — no import) | Info | Triggers a grep hit for `ingest_terrain` but is not a violation; D-13 honored (no actual import). |
| `tests/parity/test_iberia_868_live.py` | 49-59 | Module-level `pytest.mark.xfail(strict=False)` | Info | Intentional — documents the deferral to Phase 02.1 with full traceability (D-09-LIVE-WAIVER.md, ROADMAP.md backlog entry). Not a stub or hidden failure: the empirical 6 xfailed + 4 xpassed pattern matches D-09-LIVE-WAIVER.md §3 predictions exactly, confirming the marker is correctly applied. |

No blockers, warnings, or stubs found. The two info-level items are documented design choices, not deviations.

### Human Verification Required

None. All claims were verified against the running codebase:
- Static checks: 0 stale `cfg.<legacy_field>` reads, 5 new `cfg.dataset.*` reads, both v1 + v3 routers registered, all key links wired.
- Empirical: Phase 01 parity 10/10 green; Phase 02 unit tests 26/26 green; live parity test produces the expected xfail/xpass pattern per the waiver doc.
- Documentation: D-09-LIVE-WAIVER.md, Phase 02.1 ROADMAP backlog entry, and Plan 03 SUMMARY all consistently document the deferral.

### Gaps Summary

No gaps. SC-2 and SC-3 are fully verified. SC-1 is explicitly deferred to Phase 02.1 with full traceability:
1. The dead waiver-loop premise is documented in `D-09-LIVE-WAIVER.md` with 4 evidence points.
2. The user-approved Option C (defer + xfail) is recorded in Plan 03 SUMMARY.
3. The Phase 02.1 backlog entry is committed in ROADMAP.md (`d61785d`) with three concrete success criteria for resolution.
4. The live test is preserved (10 parametrized entries, xfail strict=False) so Phase 02.1 can flip the marker and observe a true green/red signal under the chosen contract.

Per Step 9b: "Phase 02.1 ('Resolve live-ingestion parity contract')" matches the deferred item directly — its goal text and success criteria explicitly address the SC-1 contract. The deferral is therefore a legitimate filter, not a hidden gap.

Phase 02 closes with the goal achieved on the verifiable axes (contract defined and consumed by both paths; adapters wrap rather than rewrite). The live-parity contract design is the unfinished piece, and it is correctly scheduled as a follow-up phase.

---

_Verified: 2026-05-08_
_Verifier: Claude (gsd-verifier)_
