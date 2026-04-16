"""PROJ-01..05: project CRUD endpoints.

T-PATH mitigation: every route that accepts a path-bound project_id
validates it via services.paths.is_valid_uuid before any DB or fs access.
"""
from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Project
from ..schemas import ProjectCreate, ProjectResponse, ProjectUpdate
from ..services.paths import ensure_project_dirs, is_valid_uuid, project_dir

import json as _json
from pathlib import Path as _Path

from ..services.countries import PRESETS

router = APIRouter(prefix="/projects", tags=["projects"])

_TERRITORY_TEMPLATES_DIR = _Path(__file__).parent.parent / "services"


@router.get("/presets")
async def list_presets() -> list[dict]:
    """Retorna presets de regiões/países com bounding box pré-definida."""
    return PRESETS


@router.get("/territory-template/{region}")
async def territory_template(region: str) -> dict:
    """Retorna dados de território de exemplo para uma região.

    Regiões disponíveis: iberia
    """
    allowed = {"iberia"}
    if region not in allowed:
        raise HTTPException(status_code=404, detail=f"Template '{region}' não encontrado. Disponíveis: {allowed}")
    path = _TERRITORY_TEMPLATES_DIR / f"territory_{region}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Ficheiro de template não encontrado")
    return _json.loads(path.read_text(encoding="utf-8"))


def _validate_project_id(project_id: str) -> None:
    if not is_valid_uuid(project_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_id must be a valid UUID",
        )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectResponse)
async def create_project(
    payload: ProjectCreate, db: AsyncSession = Depends(get_db)
) -> Project:
    project = Project(**payload.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    # D-07: per-project folder structure.
    ensure_project_dirs(project.id)
    return project


@router.get("", response_model=list[ProjectResponse])
async def list_projects(db: AsyncSession = Depends(get_db)) -> list[Project]:
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    return list(result.scalars().all())


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str, db: AsyncSession = Depends(get_db)
) -> Project:
    _validate_project_id(project_id)
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
) -> Project:
    _validate_project_id(project_id)
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    updates = payload.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(project, k, v)
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str, db: AsyncSession = Depends(get_db)
) -> None:
    _validate_project_id(project_id)
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    # Capture the project root BEFORE delete (path validation re-runs).
    proj_root = project_dir(project_id)
    await db.delete(project)
    await db.commit()
    shutil.rmtree(proj_root, ignore_errors=True)
