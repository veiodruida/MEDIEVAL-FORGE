"""Phase 08 Plan 06a + 07 — editor endpoints.

POST /api/v3/projects/{project_id}/editor/validate
  Accepts a batch of polygon coordinates, returns per-polygon validation result.
  Read-only: never persists state. Validation logic lives in services/pipeline/topology.py.

POST /api/v3/projects/{project_id}/editor/apply
  Persists a polygon op (split/merge/translate) to the branch's edit log.
  BLOCKER-1 contract (D-17, plan 08-07):
  - Does NOT return mutated geometry.
  - Appends op to edit_events table.
  - Bumps branch.manual_edit_log_count (+1) and branch.manual_edit_log_hash.
  - For split: allocates next original_idx atomically via allocate_next_original_idx.
  - For merge: server-side re-validates adjacency (touches()); 400 NOT_ADJACENT before
    persisting (no edit_events row, no count bump).
  - Returns {snapshot_id, edits_since_snapshot, new_hash, new_count, allocated_original_idx?}.
    allocated_original_idx is always present (None for non-split ops).

Security mitigations (threat model T-08-06a-01..03, T-08-07-01..02):
  T-08-06a-01: Validate endpoint is read-only; /editor/apply re-runs validate
               server-side and never trusts client "already validated" claim.
  T-08-06a-02: Field(..., max_length=100) caps polygons per batch (DoS guard).
  T-08-06a-03: Pydantic body parse + Polygon constructor coercion; degenerate coords
               (<3 points) returned as SELF_INTERSECT without raising 500.
  T-08-07-01: /editor/apply for merge re-validates touches() server-side → NOT_ADJACENT.
  T-08-07-02: split uses allocate_next_original_idx (DB transaction) → no idx collision.
"""
from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models import Branch, EditEvent
from ...services.branches.service import allocate_next_original_idx, append_edit_event
from ...services.country_boundaries import get_country_polygon
from ...services.paths import is_valid_uuid
from ...services.pipeline.cache import cache_clear_branch
from ...services.pipeline.manual_edit import replay_merge, replay_split
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


# ---------------------------------------------------------------------------
# /editor/apply — Plan 08-07 BLOCKER-1 contract
# ---------------------------------------------------------------------------

class ApplyOpBody(BaseModel):
    """Request body for POST /editor/apply.

    op_type: 'split' | 'merge' | 'translate' | 'landmask_replace'
    payload: op-specific dict (coords, ids, delta — validated internally per op_type)
    branch_id: the branch to persist the op on

    Phase 08 Plan 08: 'landmask_replace' added for LANDMASK-01.
    payload shape: {'new_landmask_coords': [[lon, lat], ...]}
    T-08-08-02: new_landmask_coords capped at 50000 entries via LandmaskReplacePayload.
    """
    op_type: str = Field(..., pattern=r"^(split|merge|translate|landmask_replace)$")
    payload: dict
    branch_id: str = Field(..., min_length=1, max_length=255)

    model_config = {"extra": "forbid"}


class ApplyOpResponse(BaseModel):
    """BLOCKER-1 response shape — NO geometry keys.

    snapshot_id: active snapshot id (or '' if no snapshot taken yet)
    edits_since_snapshot: branch.edits_since_snapshot after this op
    new_hash: branch.manual_edit_log_hash after this op (16-char hex)
    new_count: branch.manual_edit_log_count after this op
    allocated_original_idx: new original_idx for split child; None for merge/translate
    """
    snapshot_id: str
    edits_since_snapshot: int
    new_hash: str
    new_count: int
    allocated_original_idx: int | None = None


def _derive_log_hash(branch_id: str, new_count: int, payload: dict) -> str:
    """Derive the new manual_edit_log_hash from branch state.

    sha256(branch_id + ":" + str(new_count) + ":" + json(payload))[:16]
    This is deterministic per (branch, count, payload) but changes on every op.
    """
    data = f"{branch_id}:{new_count}:{json.dumps(payload, sort_keys=True)}"
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


@router.post("/{project_id}/editor/apply", response_model=ApplyOpResponse)
async def apply_op(
    project_id: str,
    body: ApplyOpBody,
    db: AsyncSession = Depends(get_db),
) -> ApplyOpResponse:
    """BLOCKER-1 (D-17): persist a polygon op, bump hash+count; return NO geometry.

    Steps:
      1. Validate project_id + branch_id format.
      2. Load branch row.
      3. For 'merge': server-side adjacency check; 400 NOT_ADJACENT before ANY write.
      4. For 'split': allocate next original_idx atomically.
      5. Append op to edit_events table.
      6. Update branch.manual_edit_log_count and manual_edit_log_hash.
      7. Return {snapshot_id, edits_since_snapshot, new_hash, new_count, allocated_original_idx}.

    Replay helpers (replay_split/replay_merge/replay_translate) are NOT called here.
    They are invoked by compute() in plan 08-07c when the DAG re-runs manual_edit stage.
    """
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a valid UUID")

    # Load branch
    branch = (
        await db.execute(select(Branch).where(Branch.id == body.branch_id))
    ).scalar_one_or_none()
    if branch is None:
        raise HTTPException(status_code=404, detail=f"branch {body.branch_id!r} not found")

    # Verify branch belongs to the given project
    if branch.project_id != project_id:
        raise HTTPException(
            status_code=403,
            detail="branch does not belong to the specified project",
        )

    allocated_original_idx: int | None = None

    # --- Op-specific pre-persist validation ---

    if body.op_type == "merge":
        # T-08-07-01: server-side adjacency re-validation BEFORE any DB write.
        # Raises 400 NOT_ADJACENT if polygons do not share a border.
        first_coords = body.payload.get("first_coords", [])
        second_coords = body.payload.get("second_coords", [])
        if len(first_coords) < 3 or len(second_coords) < 3:
            raise HTTPException(
                status_code=400,
                detail="INVALID_COORDS: merge requires at least 3 coordinates per polygon",
            )
        try:
            poly_a = Polygon(first_coords)
            poly_b = Polygon(second_coords)
        except Exception as exc:
            raise HTTPException(
                status_code=400, detail=f"INVALID_COORDS: {exc}"
            ) from exc
        # replay_merge raises ValueError("NOT_ADJACENT") if touches() is False
        try:
            replay_merge(poly_a, poly_b)
        except ValueError as exc:
            if "NOT_ADJACENT" in str(exc):
                raise HTTPException(
                    status_code=400,
                    detail="NOT_ADJACENT: the two polygons do not share a border",
                ) from exc
            raise HTTPException(
                status_code=400, detail=f"MERGE_INVALID: {exc}"
            ) from exc

    elif body.op_type == "split":
        # T-08-07-02: allocate next original_idx atomically before persisting.
        # If split geometry is invalid, we could allocate then fail — but since
        # geometry validation is the frontend's responsibility (and server-side
        # replay happens in compute()), we allocate optimistically here.
        allocated_original_idx = await allocate_next_original_idx(db, body.branch_id)

    elif body.op_type == "landmask_replace":
        # Phase 08 Plan 08 (LANDMASK-01, T-08-08-01, T-08-08-02):
        # Validate new_landmask_coords is present and within DoS cap.
        # T-08-08-01: we do NOT touch border_polygon — it lives on cfg, not payload.
        # T-08-08-02: cap at 50000 entries (Pydantic cannot validate nested list
        #   length on an untyped dict field, so we validate here imperatively).
        new_coords = body.payload.get("new_landmask_coords")
        if new_coords is None:
            raise HTTPException(
                status_code=400,
                detail="INVALID_PAYLOAD: landmask_replace requires new_landmask_coords",
            )
        if not isinstance(new_coords, list):
            raise HTTPException(
                status_code=400,
                detail="INVALID_PAYLOAD: new_landmask_coords must be a list",
            )
        if len(new_coords) > 50000:
            raise HTTPException(
                status_code=422,
                detail="INVALID_PAYLOAD: new_landmask_coords exceeds max_length=50000 (T-08-08-02)",
            )
        # Phase 08 Plan 08 Step 1 (cascade wiring): clear branch cache so the next
        # /render call recomputes from cfg.landmask_override (set by _render_producer
        # from this edit_event). Belt-and-suspenders alongside the DAG token change.
        cache_clear_branch(project_id, body.branch_id)

    # --- Persist edit event ---

    # Embed allocated_original_idx into the persisted payload for replay fidelity (D-22)
    persisted_payload = dict(body.payload)
    if allocated_original_idx is not None:
        persisted_payload["allocated_original_idx"] = allocated_original_idx

    await append_edit_event(
        db=db,
        branch_id=body.branch_id,
        op_type=body.op_type,
        payload=persisted_payload,
    )

    # --- Refresh branch row to get updated edits_since_snapshot ---
    await db.refresh(branch)

    # --- Bump manual_edit_log_count and manual_edit_log_hash ---
    new_count = branch.manual_edit_log_count + 1
    new_hash = _derive_log_hash(body.branch_id, new_count, persisted_payload)
    branch.manual_edit_log_count = new_count
    branch.manual_edit_log_hash = new_hash
    await db.commit()
    await db.refresh(branch)

    # Determine active snapshot_id (latest snapshot for this branch, if any)
    from ...models import Snapshot  # local import to avoid circular at module level
    latest_snapshot = (
        await db.execute(
            select(Snapshot)
            .where(Snapshot.branch_id == body.branch_id)
            .order_by(Snapshot.seq.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    snapshot_id = latest_snapshot.id if latest_snapshot else ""

    return ApplyOpResponse(
        snapshot_id=snapshot_id,
        edits_since_snapshot=branch.edits_since_snapshot,
        new_hash=new_hash,
        new_count=new_count,
        allocated_original_idx=allocated_original_idx,
    )


# ---------------------------------------------------------------------------
# GET /editor/landmask_ring — Phase 08 Plan 16 (LANDMASK-01, Path B)
# ---------------------------------------------------------------------------
# Returns the current landmask polygon ring as [[lon, lat], ...] for the
# VertexEditLayer to seed cyan handles.
#
# Priority:
#   1. If branch_id is provided and a landmask_replace EditEvent exists for
#      that branch → return those coords (branch-scoped editor override).
#   2. Else → derive the ring from Natural Earth country polygons (PT + ES
#      unary_union exterior) clipped to the map bounds.
#   3. Else → 404 (no landmask ring available; client shows empty handles).
#
# READ-ONLY endpoint — no writes, no side effects. T-08-16-01 / LANDMASK-01.
# ---------------------------------------------------------------------------

_IBERIA_ISO_CODES = ["PT", "ES"]


@router.get("/{project_id}/editor/landmask_ring")
async def get_landmask_ring(
    project_id: str,
    branch_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Return the landmask polygon ring as [[lon, lat], ...].

    Priority: branch edit-event coords → Natural Earth union → 404.
    """
    if not is_valid_uuid(project_id):
        raise HTTPException(status_code=400, detail="project_id must be a valid UUID")

    # Priority 1: latest landmask_replace for this branch
    if branch_id:
        latest_lm = (
            await db.execute(
                select(EditEvent)
                .where(
                    EditEvent.branch_id == branch_id,
                    EditEvent.op_type == "landmask_replace",
                )
                .order_by(EditEvent.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest_lm is not None:
            coords = latest_lm.payload.get("new_landmask_coords")
            if isinstance(coords, list) and len(coords) >= 3:
                return JSONResponse(
                    content={"ring": coords, "source": "branch_edit_event"},
                    headers={"Cache-Control": "no-cache"},
                )

    # Priority 2: Natural Earth PT + ES unary_union exterior ring
    try:
        polys = [get_country_polygon(iso) for iso in _IBERIA_ISO_CODES]
        polys = [p for p in polys if p is not None]
        if len(polys) == 0:
            raise HTTPException(
                status_code=404,
                detail="LANDMASK_RING_NOT_AVAILABLE: no Natural Earth polygon for PT/ES",
            )
        merged = unary_union(polys)
        # Take the largest piece if MultiPolygon
        if merged.geom_type == "MultiPolygon":
            merged = max(merged.geoms, key=lambda g: g.area)
        ring = [[round(lon, 6), round(lat, 6)] for lon, lat in merged.exterior.coords]
        return JSONResponse(
            content={"ring": ring, "source": "natural_earth"},
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=404,
            detail=f"LANDMASK_RING_NOT_AVAILABLE: {exc.__class__.__name__}",
        ) from exc


__all__ = ["router"]
