---
phase: 01
plan: 05
type: execute
wave: 5
depends_on:
  - 01-04
files_modified:
  - backend/medieval_forge/services/export.py
  - backend/medieval_forge/api/export.py
  - backend/medieval_forge/main.py
  - backend/tests/test_export.py
  - frontend/src/api/client.ts
  - frontend/src/pages/ProjectDetail.tsx
autonomous: true
requirements:
  - EXPORT-01
  - EXPORT-02

must_haves:
  truths:
    - "POST /api/projects/{id}/export builds {project_dir}/exports/medieval-forge-{project_id}-{timestamp}.zip from {project_dir}/generated/ files (EXPORT-01)"
    - "ZIP contains the 12-file Unity spec (EXPORT-02): 9 files map_generator produced + 3 placeholder files (terrain_lookup.png, terrain_types.json, mountain_river_data.json) created as empty/stub if not present in generated/"
    - "GET /api/projects/{id}/export/download returns the most recent ZIP via FileResponse with media_type='application/zip' and Content-Disposition: attachment"
    - "Both endpoints validate project_id via is_valid_uuid (T-PATH); export refuses if project.status not in {'generated', 'exported'} (must have generated maps to export)"
    - "Successful POST flips project.status to 'exported'"
    - "Frontend Export ZIP button is wired: triggers POST then triggers download via window.location or hidden anchor link"
  artifacts:
    - path: "backend/medieval_forge/services/export.py"
      provides: "build_unity_zip(project_id) — assembles 12-file ZIP, returns path"
      exports: ["build_unity_zip", "UNITY_ZIP_SPEC", "PLACEHOLDER_FILES"]
    - path: "backend/medieval_forge/api/export.py"
      provides: "POST /export + GET /export/download routes"
      exports: ["router"]
  key_links:
    - from: "backend/medieval_forge/services/export.py"
      to: "backend/medieval_forge/services/paths.py"
      via: "ensure_project_dirs (provides exports/ and generated/ paths) + project_dir validation"
      pattern: "ensure_project_dirs|project_dir"
    - from: "backend/medieval_forge/services/export.py"
      to: "zipfile.ZipFile"
      via: "stdlib ZIP assembly"
      pattern: "zipfile\\.ZipFile"
    - from: "backend/medieval_forge/api/export.py"
      to: "backend/medieval_forge/services/export.py"
      via: "build_unity_zip call"
      pattern: "build_unity_zip"
    - from: "frontend/src/pages/ProjectDetail.tsx"
      to: "/api/projects/{id}/export/download"
      via: "anchor href or window.location"
      pattern: "/export/download"
---

<objective>
Close out Phase 1 with the headless Unity ZIP export. After this plan, a Game Designer who has generated maps can click "Export ZIP" and receive a downloadable file containing the 12 standardized Unity files (EXPORT-02), unblocking the full ROADMAP success criterion #5 ("download a Unity ZIP containing all 12 standardized files from a generated project"). Per ROADMAP this is the headless v1 of export — Phase 6 polishes it (NEAREST upscale, Unity Y-up coords, validation gating in EXPORT-03/04).

Purpose: EXPORT-01 + EXPORT-02 turn generated artifacts into an installable Unity asset package. Per RESEARCH Open Question #3, only 9 of the 12 specified files are produced by the current map_generator; the other 3 (terrain_lookup.png, terrain_types.json, mountain_river_data.json) are filled with placeholder/stub content for Phase 1 and properly populated in Phase 6. This is captured in the ROADMAP — "headless validation stub" wording. We make the placeholder-vs-real status visible in the ZIP itself via a manifest file so Phase 6 doesn't have to guess what was real vs stub.

Output: services/export.py with the 12-file specification + placeholder generator; api/export.py with POST /export and GET /export/download; main.py wires router; test_export.py with EXPORT-01 (zip download) and EXPORT-02 (zip contents) tests; frontend Export button replaces the placeholder.
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
@.planning/phases/01-data-pipeline-backend-scaffold/01-04-map-generation-wrapper.md
@CLAUDE.md
@backend/medieval_forge/main.py
@backend/medieval_forge/services/paths.py
@backend/medieval_forge/services/generator.py
@backend/medieval_forge/api/projects.py
@backend/medieval_forge/api/generate.py
@frontend/src/pages/ProjectDetail.tsx
@frontend/src/api/client.ts

<interfaces>
<!-- Contracts THIS plan defines (Phase 1 terminus — no downstream Phase 1 plans consume them) -->

backend/medieval_forge/services/export.py:
```python
from pathlib import Path

# REQUIREMENTS.md EXPORT-02 explicit list:
UNITY_ZIP_SPEC: tuple[str, ...] = (
    "lookup_barony.png",
    "lookup_condado.png",
    "lookup_barony_colors.json",
    "lookup_condado_colors.json",
    "terrain_lookup.png",
    "terrain_types.json",
    "territory_metadata.json",
    "mountains_mask.png",
    "rivers_overlay.png",
    "visual_barony.png",
    "visual_condado.png",
    "mountain_river_data.json",
)

# 3 of these are NOT produced by map_generator in Phase 1; placeholder content is
# embedded in the ZIP and noted in the manifest (Phase 6 fills in real content).
PLACEHOLDER_FILES: frozenset[str] = frozenset({
    "terrain_lookup.png",
    "terrain_types.json",
    "mountain_river_data.json",
})

def build_unity_zip(project_id: str) -> Path:
    """Assemble {project_dir}/exports/medieval-forge-{project_id}-{timestamp}.zip.

    Returns the absolute path to the new ZIP file.
    Raises FileNotFoundError if generated/ dir is empty (project never generated).
    """
```

backend/medieval_forge/api/export.py:
```python
router = APIRouter(prefix="/projects", tags=["export"])

@router.post("/{project_id}/export", status_code=201)
async def trigger_export(project_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Returns {"project_id":..., "zip_filename":..., "size_bytes":...}."""

@router.get("/{project_id}/export/download")
async def download_export(project_id: str) -> FileResponse:
    """Returns the most recent ZIP for the project."""
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Wave 0 — test_export.py stubs (EXPORT-01, EXPORT-02 + T-PATH guards)</name>
  <files>backend/tests/test_export.py</files>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-VALIDATION.md
    - backend/tests/conftest.py
  </read_first>
  <action>
    Create `backend/tests/test_export.py`:
    ```python
    """Tests for EXPORT-01 (zip download) and EXPORT-02 (zip contents).

    Stubs in Wave 0 of Plan 01-05; implemented in Tasks 2 and 3.
    """
    import pytest


    @pytest.mark.skip(reason="Implemented by Plan 01-05 Task 2 (services.export)")
    async def test_build_unity_zip_assembles_12_files(client, tmp_path):
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-05 Task 2")
    async def test_build_unity_zip_rejects_empty_generated_dir(client, tmp_path):
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-05 Task 3 (api.export)")
    async def test_zip_download(client, tmp_path):
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-05 Task 3 (EXPORT-02 contents)")
    async def test_zip_contents(client, tmp_path):
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-05 Task 3 (T-PATH on download)")
    async def test_download_invalid_uuid_returns_400(client):
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-05 Task 3 (refuses pre-generated state)")
    async def test_export_refuses_if_not_generated(client):
        pass
    ```
  </action>
  <verify>
    <automated>py -m pytest backend/tests/test_export.py -q</automated>
  </verify>
  <done>6 tests collected, all skipped, 0 errors.</done>
  <acceptance_criteria>
    - backend/tests/test_export.py exists
    - Contains exactly 6 test functions (test_build_unity_zip_assembles_12_files, test_build_unity_zip_rejects_empty_generated_dir, test_zip_download, test_zip_contents, test_download_invalid_uuid_returns_400, test_export_refuses_if_not_generated)
    - py -m pytest backend/tests/test_export.py -q exits 0 with "6 skipped"
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: services/export.py — build_unity_zip + 12-file spec + placeholder generation + 2 unit tests</name>
  <files>
    backend/medieval_forge/services/export.py,
    backend/tests/test_export.py
  </files>
  <behavior>
    - `build_unity_zip(project_id)`:
      - Calls `ensure_project_dirs(project_id)` (which validates UUID and creates dirs if missing)
      - Asserts `generated/` is non-empty (at least one of the 9 generator outputs exists); raises FileNotFoundError if empty
      - Generates a timestamp in `YYYYMMDD-HHMMSS` UTC format
      - Creates `exports/medieval-forge-{project_id}-{timestamp}.zip`
      - Iterates over `UNITY_ZIP_SPEC` (the 12 file names per EXPORT-02): for each, if a file with that name exists in `generated/`, write it into the ZIP; otherwise create a placeholder (empty 1x1 PNG byte sequence for `.png` files, `{}` for `.json` files) and write it to the ZIP with the same filename
      - Adds a `MANIFEST.json` at the root of the ZIP listing each file as `{name, source: "generated"|"placeholder", size_bytes}` so Phase 6 can identify what needs upgrading
      - Returns the Path to the ZIP
    - Two unit tests: build_unity_zip_assembles_12_files (drop fake generated/ files, build, inspect ZIP contents); build_unity_zip_rejects_empty_generated_dir (empty generated/ → FileNotFoundError)
  </behavior>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md (Don't Hand-Roll — zipfile.ZipFile; Open Question #3 — 12-file spec gap)
    - .planning/REQUIREMENTS.md (EXPORT-02 — exact 12 file names)
    - backend/medieval_forge/services/paths.py
    - backend/medieval_forge/services/generator.py (GENERATED_FILE_WHITELIST for cross-reference)
  </read_first>
  <action>
    1. CREATE `backend/medieval_forge/services/export.py`:
       ```python
       """EXPORT-01 + EXPORT-02: Unity-ready ZIP assembly.

       The 12-file spec (REQUIREMENTS.md EXPORT-02) consists of 9 files produced by
       map_generator + 3 placeholder files (terrain_lookup.png, terrain_types.json,
       mountain_river_data.json) that Phase 6 polish will replace with real content.

       The ZIP includes a MANIFEST.json so consumers (and Phase 6) can distinguish
       real content from placeholders.
       """
       from __future__ import annotations

       import json
       import logging
       import zipfile
       from datetime import datetime, timezone
       from pathlib import Path

       from .paths import ensure_project_dirs

       logger = logging.getLogger(__name__)

       # EXPORT-02: explicit 12-file Unity spec from REQUIREMENTS.md.
       UNITY_ZIP_SPEC: tuple[str, ...] = (
           "lookup_barony.png",
           "lookup_condado.png",
           "lookup_barony_colors.json",
           "lookup_condado_colors.json",
           "terrain_lookup.png",
           "terrain_types.json",
           "territory_metadata.json",
           "mountains_mask.png",
           "rivers_overlay.png",
           "visual_barony.png",
           "visual_condado.png",
           "mountain_river_data.json",
       )

       # These three are not produced by map_generator in Phase 1 (RESEARCH Open Q #3).
       # Phase 6 (EXPORT-03/04) will replace them with real content.
       PLACEHOLDER_FILES: frozenset[str] = frozenset({
           "terrain_lookup.png",
           "terrain_types.json",
           "mountain_river_data.json",
       })

       # Minimal valid 1x1 transparent PNG (signature + IHDR + IDAT + IEND).
       _PLACEHOLDER_PNG: bytes = (
           b"\x89PNG\r\n\x1a\n"
           b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
           b"\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
           b"\x00\x00\x00\x00IEND\xaeB`\x82"
       )
       _PLACEHOLDER_JSON: bytes = b"{}\n"


       def _placeholder_payload(filename: str) -> bytes:
           if filename.endswith(".png"):
               return _PLACEHOLDER_PNG
           if filename.endswith(".json"):
               return _PLACEHOLDER_JSON
           return b""


       def build_unity_zip(project_id: str) -> Path:
           """Assemble the project's Unity ZIP. Returns the absolute path to the new file.

           Raises:
               FileNotFoundError: if generated/ has none of the expected files.
           """
           dirs = ensure_project_dirs(project_id)
           generated = dirs["generated"]
           exports = dirs["exports"]

           # Guard: must have at least one generator output before exporting.
           any_generated = any((generated / fname).exists() for fname in UNITY_ZIP_SPEC)
           if not any_generated:
               raise FileNotFoundError(
                   f"no generated outputs in {generated} — generate maps before exporting"
               )

           timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
           zip_name = f"medieval-forge-{project_id}-{timestamp}.zip"
           zip_path = exports / zip_name
           tmp_path = zip_path.with_suffix(zip_path.suffix + ".tmp")

           manifest: list[dict] = []

           with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
               for fname in UNITY_ZIP_SPEC:
                   source_path = generated / fname
                   if source_path.exists():
                       data = source_path.read_bytes()
                       source = "generated"
                   else:
                       data = _placeholder_payload(fname)
                       source = "placeholder"
                   zf.writestr(fname, data)
                   manifest.append({
                       "name": fname,
                       "source": source,
                       "size_bytes": len(data),
                   })
               manifest_payload = json.dumps(
                   {
                       "project_id": project_id,
                       "exported_at_utc": timestamp,
                       "spec_version": 1,
                       "phase": 1,
                       "note": (
                           "Phase 1 export — 'placeholder' files are stubs that "
                           "Phase 6 (EXPORT-03/04) will replace with real content."
                       ),
                       "files": manifest,
                   },
                   indent=2,
               )
               zf.writestr("MANIFEST.json", manifest_payload)

           tmp_path.replace(zip_path)
           logger.info("export built: %s (%d files)", zip_path, len(UNITY_ZIP_SPEC))
           return zip_path
       ```

    2. REPLACE the two unit-test stubs in `backend/tests/test_export.py`:
       ```python
       """Tests for EXPORT-01 (zip download) and EXPORT-02 (zip contents)."""
       from __future__ import annotations

       import json
       import zipfile
       from pathlib import Path

       import pytest


       @pytest.fixture(autouse=True)
       def _isolated_projects_root(tmp_path, monkeypatch):
           from medieval_forge.services import paths as paths_mod
           monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")


       async def _create_project(client, **overrides):
           payload = {
               "name": "exp-test",
               "country_qid": "Q29",
               "period_start": 800,
               "period_end": 1000,
           }
           payload.update(overrides)
           return (await client.post("/api/projects", json=payload)).json()


       def _drop_fake_generated_files(generated_dir: Path) -> None:
           """Drop a small set of the 9 generator outputs so build_unity_zip has
           something real to work with — placeholders fill in the other slots."""
           generated_dir.mkdir(parents=True, exist_ok=True)
           (generated_dir / "visual_condado.png").write_bytes(b"\x89PNG\r\n\x1a\nfake1")
           (generated_dir / "lookup_condado.png").write_bytes(b"\x89PNG\r\n\x1a\nfake2")
           (generated_dir / "lookup_condado_colors.json").write_text(json.dumps({"1": "rgb"}))
           (generated_dir / "territory_metadata.json").write_text(json.dumps({"k": "v"}))


       async def test_build_unity_zip_assembles_12_files(client, tmp_path):
           from medieval_forge.services.export import (
               PLACEHOLDER_FILES,
               UNITY_ZIP_SPEC,
               build_unity_zip,
           )
           from medieval_forge.services.paths import ensure_project_dirs

           created = await _create_project(client)
           pid = created["id"]
           dirs = ensure_project_dirs(pid)
           _drop_fake_generated_files(dirs["generated"])

           zip_path = build_unity_zip(pid)

           assert zip_path.exists()
           assert zip_path.parent == dirs["exports"]
           assert zip_path.name.startswith(f"medieval-forge-{pid}-")
           assert zip_path.suffix == ".zip"

           with zipfile.ZipFile(zip_path) as zf:
               names = zf.namelist()
               # All 12 spec files PLUS MANIFEST.json.
               for fname in UNITY_ZIP_SPEC:
                   assert fname in names, f"missing {fname}"
               assert "MANIFEST.json" in names

               manifest = json.loads(zf.read("MANIFEST.json").decode("utf-8"))
               assert manifest["project_id"] == pid
               assert manifest["spec_version"] == 1
               assert manifest["phase"] == 1
               manifest_files = {entry["name"]: entry for entry in manifest["files"]}

               # Files we dropped: source == "generated".
               for real in ["visual_condado.png", "lookup_condado.png",
                            "lookup_condado_colors.json", "territory_metadata.json"]:
                   assert manifest_files[real]["source"] == "generated"

               # Files in PLACEHOLDER_FILES that we never created: source == "placeholder".
               for placeholder in PLACEHOLDER_FILES:
                   assert manifest_files[placeholder]["source"] == "placeholder"


       async def test_build_unity_zip_rejects_empty_generated_dir(client, tmp_path):
           from medieval_forge.services.export import build_unity_zip
           from medieval_forge.services.paths import ensure_project_dirs

           created = await _create_project(client)
           pid = created["id"]
           ensure_project_dirs(pid)  # creates empty generated/

           with pytest.raises(FileNotFoundError):
               build_unity_zip(pid)
       ```

       Leave the other 4 stubs (test_zip_download, test_zip_contents, test_download_invalid_uuid_returns_400, test_export_refuses_if_not_generated) as `@pytest.mark.skip` — they're implemented in Task 3.

       Run: `py -m pytest backend/tests/test_export.py -x -q`. Expected: 2 passed, 4 skipped.
  </action>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md
    - .planning/REQUIREMENTS.md
    - backend/medieval_forge/services/paths.py
    - backend/tests/test_export.py
  </read_first>
  <verify>
    <automated>py -m pytest backend/tests/test_export.py -x -q</automated>
  </verify>
  <done>2 passed, 4 skipped. ZIP assembly correctly distinguishes generated from placeholder files via MANIFEST.json.</done>
  <acceptance_criteria>
    - backend/medieval_forge/services/export.py contains "UNITY_ZIP_SPEC"
    - backend/medieval_forge/services/export.py contains exactly 12 entries in UNITY_ZIP_SPEC tuple (verify by reading the file or by running a Python check)
    - backend/medieval_forge/services/export.py contains all 12 filenames from REQUIREMENTS.md EXPORT-02: "lookup_barony.png", "lookup_condado.png", "lookup_barony_colors.json", "lookup_condado_colors.json", "terrain_lookup.png", "terrain_types.json", "territory_metadata.json", "mountains_mask.png", "rivers_overlay.png", "visual_barony.png", "visual_condado.png", "mountain_river_data.json"
    - backend/medieval_forge/services/export.py contains "PLACEHOLDER_FILES"
    - backend/medieval_forge/services/export.py contains "zipfile.ZipFile"
    - backend/medieval_forge/services/export.py contains "MANIFEST.json"
    - backend/medieval_forge/services/export.py contains "tmp_path.replace(zip_path)" (atomic write)
    - py -m pytest backend/tests/test_export.py::test_build_unity_zip_assembles_12_files -x exits 0
    - py -m pytest backend/tests/test_export.py::test_build_unity_zip_rejects_empty_generated_dir -x exits 0
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 3: api/export.py — POST /export + GET /export/download + main.py wires + 4 endpoint tests</name>
  <files>
    backend/medieval_forge/api/export.py,
    backend/medieval_forge/main.py,
    backend/tests/test_export.py
  </files>
  <behavior>
    - `POST /api/projects/{project_id}/export`:
      - T-PATH: validates project_id; 400 on bad UUID
      - 404 if project missing
      - 409 if `project.status not in {"generated", "exported"}` (must have generated maps; allow re-export)
      - Calls `build_unity_zip(project_id)` (synchronous; ZIP assembly is fast — the heavy work was in Plan 04 generation)
      - Updates `project.status = "exported"`
      - Returns 201 + `{"project_id": id, "zip_filename": filename, "size_bytes": N, "download_url": "/api/projects/{id}/export/download"}`
    - `GET /api/projects/{project_id}/export/download`:
      - T-PATH: validates project_id; 400 on bad UUID
      - Lists files in `{project_dir}/exports/` matching `medieval-forge-{project_id}-*.zip`; picks the most recent by mtime
      - 404 if no ZIP exists
      - Returns FileResponse with `media_type="application/zip"` and `headers={"Content-Disposition": f'attachment; filename="{name}"'}`
    - 4 endpoint tests pass: test_zip_download, test_zip_contents, test_download_invalid_uuid_returns_400, test_export_refuses_if_not_generated
  </behavior>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md (Pattern 5/8 — main.py mount order)
    - backend/medieval_forge/main.py
    - backend/medieval_forge/api/projects.py (router pattern reference)
    - backend/medieval_forge/api/generate.py (T-PATH/T-DOS pattern reference)
    - backend/medieval_forge/services/export.py
    - backend/medieval_forge/services/paths.py
    - backend/tests/test_export.py
  </read_first>
  <action>
    1. CREATE `backend/medieval_forge/api/export.py`:
       ```python
       """EXPORT-01 + EXPORT-02: trigger ZIP build + serve download."""
       from __future__ import annotations

       import logging

       from fastapi import APIRouter, Depends, HTTPException, status
       from fastapi.responses import FileResponse
       from sqlalchemy.ext.asyncio import AsyncSession

       from ..database import get_db
       from ..models import Project
       from ..services.export import build_unity_zip
       from ..services.paths import is_valid_uuid, project_dir

       logger = logging.getLogger(__name__)
       router = APIRouter(prefix="/projects", tags=["export"])

       _ALLOWED_PRE_EXPORT_STATUSES: frozenset[str] = frozenset({"generated", "exported"})


       @router.post("/{project_id}/export", status_code=status.HTTP_201_CREATED)
       async def trigger_export(
           project_id: str,
           db: AsyncSession = Depends(get_db),
       ) -> dict:
           if not is_valid_uuid(project_id):
               raise HTTPException(status_code=400, detail="project_id must be a valid UUID")
           project = await db.get(Project, project_id)
           if project is None:
               raise HTTPException(status_code=404, detail="project not found")
           if project.status not in _ALLOWED_PRE_EXPORT_STATUSES:
               raise HTTPException(
                   status_code=409,
                   detail=(
                       f"project.status is {project.status!r}; export requires "
                       f"status in {sorted(_ALLOWED_PRE_EXPORT_STATUSES)} "
                       "(run /generate first)"
                   ),
               )

           try:
               zip_path = build_unity_zip(project_id)
           except FileNotFoundError as exc:
               raise HTTPException(status_code=409, detail=str(exc))

           project.status = "exported"
           await db.commit()

           return {
               "project_id": project_id,
               "zip_filename": zip_path.name,
               "size_bytes": zip_path.stat().st_size,
               "download_url": f"/api/projects/{project_id}/export/download",
           }


       @router.get("/{project_id}/export/download")
       async def download_export(project_id: str) -> FileResponse:
           if not is_valid_uuid(project_id):
               raise HTTPException(status_code=400, detail="project_id must be a valid UUID")
           exports_dir = project_dir(project_id) / "exports"
           if not exports_dir.is_dir():
               raise HTTPException(status_code=404, detail="no exports for this project")
           candidates = sorted(
               exports_dir.glob(f"medieval-forge-{project_id}-*.zip"),
               key=lambda p: p.stat().st_mtime,
               reverse=True,
           )
           if not candidates:
               raise HTTPException(status_code=404, detail="no exports for this project")
           target = candidates[0]
           return FileResponse(
               target,
               media_type="application/zip",
               filename=target.name,
               headers={"Content-Disposition": f'attachment; filename="{target.name}"'},
           )
       ```

    2. EDIT `backend/medieval_forge/main.py`. Add the export router AFTER generate_router and BEFORE the SPA catch-all:
       ```python
       from .api.export import router as export_router

       app.include_router(export_router, prefix="/api")
       ```

    3. REPLACE the 4 remaining skip-stubs in `backend/tests/test_export.py`:
       ```python
       async def test_zip_download(client, tmp_path):
           """EXPORT-01: POST /export builds a ZIP, GET /export/download returns it."""
           from medieval_forge.services.paths import ensure_project_dirs

           created = await _create_project(client)
           pid = created["id"]
           dirs = ensure_project_dirs(pid)
           _drop_fake_generated_files(dirs["generated"])
           # Project must be in 'generated' state to allow export.
           await client.patch(f"/api/projects/{pid}", json={"status": "generated"})

           # POST /export
           post_resp = await client.post(f"/api/projects/{pid}/export")
           assert post_resp.status_code == 201, post_resp.text
           body = post_resp.json()
           assert body["project_id"] == pid
           assert body["zip_filename"].startswith(f"medieval-forge-{pid}-")
           assert body["size_bytes"] > 0
           assert body["download_url"] == f"/api/projects/{pid}/export/download"

           # GET /export/download
           get_resp = await client.get(f"/api/projects/{pid}/export/download")
           assert get_resp.status_code == 200
           assert get_resp.headers["content-type"] == "application/zip"
           assert "attachment" in get_resp.headers.get("content-disposition", "")
           assert get_resp.content[:4] == b"PK\x03\x04"  # ZIP magic

           # Status flipped to "exported".
           proj_resp = await client.get(f"/api/projects/{pid}")
           assert proj_resp.json()["status"] == "exported"


       async def test_zip_contents(client, tmp_path):
           """EXPORT-02: downloaded ZIP contains all 12 spec files plus MANIFEST."""
           import io
           import zipfile

           from medieval_forge.services.export import UNITY_ZIP_SPEC
           from medieval_forge.services.paths import ensure_project_dirs

           created = await _create_project(client)
           pid = created["id"]
           dirs = ensure_project_dirs(pid)
           _drop_fake_generated_files(dirs["generated"])
           await client.patch(f"/api/projects/{pid}", json={"status": "generated"})
           await client.post(f"/api/projects/{pid}/export")

           resp = await client.get(f"/api/projects/{pid}/export/download")
           assert resp.status_code == 200

           with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
               names = set(zf.namelist())
           for fname in UNITY_ZIP_SPEC:
               assert fname in names, f"missing {fname}"
           assert "MANIFEST.json" in names


       async def test_download_invalid_uuid_returns_400(client):
           resp = await client.get("/api/projects/not-a-uuid/export/download")
           assert resp.status_code == 400


       async def test_export_refuses_if_not_generated(client):
           """409 if project.status is not 'generated' or 'exported'."""
           created = await _create_project(client)
           pid = created["id"]
           # status is 'created' by default — must not allow export.
           resp = await client.post(f"/api/projects/{pid}/export")
           assert resp.status_code == 409
           assert "generate" in resp.json()["detail"].lower()
       ```

       Run: `py -m pytest backend/tests/test_export.py -x -q`. Expected: 6 passed.
  </action>
  <read_first>
    - backend/medieval_forge/main.py
    - backend/medieval_forge/api/projects.py
    - backend/medieval_forge/api/generate.py
    - backend/medieval_forge/services/export.py
    - backend/medieval_forge/services/paths.py
    - backend/tests/test_export.py
  </read_first>
  <verify>
    <automated>py -m pytest backend/tests/test_export.py -x -q</automated>
  </verify>
  <done>6 passed; main.py registers export_router before SPA catch-all; ZIP magic bytes confirm valid archive.</done>
  <acceptance_criteria>
    - backend/medieval_forge/api/export.py contains "router = APIRouter(prefix=\"/projects\""
    - backend/medieval_forge/api/export.py contains "build_unity_zip(project_id)"
    - backend/medieval_forge/api/export.py contains "is_valid_uuid(project_id)"
    - backend/medieval_forge/api/export.py contains "_ALLOWED_PRE_EXPORT_STATUSES" OR equivalent status guard
    - backend/medieval_forge/api/export.py contains "media_type=\"application/zip\""
    - backend/medieval_forge/api/export.py contains "Content-Disposition"
    - backend/medieval_forge/api/export.py contains "project.status = \"exported\""
    - backend/medieval_forge/main.py contains "from .api.export import router as export_router"
    - backend/medieval_forge/main.py contains "app.include_router(export_router, prefix=\"/api\")"
    - py -m pytest backend/tests/test_export.py -x -q exits 0 with "6 passed"
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 4: Frontend wires Export button — useExport hook + download trigger</name>
  <files>
    frontend/src/api/client.ts,
    frontend/src/pages/ProjectDetail.tsx
  </files>
  <behavior>
    - New helper `useExport(projectId)` exposes `{trigger: () => Promise<ExportResponse>, isPending: boolean, error: Error | null}`. Uses `useMutation` to POST `/api/projects/{id}/export`. On success, invalidates the project query (status flips to "exported") AND triggers a browser download by setting `window.location.href = downloadUrl` (or via a hidden `<a download>` click).
    - ProjectDetail: replaces the disabled "Export ZIP (Plan 1.5)" button with a real one. Disabled when `project.status !== 'generated' && project.status !== 'exported'`. Title attribute explains: "Generate maps first (status must be 'generated' or 'exported')". On click, calls trigger() and the download starts automatically.
  </behavior>
  <read_first>
    - frontend/src/api/client.ts
    - frontend/src/pages/ProjectDetail.tsx
  </read_first>
  <action>
    1. APPEND to `frontend/src/api/client.ts`:
       ```typescript
       export interface ExportResponse {
         project_id: string
         zip_filename: string
         size_bytes: number
         download_url: string
       }

       export function useExport(projectId: string | undefined) {
         const qc = useQueryClient()
         return useMutation({
           mutationFn: async () => {
             return jsonFetch<ExportResponse>(
               `/api/projects/${projectId}/export`,
               { method: 'POST' },
             )
           },
           onSuccess: (data) => {
             qc.invalidateQueries({ queryKey: ['projects', projectId] })
             qc.invalidateQueries({ queryKey: ['projects'] })
             // Trigger browser download by navigating the hidden iframe-like link.
             // Using a hidden anchor avoids losing SPA route state.
             const a = document.createElement('a')
             a.href = data.download_url
             a.download = data.zip_filename
             document.body.appendChild(a)
             a.click()
             document.body.removeChild(a)
           },
         })
       }
       ```

    2. EDIT `frontend/src/pages/ProjectDetail.tsx`. Add the import:
       ```typescript
       import { useExport } from '../api/client'
       ```

       In the component body (alongside useGenerate / useIngestStream):
       ```typescript
       const exportZip = useExport(id)
       ```

       Replace the disabled "Export ZIP (Plan 1.5)" button with:
       ```typescript
       <Button
         variant="soft"
         color="green"
         onClick={() => exportZip.mutate()}
         disabled={
           exportZip.isPending ||
           (project.status !== 'generated' && project.status !== 'exported')
         }
         title={
           project.status === 'generated' || project.status === 'exported'
             ? 'Build and download Unity ZIP'
             : 'Generate maps first (status must be generated or exported)'
         }
       >
         {exportZip.isPending ? 'Building ZIP…' : 'Export ZIP'}
       </Button>
       ```

       Add an error display near the existing generate.error display:
       ```typescript
       {exportZip.error && (
         <Text color="red" size="2">Export error: {(exportZip.error as Error).message}</Text>
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
    <automated>cd frontend && npm run build && grep -l "useExport" src/pages/ProjectDetail.tsx</automated>
  </verify>
  <done>npm run build succeeds; ProjectDetail uses useExport; the disabled placeholder is gone; Plan 1.5 placeholder text is no longer in the file (all 3 placeholders replaced over Plans 03/04/05).</done>
  <acceptance_criteria>
    - frontend/src/api/client.ts contains "export function useExport"
    - frontend/src/api/client.ts contains "export interface ExportResponse"
    - frontend/src/api/client.ts contains "/api/projects/${projectId}/export"
    - frontend/src/api/client.ts contains "document.createElement('a')" OR equivalent download trigger
    - frontend/src/pages/ProjectDetail.tsx contains "useExport"
    - frontend/src/pages/ProjectDetail.tsx contains "exportZip.mutate()"
    - frontend/src/pages/ProjectDetail.tsx does NOT contain "Plan 1.5" anymore (all placeholders consumed)
    - frontend/src/pages/ProjectDetail.tsx does NOT contain "Plan 1.4" anymore (Plan 04 consumed it)
    - frontend/src/pages/ProjectDetail.tsx does NOT contain "Plan 1.3" anymore (Plan 03 consumed it)
    - cd frontend && npm run build exits 0
  </acceptance_criteria>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Browser → POST /api/projects/{id}/export | path param; project_id validated; no body |
| Browser → GET /api/projects/{id}/export/download | path param; project_id validated; file selected from project's exports/ via stem-bound glob |
| FastAPI → filesystem (project exports/, generated/) | All paths derived from project_dir(project_id); zipfile writes confined to exports/ |
| ZIP archive contents → end user (Unity) | The ZIP includes a MANIFEST.json declaring which files are placeholders; Phase 6 will validate and harden |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-PATH (export trigger) | Tampering | api/export.py POST /export | mitigate | `is_valid_uuid(project_id)` → 400; build_unity_zip uses ensure_project_dirs which re-validates AND constrains the path to PROJECTS_ROOT. |
| T-PATH (download) | Tampering | api/export.py GET /export/download | mitigate | `is_valid_uuid(project_id)` → 400; the glob `medieval-forge-{project_id}-*.zip` includes the validated project_id as a literal in the filename pattern, so a directory traversal in `project_id` would fail UUID validation OR would not match any actual file. The candidate file's parent is exports_dir which itself was resolved through project_dir() (T-PATH validated). |
| T-05-01 | Denial of Service | Repeated POST /export creates a new ZIP each time | accept | Local single-user tool; ZIP creation is fast (~seconds at most); old ZIPs accumulate in exports/ (acceptable disk usage; user can delete project to clean up). Phase 6 polish may add retention. |
| T-05-02 | Information Disclosure | MANIFEST.json reveals project_id and timestamp | accept | The ZIP is downloaded by the local user only; no external exposure. project_id is also visible in the URL the user just used. ASVS V7 OK. |
| T-05-03 | Tampering | Download anchor click bypasses SPA state | accept | Standard browser download pattern. The hidden anchor is appended/clicked/removed in the same tick — no race window. Project status invalidation via TanStack Query happens on success regardless. |
| T-05-04 | Tampering | ZIP includes placeholder PNG/JSON content | accept (documented) | MANIFEST.json marks each file as `"source": "generated"` or `"source": "placeholder"`. Phase 6 (EXPORT-03/04) is the explicit remediation for this Phase 1 limitation. Documented in code, in the manifest, and in this plan. |
</threat_model>

<verification>
After all 4 tasks complete:

**Quick run** (per-task feedback latency):
```bash
py -m pytest backend/tests/ -v --tb=short -m "not slow"
```
Expected: 32 passing tests cumulative (5 cli + 1 packaging + 9 projects + 7 ingest + 4 generate-fast + 6 export). All Phase 1 fast tests green.

**Slow run** (phase gate — required before /gsd-verify-work):
```bash
py -m pytest backend/tests/ -v --tb=short -m slow
```
Expected: 3 passed (1 packaging + 2 generate-slow).

**Full suite**:
```bash
py -m pytest backend/tests/ -v --tb=short
```
Expected: 35 passed (32 fast + 3 slow). 0 failures.

Manual end-to-end smoke (the canonical Phase 1 demo):
```bash
medieval-forge start --no-browser
# Browser: http://localhost:8765
# Create project country_qid=Q45 (Portugal)
# Click "Ingest from Wikidata" → wait for "DONE"
# Paste minimal territory JSON, click "Generate" → status flips to "generated", 3 previews render
# Click "Export ZIP" → file downloads as medieval-forge-{uuid}-{ts}.zip
# Verify on disk: open the ZIP, confirm 12 spec files + MANIFEST.json
unzip -l ~/Downloads/medieval-forge-*.zip
medieval-forge stop
```
</verification>

<success_criteria>
- `py -m pytest backend/tests/test_export.py -x -q` passes 6/6.
- `py -m pytest backend/tests/ -x -q` passes 32/32 fast + 3/3 slow = 35/35 total.
- Manual smoke: full pipeline (create → ingest → generate → export → download) works end-to-end through the browser, producing a valid 12-file Unity ZIP.
- All Phase 1 ROADMAP success criteria are satisfied:
  - #1: pip install + medieval-forge start + browser opens (Plan 01-01)
  - #2: full project CRUD via UI (Plan 01-02)
  - #3: Wikidata ingestion + real-time progress + GeoJSON written (Plan 01-03)
  - #4: trigger generation + view 3 PNG previews in browser (Plan 01-04)
  - #5: download Unity ZIP with all 12 standardized files (THIS PLAN)
- ZIP MANIFEST.json clearly identifies the 3 placeholder files (terrain_lookup.png, terrain_types.json, mountain_river_data.json) as `source: "placeholder"`, providing a clean handoff for Phase 6 (EXPORT-03/04) to upgrade them to real content.
</success_criteria>

<output>
After completion, create `.planning/phases/01-data-pipeline-backend-scaffold/01-05-SUMMARY.md` per the standard summary template. Note: (a) actual ZIP size for the minimal test project (informs Phase 6 file-size estimate UI in EXPORT-04), (b) any decisions about ZIP retention policy (current default: keep all ZIPs forever in exports/), (c) confirmation that Phase 1 is end-to-end exercisable and ready for /gsd-verify-work + /gsd-uat.
</output>
