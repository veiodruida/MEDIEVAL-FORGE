---
phase: 01
plan: 04
type: execute
wave: 4
depends_on:
  - 01-02
files_modified:
  - backend/medieval_forge/lib/__init__.py
  - backend/medieval_forge/lib/map_generator.py
  - backend/medieval_forge/services/generator.py
  - backend/medieval_forge/api/generate.py
  - backend/medieval_forge/main.py
  - backend/tests/test_generate.py
  - frontend/src/api/client.ts
  - frontend/src/pages/ProjectDetail.tsx
autonomous: true
requirements:
  - GEN-01
  - GEN-02
  - GEN-03
  - GEN-04

must_haves:
  truths:
    - "inicio/map_generator.py is copied to backend/medieval_forge/lib/map_generator.py and is importable as `medieval_forge.lib.map_generator` (D-04 — `if __name__ == \"__main__\"` guard at line 941 confirmed)"
    - "services.generator.run_generation(project_id, config) wraps map_generator via asyncio.to_thread (D-05); injects territory data via sys.modules patching (RESEARCH Pattern 6 + Pitfall 6)"
    - "POST /api/projects/{id}/generate returns 202 with {task_id, status} immediately and runs generation as a background task (T-DOS: refuses if project.status == 'generating')"
    - "GET /api/projects/{id}/preview/{filename} returns FileResponse for files in {project_dir}/generated/; T-PATH validates project_id AND restricts filename to a whitelist (terrain.png, territories.png, borders.png, visual_*.png, lookup_*.png, mountains_mask.png, rivers_overlay.png)"
    - "Generation completes in <60s for the example Iberia config (GEN-04) — verified by performance test marked @pytest.mark.slow"
    - "Frontend Generate button is wired: triggers POST /generate; polls GET /api/projects/{id} every 2s until status flips to 'generated' or 'error_generating'; renders three preview <img> tags using GET /preview/{filename} URLs (GEN-03)"
  artifacts:
    - path: "backend/medieval_forge/lib/map_generator.py"
      provides: "verbatim copy of inicio/map_generator.py"
      contains: "if __name__ == \"__main__\""
    - path: "backend/medieval_forge/services/generator.py"
      provides: "async run_generation + sys.modules territory injector"
      exports: ["run_generation", "GENERATED_FILE_WHITELIST"]
    - path: "backend/medieval_forge/api/generate.py"
      provides: "POST /generate (BackgroundTask) + GET /preview/{filename}"
      exports: ["router"]
  key_links:
    - from: "backend/medieval_forge/services/generator.py"
      to: "backend/medieval_forge/lib/map_generator.py"
      via: "asyncio.to_thread + RegionConfig"
      pattern: "asyncio\\.to_thread.*generate_maps|map_generator\\.RegionConfig"
    - from: "backend/medieval_forge/services/generator.py"
      to: "sys.modules"
      via: "synthetic territory module injection (Pitfall 6 mitigation)"
      pattern: "sys\\.modules\\["
    - from: "backend/medieval_forge/api/generate.py"
      to: "backend/medieval_forge/services/paths.py"
      via: "is_valid_uuid + project_dir for T-PATH; filename whitelist for preview"
      pattern: "is_valid_uuid|GENERATED_FILE_WHITELIST"
    - from: "frontend/src/pages/ProjectDetail.tsx"
      to: "/api/projects/{id}/preview/territories.png"
      via: "<img src>"
      pattern: "src=.*preview/"
---

<objective>
Wrap the existing `inicio/map_generator.py` (PROVEN importable per CONTEXT D-04) into a FastAPI background-task pipeline and expose PNG previews. After this plan, a Game Designer with an ingested project can click "Generate", see a status indicator while the pipeline runs in the background, and watch the three PNG previews (terrain.png, territories.png, borders.png) appear in the browser. No file downloads needed for preview (GEN-03).

Purpose: GEN-01..04 turn raw GeoJSON into the visual outputs that motivate the entire tool. The wrapper has THREE non-trivial responsibilities: (1) inject territory data via `sys.modules` patching to satisfy `load_territory_data`'s `importlib.import_module` call (RESEARCH Pitfall 6), (2) run the synchronous pipeline in a thread pool so the FastAPI event loop stays responsive (D-05 + Pattern 6), (3) gate the `preview/{filename}` route with a whitelist so a hostile filename can't read arbitrary files (T-PATH defence in depth on top of UUID validation).

Output: Verbatim copy of map_generator.py into the package; new generator.py service with sys.modules adapter; new api/generate.py with POST /generate (BackgroundTask) + GET /preview/{filename}; main.py wires router; frontend Generate button replaces the placeholder, polling-based status indicator, three preview images.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md
@.planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md
@.planning/phases/01-data-pipeline-backend-scaffold/01-VALIDATION.md
@.planning/phases/01-data-pipeline-backend-scaffold/01-02-sqlite-schema-project-crud.md
@CLAUDE.md
@inicio/map_generator.py
@inicio/territory_data_v3.py
@inicio/mountain_river_data.json
@backend/medieval_forge/main.py
@backend/medieval_forge/services/paths.py
@backend/medieval_forge/api/projects.py
@backend/medieval_forge/api/ingest.py
@frontend/src/pages/ProjectDetail.tsx
@frontend/src/api/client.ts

<interfaces>
<!-- Contracts THIS plan defines and Plan 05 (export) consumes -->

backend/medieval_forge/services/generator.py:
```python
import asyncio
from pathlib import Path
from typing import Any

GENERATED_FILE_WHITELIST: frozenset[str] = frozenset({
    # 9 files map_generator produces (RESEARCH "Critical Integration" section):
    "visual_condado.png",
    "visual_barony.png",
    "lookup_condado.png",
    "lookup_barony.png",
    "lookup_condado_colors.json",
    "lookup_barony_colors.json",
    "territory_metadata.json",
    "mountains_mask.png",
    "rivers_overlay.png",
    # 3 alias names that the UI uses for the headline previews (GEN-02):
    "terrain.png",      # alias for mountains_mask.png (or symlink-equivalent)
    "territories.png",  # alias for visual_condado.png
    "borders.png",      # alias for lookup_condado.png (border outlines visible there)
})

async def run_generation(project_id: str, config: dict[str, Any]) -> dict[str, str]:
    """Returns manifest: {logical_name: relative_path_under_generated/}.

    config keys:
      - territory_data: dict with {kingdoms, duchies, condados} (REQUIRED for now)
      - any RegionConfig fields you want to override (optional)
    """
```

backend/medieval_forge/api/generate.py:
```python
router = APIRouter(prefix="/projects", tags=["generate"])

@router.post("/{project_id}/generate", status_code=202)
async def trigger_generate(project_id: str, background_tasks: BackgroundTasks):
    # T-PATH + T-DOS guards
    # Sets project.status = "generating", schedules run_generation in background
    return {"project_id": ..., "status": "generating"}

@router.get("/{project_id}/preview/{filename}")
async def get_preview(project_id: str, filename: str):
    # T-PATH: validate UUID; filename MUST be in GENERATED_FILE_WHITELIST
    return FileResponse(...)
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Wave 0 — test_generate.py stubs (GEN-01..04 + T-PATH preview guard)</name>
  <files>backend/tests/test_generate.py</files>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-VALIDATION.md
    - backend/tests/conftest.py
  </read_first>
  <action>
    Create `backend/tests/test_generate.py`:
    ```python
    """Tests for GEN-01..04, T-PATH preview guard, T-DOS overlap guard.

    Stubs in Wave 0 of Plan 01-04; implemented in Tasks 3, 4, 5.
    """
    import pytest


    @pytest.mark.skip(reason="Implemented by Plan 01-04 Task 3 (services.generator)")
    def test_inject_territory_module_creates_sys_modules_entry():
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-04 Task 4 (api.generate)")
    async def test_trigger_generation(client):
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-04 Task 4 (T-DOS overlap guard)")
    async def test_trigger_generation_rejects_when_already_generating(client):
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-04 Task 4")
    async def test_png_fileresponse(client, tmp_path):
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-04 Task 4 (T-PATH whitelist)")
    async def test_preview_rejects_non_whitelisted_filename(client):
        pass


    @pytest.mark.slow
    @pytest.mark.skip(reason="Implemented by Plan 01-04 Task 5 (slow integration with real map_generator)")
    async def test_png_outputs(client, tmp_path):
        pass


    @pytest.mark.slow
    @pytest.mark.skip(reason="Implemented by Plan 01-04 Task 5 (GEN-04 performance assertion)")
    async def test_generation_time(client, tmp_path):
        pass
    ```
  </action>
  <verify>
    <automated>py -m pytest backend/tests/test_generate.py -q</automated>
  </verify>
  <done>7 tests collected, all skipped, 0 errors.</done>
  <acceptance_criteria>
    - backend/tests/test_generate.py exists
    - Contains exactly 7 test functions including test_trigger_generation, test_trigger_generation_rejects_when_already_generating, test_png_fileresponse, test_preview_rejects_non_whitelisted_filename, test_inject_territory_module_creates_sys_modules_entry, test_png_outputs, test_generation_time
    - test_png_outputs and test_generation_time decorated with @pytest.mark.slow
    - py -m pytest backend/tests/test_generate.py -q exits 0 with "7 skipped"
  </acceptance_criteria>
</task>

<task type="auto">
  <name>Task 2: Copy inicio/map_generator.py → backend/medieval_forge/lib/map_generator.py (verbatim, D-04)</name>
  <files>
    backend/medieval_forge/lib/__init__.py,
    backend/medieval_forge/lib/map_generator.py
  </files>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md (D-04 — line 941 __main__ guard confirmed)
    - inicio/map_generator.py (full file — confirms structure before copy)
  </read_first>
  <action>
    1. Create `backend/medieval_forge/lib/__init__.py` (empty: `"""Vendored geometry/raster generation library."""`).

    2. Copy `inicio/map_generator.py` byte-for-byte to `backend/medieval_forge/lib/map_generator.py`:
       ```bash
       cp inicio/map_generator.py backend/medieval_forge/lib/map_generator.py
       ```
       (On Windows shell: `cp` works in git bash; alternative: use `Read` then `Write` with the tools, or `Copy-Item` in PowerShell.)

       The file MUST be a verbatim copy — DO NOT modify any of its code, comments, imports, or whitespace. The whole point of D-04 is to leave map_generator.py as a black-box library and wrap it from outside.

    3. Verify importability:
       ```bash
       py -c "from medieval_forge.lib import map_generator; assert hasattr(map_generator, 'RegionConfig'); assert hasattr(map_generator, 'generate_maps'); print('importable, RegionConfig=', map_generator.RegionConfig); print('main guard line:', open('backend/medieval_forge/lib/map_generator.py').readlines()[940].strip()[:80])"
       ```

       Expected output: shows `<class 'medieval_forge.lib.map_generator.RegionConfig'>` and the line 941 (index 940) is the `if __name__ == "__main__":` line. This proves D-04's prerequisite (importable WITHOUT executing the script body).

    4. Confirm the file size matches the source (sanity check no truncation):
       ```bash
       wc -c inicio/map_generator.py backend/medieval_forge/lib/map_generator.py
       ```
       Both numbers MUST be identical.
  </action>
  <verify>
    <automated>py -c "from medieval_forge.lib import map_generator; assert hasattr(map_generator, 'RegionConfig'); assert hasattr(map_generator, 'generate_maps'); print('OK')"</automated>
  </verify>
  <done>map_generator.py imports cleanly; RegionConfig and generate_maps are accessible; file size matches source byte-for-byte.</done>
  <acceptance_criteria>
    - backend/medieval_forge/lib/__init__.py exists
    - backend/medieval_forge/lib/map_generator.py exists
    - File size of backend/medieval_forge/lib/map_generator.py equals file size of inicio/map_generator.py
    - py -c "from medieval_forge.lib import map_generator; assert hasattr(map_generator, 'generate_maps')" exits 0
    - backend/medieval_forge/lib/map_generator.py contains "if __name__ == \"__main__\":"
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 3: services/generator.py — sys.modules territory injector + run_generation wrapper + injector test</name>
  <files>
    backend/medieval_forge/services/generator.py,
    backend/tests/test_generate.py
  </files>
  <behavior>
    - `_inject_territory_module(name, data)` creates a `types.ModuleType(name)`, sets `KINGDOMS`, `DUCHIES`, `CONDADOS` attributes from the data dict, registers it in `sys.modules[name]`, returns the module
    - `_cleanup_territory_module(name)` removes the entry from `sys.modules` (idempotent)
    - `run_generation(project_id, config)` validates project_id via paths, ensures `generated/` dir exists, builds RegionConfig from the config dict (only fields present in `RegionConfig.__dataclass_fields__`), uses a unique synthetic module name `f"_mf_territory_{project_id.replace('-', '_')}"` to avoid collisions, calls `asyncio.to_thread(map_generator.generate_maps, region_cfg, territory_module=mod_name, draw_names=False)`, then cleans up sys.modules in a finally block, returns a manifest dict mapping logical names to relative paths
    - The 3 alias names ("terrain.png", "territories.png", "borders.png") are produced by symlinking (or copying on Windows) the appropriate underlying files post-generation, so the frontend can request stable filenames regardless of what map_generator produces internally
    - test_inject_territory_module_creates_sys_modules_entry verifies the injector contract
  </behavior>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md (Pattern 6 — wrapper with asyncio.to_thread; Code Examples — Territory Module Adapter sys.path injection; Pitfall 6 — territory_module import failure; Critical Integration — public API)
    - .planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md (D-04, D-05)
    - inicio/map_generator.py (specifically: RegionConfig dataclass fields; load_territory_data function; generate_maps signature)
    - inicio/territory_data_v3.py (KINGDOMS/DUCHIES/CONDADOS structure)
    - backend/medieval_forge/services/paths.py
  </read_first>
  <action>
    1. CREATE `backend/medieval_forge/services/generator.py`:
       ```python
       """GEN-01..04: wrapper around medieval_forge.lib.map_generator.

       D-04: map_generator is treated as a vendored black box. We do NOT modify it.
       D-05: synchronous pipeline runs in asyncio.to_thread.
       Pitfall 6 mitigation: territory data is injected via sys.modules patching
                              before generate_maps invokes load_territory_data.
       """
       from __future__ import annotations

       import asyncio
       import logging
       import shutil
       import sys
       import types
       from pathlib import Path
       from typing import Any

       from ..lib import map_generator
       from .paths import ensure_project_dirs

       logger = logging.getLogger(__name__)

       # Files map_generator produces (per RESEARCH Critical Integration section).
       _GENERATOR_OUTPUTS: tuple[str, ...] = (
           "visual_condado.png",
           "visual_barony.png",
           "lookup_condado.png",
           "lookup_barony.png",
           "lookup_condado_colors.json",
           "lookup_barony_colors.json",
           "territory_metadata.json",
           "mountains_mask.png",
           "rivers_overlay.png",
       )

       # Aliases the UI uses for headline previews (GEN-02). Each alias is a copy
       # of one of the generator outputs, written post-generation under a stable name.
       _PREVIEW_ALIASES: dict[str, str] = {
           "terrain.png": "mountains_mask.png",
           "territories.png": "visual_condado.png",
           "borders.png": "lookup_condado.png",
       }

       GENERATED_FILE_WHITELIST: frozenset[str] = frozenset(
           list(_GENERATOR_OUTPUTS) + list(_PREVIEW_ALIASES.keys())
       )


       def _inject_territory_module(name: str, data: dict[str, Any]) -> types.ModuleType:
           """Create a synthetic module with KINGDOMS/DUCHIES/CONDADOS and register in sys.modules."""
           mod = types.ModuleType(name)
           mod.KINGDOMS = data.get("kingdoms", {})
           mod.DUCHIES = data.get("duchies", {})
           mod.CONDADOS = data.get("condados", {})
           sys.modules[name] = mod
           return mod


       def _cleanup_territory_module(name: str) -> None:
           sys.modules.pop(name, None)


       def _build_region_config(generated_dir: Path, config: dict[str, Any]) -> Any:
           """Construct a RegionConfig from caller-supplied overrides, defaulting output_dir."""
           valid_fields = set(map_generator.RegionConfig.__dataclass_fields__.keys())
           kwargs: dict[str, Any] = {"output_dir": str(generated_dir)}
           for k, v in config.items():
               if k in valid_fields and k != "output_dir":
                   kwargs[k] = v
           return map_generator.RegionConfig(**kwargs)


       def _materialise_aliases(generated_dir: Path) -> None:
           """Copy underlying generator outputs to their alias names (terrain.png etc)."""
           for alias, source_name in _PREVIEW_ALIASES.items():
               source = generated_dir / source_name
               target = generated_dir / alias
               if source.exists():
                   shutil.copyfile(source, target)


       def _run_pipeline_sync(
           project_id: str,
           generated_dir: Path,
           config: dict[str, Any],
       ) -> dict[str, str]:
           territory_data = config.get("territory_data")
           if not isinstance(territory_data, dict):
               raise ValueError(
                   "config['territory_data'] must be a dict with keys {kingdoms, duchies, condados}"
               )
           module_name = f"_mf_territory_{project_id.replace('-', '_')}"
           _inject_territory_module(module_name, territory_data)
           try:
               region_cfg = _build_region_config(generated_dir, config)
               map_generator.generate_maps(
                   region_cfg,
                   territory_module=module_name,
                   draw_names=False,
               )
               _materialise_aliases(generated_dir)
           finally:
               _cleanup_territory_module(module_name)

           manifest: dict[str, str] = {}
           for fname in GENERATED_FILE_WHITELIST:
               p = generated_dir / fname
               if p.exists():
                   manifest[fname] = f"generated/{fname}"
           return manifest


       async def run_generation(project_id: str, config: dict[str, Any]) -> dict[str, str]:
           """Async entry point. Schedules the synchronous pipeline in a thread.

           Returns a manifest of {filename: relative_path}. Caller is responsible for
           updating project.status (the api layer does this).
           """
           dirs = ensure_project_dirs(project_id)
           generated_dir = dirs["generated"]
           logger.info("starting generation for %s into %s", project_id, generated_dir)
           manifest = await asyncio.to_thread(
               _run_pipeline_sync, project_id, generated_dir, config
           )
           logger.info("generation done for %s: %d files", project_id, len(manifest))
           return manifest
       ```

    2. REPLACE the `test_inject_territory_module_creates_sys_modules_entry` skip-stub in `backend/tests/test_generate.py` with a real test (keep other skip-stubs):
       ```python
       def test_inject_territory_module_creates_sys_modules_entry():
           import importlib
           import sys

           from medieval_forge.services import generator

           name = "_mf_territory_test_unit"
           data = {
               "kingdoms": {"K1": {"name": "Kingdom One"}},
               "duchies": {"D1": {"name": "Duchy"}},
               "condados": {"C1": {"name": "County"}},
           }
           try:
               mod = generator._inject_territory_module(name, data)
               # importlib.import_module finds it (this is the call inside map_generator.load_territory_data).
               loaded = importlib.import_module(name)
               assert loaded is mod
               assert loaded.KINGDOMS == data["kingdoms"]
               assert loaded.DUCHIES == data["duchies"]
               assert loaded.CONDADOS == data["condados"]
           finally:
               generator._cleanup_territory_module(name)
           assert name not in sys.modules
       ```

       Run: `py -m pytest backend/tests/test_generate.py -x -q`. Expected: 1 passed, 6 skipped (slow + endpoint tests still pending Tasks 4 and 5).
  </action>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md
    - inicio/map_generator.py
    - inicio/territory_data_v3.py
    - backend/medieval_forge/services/paths.py
  </read_first>
  <verify>
    <automated>py -m pytest backend/tests/test_generate.py -x -q</automated>
  </verify>
  <done>1 passed, 6 skipped. The injector contract is exercised by importlib.import_module — the SAME mechanism map_generator.load_territory_data uses (per Pitfall 6).</done>
  <acceptance_criteria>
    - backend/medieval_forge/services/generator.py contains "GENERATED_FILE_WHITELIST"
    - backend/medieval_forge/services/generator.py contains "_inject_territory_module"
    - backend/medieval_forge/services/generator.py contains "sys.modules[name] = mod"
    - backend/medieval_forge/services/generator.py contains "asyncio.to_thread"
    - backend/medieval_forge/services/generator.py contains "RegionConfig.__dataclass_fields__"
    - backend/medieval_forge/services/generator.py contains "generate_maps("
    - backend/medieval_forge/services/generator.py contains "_PREVIEW_ALIASES"
    - py -m pytest backend/tests/test_generate.py::test_inject_territory_module_creates_sys_modules_entry -x exits 0
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 4: api/generate.py — POST /generate (BackgroundTask) + GET /preview/{filename} (T-PATH whitelist) + main.py wires + 3 endpoint tests</name>
  <files>
    backend/medieval_forge/api/generate.py,
    backend/medieval_forge/main.py,
    backend/tests/test_generate.py
  </files>
  <behavior>
    - `POST /api/projects/{project_id}/generate`:
      - Validates project_id (T-PATH 400)
      - Loads project (404 if missing)
      - Refuses with 409 if `project.status == "generating"` (T-DOS)
      - Builds config = `{**project.generator_config, "territory_data": ...}` — for Phase 1, since territory_data ingestion isn't fully implemented yet, the route accepts an optional JSON body `{"territory_data": {...}}` that overrides; if absent AND project.generator_config doesn't contain it, returns 422 with helpful message
      - Sets `project.status = "generating"` and commits BEFORE scheduling the background task
      - Schedules `background_tasks.add_task(_run_and_update_status, project_id, config)`
      - Returns 202 + `{"project_id": id, "status": "generating"}`
    - The background task wrapper updates `project.status` to `"generated"` on success or `"error_generating"` on exception (and stores the error message in `project.generator_config["last_error"]` if config dict supports it)
    - `GET /api/projects/{project_id}/preview/{filename}`:
      - Validates project_id (T-PATH 400)
      - Validates filename ∈ GENERATED_FILE_WHITELIST (T-PATH defence in depth — 400 on rejection, NOT 404, to be explicit about rejection vs missing)
      - Resolves project_dir(project_id) / "generated" / filename; 404 if file doesn't exist
      - Returns FileResponse with appropriate media_type (image/png for .png, application/json for .json)
    - 3 of the 7 tests in test_generate.py become real (non-slow): test_trigger_generation, test_trigger_generation_rejects_when_already_generating, test_png_fileresponse, test_preview_rejects_non_whitelisted_filename. Wait — that's 4 not 3. Let me recount: test_trigger_generation, test_trigger_generation_rejects_when_already_generating, test_png_fileresponse, test_preview_rejects_non_whitelisted_filename = 4 tests. Plus the injector test from Task 3 = 5 implemented, 2 still skipped (the slow ones). All 4 stub the actual generator.run_generation call so they don't run map_generator for real (that's Task 5's slow tests).
  </behavior>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md (Anti-Pattern: BackgroundTask for long-running generation; Pattern 5/8 — main.py mount order; Security Domain — T-PATH, T-DOS)
    - backend/medieval_forge/main.py
    - backend/medieval_forge/api/projects.py (router pattern reference)
    - backend/medieval_forge/services/generator.py (created in Task 3)
    - backend/medieval_forge/services/paths.py
    - backend/tests/test_generate.py
  </read_first>
  <action>
    1. CREATE `backend/medieval_forge/api/generate.py`:
       ```python
       """GEN-01..03: trigger generation (BackgroundTask) + serve PNG previews.

       T-PATH: project_id validated; preview filename whitelisted.
       T-DOS:  reject if project already generating.
       """
       from __future__ import annotations

       import logging
       from pathlib import Path

       from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, status
       from fastapi.responses import FileResponse
       from sqlalchemy.ext.asyncio import AsyncSession

       from ..database import AsyncSessionLocal, get_db
       from ..models import Project
       from ..services.generator import GENERATED_FILE_WHITELIST, run_generation
       from ..services.paths import is_valid_uuid, project_dir

       logger = logging.getLogger(__name__)
       router = APIRouter(prefix="/projects", tags=["generate"])


       _MEDIA_TYPES = {".png": "image/png", ".json": "application/json"}


       async def _run_and_update_status(project_id: str, config: dict) -> None:
           """Background task body: runs generation; updates project.status atomically."""
           try:
               manifest = await run_generation(project_id, config)
               new_status = "generated"
               last_error: str | None = None
               logger.info("generation succeeded for %s: %d files", project_id, len(manifest))
           except Exception as exc:  # noqa: BLE001 — top of background task
               logger.exception("generation failed for %s", project_id)
               new_status = "error_generating"
               last_error = str(exc)

           # Open a fresh session — we are no longer inside the request scope.
           async with AsyncSessionLocal() as session:
               proj = await session.get(Project, project_id)
               if proj is not None:
                   proj.status = new_status
                   if last_error is not None:
                       cfg = dict(proj.generator_config or {})
                       cfg["last_error"] = last_error
                       proj.generator_config = cfg
                   await session.commit()


       @router.post("/{project_id}/generate", status_code=status.HTTP_202_ACCEPTED)
       async def trigger_generate(
           project_id: str,
           background_tasks: BackgroundTasks,
           body: dict | None = Body(default=None),
           db: AsyncSession = Depends(get_db),
       ) -> dict:
           if not is_valid_uuid(project_id):
               raise HTTPException(status_code=400, detail="project_id must be a valid UUID")
           project = await db.get(Project, project_id)
           if project is None:
               raise HTTPException(status_code=404, detail="project not found")
           if project.status == "generating":
               raise HTTPException(
                   status_code=409,
                   detail="project is already generating; wait for that to finish",
               )

           # Compose config: project.generator_config overlaid with the request body.
           merged: dict = dict(project.generator_config or {})
           if body:
               merged.update(body)
           if "territory_data" not in merged:
               raise HTTPException(
                   status_code=422,
                   detail=(
                       "territory_data is required (provide in request body as "
                       "{\"territory_data\": {\"kingdoms\":..., \"duchies\":..., \"condados\":...}} "
                       "or persist into project.generator_config first)"
                   ),
               )

           project.status = "generating"
           await db.commit()

           background_tasks.add_task(_run_and_update_status, project_id, merged)
           return {"project_id": project_id, "status": "generating"}


       @router.get("/{project_id}/preview/{filename}")
       async def get_preview(project_id: str, filename: str) -> FileResponse:
           if not is_valid_uuid(project_id):
               raise HTTPException(status_code=400, detail="project_id must be a valid UUID")
           if filename not in GENERATED_FILE_WHITELIST:
               raise HTTPException(
                   status_code=400,
                   detail=f"filename not in whitelist; allowed: {sorted(GENERATED_FILE_WHITELIST)}",
               )
           generated_dir: Path = project_dir(project_id) / "generated"
           target = generated_dir / filename
           if not target.exists():
               raise HTTPException(status_code=404, detail=f"preview {filename!r} not generated yet")
           media_type = _MEDIA_TYPES.get(target.suffix, "application/octet-stream")
           return FileResponse(target, media_type=media_type)
       ```

    2. EDIT `backend/medieval_forge/main.py`. Add the generate router import and registration AFTER the ingest router and BEFORE the SPA catch-all:
       ```python
       from .api.generate import router as generate_router

       app.include_router(generate_router, prefix="/api")
       ```

    3. REPLACE 4 of the skip-stubs in `backend/tests/test_generate.py` with real implementations. Keep `test_png_outputs` and `test_generation_time` as `@pytest.mark.slow @pytest.mark.skip` for Task 5. Updated test file structure:

       ```python
       """Tests for GEN-01..04, T-PATH preview guard, T-DOS overlap guard."""
       from __future__ import annotations

       from pathlib import Path
       from unittest.mock import patch

       import pytest


       @pytest.fixture(autouse=True)
       def _isolated_projects_root(tmp_path, monkeypatch):
           from medieval_forge.services import paths as paths_mod
           monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")


       def test_inject_territory_module_creates_sys_modules_entry():
           import importlib
           import sys
           from medieval_forge.services import generator

           name = "_mf_territory_test_unit"
           data = {
               "kingdoms": {"K1": {"name": "Kingdom One"}},
               "duchies": {"D1": {"name": "Duchy"}},
               "condados": {"C1": {"name": "County"}},
           }
           try:
               mod = generator._inject_territory_module(name, data)
               loaded = importlib.import_module(name)
               assert loaded is mod
               assert loaded.KINGDOMS == data["kingdoms"]
           finally:
               generator._cleanup_territory_module(name)
           assert name not in sys.modules


       async def _create_project(client, **overrides):
           payload = {
               "name": "gen-test",
               "country_qid": "Q29",
               "period_start": 800,
               "period_end": 1000,
           }
           payload.update(overrides)
           return (await client.post("/api/projects", json=payload)).json()


       async def test_trigger_generation(client):
           """POST /generate returns 202 and flips status to 'generating'."""
           created = await _create_project(client)
           pid = created["id"]
           # Stub run_generation so the background task completes quickly without invoking real pipeline.
           async def fake_run(project_id, config):
               return {"territories.png": "generated/territories.png"}
           with patch("medieval_forge.api.generate.run_generation", side_effect=fake_run):
               resp = await client.post(
                   f"/api/projects/{pid}/generate",
                   json={"territory_data": {"kingdoms": {}, "duchies": {}, "condados": {}}},
               )
               assert resp.status_code == 202, resp.text
               assert resp.json() == {"project_id": pid, "status": "generating"}


       async def test_trigger_generation_rejects_when_already_generating(client):
           """T-DOS: 409 if project.status == 'generating'."""
           created = await _create_project(client)
           pid = created["id"]
           # Manually flip status to 'generating'.
           await client.patch(f"/api/projects/{pid}", json={"status": "generating"})
           resp = await client.post(
               f"/api/projects/{pid}/generate",
               json={"territory_data": {"kingdoms": {}, "duchies": {}, "condados": {}}},
           )
           assert resp.status_code == 409
           assert "generating" in resp.json()["detail"].lower()


       async def test_png_fileresponse(client, tmp_path):
           """GEN-03: GET /preview/{filename} returns the file with image/png content-type."""
           from medieval_forge.services.paths import PROJECTS_ROOT, ensure_project_dirs

           created = await _create_project(client)
           pid = created["id"]
           dirs = ensure_project_dirs(pid)
           # Drop a 1x1 PNG byte sequence (valid PNG signature) into generated/.
           png_bytes = (
               b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
               b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4"
               b"\x89\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
               b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
           )
           (dirs["generated"] / "territories.png").write_bytes(png_bytes)
           resp = await client.get(f"/api/projects/{pid}/preview/territories.png")
           assert resp.status_code == 200, resp.text
           assert resp.headers["content-type"] == "image/png"
           assert resp.content == png_bytes


       async def test_preview_rejects_non_whitelisted_filename(client):
           """T-PATH: filename ∉ whitelist → 400 (not 404)."""
           created = await _create_project(client)
           pid = created["id"]
           for bad in ["../../etc/passwd", "secrets.txt", "../../../../../../tmp/x", "wat.png"]:
               resp = await client.get(f"/api/projects/{pid}/preview/{bad}")
               assert resp.status_code in (400, 404), f"{bad}: {resp.status_code}"
               # Most should be 400 from whitelist check; path traversal strings may
               # be normalized by the URL router into 404. Either way, the file is
               # never read.
           # And: invalid UUID returns 400.
           resp = await client.get("/api/projects/not-a-uuid/preview/territories.png")
           assert resp.status_code == 400


       @pytest.mark.slow
       @pytest.mark.skip(reason="Implemented by Plan 01-04 Task 5 (slow integration with real map_generator)")
       async def test_png_outputs(client, tmp_path):
           pass


       @pytest.mark.slow
       @pytest.mark.skip(reason="Implemented by Plan 01-04 Task 5 (GEN-04 performance assertion)")
       async def test_generation_time(client, tmp_path):
           pass
       ```

       Run: `py -m pytest backend/tests/test_generate.py -x -q`. Expected: 5 passed, 2 skipped.
  </action>
  <read_first>
    - backend/medieval_forge/main.py
    - backend/medieval_forge/api/projects.py
    - backend/medieval_forge/services/generator.py
    - backend/medieval_forge/services/paths.py
    - backend/tests/test_generate.py
  </read_first>
  <verify>
    <automated>py -m pytest backend/tests/test_generate.py -x -q</automated>
  </verify>
  <done>5 passed, 2 skipped (slow); main.py registers generate_router before SPA catch-all.</done>
  <acceptance_criteria>
    - backend/medieval_forge/api/generate.py contains "router = APIRouter(prefix=\"/projects\""
    - backend/medieval_forge/api/generate.py contains "background_tasks.add_task(_run_and_update_status"
    - backend/medieval_forge/api/generate.py contains "is_valid_uuid(project_id)"
    - backend/medieval_forge/api/generate.py contains "filename not in GENERATED_FILE_WHITELIST"
    - backend/medieval_forge/api/generate.py contains "project.status == \"generating\"" (T-DOS)
    - backend/medieval_forge/api/generate.py contains "media_type=media_type"
    - backend/medieval_forge/api/generate.py contains "FileResponse"
    - backend/medieval_forge/main.py contains "from .api.generate import router as generate_router"
    - backend/medieval_forge/main.py contains "app.include_router(generate_router, prefix=\"/api\")"
    - py -m pytest backend/tests/test_generate.py -x -q exits 0 with "5 passed" and "2 skipped"
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 5: Slow integration tests — real map_generator end-to-end + GEN-04 <60s assertion</name>
  <files>backend/tests/test_generate.py</files>
  <behavior>
    - `test_png_outputs` (slow): runs `run_generation` against a SMALL synthetic territory_data (1 kingdom, 1 duchy, 2 condados — minimal but non-trivial); asserts that the 9 generator outputs + 3 alias files exist in the project's `generated/` dir; asserts at least `territories.png` is non-empty
    - `test_generation_time` (slow): same setup; asserts the full call completes in less than 60.0 seconds (GEN-04). Use `time.monotonic()` before/after; fail if elapsed > 60.0.
    - Both tests are guarded by `@pytest.mark.slow` so the default `--ignore` flag in VALIDATION.md skips them on per-task runs; they MUST be run on the per-wave merge / phase gate
    - If the synthetic territory_data is too minimal for map_generator to produce all 9 files (some files are conditional on data presence — e.g. mountains_mask.png depends on mountain data), the test asserts on the SUBSET that should always exist: at minimum `visual_condado.png`, `lookup_condado.png`, `lookup_condado_colors.json`, `territory_metadata.json` plus the alias `territories.png`. The test documents which files are conditional.
  </behavior>
  <read_first>
    - inicio/territory_data_v3.py (study the KINGDOMS/DUCHIES/CONDADOS structure to design a minimal test fixture)
    - inicio/map_generator.py (search for `mountain` and `river` to understand which outputs are conditional)
    - backend/medieval_forge/services/generator.py
    - backend/tests/test_generate.py
  </read_first>
  <action>
    Replace the two `@pytest.mark.slow @pytest.mark.skip` stubs at the bottom of `backend/tests/test_generate.py` with real implementations. The other tests in the file remain unchanged.

    Add this block at the end (replacing the two skipped slow stubs):

    ```python
    # ---------- SLOW: real map_generator integration ----------

    def _minimal_territory_data() -> dict:
        """Synthetic minimal territory hierarchy.

        Caveat: map_generator was designed for the Iberia v3 dataset. The exact
        schema (whether each condado needs `capital_lat`, `capital_lon`, etc.)
        is determined by reading inicio/territory_data_v3.py during plan execution.
        """
        return {
            "kingdoms": {
                "K_TEST": {"name": "Test Kingdom", "color": [200, 100, 100]},
            },
            "duchies": {
                "D_TEST": {"name": "Test Duchy", "kingdom": "K_TEST", "color": [180, 90, 90]},
            },
            "condados": {
                "C_NORTH": {
                    "name": "North County",
                    "duchy": "D_TEST",
                    "kingdom": "K_TEST",
                    "capital_lat": 41.0,
                    "capital_lon": -3.0,
                    "color": [160, 80, 80],
                },
                "C_SOUTH": {
                    "name": "South County",
                    "duchy": "D_TEST",
                    "kingdom": "K_TEST",
                    "capital_lat": 39.0,
                    "capital_lon": -3.0,
                    "color": [140, 70, 70],
                },
            },
        }


    @pytest.mark.slow
    async def test_png_outputs(client, tmp_path):
        """GEN-02: real generator produces the headline PNG outputs."""
        from medieval_forge.services import paths as paths_mod
        from medieval_forge.services.generator import run_generation

        # Reuse the autouse _isolated_projects_root for fake_root.
        fake_root = paths_mod.PROJECTS_ROOT
        created = await _create_project(client)
        pid = created["id"]

        config = {"territory_data": _minimal_territory_data()}
        manifest = await run_generation(pid, config)

        gen_dir = fake_root / pid / "generated"
        # Files that must always exist (independent of optional mountain/river data).
        for required in [
            "visual_condado.png",
            "lookup_condado.png",
            "lookup_condado_colors.json",
            "territory_metadata.json",
            "territories.png",  # alias
        ]:
            p = gen_dir / required
            assert p.exists(), f"missing required output: {required}"
            if required.endswith(".png"):
                assert p.stat().st_size > 100, f"{required} suspiciously small"
        # Manifest reports at least the required files.
        assert "territories.png" in manifest


    @pytest.mark.slow
    async def test_generation_time(client, tmp_path):
        """GEN-04: generation completes in <60s for the minimal example."""
        import time
        from medieval_forge.services.generator import run_generation

        created = await _create_project(client)
        pid = created["id"]
        config = {"territory_data": _minimal_territory_data()}

        t0 = time.monotonic()
        await run_generation(pid, config)
        elapsed = time.monotonic() - t0

        assert elapsed < 60.0, f"generation took {elapsed:.1f}s, exceeds GEN-04 budget"
    ```

    Important caveat for the executor: the `_minimal_territory_data` shape MUST match what `map_generator.load_territory_data` expects. Before running the slow tests, READ `inicio/territory_data_v3.py` to confirm the field names (capital_lat/capital_lon, color tuple length, etc.) AND read `inicio/map_generator.py`'s `load_territory_data` function to see what attributes it accesses. Adjust the fixture if needed. If the minimal fixture causes map_generator to crash (e.g. due to a missing required field), enrich the fixture iteratively — the goal is to find the SMALLEST possible valid input that exercises the full pipeline.

    Run BOTH commands:
    ```bash
    # Quick run still passes (slow tests skipped by default in validation strategy):
    py -m pytest backend/tests/test_generate.py -x -q -m "not slow"
    # Slow run for the phase gate:
    py -m pytest backend/tests/test_generate.py -x -q -m slow
    ```
  </action>
  <read_first>
    - inicio/territory_data_v3.py
    - inicio/map_generator.py
    - backend/medieval_forge/services/generator.py
    - backend/tests/test_generate.py
  </read_first>
  <verify>
    <automated>py -m pytest backend/tests/test_generate.py -x -q -m slow</automated>
  </verify>
  <done>Both slow tests pass; total runtime under 120s combined; assertion of <60s per generation holds.</done>
  <acceptance_criteria>
    - backend/tests/test_generate.py contains "_minimal_territory_data"
    - backend/tests/test_generate.py contains "elapsed < 60.0"
    - backend/tests/test_generate.py contains the strings "test_png_outputs" and "test_generation_time" (NOT decorated with @pytest.mark.skip)
    - py -m pytest backend/tests/test_generate.py -x -q -m slow exits 0 with "2 passed"
    - py -m pytest backend/tests/test_generate.py -x -q -m "not slow" exits 0 with "5 passed"
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 6: Frontend wires Generate button — useGenerate hook + status polling + preview <img> tags (GEN-03)</name>
  <files>
    frontend/src/api/client.ts,
    frontend/src/pages/ProjectDetail.tsx
  </files>
  <behavior>
    - New helper `useGenerate(projectId)` exposes `{trigger: (territoryData?: object) => Promise<void>, isPending: boolean, error: Error | null}`. Uses `useMutation` to POST `/api/projects/{id}/generate` with body `{territory_data: territoryData}` (or empty body if territoryData omitted, allowing project.generator_config to provide it).
    - Polling: when `useProject(id).data.status === "generating"`, the existing `useProject` query refetches every 2 seconds. Achieved via `refetchInterval` option on `useProject` based on the current cached status.
    - ProjectDetail: replaces the disabled "Generate (Plan 1.4)" button with a real one. A textarea (Radix `<TextArea>`) lets the user paste JSON for territory_data (placeholder: example minimal hierarchy). Button disabled while `project.status === "generating"`. After status flips to `"generated"`, render three `<img>` tags pointing at `/api/projects/{id}/preview/territories.png`, `/api/projects/{id}/preview/borders.png`, `/api/projects/{id}/preview/terrain.png`. If status is `"error_generating"` show the `project.generator_config.last_error` field in red.
  </behavior>
  <read_first>
    - frontend/src/api/client.ts (current; has useProject)
    - frontend/src/pages/ProjectDetail.tsx (current; has Generate placeholder button)
    - .planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md (D-09 — actions live in detail page)
  </read_first>
  <action>
    1. EDIT `frontend/src/api/client.ts`. Update the existing `useProject` to support polling AND add a new `useGenerate` hook.

       Replace the existing `useProject` function with:
       ```typescript
       export function useProject(id: string | undefined) {
         return useQuery({
           queryKey: ['projects', id],
           queryFn: () => jsonFetch<Project>(`/api/projects/${id}`),
           enabled: Boolean(id),
           // Poll every 2s while the project is in a transient processing state.
           refetchInterval: (query) => {
             const data = query.state.data as Project | undefined
             if (data && (data.status === 'generating' || data.status.startsWith('ingesting'))) {
               return 2000
             }
             return false
           },
         })
       }
       ```

       Add the useGenerate hook (anywhere in the file after useProject):
       ```typescript
       export function useGenerate(projectId: string | undefined) {
         const qc = useQueryClient()
         return useMutation({
           mutationFn: async (territoryData?: Record<string, unknown>) => {
             const body: Record<string, unknown> = {}
             if (territoryData) body.territory_data = territoryData
             return jsonFetch<{ project_id: string; status: string }>(
               `/api/projects/${projectId}/generate`,
               { method: 'POST', body: JSON.stringify(body) },
             )
           },
           onSuccess: () => {
             qc.invalidateQueries({ queryKey: ['projects', projectId] })
             qc.invalidateQueries({ queryKey: ['projects'] })
           },
         })
       }
       ```

    2. EDIT `frontend/src/pages/ProjectDetail.tsx`. Add at the top:
       ```typescript
       import { TextArea } from '@radix-ui/themes'
       import { useGenerate } from '../api/client'
       ```

       In the component body (alongside the existing useIngestStream from Plan 03):
       ```typescript
       const generate = useGenerate(id)
       const [territoryJson, setTerritoryJson] = useState<string>(`{
         "kingdoms": {"K_TEST": {"name": "Test Kingdom", "color": [200, 100, 100]}},
         "duchies": {"D_TEST": {"name": "Test Duchy", "kingdom": "K_TEST", "color": [180, 90, 90]}},
         "condados": {
           "C_NORTH": {"name": "North", "duchy": "D_TEST", "kingdom": "K_TEST", "capital_lat": 41.0, "capital_lon": -3.0, "color": [160, 80, 80]},
           "C_SOUTH": {"name": "South", "duchy": "D_TEST", "kingdom": "K_TEST", "capital_lat": 39.0, "capital_lon": -3.0, "color": [140, 70, 70]}
         }
       }`)
       ```

       Replace the existing disabled "Generate (Plan 1.4)" button (in the Pipeline actions Card) with:
       ```typescript
       <Button
         onClick={() => {
           try {
             const data = JSON.parse(territoryJson)
             generate.mutate(data)
           } catch (e) {
             alert(`territory_data JSON parse error: ${(e as Error).message}`)
           }
         }}
         disabled={project.status === 'generating' || generate.isPending}
       >
         {project.status === 'generating' ? 'Generating…' : 'Generate'}
       </Button>
       ```

       Add a TextArea below the action buttons row but above the ingest log:
       ```typescript
       <Box mb="3">
         <Text size="2" weight="medium">Territory data (JSON)</Text>
         <TextArea
           value={territoryJson}
           onChange={(e) => setTerritoryJson(e.target.value)}
           rows={10}
           style={{ fontFamily: 'monospace', fontSize: 12 }}
         />
         {generate.error && (
           <Text color="red" size="2">Generate error: {(generate.error as Error).message}</Text>
         )}
         {project.status === 'error_generating' && project.generator_config?.last_error && (
           <Text color="red" size="2">
             Last generation error: {String(project.generator_config.last_error)}
           </Text>
         )}
       </Box>
       ```

       Add a previews Card after the existing Pipeline actions Card (only renders when status === 'generated'):
       ```typescript
       {project.status === 'generated' && (
         <Card mt="4">
           <Heading size="3" mb="2">Previews</Heading>
           <Flex gap="3" wrap="wrap">
             {(['territories.png', 'borders.png', 'terrain.png'] as const).map((fname) => (
               <Box key={fname}>
                 <Text size="2" weight="medium">{fname}</Text>
                 <img
                   src={`/api/projects/${project.id}/preview/${fname}`}
                   alt={fname}
                   style={{
                     display: 'block',
                     maxWidth: 360,
                     border: '1px solid #ddd',
                     borderRadius: 4,
                     marginTop: 4,
                   }}
                   onError={(e) => {
                     (e.target as HTMLImageElement).style.opacity = '0.3'
                   }}
                 />
               </Box>
             ))}
           </Flex>
         </Card>
       )}
       ```

    3. Rebuild:
       ```bash
       cd frontend && npm run build
       ```
  </action>
  <read_first>
    - frontend/src/api/client.ts
    - frontend/src/pages/ProjectDetail.tsx
  </read_first>
  <verify>
    <automated>cd frontend && npm run build && grep -l "useGenerate" src/pages/ProjectDetail.tsx && grep -l "preview/" src/pages/ProjectDetail.tsx</automated>
  </verify>
  <done>npm run build succeeds; ProjectDetail uses useGenerate; preview img src points at /api/projects/.../preview/...; useProject polls when status is "generating".</done>
  <acceptance_criteria>
    - frontend/src/api/client.ts contains "export function useGenerate"
    - frontend/src/api/client.ts contains "refetchInterval"
    - frontend/src/api/client.ts contains "data.status === 'generating'"
    - frontend/src/api/client.ts contains "/generate"
    - frontend/src/pages/ProjectDetail.tsx contains "useGenerate"
    - frontend/src/pages/ProjectDetail.tsx contains "territories.png" AND "borders.png" AND "terrain.png"
    - frontend/src/pages/ProjectDetail.tsx contains "src={`/api/projects/${project.id}/preview/"
    - frontend/src/pages/ProjectDetail.tsx contains "Plan 1.5" (placeholder for Export)
    - frontend/src/pages/ProjectDetail.tsx still contains the Ingest from Wikidata button (Plan 03 work preserved)
    - cd frontend && npm run build exits 0
  </acceptance_criteria>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Browser → POST /api/projects/{id}/generate | path param + JSON body; project_id validated; territory_data structure not deeply validated (passed to vendored map_generator) |
| Browser → GET /api/projects/{id}/preview/{filename} | TWO untrusted path components; both must pass guards before any filesystem access |
| FastAPI → backend/medieval_forge/lib/map_generator.py | vendored synchronous library; runs in thread pool; territory data injected via sys.modules |
| FastAPI → filesystem (project generated/) | Path computed via project_dir() (T-PATH validated) + filename whitelist (defence in depth) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-PATH (preview) | Tampering | api/generate.py GET /preview/{filename} | mitigate | TWO checks: (a) `is_valid_uuid(project_id)` → 400; (b) `filename in GENERATED_FILE_WHITELIST` → 400 if not. Even if (a) were bypassed, (b) restricts disclosure to a fixed set of 12 filenames within the project's generated/ dir. |
| T-PATH (generate) | Tampering | api/generate.py POST /generate path param | mitigate | `is_valid_uuid(project_id)` → 400; project_dir() re-validates and verifies resolved path within PROJECTS_ROOT. |
| T-DOS (overlap) | Denial of Service | api/generate.py POST /generate | mitigate | 409 if `project.status == "generating"`. The status flip + DB commit happens BEFORE the BackgroundTask is scheduled, preventing race conditions with multiple in-flight requests. |
| T-DOS (queue depth) | Denial of Service | FastAPI BackgroundTasks | accept | Local single-user tool; queue is unbounded but realistically a Game Designer never queues more than one generation at a time. The 409 guard prevents accidental double-clicks. |
| T-04-01 | Tampering | sys.modules[name] injection | mitigate | The synthetic module name is `_mf_territory_{uuid}` — namespaced so it cannot collide with real importable modules. Cleanup happens in `finally` so a failed generation doesn't leave the synthetic module persisted. |
| T-04-02 | Information Disclosure | error message in `project.generator_config.last_error` | mitigate | The last_error string is `str(exc)` of the generator exception. For map_generator failures this typically includes filenames inside the project's own generated/ dir — acceptable for a local single-user tool. ASVS V7 satisfied (no stack traces in HTTP response). |
| T-04-03 | Tampering | territory_data JSON from request body fed to vendored map_generator | accept | map_generator is trusted vendored code (we own the source). It accesses dict keys; malformed input may crash it but cannot escape its own process boundary. Pydantic validation NOT added because the schema is determined by map_generator (D-04 says don't modify the lib); deep validation belongs in Phase 6 if needed. |
</threat_model>

<verification>
After all 6 tasks complete:

**Quick run** (excludes slow tests; this is the per-task feedback latency):
```bash
py -m pytest backend/tests/ -v --tb=short -m "not slow"
```
Expected: 26 passing tests (5 cli + 1 packaging + 9 projects + 7 ingest + 4 generate non-slow). Plan 05 (export) tests don't exist yet.

**Slow run** (phase gate):
```bash
py -m pytest backend/tests/ -v --tb=short -m slow
```
Expected: 3 passed (1 packaging + 2 generate-slow). Total runtime ~30-60s.

Manual end-to-end smoke (one-off, no network needed since territory_data is provided in the UI):
```bash
medieval-forge start --no-browser
# Browser: http://localhost:8765
# Create project (any country_qid since we'll provide territory_data inline)
# On detail page: paste the example territory JSON, click "Generate"
# Status indicator transitions: "created" → "generating" → "generated" (polled every 2s)
# Three preview images appear (territories.png, borders.png, terrain.png)
medieval-forge stop
```
</verification>

<success_criteria>
- `py -m pytest backend/tests/test_generate.py -x -q -m "not slow"` passes 5/5.
- `py -m pytest backend/tests/test_generate.py -x -q -m slow` passes 2/2 with elapsed < 60s per generation (GEN-04).
- `py -m pytest backend/tests/ -x -q -m "not slow"` passes cumulative 26/26.
- Manual smoke: clicking Generate on a project flips status to "generating", background task runs, status becomes "generated", three PNG previews render in the browser without downloads (GEN-03).
- map_generator remains UNMODIFIED (verbatim copy preserved); all integration is via the wrapper layer.
- ROADMAP success criterion #4 (trigger map generation + view three PNG previews in browser) is now exercisable end-to-end.
</success_criteria>

<output>
After completion, create `.planning/phases/01-data-pipeline-backend-scaffold/01-04-SUMMARY.md` per the standard summary template. Note: (a) the actual minimal territory_data fixture used (and any field-name corrections discovered while reading territory_data_v3.py), (b) measured generation time for the minimal fixture (helps inform Phase 4's <500ms Voronoi-recalc target by establishing the baseline cost of a full pipeline), (c) any preview alias mappings that needed adjustment (e.g. if "borders.png" alias should map to lookup_barony.png instead of lookup_condado.png).
</output>
