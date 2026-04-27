---
phase: 5
slug: canvas-editing-advanced
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-27
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend), Vitest (frontend) |
| **Config file** | `backend/pyproject.toml [tool.pytest.ini_options]` / `frontend/vitest.config.*` |
| **Quick run command (backend)** | `cd backend && pytest tests/api/test_paint_terrain.py -x` |
| **Quick run command (frontend)** | `cd frontend && npx vitest run src/components/canvas/` |
| **Full suite command** | `cd backend && pytest && cd ../frontend && npx vitest run` |
| **Estimated runtime** | ~30–60 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run for the subsystem being changed (backend or frontend)
- **After every plan wave:** Run full suite (backend + frontend)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 5.1 | 0 | EDIT-05 | T-5-01 | `territory_ids` validated against project's known territories (prevents cross-project id injection) | unit | `pytest tests/api/test_paint_terrain.py::test_paint_terrain_excludes_ocean -x` | ❌ W0 | ⬜ pending |
| 5-01-02 | 5.1 | 0 | EDIT-05 | — | N/A | unit | `pytest tests/api/test_paint_terrain.py::test_paint_terrain_returns_painted_ids -x` | ❌ W0 | ⬜ pending |
| 5-01-03 | 5.1 | 0 | EDIT-05 | — | N/A | unit | `cd frontend && npx vitest run src/stores/useProjectStore.test.ts` | ❌ W0 | ⬜ pending |
| 5-01-04 | 5.1 | 1 | EDIT-05 | — | N/A | unit | `cd frontend && npx vitest run src/components/canvas/TerrainBadgesLayer.test.tsx` | ❌ W0 | ⬜ pending |
| 5-01-05 | 5.1 | 1 | EDIT-05 | — | Optimistic update reverts skipped_ids (ocean) to pre-stroke snapshot | unit | `cd frontend && npx vitest run src/components/canvas/CanvasViewer.test.tsx` | ❌ W0 | ⬜ pending |
| 5-02-01 | 5.2 | 0 | EDIT-06 | — | N/A | unit | `cd frontend && npx vitest run src/stores/uiStore.test.ts` | ❌ W0 | ⬜ pending |
| 5-02-02 | 5.2 | 1 | EDIT-06 | — | N/A | unit | `cd frontend && npx vitest run src/components/canvas/TerrainOverlayLayer.test.tsx` | ❌ W0 | ⬜ pending |
| 5-02-03 | 5.2 | 1 | EDIT-06 | — | N/A | unit | `cd frontend && npx vitest run src/components/canvas/ReferenceOverlayPanel.test.tsx` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/api/test_paint_terrain.py` — RED stubs for EDIT-05 backend (land mask guard + success path)
- [ ] `frontend/src/stores/useProjectStore.test.ts` — extend existing tests to cover new `terrain_types` diff block
- [ ] `frontend/src/components/canvas/TerrainBadgesLayer.test.tsx` — emoji badge at centroid (EDIT-05)
- [ ] `frontend/src/components/canvas/TerrainOverlayLayer.test.tsx` — Konva Image + opacity (EDIT-06)
- [ ] `frontend/src/components/canvas/ReferenceOverlayPanel.test.tsx` — file input + opacity Slider (EDIT-06)
- [ ] `frontend/src/stores/uiStore.test.ts` — extend to cover `overlayOpacity`, `overlayImageUrl`, and `URL.revokeObjectURL` on replace (EDIT-06)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Brush cursor circle follows mouse smoothly without lag | EDIT-05 | Canvas pointer event timing not reliably reproducible in Vitest/jsdom | Open canvas, activate paint mode, hover over territory polygons — cursor should track at < 1 frame lag |
| Opacity slider blends overlay behind territory polygons in real time | EDIT-06 | Konva rendering output not inspectable in Vitest | Load reference image, drag opacity slider from 1.0 to 0.0 — image fades smoothly without flash |
| Ocean territory correctly rejected by paint brush | EDIT-05 | Backend land mask depends on actual project GeoJSON on disk | Open a generated project, paint over ocean area — no terrain badge or color change should appear |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
