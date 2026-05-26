---
phase: 08
plan: 06b
type: execute
wave: 6
depends_on: [08-06a]
autonomous: true
requirements: [TOPO-01, TOPO-02, TOPO-03, TOPO-04]
files_modified:
  - frontend/src/lib/snap.ts
  - frontend/src/lib/sharedVertex.ts
  - frontend/src/lib/__tests__/snap.test.ts
  - frontend/src/lib/__tests__/sharedVertex.test.ts
  - frontend/src/components/canvas/VertexEditLayer.tsx
  - backend/tests/unit/test_topology_validate.py
  - backend/tests/unit/test_shared_vertex_coupling.py

must_haves:
  truths:
    - "snap.ts: snapToNeighbour(cursor, candidates, stageScale) returns nearest within 5/scale world units; respects Alt-disable"
    - "Snap target indicator: yellow circle #eab308 radius 8 stroke 2 (D-28)"
    - "sharedVertex.ts: buildSharedVertexIndex(allBaronies, tolerance) returns Map<vertexId, baronyIds[]>"
    - "moveVertex on a shared vertex updates all coupled baronies in a single store mutation (D-30)"
    - "Shared edge hover highlights purple #a855f7 stroke 2; endpoint vertices enlarge to radius 7 (D-31)"
    - "Self-intersect: polygon border + fill turn #ef4444 during invalid drag; snap-back on mouseup (D-26)"
    - "Duplicate vertex (≤1e-6) + sliver polygon (<0.001° area) → amber Badge in inspector (D-27)"
    - "Backend test_shared_vertex_coupling and test_topology_validate both green with explicit numeric fixtures"
  artifacts:
    - path: "frontend/src/lib/snap.ts"
      provides: "scale-aware snap + Alt-disable"
      contains: "stageScale"
    - path: "frontend/src/lib/sharedVertex.ts"
      provides: "shared-vertex index + couple-mover"
      contains: "buildSharedVertexIndex"
  key_links:
    - from: "VertexEditLayer onDragMove"
      to: "snap.ts + sharedVertex.ts"
      via: "compute snap target each frame; on shared vertex, move all coupled baronies' coords in lockstep"
      pattern: "snapToNeighbour\\|sharedVertexIndex"
---

<objective>
Wave 6 vertex ops part B: topology block (TOPO-01) + warn badges (TOPO-02) + snap (TOPO-03) + shared-vertex coupling (TOPO-04). Builds on 08-06a's editor/validate endpoint to make invalid drags visually rejected, and on Phase 04 ProjectionContext for screen↔world scaling (RESEARCH Pitfall 7).

Per D-30: shared-vertex coupling is the default and only behaviour — no escape hatch.
Per D-28: snap is auto; Alt held → disabled for current drag.

Output: 2 frontend lib modules + VertexEditLayer extension + 2 backend tests filled (already covered partially in 08-06a but require shared-vertex coupling tests).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/REQUIREMENTS.md
@.planning/phases/08-.../08-RESEARCH.md §Pitfall 7 (scale-aware snap) + §Pattern 5 + §Don't Hand-Roll (scipy KDTree, shapely STRtree)
@.planning/phases/08-.../08-UI-SPEC.md §Konva colors + §Shared edge hover
@frontend/src/components/canvas/VertexEditLayer.tsx
@frontend/src/lib/projection.ts
@backend/medieval_forge/services/pipeline/topology.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: snap.ts (scale-aware) + sharedVertex.ts (KDTree-style index)</name>
  <files>frontend/src/lib/snap.ts, frontend/src/lib/sharedVertex.ts, frontend/src/lib/__tests__/snap.test.ts, frontend/src/lib/__tests__/sharedVertex.test.ts</files>
  <read_first>
    - frontend/src/lib/projection.ts (world↔screen conversion)
    - .planning/phases/08-.../08-RESEARCH.md §Pitfall 7 + §Don't Hand-Roll (scipy KDTree, shapely STRtree — JS port uses naive O(N) since N is small per visible viewport)
    - Wave 0 stubs for both test files
  </read_first>
  <behavior>
    - Test: snapToNeighbour(cursor=(0,0), candidates=[(0.0001,0.0001)], stageScale=1, altHeld=false) returns the candidate (within tolerance)
    - Test: snapToNeighbour with altHeld=true returns null (no snap)
    - Test: at stageScale=10, 5 screen-px = 0.5 world-px → snap tolerance shrinks correspondingly
    - Test: buildSharedVertexIndex([baronyA with vertex V1@(0,0), baronyB with vertex V2@(0.0000001,0.0000001)], tolerance=1e-6) returns Map where V1 and V2 are coupled
    - Test: getCoupledVertices(index, V1id) returns [V1id, V2id]
  </behavior>
  <action>
**Step 1 — `snap.ts`:**
```typescript
export interface SnapCandidate { id: string; lat: number; lon: number; }
export interface SnapResult { id: string; lat: number; lon: number; }

const SNAP_SCREEN_PX = 5;

export function snapToNeighbour(
  cursorWorld: {lat:number; lon:number},
  candidates: SnapCandidate[],
  stageScale: number,
  altHeld: boolean,
): SnapResult | null {
  if (altHeld) return null;
  // Pitfall 7: convert screen-px tolerance to world-units via current scale.
  // ProjectionContext: 1 world-unit ≈ N screen-px at scale=1.
  const worldTol = SNAP_SCREEN_PX / stageScale;
  let best: { c: SnapCandidate; d: number } | null = null;
  for (const c of candidates) {
    const dLat = c.lat - cursorWorld.lat;
    const dLon = c.lon - cursorWorld.lon;
    const d = Math.sqrt(dLat*dLat + dLon*dLon);
    if (d <= worldTol && (best === null || d < best.d)) {
      best = { c, d };
    }
  }
  return best ? { id: best.c.id, lat: best.c.lat, lon: best.c.lon } : null;
}
```

**Step 2 — `sharedVertex.ts`:**
```typescript
export interface VertexRef { vertexId: string; baronyId: string; lat: number; lon: number; }

export type SharedVertexIndex = Map<string, string[]>; // vertexId → coupled vertex IDs

export function buildSharedVertexIndex(
  vertices: VertexRef[],
  tolerance: number = 1e-6,
): SharedVertexIndex {
  const index: SharedVertexIndex = new Map();
  // Naive O(N²) — small N per editable region; refresh on edit-mode entry + mouseup.
  // Karpathy: don't optimise hypothetically (RESEARCH §Pitfall 8). Replace with KDTree
  // only when measured-slow.
  for (let i = 0; i < vertices.length; i++) {
    const coupled: string[] = [vertices[i].vertexId];
    for (let j = 0; j < vertices.length; j++) {
      if (i === j) continue;
      const dLat = vertices[i].lat - vertices[j].lat;
      const dLon = vertices[i].lon - vertices[j].lon;
      if (Math.sqrt(dLat*dLat + dLon*dLon) <= tolerance) {
        coupled.push(vertices[j].vertexId);
      }
    }
    if (coupled.length > 1) index.set(vertices[i].vertexId, coupled);
  }
  return index;
}

export function getCoupledVertices(index: SharedVertexIndex, vertexId: string): string[] {
  return index.get(vertexId) ?? [vertexId];
}
```

**Step 3 — fill both tests.** Use explicit numeric fixtures per user memory.
  </action>
  <verify>
    <automated>cd frontend && npx vitest run src/lib/__tests__/snap.test.ts src/lib/__tests__/sharedVertex.test.ts</automated>
  </verify>
  <acceptance_criteria>
    - All tests pass
    - `grep -c "stageScale" frontend/src/lib/snap.ts` returns 2+
    - `grep -c "1e-6\\|tolerance" frontend/src/lib/sharedVertex.ts` returns 2+
  </acceptance_criteria>
  <done>snap + shared-vertex lib + tests committed.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: VertexEditLayer integrates snap + sharedVertex + topology-block visuals + backend coupling test</name>
  <files>frontend/src/components/canvas/VertexEditLayer.tsx, backend/tests/unit/test_shared_vertex_coupling.py, backend/tests/unit/test_topology_validate.py</files>
  <read_first>
    - frontend/src/components/canvas/VertexEditLayer.tsx (from 08-06a)
    - frontend/src/lib/snap.ts + sharedVertex.ts (from Task 1)
    - .planning/phases/08-.../08-UI-SPEC.md §Vertex Edit Mode + §Shared edge hover
    - Wave 0 stubs for backend tests
  </read_first>
  <behavior>
    - Test (frontend integration in VertexEditLayer.test.tsx, extend existing): drag near neighbour vertex → snap target indicator renders #eab308 circle
    - Test: Alt-held during drag → no snap indicator
    - Test: invalid drag (mocked POST /editor/validate returning {valid:false}) → polygon turns #ef4444 fill 0.25 opacity; on mouseup vertex snaps back
    - Test: dragging a shared vertex updates ALL coupled vertices in a single setVerticesAndLog call (one undoable op)
    - Backend: test_topology_validate covers SELF_INTERSECT and NEIGHBOUR_GAP with descriptive names + explicit fixtures
    - Backend: test_shared_vertex_coupling.py — validate_edit called on coupled polygons returns valid only if ALL touch
  </behavior>
  <action>
**Step 1 — `VertexEditLayer.tsx`:**
- On edit-mode entry: build `sharedVertexIndex` from all visible baronies' vertices (via prop).
- On dragmove: call `snapToNeighbour(cursor, candidates, stageScale, altHeld)`; if hit, render `<Circle x={target.x} y={target.y} radius={8} stroke="#eab308" strokeWidth={2}/>` overlay.
- On dragend: if shared, gather coupled vertexIds → call `setVerticesAndLog(nextVertices, {op:'move', vertexIds:coupledIds, ...})` → single undoable op.
- Listen for Alt key state via window keydown/keyup.
- On invalid validate response: paint polygon fill/stroke #ef4444 (use Konva.Line with `stroke`+`fill`); after 600ms revert preview.
- Add D-27 warning emission: when polygon has duplicate vertex (≤1e-6) or area < 0.001°, store flag on editor store for inspector to show amber badge.

**Step 2 — backend tests:** Remove skip markers, implement with explicit numeric fixtures (square, figure-8, two adjacent triangles, two disjoint squares).
  </action>
  <verify>
    <automated>cd frontend && npx vitest run src/components/canvas/__tests__/VertexEditLayer.test.tsx && cd ../backend && python -m pytest tests/unit/test_topology_validate.py tests/unit/test_shared_vertex_coupling.py -v -x</automated>
  </verify>
  <acceptance_criteria>
    - All tests pass
    - `grep -c "snapToNeighbour\\|sharedVertex" frontend/src/components/canvas/VertexEditLayer.tsx` returns 2+
    - `grep -c "#eab308" frontend/src/components/canvas/VertexEditLayer.tsx` returns 1+
    - `grep -c "#ef4444" frontend/src/components/canvas/VertexEditLayer.tsx` returns 1+
  </acceptance_criteria>
  <done>Snap + coupling + topology visuals wired; backend coupling tests green.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Browser → backend topology validate | per-drag commit |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-08-06b-01 | Tampering | client bypasses topology check | mitigate | RESEARCH Pattern: backend re-validates on /editor/apply (plan 08-11 wires); validate endpoint here is advisory only. |
| T-08-06b-02 | DoS | Naive O(N²) sharedVertex on huge regions | accept | Karpathy: don't optimise hypothetically. Replace with KDTree only when measured slow (RESEARCH §Pitfall 8). |
</threat_model>

<verification>
- snap + sharedVertex lib green
- Topology visuals + backend tests green
- D-26..D-30 covered
</verification>

<success_criteria>
Topology blocking + snap + shared-vertex coupling delivered.
</success_criteria>

<output>
After completion, create `.planning/phases/08-.../08-06b-SUMMARY.md`.
</output>
