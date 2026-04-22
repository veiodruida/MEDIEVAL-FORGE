---
phase: 260422-m1f-fix-multipolygon-territories-rendering-a
plan: "01"
subsystem: frontend/canvas
tags: [multipolygon, rendering, konva, territory-layer, interaction-layer]
dependency_graph:
  requires: []
  provides: [QUICK-MULTIPOLY-01]
  affects: [frontend/src/hooks/useCanvasArtifacts.ts, frontend/src/components/canvas/TerritoryLayer.tsx, frontend/src/components/canvas/InteractionLayer.tsx]
tech_stack:
  added: []
  patterns: [expand-multipolygon-to-render-entries, composite-index-key, filter-for-multi-match]
key_files:
  created: []
  modified:
    - frontend/src/hooks/useCanvasArtifacts.ts
    - frontend/src/components/canvas/TerritoryLayer.tsx
    - frontend/src/components/canvas/InteractionLayer.tsx
decisions:
  - "Expand MultiPolygon at the select() boundary (useCanvasArtifacts) so all consumers receive a flat TerritoryRender[] — no consumer change needed to 'understand' MultiPolygon"
  - "Composite key ${id}-${index} chosen over UUID generation to keep keys stable across re-renders (same order every time from GeoJSON)"
  - "firstOuterRing helper preserved unchanged — still used by baronies query select"
metrics:
  duration: "~10 minutes"
  completed: "2026-04-22"
  tasks: 3
  files_modified: 3
---

# Quick Task 260422-m1f: Fix MultiPolygon Territories Rendering

**One-liner:** Expanded MultiPolygon features into one TerritoryRender per outer ring in useCanvasArtifacts, then used composite `${id}-${i}` keys in TerritoryLayer and filter+map in InteractionLayer so all polygon rings of territories like alicante, mallorca, gijon render filled and selectable.

## Problem

The `select` function in `useCanvasArtifacts.ts` called `firstOuterRing()` — which for a MultiPolygon returns only `coordinates[0][0]`, silently dropping all remaining polygons. Affected territories (pravia, gijon, tui, coimbra, alicante, mallorca) had their secondary polygons appear as white background with no hit area.

## Changes Made

### Task 1: useCanvasArtifacts.ts — expand MultiPolygon into multiple TerritoryRender entries

**Before:**
```ts
select: (raw: FC<CondadoFeature>): TerritoryRender[] => {
  if (!projection) return []
  return raw.features.map((f) => ({
    id: f.properties.id,
    name: f.properties.name,
    points: geoRingToKonvaPoints(firstOuterRing(f.geometry), projection),
    neighbors: f.properties.neighbors,
  }))
},
```

**After:**
```ts
select: (raw: FC<CondadoFeature>): TerritoryRender[] => {
  if (!projection) return []
  const result: TerritoryRender[] = []
  for (const f of raw.features) {
    const rings: [number, number][][] =
      f.geometry.type === 'Polygon'
        ? [f.geometry.coordinates[0]]
        : f.geometry.coordinates.map((poly) => poly[0])
    for (const ring of rings) {
      result.push({
        id: f.properties.id,
        name: f.properties.name,
        points: geoRingToKonvaPoints(ring, projection),
        neighbors: f.properties.neighbors,
      })
    }
  }
  return result
},
```

Commit: `baa3d06`

### Task 2: TerritoryLayer.tsx — composite index-based key

**Before:**
```tsx
{territories.map((t) => (
  <TerritoryPolygon
    key={t.id}
```

**After:**
```tsx
{territories.map((t, i) => (
  <TerritoryPolygon
    key={`${t.id}-${i}`}
```

Commit: `dab3271`

### Task 3: InteractionLayer.tsx — filter+map to outline all polygons

**Before:**
```tsx
const selected = selectedTerritoryId
  ? territories.find((t) => t.id === selectedTerritoryId)
  : null

return (
  <Layer listening={false}>
    {selected && (
      <Line points={selected.points} closed stroke="#f0c040" strokeWidth={3} listening={false} />
    )}
  </Layer>
)
```

**After:**
```tsx
const selectedPolygons = selectedTerritoryId
  ? territories.filter((t) => t.id === selectedTerritoryId)
  : []

return (
  <Layer listening={false}>
    {selectedPolygons.map((t, i) => (
      <Line key={`${t.id}-${i}`} points={t.points} closed stroke="#f0c040" strokeWidth={3} listening={false} />
    ))}
  </Layer>
)
```

Commit: `d96c9a4`

## Build Output

```
vite v6.4.2 building for production...
✓ 452 modules transformed.
✓ built in 1.88s
```

TypeScript (`tsc -b`) and Vite build both pass with no errors. The large chunk warning (815 kB) is pre-existing and unrelated to this change.

## Verification

- `npx tsc --noEmit` — passed (no output = no errors)
- `npm run build` — passed, dist regenerated in `backend/medieval_forge/static/`
- Manual smoke test: pending (requires running backend with an Iberia project containing the affected territories)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check

| Claim | Result |
|-------|--------|
| useCanvasArtifacts.ts contains `f.geometry.coordinates.map` | FOUND |
| TerritoryLayer.tsx contains `${t.id}-${i}` | FOUND |
| InteractionLayer.tsx contains `territories.filter` | FOUND |
| firstOuterRing still present in useCanvasArtifacts.ts | FOUND |
| Commit baa3d06 exists | FOUND |
| Commit dab3271 exists | FOUND |
| Commit d96c9a4 exists | FOUND |

## Self-Check: PASSED
