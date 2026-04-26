---
phase: quick-260426-pcy
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scripts/diagnose_orphans.py
  - backend/medieval_forge/services/territories_geojson.py
  - backend/medieval_forge/lib/map_generator.py
  - backend/tests/services/test_territories_geojson_consistency.py
autonomous: false
requirements:
  - QUICK-260426-pcy-orphan-fix
must_haves:
  truths:
    - "After generation, every condado id in territory_metadata.json appears as a feature in territories.geojson"
    - "Capital drag on previously-orphaned condados (braganca, madrid, leon, malaga) returns 200, not 404"
    - "The root cause of the orphan drop is identified by evidence, not guessed"
  artifacts:
    - path: "scripts/diagnose_orphans.py"
      provides: "One-shot diagnostic that compares metadata vs geojson vs lookup PNG and prints evidence per orphan"
    - path: "backend/tests/services/test_territories_geojson_consistency.py"
      provides: "Regression test asserting set(metadata.condados.id) == set(geojson.features.id) on a fixture that previously dropped"
  key_links:
    - from: "backend/medieval_forge/lib/map_generator.py:export_metadata"
      to: "backend/medieval_forge/services/territories_geojson.py:build_territories_geojson"
      via: "shared pc/level_map reasoning — every metadata entry must produce exactly one geojson feature"
      pattern: "id set equality between territory_metadata.json and territories.geojson"
---

<objective>
Fix the orphan bug: 13 condados in `territory_metadata.json` are missing from
`territories.geojson` after generation (e.g. braganca, madrid, leon, malaga).
Capital drag on these returns 404. Source: `.planning/phases/04-canvas-editing-basic/04-HUMAN-UAT.md` line 176.

Both `export_metadata` (map_generator.py:681) and `generate_lookup_map`
(map_generator.py:657) iterate the same `pc` with the same `np.any` /
`npx > 0` gate, so in theory they agree. But the bug is observed, so ONE of
the following is true:

1. `pc` is mutated between lookup-PNG write (line 1027) and metadata export (line 1033).
2. PNG roundtrip in `emit_territories_from_disk` drops pixels — most likely
   because a condado's deterministic RGB
   `((i*37+50)%256, (i*73+80)%256, (i*113+30)%256)` collides with
   `cfg.ocean_far` (the background fill at `lookup_map[H,W,3]` initialisation,
   `generate_lookup_map` line 660). Those pixels become indistinguishable from
   background after PNG roundtrip.
3. `rasterio.features.shapes` produces shapes that `unary_union` collapses to
   degenerate / empty geometry not caught by `if not geoms: continue`.
4. Manual-provider stale-research bug (UAT bug #4) — metadata and geojson
   produced from different research files.

Plan strategy: diagnose first, then fix the proven cause, then add a regression
invariant. Do not commit to fix path (a fallback Voronoi) or (b skip-from-metadata)
until Task 1 evidence selects the correct branch.

Purpose: keep metadata and geojson consistent so every metadata condado is
clickable / editable on the canvas.
Output: identified root cause, targeted fix, regression test enforcing
`set(metadata.condados.id) == set(geojson.features.id)`.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@./CLAUDE.md
@.planning/STATE.md
@.planning/phases/04-canvas-editing-basic/04-HUMAN-UAT.md
@backend/medieval_forge/lib/map_generator.py
@backend/medieval_forge/services/territories_geojson.py
@backend/medieval_forge/services/generator.py

<interfaces>
<!-- Key code paths the executor needs. Extracted from codebase. -->

From backend/medieval_forge/lib/map_generator.py:

```python
# line 657 — generate_lookup_map: writes lookup_<label>.png + lookup_<label>_colors.json
def generate_lookup_map(result, level_map, n_items, cfg, label="barony"):
    h, w = result.shape
    lk = np.full((h, w, 3), list(cfg.ocean_far), dtype=np.uint8)  # ← background fill
    color_map = {}
    for i in range(n_items):
        m = level_map == i if label != "barony" else result == i
        if not np.any(m):
            continue
        r = (i * 37 + 50) % 256
        g = (i * 73 + 80) % 256
        b = (i * 113 + 30) % 256
        lk[m] = [r, g, b]
        color_map[f"{r},{g},{b}"] = i  # ← KEY: original i (orig_idx)
    return lk, color_map

# line 681 — export_metadata: writes territory_metadata.json
def export_metadata(condados, duchies, kingdoms, bars, result, pc, cfg):
    ...
    for ci, c in enumerate(condados):
        npx = int(np.sum(pc == ci))
        if npx == 0:
            continue  # ← drops 0-pixel condados (these are not the orphans)
        metadata["condados"].append({...})
```

From backend/medieval_forge/services/territories_geojson.py:

```python
# line 137 — emit_territories_from_disk: rebuilds pc from PNG, calls build_territories_geojson
# Already does orig_idx → meta_ci remap via original_condados (Problem B fix)

# line 78 — build_territories_geojson: iterates metadata-position condados
def build_territories_geojson(project_id, pc, condados, cfg):
    pc32 = pc.astype(np.int32)
    shapes_per_idx = {}
    for geom, idx in rasterio.features.shapes(pc32, mask=(pc32 >= 0)):
        i = int(idx)
        shapes_per_idx.setdefault(i, []).append(shape(geom))
    features = []
    for ci, c in enumerate(condados):
        geoms = shapes_per_idx.get(ci, [])
        if not geoms:
            continue   # ← THE DROP POINT for orphans
        u = unary_union(geoms)
        ...
```

The disk artifacts under `<DATA_DIR>/projects/<uuid>/generated/`:
- `territory_metadata.json` — `{"condados":[{"id","name","lon","lat",...}], ...}`
- `territories.geojson` — FeatureCollection, feature.id == condado id
- `lookup_condado.png` — RGB image, one unique RGB per surviving condado
- `lookup_condado_colors.json` — `{"r,g,b": orig_idx}`
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Diagnose — write one-shot script that identifies which of the 4 hypotheses is actually causing the drop</name>
  <files>scripts/diagnose_orphans.py</files>
  <action>
Create `scripts/diagnose_orphans.py` that takes a project UUID (CLI arg) and:

1. Loads from `<DATA_DIR>/projects/<uuid>/generated/`:
   - `territory_metadata.json` → `metadata_ids = {c["id"] for c in meta["condados"]}`
   - `territories.geojson` → `geojson_ids = {f["id"] for f in fc["features"]}`
   - `lookup_condado_colors.json` → `colors = {"r,g,b": orig_idx}`
   - `lookup_condado.png` → numpy array via PIL

   Resolve `DATA_DIR` exactly the way the app does:
   `from medieval_forge.database import DATA_DIR` then
   `<DATA_DIR>/projects/<uuid>/generated/`.

2. Compute `orphans = metadata_ids - geojson_ids`. If empty, print "no orphans"
   and exit 0 (script must be safe on healthy projects).

3. Reconstruct `original_condados` order: the UAT mentions multi-country
   research; the project DB has the canonical condados. Read the project's
   research result from the DB (use `medieval_forge.database` async session;
   the script may run sync via `asyncio.run`). Get `condados` field exactly
   as `services/generator.py` line 360 reads it (`territory_data["condados"]`).
   This gives us `orig_idx` per condado id.

4. For each orphan condado id, print a row with:
   - `id`, `name` (from metadata)
   - `orig_idx` (its position in `original_condados`)
   - `expected_rgb` = `((orig_idx*37+50)%256, (orig_idx*73+80)%256, (orig_idx*113+30)%256)`
   - `is_in_colors_json` = `f"{r},{g},{b}" in colors`
   - `pixel_count_in_png` = count of `(img == expected_rgb).all(axis=-1)`
   - `equals_ocean_far` = whether `expected_rgb == tuple(_build_region_config(...).ocean_far)`
     (call the same `_build_region_config` from `services/generator.py` so we
     reproduce the exact ocean_far the run used; load the project's config from DB).
   - `npx_metadata` = `c["pixel_count"]` from metadata (export_metadata writes this).

5. Also print a summary count for each hypothesis class:
   - H2 ocean_far collision: `equals_ocean_far == True`
   - H1 mutation: `is_in_colors_json == True AND pixel_count_in_png == 0`
   - H3 degenerate geom: `is_in_colors_json == True AND pixel_count_in_png > 0`
     (means PNG has pixels, colors.json has the entry, but build_territories_geojson
     still didn't produce a shape — would need a follow-up to test
     `rasterio.features.shapes` on that mask).
   - H4 manual-provider mismatch: orphan id is NOT in `original_condados` at all.

6. Print final line: `ROOT_CAUSE_HYPOTHESIS: H<n>` where n is whichever bucket
   contains all/most orphans. If split across buckets, print `MIXED` and list
   each bucket's count.

Run the script against the user's project that exhibits the bug. Capture its
output verbatim into a comment block at the TOP of the script for posterity
(so Task 2 has the evidence in the same file the executor edits). Then commit.

The user must point you at a project UUID that has the orphan bug. Ask in the
checkpoint if not provided up front.
  </action>
  <verify>
    <automated>python scripts/diagnose_orphans.py &lt;project_uuid&gt; (must print ROOT_CAUSE_HYPOTHESIS: H&lt;n&gt; and exit 0)</automated>
  </verify>
  <done>Script committed with the diagnostic output captured in its top-of-file comment. The output names ONE primary hypothesis (H1/H2/H3/H4) backed by per-orphan evidence rows.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: Confirm the diagnosis and select fix branch</name>
  <what-built>Diagnostic script output identifying the root cause hypothesis (H1, H2, H3, or H4) and per-orphan evidence rows.</what-built>
  <how-to-verify>
Read the diagnostic output captured in `scripts/diagnose_orphans.py`'s top
comment. Confirm the assignment of orphans to a hypothesis bucket is correct.
The fix branch is mechanically determined by which hypothesis is the cause:

- **H2 (ocean_far collision)** → fix in `map_generator.py:generate_lookup_map`:
  when the deterministic `(r,g,b)` for `i` equals `cfg.ocean_far`, perturb
  (e.g. `(r ^ 1, g, b)` or rotate to next non-colliding triple). Update
  `color_map` with the perturbed RGB. This preserves the metadata/PNG/colors
  invariant and adds zero orphans by construction.

- **H1 (mutation between line 1027 and 1033)** → identify the mutation in
  `map_generator.py` lines 1027-1033 and either move metadata export BEFORE
  the mutation or compute `pc` snapshot. (Currently no obvious mutation exists
  in those lines; if H1 wins, the mutation is real and must be located.)

- **H3 (degenerate geometry)** → fix in
  `services/territories_geojson.py:build_territories_geojson`: when
  `unary_union(geoms)` collapses to empty/invalid, fall back to a tiny
  centroid polygon using the metadata `lon`/`lat` so the feature still exists.

- **H4 (manual-provider mismatch)** → out of scope for this quick task; the
  pipeline is operating on inconsistent inputs. Stop here and convert the
  remainder to a separate task targeting UAT bug #4.

Confirm the selected branch matches the evidence. If H4 wins, instruct the
executor to stop and do NOT proceed to Task 3 / Task 4 in this plan.
  </how-to-verify>
  <resume-signal>Reply with "branch: H1" / "branch: H2" / "branch: H3" / "branch: H4 stop". Anything else means revise Task 1.</resume-signal>
</task>

<task type="auto">
  <name>Task 3: Implement the fix selected in Task 2 and add the metadata↔geojson consistency invariant</name>
  <files>backend/medieval_forge/lib/map_generator.py, backend/medieval_forge/services/territories_geojson.py</files>
  <action>
Implement ONLY the branch confirmed in Task 2.

**If H2 (ocean_far collision):**
- Edit `backend/medieval_forge/lib/map_generator.py:generate_lookup_map`.
- After computing `(r, g, b)` for index `i`, if `(r, g, b) == tuple(cfg.ocean_far)`
  OR `f"{r},{g},{b}"` is already in `color_map` (collision with a prior i),
  search for the nearest non-colliding triple by incrementing
  (e.g. `r = (r + 1) % 256`, retry up to 256 times; raise a clear error if
  no slot exists, which won't happen for n_items < 256³).
- Update both `lk[m] = [r, g, b]` and `color_map[f"{r},{g},{b}"] = i` with the
  resolved triple.
- Do NOT change the deterministic formula for non-colliding indices — keep
  existing PNG outputs identical for unaffected runs.

**If H3 (degenerate geometry):**
- Edit `backend/medieval_forge/services/territories_geojson.py:build_territories_geojson`.
- When `geoms` is empty for a `ci` that exists in `condados`, build a fallback
  feature: a tiny square polygon centered at `(c[2], c[3])` (the metadata
  `lon`/`lat`) with side length `min(0.001, (lon_max-lon_min)/map_w)` in
  degrees, properties `{id, name, neighbors: []}`. This guarantees the feature
  exists so the editor doesn't 404. Add a `WARN`-level log per fallback so
  these stay visible.

**If H1 (mutation):**
- Locate the mutation between map_generator.py lines 1027-1033, then either
  snapshot `pc` (`pc_for_meta = pc.copy()`) immediately after `build_hierarchy_maps`
  and pass that snapshot to `export_metadata`, OR re-order the steps so
  metadata is computed from the same `pc` that the lookup PNG was painted
  from. Add a comment naming the bug.

**Always (regardless of branch):**
- In `services/territories_geojson.py:build_territories_geojson`, after writing
  `territories.geojson`, verify the invariant in the function itself:
  ```python
  meta_ids = {c[0] for c in condados}
  feat_ids = {f["id"] for f in features}
  missing = meta_ids - feat_ids
  if missing:
      logger.error(
          "territories.geojson MISSING %d condados from metadata: %s",
          len(missing), sorted(missing)[:10],
      )
  ```
  This is a soft assertion (log, not raise) so legitimate generation failures
  still produce a usable file, but the symptom is loud in logs.

Do NOT modify both branches. Do NOT add a fallback Voronoi computation —
it is not a valid `.gitignore` for the actual root cause.
  </action>
  <verify>
    <automated>python scripts/diagnose_orphans.py &lt;same_project_uuid&gt; (must print "no orphans" after re-running generation; user must regenerate the affected project before running)</automated>
  </verify>
  <done>The selected fix is implemented in the correct module. Re-running generation on the affected project produces zero orphans per the diagnostic script. The soft-assertion log line is present in `build_territories_geojson`.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: Regression test — assert metadata.condados.id ⊆ geojson.features.id</name>
  <files>backend/tests/services/test_territories_geojson_consistency.py</files>
  <behavior>
- Test 1: `test_metadata_and_geojson_have_matching_condado_ids` — given a
  fixture `pc` numpy array + `condados` list crafted to trigger the previously-
  orphaning condition (H2: include an index whose deterministic RGB equals a
  known `cfg.ocean_far`; OR H3: include a 1-pixel condado that historically
  collapsed), call `build_territories_geojson` and assert
  `set(meta_ids) == set(feature_ids)`.
- Test 2: `test_no_drop_when_color_collides_with_ocean_far` (only if H2 path
  was implemented) — explicitly construct an `i` whose deterministic
  `(r,g,b) == cfg.ocean_far`, run `generate_lookup_map`, verify the resulting
  `color_map` contains `i` under a non-ocean key and the PNG has pixels for `i`.
- Test 3: `test_orphan_invariant_logs_when_violated` — manually construct
  inputs that DO produce a missing feature (e.g. pass condados list with an
  id that has no pixels), assert the `ERROR` log line is emitted (use
  `caplog`).
  </behavior>
  <action>
Write the tests in `backend/tests/services/test_territories_geojson_consistency.py`
using pytest. Follow the project convention from feedback-tests-descriptive.md
(descriptive names + explicit numeric fixtures).

Use small handcrafted numpy arrays (e.g. 10×10) — do NOT depend on real
project data. Build `_ProjCfg` directly. The fixture must reproduce the
historical bug (the test should FAIL on a checkout BEFORE Task 3's fix and
PASS after).

Run: `pytest backend/tests/services/test_territories_geojson_consistency.py -x -v`
  </action>
  <verify>
    <automated>pytest backend/tests/services/test_territories_geojson_consistency.py -x -v</automated>
  </verify>
  <done>All three tests pass on the post-fix code. Test 1 documented to fail on the pre-fix code (committer notes the SHA where it would fail).</done>
</task>

</tasks>

<verification>
1. `scripts/diagnose_orphans.py <project_uuid>` prints "no orphans" after regeneration.
2. `pytest backend/tests/services/test_territories_geojson_consistency.py -x -v` — all pass.
3. Manual: in the canvas editor, drag the capital of a previously-orphaned
   condado (braganca, madrid, leon, or malaga) — request returns 200, polygon
   updates.
4. `set(metadata.condados[*].id) == set(geojson.features[*].id)` for any newly
   generated project.
</verification>

<success_criteria>
- [ ] Diagnostic script identifies a single primary hypothesis backed by evidence
- [ ] Fix targets the proven hypothesis (no speculative fallback Voronoi)
- [ ] Regression test asserts the metadata↔geojson id-set equality and would have caught the bug
- [ ] Soft-assertion log fires when a future regression appears
- [ ] Manual capital drag on previously-orphaned condados succeeds
- [ ] No change to the public `territories.geojson` schema or `lookup_condado_colors.json` shape (D-04 black-box preserved for Unity consumers)
</success_criteria>

<output>
After completion, create `.planning/quick/260426-pcy-fix-orphan-bug-13-condados-in-territory-/260426-pcy-SUMMARY.md` describing:
- which hypothesis (H1/H2/H3/H4) was the cause, with the diagnostic table
- which file was modified for the fix
- the regression test file and what it asserts
- any follow-ups (e.g. if H4 was actually present in addition to the primary cause)
</output>
