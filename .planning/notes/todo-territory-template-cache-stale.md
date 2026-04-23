---
type: todo
area: frontend-canvas
priority: medium
created: 2026-04-23
status: open
---

# Fix territory-template cache staleness after backend JSON edits

## Problem

When `backend/medieval_forge/services/territory_iberia.json` is edited
(e.g. adding a new condado like the 2026-04-23 Aveiro split), users who
click "2. Gerar mapa" on an already-open ProjectDetail page send the OLD
cached `territory_data` to the backend. The backend regenerates with the
stale payload → map looks identical.

Observed 2026-04-23: after Aveiro split, user clicked regenerate and saw
no change. Required hard-refresh (Ctrl+Shift+R) to pick up the new 93
condados.

## Root Cause

Two stacked caches block refetch:

1. **`frontend/src/api/client.ts:74-81`** — `useTerritoryTemplate` has
   `staleTime: Infinity`, so TanStack Query never refetches the template.
2. **`frontend/src/pages/ProjectDetail.tsx:63-68`** — even if the query
   refetches, the `templateLoaded` boolean gate prevents `territory`
   state from being re-synced from `templateData`:

   ```ts
   useEffect(() => {
     if (templateData && !templateLoaded) {
       setTerritory(templateData as unknown as TerritoryData)
       setTemplateLoaded(true)
     }
   }, [templateData, templateLoaded])
   ```

## Proposed Fix

**Option A (simplest):** change `staleTime: Infinity` → `staleTime: 0` and
invert the gate so `territory` re-syncs when `templateData` changes.
Downside: if TerritoryEditor allows user edits, they get clobbered.

**Option B (safer):** keep gate for editor mode, but add a "Reload
template" button in TerritoryEditor + `queryClient.invalidateQueries({
queryKey: ['territory-template', region] })` on click.

**Option C (gsd-quick):** also add a "territory_template_version" header
to the backend response (hash of the JSON file) and include it in the
queryKey so any JSON edit naturally busts the cache.

Recommend C — detects backend edits without requiring user action.

## References

- `backend/medieval_forge/api/projects.py:36-47` — territory-template route
- `frontend/src/api/client.ts:74-81` — useTerritoryTemplate
- `frontend/src/pages/ProjectDetail.tsx:56-68,328` — template load + generate
