"""v3 artifact-serving endpoint (D-18, T-03-01, T-03-05).

Serves files from `projects/<uuid>/output/` via FastAPI `FileResponse` (per
RESEARCH §Pitfall 3: StaticFiles cannot rewrite `{id}/artifacts/*` → disk
`{id}/output/*`).

Single source of truth for the 16-file allowlist: `ARTIFACT_FILES`. The
`status.py` manifest endpoint imports this exact frozenset. Plan 05-11 added
the terrain pair (terrain_lookup.png + terrain_types.json) to close the SC-3
12-file contract.

Defense-in-depth path containment:
  1. `is_valid_uuid(project_id)` — 400 on bad UUID.
  2. `file_name in ARTIFACT_FILES` — 404 on anything else (mitigates
     T-03-05 information disclosure via the allowlist).
  3. `project_dir(project_id)` — raises ValueError on PROJECTS_ROOT escape;
     wrapped → 404.
  4. `target.resolve()` + `startswith(output_dir.resolve())` — final
     containment check (mitigates T-03-01 path traversal via symlinks).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ...services.paths import is_valid_uuid, project_dir

router = APIRouter(prefix="/v3/projects", tags=["v3-artifacts"])

# 16-file allowlist: 12 Unity-contract files + 4 Phase 03-01 canvas-sidecar
# files. Single source of truth — status.py imports this. Plan 05-11 closed
# the terrain pair (terrain_lookup.png + terrain_types.json) so the full
# 12-file Unity contract is now serveable.
ARTIFACT_FILES: frozenset[str] = frozenset({
    # 12 Unity-contract files (per CLAUDE.md §"v3 Pipeline Contract").
    "lookup_barony.png",
    "lookup_condado.png",
    "lookup_barony_colors.json",
    "lookup_condado_colors.json",
    "terrain_lookup.png",
    "terrain_types.json",
    "territory_metadata.json",
    "visual_condado.png",
    "visual_barony.png",
    "mountains_mask.png",
    "rivers_overlay.png",
    "mountain_river_data.json",
    # 4 Phase 03-01 canvas-sidecar files.
    "territories.geojson",
    "baronies.geojson",
    "condado_colors.json",
    "barony_colors.json",
})


@router.get("/{project_id}/artifacts/{file_name}")
async def serve_artifact(project_id: str, file_name: str) -> FileResponse:
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a valid UUID")

    if file_name not in ARTIFACT_FILES:
        raise HTTPException(
            status_code=404, detail=f"file '{file_name}' is not a serveable artifact"
        )

    try:
        root = project_dir(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="project not found")

    output_dir = (root / "output").resolve()
    target = (output_dir / file_name).resolve()

    # Defense-in-depth: ensure target is still inside the project's output dir.
    # (FastAPI's path matcher already blocks `..` segments in `{file_name}`,
    # but symlinks inside output/ could escape — this catches that.)
    if not str(target).startswith(str(output_dir)):
        raise HTTPException(status_code=404, detail="file not found")

    if not target.is_file():
        raise HTTPException(
            status_code=404, detail=f"artifact '{file_name}' not generated yet"
        )

    # Native HTTP cache; ?v={updated_at} on the URL is what makes regen invalidate
    # (D-19 cache-bust pattern). `immutable` directive is safe because the URL
    # changes whenever artifacts change.
    return FileResponse(
        target,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


__all__ = ["router", "ARTIFACT_FILES"]
