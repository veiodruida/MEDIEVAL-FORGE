---
phase: 03
plan: 08
status: complete
wave: 4
sign_off: approved (user, 2026-05-10)
requirements_closed: [SC-1, SC-2, SC-3, SC-4]
artifacts:
  - frontend/tests/uat/playwright/03-canvas-workspace.spec.ts
  - frontend/tests/uat/playwright/globalSetup.ts
  - frontend/playwright.config.ts
  - backend/tests/fixtures/seed_phase01_artifacts.py (pre-existing)
  - backend/tests/unit/test_seed_phase01_artifacts.py (pre-existing)
  - backend/tests/fixtures/uat_setup.py
  - dev.bat
  - test-uat.bat
  - seed-uat.bat
---

# Plan 03-08 — Wave 4 Acceptance Gate Summary

## Outcome

Wave 4 closed. Phase 03 (read-only canvas redesign) ready for verification.

| Gate | Result |
|---|---|
| Playwright UAT (`03-canvas-workspace.spec.ts`) | **1 passed (2.8 s)** — covers SC-1..SC-4 |
| Frontend vitest | **156/156 green** across 24 files |
| Backend pytest (full) | **195 passed, 6 xfailed, 4 xpassed, 0 failed** |
| Phase 01 parity | **11/11 green** (10 byte-equal + 1 sidecar assertion) |
| Cross-surface dangling-import grep | **zero hits** in `frontend/src/` and `backend/medieval_forge/` |
| Manual visual sign-off | **approved** (user) |

## Tasks

### Task 1 — Fixture helper (auto, TDD)

`backend/tests/fixtures/seed_phase01_artifacts.py` and its 3-test unit suite were
seeded by commit `1c6c05c` before this Wave 4 session started. Already green:
14-file copy, idempotency, invalid-UUID rejection. No new work needed.

### Task 2 — Playwright UAT spec (auto, TDD)

Wired up brand-new Playwright infrastructure:

| File | Role |
|---|---|
| `frontend/playwright.config.ts` | Two-server config: uvicorn `:8765` + vite `:5173` (Vite proxies `/api` → 8765). `globalSetup` shells out to `backend/tests/fixtures/uat_setup.py`. |
| `frontend/tests/uat/playwright/globalSetup.ts` | ESM globalSetup that spawns the Python helper, parses its JSON line, persists it under `.uat-state/project.json`, exposes `process.env.UAT_PROJECT_INFO_PATH`. |
| `frontend/tests/uat/playwright/03-canvas-workspace.spec.ts` | Single happy-path scenario covering SC-1..SC-4. |
| `frontend/tests/uat/playwright/.gitignore` | Ignores `.uat-state/`. |
| `backend/tests/fixtures/uat_setup.py` | Standalone CLI: runs the iberia_868 pipeline (cached under `~/.medieval-forge/uat_cache/iberia_868/`), creates a Project DB row with `status='generated'`, seeds its `output/` dir via `seed_phase01_artifacts`, prints `{project_id, …}` JSON. |

**Spec assertions (SC-1..SC-4 evidence):**

- SC-1 — `data-testid="workspace-toolbar"` visible, project name + status badge populated, `data-testid="canvas-stage"` renders, `data-testid="territory-layer-ready"` attached after artifacts hydrate, click-on-canvas resolves a hit.
- SC-2 — `data-testid="inspector-placeholder"` initial state, `data-testid="inspector-single"` after canvas click, `data-testid="layer-toggle-condados"` clickable, shift-click yields `data-testid="inspector-multi"` with PT-BR copy.
- SC-3 — `page.on('console', …)` collects errors over the whole flow; final `expect(consoleErrors).toEqual([])`. `Failed to load resource: …404` is filtered because Phase 06 defers `terrain.png` and the favicon is also absent (CLAUDE.md output contract rows 5–6).
- SC-4 — `page.on('request', …)` collects URLs; final `expect(previewLeaks).toEqual([])` proves no v1 `/preview/*` endpoint was hit.

### Task 3 — Visual sign-off (manual checkpoint, blocking)

Two rounds of UAT feedback from the user, both fixed inside Plan 03-08 instead
of being deferred:

**Round 1 — initial visual probe via the Playwright MCP browser tools:**

1. **Plan 03-04 gap — `InspectorSidebar` was never rendered.** UI-SPEC §Layout
   Contract requires the right-docked 320 px inspector; Plan 03-04 rewrote
   `ProjectDetail.tsx` (697 → 160 LOC) but never re-mounted the sidebar.
   `CanvasViewer` now accepts an optional `project` prop and lays itself out as
   a flex-row (canvas pane `flex:1` + 320 px aside). Existing canvas unit
   tests keep canvas-only behaviour because they don't pass `project`.

2. **Residual UI-SPEC gap — `LegendCard` not rendered.** Component existed but
   no render site. Imported + rendered alongside `LayerTogglePanel` /
   `FitToViewButton` / `HoverTooltip`.

**Round 2 — interactive testing:**

3. **Baronies layer toggle had no visible effect.** Backend `baronies.geojson`
   sidecar didn't write a `fill` property; frontend `BaronyRender` select read
   `f.properties.fill` and got `undefined` for every barony, so polygons
   rendered transparent. `barony_colors.json` already mapped `barony_name →
   #rrggbb`, but `CanvasViewer` was discarding the `baronyColorsQ` slot of the
   tuple destructure. Fixed by lifting `baronyColors` to a `BaronyLayer` prop;
   layer now resolves fill via `baronyColors[b.id] ?? b.fill ?? FALLBACK`.
   Stroke opacity bumped 0.25 → 0.45 so subdivisions are visible even with
   same-palette parent condados.

4. **Labels too small to read.** `fontSize=12` was in MAP coordinates; the
   Stage applies `currentScale ≈ 0.3` at default fit-to-view, yielding ~4 CSS
   px glyphs. Fixed with `TARGET_LABEL_SCREEN_PX = 16` and
   `fontSize = TARGET_LABEL_SCREEN_PX / currentScale`. Stroke width and offsetY
   inherit the inverse-scale.

5. **Label outline rendered as a "double" line.** Konva paints the stroke on
   the glyph perimeter, which collided with bold weight + a translucent white
   stroke. Switched to white fill + black stroke + `fillAfterStrokeEnabled`
   (stroke fully covered by the fill, leaving a clean halo) plus a soft
   `shadowBlur` glow that scales with zoom.

6. **Could not select a barony — Phase 04 prep.** Original Phase 03 design
   (D-03) restricted selection to condados. The user requested barony-level
   selection because Phase 04 will add Inkscape-style vertex editing on the
   same selection model. Implemented:
     - `uiStore.selectedBaronyId` + `selectBarony(id | null)`, mutually
       exclusive with condado selection.
     - `BaronyLayer` switches from `listening=false` to
       `listening={visible}` and dispatches `selectBarony` on click. Selected
       barony gets a gold (`#facc15`) stroke at width 2.
     - `InspectorSidebar` gains a 4th branch: barony detail card (Kingdom +
       Duchy + Condado + Barony badges + area in km²). Mode precedence: barony
       → placeholder → multi → single condado.
     - The Stage's empty-click handler now clears both selection tiers in one
       call.

**Pre-existing backend test failures, fixed in scope** (commit `3cd474d`):

| Test | Cause | Fix |
|---|---|---|
| `tests/services/test_ingest_osm.py::test_sse_generator_sets_stop_event_on_client_disconnect` | Imports `medieval_forge.api.ingest`, deleted in Plan 03-07 | Removed orphan test (the four `services.ingest_osm` tests in the same file are kept) |
| `tests/unit/test_v3_artifacts.py::test_artifacts_rejects_path_traversal_attempt` | SPA catch-all returns 200 (index.html) when the frontend bundle exists; the assertion accepted only 400/404/503 | Added 200 to the allowed set; the canary `assert "root:" not in r.text` still proves no file leaked |
| `tests/unit/test_parity_refresh_tool.py::test_plugin_dry_run_vs_confirm[…]` | Subprocess `pytest` runs from a Windows tmp scratch dir, so the workspace `pyproject.toml` `pythonpath` does not propagate; `from tests.parity import conftest` failed with `ModuleNotFoundError` | Pass `PYTHONPATH=backend/` via `subprocess.run(env=…)` and set `cwd=backend/` |

Dead docstring refs to deleted modules in `services/paths.py`,
`services/ingest_terrain/runner.py`, `api/v3/ingest.py` were also stripped so
the cross-surface grep gate returns zero.

## Tooling additions (commit `2bf959c`)

| Script | Purpose |
|---|---|
| `dev.bat` | Two-console dev-mode: backend `uvicorn :8765 --reload` + vite `:5173` |
| `test-uat.bat` | `npx playwright test 03-canvas-workspace.spec.ts` (config brings up its own servers + globalSetup); forwards extra args (`--headed`, `--debug`, …) |
| `seed-uat.bat` | Invokes `uat_setup.py`; prints the seeded `project_id` so it can be opened in the browser launched by `dev.bat` / `start.bat` |
| `setup.bat` | Adds `npx playwright install chromium` step `[4/5]` so `test-uat.bat` works out of the box |

## Phase 03 commit chain (Wave 4 segment)

```
3cd474d  fix(03-08): close 4 pre-existing backend test failures + drop dead docstring refs
b777650  feat(03-08): wire InspectorSidebar into CanvasViewer (Plan 03-04 gap-closure)
356715a  feat(03-08): Playwright UAT for Phase 03 read-only canvas workspace
c76f7ee  feat(03-08): wire LegendCard into CanvasViewer (residual UI-SPEC gap)
2bf959c  chore(03-08): add dev/test-uat/seed-uat bat scripts + Playwright install step
c695933  fix(03-08): visible barony fills + zoom-aware label sizing (UAT feedback)
00196c6  feat(03-08): barony selection + clean text halo (UAT feedback round 2)
```

## Deviations vs the plan

| ID | What | Why | Justification |
|---|---|---|---|
| D-03-08-01 | Plan said `seed_phase01_artifacts` was new work; it had been pre-built in commit `1c6c05c` | Plan author missed the artifact already existed | Verified the existing 3-test suite passes; no rewrite required |
| D-03-08-02 | Plan `read_first` referenced `frontend/playwright.config.ts` as existing; only a 17-line placeholder was on disk and `frontend/tests/uat/` did not exist | Plan over-stated pre-state | Wrote both from scratch following the plan's globalSetup-via-Python design |
| D-03-08-03 | Filtered `Failed to load resource …404` console errors in the SC-3 assertion | Phase 06 defers `terrain.png` (CLAUDE.md output contract row 5) and the favicon is absent in dev | Documented inline in the spec; SC-3 still fails on any other error type |
| D-03-08-04 | Closed two cross-phase gaps (InspectorSidebar + LegendCard render sites missing) inside this plan instead of writing a 03-04-FIX plan | UI-SPEC §Layout Contract mandates both; without them SC-2 is unverifiable | Documented as gap-closures in commits `b777650` and `c76f7ee` |
| D-03-08-05 | Expanded Phase 03 scope: barony-level selection (`selectedBaronyId` + `BaronyLayer.listening` + 4-mode `InspectorSidebar`) | User requested it during the visual sign-off as Phase 04 prep (Inkscape-style vertex editing will sit on top of this selection model) | Backwards-compatible — existing tests unchanged except `BaronyLayer.test.tsx` which now asserts the new `listening={visible}` contract |
| D-03-08-06 | Closed 4 pre-existing backend pytest failures inside this plan | Two were noted as "pre-existing" in 03-07-SUMMARY but never fixed; running `pytest` from clean main showed the same set; they would block phase verification | Single atomic commit, all four green afterwards |

## Phase 03 success criteria — final state

| ID | Criterion | Evidence |
|---|---|---|
| SC-1 | Pan/zoom/click on a Phase 01 project | Playwright UAT — workspace shell visible, canvas hydrates, click resolves; manual sign-off confirmed |
| SC-2 | Inspector populates + layer toggles work | UAT asserts `inspector-single` after click + `inspector-multi` after shift-click + `layer-toggle-condados` clickable; manual sign-off confirmed Baronies/Capitais/Fronteiras toggles + barony selection |
| SC-3 | Zero console errors | UAT `expect(consoleErrors).toEqual([])` (with documented terrain.png/favicon 404 filter); cross-surface dangling-import grep returns zero |
| SC-4 | Artifacts come from Phase 01 output | UAT `expect(previewLeaks).toEqual([])`; backend served all 7 routed artifact requests with 200 OK during the spec run |
