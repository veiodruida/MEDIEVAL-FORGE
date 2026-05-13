---
phase: 05-region-generalization
reviewed: 2026-05-13T00:00:00Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - backend/medieval_forge/api/v3/artifacts.py
  - backend/medieval_forge/api/v3/render.py
  - backend/medieval_forge/schemas.py
  - backend/medieval_forge/services/export.py
  - backend/medieval_forge/services/pipeline/__init__.py
  - backend/medieval_forge/services/pipeline/contracts.py
  - backend/medieval_forge/services/pipeline/region_loader.py
  - backend/medieval_forge/services/pipeline/terrain.py
  - backend/tests/e2e/test_france_1066_export_contract.py
  - backend/tests/parity/test_iberia_868_yaml.py
  - backend/tests/unit/test_gen_toy_france.py
  - backend/tests/unit/test_region_loader.py
  - backend/tests/unit/test_terrain_render.py
  - backend/tests/unit/test_v3_artifacts.py
  - backend/tests/unit/test_v3_status.py
  - data/regions/england_1216.yaml
  - frontend/package.json
  - frontend/src/components/projects/NewProjectModal.tsx
  - scripts/run_france_uat.ps1
  - scripts/run_france_uat.sh
findings:
  critical: 1
  warning: 4
  info: 6
  total: 11
status: issues_found
---

# Phase 05: Code Review Report (Plans 11-15 + hotfix 5daa563)

**Reviewed:** 2026-05-13
**Depth:** standard
**Files Reviewed:** 20
**Status:** issues_found

## Summary

Phase 05 (region generalization) ships YAML-driven region loading, France 1066 toy region with autogen, terrain palette closure for SC-3 (Plan 11), the live UAT runner scripts (Plan 12), and the WR-01 single-country dedupe hotfix (`5daa563`). The architectural shape is solid — `RegionConfig` remains the only mutable input, pydantic validates inputs (`extra='forbid'`, `smooth_sigma` clamped to [3.0, 4.5]), and threat-modelled paths (T-05-01-01..03) are guarded.

**One critical defect was found:** the Unity ZIP export in `services/export.py` is missing `rivers_overlay.png` from `UNITY_ZIP_SPEC`. The contract is declared as 12 files in CLAUDE.md and in `contracts.EXPORT_FILE_CONTRACT`, but `UNITY_ZIP_SPEC` lists only 11 entries — the rivers overlay is generated and served via `/artifacts/`, yet never written into the shipped ZIP. Tests that walk `UNITY_ZIP_SPEC` (e.g. `test_zip_contents`) iterate the truncated list and silently pass, so the gap is invisible to CI.

The remaining warnings touch auto-generation edge cases and a regression-prone `assert`-as-validation choice; the info items are minor cosmetics.

## Critical Issues

### CR-01: `UNITY_ZIP_SPEC` is missing `rivers_overlay.png` — Unity ZIP ships 11/12 contract files

**File:** `backend/medieval_forge/services/export.py:25-37`
**Issue:** `UNITY_ZIP_SPEC` lists 11 filenames but the 12-file Unity contract (CLAUDE.md §"v3 Pipeline Contract" row 11, `contracts.EXPORT_FILE_CONTRACT` line 204, `api/v3/artifacts.ARTIFACT_FILES` line 46) includes `rivers_overlay.png`. The pipeline writes the file to disk (`pipeline/__init__.py:229`), the artifacts endpoint serves it, but `build_unity_zip()` iterates `UNITY_ZIP_SPEC` only — so the downloaded ZIP never contains it. Consumers downloading the ZIP receive an incomplete export. `test_zip_contents` and `test_build_unity_zip_assembles_12_files` both iterate `UNITY_ZIP_SPEC`, so the missing entry is also a missing assertion: the tests pass on 11 files while their docstrings still claim 12.

This is a contract-level defect: CLAUDE.md §v3 Pipeline Contract is explicit that the 12-file export is non-negotiable, and Phase 06 will validate against it.

**Fix:**
```python
# backend/medieval_forge/services/export.py
UNITY_ZIP_SPEC: tuple[str, ...] = (
    "lookup_barony.png",
    "lookup_condado.png",
    "lookup_barony_colors.json",
    "lookup_condado_colors.json",
    "terrain_lookup.png",
    "terrain_types.json",
    "territory_metadata.json",
    "mountains_mask.png",
    "rivers_overlay.png",   # <-- ADD: CLAUDE.md row 11
    "visual_barony.png",
    "visual_condado.png",
    "mountain_river_data.json",
)
assert len(UNITY_ZIP_SPEC) == 12, "Unity contract: 12 files"
```
Also: derive `UNITY_ZIP_SPEC` from `contracts.EXPORT_FILE_CONTRACT` (or add a unit test importing both and asserting set-equality) to eliminate the duplication and prevent silent re-drift.

## Warnings

### WR-01: `ProjectCreate` does not enforce `period_start < period_end`

**File:** `backend/medieval_forge/schemas.py:32-50, 74-80`
**Issue:** `ProjectUpdate._check_period_ordering` enforces `period_start < period_end` via `model_validator(mode="after")`, but `ProjectCreate` has no equivalent validator. A new project can be created with `period_start >= period_end`, which `ProjectUpdate` would later refuse to patch. The asymmetry is pre-Phase-05 but `country_qid` enhancements (`_resolve_country_list`) were added in this module without surfacing the gap.

**Fix:**
```python
class ProjectCreate(BaseModel):
    # ... existing fields ...
    @model_validator(mode="after")
    def _check_period_ordering(self) -> "ProjectCreate":
        if self.period_start >= self.period_end:
            raise ValueError("period_start must be less than period_end")
        return self
```

### WR-02: `_autogen_territories` overwrites partially-populated `kingdoms`/`duchies`

**File:** `backend/medieval_forge/services/pipeline/region_loader.py:222-242`
**Issue:** Autogen is triggered solely on `not kwargs.get("condados")`. If a region YAML declares `kingdoms` and `duchies` (e.g. a future hand-curated region) but leaves `condados: []`, autogen runs and replaces the curated kingdoms/duchies with `{"unnamed": ...}` / `{"unnamed_duchy": ...}`. The curator's data is silently dropped. The current `england_1216.yaml` template-only path never reaches autogen, and `france_1066.yaml` legitimately starts with all three empty — but the condition is fragile.

**Fix:** Either gate autogen on all three being empty, or fail loudly when only `condados` is empty:
```python
co_empty = not kwargs.get("condados")
kg_empty = not kwargs.get("kingdoms")
du_empty = not kwargs.get("duchies")
if co_empty and not (kg_empty and du_empty):
    raise ValueError(
        f"region {key!r}: condados empty but kingdoms/duchies populated — "
        "autogen would overwrite curated data. Provide condados or clear all three."
    )
if co_empty:
    # ... existing autogen ...
```

### WR-03: `terrain.render_terrain_lookup` uses `assert` for input validation (stripped under `python -O`)

**File:** `backend/medieval_forge/services/pipeline/terrain.py:89-95`
**Issue:** Shape/dtype invariants are enforced with `assert` statements. Python optimised mode (`python -O`) strips asserts, so any caller passing the wrong `land` dtype/shape in a production deployment would silently corrupt the terrain raster (e.g. `arr[land] = PLAINS_RGB` with an int array indexing would broadcast unexpectedly). Although `medieval-forge start` is unlikely to ship with `-O`, defensive checks belong to runtime, not optimisation flags.

**Fix:**
```python
def render_terrain_lookup(land: np.ndarray, cfg: "RegionConfig") -> np.ndarray:
    if land.dtype != np.bool_:
        raise TypeError(f"land must be bool[H,W], got dtype={land.dtype}")
    if land.shape != (cfg.map_h, cfg.map_w):
        raise ValueError(
            f"land shape mismatch: expected ({cfg.map_h}, {cfg.map_w}), got {land.shape}"
        )
    # ... rest unchanged
```

### WR-04: `_render_producer` cleanup ordering — narrow race window between sentinel and queue pop

**File:** `backend/medieval_forge/api/v3/render.py:182-187`
**Issue:** The `finally` block pops `_RUN_QUEUES[project_id]` *after* `await queue.put(None)`. If a client calls `/render/stream` between the `put(None)` and the `pop`, it gets the queue, drains the sentinel immediately, and sees nothing of the run. After the pop, late subscribers get 404. The race is narrow but produces an inconsistent UX: same elapsed-time client either sees "queue gone (404)" or "queue empty (immediate done)". The comment "WR-02 fix: prevent late-subscriber hang" indicates the previous bug was hanging; the current ordering trades a hang for a race. Document the contract explicitly, or hold the queue for a grace window after `put(None)`.

**Fix (minimal — clarify the contract):**
```python
@router.get("/{project_id}/render/stream")
async def stream_render(project_id: str) -> StreamingResponse:
    """Drain the per-project render SSE queue until the None sentinel.

    Subscribe immediately after `/render` returns 202; the queue is evicted
    in the producer's `finally` block once the run completes, so late
    subscribers (after the run finished) receive 404. There is a narrow
    race between sentinel emission and eviction where a subscriber may
    receive an immediately-completed stream — frontend MUST treat this
    case identically to a 404.
    """
```

## Info

### IN-01: `region_loader._DEFAULT_REGIONS_DIR` uses brittle `parents[4]`

**File:** `backend/medieval_forge/services/pipeline/region_loader.py:50`
**Issue:** `Path(__file__).resolve().parents[4] / "data" / "regions"` breaks silently if anyone moves `region_loader.py` into a deeper or shallower package. The pattern is documented as matching `regions.py`, but it's still a magic number.
**Fix:** Compute the repo root once at package init (e.g. by walking up until `pyproject.toml` is found) and re-use that across the codebase.

### IN-02: `_autogen_territories` accepts unused `rng_seed`

**File:** `backend/medieval_forge/services/pipeline/region_loader.py:363-381`
**Issue:** `rng_seed` parameter is documented as "kept for forward compatibility" but never consumed. Readers tracing the call site at line 223 must follow the function to learn the seed is dead.
**Fix:** Drop the parameter from the signature; reintroduce only when an RNG path actually appears.

### IN-03: Unused locals in `run_pipeline_incremental` voronoi cold-recovery branch

**File:** `backend/medieval_forge/services/pipeline/__init__.py:557-558`
**Issue:** `pi, ei, tp, te` are unpacked from `setup_baronies(cfg)` but never used in the else-branch (raw is already cached). Triggers no warning today but adds visual noise and risks future readers thinking they should be wired in.
**Fix:** Use `_` placeholders or split into a dedicated helper that returns only the needed tuple.

### IN-04: `defaultRegionKey` returns implicit empty string for "no region available"

**File:** `frontend/src/components/projects/NewProjectModal.tsx:22-28`
**Issue:** The triple fallback (Iberia → first-with-dataset → first → `''`) returns an empty string when there are zero regions. Submit handler at line 82 short-circuits on `!regionKey`, but the UX is "button stays disabled" with no explanation. An explicit `null` return forces callers to handle the empty-list case visibly.
**Fix:** Change return type to `string | null`, and when null, render a toast/inline message "Nenhuma região disponível — cheque sua instalação".

### IN-05: `run_france_uat.ps1` process-kill heuristic relies on `MainWindowTitle` (won't match headless servers)

**File:** `scripts/run_france_uat.ps1:12-15`
**Issue:** `Get-Process | Where-Object { $_.ProcessName -match "medieval-forge|uvicorn|node" -and $_.MainWindowTitle -match "vite|forge" }` filters by `MainWindowTitle`, which is empty for background/console processes. The Bash variant (`pkill -f`) matches command line — so headless `uvicorn`/`vite` processes survive on Windows. Result: re-runs of the UAT script leave stale dev servers on ports 8000/5173, causing the next `Start-Job` to fail silently.
**Fix:**
```powershell
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match "medieval-forge|uvicorn|vite" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
```

### IN-06: `england_1216.yaml` declares identical `pt_geojson` / `es_input` without an explanatory comment

**File:** `data/regions/england_1216.yaml:16-17`
**Issue:** Both `pt_geojson` and `es_input` point at `inputs/england_municipalities.geojson`. Currently moot because the file is intentionally absent (D-12 template-only), but when v3.1 adds real inputs, the WR-01 dedupe fix in `_autogen_territories` (commit `5daa563`, Plan 05-13) will be the only thing preventing the double-read. A future regression in dedupe would silently double England's condado count. An inline comment captures the load-bearing intent.
**Fix:**
```yaml
dataset:
  # Single-country region: pt_geojson and es_input point at the same file.
  # _autogen_territories deduplicates by absolute path (Plan 05-13 WR-01 fix).
  pt_geojson: inputs/england_municipalities.geojson
  es_input: inputs/england_municipalities.geojson
  mountain_river_json: inputs/mountain_river_data.json
```

---

_Reviewed: 2026-05-13_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
