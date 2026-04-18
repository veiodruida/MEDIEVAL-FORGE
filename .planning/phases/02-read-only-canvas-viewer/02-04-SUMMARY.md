---
phase: 02-read-only-canvas-viewer
plan: 04
subsystem: e2e-pipeline-fix
tags: [gap-closure, g-01, g-02, g-03, tdd, d-04, canvas-01, canvas-03, canvas-04]
gap_closure: true
closes_gaps: [G-01, G-02, G-03]
requirements: [CANVAS-01, CANVAS-03, CANVAS-04]
dependency_graph:
  requires:
    - plan 02-01 (territories_geojson / baronies_geojson adapters; generator.py whitelist; useCanvasArtifacts 5-tuple)
    - plan 02-02 (TerritoryLayer + BaronyLayer consuming useCanvasArtifacts)
    - plan 02-03 (CanvasViewer + InspectorSidebar consuming the same 5-tuple)
  provides:
    - condado_colors.json sidecar (per-project, `{condado_id: "#rrggbb"}`) emitted by emit_territories_from_disk
    - barony_colors.json sidecar (per-project, `{barony_name: "#rrggbb"}`) emitted by emit_baronies_from_disk
    - tests/test_generator_e2e.py (blocking integration test exercising real emit_*_from_disk path)
  affects:
    - UAT items 1, 2, 5, 7, 9 (previously FAILED/BLOCKED on 02-HUMAN-UAT.md) — now unblocked for human re-verification against a generated project
    - api/generate.py background-task status machine (now correctly records `status='error_generating'` + `last_error` when emitters fail)
tech_stack:
  added: []
  patterns:
    - Adapter-layer format translation (real `{"r,g,b": idx}` on disk → frontend-friendly `{id: "#hex"}` sidecar) without modifying the vendored generator
    - Fail-loud emitter contract — exceptions propagate to run_generation so the status machine downgrades the project to error_generating
    - TDD RED → GREEN for both unit-level (adapter rewrite) and integration-level (real pipeline pathway) test additions
key_files:
  created:
    - backend/tests/test_generator_e2e.py
  modified:
    - backend/medieval_forge/services/territories_geojson.py
    - backend/medieval_forge/services/baronies_geojson.py
    - backend/medieval_forge/services/generator.py
    - backend/tests/test_territories_geojson.py
    - backend/tests/test_baronies_geojson.py
    - frontend/src/hooks/useCanvasArtifacts.ts
    - frontend/src/components/canvas/__tests__/CanvasViewer.test.tsx
    - frontend/src/components/canvas/TerritoryLayer.tsx (JSDoc only)
    - frontend/src/components/canvas/BaronyLayer.tsx (JSDoc only)
decisions:
  - G-01 fixed via adapter rewrite (not generator rewrite) — lib/map_generator.py stays unchanged, honoring D-04 black-box constraint. Unity continues to consume lookup_*_colors.json in its original int-index shape.
  - Added two new SIDECAR files (condado_colors.json, barony_colors.json) served through the existing /preview/{filename} whitelist route; no new FastAPI routes.
  - G-02 fix is option A (re-raise + propagate) from 02-VERIFICATION.md fix_hint — cleaner than option B (post-check artifact presence) because the status machine in api/generate.py already handles ValueError/RuntimeError.
  - Malformed lookup keys raise ValueError; out-of-range idx values log a WARNING and are skipped (not crashed) so one bad entry does not nuke the batch.
metrics:
  duration_minutes: 25
  completed_date: "2026-04-18"
  tasks_completed: 3
  tasks_total: 3
  files_created: 1
  files_modified: 9
---

# Phase 2 Plan 4: E2E Pipeline Fix (G-01/G-02/G-03) Summary

**One-liner:** Closed the three P2 verification blockers by rewriting the service-layer emitter to consume map_generator's real `{"r,g,b": idx}` lookup format, removing the silent `try/except` that was hiding the defect in `generator.py`, and adding a [BLOCKING] integration test that exercises the real disk codepath end-to-end.

## Gap Closure Map

| Gap | Where the defect lived | Fix location | Evidence |
|-----|------------------------|--------------|----------|
| **G-01** format mismatch (`hexstr[1:3]` on an `int`) | `territories_geojson.emit_territories_from_disk` lines 141–154; same defect in `baronies_geojson.emit_baronies_from_disk` lines 78–81 | Adapter rewrite — both functions now split `"r,g,b"` keys, resolve `idx` via range check, and emit `{id: "#rrggbb"}` sidecar for the frontend. `grep -n 'hexstr\[1:3\]' backend/medieval_forge/services/*.py` → 0 matches. | Commits `0a90b05` (RED) + `1d37afb` (GREEN); 5 new unit tests exercising malformed-key, out-of-range-idx, and happy-path pc paint + sidecar write |
| **G-02** silent `try/except` in `generator.py:341-348` | `_run_pipeline_sync` wrapped emitter calls and swallowed every exception with a `logger.exception` + a "Do not fail the pipeline" comment | Removed the wrapper. Emitter errors now propagate → `run_generation` → `api/generate.py::_run_and_update_status` → `status='error_generating'` + `last_error` in `generator_config`. | Commit `cba9ec7`; `test_emitter_error_propagates_to_caller` asserts `pytest.raises(ValueError, match="malformed key")` bubbles up through `_run_pipeline_sync` |
| **G-03** no integration test exercising real disk codepath | 9 pre-existing backend tests all called `build_*` directly with in-memory numpy; none drove `emit_*_from_disk` through `_run_pipeline_sync` | Created `backend/tests/test_generator_e2e.py` with 20×20 synthetic fixture (two-color lookup pngs + real-format color jsons + `territory_metadata.json`) and monkeypatched `map_generator.generate_maps` to a no-op. Test asserts [BLOCKING] — `territories.geojson`, `baronies.geojson`, `condado_colors.json`, `barony_colors.json` all emitted and surfaced in the manifest. | Commits `9ffe405` (RED) + `cba9ec7` (GREEN); `pytest.raises(...)` on malformed key also lives in this file |

## What Shipped

### Task 1 — Adapter Rewrite (Commits: 0a90b05 RED, 1d37afb GREEN)

Both `emit_territories_from_disk` and `emit_baronies_from_disk` now parse the real on-disk format `{"r,g,b": idx}` produced by `map_generator.py` SECTION 10. They also emit two new sidecar files:

```python
# condado_colors.json  (written by emit_territories_from_disk)
{ "C_ALPHA": "#7b2d43", "C_BETA": "#22d20c" }

# barony_colors.json   (written by emit_baronies_from_disk)
{ "B_A1": "#c80a1e", "B_B1": "#0f50f0" }
```

These are consumed by the frontend (`useCanvasArtifacts` indices `[2]` and `[3]`) via the existing `/preview/{filename}` whitelist route. Unity continues to consume the original `lookup_*_colors.json` files in their untouched `{"r,g,b": idx}` shape — D-04 preserved. `lib/map_generator.py` is not modified.

**New unit tests (5):**
- `test_emit_territories_from_disk_parses_real_format_and_writes_sidecar` — happy path + sidecar content (zero-padded hex: `#0a141e`)
- `test_emit_territories_from_disk_malformed_key_raises_value_error` — asserts `ValueError` on `"not,a,triple,extra"` key
- `test_emit_territories_from_disk_out_of_range_idx_skipped_not_crashed` — out-of-range idx logs warning, skipped, remaining features still emitted
- `test_emit_baronies_from_disk_parses_real_format_and_writes_sidecar` — analogous to territories happy path
- `test_emit_baronies_from_disk_malformed_key_raises_value_error` — analogous malformed-key assertion

All 9 pre-existing `build_*` tests keep passing unchanged (no signature changes).

### Task 2 — Fail-Loud Generator + Integration Test (Commits: 9ffe405 RED, cba9ec7 GREEN)

`generator.py::_run_pipeline_sync` changes:

1. Removed the `try/except Exception: logger.exception(...)` that wrapped the emitter calls at lines 341–348.
2. Appended `"condado_colors.json"` and `"barony_colors.json"` to `GENERATED_FILE_WHITELIST` so FastAPI's `/preview/{filename}` route serves the new sidecars.

No changes to `api/generate.py` — the outer `_run_and_update_status` handler at lines 30–51 already sets `status='error_generating'` + `last_error` on any exception out of `run_generation`. The new fail-loud contract plugs directly into that path.

**New integration tests (2, both in `backend/tests/test_generator_e2e.py`):**
- `test_run_generation_emits_both_geojson_artifacts` [BLOCKING] — drives `_run_pipeline_sync` end-to-end against a synthetic fixture, asserts all four on-disk artifacts and their presence in the returned manifest.
- `test_emitter_error_propagates_to_caller` — corrupts `lookup_condado_colors.json`, asserts `ValueError` bubbles up.

### Task 3 — Frontend Sidecar Switch (Commit: 4eb6f32)

Two URL substrings updated in `useCanvasArtifacts.ts`:

- `[2]` query: `/preview/lookup_condado_colors.json` → `/preview/condado_colors.json`
- `[3]` query: `/preview/lookup_barony_colors.json`  → `/preview/barony_colors.json`

The returned shape stays `Record<string, string>` (id → "#hex"), so `TerritoryLayer`, `DecorationsLayer`, and all downstream consumers keep working without changes. The `CanvasViewer.test.tsx` fetch mock's if-ladder updated to match the new URL substrings. JSDoc comments in `BaronyLayer.tsx` and `TerritoryLayer.tsx` also updated for accuracy.

## Verification Results

| Check | Command | Result |
|-------|---------|--------|
| Backend unit + integration suite | `pytest tests/test_territories_geojson.py tests/test_baronies_geojson.py tests/test_generator_e2e.py -v` | 16/16 pass |
| Frontend full vitest suite | `npx vitest run` | 86/86 pass across 13 files |
| Frontend TypeScript build | `npx tsc -b` | exit 0 |
| G-01 defect gone | `grep -n "hexstr\[1:3\]" backend/medieval_forge/services/*.py` | 0 matches |
| G-01 real format parsing present | `grep -n 'rgb_key.split(",")' backend/medieval_forge/services/*.py` | 2 matches (territories + baronies) |
| G-01 sidecar write sites | `grep -n 'condado_colors.json' services/territories_geojson.py` | write at `:179` |
| G-02 silent swallow gone | `grep -nC2 "emit_territories_from_disk" services/generator.py` | bare call, no surrounding try/except |
| G-03 integration test exists | `ls backend/tests/test_generator_e2e.py` | 164 lines, 2 tests |
| G-03 BLOCKING assertion | grep `BLOCKING:` in test file | 4 blocking asserts (territories, baronies, and 2 sidecars) |
| D-04 preserved | `git diff backend/medieval_forge/lib/map_generator.py` | empty |
| Frontend legacy URL purge | `grep -rn "lookup_condado_colors\|lookup_barony_colors" frontend/src frontend/e2e` | 0 matches |
| Frontend new URLs present | `grep -n "condado_colors.json\|barony_colors.json" frontend/src/hooks/useCanvasArtifacts.ts` | 6 matches (defs + URL strings) |

## Human UAT Unblocked

The following items in `02-HUMAN-UAT.md` were FAILED or BLOCKED by G-01 and can now be re-run against a freshly generated Iberia project:

- **Item 1** — Pixel-parity condado fills (was FAILED — blue empty canvas from missing territories.geojson)
- **Item 2** — Barony overlay at 85% opacity (was BLOCKED — no baronies.geojson)
- **Item 5** — Click-select + neighbor chip pan (was BLOCKED — nothing to click)
- **Item 7** — Label gate at 2× minScale (was BLOCKED — capitals rendered but labels visually tied to condado colors)
- **Item 9** — D-06.3 capital sentinel end-to-end (was BLOCKED — cannot select without territories.geojson)

Re-verification requires a real generation run against the Iberia test dataset; that is an explicit human step (no automated path can cover pixel-parity).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing] Stale JSDoc comments referenced legacy lookup filenames**
- **Found during:** Task 3 grep sweep (`grep -rn "lookup_condado_colors" frontend/src` returned 2 JSDoc hits in `BaronyLayer.tsx` + `TerritoryLayer.tsx`)
- **Issue:** Plan's acceptance criterion requires **zero** matches for `lookup_condado_colors` / `lookup_barony_colors` across `frontend/src`. Two comments still referenced the legacy filename in their docblocks.
- **Fix:** Updated JSDoc comments to reference the new sidecar names; no behavior change.
- **Files modified:** `frontend/src/components/canvas/BaronyLayer.tsx`, `frontend/src/components/canvas/TerritoryLayer.tsx`
- **Commit:** `4eb6f32` (bundled with the main Task 3 commit)

No other deviations. No Rule 4 (architectural) checkpoints — the plan's explicit code templates were followed as written.

## Authentication Gates

None — plan 02-04 is a pure bugfix + test addition on local code. No network secrets, no external credentials, no CLI login flows involved.

## Known Stubs

None. All rendered data (including the two new sidecars) comes from real service-layer emission driven by real on-disk lookup files. The frontend has no remaining empty placeholders tied to this plan.

## Known Open Items (inherited from earlier plans — not regressed here)

Still deferred per 02-VERIFICATION.md (out of scope for gap-closure):

- MultiPolygon islands/exclaves (`firstOuterRing` discards all but first ring) → Phase 3+
- Single-point corner adjacency via `STRtree.touches()` → Phase 4+
- Separate `capital_lat / capital_lon` emission (currently uses centroid for capital coords) → Phase 3+
- `InspectorSidebarWrapper` double `useCanvasArtifacts` call → Phase 4+ refactor

## Commits

| Task | Phase | Commit | Description |
|------|-------|--------|-------------|
| 1 | RED | `0a90b05` | test(02-04): add failing tests for real-format adapter + sidecar emit |
| 1 | GREEN | `1d37afb` | feat(02-04): rewrite emit_*_from_disk to parse real {r,g,b:idx} format |
| 2 | RED | `9ffe405` | test(02-04): add failing integration test for loud-fail + sidecar whitelist |
| 2 | GREEN | `cba9ec7` | feat(02-04): propagate emitter errors + whitelist sidecar files |
| 3 | —  | `4eb6f32` | refactor(02-04): switch frontend to condado/barony_colors.json sidecars |

## Threat Flags

None new. All mitigations in the plan's `<threat_model>` (T-02-04-01 through T-02-04-06) are honored:

- **T-02-04-04** (path-traversal / Elevation of Privilege) — `idx = int(idx_val)` followed by `0 <= idx < len(condados)` range check before `pc[mask] = idx`. Malformed `"r,g,b"` keys raise `ValueError` before any disk write.
- **T-02-04-05** (Repudiation) — silent-swallow removal (G-02 fix) improves audit trail; `api/generate.py` records `last_error` on project status machine.

Threat surface delta: the two new whitelisted files (`condado_colors.json`, `barony_colors.json`) are derived from public disk artifacts and contain only `{id: "#hex"}` — zero PII, zero credentials, zero new disclosure surface vs. what was already served.

## Self-Check: PASSED

Files created/modified verified on disk:

- `backend/tests/test_generator_e2e.py` — FOUND (164 lines, 2 test functions)
- `backend/medieval_forge/services/territories_geojson.py` — FOUND (modified; `grep condado_colors.json` → 7 matches)
- `backend/medieval_forge/services/baronies_geojson.py` — FOUND (modified; `grep barony_colors.json` → 6 matches)
- `backend/medieval_forge/services/generator.py` — FOUND (modified; whitelist updated, try/except removed)
- `backend/tests/test_territories_geojson.py` — FOUND (modified; 8 total tests, 3 new)
- `backend/tests/test_baronies_geojson.py` — FOUND (modified; 6 total tests, 2 new)
- `frontend/src/hooks/useCanvasArtifacts.ts` — FOUND (modified; new URLs present)
- `frontend/src/components/canvas/__tests__/CanvasViewer.test.tsx` — FOUND (modified; new URL substrings)

Commits verified in `git log --oneline --all`:

- `0a90b05` — test(02-04): add failing tests for real-format adapter + sidecar emit
- `1d37afb` — feat(02-04): rewrite emit_*_from_disk to parse real {r,g,b:idx} format
- `9ffe405` — test(02-04): add failing integration test for loud-fail + sidecar whitelist
- `cba9ec7` — feat(02-04): propagate emitter errors + whitelist sidecar files
- `4eb6f32` — refactor(02-04): switch frontend to condado/barony_colors.json sidecars

All gap closures verified:
- G-01 — adapter rewrite (Task 1) + 5 unit tests pass
- G-02 — silent try/except removed (Task 2) + error-propagation test passes
- G-03 — integration test added (Task 2) + [BLOCKING] assertions pass end-to-end
