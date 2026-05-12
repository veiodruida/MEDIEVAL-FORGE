---
phase: 05-region-generalization
reviewed: 2026-05-12T00:00:00Z
depth: standard
files_reviewed: 41
files_reviewed_list:
  - alembic/versions/0004_add_region_key_to_projects.py
  - alembic/versions/0005_make_v1_legacy_fields_nullable_for_v3.py
  - backend/medieval_forge/api/v3/__init__.py
  - backend/medieval_forge/api/v3/generate.py
  - backend/medieval_forge/api/v3/projects.py
  - backend/medieval_forge/api/v3/regions.py
  - backend/medieval_forge/api/v3/render.py
  - backend/medieval_forge/main.py
  - backend/medieval_forge/models.py
  - backend/medieval_forge/services/pipeline/__main__.py
  - backend/medieval_forge/services/pipeline/contracts.py
  - backend/medieval_forge/services/pipeline/export.py
  - backend/medieval_forge/services/pipeline/region_loader.py
  - backend/tests/api/test_regions_endpoint.py
  - backend/tests/conftest.py
  - backend/tests/e2e/test_france_1066_export_contract.py
  - backend/tests/fixtures/uat_setup.py
  - backend/tests/integration/test_generate_render_load_region.py
  - backend/tests/integration/test_render_endpoint.py
  - backend/tests/parity/conftest.py
  - backend/tests/parity/test_iberia_868_live.py
  - backend/tests/parity/test_iberia_868_render_default.py
  - backend/tests/parity/test_iberia_868_yaml.py
  - backend/tests/unit/test_dag_tokens.py
  - backend/tests/unit/test_england_1216_missing_inputs.py
  - backend/tests/unit/test_gen_toy_france.py
  - backend/tests/unit/test_region_loader.py
  - backend/tests/unit/test_run_pipeline_on_stage.py
  - data/regions/england_1216.yaml
  - data/regions/france_1066.yaml
  - frontend/src/api/__tests__/useRegions.test.ts
  - frontend/src/api/client.ts
  - frontend/src/api/useRegions.ts
  - frontend/src/components/projects/NewProjectModal.tsx
  - frontend/src/components/projects/__tests__/NewProjectModal.test.tsx
  - frontend/src/pages/ProjectList.tsx
  - frontend/src/types/region.ts
  - frontend/tests/uat/playwright/france_1066_create_project.spec.ts
  - pyproject.toml
  - scripts/gen_toy_france.py
findings:
  critical: 0
  warning: 2
  info: 7
  total: 9
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-05-12
**Depth:** standard
**Files Reviewed:** 41
**Status:** issues_found

## Summary

Phase 05 ("region-generalization") delivers a YAML-driven region loader, the
`POST /api/v3/projects` endpoint with strict input validation, a `GET /api/v3/regions`
discovery endpoint, two new Alembic migrations, frontend region-picker UI, and a France
1066 toy region with autogen territories. The architecture is solid and the focus areas
flagged by the workflow (path-traversal guards, pydantic enum validation, σ range,
SQLite batch_alter_table, Pitfall 9 immutability) are all covered correctly.

Findings cluster around two areas:

1. **Autogen double-read of dataset files (Warning).** When `pt_geojson` and `es_input`
   point at the same file (intentional for single-country regions like france_1066 and
   england_1216), `_autogen_territories` reads it twice and produces a doubled seed set.
   No functional break — the dedup loop preserves unique `original_idx` — but the
   resulting condado count is ~2× what the YAML intent implies, and the unit test
   bound (`>=40 condados`) is loose enough to mask it.

2. **One Pitfall 9 violation in a test fixture (Warning).** `test_iberia_868_yaml.py`
   mutates `cfg.output_dir` directly after `load_region()` instead of using
   `dataclasses.replace()`. The autouse `clear_region_cache_between_tests` hides the
   blast radius, but the focus-area mandate explicitly calls Pitfall 9 out.

The remaining items are small: a dead-code helper in render.py, an unused test fixture
helper with a duplicated YAML key, a redundant try/except, one test that doesn't test
what its name claims, and minor React patterns in NewProjectModal.

No security issues. No critical bugs. Pipeline determinism guarantees (seed, NEAREST
upscale, σ range, KD-tree-per-country, original_idx uniqueness) are all enforced by
schema + tests.

## Warnings

### WR-01: Autogen reads the same dataset file twice when pt_geojson == es_input

**File:** `backend/medieval_forge/services/pipeline/region_loader.py:389-411`
**Issue:** `_autogen_territories` iterates `(dataset.pt_geojson, dataset.es_input)` and
parses each file unconditionally. Both `france_1066.yaml` and `england_1216.yaml` point
both fields at the same file (a documented single-country fallthrough pattern). The
result is that every GeoJSON feature is appended to `features[]` twice, producing
~2× the condados that the YAML implies (e.g., France toy: 40-50 polygons → 80-100
autogen condados). `enumerate(features, start=1)` keeps `original_idx` unique so the
parity test `original_idx not unique` does NOT fire — but Voronoi seeds collide and
downstream baronies inherit duplicate centroids. The unit test
`test_load_region_autogen` asserts `len(cfg.condados) >= 40` which passes for both 50
and 100, masking the doubling.

**Fix:**
```python
# region_loader.py:389
seen_paths: set[Path] = set()
for geojson_path in (dataset.pt_geojson, dataset.es_input):
    if geojson_path is None or not geojson_path.exists():
        continue
    if geojson_path in seen_paths:
        continue                  # skip duplicate pt==es fallthrough
    seen_paths.add(geojson_path)
    try:
        data = json.loads(geojson_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        continue
    # ... rest unchanged
```
Tighten the unit test bound to `40 <= len(cfg.condados) <= 50` so the regression is
caught next time.

### WR-02: Parity test mutates load_region() singleton directly (Pitfall 9 violation in test code)

**File:** `backend/tests/parity/test_iberia_868_yaml.py:42-44`
**Issue:** The fixture uses
```python
clear_region_cache()
cfg = load_region("iberia_868")
cfg.output_dir = str(out)
```
This mutates the cached singleton — the exact pattern CLAUDE.md's "Pitfall 9 /
T-05-04-04" rule prohibits and that `test_load_region_singleton_not_mutated` regression-
guards in `backend/tests/integration/test_generate_render_load_region.py`. The autouse
`clear_region_cache_between_tests` resets state between tests so this works in CI today,
but the focus areas explicitly call out Pitfall 9 and every other touchpoint in this
phase uses `dataclasses.replace(...)` (see `parity/conftest.py:97-98`, `__main__.py:26`,
`uat_setup.py:65`, `test_iberia_868_render_default.py:60`, `test_france_1066_export_contract.py:58`,
both API producers).

**Fix:**
```python
# backend/tests/parity/test_iberia_868_yaml.py:42
from dataclasses import replace
# ...
out = tmp_path_factory.mktemp("iberia_868_yaml_actual")
clear_region_cache()
cfg = replace(load_region("iberia_868"), output_dir=str(out))
run_pipeline(cfg)
return out
```

## Info

### IN-01: Dead helper `_make_on_stage` in render.py shadowed by inlined `_on_stage_tracking`

**File:** `backend/medieval_forge/api/v3/render.py:94-99`
**Issue:** `_make_on_stage(queue, loop)` is defined at module scope but never
referenced. The producer at lines 153-156 inlines an equivalent `_on_stage_tracking`
closure that additionally appends to `completed_stages`. The standalone helper is dead
code; if a maintainer reuses it, the `completed_stages` tracking (needed for the D-13
`stage_cancel` emission at line 178) silently breaks.

**Fix:** Remove the unused `_make_on_stage` function (and the unused `Callable` import
if no other use remains).

### IN-02: No-op try/except in `_resolve_dataset`

**File:** `backend/medieval_forge/services/pipeline/region_loader.py:350-360`
**Issue:**
```python
try:
    return ProjectDataset(...)
except FileNotFoundError:
    raise
except ValueError:
    raise
```
Catches exactly the two exceptions that the inner `_resolve` helper raises and
re-raises them unchanged. Equivalent to no `try` block at all.

**Fix:**
```python
return ProjectDataset(
    pt_geojson=_resolve(ds.pt_geojson),
    es_input=_resolve(ds.es_input),
    mountain_river_json=_resolve(ds.mountain_river_json),
    dem_raster=_resolve(ds.dem_raster),
)
```

### IN-03: Unused test fixture helper with duplicated `kingdoms:` YAML key

**File:** `backend/tests/unit/test_region_loader.py:100-141`
**Issue:** `_make_toy_region_with_territories` is defined but no test imports/calls it
(verified via grep — single occurrence in the file). The embedded YAML also declares
`kingdoms:` twice in a row (lines 125-127 and 128-130). YAML parsers silently use the
last occurrence, but it signals the helper has never been exercised.

**Fix:** Delete the helper, or wire it into a test that exercises the explicit-
territory (non-autogen) code path of `_convert_territory_data`.

### IN-04: `useRegions` queryKey test does not validate what its name claims

**File:** `frontend/src/api/__tests__/useRegions.test.ts:81-95`
**Issue:** The `'uses queryKey ["v3", "regions"]'` test calls
`vi.spyOn({useQuery}, 'useQuery')` on a fresh object literal, which never replaces
the `useQuery` imported by the hook under test. The body comment admits
*"queryKey verified by integration"*. The test as written only smoke-checks that
`useRegions` is defined — already covered by the other three tests in the block.

**Fix:** Either delete the test, or replace the body with a real assertion against
`queryClient.getQueryCache().getAll()[0].queryKey` to verify `['v3', 'regions']` is
actually used.

### IN-05: `Select.Root` mixes controlled and uncontrolled mode

**File:** `frontend/src/components/projects/NewProjectModal.tsx:144-148`
**Issue:**
```tsx
<Select.Root
  defaultValue="iberia_868"
  value={regionKey}
  onValueChange={setRegionKey}
  ...
```
A Radix Select is controlled iff `value` is set; passing both `defaultValue` and
`value` mixes controlled and uncontrolled modes. Radix uses the controlled `value`
(making `defaultValue` dead), but React DevTools warns and the next maintainer reads
contradictory intent.

**Fix:** Remove `defaultValue="iberia_868"` — the initial value is already wired via
the `useEffect(... setRegionKey(defaultRegionKey(regions))` at lines 42-46.

### IN-06: `<Text as="label">` without `htmlFor` breaks accessibility (and Playwright label selectors)

**File:** `frontend/src/components/projects/NewProjectModal.tsx:120, 140`
**Issue:** Two labels are rendered as `<Text as="label" size="2" weight="medium">...`
without `htmlFor` (or wrapping the input). They produce a visual label but not an
accessibility association. The Playwright UAT spec at
`frontend/tests/uat/playwright/france_1066_create_project.spec.ts:46-48` already
documents the consequence — it must select the input by placeholder because no
`<label>`/`<input>` link exists.

**Fix:**
```tsx
<Text as="label" size="2" weight="medium" htmlFor="new-project-name">
  Nome do projeto
</Text>
<Box mt="1">
  <TextField.Root
    id="new-project-name"
    value={name}
    ...
```
Apply the same pattern to the Região label + Select.Trigger (Radix accepts `id` on
`Select.Trigger`).

### IN-07: `Toast.Root duration={Infinity}` — semantically suspicious

**File:** `frontend/src/components/projects/NewProjectModal.tsx:210`
**Issue:** `duration={Infinity}` is passed to Radix `Toast.Root`. Radix internally
`setTimeout(_, duration)`; in browsers, `setTimeout(_, Infinity)` clamps to its max
(~24.8 days) so the practical behavior is "never auto-dismiss," which is the intent.
But the explicit Radix-documented sentinel for "no auto-close" is omitting `duration`
or using a very large finite number; `Infinity` is undocumented and may regress on a
future Radix patch.

**Fix:** Replace with a documented value:
```tsx
<Toast.Root open={toastOpen} onOpenChange={setToastOpen} duration={1000 * 60 * 60 * 24}>
```
Or omit `duration` entirely and rely on the user-driven dismiss (the "Tentar novamente"
button + close gesture already handle it).

---

_Reviewed: 2026-05-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
