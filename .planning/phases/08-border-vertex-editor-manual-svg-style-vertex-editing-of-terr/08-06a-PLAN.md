---
phase: 08
plan: 06a
type: execute
wave: 5
depends_on: [08-05]
autonomous: true
requirements: [EDIT-VERTEX-01, EDIT-VERTEX-02, EDIT-VERTEX-03, EDIT-VERTEX-04]
files_modified:
  - backend/medieval_forge/services/pipeline/topology.py
  - backend/medieval_forge/api/v3/editor.py
  - backend/medieval_forge/main.py
  - frontend/src/components/canvas/VertexEditLayer.tsx
  - frontend/src/components/editor/VertexCapBadge.tsx
  - frontend/src/components/editor/__tests__/VertexCapBadge.test.tsx
  - backend/tests/unit/test_manual_edit_simplify.py
  - backend/tests/integration/test_editor_validate_endpoint.py

must_haves:
  truths:
    - "Vertex move/add/delete are wired from VertexEditLayer to useEditorStore"
    - "Add-vertex disabled when polygon has 1000 vertices (D-06)"
    - "Warning badge color=\"amber\" at 500 vertices; red at 1000"
    - "Multi-select delete (marquee/Shift-click + Del) is one undoable op (D-29)"
    - "Douglas-Peucker simplify uses shapely.simplify(preserve_topology=True) and a popover with tolerance slider 0.00001–0.01 step 0.00001"
    - "Backend POST /api/v3/projects/{pid}/editor/validate accepts batch of polygons, returns per-polygon valid/code"
    - "Only barony-tier polygons editable (D-03) — frontend rejects edit attempts on condado/duchy/kingdom"
  artifacts:
    - path: "backend/medieval_forge/services/pipeline/topology.py"
      provides: "validate_edit + douglas_peucker_simplify"
      contains: "is_valid\\|simplify"
    - path: "backend/medieval_forge/api/v3/editor.py"
      provides: "POST /editor/validate batch endpoint"
      min_lines: 40
  key_links:
    - from: "VertexEditLayer onDragEnd"
      to: "POST /editor/validate then useEditorStore.moveVertex on valid"
      via: "topology.py via API"
      pattern: "editor/validate"
---

<objective>
Wave 5 vertex ops part A: vertex move + add + delete + simplify. Wires Wave-4 VertexEditLayer scaffold to actual ops in useEditorStore + backend topology endpoint. Topology BLOCK rules (TOPO-01) and snap/shared-vertex (TOPO-03/04) land in 08-06b — this plan handles the per-vertex ops + cap badges + simplify.

Per D-03: barony-tier only. Per D-06: hard cap 1000 vertices, warning at 500. Per D-01: simplify uses `shapely.simplify(preserve_topology=True)` — RESEARCH §Don't Hand-Roll item #4.

Purpose: deliver EDIT-VERTEX-01..04 at functional level; 08-06b adds topology blocking + snap; 08-07 adds polygon ops.
Output: backend topology helper + editor endpoint + frontend wiring + vertex cap badge.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/REQUIREMENTS.md
@.planning/phases/08-.../08-CONTEXT.md
@.planning/phases/08-.../08-RESEARCH.md §Code Examples (Shapely topology validate, simplify) + §"Don't Hand-Roll"
@.planning/phases/08-.../08-UI-SPEC.md §Error/Warning States + §Notes #9 (simplify popover)
@backend/medieval_forge/services/pipeline/voronoi.py
@frontend/src/components/canvas/VertexEditLayer.tsx
@frontend/src/stores/useEditorStore.ts

<interfaces>
shapely 2.0 API (verified):
  Polygon(coords).is_valid          # bool
  Polygon(coords).simplify(tol, preserve_topology=True) → Polygon
  Polygon(coords).disjoint(other)   # bool (gap check)
  Polygon(coords).touches(other)    # bool (adjacency)

D-22 high-water-mark for new vertex IDs:
  Use UUID for vertex ID (client-generated via crypto.randomUUID()).
  Backend doesn't need to track vertex IDs uniqueness — only barony original_idx.

Cap badge color logic:
  count < 500: no badge
  500 <= count < 1000: amber "N vértices — simplificar recomendado"
  count == 1000: red "Limite de 1000 vértices atingido"
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Backend topology.py + POST /editor/validate endpoint + simplify test</name>
  <files>backend/medieval_forge/services/pipeline/topology.py, backend/medieval_forge/api/v3/editor.py, backend/medieval_forge/main.py, backend/tests/unit/test_manual_edit_simplify.py, backend/tests/integration/test_editor_validate_endpoint.py</files>
  <read_first>
    - .planning/phases/08-.../08-RESEARCH.md §Code Examples (validate_edit) + §Pitfall 4 (batch endpoint)
    - backend/medieval_forge/api/v3/render.py (router/body pattern for v3 endpoints)
    - Wave 0 stubs: test_manual_edit_simplify.py, test_editor_validate_endpoint.py
  </read_first>
  <behavior>
    - Test: validate_edit(simple square, []) returns (True, None)
    - Test: validate_edit(figure-8 self-intersect, []) returns (False, 'SELF_INTERSECT')
    - Test: validate_edit(disjoint from neighbour, [neighbour]) returns (False, 'NEIGHBOUR_GAP')
    - Test: douglas_peucker_simplify(square_with_extra_vertex, tolerance=0.001) reduces vertex count, preserve_topology=True
    - Test: POST /editor/validate {"polygons": [...]} returns [{valid, code}, ...] batch
    - Test: invalid POST body rejected via pydantic
  </behavior>
  <action>
**Step 1 — `topology.py`:**
```python
"""Phase 08 D-26 + D-01: topology validation + Douglas-Peucker simplify."""
from __future__ import annotations
from typing import Iterable
from shapely.geometry import Polygon


def validate_edit(target: Polygon, neighbours: list[Polygon]) -> tuple[bool, str | None]:
    """D-26: returns (valid, error_code).

    Blocking errors:
      - target invalid (self-intersection): 'SELF_INTERSECT'
      - target disjoint from a previously-touching neighbour: 'NEIGHBOUR_GAP'
    """
    if not target.is_valid:
        return False, "SELF_INTERSECT"
    for n in neighbours:
        if target.disjoint(n):
            return False, "NEIGHBOUR_GAP"
    return True, None


def douglas_peucker_simplify(target: Polygon, tolerance: float) -> Polygon:
    """D-01: preserve_topology=True is non-negotiable (RESEARCH §Don't Hand-Roll #4)."""
    if tolerance <= 0 or tolerance > 0.1:
        raise ValueError("tolerance must be in (0, 0.1]")
    return target.simplify(tolerance, preserve_topology=True)
```

**Step 2 — `api/v3/editor.py`:**
```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from shapely.geometry import Polygon
from ..services.pipeline.topology import validate_edit

router = APIRouter(prefix="/v3/projects/{project_id}/editor", tags=["v3-editor"])


class PolygonValidationRequest(BaseModel):
    polygon_id: str
    coords: list[tuple[float, float]]  # (lon, lat) ring, no closing duplicate
    neighbour_ids: list[str] = []


class ValidateBatchBody(BaseModel):
    polygons: list[PolygonValidationRequest] = Field(..., max_length=100)
    neighbour_lookup: dict[str, list[tuple[float, float]]] = {}


class ValidateResult(BaseModel):
    polygon_id: str
    valid: bool
    code: str | None = None


@router.post("/validate")
async def validate_batch(project_id: str, body: ValidateBatchBody) -> list[ValidateResult]:
    """RESEARCH Open Q5: batch endpoint — marquee delete of N vertices = 1 request."""
    results: list[ValidateResult] = []
    for req in body.polygons:
        if len(req.coords) < 3:
            results.append(ValidateResult(polygon_id=req.polygon_id, valid=False,
                                          code="SELF_INTERSECT"))
            continue
        target = Polygon(req.coords)
        neighbours = [Polygon(body.neighbour_lookup[nid])
                      for nid in req.neighbour_ids if nid in body.neighbour_lookup]
        valid, code = validate_edit(target, neighbours)
        results.append(ValidateResult(polygon_id=req.polygon_id, valid=valid, code=code))
    return results
```

**Step 3 — `main.py`:** Mount `editor.router` with prefix=`/api` next to other v3 routers.

**Step 4 — fill both tests.**
  </action>
  <verify>
    <automated>cd backend && python -m pytest tests/unit/test_manual_edit_simplify.py tests/integration/test_editor_validate_endpoint.py -v -x</automated>
  </verify>
  <acceptance_criteria>
    - All tests pass
    - `grep -c "preserve_topology=True" backend/medieval_forge/services/pipeline/topology.py` returns 1
    - `grep -c "editor.router" backend/medieval_forge/main.py` returns 1
    - POST /api/v3/projects/{uuid}/editor/validate returns batch response
  </acceptance_criteria>
  <done>Backend topology + editor endpoint live.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: VertexEditLayer wires move/add/delete + VertexCapBadge component</name>
  <files>frontend/src/components/canvas/VertexEditLayer.tsx, frontend/src/components/editor/VertexCapBadge.tsx, frontend/src/components/editor/__tests__/VertexCapBadge.test.tsx</files>
  <read_first>
    - frontend/src/components/canvas/VertexEditLayer.tsx (from plan 08-05)
    - frontend/src/stores/useEditorStore.ts (move/add/delete actions exist)
    - .planning/phases/08-.../08-UI-SPEC.md §Error/Warning States (cap badge copy)
    - Wave 0 stub: VertexCapBadge.test.tsx
  </read_first>
  <behavior>
    - Test: VertexCapBadge with count=499 renders nothing
    - Test: count=500 renders amber Badge with text "500 vértices — simplificar recomendado"
    - Test: count=1000 renders red Badge with text "Limite de 1000 vértices atingido"
    - Test: VertexEditLayer onDragEnd calls POST /editor/validate via fetch; on valid commits moveVertex; on invalid logs (08-06b adds visual rollback)
    - Test: clicking on edge (Add tool) appends new vertex via addVertex; disabled when count==1000
    - Test: pressing Del with selectedVertexIds.length > 0 calls deleteVertices (one op)
  </behavior>
  <action>
**Step 1 — `VertexCapBadge.tsx`:**
```tsx
import { Badge } from '@radix-ui/themes';

export const VertexCapBadge: React.FC<{count:number; max:number}> = ({count, max}) => {
  if (count >= max) {
    return <Badge color="red" variant="soft">Limite de {max} vértices atingido</Badge>;
  }
  if (count >= max / 2) {
    return <Badge color="amber" variant="soft">{count} vértices — simplificar recomendado</Badge>;
  }
  return null;
};
```

**Step 2 — `VertexEditLayer.tsx`:** Extend with action wiring:
- onDragEnd: build polygon coords from current vertices, POST to /api/v3/projects/{pid}/editor/validate, on valid call `useEditorStore.getState().moveVertex(id, lat, lon)`; on invalid revert preview state (visual feedback added in 08-06b).
- For Add tool: onClick on edge → compute insertion lat/lon → `addVertex(crypto.randomUUID(), lat, lon)`.
- For Delete tool / Del key: collect selectedVertexIds → `deleteVertices(ids)`.
- Disable add when polygon vertex count >= 1000.
- All barony-only enforcement: read territory tier from prop; ignore events on non-barony.

**Step 3 — `VertexCapBadge.test.tsx`:** Remove skip; implement 3 tests.
  </action>
  <verify>
    <automated>cd frontend && npx vitest run src/components/editor/__tests__/VertexCapBadge.test.tsx src/components/canvas/__tests__/VertexEditLayer.test.tsx && npx tsc --noEmit</automated>
  </verify>
  <acceptance_criteria>
    - All tests pass
    - `grep -c "1000" frontend/src/components/editor/VertexCapBadge.tsx` returns 1+
    - tsc clean
  </acceptance_criteria>
  <done>Vertex move/add/delete wired; cap badge live.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Browser → POST /editor/validate | Polygon coords from client |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-08-06a-01 | Tampering | Topology bypass via direct API | mitigate | RESEARCH §Pattern: /editor/apply (future plan) re-runs validate server-side; never trusts "client said valid". Validate endpoint is read-only — accepts coords, returns valid/code only. |
| T-08-06a-02 | DoS | Huge polygon list in /validate body | mitigate | `Field(..., max_length=100)` caps polygons per batch. |
| T-08-06a-03 | V5 Input Validation | malformed coords | mitigate | pydantic body parse; Polygon constructor raises on invalid → return code SELF_INTERSECT. |
</threat_model>

<verification>
- Backend topology + endpoint
- Frontend wires move/add/delete to store
- Cap badge active
- 6+6 = 12 tests pass
</verification>

<success_criteria>
Vertex ops functional; ready for 08-06b topology blocking + snap.
</success_criteria>

<output>
After completion, create `.planning/phases/08-.../08-06a-SUMMARY.md`.
</output>
