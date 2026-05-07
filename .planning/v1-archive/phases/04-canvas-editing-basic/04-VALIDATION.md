---
phase: 4
slug: canvas-editing-basic
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-23
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) + vitest (frontend) |
| **Config file** | `backend/pyproject.toml` (pytest) / `frontend/vite.config.ts` (vitest) |
| **Quick run command** | `cd backend && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ && cd ../frontend && npm run test` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ && cd ../frontend && npm run test`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 4.1 | 1 | EDIT-07 | — | N/A | unit | `cd frontend && npm run test -- useProjectStore` | ❌ W0 | ⬜ pending |
| 04-01-02 | 4.1 | 1 | EDIT-08 | — | N/A | unit | `cd frontend && npm run test -- temporal` | ❌ W0 | ⬜ pending |
| 04-02-01 | 4.2 | 1 | EDIT-01 | — | Validate coordinates before Voronoi recalc | unit | `cd backend && python -m pytest tests/test_voronoi.py -x -q` | ❌ W0 | ⬜ pending |
| 04-02-02 | 4.2 | 1 | EDIT-01 | — | Reject malformed capital move payload | integration | `cd backend && python -m pytest tests/test_edit_api.py::test_move_capital -x -q` | ❌ W0 | ⬜ pending |
| 04-03-01 | 4.3 | 2 | EDIT-02 | — | N/A | unit | `cd backend && python -m pytest tests/test_reshape.py -x -q` | ❌ W0 | ⬜ pending |
| 04-03-02 | 4.3 | 2 | EDIT-03 | — | Reject merge of non-adjacent territories | unit | `cd backend && python -m pytest tests/test_merge.py -x -q` | ❌ W0 | ⬜ pending |
| 04-04-01 | 4.4 | 2 | EDIT-04 | — | Reject split when cut line doesn't cross at 2 points | unit | `cd backend && python -m pytest tests/test_split.py -x -q` | ❌ W0 | ⬜ pending |
| 04-04-02 | 4.4 | 2 | EDIT-07 | — | N/A | e2e-manual | See Manual Verifications | — | ⬜ pending |
| 04-04-03 | 4.4 | 2 | EDIT-08 | — | N/A | e2e-manual | See Manual Verifications | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_voronoi.py` — stubs for EDIT-01 (capital move + neighbor recalc)
- [ ] `backend/tests/test_edit_api.py` — stubs for EDIT-01 endpoint contract
- [ ] `backend/tests/test_reshape.py` — stubs for EDIT-02 (vertex drag reshape)
- [ ] `backend/tests/test_merge.py` — stubs for EDIT-03 (territory merge, adjacency)
- [ ] `backend/tests/test_split.py` — stubs for EDIT-04 (cut-line split, silent failure check)
- [ ] `frontend/src/stores/__tests__/useProjectStore.test.ts` — stubs for EDIT-07/EDIT-08 (undo/redo, partialize, diff)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Capital drag renders neighbor recalc in <500ms | EDIT-01 | Requires live canvas timing | Load project, drag capital, observe network+render time in DevTools |
| Ctrl+Z undoes compound op as one step | EDIT-08 | Multi-step browser interaction | Drag capital, verify 6+ Voronoi recalcs happen, press Ctrl+Z, verify single undo |
| Memory stays bounded at 800 territories over 50 ops | EDIT-07 | Requires browser heap profiling | Use Chrome Memory tab, run 50 edit ops, verify heap growth < 50MB |
| Merge preserves exterior topology, no interior holes | EDIT-03 | Visual polygon inspection | Select 2+ territories, merge, inspect result in canvas |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
