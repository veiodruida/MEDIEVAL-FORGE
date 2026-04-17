---
phase: quick-260417-hpt
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/medieval_forge/lib/map_generator.py
  - backend/medieval_forge/services/generator.py
  - backend/medieval_forge/services/export.py
  - .planning/debug/terrain-real-geography.md
  - .planning/debug/resolved/terrain-real-geography.md
autonomous: true
requirements:
  - QUICK-260417-hpt
must_haves:
  truths:
    - "Running the generator pipeline (generate_maps) does NOT write rivers_overlay.png to the output dir"
    - "Visual maps (visual_condado.png, visual_barony.png) are NOT composited with rivers"
    - "render_rivers function still exists in lib/map_generator.py (disconnected, not deleted)"
    - "mountain_river_data_iberia.json is untouched (river data preserved for future reactivation)"
    - "All existing tests in test_terrain.py still pass"
    - "The resolved debug note documents the rivers-disconnect decision"
  artifacts:
    - path: "backend/medieval_forge/lib/map_generator.py"
      provides: "render_rivers function retained, pipeline call removed"
      contains: "def render_rivers"
    - path: ".planning/debug/resolved/terrain-real-geography.md"
      provides: "Resolved debug note with rivers-disconnect addendum"
  key_links:
    - from: "backend/medieval_forge/lib/map_generator.py generate_maps()"
      to: "render_rivers"
      via: "REMOVED — no longer invoked"
      pattern: "no call to render_rivers inside generate_maps"
---

<objective>
Disconnect rivers generation from the map pipeline while preserving all river assets
(render_rivers function + mountain_river_data_iberia.json) for future reactivation.

Purpose: User decided rivers are not wanted in current map output. This is a
reversible disconnection, NOT a deletion — the function and data stay intact so
rivers can be re-enabled later by restoring a single call site.

Output: Pipeline runs produce no rivers_overlay.png; visual maps are not
composited with rivers; function + JSON data remain available; tests still pass;
decision is documented in the resolved debug archive.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md
@backend/medieval_forge/lib/map_generator.py
@backend/medieval_forge/services/generator.py
@backend/medieval_forge/services/export.py
@backend/tests/test_terrain.py
@.planning/debug/terrain-real-geography.md

<interfaces>
Current rivers wiring (to be disconnected):

map_generator.py generate_maps() lines 1060-1070:
```python
# 13. Rivers
print("[14] Rivers...")
rivers_img = render_rivers(cfg)
if rivers_img is not None:
    rivers_img.save(f"{cfg.output_dir}/rivers_overlay.png")

    # Also composite rivers on visual maps
    for mt in ["condado", "barony"]:
        vis = Image.open(f"{cfg.output_dir}/visual_{mt}.png").convert("RGBA")
        vis.paste(rivers_img, (0, 0), rivers_img)
        vis.convert("RGB").save(f"{cfg.output_dir}/visual_{mt}.png")
```

Downstream callers of generate_terrain_lookup (line ~1074) pass `rivers_img=rivers_img`
but that parameter is documented as unused. Safe to pass `rivers_img=None`.

Whitelist (MUST remove rivers_overlay.png):
- generator.py line 42: `_GENERATOR_OUTPUTS` tuple includes "rivers_overlay.png"
- export.py line 32: `UNITY_ZIP_SPEC` includes "rivers_overlay.png"

Function signature (LEAVE UNTOUCHED):
```python
def render_rivers(cfg):  # lib/map_generator.py line 768
    """Render river lines as transparent PNG overlay."""
    ...
```

Test surface — test_terrain.py:
- Only reads JSON structure (lines 90-96); does NOT assert rivers_overlay.png exists.
- No changes required unless a new test needs to assert rivers are OFF.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Disconnect rivers from pipeline + remove from output whitelists</name>
  <files>
    backend/medieval_forge/lib/map_generator.py,
    backend/medieval_forge/services/generator.py,
    backend/medieval_forge/services/export.py
  </files>
  <action>
In backend/medieval_forge/lib/map_generator.py:
1. In generate_maps() (Section 14), locate the "# 13. Rivers" block (around lines
   1060-1070 — the print("[14] Rivers..."), the render_rivers(cfg) call, the
   rivers_img.save(), and the for-loop that composites rivers onto
   visual_condado.png / visual_barony.png). REPLACE the entire block with a short
   comment indicating the pipeline call was disabled and pointing to the
   resolved debug note. Keep the variable `rivers_img = None` so the subsequent
   `generate_terrain_lookup(..., rivers_img=rivers_img)` call remains valid.

   Example replacement:
   ```python
   # 13. Rivers — DISCONNECTED from pipeline on 2026-04-17.
   # render_rivers() remains available in this module for future reactivation.
   # See .planning/debug/resolved/terrain-real-geography.md (Rivers Disconnect addendum).
   rivers_img = None
   ```

2. In the module header docstring (lines 1-35) and in the final print summary
   (around lines 1083-1094), remove the line `rivers_overlay.png   — river lines`
   so the "DONE" summary no longer advertises a file the pipeline does not
   produce. Leave `mountains_mask.png` line intact.

3. LEAVE `def render_rivers(cfg):` (line 768) completely untouched. Do NOT
   delete it, do NOT change its signature, do NOT change its body.

In backend/medieval_forge/services/generator.py:
4. In the `_GENERATOR_OUTPUTS` tuple (around line 33), remove the
   `"rivers_overlay.png",` entry. The whitelist should no longer advertise
   rivers_overlay.png as an expected pipeline artifact.

5. In the comment at lines 230-232 that mentions "render_mountains() and
   render_rivers() have real geographic polygon data", update it to mention
   only render_mountains() (render_rivers is disconnected but data is still
   wired because the function itself is preserved — this is fine, but the
   comment should not imply the pipeline calls it).

In backend/medieval_forge/services/export.py:
6. In `UNITY_ZIP_SPEC` (line 23-36), remove `"rivers_overlay.png",` (line 32).
   Also check `PLACEHOLDER_FILES` — rivers_overlay.png is NOT in that set
   currently, so no change needed there. If export logic requires 12 files and
   this drops it to 11, that's intentional — the Unity zip will simply not
   contain a rivers overlay until rivers are reactivated.

Critical constraints:
- Do NOT touch mountain_river_data_iberia.json.
- Do NOT delete render_rivers().
- Do NOT change the mountain_river_json wiring in _build_region_config()
  (mountains still need it; render_rivers will also need it if reactivated).
- This is a disconnection ONLY — the function and data must survive for
  future reactivation by restoring the pipeline call site.
  </action>
  <verify>
    <automated>cd backend && python -c "from medieval_forge.lib.map_generator import render_rivers; print('render_rivers still exists:', render_rivers)" && python -m pytest tests/test_terrain.py -x -v</automated>
  </verify>
  <done>
- render_rivers function still importable from lib.map_generator
- "# 13. Rivers" block in generate_maps no longer calls render_rivers nor
  writes rivers_overlay.png nor composites rivers onto visual maps
- rivers_overlay.png removed from _GENERATOR_OUTPUTS and UNITY_ZIP_SPEC
- mountain_river_data_iberia.json unchanged (git diff shows it untouched)
- All 5 tests in test_terrain.py pass
  </done>
</task>

<task type="auto">
  <name>Task 2: Archive debug note to resolved/ with rivers-disconnect addendum</name>
  <files>
    .planning/debug/resolved/terrain-real-geography.md,
    .planning/debug/terrain-real-geography.md
  </files>
  <action>
The existing debug file lives at `.planning/debug/terrain-real-geography.md`
(status: awaiting_human_verify) — it documents the terrain-real-geography fix
that bundled mountain_river_data_iberia.json and rewrote generate_terrain_lookup.
The user's description references the path `.planning/debug/resolved/terrain-real-geography.md`,
so this task moves the debug file to `resolved/` and appends an addendum
documenting the rivers-disconnect decision.

Steps:
1. Read the current content of `.planning/debug/terrain-real-geography.md`.

2. Create `.planning/debug/resolved/terrain-real-geography.md` with the SAME
   content, but:
   a. Update the frontmatter: change `status: awaiting_human_verify` to
      `status: resolved`, and bump `updated:` to 2026-04-17T12:45:00Z.
   b. Append a new section at the end titled exactly:
      `## Addendum — 2026-04-17: Rivers Disconnected from Pipeline`

      The addendum must cover:
      - Decision: rivers no longer produced by the pipeline
      - Scope of change: render_rivers() retained in lib/map_generator.py;
        mountain_river_data_iberia.json retained intact; pipeline call in
        generate_maps() removed; rivers_overlay.png dropped from
        _GENERATOR_OUTPUTS and UNITY_ZIP_SPEC
      - Reversibility: to re-enable rivers, restore the "# 13. Rivers" block
        in generate_maps() and re-add "rivers_overlay.png" to both whitelists
      - Rationale: per user request on 2026-04-17 — rivers not desired in
        current map output; data preserved for potential future reactivation
      - Note about existing rivers_overlay.png files in user project
        directories: cleanup not required (per user: "não precisa ser limpo")

3. Delete the original `.planning/debug/terrain-real-geography.md` (it has
   been moved to resolved/).

Keep all existing content (Current Focus, Symptoms, Eliminated, Evidence,
Resolution sections) intact in the resolved copy. Only the frontmatter status/
updated fields change, and the new addendum section is appended at the bottom.
  </action>
  <verify>
    <automated>test -f .planning/debug/resolved/terrain-real-geography.md && ! test -f .planning/debug/terrain-real-geography.md && grep -q "Rivers Disconnected from Pipeline" .planning/debug/resolved/terrain-real-geography.md && grep -q "status: resolved" .planning/debug/resolved/terrain-real-geography.md</automated>
  </verify>
  <done>
- `.planning/debug/resolved/terrain-real-geography.md` exists with status: resolved
- `.planning/debug/terrain-real-geography.md` no longer exists (moved to resolved/)
- Addendum section present with decision, scope, reversibility, rationale
  </done>
</task>

</tasks>

<verification>
Full-plan verification checklist:

1. `cd backend && python -m pytest tests/test_terrain.py -x -v` — all 5 tests pass.
2. `grep -n "render_rivers" backend/medieval_forge/lib/map_generator.py` — only
   the function definition remains; no call site inside generate_maps().
3. `grep -n "rivers_overlay" backend/medieval_forge/` — appears nowhere in
   services/generator.py `_GENERATOR_OUTPUTS`, nowhere in services/export.py
   `UNITY_ZIP_SPEC`, and nowhere in the print-summary of generate_maps().
4. `git diff backend/medieval_forge/services/mountain_river_data_iberia.json` —
   empty (file must be untouched).
5. `test -f .planning/debug/resolved/terrain-real-geography.md` — passes.
6. `test ! -f .planning/debug/terrain-real-geography.md` — passes (moved).
</verification>

<success_criteria>
- Pipeline run produces no rivers_overlay.png artifact
- Visual maps (visual_condado.png, visual_barony.png) have no river overlay
- render_rivers function still defined and importable
- mountain_river_data_iberia.json byte-identical to pre-change state
- All existing test_terrain.py tests pass
- Debug note archived to resolved/ with rivers-disconnect addendum
- Change is fully reversible: restoring the "# 13. Rivers" block + two
  whitelist entries re-enables rivers end-to-end
</success_criteria>

<output>
After completion, no summary file required for this quick task. The resolved
debug note serves as the permanent record of the decision.
</output>
