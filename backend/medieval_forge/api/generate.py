"""GEN-01..03: trigger generation (BackgroundTask) + serve PNG previews.

T-PATH: project_id validated; preview filename whitelisted.
T-DOS:  reject if project already generating.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import AsyncSessionLocal, get_db
from ..models import Project
import asyncio

from ..services.generator import GENERATED_FILE_WHITELIST, run_generation
from ..services.paths import is_valid_uuid, project_dir
from ..services.render_modern import render_modern_map
from ..services.territory_builder import build_territory_data_from_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["generate"])


_MEDIA_TYPES = {".png": "image/png", ".json": "application/json; charset=utf-8"}


async def _run_and_update_status(project_id: str, config: dict) -> None:
    """Background task body: runs generation; updates project.status atomically."""
    last_error: str | None = None
    try:
        manifest = await run_generation(project_id, config)
        new_status = "generated"
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

    # Compose config: project bbox → project.generator_config → request body
    # Precedence for territory_data (QUICK-260426-q3v fix for orphan bug #4):
    #   1. Latest ResearchCache row keyed on (country_qid, period_start, period_end)
    #      — this is the canonical source of truth (e.g., 91-condado manual research).
    #   2. Request body — IGNORED unless `force_body_territory_data: true` is set,
    #      which acts as a power-user/test escape hatch.
    # The cache key is derived from the project row, never the body — so a
    # malicious client cannot redirect the lookup (T-q3v-04).
    merged: dict = {}
    # Injetar bbox do projeto no RegionConfig (evita usar bounds padrão incorretos)
    if project.bbox_lon_min is not None:
        merged["lon_min"] = project.bbox_lon_min
        merged["lon_max"] = project.bbox_lon_max
        merged["lat_min"] = project.bbox_lat_min
        merged["lat_max"] = project.bbox_lat_max
    merged.update(project.generator_config or {})
    if body:
        merged.update(body)

    force_body = bool(merged.pop("force_body_territory_data", False))
    if not force_body:
        cached_td = await build_territory_data_from_cache(
            db, project, project_dir(project_id)
        )
        if cached_td is not None:
            logger.info(
                "generate: using cached research (%d condados) for project=%s",
                len(cached_td.get("condados", [])),
                project_id,
            )
            merged["territory_data"] = cached_td
    else:
        logger.info("generate: force_body_territory_data=true — skipping cache lookup for project=%s", project_id)

    if "territory_data" not in merged:
        raise HTTPException(
            status_code=422,
            detail=(
                "No cached research found and no territory_data provided. "
                "Run research first (POST /projects/{id}/research/manual or via an LLM provider), "
                "or include territory_data explicitly in the request body with "
                '"force_body_territory_data": true.'
            ),
        )

    project.status = "generating"
    await db.commit()

    background_tasks.add_task(_run_and_update_status, project_id, merged)
    return {"project_id": project_id, "status": "generating"}


@router.post("/{project_id}/render-modern")
async def trigger_render_modern(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Renderiza um mapa visual simples dos polígonos ingeridos (validação geográfica).

    Este endpoint NÃO precisa de territory_data — apenas pinta cada município
    com uma cor única para o utilizador validar que a ingestão está correta
    antes de tentar a geração medieval completa.
    """
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a valid UUID")
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    if project.bbox_lon_min is None or project.bbox_lat_min is None \
            or project.bbox_lon_max is None or project.bbox_lat_max is None:
        raise HTTPException(
            status_code=400,
            detail="Projeto sem bounding box definida. Edite o projeto e defina o bbox primeiro.",
        )

    bbox = (
        float(project.bbox_lon_min), float(project.bbox_lat_min),
        float(project.bbox_lon_max), float(project.bbox_lat_max),
    )
    try:
        result = await asyncio.to_thread(render_modern_map, project_id, bbox)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("render_modern failed for %s", project_id)
        raise HTTPException(status_code=500, detail=f"Falha ao renderizar: {exc}")

    return {
        "project_id": project_id,
        "map_file": result["map"].name,
        "colors_file": result["colors"].name,
    }


@router.get("/{project_id}/preview/{filename}")
async def get_preview(project_id: str, filename: str) -> Response:
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
    # Read into memory instead of streaming via FileResponse: this releases
    # the file handle as soon as the bytes are loaded, so concurrent edit
    # endpoints (move_capital / merge / reshape) can write to the file
    # without colliding with an in-flight stream. On Windows this is
    # mandatory — POSIX-style file replace fails with PermissionError if
    # any handle is still open. The previous FileResponse approach kept
    # the handle open for the whole streaming lifetime, blocking writes.
    # (UAT 2026-04-26 Windows file-lock + ERR_CONTENT_LENGTH_MISMATCH bugs.)
    payload = target.read_bytes()
    # no-cache forces the browser to revalidate every request. Edit endpoints
    # rewrite these files in place but the ?v=updated_at cache-buster is not
    # bumped on every edit — without this header the browser serves a stale
    # response and the canvas appears frozen despite TanStack refetching.
    return Response(
        content=payload,
        media_type=media_type,
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )
