---
phase: 06
slug: export-contract-validation-gate
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-13
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `06-RESEARCH.md` §Validation Architecture (verified against `pyproject.toml`).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 + pytest-asyncio (`asyncio_mode=auto`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest backend/tests/unit/test_validator_*.py backend/tests/unit/test_export_schemas.py -x` |
| **Full suite command** | `pytest backend/tests -x` |
| **Estimated runtime** | quick ~5s · full ~120s (Iberia parity dominates) |

Markers in use: `slow, unit, parity, integration, uat, e2e` (verified in `pyproject.toml`).

---

## Sampling Rate

- **After every task commit:** Run the quick command (`pytest backend/tests/unit/test_validator_*.py backend/tests/unit/test_export_schemas.py -x`). Target latency <10s.
- **After every plan wave:** Run `pytest backend/tests/unit backend/tests/e2e -x` (~30s).
- **Before `/gsd-verify-work`:** Full suite (`pytest backend/tests -x`) must be green — includes parity (`tests/parity/test_iberia_868_yaml.py`).
- **Max feedback latency:** 30 seconds for the wave checkpoint.

---

## Per-Task Verification Map

> Filled by the planner during Step 8. Each PLAN.md task gets one row.
> Threat Ref column wired for Phase 06 security gate (no current threats — backend-only, single-user, local; planner confirms).

| Task ID | Plan | Wave | Requirement (SC) | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|------------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | SC-1 | — | N/A | unit | `pytest backend/tests/unit/test_export_schemas.py -x` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 1 | SC-2b | — | N/A | unit | `pytest backend/tests/unit/test_validator_color_collision.py -x` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 1 | SC-2c | — | N/A | unit | `pytest backend/tests/unit/test_validator_ocean_leak.py -x` | ❌ W0 | ⬜ pending |
| 06-02-03 | 02 | 1 | SC-2a | — | N/A | unit | `pytest backend/tests/unit/test_validator_territory_size.py -x` | ❌ W0 | ⬜ pending |
| 06-02-04 | 02 | 1 | SC-2d | — | N/A | unit | `pytest backend/tests/unit/test_validator_original_idx.py -x` | ❌ W0 | ⬜ pending |
| 06-02-05 | 02 | 1 | SC-2e | — | N/A | unit | `pytest backend/tests/unit/test_validator_pixel_center.py -x` | ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 2 | SC-3, SC-4-Iberia, SC-4-France, SC-4-Broken | — | N/A | e2e + parity | `pytest backend/tests/e2e/test_export_gate_*.py backend/tests/parity/test_iberia_868_yaml.py -x` | ❌ W0 / ✅ extend | ⬜ pending |

*Status legend: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Row count is illustrative; planner re-issues with the actual `06-NN-MM` task IDs once PLAN.md files are written.*

---

## Per-Code Coverage Matrix (D-08 stable codes)

Mirrors RESEARCH §Validation Architecture. Each code MUST be exercised at every layer.

| Code | Unit test (isolated check fn) | E2E broken fixture | Parity assertion (Iberia) |
|------|-------------------------------|---------------------|---------------------------|
| `SCHEMA_INVALID` | `test_export_schemas.py::test_*_rejects_*` | broken: corrupt JSON byte | parity: schema_ok=True |
| `COLOR_COLLISION` | `test_validator_color_collision.py` | broken: dup RGB in `lookup_condado_colors.json` | parity: 0 collisions |
| `OCEAN_LEAK` | `test_validator_ocean_leak.py` | broken: paint condado RGB into ocean pixels | parity: 0 leaks |
| `MISSING_ORIGINAL_IDX` | `test_validator_original_idx.py` | broken: drop `original_idx` from one condado | parity: 91/91 condados carry `original_idx` |
| `TERRITORY_TOO_SMALL` | `test_validator_territory_size.py` | broken: shrink one condado to 150px | parity: 0 territories <200px |
| `PIXEL_CENTER_OUT_OF_RANGE` | `test_validator_pixel_center.py` | broken: set `pixel_center=[-1, 0]` | parity: all in-bounds |

D-17 (per-broken-fixture EXACT-code assertion) and D-18 (validator collects all, no fail-fast except SCHEMA_INVALID short-circuit) are wired into the e2e fixtures' assertion style.

---

## Wave 0 Requirements

> Files / infrastructure that MUST exist before any task can be green.

- [ ] `backend/medieval_forge/services/export/__init__.py` — re-exports
- [ ] `backend/medieval_forge/services/export/schemas.py` — 6 pydantic models + `MANIFEST_SCHEMA_VERSION = 2`
- [ ] `backend/medieval_forge/services/export/validator.py` — `validate_export` + 5 check fns + `ValidationFailedError`
- [ ] `backend/medieval_forge/services/export/zip.py` — refactored `build_unity_zip` (calls validator first)
- [ ] `backend/medieval_forge/api/v3/export.py` — new router (prefix `/v3/projects`, registered via `api/v3/__init__.py`)
- [ ] `backend/tests/unit/test_export_schemas.py`
- [ ] `backend/tests/unit/test_validator_color_collision.py`
- [ ] `backend/tests/unit/test_validator_ocean_leak.py`
- [ ] `backend/tests/unit/test_validator_original_idx.py`
- [ ] `backend/tests/unit/test_validator_territory_size.py`
- [ ] `backend/tests/unit/test_validator_pixel_center.py`
- [ ] `backend/tests/e2e/test_export_gate_iberia.py`
- [ ] `backend/tests/e2e/test_export_gate_france.py`
- [ ] `backend/tests/e2e/test_export_gate_broken.py`
- [ ] Extend `backend/tests/parity/test_iberia_868_yaml.py` with the MANIFEST `validation_report.passed == true` assertion (D-16)
- [ ] Delete `backend/medieval_forge/api/export.py` + `backend/tests/test_export.py` (D-04)

No framework install needed — pytest 8.4 already in place. No new external dependencies.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| — | — | — | — |

All phase behaviors have automated verification. Phase 06 is backend-only (D-19); no UI surface, no Playwright UAT, no human-in-the-loop step. The aggregate broken-fixture (D-14, "every error code fires once") automates the regression Reconquista would otherwise catch only at engine boot.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (planner fills during Step 8)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (the 15-item list above is exhaustive per RESEARCH)
- [ ] No watch-mode flags (`pytest -x` is one-shot, exits non-zero on first failure)
- [ ] Feedback latency < 30s (wave checkpoint)
- [ ] `nyquist_compliant: true` set in frontmatter (toggle after planner verification and full-suite green)

**Approval:** pending
