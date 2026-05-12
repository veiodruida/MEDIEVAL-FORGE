---
phase: 05
slug: region-generalization
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-12
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (backend) + vitest 2.x (frontend) + Playwright (UAT) |
| **Config file** | `pyproject.toml` (pytest), `frontend/vitest.config.ts`, `tests/uat/playwright.config.ts` |
| **Quick run command** | `cd backend && pytest tests/unit/test_region_loader.py -q` |
| **Full suite command** | `cd backend && pytest -q && cd ../frontend && npm test -- --run && cd .. && npx playwright test tests/uat/` |
| **Estimated runtime** | ~90 seconds (unit ~10s, parity ~30s, frontend ~15s, UAT ~35s) |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-* | 01 | 1 | SC-1 | T-05-01 (path traversal in key) | reject `..`/`/` in region key | unit | `pytest tests/unit/test_region_loader.py -q` | ❌ W0 | ⬜ pending |
| 05-02-* | 02 | 2 | SC-1 | — | migration script idempotent | unit | `pytest tests/unit/test_migrate_iberia_to_yaml.py -q` | ❌ W0 | ⬜ pending |
| 05-03-* | 03 | 2 | SC-1 | — | byte-equal lookup PNGs vs Phase 01 golden | parity | `pytest tests/parity/test_iberia_868_yaml.py -q` | ❌ W0 | ⬜ pending |
| 05-04-* | 04 | 3 | SC-1 | T-05-02 (region_key injection) | VARCHAR(64) bounded | integration | `pytest tests/integration/test_generate_render_load_region.py -q` | ❌ W0 | ⬜ pending |
| 05-05-* | 05 | 4 | SC-1 | — | no import of deleted symbols | unit | `pytest -q --collect-only` (collection clean) | ✅ | ⬜ pending |
| 05-06-* | 06 | 2 | SC-2 | — | deterministic Voronoi (rng_seed=42) | unit | `pytest tests/unit/test_gen_toy_france.py -q` | ❌ W0 | ⬜ pending |
| 05-07-* | 07 | 3 | SC-2 | T-05-03 (regions enum) | reject keys not in `data/regions/*.yaml` | unit | `pytest tests/api/test_regions_endpoint.py -q` | ❌ W0 | ⬜ pending |
| 05-08-* | 08 | 4 | SC-2 | — | default region = iberia_868 | unit (vitest) | `cd frontend && vitest run NewProjectModal` | ❌ W0 | ⬜ pending |
| 05-09-* | 09 | 4 | SC-2 | — | england_1216 generate raises clear error | unit | `pytest tests/unit/test_england_1216_missing_inputs.py -q` | ❌ W0 | ⬜ pending |
| 05-10-* | 10 | 5 | SC-3 | — | 12-file contract well-formed for France | e2e | `pytest tests/e2e/test_france_1066_export_contract.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/unit/test_region_loader.py` — schema validation, cache hit/miss, missing file, autogen-when-empty, smooth_sigma range guard
- [ ] `backend/tests/unit/test_migrate_iberia_to_yaml.py` — idempotency + byte-equal output for same rng
- [ ] `backend/tests/parity/test_iberia_868_yaml.py` — copy of test_iberia_868.py adapted to `load_region('iberia_868')`
- [ ] `backend/tests/integration/test_generate_render_load_region.py` — POST /api/v3/projects with `region_key` → /generate → /render
- [ ] `backend/tests/unit/test_gen_toy_france.py` — deterministic output, ~50 cells, valid GeoJSON Polygons
- [ ] `backend/tests/api/test_regions_endpoint.py` — GET /api/v3/regions response shape + `has_dataset`
- [ ] `backend/tests/unit/test_england_1216_missing_inputs.py` — FileNotFoundError with clear message
- [ ] `backend/tests/e2e/test_france_1066_export_contract.py` — 12-file presence + dimensions + JSON schema
- [ ] `frontend/src/components/projects/__tests__/NewProjectModal.test.tsx` — Radix Select renders regions; default = iberia_868
- [ ] `tests/uat/playwright/france_1066_create_project.spec.ts` — create France project → submit → assert row + region_key persisted
- [ ] Add `pyyaml >= 6.0` to `backend/pyproject.toml` (RESEARCH gap)
- [ ] `backend/tests/conftest.py` — `clear_region_cache()` fixture between tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual diff of France 1066 visual PNGs | SC-3 | No golden to compare; humans judge "looks like a map" | Open `visual_condado.png` + `visual_barony.png` from France export; verify regions are contiguous, no fragmenting, colors deterministic re-run-to-re-run |
| Region dropdown UX in NewProjectModal | SC-2 | Cosmetic — disabled-state styling for `has_dataset: false` | Open modal, observe England 1216 grayed out with tooltip "inputs missing" |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
