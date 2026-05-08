---
phase: 01-pipeline-parity-port-harness-together
reviewed: 2026-05-08T00:00:00Z
depth: standard
files_reviewed: 26
files_reviewed_list:
  - .gitattributes
  - .github/workflows/ci.yml
  - .gitignore
  - backend/medieval_forge/data/__init__.py
  - backend/medieval_forge/data/regions/__init__.py
  - backend/medieval_forge/data/regions/iberia_868/__init__.py
  - backend/medieval_forge/data/regions/iberia_868/territory_data.py
  - backend/medieval_forge/main.py
  - backend/medieval_forge/services/pipeline/__init__.py
  - backend/medieval_forge/services/pipeline/__main__.py
  - backend/medieval_forge/services/pipeline/border.py
  - backend/medieval_forge/services/pipeline/cleanup.py
  - backend/medieval_forge/services/pipeline/contracts.py
  - backend/medieval_forge/services/pipeline/export.py
  - backend/medieval_forge/services/pipeline/landmask.py
  - backend/medieval_forge/services/pipeline/lookup.py
  - backend/medieval_forge/services/pipeline/regions.py
  - backend/medieval_forge/services/pipeline/render.py
  - backend/medieval_forge/services/pipeline/voronoi.py
  - backend/tests/integration/test_app_boot.py
  - backend/tests/parity/__init__.py
  - backend/tests/parity/conftest.py
  - backend/tests/parity/test_iberia_868.py
  - backend/tests/unit/test_parity_refresh_tool.py
  - backend/tests/unit/test_pipeline_cli.py
  - backend/tests/unit/test_pipeline_module.py
  - tests/fixtures/iberia_868/golden/README.md
findings:
  critical: 1
  warning: 3
  info: 4
  total: 8
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-05-08
**Depth:** standard
**Files Reviewed:** 26 (one zero-byte file omitted: see Info IN-04)
**Status:** issues_found

## Summary

The Phase 01 verbatim port of `inicio/map_generator.py` is faithful: all six non-negotiable
rules from CLAUDE.md (NEAREST upscale, sigma in [3.0, 4.5], per-country KD-trees, sentinels
in median pass, independent 2x mask, draw_names off) are correctly preserved in the
submodule split. The three documented signature substitutions (D-03 run_pipeline rename,
D-13 territory data on cfg, D-03 draw_names from cfg) are applied consistently across
`__init__.py`, `regions.py`, `voronoi.py`, and `render.py`. Determinism is anchored to
`np.random.default_rng(cfg.rng_seed)` in both render call sites (`render.py:57`,
`__init__.py:152`), and the territory data file is byte-identical to `inicio/territory_data_v3.py`
(verified via `diff -q`).

The harness is sound: the parity test suite (10 parametrised tests across byte-equal /
SSIM / JSON-deep-equal) covers 10 of 12 contract files (terrain pair correctly deferred per
P-2), the session-scoped `pipeline_output` fixture amortises the ~45 s pipeline cost, and
the `--refresh-baseline / --confirm` CLI plugin is unit-tested without ever touching the real
golden directory (good test isolation).

The findings below are concentrated in the CI plumbing (one **Critical** that will block
the parity job from ever passing on CI), pipeline-input path resolution, and end-to-end
coverage gaps in the CLI smoke test.

## Critical Issues

### CR-01: Parity CI job will fail because checkout does not fetch LFS

**File:** `.github/workflows/ci.yml:32-46` (and indirectly `.gitattributes:5`)

**Issue:**
`.gitattributes:5` marks
`data/regions/iberia_868/inputs/pt_concelhos_wgs84.geojson` as a Git LFS file:

```
data/regions/iberia_868/inputs/pt_concelhos_wgs84.geojson filter=lfs diff=lfs merge=lfs -text
```

But the `pytest-parity` job uses `actions/checkout@v4` with default options, which does
**not** fetch LFS objects (`lfs: false` is the default). On a fresh CI runner the file is
checked out as a ~130-byte LFS pointer, not the GeoJSON content.

When `pipeline_output` (parity conftest, line 92-98) runs `run_pipeline(cfg)`:

1. `landmask.load_municipalities` (line 84-87) opens the LFS pointer file
2. `json.load(f)` raises `json.JSONDecodeError` on the pointer's `version https://git-lfs.github.com/spec/v1\n...` text

The non-skippable parity job promised by RESEARCH §7 (and reinforced by the workflow
comment at line 45 "Non-skippable from Phase 01. Any parity-test failure blocks merge.")
will fail on every CI run with an opaque error before reaching any parity assertion.

This affects only the `pytest-parity` job (the unit job does not need LFS inputs because
`test_parity_refresh_tool.py` uses synthetic fixtures).

**Fix:** Add `with: lfs: true` to the parity job's checkout step.

```yaml
  pytest-parity:
    name: pytest parity + integration
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          lfs: true
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      ...
```

Optional hardening: add an early sanity check in the workflow that fails loud rather
than producing a confusing JSONDecodeError, e.g.:

```yaml
      - name: Verify LFS inputs were fetched (not pointers)
        run: |
          head -c 100 data/regions/iberia_868/inputs/pt_concelhos_wgs84.geojson \
            | grep -q 'git-lfs' && { echo "LFS pointer not resolved"; exit 1; } || true
```

## Warnings

### WR-01: Pipeline input paths in `regions.py` are cwd-dependent and fail silently

**File:** `backend/medieval_forge/services/pipeline/regions.py:32-34`

**Issue:**
`iberia_config()` sets three input paths as **relative** strings:

```python
municipality_pt_geojson="data/regions/iberia_868/inputs/pt_concelhos_wgs84.geojson",
municipality_es_topojson="data/regions/iberia_868/inputs/es-atlas-pkg/package/es/municipalities.json",
mountain_river_json="data/regions/iberia_868/inputs/mountain_river_data.json",
```

These resolve only when the process is started from the repo root. The parity session
fixture (`backend/tests/parity/conftest.py:92-98`) does not anchor the cwd, so a
developer running `pytest backend/tests/parity/` from inside `backend/` will hit:

1. `os.path.exists(cfg.municipality_pt_geojson)` returns False (lines 84, 89 of `landmask.py`)
2. `load_municipalities` silently returns `(None, [])`
3. `build_land_mask` paints zero polygons -> all-ocean mask -> empty `result` array
4. `setup_baronies` runs, `rasterize_baronies` writes -1 everywhere
5. `cleanup_and_smooth` runs on -1-only input
6. Tests fail with confusing pixel-level diffs instead of "input not found"

This is **not** a verbatim-port artifact: inicio used different relative paths
(`../Assets/StreamingAssets/Maps/...`) and D-11 deliberately rewrote them. The new
location is correct; the issue is that nothing forces the path to resolve from a stable
anchor.

**Fix:** Resolve the paths against the package data directory at config time. Add a
helper in `regions.py`:

```python
from pathlib import Path

_INPUTS_DIR = Path(__file__).resolve().parents[2] / "data" / "regions" / "iberia_868" / "inputs"

def iberia_config() -> RegionConfig:
    cfg = RegionConfig(
        ...
        municipality_pt_geojson=str(_INPUTS_DIR / "pt_concelhos_wgs84.geojson"),
        municipality_es_topojson=str(_INPUTS_DIR / "es-atlas-pkg" / "package" / "es" / "municipalities.json"),
        mountain_river_json=str(_INPUTS_DIR / "mountain_river_data.json"),
        ...
    )
```

Alternatively, raise a clear error in `load_municipalities` when configured paths exist
on cfg but do not resolve on disk (rather than silently returning empty data).

### WR-02: `__main__.py` end-to-end CLI flow is not exercised by any test

**File:** `backend/medieval_forge/services/pipeline/__main__.py:13-20` and
`backend/tests/unit/test_pipeline_cli.py`

**Issue:**
`test_pipeline_cli.py` covers only `--help`, exiting before `run_pipeline(cfg)` executes:

```python
result = subprocess.run(
    [sys.executable, "-m", "medieval_forge.services.pipeline", "--help"],
    ...
)
```

The parity fixture (`conftest.py:92-98`) calls `run_pipeline` via direct import, never
through the `__main__` shim. The three lines that matter for ROADMAP SC-2 ("the pipeline
must run without FastAPI via `python -m medieval_forge.services.pipeline`") are
untested end-to-end:

```python
cfg = REGIONS[args.region]()        # __main__.py:18
cfg.output_dir = args.out           # __main__.py:19
run_pipeline(cfg)                   # __main__.py:20
```

A typo on any of those (e.g. `args.region` -> `args.regions`, `cfg.output_dir` ->
`cfg.outdir`) would not be caught by the existing CI gate, only by humans running the
command manually.

**Fix:** Add one slow-marker test that runs the CLI subprocess against a tmpdir and
asserts the 10 expected files are produced. To avoid doubling parity-job runtime, mark
it `@pytest.mark.slow` and run it only on a release branch, OR run it once nightly.

```python
import os
import subprocess
import sys
import pytest

@pytest.mark.slow
def test_main_cli_end_to_end(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "medieval_forge.services.pipeline",
         "--region", "iberia_868", "--out", str(tmp_path)],
        capture_output=True, text=True, timeout=120,
        cwd=os.environ.get("REPO_ROOT", "."),
    )
    assert result.returncode == 0, result.stderr
    expected = {"lookup_barony.png", "lookup_condado.png",
                "lookup_barony_colors.json", "lookup_condado_colors.json",
                "territory_metadata.json", "visual_condado.png",
                "visual_barony.png", "mountains_mask.png",
                "rivers_overlay.png", "mountain_river_data.json"}
    produced = {p.name for p in tmp_path.iterdir()}
    assert expected <= produced, f"missing: {expected - produced}"
```

### WR-03: `lookup.py` ignores `level_map` for `label == "barony"` despite accepting it

**File:** `backend/medieval_forge/services/pipeline/lookup.py:35`

**Issue:**

```python
m = level_map == i if label != "barony" else result == i
```

For `label == "barony"`, the function ignores its `level_map` argument and uses `result`
instead. The orchestrator (`__init__.py:127`) currently passes `result` for both
positions in the barony case (`("barony", result, nb)`), so the two branches happen to
be equivalent today. But:

1. The signature is misleading — a future refactor that passes a different `level_map`
   would silently produce wrong RGBs (the bug would not surface until parity tests
   compared the lookup PNG, far from the cause).
2. This is **verbatim** with inicio:660-661, so per the review-context rule it should
   not be flagged as a deviation. However the equality `result == i` bypassing the
   parameter is still a latent foot-gun in the new submodule API surface where
   `generate_lookup_map` is callable independently of the orchestrator.

**Fix:** Either keep the verbatim body and add a docstring note, or — preferable for the
submodule API — drop the dead branch by removing the `result` parameter entirely and
having callers always pass the level map they want:

```python
def generate_lookup_map(level_map: np.ndarray, n_items: int,
                        cfg: RegionConfig) -> Tuple[np.ndarray, dict]:
    h, w = level_map.shape
    lk = np.full((h, w, 3), list(cfg.ocean_far), dtype=np.uint8)
    color_map = {}
    for i in range(n_items):
        m = level_map == i
        if not np.any(m):
            continue
        r = (i * 37 + 50) % 256
        g = (i * 73 + 80) % 256
        b = (i * 113 + 30) % 256
        lk[m] = [r, g, b]
        color_map[f"{r},{g},{b}"] = i
    return lk, color_map
```

If the verbatim contract takes precedence (D-01), then at minimum add a `# verbatim
inicio:660 — level_map ignored when label=='barony'; do not refactor` comment so the
next reader does not chase a phantom regression.

## Info

### IN-01: `original_idx` deferred — flag for downstream phases

**File:** `backend/medieval_forge/services/pipeline/export.py:6-15`

**Issue:**
CLAUDE.md non-negotiable rule #4 says every territory must carry `original_idx` (the
Nájera-bug fix). `export.py` correctly documents that this is intentionally absent in
Phase 01 per PREFLIGHT.md Q8 + D-09 (deployed wins). The deferred work is a Phase 06
concern.

**Fix:** No code change in Phase 01. Carry the deferred constraint forward — the next
phase that touches `territory_metadata.json` (Phase 06 export-validation) must add
`original_idx` and refresh the golden fixture in the same commit. Recommend dropping a
single-line tracker into ROADMAP.md or the Phase 06 PREFLIGHT.

### IN-02: `bd[np.where(bc == ci)[0][0]]` — guarded but worth a one-line comment

**File:** `backend/medieval_forge/services/pipeline/render.py:67`

**Issue:**

```python
di_val = bd[np.where(bc == ci)[0][0]] if np.any(bc == ci) else 0
```

The guard `np.any(bc == ci)` correctly prevents the `IndexError` when no barony belongs
to a condado, but the chained subscripts (`np.where(...)[0][0]`) are easy to misread
during refactor. This is verbatim inicio:547, so do not change the body — but a short
inline comment would help future readers:

**Fix:**

```python
# verbatim inicio:547 — first barony's duchy idx; guarded by `np.any(bc == ci)`
di_val = bd[np.where(bc == ci)[0][0]] if np.any(bc == ci) else 0
```

### IN-03: Bare `except:` in `render.py` — verbatim, but document scope of the swallow

**File:** `backend/medieval_forge/services/pipeline/render.py:130`

**Issue:**

```python
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11)
    font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
except:
    font = font_sm = ImageFont.load_default()
```

This is verbatim inicio:610 (D-01) and the cfg.draw_names default is `False`, so the
block is unreachable in CI/parity. Not flagging for change. If draw_names ever becomes a
default-on path (Phase 04 parameter studio), narrowing the except clause to
`(OSError, IOError)` and logging the error would help cross-platform diagnostics.

**Fix:** No change in Phase 01. Note this for whichever phase enables `draw_names`.

### IN-04: Three zero-byte files reported by the file scope

**File:**
- `backend/medieval_forge/data/__init__.py`
- `backend/medieval_forge/data/regions/__init__.py`
- `backend/medieval_forge/data/regions/iberia_868/__init__.py`

**Issue:**
The Read tool reports each as "shorter than the provided offset (1)" — i.e. zero-byte
files. Empty `__init__.py` files are perfectly valid for Python package markers, but
since the `data/regions/iberia_868/` directory ships territory data that other modules
import via `from ...data.regions.iberia_868.territory_data import (KINGDOMS, ...)`,
an empty `__init__.py` is sufficient and correct. This is **not** an issue — recording
here only because the review scope asked for findings on every listed file and these
three otherwise wouldn't appear in the report.

**Fix:** None. Empty `__init__.py` is the conventional, intentional state.

---

_Reviewed: 2026-05-08_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
