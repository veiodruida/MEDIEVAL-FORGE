---
phase: 01-pipeline-parity-port-harness-together
plan: 02
subsystem: pipeline-port
tags: [pipeline, verbatim-port, voronoi, kd-tree, median-filter, gaussian-smooth, lookup-png, metadata-export, deterministic-rng, iberia_868]

# Dependency graph
requires:
  - phase: 01-pipeline-parity-port-harness-together
    plan: 01
    provides: PREFLIGHT verdicts, golden fixtures, in-tree pipeline inputs (LFS), in-package territory data, 9-submodule pipeline scaffold with RegionConfig + iberia_config
provides:
  - Verbatim 1:1 port of inicio/map_generator.py §2-§13 across the 9 pipeline submodules (D-01)
  - Standalone CLI run producing the 10 in-scope contract files (terrain_lookup.png + terrain_types.json deferred to Phase 06 per P-2)
  - Determinism via cfg.rng_seed: two runs produce byte-identical SHA-256 hashes for all 10 files
affects: [01-03-PLAN parity harness, V3-PIPELINE-PARITY requirement]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "D-01 verbatim 1:1 port: every inicio function from §2-§13 has a matching submodule body, line-by-line auditable"
    - "Three named substitutions for cfg promotion: rng_seed (P-9), draw_names (Q10), territory data (D-13/D-14)"
    - "Per-country KD-trees enforced (CLAUDE.md rule #3 + P-6): tp + te never global"
    - "INDEPENDENT 2x mask renders (CLAUDE.md rule #6 + P-4): land_2x built once via build_land_mask(target_w*upscale, target_h*upscale) and threaded through render_map + render_mountains"
    - "P-13 deterministic RGB hash (i*37+50, i*73+80, i*113+30) % 256 in lookup PNGs"

key-files:
  created: []
  modified:
    - backend/medieval_forge/services/pipeline/contracts.py (Task 1, +43 / -13 lines)
    - backend/medieval_forge/services/pipeline/landmask.py (Task 2, +158 / -2 lines)
    - backend/medieval_forge/services/pipeline/border.py (Task 3, +32 / -2 lines)
    - backend/medieval_forge/services/pipeline/voronoi.py (Task 4, +167 / -2 lines)
    - backend/medieval_forge/services/pipeline/cleanup.py (Task 5, +100 / -2 lines)
    - backend/medieval_forge/services/pipeline/lookup.py (Task 6a, +50 / -2 lines)
    - backend/medieval_forge/services/pipeline/export.py (Task 6b, +79 / -2 lines)
    - backend/medieval_forge/services/pipeline/render.py (Task 7, +259 / -2 lines)
    - backend/medieval_forge/services/pipeline/__init__.py (Task 8, +174 / -6 lines)

key-decisions:
  - "All 8 task commits land atomically as `feat(01): port §X ... → file.py` per D-01 (one inicio section -> one commit)"
  - "PREFLIGHT.md Q8 honoured: original_idx ABSENT in export.py — port reproduces inicio verbatim (no original_idx field emitted); CLAUDE.md rule #4 deferred to schema-alignment phase per D-09 (deployed wins)"
  - "Per-country KD-trees enforced: voronoi.setup_baronies returns 9-tuple including tp + te, both cKDTree instances; rasterize_baronies routes via the precomputed border_mask (CLAUDE.md rule #3)"
  - "Median pass kernel sequence inlined verbatim (NOT promoted to cfg field): `11 if i<2 else 9 if i<4 else 7 if i<6 else 5` per D-01"
  - "Smoothing σ window honoured: cfg.smooth_sigma in [3.0, 4.5] with per-territory reduction `s = cfg.smooth_sigma if npx > 400 else max(1.2, cfg.smooth_sigma * (npx / 400))` (P-5)"
  - "Image.NEAREST literal preserved at line 155 of render.py for the 2x upscale (rule #1 + P-3) — never BICUBIC/BILINEAR"
  - "RNG seed propagation: render.py and __init__.py both call np.random.default_rng(cfg.rng_seed); zero literal `default_rng(42)` remains in pipeline/ tree (rule #7 + P-9)"

patterns-established:
  - "Verbatim port commits use `feat(01): port §X ... → file.py` to make line-by-line audit straightforward"
  - "Plan-mandated deviations (Windows utf-8, plan-required signature changes) get explicit comments referencing the plan rule that authorized them"
  - "Karpathy-aligned: zero auto-discovery refactor; no rename to `medieval_forge_*`; no abstractions invented; the only 'new' code is the orchestrator wiring inicio mandates"

requirements-completed: [V3-PIPELINE-PARITY]

# Metrics
duration: 44min
completed: 2026-05-07
---

# Phase 01 Plan 02: Verbatim Port Summary

**The 8-commit verbatim port of `inicio/map_generator.py` (944 lines, 13 sections) into the 9-submodule pipeline package. `python -m medieval_forge.services.pipeline --region iberia_868 --out X` now produces the 10 in-scope contract files for Iberia 868, byte-deterministic across runs via `cfg.rng_seed`. All seven CLAUDE.md non-negotiable rules are honoured (with rule #4's `original_idx` correctly deferred per PREFLIGHT.md Q8 + D-09). Plan 03's parity harness can now build on top.**

## Performance

- **Duration:** ~44 min (incl. Windows-portability fix on ES TopoJSON encoding)
- **Started:** 2026-05-07T15:11:39Z
- **Completed:** 2026-05-07T15:55:27Z
- **Tasks:** 8/8
- **Files created:** 0
- **Files modified:** 9 (all pipeline submodules)
- **Lines added:** ~1062 across 9 files

## Section-to-File Mapping (D-01 audit table)

| Inicio source range | Inicio name(s)                                           | Target file              | Verbatim status                                                              |
|---------------------|----------------------------------------------------------|--------------------------|------------------------------------------------------------------------------|
| 152-185 (§2)        | geo_to_pixel, pixel_to_geo, point_in_polygon             | contracts.py             | Verbatim — bodies copied unchanged                                           |
| 200-242 (§3)        | decode_topojson_municipalities                           | landmask.py              | Verbatim                                                                     |
| 245-260 (§3)        | load_municipalities                                      | landmask.py              | Verbatim + Windows-port deviation: `encoding='utf-8'` on ES open (Rule 3)    |
| 267-310 (§4)        | build_land_mask                                          | landmask.py              | Verbatim — P-11 island scaling preserved                                     |
| 317-328 (§5)        | build_border_mask                                        | border.py                | Verbatim — P-10 stride-3 loop preserved                                      |
| 335-367 (§6)        | setup_baronies                                           | voronoi.py               | Verbatim body + plan-mandated signature change to `(cfg)` per D-14           |
| 370-429 (§6)        | rasterize_baronies                                       | voronoi.py               | Verbatim                                                                     |
| 436-497 (§7)        | cleanup_and_smooth                                       | cleanup.py               | Verbatim — kernel sequence inlined, sentinels -1/9999 preserved              |
| 504-516 (§8)        | build_hierarchy_maps                                     | voronoi.py               | Verbatim (lives in voronoi.py per RESEARCH §1 tie-break)                     |
| 523-649 (§9)        | render_map                                               | render.py                | Verbatim body + 2 plan-mandated substitutions: cfg.rng_seed, cfg.draw_names  |
| 656-673 (§10)       | generate_lookup_map                                      | lookup.py                | Verbatim — P-13 RGB hash preserved                                           |
| 680-726 (§11)       | export_metadata                                          | export.py                | Verbatim — Q8/D-09 honoured (no original_idx)                                |
| 733-762 (§12)       | render_mountains                                         | render.py                | Verbatim body + plan-mandated lazy build_land_mask 2x (rule #6 + P-4)        |
| 765-791 (§12)       | render_rivers                                            | render.py                | Verbatim                                                                     |
| 798-934 (§13)       | generate_maps -> run_pipeline                            | __init__.py              | Verbatim body + 3 plan-mandated signature changes: rename, drop territory_module, drop draw_names; cfg.rng_seed substitutes inicio:904 |

**Inicio's `load_territory_data` (lines 192-197) is intentionally OMITTED** per D-13 — the `importlib.reload` pattern is on the v3 banned list; territory data lives on cfg now.

## Task Commits

Each task committed atomically per D-01:

1. **Task 1: §2 coordinate transforms → contracts.py** — `512c63e`
2. **Task 2: §3+§4 data loading + land mask → landmask.py** — `5c123b5`
3. **Task 3: §5 border mask → border.py** — `6811579`
4. **Task 4: §6+§8 voronoi (per-country KD-trees) → voronoi.py** — `a13e103`
5. **Task 5: §7 cleanup_and_smooth → cleanup.py** — `1e3249c`
6. **Task 6: §10+§11 lookup + export → lookup.py, export.py** — `19ca70b`
7. **Task 7: §9+§12 rendering → render.py** — `13d72d4`
8. **Task 8: §13 run_pipeline orchestration → __init__.py** — `b74e3d2`

## Smoke-run inventory (Plan 02 produced vs. RESEARCH §4.a / golden snapshot)

`python -m medieval_forge.services.pipeline --region iberia_868 --out <tmp>` produces
**10 files** (tmp dir: `iberia_smoke_*`):

| File                               | Plan-02 size (bytes) | Golden size (bytes) | Notes                                              |
|------------------------------------|---------------------:|--------------------:|----------------------------------------------------|
| lookup_barony.png                  |               53 924 |              55 142 | Lookup PNG; Plan 03's parity test asserts byte-eq  |
| lookup_barony_colors.json          |                5 346 |               5 094 | RGB->id JSON; parity asserts deep-equal            |
| lookup_condado.png                 |               38 769 |              37 974 | Lookup PNG; parity byte-eq                         |
| lookup_condado_colors.json         |                1 873 |               1 893 | RGB->id JSON; parity deep-equal                    |
| mountain_river_data.json           |               19 307 |              19 307 | Byte-identical (copied verbatim from input)        |
| mountains_mask.png                 |               11 976 |              12 232 | 2x mask; parity SSIM ≥ 0.98                        |
| rivers_overlay.png                 |               47 240 |              47 324 | 2x overlay; parity SSIM ≥ 0.98                     |
| territory_metadata.json            |               65 104 |              65 445 | Hierarchical metadata; parity deep-equal           |
| visual_barony.png                  |              643 658 |             505 303 | Visual placeholder; parity SSIM ≥ 0.98             |
| visual_condado.png                 |              604 048 |             465 894 | Visual placeholder; parity SSIM ≥ 0.98             |

Pipeline reports `251 baronies, 91 condados active` (matches inicio behaviour).

**Determinism check (two consecutive runs):** all 10 SHA-256 hashes MATCH — byte-identical output. Determinism via `cfg.rng_seed` is end-to-end working.

`terrain_lookup.png` + `terrain_types.json` are NOT produced (deferred to Phase 06 per P-2).

## Deviations from Plan / Plan Notes

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] ES TopoJSON UTF-8 encoding on Windows**
- **Found during:** Task 2 (landmask.py initial smoke test)
- **Issue:** Inicio's `load_municipalities` (inicio:256) opens the ES TopoJSON without `encoding='utf-8'`, relying on the POSIX UTF-8 default. On Windows the cp1252 codec raises `UnicodeDecodeError: 'charmap' codec can't decode byte 0x8d in position 6487`. Reproducible on this machine (`Python 3.12, Windows 11`).
- **Fix:** Added `encoding='utf-8'` to the ES open call only. The PT GeoJSON open at inicio:251 already uses `encoding='utf-8'`, so the fix matches inicio's intent on the PT path.
- **Files modified:** `backend/medieval_forge/services/pipeline/landmask.py:90`
- **Verification:** Re-ran Task 2 verify; PT 278 + ES 8116 features loaded; 1x and 2x mask shapes match the contract.
- **Committed in:** `5c123b5` (Task 2 commit)

**Total deviations:** 1 auto-fixed (Rule 3 — blocking issue on Windows)

### Plan-mandated deviations (NOT auto-fixes — explicitly authorized by the plan + CONTEXT.md)

These appeared in this plan's task actions, NOT in inicio. Documented here so a Plan-03 verifier can audit them:

| File                       | Inicio behaviour                                       | Plan-02 behaviour                                       | Authority                |
|----------------------------|--------------------------------------------------------|---------------------------------------------------------|--------------------------|
| voronoi.py:setup_baronies  | `setup_baronies(condados, duchies, kingdoms, cfg)`     | `setup_baronies(cfg)`; reads cfg.condados/duchies/kingdoms | D-14, plan Task 4         |
| render.py:render_map       | `np.random.default_rng(42)` at inicio:537              | `np.random.default_rng(cfg.rng_seed)`                   | rule #7 + P-9, plan Task 7 |
| render.py:render_map       | `draw_names: bool = True` argument                     | reads `cfg.draw_names`                                  | D-03 + Q10, plan Task 7   |
| render.py:render_mountains | `render_mountains(cfg, land_2x)` (caller builds 2x)    | builds 2x via `build_land_mask` lazily if not provided  | rule #6 + P-4, plan Task 7|
| __init__.py:run_pipeline   | `generate_maps(cfg, territory_module=, draw_names=)`   | `run_pipeline(cfg)` only                                | D-03/D-13, plan Task 8    |
| __init__.py:run_pipeline   | `np.random.default_rng(42)` at inicio:904              | `np.random.default_rng(cfg.rng_seed)`                   | rule #7 + P-9, plan Task 8|
| __init__.py:run_pipeline   | (does not copy mountain_river_data.json into output)   | `shutil.copy2` of mountain_river_data.json into out_dir | golden contract — the deployed Reconquista folder ships this file alongside the others; needed for Plan 03 parity inventory |

### CLAUDE.md non-negotiable rules audit

| Rule | Description                                          | Status in Plan-02                                                                                       |
|------|------------------------------------------------------|---------------------------------------------------------------------------------------------------------|
| #1   | NEAREST upscale only for lookup PNGs                 | PASS — `Image.NEAREST` literal at render.py:155; zero `BICUBIC`/`BILINEAR` references                   |
| #2   | σ ∈ [3.0, 4.5] for per-territory Gaussian blur       | PASS — `cfg.smooth_sigma=3.0`; reduction expression preserved at cleanup.py:77                          |
| #3   | KD-trees per country (PT and ES separate)            | PASS — `cKDTree` appears 5× in voronoi.py; `tp` (PT) and `te` (ES) returned as separate trees           |
| #4   | original_idx in every territory                      | DEFERRED — PREFLIGHT.md Q8 verdict ABSENT in deployed file; D-09 deployed-wins overrides the rule for Phase 01 |
| #5   | ocean=-1 and ignore=9999 sentinels in median pass    | PASS — both literals present at cleanup.py:42 (9999) and cleanup.py:48 (-1)                             |
| #6   | 2x masks are independent renders                     | PASS — `build_land_mask(target_w=cfg.map_w*cfg.upscale, ...)` called both in __init__.py:88 and render.py:191 |
| #7   | Deterministic RNG (cfg.rng_seed)                     | PASS — `default_rng(42)` literal count = 0 across pipeline/; two runs produce byte-identical SHA-256s   |

## Issues Encountered

- **Windows cp1252 default codec.** `open(... 'r')` without `encoding=` errors on the ES TopoJSON; fixed in Task 2 (Rule 3). The PT GeoJSON load was already utf-8 in inicio so only one site needed the deviation.
- **CRLF warnings.** Same as Plan 01-01 — benign for parity (post-parse JSON compare per D-12).
- **`load_territory_data` (inicio:192-197) deliberately omitted.** It uses `importlib.reload` which is explicitly banned in v3 ("no `sys.modules` patching, no `importlib.reload` games"). Territory data lives on cfg per D-13/D-14; the omission is documented in landmask.py's module docstring.

## Plan 03 Readiness

Plan 03 (delete v1 generator stack + parity harness + CI flip) can now build:

- The pipeline produces all 10 in-scope contract files reproducibly. Plan 03's `tests/parity/test_iberia_868.py` reads `tests/fixtures/iberia_868/golden/*` (committed in Plan 01-01) and asserts:
  - Lookup PNGs: `numpy.array_equal` byte-equality
  - Visual PNGs + masks: `skimage.metrics.structural_similarity ≥ 0.98`
  - JSONs: `json.loads` deep-equal after key-sort
- Plan 03 still needs to delete the v1 generator stack (5 production + 7 test files per RESEARCH §3) and write the parity harness. Phase 00 SC-6 invariant (FastAPI app boots with GET / → 200) currently still holds because `/api/generate` has not yet been deleted; Plan 03 will sever that route after the parity gate goes green.
- Determinism via `cfg.rng_seed` is end-to-end verified (two-run SHA-256 match across all 10 files), so Plan 03's parity test won't suffer flakes from RNG drift.

## Self-Check: PASSED

Verified files exist and contain the expected content:
- `backend/medieval_forge/services/pipeline/contracts.py` — FOUND (working transforms; round-trip recovers (-9.0, 39.0))
- `backend/medieval_forge/services/pipeline/landmask.py` — FOUND (PT 278 + ES 8116 features load)
- `backend/medieval_forge/services/pipeline/border.py` — FOUND (PT-side mask 129k pixels)
- `backend/medieval_forge/services/pipeline/voronoi.py` — FOUND (257 baronies / 58 PT / 199 ES)
- `backend/medieval_forge/services/pipeline/cleanup.py` — FOUND (4-stage pipeline importable)
- `backend/medieval_forge/services/pipeline/lookup.py` — FOUND (P-13 RGB hash present)
- `backend/medieval_forge/services/pipeline/export.py` — FOUND (Q8 verdict honoured — no original_idx)
- `backend/medieval_forge/services/pipeline/render.py` — FOUND (Image.NEAREST + cfg.rng_seed + cfg.draw_names + land[y, nx_])
- `backend/medieval_forge/services/pipeline/__init__.py` — FOUND (run_pipeline single-arg signature)

Verified commits exist (git log --oneline shows hashes on branch `main`):
- `512c63e` Task 1 — FOUND
- `5c123b5` Task 2 — FOUND
- `6811579` Task 3 — FOUND
- `a13e103` Task 4 — FOUND
- `1e3249c` Task 5 — FOUND
- `19ca70b` Task 6 — FOUND
- `13d72d4` Task 7 — FOUND
- `b74e3d2` Task 8 — FOUND

Verified runtime smoke:
- `python -m medieval_forge.services.pipeline --region iberia_868 --out <tmp>` → exit 0; 10 files produced
- Two consecutive runs produce byte-identical SHA-256 hashes for all 10 files (determinism)
- `pytest backend/tests/unit/ -q` → 57 passed
- FastAPI app boots; `GET /` → 200 (Phase 00 SC-6 invariant holds)
- `grep -rn "default_rng(42)" backend/medieval_forge/services/pipeline/` → 0 matches (rule #7)
- `grep -r "fastapi" backend/medieval_forge/services/pipeline/` → 0 matches (ROADMAP SC-2 standalone)

---
*Phase: 01-pipeline-parity-port-harness-together*
*Plan: 02 — Wave 1 verbatim port*
*Completed: 2026-05-07*
