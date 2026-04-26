---
phase: 04-canvas-editing-basic
plan: 13
status: complete
completed: 2026-04-26
type: hotfix
---

# 04-13 Summary — Backend recalc 500 hotfix (UAT T1)

## Why this plan exists

Plans 04-11 and 04-12 (executed by Paperclip) closed the frontend hydration and shift-click gaps. But human UAT on 2026-04-26 revealed that capital drag (T1) still failed end-to-end — with a different root cause that 04-11/12 had been masking.

Once the store hydrated correctly, the optimistic capital drag fired `POST /territories/{id}/recalc` and the **backend returned 500 Internal Server Error**. Diagnosed via Playwright MCP + direct curl reproduction.

## Root cause

`territories.geojson` stores `id`, `name`, `neighbors` per feature — but **NOT** `lon`/`lat`. Capital coordinates live in `territory_metadata.json` under `condados[]`.

In [`api/edit.py:41-46`](../../../backend/medieval_forge/api/edit.py#L41-L46), `move_capital` was building Voronoi seeds with `t.get("lon", 0.0)` — defaulting all 92 territories except the moved one to `(0.0, 0.0)`. `scipy.spatial.Voronoi` raised `QhullError` on coincident points, which is NOT a `ValueError`, so it escaped the try/except and surfaced as a mute 500.

Disk evidence: `unique seeds: 1 / 92`, `seeds at (0,0): 92`.

## Why earlier tests passed

Backend unit tests in `tests/api/test_edit_api.py` use synthetic fixtures with populated lon/lat. Real production data exercising this path was not covered. This is the same blind-spot pattern as 04-11 (imperative test setup masking integration gaps).

## Fix

Two surgical changes in [`backend/medieval_forge/api/edit.py`](../../../backend/medieval_forge/api/edit.py):

1. Added `_load_capitals(project_id)` helper that reads `territory_metadata.json` and returns `{condado_id: (lon, lat)}`. Returns empty dict on missing file (graceful for test fixtures).
2. `move_capital` now merges metadata capitals into the seed list, falling back to `(t.get("lon", 0.0), t.get("lat", 0.0))` only when the metadata is absent.
3. Widened the exception handler from `except ValueError` to also catch `Exception` with `logger.exception(...)` and a clear `detail=f"recalc failed: {type(e).__name__}: {e}"` — so future failures aren't mute 500s.

## Verification

| Path | Result |
|---|---|
| Direct curl `POST /recalc` | `200 OK` with updated geometries for oviedo + 6 ridge-neighbors (pamplona, tudela, osma, najera, medinaceli, alava) |
| Playwright UAT — drag capital end-to-end | `POST /recalc → 200`, zero console errors |
| T2 vertex drag (regression check) | Still passes (`PATCH /geometry → 200`) |
| T3 shift-click + merge (regression check) | Still passes (`POST /merge → 200`) |
| T4 Ctrl+Z listener | Still active (`defaultPrevented: true`) |
| T5 Ctrl+S explicit (regression check) | Still passes (`POST /geometry/save → 200`) |

All 5 UAT scenarios now pass.

## Tooling additions (separate from the fix)

To avoid future "user copy-pastes console errors" loops, this plan also adds:

- `.mcp.json` configuring Playwright MCP server — gives Claude direct browser control (navigate/click/console/network) without the user copying logs.
- `tools/debug-browser.mjs` — fallback Playwright harness for environments without MCP.
- `.planning/debug/.gitignore` — keeps generated logs/screenshots local.
- Root `.gitignore` entries for `.playwright-mcp/` and ad-hoc screenshots.

## Files changed

- `backend/medieval_forge/api/edit.py` — fix
- `.gitignore` — ignore Playwright MCP artifacts
- `.mcp.json` — new
- `tools/debug-browser.mjs` — new
- `.planning/debug/.gitignore` — new

## Open items / not addressed in this plan

- **No new automated test for the fix.** The test would need a project fixture with `territory_metadata.json` on disk, which is heavier than the existing in-memory fixtures. Flagged for future polish — the regression risk is low because `_load_capitals` has a defensive empty-dict fallback.
- **Missing visual highlight for shift-click multi-selected territories** (carried over from 04-12 — separate UX polish, not blocking UAT).
