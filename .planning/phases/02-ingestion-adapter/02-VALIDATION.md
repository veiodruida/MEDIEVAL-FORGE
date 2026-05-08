---
phase: 02
slug: ingestion-adapter
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-08
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend); pytest-asyncio for SSE/httpx tests |
| **Config file** | `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` (markers: `unit`, `parity`, `integration`) |
| **Quick run command** | `pytest -m "unit and not integration" tests/unit/adapters/ -q` |
| **Full suite command** | `pytest -m "unit or parity" -q` |
| **Estimated runtime** | ~30s unit; ~120s full (parity-iberia-868 dominates) |

---

## Sampling Rate

- **After every task commit:** Run quick command (unit-adapter tests only — under 30s)
- **After every plan wave:** Run full suite (unit + parity)
- **Before `/gsd-verify-work`:** Full suite must be green AND `tests/parity/test_iberia_868.py` AND `tests/parity/test_iberia_868_live.py` both pass
- **Max feedback latency:** 30 seconds (per-task)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | ROADMAP-02#2 | — | N/A | unit | `pytest tests/unit/test_contracts.py::test_project_dataset_required_fields -q` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | ROADMAP-02#2 | — | N/A | unit | `pytest tests/unit/test_regions.py::test_iberia_config_returns_dataset -q` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | ROADMAP-02#3 | — | N/A | unit | `pytest tests/unit/adapters/test_osm_split.py -q` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | ROADMAP-02#3 | — | N/A | unit | `pytest tests/unit/adapters/test_terrain_passthrough.py -q` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 2 | ROADMAP-02#1 | — | N/A | parity | `pytest -m parity tests/parity/test_iberia_868.py -q` | ✅ | ⬜ pending |
| 02-03-02 | 03 | 2 | ROADMAP-02#1 | — | N/A | parity | `pytest -m parity tests/parity/test_iberia_868_live.py -q` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04 | 3 | ROADMAP-02#3 | — | SSE stream emits terminal `done` sentinel | unit | `pytest tests/unit/api/test_v3_ingest.py -q` | ❌ W0 | ⬜ pending |
| 02-04-02 | 04 | 3 | ROADMAP-02#3 | — | Path-existence assert at `landmask.py` top fails fast on missing input | unit | `pytest tests/unit/test_landmask_input_assert.py -q` | ❌ W0 | ⬜ pending |

> Final IDs/wave assignments will be set by the planner. This is the validation skeleton; cells refine during planning.

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/adapters/__init__.py` — package marker
- [ ] `tests/unit/adapters/conftest.py` — shared synthetic Overpass GeoJSON fixture (PT+ES features, ~6 features)
- [ ] `tests/unit/adapters/test_osm_split.py` — split-by-ISO correctness (per-country counts, centroid-in-polygon)
- [ ] `tests/unit/adapters/test_terrain_passthrough.py` — terrain stub returns vendored `mountain_river_data.json` Path unchanged (D-13)
- [ ] `tests/unit/test_contracts.py` — `ProjectDataset` shape + required-field assertion
- [ ] `tests/unit/test_regions.py` — `iberia_config()` returns ProjectDataset pointing at vendored es-atlas + pt_concelhos
- [ ] `tests/unit/test_landmask_input_assert.py` — missing path → FileNotFoundError at top of `landmask.py`
- [ ] `tests/unit/api/test_v3_ingest.py` — `/api/v3/projects/{id}/ingest` SSE stream contract (event ordering, terminal sentinel, status update on Project)
- [ ] `tests/parity/test_iberia_868_live.py` — derived from `test_iberia_868.py`; substitutes adapter-built ProjectDataset reading `tests/fixtures/iberia_868/live-ingestion/`
- [ ] `tests/fixtures/iberia_868/live-ingestion/{pt_concelhos_live.geojson, es_municipalities_live.geojson, mountain_river_data_live.json}` — committed snapshot (D-09, D-10)
- [ ] `scripts/refresh_live_snapshot.py` — manual refresh entrypoint; emits `docs(parity): refresh live snapshot` commit guidance

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live OSM Overpass connectivity | ROADMAP-02#3 | D-09 forbids network in CI — runs once locally during snapshot refresh | `python scripts/refresh_live_snapshot.py --region iberia_868`; inspect `tests/fixtures/iberia_868/live-ingestion/` diff; commit if intended |
| Live-path golden equivalence after snapshot refresh | ROADMAP-02#1 | Re-running pipeline against refreshed snapshot may legitimately diverge from `golden/` if OSM has improved data; needs human review | After refresh, run `pytest -m parity tests/parity/test_iberia_868_live.py`; if fails, diff vs `golden/` and decide: refresh golden (Phase 01 D-09 "deployed wins" override) or roll back snapshot |
| SSE event payload schema review | ROADMAP-02#3 / D-14 | Schema invisible to Phase 01 parity gate; visual review for Phase 03 consumer | `curl -N http://localhost:8000/api/v3/projects/{uuid}/ingest`; inspect events in stdout |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (`adapters/`, `tests/unit/adapters/`, live-ingestion fixture dir, v3 ingest endpoint test, refresh script)
- [ ] No watch-mode flags (pytest is one-shot)
- [ ] Feedback latency < 30s for unit; full suite < 150s
- [ ] `nyquist_compliant: true` set in frontmatter (after planner closes per-task IDs and waves)

**Approval:** pending
