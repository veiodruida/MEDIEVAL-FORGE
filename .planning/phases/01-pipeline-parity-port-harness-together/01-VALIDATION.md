---
phase: 01
slug: pipeline-parity-port-harness-together
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-07
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Sourced from `01-RESEARCH.md` §8 "Validation Architecture". Update during planning if any test path changes.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (already in `pyproject.toml`) |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` — `parity` marker registered (Phase 00) |
| **Quick run command** | `pytest backend/tests/unit/ -v --cov=medieval_forge --cov-fail-under=85` |
| **Full suite command** | `pytest backend/tests/ -v -m "parity or integration or not slow"` |
| **Estimated runtime** | ~45 s session-fixture pipeline + 12 parity asserts; full suite ≤2 min on local |

---

## Sampling Rate

- **After every task commit:** Run `pytest backend/tests/unit/ -v --cov=medieval_forge --cov-fail-under=85`
- **After every plan wave:** Run `pytest backend/tests/ -v -m "parity or integration or not slow"`
- **Before `/gsd-verify-work`:** Full suite green, including all 10 parity assertions (12 minus the 2 deferred per Pitfall P-2 — `terrain_lookup.png` and `terrain_types.json` defer to Phase 06).
- **Max feedback latency:** 45 s for parity-touching tasks; <5 s for unit-only tasks.

---

## Per-Task Verification Map

> The plan-task IDs ({phase}-{plan}-{task}) are filled in by the planner. The phase-requirement → command map below is locked.

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| V3-PIPELINE-PARITY | `lookup_barony.png` byte-equal vs golden | parity | `pytest backend/tests/parity/test_iberia_868.py::test_lookup_png_byte_equal[lookup_barony.png] -x` | ❌ W0 | ⬜ |
| V3-PIPELINE-PARITY | `lookup_condado.png` byte-equal vs golden | parity | `pytest backend/tests/parity/test_iberia_868.py::test_lookup_png_byte_equal[lookup_condado.png] -x` | ❌ W0 | ⬜ |
| V3-PIPELINE-PARITY | `terrain_lookup.png` byte-equal vs golden | parity | DEFERRED to Phase 06 (Pitfall P-2 — inicio doesn't generate this file) | — | — |
| V3-PIPELINE-PARITY | `visual_condado.png` SSIM ≥ 0.98 vs golden | parity | `pytest backend/tests/parity/test_iberia_868.py::test_visual_png_ssim[visual_condado.png] -x` | ❌ W0 | ⬜ |
| V3-PIPELINE-PARITY | `visual_barony.png` SSIM ≥ 0.98 vs golden | parity | `pytest backend/tests/parity/test_iberia_868.py::test_visual_png_ssim[visual_barony.png] -x` | ❌ W0 | ⬜ |
| V3-PIPELINE-PARITY | `mountains_mask.png` SSIM ≥ 0.98 vs golden | parity | `pytest backend/tests/parity/test_iberia_868.py::test_visual_png_ssim[mountains_mask.png] -x` | ❌ W0 | ⬜ |
| V3-PIPELINE-PARITY | `rivers_overlay.png` SSIM ≥ 0.98 vs golden | parity | `pytest backend/tests/parity/test_iberia_868.py::test_visual_png_ssim[rivers_overlay.png] -x` | ❌ W0 | ⬜ |
| V3-PIPELINE-PARITY | `lookup_barony_colors.json` deep-equal | parity | `pytest backend/tests/parity/test_iberia_868.py::test_json_deep_equal[lookup_barony_colors.json] -x` | ❌ W0 | ⬜ |
| V3-PIPELINE-PARITY | `lookup_condado_colors.json` deep-equal | parity | `pytest backend/tests/parity/test_iberia_868.py::test_json_deep_equal[lookup_condado_colors.json] -x` | ❌ W0 | ⬜ |
| V3-PIPELINE-PARITY | `terrain_types.json` deep-equal | parity | DEFERRED to Phase 06 (companion to terrain_lookup) | — | — |
| V3-PIPELINE-PARITY | `territory_metadata.json` deep-equal | parity | `pytest backend/tests/parity/test_iberia_868.py::test_json_deep_equal[territory_metadata.json] -x` | ❌ W0 | ⬜ |
| V3-PIPELINE-PARITY | `mountain_river_data.json` deep-equal | parity | `pytest backend/tests/parity/test_iberia_868.py::test_json_deep_equal[mountain_river_data.json] -x` | ❌ W0 | ⬜ |
| V3-PIPELINE-PARITY | `run_pipeline(cfg)` callable from in-process Python | unit | `pytest backend/tests/unit/test_pipeline_module.py::test_run_pipeline_signature -x` | ❌ W0 | ⬜ |
| V3-PIPELINE-PARITY | `python -m medieval_forge.services.pipeline --region iberia_868 --out /tmp/out` runs without FastAPI (ROADMAP SC-2) | unit | `pytest backend/tests/unit/test_pipeline_cli.py::test_main_cli_smoke -x` | ❌ W0 | ⬜ |
| V3-PIPELINE-PARITY | `medieval-forge start` still boots HTTP 200 on `/` after v1 generator-stack delete (Phase 00 SC-6 protection) | integration | `pytest backend/tests/integration/test_app_boot.py::test_root_returns_200 -x` | ❌ W0 (or extend existing) | ⬜ |
| V3-PIPELINE-PARITY | CI parity job is non-skippable (ROADMAP SC-3) | manual | Verify `.github/workflows/ci.yml` no longer guards parity step with `|| (echo …; exit 0)` | — | ⬜ |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/parity/__init__.py` — empty package init
- [ ] `backend/tests/parity/conftest.py` — session-scoped `pipeline_output` + `golden_dir` fixtures with diff-on-failure helper
- [ ] `backend/tests/parity/test_iberia_868.py` — 10 parametrised parity tests (12 contract files minus the 2 deferred per Pitfall P-2)
- [ ] `backend/tests/unit/test_pipeline_module.py` — verifies `run_pipeline` exists + signature
- [ ] `backend/tests/unit/test_pipeline_cli.py` — verifies `python -m medieval_forge.services.pipeline` smoke
- [ ] `backend/tests/integration/test_app_boot.py` (or extend existing) — FastAPI boot still 200 OK after generator delete
- [ ] `tests/fixtures/iberia_868/golden/*` — 11 files committed (~1.18 MB; 12th `terrain_lookup.png` deferred to Phase 06)
- [ ] `data/regions/iberia_868/inputs/*` — 3 files (~28-43 MB; LFS for the 29.7 MB PT GeoJSON, direct commit for the rest)
- [ ] `backend/medieval_forge/data/regions/iberia_868/__init__.py` + `territory_data.py` — D-13 move
- [ ] `backend/medieval_forge/data/__init__.py` + `data/regions/__init__.py` — package markers
- [ ] CI flip: `.github/workflows/ci.yml` parity step — drop the `|| (echo …; exit 0)` tail (SCHEDULED AS THE LAST COMMIT OF THE PHASE per RESEARCH §7)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Confirm deployed `territory_metadata.json` shape (with-vs-without `original_idx`) | V3-PIPELINE-PARITY (P-1 resolution) | One-time discovery against external Reconquista source-of-truth file; informs whether `export.py` adds `original_idx` (D-09 deployed-wins). | `jq '.condados[0] \| keys' D:/Projetos_Jogo/Reconquista/Assets/StreamingAssets/Maps/territory_metadata.json` and record finding in PLAN comment + RESEARCH §6 P-1. |
| Confirm `draw_names` boolean against deployed `visual_condado.png` | V3-PIPELINE-PARITY | One-time visual spot-check against external Reconquista PNG; can't be fully automated until Phase 06 export-validation gate. | Open both files in an image viewer; eyeball whether known condado labels (e.g. "Najera") are rendered on the deployed PNG; record `True` / `False` in `iberia_config()`. |
| Confirm CI parity job is non-skippable post-flip | V3-PIPELINE-PARITY (ROADMAP SC-3) | GitHub-side merge-protection rule check — outside repo. | Push a deliberately broken parity-test branch; confirm GitHub blocks merge with red status check on `pytest-parity`. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60 s (parity tasks) / < 5 s (unit-only)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
