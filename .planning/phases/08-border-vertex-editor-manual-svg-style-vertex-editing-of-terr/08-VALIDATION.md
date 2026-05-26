---
phase: 8
slug: border-vertex-editor-manual-svg-style-vertex-editing-of-terr
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-26
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) + vitest (frontend unit) + Playwright (UAT) |
| **Config file** | `backend/pyproject.toml`, `frontend/vitest.config.ts`, `tests/uat/playwright/playwright.config.ts` |
| **Quick run command** | `pytest tests/unit/test_phase08_*.py -x` / `cd frontend && npx vitest run src/**/__tests__/*phase08*` |
| **Full suite command** | `pytest tests/ -q && cd frontend && npx vitest run && npx playwright test tests/uat/playwright/phase08-*` |
| **Estimated runtime** | ~90 seconds quick / ~6 min full (Iberia 868 parity included) |

---

## Sampling Rate

- **After every task commit:** Run quick command for the task's plan
- **After every plan wave:** Run full unit + parity for the affected layer
- **Before `/gsd-verify-work`:** Full suite green incl. Playwright UAT
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

> Filled by planner. Every PLAN.md task gets a row mapping REQ-ID → command.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 8-XX-XX | XX | X | REQ-08-XX | — | N/A | unit/parity/uat | `{command}` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_manual_edit_stage.py` — stubs for `manual_edit` DAG stage tokens + identity pass-through
- [ ] `tests/unit/test_branch_storage.py` — stubs for SQLite `branches`/`snapshots`/`edit_events`
- [ ] `tests/parity/test_phase08_edit_roundtrip.py` — stub: empty edit log == pre-edit parity
- [ ] `frontend/src/stores/__tests__/useEditorStore.test.ts` — zundo wiring stub
- [ ] `frontend/src/components/canvas/__tests__/VertexEditLayer.test.tsx` — handle render stub
- [ ] `tests/uat/playwright/phase08-vertex-edit.spec.ts` — UAT scenario stub
- [ ] `tests/conftest.py` — branch + snapshot fixtures

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 60fps drag perceived smoothness | REQ-08-perf | Frame timing thresholds noisy in CI | Open Iberia 868, drag a barony vertex across screen, observe no jank |
| Snap visual feedback (yellow circle) | REQ-08-snap | Visual-only artifact | Hover vertex near neighbour vertex, confirm yellow circle appears |
| Purple shared-edge highlight | REQ-08-shared-edge | Visual-only | Hover edge between two baronies, confirm purple highlight |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
