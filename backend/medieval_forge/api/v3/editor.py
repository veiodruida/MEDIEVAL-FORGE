"""Phase 08 Plan 06a — POST /editor/validate batch endpoint.

POST /api/v3/projects/{project_id}/editor/validate
  Accepts a batch of polygon coordinates, returns per-polygon validation result.
  Read-only: never persists state. Validation logic lives in services/pipeline/topology.py.

Security mitigations (threat model T-08-06a-01..03):
  T-08-06a-01: Validate endpoint is read-only; /editor/apply (future plan) re-runs validate
               server-side and never trusts client "already validated" claim.
  T-08-06a-02: Field(..., max_length=100) caps polygons per batch (DoS guard).
  T-08-06a-03: Pydantic body parse + Polygon constructor coercion; degenerate coords
               (<3 points) returned as SELF_INTERSECT without raising 500.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from shapely.geometry import Polygon

from ...services.paths import is_valid_uuid
from ...services.pipeline.topology import validate_edit

router = APIRouter(prefix="/v3/projects", tags=["v3-editor"])


# ---------------------------------------------------------------------------
# Request / response models (ASVS V5 input validation)
# ---------------------------------------------------------------------------

class PolygonValidationRequest(BaseModel):
    """A single polygon to validate, plus the IDs of its expected neighbours."""
    polygon_id: str = Field(..., min_length=1, max_length=255)
    coords: list[tuple[float, float]]  # (lon, lat) ring — no closing duplicate
    neighbour_ids: list[str] = []

    model_config = {"extra": "forbid"}


class ValidateBatchBody(BaseModel):
    """Batch of polygons to validate. max_length=100 caps DoS (T-08-06a-02)."""
    polygons: list[PolygonValidationRequest] = Field(..., max_length=100)
    # Lookup map: neighbour_id → coords; only needed entries required.
    neighbour_lookup: dict[str, list[tuple[float, float]]] = {}

    model_config = {"extra": "forbid"}


class ValidateResult(BaseModel):
    """Per-polygon validation result."""
    polygon_id: str
    valid: bool
    code: str | None = None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/{project_id}/editor/validate")
async def validate_batch(
    project_id: str,
    body: ValidateBatchBody,
) -> list[ValidateResult]:
    """RESEARCH Open Q5: batch endpoint — marquee delete of N polygons = 1 request.

    Validates each polygon against Shapely topology rules and (optionally)
    checks that expected neighbours are still adjacent after the edit.

    Returns results in the same order as the request polygons list.
    """
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a valid UUID")

    results: list[ValidateResult] = []
    for req in body.polygons:
        # Degenerate polygon: fewer than 3 coordinates cannot form a valid polygon.
        if len(req.coords) < 3:
            results.append(
                ValidateResult(
                    polygon_id=req.polygon_id,
                    valid=False,
                    code="SELF_INTERSECT",
                )
            )
            continue

        target = Polygon(req.coords)

        # Resolve neighbour polygons from lookup — silently skip unknown IDs
        # (client may send stale neighbour_ids after a delete).
        neighbours = [
            Polygon(body.neighbour_lookup[nid])
            for nid in req.neighbour_ids
            if nid in body.neighbour_lookup
        ]

        valid, code = validate_edit(target, neighbours)
        results.append(ValidateResult(polygon_id=req.polygon_id, valid=valid, code=code))

    return results


__all__ = ["router"]
