"""v3 artifact-serving endpoint (D-18, T-03-01, T-03-05).

Serves files from `projects/<uuid>/output/` via FastAPI `FileResponse` (per
RESEARCH §Pitfall 3: StaticFiles cannot rewrite `{id}/artifacts/*` → disk
`{id}/output/*`).

Plan 07-08 Task 2 (Pattern 12): `territory_metadata.json` is special-cased.
When `project_dir/research_overlay.json` exists the endpoint merges it via
`services/research/overlay.merge_overlay()` and returns a `JSONResponse`
instead of `FileResponse`. The merge defaults to `_ALL_OVERLAY_FIELDS` (no
`allowed_fields` argument) so the UI receives all three overlay fields
regardless of the zip-bound verdict (Strict vs Tolerant). The endpoint is
READ-ONLY — no disk writes (T-07-08-01 + WARNING 5 sha256 regression test).

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
from fastapi.responses import FileResponse, JSONResponse, Response

from ...services.paths import is_valid_uuid, project_dir
# Plan 07-08 Task 2 (Pattern 12): merge_overlay + load_overlay_if_exists imports.
# Grep contract: `from ..services.research.overlay import` (wildcard-friendly).
from ...services.research.overlay import load_overlay_if_exists, merge_overlay

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
async def serve_artifact(project_id: str, file_name: str) -> Response:
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

    # Plan 07-08 Task 2 (Pattern 12): merged-on-the-fly territory_metadata.json.
    # When `project_dir/research_overlay.json` exists, merge it into the raw
    # territory_metadata.json IN MEMORY and return JSONResponse. The endpoint is
    # READ-ONLY — no disk writes, ever (T-07-08-01 + WARNING 5 regression test).
    #
    # The merge call here passes NO `allowed_fields` argument so the function
    # defaults to `_ALL_OVERLAY_FIELDS` — the UI always sees the full overlay
    # regardless of the Strict/Tolerant zip-bound verdict. Only build_unity_zip
    # narrows the field set via `_ZIP_BOUND_FIELDS` (Pattern 11).
    if file_name == "territory_metadata.json":
        overlay_path = root / "research_overlay.json"
        overlay = load_overlay_if_exists(overlay_path)
        if overlay is not None:
            import json as _json
            raw = _json.loads(target.read_bytes())
            merged = merge_overlay(raw, overlay)
            return JSONResponse(
                content=merged,
                headers={"Cache-Control": "public, max-age=31536000, immutable"},
            )

    # Native HTTP cache; ?v={updated_at} on the URL is what makes regen invalidate
    # (D-19 cache-bust pattern). `immutable` directive is safe because the URL
    # changes whenever artifacts change.
    return FileResponse(
        target,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


__all__ = ["router", "ARTIFACT_FILES"]
