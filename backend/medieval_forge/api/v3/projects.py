"""v3 POST /api/v3/projects endpoint (Plan 05-04).

POST /api/v3/projects  → 201 + {id, name, region_key}

Creates a new project with an explicit region_key that must match one of the
discovered YAML regions in data/regions/.

Security mitigations (T-05-04-01 through T-05-04-03):
  T-05-04-01: Pydantic Field(pattern=r"^[a-z0-9_]+$") rejects path-injection input;
              server-side set membership check rejects unknown region_key with 400.
  T-05-04-02: VARCHAR(64) NOT NULL in DB (enforced by Alembic migration 0004).
  T-05-04-03: 400 detail exposes only region keys (no filesystem paths).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models import Project

router = APIRouter(prefix="/v3/projects", tags=["v3-projects"])

# R-04 (review): permanent path-depth anchor — DO NOT change to parents[3].
# File depth: backend/medieval_forge/api/v3/projects.py
#              4         3            2   1  0
# parents[4] = repo root (parents[3] resolves to backend/ and breaks region
# discovery — the regression has happened before). Verified empirically.
_REGIONS_DIR = Path(__file__).resolve().parents[4] / "data" / "regions"


class V3ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    region_key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")


def _available_region_keys() -> set[str]:
    return {p.stem for p in _REGIONS_DIR.glob("*.yaml")}


# Maps curated region_key values to their Wikidata country_qid.
# Required so GET /api/projects/{id} returns a non-null country_qid that the
# frontend's ResearchDialog can use when submitting LLM research requests.
_REGION_KEY_COUNTRY_QID: dict[str, str] = {
    "iberia_868": "Q29,Q45",
    "france_1066": "Q142",
    "england_1216": "Q145,Q27",
}


@router.post("", status_code=201)
async def create_v3_project(
    payload: V3ProjectCreate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new v3 project with region_key enum validation.

    Full route: POST /api/v3/projects (main.py mounts with prefix=/api).

    Returns 400 if region_key is not a discovered YAML region.
    Returns 422 if region_key contains path-injection characters (pydantic regex).
    """
    available = _available_region_keys()
    if payload.region_key not in available:
        raise HTTPException(
            status_code=400,
            detail=f"region_key {payload.region_key!r} not in available regions: {sorted(available)}",
        )
    project = Project(
        name=payload.name,
        region_key=payload.region_key,
        country_qid=_REGION_KEY_COUNTRY_QID.get(payload.region_key),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return {"id": project.id, "name": project.name, "region_key": project.region_key}


__all__ = ["router"]
