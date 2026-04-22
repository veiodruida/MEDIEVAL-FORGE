---
phase: quick-260422-ktb
plan: "01"
subsystem: frontend/canvas
tags: [canvas, research, coloring, inspector, zustand, konva]
dependency_graph:
  requires: [260422-h24, 260422-i0q]
  provides: [kingdom-colored-territories, research-inspector-badges]
  affects: [CanvasViewer, TerritoryLayer, InspectorSidebar, useResearchStore]
tech_stack:
  added: [kingdomColors.ts palette module]
  patterns: [zustand async action, useMemo merged colors, Radix Badge solid variant]
key_files:
  created:
    - frontend/src/lib/kingdomColors.ts
  modified:
    - frontend/src/api/research.ts
    - frontend/src/stores/useResearchStore.ts
    - frontend/src/components/canvas/CanvasViewer.tsx
    - frontend/src/components/canvas/InspectorSidebar.tsx
decisions:
  - "DecorationsLayer keeps condadoColorsQ.data (file-based) so capital rings and label halos remain readable regardless of research state"
  - "Research colors override file colors in mergedCondadoColors (spread order: {...fileColors, ...researchColors})"
  - "loadCachedForProject silently swallows transient errors — canvas falls back to file colors rather than surfacing an error"
metrics:
  duration_seconds: 183
  completed_date: "2026-04-22"
  tasks_completed: 6
  files_changed: 5
---

# Quick Task 260422-ktb: Apply Research Result to Canvas Color + Territory Inspector Summary

**One-liner:** Kingdom-colored territory fills via 20-color palette + Reino/Ducado inspector badges auto-loaded from cached manual research on project mount.

## Tasks Completed

| # | Name | Commit | Key Files |
|---|------|--------|-----------|
| 1 | Kingdom color palette module | 59b33c9 | `frontend/src/lib/kingdomColors.ts` (created) |
| 2 | fetchCachedManualResearch API helper | c2ef082 | `frontend/src/api/research.ts` |
| 3 | Extend useResearchStore with computeCondadoColors + loadCachedForProject | 81afce9 | `frontend/src/stores/useResearchStore.ts` |
| 4 | CanvasViewer auto-load + merged colors | 31e1ddc | `frontend/src/components/canvas/CanvasViewer.tsx` |
| 5 | InspectorSidebar Reino/Ducado badges | 00fc737 | `frontend/src/components/canvas/InspectorSidebar.tsx` |
| 6 | Rebuild frontend bundle | (no commit — static/ gitignored) | `backend/medieval_forge/static/` |

## What Was Built

**kingdomColors.ts** — 20 jewel-tone hex colors (`KINGDOM_PALETTE`) + `kingdomColorFor(kingdomId, indexInDict)` with index-based lookup and deterministic char-code hash fallback for unknown kingdoms.

**fetchCachedManualResearch** — standalone async helper (not a hook) calling `GET /api/projects/:id/research/cached?provider=manual&model=manual`. Returns `ResearchResult` on 200, `null` on 404, throws on other errors. Placed below `submitManualResearch` in `research.ts`.

**computeCondadoColors** — pure module-level export in the store file. Builds a `Map<kingdomId, index>` from `kingdomIds`, then maps each `condados_assignment` entry to its kingdom's palette color. Returns `{}` when `result` is null.

**loadCachedForProject** — async Zustand action. Calls `fetchCachedManualResearch`, sets `manualResult` to the result (including `null` for 404). Silently swallows transient errors so the canvas always has a usable fallback.

**CanvasViewer** — new `useEffect([projectId])` auto-loads cached research on mount and on project change. New `mergedCondadoColors` useMemo spreads `fileColors` then `researchColors` (research wins). `TerritoryLayer` receives `mergedCondadoColors`; `DecorationsLayer` intentionally keeps `condadoColorsQ.data` for stable capital/label rendering.

**InspectorSidebar** — `useResearchStore` hook added at top of component (before early returns for hook-order stability). `researchAssignment` lookup and name resolution computed after `condado` is found. Two solid Radix Badges (`variant="solid"`, amber Reino + blue Ducado) rendered between Group 1 (soft hierarchy badges) and Group 2 (path/area/centroid) when a research assignment exists for the selected territory.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced. All changes are pure frontend read paths consuming an existing cached endpoint.

## Self-Check: PASSED

- `frontend/src/lib/kingdomColors.ts` — FOUND
- `frontend/src/api/research.ts` — FOUND (fetchCachedManualResearch exported)
- `frontend/src/stores/useResearchStore.ts` — FOUND (computeCondadoColors + loadCachedForProject added)
- `frontend/src/components/canvas/CanvasViewer.tsx` — FOUND (mergedCondadoColors + useEffect)
- `frontend/src/components/canvas/InspectorSidebar.tsx` — FOUND (Reino/Ducado badges)
- Commit 59b33c9 — FOUND
- Commit c2ef082 — FOUND
- Commit 81afce9 — FOUND
- Commit 31e1ddc — FOUND
- Commit 00fc737 — FOUND
- `npm run build` — PASSED (exit 0, 452 modules, 2.25s)
