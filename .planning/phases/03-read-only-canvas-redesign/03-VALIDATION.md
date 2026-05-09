---
phase: 03
slug: read-only-canvas-redesign
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-09
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Filled by gsd-planner during planning. Wave 0 tasks must close all `❌ W0` rows.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend)** | pytest 7.x (markers: `unit`, `parity`, `integration`) |
| **Framework (frontend)** | vitest 2.x + Playwright (UAT) |
| **Config file (backend)** | `backend/pyproject.toml` |
| **Config file (frontend)** | `frontend/vitest.config.ts` + `frontend/playwright.config.ts` |
| **Quick run command (backend)** | `cd backend && pytest -m "unit and not parity" -x` |
| **Quick run command (frontend)** | `cd frontend && npm run test -- --run` |
| **Full suite command (backend)** | `cd backend && pytest` |
| **Full suite command (frontend)** | `cd frontend && npm run test -- --run && npx playwright test` |
| **Estimated runtime** | backend quick ~5s, full ~25s; frontend quick ~10s, Playwright ~30s |

---

## Sampling Rate

- **After every task commit:** Run quick command for the modified surface (backend or frontend)
- **After every plan wave:** Run full suite (both surfaces)
- **Before `/gsd-verify-work`:** Full suite + Playwright UAT must be green; Phase 01 parity test still 10/10
- **Max feedback latency:** 30 seconds (quick) / 60 seconds (full)

---

## Per-Task Verification Map

> Filled by gsd-planner. Each task in every PLAN.md gets a row here with its automated command.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | SC-1..4 | T-03-01..T-03-04 | TBD | unit/parity/uat | TBD | TBD | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

> Wave 0 is the test-infra + canvas-sidecar emitter task chain that must complete before downstream waves. Filled by planner.

- [ ] Canvas-sidecar emitter (`run_pipeline` extension) — emits `territories.geojson`, `baronies.geojson`, `condado_colors.json`, `barony_colors.json` (BLOCKER from RESEARCH.md Q1)
- [ ] `_write_geojson_atomic` lift to `services/paths.py` — gates D-12 v1 ingest delete (RESEARCH.md Q2)
- [ ] Test stubs for `/api/v3/projects/{id}/generate` POST + SSE pair
- [ ] Test stubs for `/api/v3/projects/{id}/status` GET
- [ ] Playwright fixture: project seeded with Phase 01 artifacts
- [ ] Frontend: `useRunStore` + `useCanvasArtifacts` URL switch test scaffold

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual parity of Mapbox-like shell with UI-SPEC.md mockup | SC-3 | Layout aesthetics not asserted in unit tests | Open `/projects/<seeded-id>` in dev server; compare against UI-SPEC.md §"Layout" |
| SSE stage-by-stage check progression in expanded log panel | D-03 | Streaming UX flow | Click "Generate Map" → expand status badge → confirm 11 ✓ marks appear in DAG order |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
