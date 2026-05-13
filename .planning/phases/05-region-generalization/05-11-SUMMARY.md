---
phase: 05
plan: 11
subsystem: pipeline-export-contract
tags: [terrain, export-contract, sc-3, gap-closure]
requires:
  - "EXPORT_FILE_CONTRACT (Plan 05-10)"
  - "RegionConfig.map_w / .map_h / .kingdom_colors / .ocean_near / .ocean_far / .mountain_color_* / .river_color / .coast_inner_color"
  - "build_land_mask -> bool[H, W]"
provides:
  - "services/pipeline/terrain.py — render_terrain_lookup + build_terrain_types_json + assert_palette_no_collision"
  - "12-file EXPORT_FILE_CONTRACT (terrain pair moved out of DEFERRED)"
  - "ARTIFACT_FILES allowlist extended from 14 → 16"
affects:
  - "backend/medieval_forge/services/pipeline/__init__.py (_write_outputs_to_disk lookup block)"
  - "backend/medieval_forge/services/pipeline/contracts.py (EXPORT_FILE_CONTRACT + EXPORT_FILE_CONTRACT_DEFERRED)"
  - "backend/medieval_forge/services/export.py (PLACEHOLDER_FILES no longer flags terrain as placeholder)"
  - "backend/medieval_forge/api/v3/artifacts.py (ARTIFACT_FILES 14 → 16)"
tech-stack:
  added: []
  patterns:
    - "Pure-function raster renderer (np.bool_ mask → np.uint8 RGB array) — consistent with services/pipeline/render.py"
    - "Runtime palette-collision guard called from the JSON builder (defensive single point)"
key-files:
  created:
    - "backend/medieval_forge/services/pipeline/terrain.py"
    - "backend/tests/unit/test_terrain_render.py"
  modified:
    - "backend/medieval_forge/services/pipeline/__init__.py"
    - "backend/medieval_forge/services/pipeline/contracts.py"
    - "backend/medieval_forge/services/export.py"
    - "backend/medieval_forge/api/v3/artifacts.py"
    - "backend/tests/e2e/test_france_1066_export_contract.py"
    - "backend/tests/unit/test_v3_artifacts.py"
    - "backend/tests/unit/test_v3_status.py"
key-decisions:
  - "Decision A chosen (close in Phase 05): SC-3 wording (file contract IS) is unambiguous; Phase 06 is validation, not creation."
  - "Palette locked: PLAINS_RGB=(124,179,66), OCEAN_RGB=(0,0,0). No collision with any color field across iberia_868.yaml, france_1066.yaml, england_1216.yaml or RegionConfig defaults."
  - "terrain_lookup.png is NATIVE 1x (1920×1080) — not NEAREST-upscaled; CLAUDE.md rule #1 only constrains upscale operations."
  - "Terrain files write in the existing lookup block of _write_outputs_to_disk, sharing _RENDER_TRIGGERS gating + _check_cancel — no 13th PIPELINE_STAGES entry, no frontend change."
  - "Terrain is NOT composited onto visual_*.png — keeps Iberia SSIM ≥ 0.98 contract intact (terrain is a lookup file, not a visual)."
metrics:
  duration_minutes: 22
  completed_date: "2026-05-13"
  tasks_total: 3
  tasks_completed: 3
---

# Phase 5 Plan 11: SC-3 Gap Closure — Terrain Files Summary

One-liner: Close the SC-3 12-file contract by emitting `terrain_lookup.png` + `terrain_types.json` via a new `services/pipeline/terrain.py` module, while preserving byte/SSIM parity with the Phase 01 Iberia golden set.

## What This Plan Did

1. **New module `services/pipeline/terrain.py`** (121 lines): `PLAINS_RGB`, `OCEAN_RGB`, `TERRAIN_TYPES_JSON`, `render_terrain_lookup`, `build_terrain_types_json`, `assert_palette_no_collision`. Module docstring marks the placeholder nature ("Phase 05 contract placeholder — flat plains-everywhere-on-land emitter. Real terrain (DEM-derived, biome-aware) is Phase 06/07.").
2. **9 unit tests** in `tests/unit/test_terrain_render.py` (90 lines) cover palette values, JSON schema, raster shape, land/ocean partition, collision guard (real Iberia + real France pass; injected collision raises).
3. **Contract flip** in `contracts.py`: `EXPORT_FILE_CONTRACT` 10 → 12 entries; `EXPORT_FILE_CONTRACT_DEFERRED = ()`.
4. **Pipeline wire-up** in `__init__.py`: terrain raster + JSON written inside the existing lookup block (same `_RENDER_TRIGGERS` gating + same `_check_cancel()` interleaving).
5. **2 new E2E tests** in `test_france_1066_export_contract.py`: `test_france_1066_terrain_types_schema` (RGB→{name,movement,defense,attack}) and `test_france_1066_terrain_lookup_pixel_palette` (no rogue colors).

## Decision Rationale (A vs B)

| Option | Outcome | Verdict |
|--------|---------|---------|
| **A. Implement in Phase 05** | Two new outputs added; contract closed; Iberia parity preserved. | **Chosen** — SC-3 wording ("file contract IS") is unambiguous; Phase 06's role is to validate the 12-file contract on real DEM, not to create files. |
| B. Defer to Phase 06 | Override SC-3, ship 10/12 indefinitely. | Rejected — effectively rewrites a written ROADMAP success criterion. |

## Why terrain_lookup.png is 1x-Native (Not NEAREST-Upscaled)

CLAUDE.md §"v3 Pipeline Contract" row 5 declares the dimension as `1920×1080` (the 1x lookup dimension). Rule #1 ("NEAREST upscale only — never BICUBIC/BILINEAR for lookup PNGs") constrains *upscale operations*. A file that is generated natively at 1x is never upscaled at all — the rule is honored vacuously. Generating at 1x avoids an extra `Image.resize` call and matches the existing `lookup_barony.png` / `lookup_condado.png` pattern (also 1x native).

## Why Terrain Is NOT Composited onto visual_*.png

`visual_condado.png` and `visual_barony.png` are gated by Iberia SSIM ≥ 0.98 in `test_iberia_868_yaml.py`. Painting plains green over land would change every pixel and immediately break that parity gate. Terrain is a *lookup* file — Unity reads it pixel-by-pixel through the shader and never renders it on the visual map. Compositing would conflate two trust layers (visual = human eye; lookup = Unity shader).

## Palette Collision Evidence

Grep of all committed region YAMLs:
```
grep -nE "124,?\s*179,?\s*66" data/regions/*.yaml
```
Zero matches in YAML color fields. The lone hit for `66` in `iberia_868.yaml:1335` is `original_idx: 66` (an integer identifier, not an RGB tuple). `assert_palette_no_collision` is called from `build_terrain_types_json` on every write, so any future YAML drift trips a `ValueError` at write-time.

## Deviations from Plan

### Rule 1 / Rule 2 — Auto-fixed Downstream Hardcodes

The Replan Note SSoT-grep gate flagged `services/export.py` and `api/v3/artifacts.py` as parallel hardcodes of the file list. Both were updated as part of Task 2:

1. **`services/export.py`** — `PLACEHOLDER_FILES` no longer flags `terrain_lookup.png` / `terrain_types.json` as placeholders (they are now real outputs). Docstring updated accordingly. `UNITY_ZIP_SPEC` already listed both names, so the ZIP shipped them; the placeholder set just needed pruning.
2. **`api/v3/artifacts.py`** — `ARTIFACT_FILES` allowlist grew from 14 → 16 (added the terrain pair). Without this fix the new files would be generated but the serving endpoint would 404 them.
3. **`tests/unit/test_v3_artifacts.py` + `test_v3_status.py`** — fixed `assert len(...) == 14` to `== 16`; renamed `test_allowlist_contains_14_files` → `..._16_files`; removed a contradictory `not in ARTIFACT_FILES` assertion that referenced the deferred state.

Each of these was a direct consequence of expanding the contract — without them the suite would have failed and the new files would not have been observable from the v3 API.

## Out-of-Scope Backlog (flagged in Plan 05-11 <action> — for orchestrator STATE.md sweep)

- `region_loader.py:_autogen_territories` — Voronoi seed collision (~80 condados for france_1066 instead of ~40). No CLAUDE.md rule violated. Covered by Plan 05-13.
- `tests/parity/test_iberia_868_yaml.py:43` — direct `cfg.output_dir` mutation of `load_region()` singleton (Pitfall 9). Covered by Plan 05-14.
- `api/v3/render.py:94-99` — dead `_make_on_stage` helper.
- `services/pipeline/region_loader.py:350-360` — no-op try/except re-raise.

## Threat Surface Scan

The new artifacts (terrain palette + raster) introduce no new network surface, no new auth path, and no new file access pattern beyond the existing `output_dir` writes. The single new trust boundary (YAML config → terrain palette) is mitigated by `assert_palette_no_collision` (T-05-11-01). No `threat_flags` to add.

## Test Counts

| Suite | Before | After | Delta |
|-------|--------|-------|-------|
| `tests/unit/test_terrain_render.py` | 0 | 9 | +9 |
| `tests/e2e/test_france_1066_export_contract.py` | 6 | 8 | +2 |
| `tests/parity/test_iberia_868_yaml.py` | 22 (12 pass + 6 xfail + 4 xpass) | 22 | 0 |
| `tests/unit/test_v3_artifacts.py` + `test_v3_status.py` | passing | passing (3 assertions updated 14→16) | 0 |
| **Full backend `pytest tests/unit tests/parity tests/e2e -q`** | 152 passed | 154 passed, 6 xfailed, 4 xpassed | **+2 new tests; parity preserved** |

## Verification Evidence

- `cd backend && pytest tests/unit/test_terrain_render.py -q` → 9 passed (0.12 s)
- `cd backend && pytest tests/e2e/test_france_1066_export_contract.py tests/parity/test_iberia_868_yaml.py tests/unit/test_terrain_render.py -q` → 28 passed (42.51 s)
- `cd backend && pytest tests/unit tests/parity tests/e2e -q` → 154 passed, 6 xfailed, 4 xpassed (170.03 s)
- Live smoke: `france_1066` pipeline ran end-to-end; both `terrain_lookup.png` (1080×1920) and `terrain_types.json` present in output.
- `len(EXPORT_FILE_CONTRACT) == 12`; `EXPORT_FILE_CONTRACT_DEFERRED == ()`.

## Commits

| Hash | Message |
|------|---------|
| `637f5e8` | feat(05-11): terrain.py — PLAINS_RGB palette + JSON schema + 1x raster renderer |
| `2689e4a` | feat(05-11): emit terrain_lookup.png + terrain_types.json — 12-file contract closed |
| `2e366e4` | test(05-11): extend SC-3 gate to 12 files + add terrain_types.json schema test |

## Self-Check: PASSED

Files verified present:
- backend/medieval_forge/services/pipeline/terrain.py (FOUND, 121 lines)
- backend/tests/unit/test_terrain_render.py (FOUND, 90 lines)

Commits verified:
- 637f5e8 (FOUND in git log)
- 2689e4a (FOUND in git log)
- 2e366e4 (FOUND in git log)

Contract verified:
- `python -c "from medieval_forge.services.pipeline.contracts import EXPORT_FILE_CONTRACT, EXPORT_FILE_CONTRACT_DEFERRED; print(len(EXPORT_FILE_CONTRACT), len(EXPORT_FILE_CONTRACT_DEFERRED))"` → `12 0`
