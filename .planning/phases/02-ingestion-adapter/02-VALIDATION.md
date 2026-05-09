---
phase: 02
slug: ingestion-adapter
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-08
audited_at: 2026-05-09
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (backend); pytest-asyncio for SSE/httpx tests |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` (markers: `unit`, `parity`, `integration`) |
| **Quick run command** | `pytest backend/tests/unit/adapters/ backend/tests/unit/api/test_v3_ingest.py -v` |
| **Full suite command** | `pytest backend/tests/unit/ backend/tests/parity/ -v -m "parity or not slow"` |
| **Estimated runtime** | ~30s unit; ~120s full (parity-iberia-868 dominates at 35s) |

---

## Sampling Rate

- **After every task commit:** Run quick command (unit-adapter + v3-ingest tests — under 1s post-warmup)
- **After every plan wave:** Run full suite (unit + parity)
- **Before `/gsd-verify-work`:** Full suite must be green; live parity test marked xfail per Phase 02.1 contract decision (commit `23cd5a1`)
- **Max feedback latency:** 30 seconds (per-task)

---

## Per-Task Verification Map

> Test paths corrected 2026-05-09: actual paths use `backend/tests/...` not `tests/...`. Test function names updated to match implementation.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | ROADMAP-02#2 | T-02-01-03 | ProjectDataset required fields enforced | unit | `pytest backend/tests/unit/test_contracts.py::test_project_dataset_required_fields_are_paths -v` | ✅ | ✅ |
| 02-01-02 | 01 | 1 | ROADMAP-02#2 | — | iberia_config returns vendored ProjectDataset | unit | `pytest backend/tests/unit/test_regions.py::test_iberia_config_returns_vendored_project_dataset -v` | ✅ | ✅ |
| 02-01-03 | 01 | 1 | ROADMAP-02#2 | T-02-01-01 | landmask fails fast on missing dataset paths | unit | `pytest backend/tests/unit/test_landmask_input_assert.py -v` | ✅ | ✅ |
| 02-02-01 | 02 | 2 | ROADMAP-02#3 | T-02-02-01, T-02-02-02 | OSM adapter splits PT/ES correctly + UUID/bbox guards | unit | `pytest backend/tests/unit/adapters/test_osm_split.py -v` | ✅ | ✅ |
| 02-02-02 | 02 | 2 | ROADMAP-02#3 | — | Terrain stub passthrough (D-13) | unit | `pytest backend/tests/unit/adapters/test_terrain_passthrough.py -v` | ✅ | ✅ |
| 02-03-01 | 03 | 2 | ROADMAP-02#1 | — | Vendored-path parity (Phase 01 contract) | parity | `pytest backend/tests/parity/test_iberia_868.py -v -m parity` | ✅ | ✅ (10/10 PASSED) |
| 02-03-02 | 03 | 2 | ROADMAP-02#1 | — | Live-path parity (post-adapter snapshot) | parity | `pytest backend/tests/parity/test_iberia_868_live.py -v` | ✅ | ⚠️ xfail (Phase 02.1 contract decision — live OSM structurally diverges from vendored es-atlas; deferred per `23cd5a1`) |
| 02-04-01 | 04 | 3 | ROADMAP-02#3 | T-02-04-01..05 | SSE endpoint contract: UUID gate, 404, 409, bbox gate, terminal sentinel, error path | unit | `pytest backend/tests/unit/api/test_v3_ingest.py -v` | ✅ | ✅ (6/6 PASSED) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky/xfail*

**Audit run 2026-05-09:**
- Unit (contracts + regions + landmask + adapters + v3-ingest): `pytest backend/tests/unit/...` — 26/26 PASSED in 0.21s
- Parity vendored path: `pytest backend/tests/parity/test_iberia_868.py -m parity` — 10/10 PASSED in 35.69s
- Parity live path: `test_iberia_868_live.py` xfail (deliberate, Phase 02.1 deferred contract)
- Total: 36/36 green; 1 xfail (documented).

---

## Wave 0 Requirements

- [x] `backend/tests/unit/adapters/__init__.py` — package marker
- [x] `backend/tests/unit/adapters/conftest.py` — shared synthetic Overpass GeoJSON fixture
- [x] `backend/tests/unit/adapters/test_osm_split.py` — split-by-ISO correctness
- [x] `backend/tests/unit/adapters/test_terrain_passthrough.py` — terrain stub passthrough (D-13)
- [x] `backend/tests/unit/test_contracts.py` — `ProjectDataset` shape + required-field assertion
- [x] `backend/tests/unit/test_regions.py` — `iberia_config()` returns ProjectDataset pointing at vendored es-atlas + pt_concelhos
- [x] `backend/tests/unit/test_landmask_input_assert.py` — missing path → FileNotFoundError at top of `landmask.py`
- [x] `backend/tests/unit/api/test_v3_ingest.py` — `/api/v3/projects/{id}/ingest` SSE stream contract (6 tests: UUID, 404, 409, bbox, success, adapter-raises)
- [x] `backend/tests/parity/test_iberia_868_live.py` — present with `pytest.mark.xfail` per Phase 02.1 contract decision
- [x] `tests/fixtures/iberia_868/live-ingestion/{pt_concelhos_live.geojson, es_municipalities_live.geojson, mountain_river_data_live.json}` — committed snapshot
- [x] `scripts/refresh_live_snapshot.py` — manual refresh entrypoint

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions | Status |
|----------|-------------|------------|-------------------|--------|
| Live OSM Overpass connectivity | ROADMAP-02#3 | D-09 forbids network in CI — runs once locally during snapshot refresh | `python scripts/refresh_live_snapshot.py --region iberia_868`; inspect `tests/fixtures/iberia_868/live-ingestion/` diff; commit if intended | ⬜ deferred (Phase 02.1 contract decision pending) |
| Live-path golden equivalence after snapshot refresh | ROADMAP-02#1 | Re-running pipeline against refreshed snapshot may legitimately diverge from `golden/` if OSM has improved data; needs human review | After refresh, run `pytest -m parity backend/tests/parity/test_iberia_868_live.py`; if fails, diff vs `golden/` and decide | ⬜ deferred (Phase 02.1) |
| SSE event payload schema review | ROADMAP-02#3 / D-14 | Schema invisible to Phase 01 parity gate; visual review for Phase 03 consumer | `curl -N http://localhost:8000/api/v3/projects/{uuid}/ingest`; inspect events in stdout | ⬜ Phase 03 dependency |

---

## Validation Audit 2026-05-09

| Metric | Count |
|--------|-------|
| Tasks total | 8 |
| Automated covered | 7/8 (✅) |
| Automated xfail | 1/8 (live-parity, deferred Phase 02.1) |
| Implementation gaps | 0 |
| Naming/path drift fixed | 5 (`tests/...` → `backend/tests/...`; 2 test function names) |
| Resolved | 0 (no implementation gap) |
| Escalated | 0 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags (pytest is one-shot)
- [x] Feedback latency < 30s for unit; full suite ≤ 60s (parity dominates at 35s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** verified 2026-05-09 — 7/8 automated requirements green; 1 xfail by deliberate Phase 02.1 contract decision (live-parity); 3 manual-only deferred. No implementation gaps.
