---
phase: 02-read-only-canvas-viewer
plan: 04
type: execute
wave: 1
depends_on: [02-01, 02-02, 02-03]
gap_closure: true
closes_gaps: [G-01, G-02, G-03]
files_modified:
  - backend/medieval_forge/services/territories_geojson.py
  - backend/medieval_forge/services/baronies_geojson.py
  - backend/medieval_forge/services/generator.py
  - backend/tests/test_territories_geojson.py
  - backend/tests/test_baronies_geojson.py
  - backend/tests/test_generator_e2e.py
  - frontend/src/hooks/useCanvasArtifacts.ts
  - frontend/src/components/canvas/__tests__/CanvasViewer.test.tsx
autonomous: true
requirements: [CANVAS-01, CANVAS-03, CANVAS-04]

must_haves:
  truths:
    - "Running run_generation on a real pipeline input produces territories.geojson and baronies.geojson files on disk (closes G-01)"
    - "If the emitter crashes for any reason, run_generation raises and the FastAPI background task records status='error_generating' with last_error (closes G-02)"
    - "A backend integration test exercises the real emit_*_from_disk codepath end-to-end and fails loudly if either geojson artifact is missing (closes G-03)"
    - "Frontend TerritoryLayer receives fills from a backend-produced {condado_id: '#hex'} map — no #666666 fallback in the happy path"
    - "The original lookup_condado_colors.json / lookup_barony_colors.json files keep their Unity-consumed {'r,g,b': idx} format unchanged (D-04 black-box preserved)"
  artifacts:
    - path: "backend/medieval_forge/services/territories_geojson.py"
      provides: "emit_territories_from_disk that parses the real {'r,g,b': idx} format and emits territories.geojson + condado_colors.json sidecar"
      contains: "condado_colors.json"
    - path: "backend/medieval_forge/services/baronies_geojson.py"
      provides: "emit_baronies_from_disk that parses the real {'r,g,b': idx} format and emits baronies.geojson + barony_colors.json sidecar"
      contains: "barony_colors.json"
    - path: "backend/medieval_forge/services/generator.py"
      provides: "Emitter call site that lets exceptions propagate (no silent swallow) + whitelist entries for the two new sidecar files"
      contains: "condado_colors.json"
    - path: "backend/tests/test_generator_e2e.py"
      provides: "[BLOCKING] integration test that runs the real run_generation path against a synthetic fixture and asserts both geojson files exist and parse"
      contains: "def test_run_generation_emits_both_geojson_artifacts"
    - path: "frontend/src/hooks/useCanvasArtifacts.ts"
      provides: "Fetches condado_colors.json / barony_colors.json sidecars (shape Record<id, hex>) for UI fills"
      contains: "condado_colors.json"
  key_links:
    - from: "generator.py _run_pipeline_sync"
      to: "emit_territories_from_disk + emit_baronies_from_disk"
      via: "direct call, no try/except swallow"
      pattern: "emit_territories_from_disk\\(project_id"
    - from: "emit_territories_from_disk"
      to: "pc raster painted with idx from {'r,g,b': idx} directly"
      via: "no hex parsing; int values from map_generator SECTION 11"
      pattern: "pc\\[mask\\]\\s*=\\s*idx|pc\\[mask\\]\\s*=\\s*int\\(idx\\)"
    - from: "frontend useCanvasArtifacts [2]"
      to: "/api/projects/{id}/preview/condado_colors.json"
      via: "TanStack Query; shape Record<condado_id, '#hex'>"
      pattern: "condado_colors\\.json"
---

<objective>
Close the three P2-02 verification gaps so the canvas renders real condado/barony polygons end-to-end against a generated project.

Purpose: Unblock UAT items 1, 2, 5, 7, 9 (currently FAILED or BLOCKED in 02-HUMAN-UAT.md) by fixing the emitter format mismatch (G-01), surfacing pipeline errors instead of swallowing them (G-02), and adding the missing real-pipeline integration test (G-03).

Output: Adapter rewrite (no modification to `lib/map_generator.py` — D-04 honored), hard exception propagation in `generator.py`, one new pytest integration test, sidecar JSON files for frontend consumption, two-line frontend URL switch.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/02-read-only-canvas-viewer/02-CONTEXT.md
@.planning/phases/02-read-only-canvas-viewer/02-VERIFICATION.md
@.planning/phases/02-read-only-canvas-viewer/02-HUMAN-UAT.md
@backend/medieval_forge/services/territories_geojson.py
@backend/medieval_forge/services/baronies_geojson.py
@backend/medieval_forge/services/generator.py
@backend/tests/test_territories_geojson.py
@backend/tests/test_baronies_geojson.py
@frontend/src/hooks/useCanvasArtifacts.ts

<interfaces>
<!-- Real on-disk format from backend/medieval_forge/lib/map_generator.py SECTION 10 -->
<!-- generate_lookup_map() writes: color_map[f"{r},{g},{b}"] = i   where i is the territory/barony index -->
<!-- DO NOT modify lib/map_generator.py (D-04). All fixes live in service-layer adapters. -->

Real shape of lookup_condado_colors.json (as produced by map_generator.py:672):
```json
{ "123,45,67": 0, "34,210,12": 1, "...": 2 }
```
Key: "r,g,b" (base-10, no # prefix, comma-joined).
Value: int — the condado's index into the `condados` list (same ordering used by build_territories_geojson).

Same shape for lookup_barony_colors.json:
```json
{ "200,10,30": 0, "15,80,240": 1 }
```
Value: int — the barony's index into the `baronies` list.

Sidecar files this plan introduces for the frontend
(Unity still consumes the original lookup_*_colors.json unchanged — D-04 preserved):

`condado_colors.json`:
```json
{ "C_ALPHA": "#7b2d43", "C_BETA": "#22d20c" }
```
Key: condado id (from condados[i][0]). Value: "#rrggbb" hex.

`barony_colors.json`:
```json
{ "B_A1": "#c80a1e", "B_B1": "#0f50f0" }
```
Key: barony name (from baronies[i]["name"]). Value: "#rrggbb" hex.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Rewrite emit_territories_from_disk + emit_baronies_from_disk to consume real format and emit sidecars</name>

  <read_first>
    - backend/medieval_forge/services/territories_geojson.py (lines 126-155 — current broken adapter)
    - backend/medieval_forge/services/baronies_geojson.py (lines 64-86 — same defect)
    - backend/medieval_forge/lib/map_generator.py (lines 655-674, SECTION 10 — real format emitter — DO NOT MODIFY)
    - backend/tests/test_territories_geojson.py (existing unit tests — preserve all 4)
    - backend/tests/test_baronies_geojson.py (existing unit tests — preserve all 4)
  </read_first>

  <behavior>
    - Test 1 (territories): given a 10x10 lookup_condado.png painted with two distinct colors and a lookup_condado_colors.json = {"10,20,30": 0, "40,50,60": 1}, emit_territories_from_disk must produce territories.geojson with 2 features whose ids come from territory_metadata.json condados[0][0] and condados[1][0], AND produce condado_colors.json = {"<id0>": "#0a141e", "<id1>": "#28323c"}.
    - Test 2 (territories): malformed key "not,a,triple" in lookup_condado_colors.json raises ValueError (NOT TypeError — explicit).
    - Test 3 (territories): int index out of range (>= len(condados)) is skipped, not crashed (logger.warning); remaining features still emitted.
    - Test 4 (baronies): analogous to Test 1 — emit_baronies_from_disk produces baronies.geojson + barony_colors.json = {barony_name: "#hex"} using the same parsing.
    - Test 5 (baronies): condado_idx on a barony whose condado has no pixels still produces a feature with the empty-string condado_id fallback already in build_baronies_geojson (preserved behavior).
    - Existing 9 unit tests (build_* direct-call path) must still pass unchanged.
  </behavior>

  <action>
    Replace the `emit_territories_from_disk` function body at `backend/medieval_forge/services/territories_geojson.py:126-155` with the following logic:

    ```python
    def emit_territories_from_disk(
        project_id: str,
        generated_dir: Path,
        cfg: _ProjCfg,
    ) -> Path:
        """Read-back orchestrator. Parses the REAL map_generator lookup format
        `{"r,g,b": idx}` (see lib/map_generator.py SECTION 10, generate_lookup_map).
        DO NOT change to hex parsing — that schema does not exist on disk.
        """
        meta = json.loads((generated_dir / "territory_metadata.json").read_text())
        condados_meta = meta["condados"]
        condados = [
            [c["id"], c["name"], c["lon"], c["lat"], c.get("duchy", ""), c.get("baronies", [])]
            for c in condados_meta
        ]
        colors_raw = json.loads((generated_dir / "lookup_condado_colors.json").read_text())

        from PIL import Image
        img = np.array(Image.open(generated_dir / "lookup_condado.png").convert("RGB"))
        H, W, _ = img.shape
        pc = np.full((H, W), -1, dtype=np.int32)

        sidecar: dict[str, str] = {}
        for rgb_key, idx_val in colors_raw.items():
            parts = rgb_key.split(",")
            if len(parts) != 3:
                raise ValueError(
                    f"lookup_condado_colors.json malformed key {rgb_key!r}; expected 'r,g,b'"
                )
            r, g, b = (int(p) for p in parts)
            idx = int(idx_val)
            if idx < 0 or idx >= len(condados):
                logger.warning(
                    "lookup_condado_colors.json idx %d out of range (len=%d) — skipping",
                    idx, len(condados),
                )
                continue
            mask = (img[:, :, 0] == r) & (img[:, :, 1] == g) & (img[:, :, 2] == b)
            pc[mask] = idx
            # Build sidecar: condado id -> #rrggbb (for frontend fills)
            sidecar[condados[idx][0]] = f"#{r:02x}{g:02x}{b:02x}"

        (generated_dir / "condado_colors.json").write_text(json.dumps(sidecar))
        return build_territories_geojson(project_id, pc, condados, cfg)
    ```

    Add at the top of `territories_geojson.py` (if not already present):
    ```python
    import logging
    logger = logging.getLogger(__name__)
    ```

    Apply the analogous rewrite to `backend/medieval_forge/services/baronies_geojson.py` `emit_baronies_from_disk`:

    ```python
    def emit_baronies_from_disk(project_id: str, generated_dir: Path, cfg: _ProjCfg) -> Path:
        from PIL import Image
        meta = json.loads((generated_dir / "territory_metadata.json").read_text())
        baronies = meta.get("baronies", [])
        condados = [
            [c["id"], c["name"], c["lon"], c["lat"], c.get("duchy", ""), c.get("baronies", [])]
            for c in meta["condados"]
        ]
        colors_raw = json.loads((generated_dir / "lookup_barony_colors.json").read_text())

        img = np.array(Image.open(generated_dir / "lookup_barony.png").convert("RGB"))
        H, W, _ = img.shape
        pb = np.full((H, W), -1, dtype=np.int32)

        sidecar: dict[str, str] = {}
        barony_colors_hex: dict[str, str] = {}
        for rgb_key, idx_val in colors_raw.items():
            parts = rgb_key.split(",")
            if len(parts) != 3:
                raise ValueError(
                    f"lookup_barony_colors.json malformed key {rgb_key!r}; expected 'r,g,b'"
                )
            r, g, blue = (int(p) for p in parts)
            idx = int(idx_val)
            if idx < 0 or idx >= len(baronies):
                logger.warning(
                    "lookup_barony_colors.json idx %d out of range (len=%d) — skipping",
                    idx, len(baronies),
                )
                continue
            mask = (img[:, :, 0] == r) & (img[:, :, 1] == g) & (img[:, :, 2] == blue)
            pb[mask] = idx
            hex_str = f"#{r:02x}{g:02x}{blue:02x}"
            sidecar[baronies[idx]["name"]] = hex_str
            barony_colors_hex[baronies[idx]["name"]] = hex_str

        (generated_dir / "barony_colors.json").write_text(json.dumps(sidecar))
        # Pass the hex map to build_baronies_geojson (it expects name -> "#hex")
        return build_baronies_geojson(project_id, pb, baronies, condados, cfg, barony_colors_hex)
    ```

    Also add `import logging; logger = logging.getLogger(__name__)` to `baronies_geojson.py` if absent.

    Also add five new unit tests (three in `test_territories_geojson.py`, two in `test_baronies_geojson.py`) that stub the disk layout in tmp_path and exercise the `emit_*_from_disk` path directly. Tests must monkeypatch `paths.PROJECTS_ROOT`, create `generated/` with `lookup_condado.png`, `lookup_condado_colors.json`, `territory_metadata.json`, then call `emit_territories_from_disk` and assert: (a) territories.geojson has expected feature ids, (b) condado_colors.json exists and has correct hex values (including zero-padding: `#0a141e` for (10,20,30)), (c) ValueError raised on malformed key, (d) out-of-range idx silently skipped.

    Avoid: DO NOT touch `build_territories_geojson` or `build_baronies_geojson` signatures — existing 9 unit tests must keep passing. DO NOT modify `lib/map_generator.py`.
  </action>

  <verify>
    <automated>cd backend && python -m pytest tests/test_territories_geojson.py tests/test_baronies_geojson.py -v</automated>
  </verify>

  <acceptance_criteria>
    - `grep -n "hexstr\[1:3\]" backend/medieval_forge/services/territories_geojson.py backend/medieval_forge/services/baronies_geojson.py` returns ZERO matches (hex parsing defect gone).
    - `grep -n 'rgb_key.split(",")' backend/medieval_forge/services/territories_geojson.py backend/medieval_forge/services/baronies_geojson.py` returns at least one match per file (real format parsing present).
    - `grep -n 'condado_colors.json' backend/medieval_forge/services/territories_geojson.py` returns at least one write site.
    - `grep -n 'barony_colors.json' backend/medieval_forge/services/baronies_geojson.py` returns at least one write site.
    - `cd backend && python -m pytest tests/test_territories_geojson.py tests/test_baronies_geojson.py -v` shows >= 14 tests pass (9 old + >=5 new), 0 failures.
    - `git diff backend/medieval_forge/lib/map_generator.py` is empty (D-04 preserved).
  </acceptance_criteria>

  <done>
    Adapter rewrite complete. Both service files parse the real `{"r,g,b": idx}` format; both write sidecar `*_colors.json` files with `{id: "#hex"}` for frontend fills. Unit test suite ≥14 tests all green.
  </done>
</task>


<task type="auto" tdd="true">
  <name>Task 2: Fail loudly — remove silent try/except and add [BLOCKING] real-pipeline integration test</name>

  <read_first>
    - backend/medieval_forge/services/generator.py (lines 63-68 whitelist; lines 296-357 _run_pipeline_sync; lines 341-348 the silent try/except)
    - backend/medieval_forge/api/generate.py (background-task handler — status=error_generating path; consult lines around :30-51)
    - backend/tests/test_generator_e2e.py (NEW FILE — will be created here)
    - backend/tests/test_territories_geojson.py (pattern for monkeypatching PROJECTS_ROOT)
    - backend/medieval_forge/services/paths.py (PROJECTS_ROOT + project_dir + ensure_project_dirs)
  </read_first>

  <behavior>
    - Test A (G-02 propagation): given a project with corrupted lookup_condado_colors.json (e.g. malformed key), run_generation raises the underlying exception (NOT swallowed). Assert with pytest.raises(ValueError) (or whatever the emitter raises).
    - Test B [BLOCKING] (G-03 integration): given a synthetic-but-complete generated_dir fixture (lookup_condado.png painted with 2 colors, matching lookup_condado_colors.json in real format, matching territory_metadata.json; analogous for baronies), call `_run_pipeline_sync` via a fake map_generator.generate_maps that only materializes those fixture files (monkeypatch map_generator.generate_maps to a stub that copies fixture files into generated_dir). After the call:
        * assert (generated_dir / "territories.geojson").exists() is True
        * assert (generated_dir / "baronies.geojson").exists() is True
        * both parse to FeatureCollections with non-empty features[]
        * (generated_dir / "condado_colors.json").exists() is True
        * (generated_dir / "barony_colors.json").exists() is True
        * test MUST FAIL LOUDLY if any file is missing (use plain `assert path.exists(), f"missing {path}"`)
  </behavior>

  <action>
    **Edit 1 (G-02 fix) — `backend/medieval_forge/services/generator.py`:**
    Remove the silent try/except at lines 341-348 and replace with a direct call. Final block replacing lines 341-348:

    ```python
            # CANVAS-01 + D-02: emission must succeed or the whole generation fails.
            # Previously this was wrapped in try/except that swallowed the format-mismatch
            # crash from G-01 for days. Any exception here propagates to run_generation,
            # which lets api/generate.py's background task set status='error_generating'
            # with last_error. (G-02: no silent swallow.)
            emit_territories_from_disk(project_id, generated_dir, cfg_shim)
            emit_baronies_from_disk(project_id, generated_dir, cfg_shim)
    ```

    Also: keep the imports of `emit_territories_from_disk`, `emit_baronies_from_disk`, `_ProjCfg`, and `math as _math` where they currently are.

    **Edit 2 (whitelist) — same file, line 63-68:** Append the two new sidecar filenames so FastAPI's `/preview/{filename}` route serves them:
    ```python
    GENERATED_FILE_WHITELIST: frozenset[str] = frozenset(
        list(_GENERATOR_OUTPUTS)
        + list(_PREVIEW_ALIASES.keys())
        + list(_AUXILIARY_OUTPUTS)
        + ["territories.geojson", "baronies.geojson",
           "condado_colors.json", "barony_colors.json"]
    )
    ```

    **Edit 3 (G-03 test) — CREATE `backend/tests/test_generator_e2e.py`:**

    ```python
    """[BLOCKING] Real-pipeline integration test closing verification gap G-03.

    Runs the real emit_*_from_disk codepath end-to-end against an on-disk fixture
    that matches map_generator.py SECTION 10's output format exactly. Fails loudly
    if either territories.geojson or baronies.geojson is missing or un-parseable.
    """
    import json
    import uuid
    from pathlib import Path

    import numpy as np
    import pytest
    from PIL import Image


    def _paint_rgb(path: Path, rgb_by_region: dict[tuple[int, int, int], tuple[int, int, int, int]]) -> None:
        """Write a small RGB PNG where each (r,g,b) fills the given (x0,y0,x1,y1) rect."""
        arr = np.zeros((20, 20, 3), dtype=np.uint8)
        for (r, g, b), (x0, y0, x1, y1) in rgb_by_region.items():
            arr[y0:y1, x0:x1] = (r, g, b)
        Image.fromarray(arr, mode="RGB").save(path)


    @pytest.fixture
    def fake_generated_dir(tmp_path, monkeypatch):
        from medieval_forge.services import paths as _paths
        monkeypatch.setattr(_paths, "PROJECTS_ROOT", tmp_path / "projects")
        pid = str(uuid.uuid4())
        (_paths.PROJECTS_ROOT / pid / "raw").mkdir(parents=True)
        (_paths.PROJECTS_ROOT / pid / "raw" / "municipalities.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": [
                {"type": "Feature", "geometry": {"type": "Polygon",
                 "coordinates": [[[-10, 36], [-10, 44], [0, 44], [0, 36], [-10, 36]]]},
                 "properties": {}}
            ]})
        )
        gen = _paths.PROJECTS_ROOT / pid / "generated"
        gen.mkdir()
        # lookup_condado.png with two colors
        _paint_rgb(gen / "lookup_condado.png", {
            (10, 20, 30): (0, 0, 10, 20),
            (40, 50, 60): (10, 0, 20, 20),
        })
        # lookup_condado_colors.json in REAL format
        (gen / "lookup_condado_colors.json").write_text(
            json.dumps({"10,20,30": 0, "40,50,60": 1})
        )
        # lookup_barony.png with two colors
        _paint_rgb(gen / "lookup_barony.png", {
            (200, 10, 30): (0, 0, 10, 20),
            (15, 80, 240): (10, 0, 20, 20),
        })
        (gen / "lookup_barony_colors.json").write_text(
            json.dumps({"200,10,30": 0, "15,80,240": 1})
        )
        (gen / "territory_metadata.json").write_text(json.dumps({
            "region": "test",
            "map_size": [20, 20],
            "bounds": {"lon_min": -10.0, "lon_max": 0.0, "lat_min": 36.0, "lat_max": 44.0},
            "kingdoms": {"K1": "K1"},
            "duchies": {"D1": {"kingdom": "K1", "name": "D1"}},
            "condados": [
                {"id": "C_A", "name": "Alpha", "lon": -7.5, "lat": 42.0, "duchy": "D1",
                 "kingdom": "K1", "pixel_center": [5, 10], "pixel_count": 200, "baronies": ["B_A1"]},
                {"id": "C_B", "name": "Beta",  "lon": -2.5, "lat": 42.0, "duchy": "D1",
                 "kingdom": "K1", "pixel_center": [15, 10], "pixel_count": 200, "baronies": ["B_B1"]},
            ],
            "baronies": [
                {"name": "B_A1", "condado_idx": 0, "duchy": "D1", "pixel_count": 200},
                {"name": "B_B1", "condado_idx": 1, "duchy": "D1", "pixel_count": 200},
            ],
        }))
        return pid, gen


    def test_run_generation_emits_both_geojson_artifacts(fake_generated_dir, monkeypatch):
        """[BLOCKING] closes G-03. Runs the real emitter orchestration end-to-end."""
        pid, gen = fake_generated_dir
        from medieval_forge.services import generator as gen_mod
        from medieval_forge.services.territories_geojson import _ProjCfg

        # Stub map_generator.generate_maps: fixture files already on disk, no-op.
        def _fake_generate_maps(region_cfg, territory_module, draw_names):
            # Ensure the generator's output_dir matches our fixture dir.
            assert Path(region_cfg.output_dir) == gen
        monkeypatch.setattr(gen_mod.map_generator, "generate_maps", _fake_generate_maps)

        config = {
            "territory_data": {
                "kingdoms": {"K1": "K1"},
                "duchies": {"D1": ("K1", "D1")},
                "condados": [
                    ("C_A", "Alpha", -7.5, 42.0, "D1", [("B_A1", -7.5, 42.0)]),
                    ("C_B", "Beta", -2.5, 42.0, "D1", [("B_B1", -2.5, 42.0)]),
                ],
            },
            "lon_min": -10.0, "lon_max": 0.0, "lat_min": 36.0, "lat_max": 44.0,
            "map_w": 20, "map_h": 20, "upscale": 1,
        }

        manifest = gen_mod._run_pipeline_sync(pid, gen, config)

        # [BLOCKING] assertions — fail loudly
        tpath = gen / "territories.geojson"
        bpath = gen / "baronies.geojson"
        assert tpath.exists(), f"BLOCKING: territories.geojson missing at {tpath}"
        assert bpath.exists(), f"BLOCKING: baronies.geojson missing at {bpath}"
        assert (gen / "condado_colors.json").exists(), "BLOCKING: condado_colors.json sidecar missing"
        assert (gen / "barony_colors.json").exists(), "BLOCKING: barony_colors.json sidecar missing"

        tdata = json.loads(tpath.read_text())
        bdata = json.loads(bpath.read_text())
        assert tdata["type"] == "FeatureCollection"
        assert bdata["type"] == "FeatureCollection"
        assert len(tdata["features"]) == 2
        assert len(bdata["features"]) == 2
        assert {f["id"] for f in tdata["features"]} == {"C_A", "C_B"}
        assert {f["id"] for f in bdata["features"]} == {"B_A1", "B_B1"}

        # Manifest surfaces all emitted files via the whitelist
        assert "territories.geojson" in manifest
        assert "baronies.geojson" in manifest
        assert "condado_colors.json" in manifest
        assert "barony_colors.json" in manifest


    def test_emitter_error_propagates_to_caller(fake_generated_dir, monkeypatch):
        """G-02: malformed lookup colors must raise — no silent swallow."""
        pid, gen = fake_generated_dir
        # Corrupt the file so emit_territories_from_disk raises ValueError
        (gen / "lookup_condado_colors.json").write_text(json.dumps({"not-a-triple": 0}))

        from medieval_forge.services import generator as gen_mod

        def _fake_generate_maps(region_cfg, territory_module, draw_names):
            pass
        monkeypatch.setattr(gen_mod.map_generator, "generate_maps", _fake_generate_maps)

        config = {
            "territory_data": {
                "kingdoms": {"K1": "K1"},
                "duchies": {"D1": ("K1", "D1")},
                "condados": [("C_A", "Alpha", -7.5, 42.0, "D1", [("B_A1", -7.5, 42.0)])],
            },
            "lon_min": -10.0, "lon_max": 0.0, "lat_min": 36.0, "lat_max": 44.0,
            "map_w": 20, "map_h": 20, "upscale": 1,
        }

        with pytest.raises(ValueError, match="malformed key"):
            gen_mod._run_pipeline_sync(pid, gen, config)
    ```

    Avoid: DO NOT pre-emptively check artifact presence after the emitter calls — the raised exception is the single source of truth (fix hint per 02-VERIFICATION.md gap G-02 option A). DO NOT touch `api/generate.py` — its existing outer handler at `:30-51` already sets `status='error_generating'` on any exception from `run_generation` (confirm by reading it during task execution; adjust only if that assumption turns out to be wrong).
  </action>

  <verify>
    <automated>cd backend && python -m pytest tests/test_generator_e2e.py -v</automated>
  </verify>

  <acceptance_criteria>
    - `grep -n "except Exception" backend/medieval_forge/services/generator.py` has ZERO matches in the 330-350 line range (the swallow is gone). Run `grep -nC2 "emit_territories_from_disk" backend/medieval_forge/services/generator.py` to confirm the bare call site with no wrapping try/except.
    - `grep -n "condado_colors.json" backend/medieval_forge/services/generator.py` returns at least one match (whitelist updated).
    - `grep -n "barony_colors.json"  backend/medieval_forge/services/generator.py` returns at least one match.
    - `cd backend && python -m pytest tests/test_generator_e2e.py::test_run_generation_emits_both_geojson_artifacts -v` passes (the [BLOCKING] assertion).
    - `cd backend && python -m pytest tests/test_generator_e2e.py::test_emitter_error_propagates_to_caller -v` passes (G-02 propagation).
    - Full backend suite regression check: `cd backend && python -m pytest tests/test_territories_geojson.py tests/test_baronies_geojson.py tests/test_generator_e2e.py -v` is all green (>=16 tests).
  </acceptance_criteria>

  <done>
    generator.py no longer swallows emitter exceptions; whitelist includes the two sidecar files; a failing-loudly integration test exercises the real disk codepath and proves both geojson artifacts are emitted end-to-end.
  </done>
</task>


<task type="auto">
  <name>Task 3: Switch frontend to sidecar color files + update CanvasViewer mock</name>

  <read_first>
    - frontend/src/hooks/useCanvasArtifacts.ts (lines 142-163 — the two color-file queries)
    - frontend/src/components/canvas/__tests__/CanvasViewer.test.tsx (lines 100-115 — URL mock switch)
    - frontend/src/components/canvas/TerritoryLayer.tsx (consumer — confirm prop shape unchanged)
    - frontend/src/components/canvas/DecorationsLayer.tsx (consumer — confirm prop shape unchanged)
  </read_first>

  <action>
    **Edit 1 — `frontend/src/hooks/useCanvasArtifacts.ts`:**

    Replace the two URL strings in the `[2]` and `[3]` queryFn calls:
      - Line ~147: `/api/projects/${projectId}/preview/lookup_condado_colors.json` → `/api/projects/${projectId}/preview/condado_colors.json`
      - Line ~158: `/api/projects/${projectId}/preview/lookup_barony_colors.json`  → `/api/projects/${projectId}/preview/barony_colors.json`

    Also update the two adjacent doc comments at lines 89, 90, 143, 154 to reflect the new filename (preserve shape comment — they still resolve to `Record<string, string>` of `{id: "#hex"}` now, not the raw Unity lookup).

    **Edit 2 — `frontend/src/components/canvas/__tests__/CanvasViewer.test.tsx`:**

    Update the URL substring checks at lines ~104 and ~107:
      - `if (urlStr.includes('lookup_condado_colors'))` → `if (urlStr.includes('condado_colors'))`
      - `if (urlStr.includes('lookup_barony_colors'))`  → `if (urlStr.includes('barony_colors'))`

    NOTE: `'condado_colors'` is a proper suffix of `'lookup_condado_colors'`, so you must place the NEW check BEFORE any legacy substring check, or just rewrite both as the new names since the legacy files are no longer fetched by production code.

    Avoid: DO NOT modify the Unity-consumed `lookup_condado_colors.json` / `lookup_barony_colors.json` files anywhere (D-04: those stay in the original int-index format for Unity downstream). DO NOT touch BaronyLayer or TerritoryLayer rendering code — their props already accept `Record<string, string>` and the new sidecar shape matches.
  </action>

  <verify>
    <automated>cd frontend && npx vitest run --reporter=basic</automated>
  </verify>

  <acceptance_criteria>
    - `grep -rn "lookup_condado_colors" frontend/src frontend/e2e 2>/dev/null` returns ZERO matches (all call sites updated).
    - `grep -rn "lookup_barony_colors" frontend/src frontend/e2e 2>/dev/null` returns ZERO matches.
    - `grep -n "condado_colors.json" frontend/src/hooks/useCanvasArtifacts.ts` returns at least one match.
    - `grep -n "barony_colors.json"  frontend/src/hooks/useCanvasArtifacts.ts` returns at least one match.
    - `cd frontend && npx vitest run` passes 86/86 tests (no regressions).
    - `cd frontend && npx tsc -b` exits 0 (no type errors).
  </acceptance_criteria>

  <done>
    Frontend fetches the new sidecar color files produced by Task 1. All 86 vitest tests remain green; TypeScript build clean.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| disk → service-adapter | `lookup_*_colors.json` read by adapter. Written by our own `lib/map_generator.py` inside `~/.medieval-forge/projects/{uuid}/generated/`. No network or user-supplied content crosses here. |
| service-adapter → FastAPI static route | New sidecar files `condado_colors.json` / `barony_colors.json` served via existing whitelisted `/preview/{filename}` route. Filenames hard-coded in `GENERATED_FILE_WHITELIST`. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-04-01 | Tampering | `emit_*_from_disk` reading `lookup_*_colors.json` | accept | Source is our own `map_generator.py` output under the per-project UUID dir. No external writer. If the file is hand-edited to a malformed shape, we now raise `ValueError` (Task 1) instead of silently mis-parsing — safer failure mode. |
| T-02-04-02 | Denial of Service | adapter loops over `colors_raw` entries and paints `img[...] == (r,g,b)` masks | accept | Bounded by the number of distinct territories in a project (Iberia test set ~91 condados; realistic cap <500). Each mask is O(H·W). Input size is bounded by the generator's own `map_w*upscale × map_h*upscale` config (hundreds to low thousands of pixels per side). No untrusted-size amplification. |
| T-02-04-03 | Information Disclosure | New whitelisted files `condado_colors.json` / `barony_colors.json` | accept | Contain only `{territory_id: "#hex"}`. No PII, no credentials. Already derivable from the existing public `lookup_*_colors.json` + `territory_metadata.json` files — zero new disclosure surface. |
| T-02-04-04 | Elevation of Privilege | Path-traversal via `rgb_key` or idx values entering `pc[mask] = idx` | mitigate | `idx = int(idx_val)` followed by range check `0 <= idx < len(condados)` before array assignment. Malformed `"r,g,b"` keys raise `ValueError` before any disk write. `generated_dir` is resolved upstream via `paths.project_dir(project_id)` which already rejects non-UUID ids. |
| T-02-04-05 | Repudiation | Silent-swallow removal means errors now propagate to logs + status machine | mitigate | Fix (Task 2) directly improves auditability: `api/generate.py` records `last_error` on project status when emitter fails. Opposite of a repudiation risk — this gap-closure strengthens the audit trail. |
| T-02-04-06 | Spoofing | N/A | accept | No authentication context touched; backend runs locally only. |
</threat_model>

<verification>
Run all three verification commands after completing the tasks:

1. `cd backend && python -m pytest tests/test_territories_geojson.py tests/test_baronies_geojson.py tests/test_generator_e2e.py -v` — expect ≥16 tests green, 0 failures.
2. `cd frontend && npx vitest run` — expect 86/86 green.
3. `cd frontend && npx tsc -b` — expect exit 0.
4. Grep sweep (manual but scripted):
   - `grep -rn "lookup_condado_colors\|lookup_barony_colors" frontend/src` → 0 matches.
   - `grep -n "hexstr\[1:3\]" backend/medieval_forge/services/*.py` → 0 matches.
   - `grep -nC2 "emit_territories_from_disk" backend/medieval_forge/services/generator.py` → no surrounding try/except.
   - `git diff backend/medieval_forge/lib/map_generator.py` → empty (D-04 preserved).

Human UAT re-run required (per 02-HUMAN-UAT.md) — items 1, 2, 5, 7, 9 should move from FAILED/BLOCKED to PASSED after this plan ships.
</verification>

<success_criteria>
- All three verification gaps G-01, G-02, G-03 closed (evidence: grep sweep + pytest + integration test).
- `territories.geojson` and `baronies.geojson` emitted end-to-end when `run_generation` runs against the real pipeline — demonstrated by the [BLOCKING] integration test.
- Emitter exceptions propagate to FastAPI background task (no silent swallow) — project status is correctly downgraded to `error_generating` on failure.
- Frontend renders real condado fills (no `#666666` fallback) the next time a project is generated — enables UAT Test 1 to move from FAILED to PASSED.
- `lib/map_generator.py` is unchanged (D-04 black-box honored).
- All existing 9 backend unit tests + 86 frontend tests remain green (no regressions).
</success_criteria>

<output>
After completion, create `.planning/phases/02-read-only-canvas-viewer/02-04-SUMMARY.md` describing:
- Fix applied to G-01 (adapter rewrite + sidecar files)
- Fix applied to G-02 (silent try/except removed + error propagation verified)
- Fix applied to G-03 (integration test added with [BLOCKING] assertions)
- Any follow-up human verification still required from 02-HUMAN-UAT.md
</output>
