---
phase: quick-260422-ktb
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/src/lib/kingdomColors.ts
  - frontend/src/api/research.ts
  - frontend/src/stores/useResearchStore.ts
  - frontend/src/components/canvas/CanvasViewer.tsx
  - frontend/src/components/canvas/InspectorSidebar.tsx
  - backend/medieval_forge/static/
autonomous: true
requirements:
  - QUICK-260422-ktb
must_haves:
  truths:
    - "When a project is loaded on the canvas, any previously cached manual research result is auto-loaded into the research store without opening the dialog."
    - "Territories on the canvas are filled with the color of the kingdom they were assigned to in the research result (one distinct color per kingdom, shared across all condados of that kingdom)."
    - "When no research result exists, the canvas falls back to the existing file-based condado_colors.json palette (no regression)."
    - "Research-derived colors override the file-based colors when both exist."
    - "Selecting a territory that has a research assignment shows two extra Radix Badges in the InspectorSidebar: 'Reino: {kingdom_name}' and 'Ducado: {duchy_name}'."
    - "The frontend bundle served by the backend (backend/medieval_forge/static/) is rebuilt so the user sees the new behavior without a dev server."
  artifacts:
    - path: "frontend/src/lib/kingdomColors.ts"
      provides: "20-color kingdom palette + kingdomColorFor(kingdomId, indexInDict) lookup helper"
      exports: ["KINGDOM_PALETTE", "kingdomColorFor"]
    - path: "frontend/src/api/research.ts"
      provides: "fetchCachedManualResearch(projectId) helper — null on 404"
      exports: ["fetchCachedManualResearch"]
    - path: "frontend/src/stores/useResearchStore.ts"
      provides: "computeCondadoColors pure helper + loadCachedForProject async action"
      exports: ["computeCondadoColors", "useResearchStore"]
    - path: "frontend/src/components/canvas/CanvasViewer.tsx"
      provides: "projectId useEffect → loadCachedForProject + merged condado colors prop to TerritoryLayer"
    - path: "frontend/src/components/canvas/InspectorSidebar.tsx"
      provides: "Two additional Reino/Ducado badges below existing metadata when research assignment exists"
    - path: "backend/medieval_forge/static/"
      provides: "Rebuilt frontend bundle reflecting all of the above"
  key_links:
    - from: "frontend/src/components/canvas/CanvasViewer.tsx"
      to: "frontend/src/stores/useResearchStore.ts"
      via: "useEffect([projectId]) → loadCachedForProject(projectId)"
      pattern: "loadCachedForProject\\("
    - from: "frontend/src/components/canvas/CanvasViewer.tsx"
      to: "frontend/src/components/canvas/TerritoryLayer.tsx"
      via: "useMemo merge { ...fileColors, ...researchColors } passed as condadoColors prop"
      pattern: "condadoColors=\\{"
    - from: "frontend/src/stores/useResearchStore.ts"
      to: "frontend/src/api/research.ts"
      via: "loadCachedForProject calls fetchCachedManualResearch"
      pattern: "fetchCachedManualResearch\\("
    - from: "frontend/src/stores/useResearchStore.ts"
      to: "frontend/src/lib/kingdomColors.ts"
      via: "computeCondadoColors uses kingdomColorFor"
      pattern: "kingdomColorFor\\("
    - from: "frontend/src/components/canvas/InspectorSidebar.tsx"
      to: "frontend/src/stores/useResearchStore.ts"
      via: "useResearchStore selector reads manualResult"
      pattern: "useResearchStore\\(.*manualResult"
---

<objective>
Apply the manual research result to the canvas so Game Designers can SEE the
political hierarchy they just pasted: territories are colored per-kingdom, the
cached result auto-loads on project mount, and the inspector shows Reino/Ducado
badges for selected territories.

Purpose: Close the feedback loop between /gsd-research-phase (manual paste) and
the read-only canvas viewer — today the result is stored but invisible.
Output: Updated frontend with kingdom-colored territories, enriched inspector,
and a rebuilt static bundle served by the backend.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@./CLAUDE.md
@.planning/STATE.md
@frontend/src/stores/useResearchStore.ts
@frontend/src/api/research.ts
@frontend/src/components/canvas/CanvasViewer.tsx
@frontend/src/components/canvas/TerritoryLayer.tsx
@frontend/src/components/canvas/InspectorSidebar.tsx
@frontend/src/components/canvas/LegendCard.tsx
@frontend/src/components/research/ResearchDialog.tsx
@frontend/src/components/research/ManualResearchPanel.tsx
@backend/medieval_forge/api/research.py

<interfaces>
<!-- Contracts the executor needs. Extracted from the files above so no codebase scavenging is required. -->

From frontend/src/api/research.ts:
```typescript
export type ResearchResult = {
  kingdoms: Record<string, string>;                                          // kingdom_id -> kingdom_name
  duchies: Record<string, [string, string]>;                                 // duchy_id   -> [duchy_name, kingdom_id]
  condados_assignment: Array<{ condado_id: string; kingdom_id: string; duchy_id: string }>;
  baronies: Record<string, Array<{ name: string; lon: number; lat: number }>>;
};
```

Cached endpoint (from backend/medieval_forge/api/research.py — line 104-129):
```
GET /api/projects/{project_id}/research/cached?provider=manual&model=manual
  → 200: ResearchResult JSON
  → 404: when no cache row exists (expected happy path before any research was run)
```

From frontend/src/stores/useResearchStore.ts (current shape):
- manualResult: ResearchResult | null
- setManualResult: (result: ResearchResult | null) => void
- Plain `create<State>` — NO zundo temporal wrapper (ephemeral research UI state)

From frontend/src/components/canvas/TerritoryLayer.tsx:
- prop `condadoColors: Record<string, string>` — already used; we only change WHAT we pass.

From frontend/src/hooks/useCanvasArtifacts.ts:
- condadoColorsQ.data is already `Record<string, string>` loaded from
  `/api/projects/{id}/preview/condado_colors.json` sidecar. This is the
  "fileColors" base that research colors must override.

From frontend/src/components/canvas/InspectorSidebar.tsx:
- Existing Group 1 already renders amber "Kingdom: {name}" + blue "Duchy: {name}"
  badges from metadata.kingdoms / metadata.duchies (the generator-derived names,
  NOT research-derived). The spec below adds TWO NEW badges derived from
  manualResult — keep existing Group 1 untouched.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Kingdom color palette module</name>
  <files>frontend/src/lib/kingdomColors.ts</files>
  <action>
    Create a new file with:

    1. `export const KINGDOM_PALETTE: readonly string[]` — exactly 20 hex colors
       chosen to be visually distinct and saturated enough to read over the muted
       terrain base of the canvas. Favor jewel tones + distinct hues. Example
       seed (you may refine, must be 20 unique values, all `#rrggbb`):
         '#c0392b', '#2980b9', '#27ae60', '#8e44ad', '#f39c12',
         '#16a085', '#d35400', '#2c3e50', '#c2185b', '#00897b',
         '#7b1fa2', '#388e3c', '#f57c00', '#1976d2', '#5d4037',
         '#00695c', '#ad1457', '#283593', '#bf360c', '#4527a0'
       Do NOT reuse Radix accent tokens here — these fills bypass Tailwind/Radix
       and are set directly on Konva shape `fill` props.

    2. `export function kingdomColorFor(kingdomId: string, indexInDict: number): string`
       — index-based lookup with fallback cycling:
       - If `indexInDict` is a non-negative finite integer, return
         `KINGDOM_PALETTE[indexInDict % KINGDOM_PALETTE.length]`.
       - Otherwise (negative / NaN / undefined) fall back to a deterministic hash
         of `kingdomId` mod palette length so unknown kingdoms still get a stable
         color across renders. A simple sum-of-char-codes is sufficient.

    The `kingdomId` parameter is kept in the signature for the fallback path and
    future callers that lack index context; do not drop it. Export both symbols
    named — no default export.

    No tests required (pure lib, trivially inspectable). Keep file under ~40
    lines incl. palette.
  </action>
  <verify>
    <automated>cd frontend && npx tsc --noEmit</automated>
  </verify>
  <done>
    File exists, exports KINGDOM_PALETTE (length 20, all unique `#rrggbb`) and
    kingdomColorFor. `tsc --noEmit` passes.
  </done>
</task>

<task type="auto">
  <name>Task 2: fetchCachedManualResearch API helper</name>
  <files>frontend/src/api/research.ts</files>
  <action>
    In the existing file, BELOW the current `submitManualResearch` function,
    add a new exported async helper:

    ```ts
    /**
     * GET /api/projects/:id/research/cached?provider=manual&model=manual
     * Returns the cached manual research result, or null if no cache row exists (404).
     * Throws on other non-2xx responses so callers can surface transient errors.
     */
    export async function fetchCachedManualResearch(
      projectId: string,
    ): Promise<ResearchResult | null> {
      const res = await fetch(
        `/api/projects/${projectId}/research/cached?provider=manual&model=manual`,
      );
      if (res.status === 404) return null;
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(body.detail ?? `cached ${res.status}`);
      }
      return (await res.json()) as ResearchResult;
    }
    ```

    IMPORTANT: The backend returns the ResearchResult payload DIRECTLY (see
    api/research.py `get_cached_research` — `JSONResponse(content=cached)`),
    NOT wrapped in a `{ result: ... }` envelope. Do not unwrap.

    Do not touch `useCachedResultQuery`, `submitManualResearch`, or anything else.
  </action>
  <verify>
    <automated>cd frontend && npx tsc --noEmit</automated>
  </verify>
  <done>
    Function exported and type-checks clean. Returns ResearchResult on 200, null on 404, throws otherwise.
  </done>
</task>

<task type="auto">
  <name>Task 3: Extend useResearchStore with computeCondadoColors + loadCachedForProject</name>
  <files>frontend/src/stores/useResearchStore.ts</files>
  <action>
    Two additions to the existing file. DO NOT rewrite the file — only add.

    (a) Add a pure, module-level exported helper BEFORE `create<State>(...)`:

    ```ts
    import { kingdomColorFor } from "../lib/kingdomColors";

    /**
     * Map each condado_id in the research result to its kingdom's palette color.
     * `kingdomIds` is the canonical ordered list of kingdom IDs (typically
     * Object.keys(result.kingdoms)); each kingdom's index in that list selects
     * its color via kingdomColorFor. Returns {} when result is null.
     *
     * Pure — no store reads, no side effects. Safe to call inside useMemo.
     */
    export function computeCondadoColors(
      result: ResearchResult | null,
      kingdomIds: string[],
    ): Record<string, string> {
      if (!result) return {};
      const kingdomIndex = new Map<string, number>();
      kingdomIds.forEach((id, i) => kingdomIndex.set(id, i));
      const out: Record<string, string> = {};
      for (const a of result.condados_assignment) {
        const idx = kingdomIndex.get(a.kingdom_id);
        out[a.condado_id] = kingdomColorFor(a.kingdom_id, idx ?? -1);
      }
      return out;
    }
    ```

    (b) Extend the State type and the `create<State>` body with a new action:

    - Add to the `type State` declaration:
      `loadCachedForProject: (projectId: string) => Promise<void>;`

    - Add to the `create<State>((set) => ({ ... }))` body (near the existing
      manualResult/setManualResult pair):
      ```ts
      loadCachedForProject: async (projectId: string) => {
        try {
          const cached = await fetchCachedManualResearch(projectId);
          set({ manualResult: cached });
        } catch {
          // Transient errors are non-fatal for canvas auto-load; leave
          // whatever manualResult is currently in the store untouched.
          // (Intentionally swallow — the UI falls back to file colors.)
        }
      },
      ```

    - Add the import at the top of the file:
      `import { fetchCachedManualResearch } from "../api/research";`

    Keep the existing comment block about zundo temporal — it still applies.
    Do not change any other fields.
  </action>
  <verify>
    <automated>cd frontend && npx tsc --noEmit</automated>
  </verify>
  <done>
    `useResearchStore.getState().loadCachedForProject` is a function.
    `computeCondadoColors(null, [])` returns `{}`.
    `computeCondadoColors(result, Object.keys(result.kingdoms))` returns one entry per `condados_assignment` item.
    TypeScript passes.
  </done>
</task>

<task type="auto">
  <name>Task 4: CanvasViewer auto-load + merged colors</name>
  <files>frontend/src/components/canvas/CanvasViewer.tsx</files>
  <action>
    Minimal, surgical edits to the existing component.

    1. Add imports near the other store/store-hook imports at the top:
       ```ts
       import { useResearchStore, computeCondadoColors } from '../../stores/useResearchStore'
       ```

    2. Inside the `CanvasViewer` component, BEFORE the early-return block (i.e.
       alongside the other hook calls — NEVER after an early return; hook order
       must remain stable, same rule already documented in this file for
       viewportW/H), add:

       ```ts
       const loadCachedForProject = useResearchStore((s) => s.loadCachedForProject)
       const manualResult = useResearchStore((s) => s.manualResult)

       // Auto-load cached manual research whenever the project changes.
       useEffect(() => {
         loadCachedForProject(projectId)
       }, [projectId, loadCachedForProject])
       ```

    3. Compute merged colors with useMemo, placed near the other useMemo hooks:

       ```ts
       const mergedCondadoColors = useMemo(() => {
         const fileColors = condadoColorsQ.data ?? {}
         const researchColors = computeCondadoColors(
           manualResult,
           manualResult ? Object.keys(manualResult.kingdoms) : [],
         )
         // Research overrides file colors, per spec.
         return { ...fileColors, ...researchColors }
       }, [condadoColorsQ.data, manualResult])
       ```

    4. In the JSX, swap the `condadoColors` prop on `<TerritoryLayer>` from
       `condadoColorsQ.data` to `mergedCondadoColors`.
       Leave `<DecorationsLayer condadoColors={condadoColorsQ.data} ...>` as-is
       — capital rings and label halos should keep using the stable file palette
       so they read clearly regardless of research state (out of scope for this
       quick task).

    5. Do NOT change any early-return conditions, ResizeObserver code, fit logic,
       pan logic, wheel handlers, or click handlers.
  </action>
  <verify>
    <automated>cd frontend && npx tsc --noEmit</automated>
  </verify>
  <done>
    CanvasViewer compiles. Opening a project triggers loadCachedForProject(projectId) once per id change. TerritoryLayer receives mergedCondadoColors; when manualResult is null behavior is byte-identical to before.
  </done>
</task>

<task type="auto">
  <name>Task 5: InspectorSidebar Reino/Ducado badges from research</name>
  <files>frontend/src/components/canvas/InspectorSidebar.tsx</files>
  <action>
    Pure addition — do NOT touch any existing content (Group 1 hierarchy badges,
    Group 2 geometry, Group 3 capital, Group 4 neighbors). The existing amber
    "Kingdom: ..." / blue "Duchy: ..." badges are derived from the generator's
    metadata.kingdoms/duchies (political hierarchy from territory_data). The
    NEW badges below are derived from the LLM research result — they are
    conceptually distinct and may show different names.

    1. Add an import at the top, after existing imports:
       ```ts
       import { useResearchStore } from '../../stores/useResearchStore'
       ```

    2. Inside the territory-detail branch (the `return` after `if (!condado)`),
       subscribe to manualResult with a narrow selector:
       ```ts
       const manualResult = useResearchStore((s) => s.manualResult)
       ```
       Place this call at the TOP of the component function body alongside the
       existing `useUIStore` hooks — NOT inside a conditional — to keep hook
       order stable across null/detail branches.

    3. Compute the research-derived labels (also at top of function body,
       after the existing `const condado = ...` line — safe because it does
       not use hooks):
       ```ts
       const researchAssignment = selectedId && manualResult
         ? manualResult.condados_assignment.find((a) => a.condado_id === selectedId)
         : undefined
       const researchKingdomName = researchAssignment
         ? manualResult!.kingdoms[researchAssignment.kingdom_id] ?? researchAssignment.kingdom_id
         : undefined
       const researchDuchyName = researchAssignment
         ? manualResult!.duchies[researchAssignment.duchy_id]?.[0] ?? researchAssignment.duchy_id
         : undefined
       ```
       Note the duchy shape: `duchies[duchy_id] = [duchy_name, kingdom_id]` —
       so `[0]` is the name.

    4. In the territory-detail JSX, AFTER the existing Group 1 Flex with the
       four hierarchy badges and BEFORE the Group 2 `Box` with `{COPY.PATH_LABEL}`,
       insert:
       ```tsx
       {researchAssignment && (
         <Flex gap="2" wrap="wrap">
           <Badge color="amber" variant="solid">Reino: {researchKingdomName}</Badge>
           <Badge color="blue" variant="solid">Ducado: {researchDuchyName}</Badge>
         </Flex>
       )}
       ```
       Use `variant="solid"` so these badges read distinctly from the existing
       `variant="soft"` generator-derived badges. Color choice matches the spec
       ("amber" / "blue"). Per-kingdom palette swatch is OUT OF SCOPE for this
       quick task — Radix's amber is sufficient visual differentiation for the
       badge itself; the per-kingdom palette appears on the canvas fills.

    5. Leave the project-overview branch (`if (!condado)`) completely untouched.
  </action>
  <verify>
    <automated>cd frontend && npx tsc --noEmit</automated>
  </verify>
  <done>
    InspectorSidebar compiles. With no research: inspector looks identical to
    current behavior. With a research result: selecting a territory that is in
    `condados_assignment` shows exactly two extra solid badges between Group 1
    and Group 2: "Reino: {name}" (amber) and "Ducado: {name}" (blue).
  </done>
</task>

<task type="auto">
  <name>Task 6: Rebuild frontend bundle</name>
  <files>backend/medieval_forge/static/</files>
  <action>
    From the `frontend/` directory, run `npm run build`. This regenerates the
    static bundle that the backend's FastAPI StaticFiles mount serves so the
    user sees the new canvas coloring + inspector badges without running the
    dev server.

    If the build fails on type errors, fix them in-place (likely indicates a
    mistake in a prior task) and re-run. If it fails on lint/test regressions
    that are clearly unrelated to this quick task (e.g. pre-existing flakes),
    surface the output and stop — do NOT blanket-disable checks.

    Do not manually edit anything under `backend/medieval_forge/static/` — it is
    a build artifact and will be overwritten.
  </action>
  <verify>
    <automated>cd frontend && npm run build</automated>
  </verify>
  <done>
    `npm run build` exits 0. `backend/medieval_forge/static/` contains a fresh
    `index.html` and asset bundle reflecting all prior task changes.
  </done>
</task>

</tasks>

<verification>
End-to-end smoke (manual, user-driven — no automated E2E required for this quick task):

1. Start `medieval-forge start`, open an existing project that already has a
   cached manual research result.
2. EXPECT: territories are colored by kingdom immediately on load (no dialog
   interaction needed). Each kingdom has a distinct color shared across all its
   condados.
3. Click a territory that is in `condados_assignment`.
4. EXPECT: inspector shows TWO extra solid badges below the existing Group 1
   row: "Reino: {name}" (amber) and "Ducado: {name}" (blue). Existing soft
   badges remain untouched.
5. Open another project with NO cached research.
6. EXPECT: canvas falls back to the existing file-based condado_colors.json
   palette (pre-quick-task behavior). Inspector shows no extra badges.

Automated verification scope:
- `npx tsc --noEmit` in frontend passes after every task.
- `npm run build` in frontend passes at the end (Task 6).
</verification>

<success_criteria>
- [ ] `frontend/src/lib/kingdomColors.ts` exports KINGDOM_PALETTE (length 20) + kingdomColorFor
- [ ] `fetchCachedManualResearch` exported from `frontend/src/api/research.ts`; returns null on 404
- [ ] `computeCondadoColors` exported from `frontend/src/stores/useResearchStore.ts`; pure function
- [ ] `loadCachedForProject` action added to useResearchStore
- [ ] CanvasViewer calls `loadCachedForProject(projectId)` on mount/projectId change
- [ ] TerritoryLayer receives `mergedCondadoColors` (research overrides file)
- [ ] InspectorSidebar renders two extra Reino/Ducado solid badges when research assignment exists
- [ ] All existing InspectorSidebar groups (1-4) unchanged when no research present
- [ ] `frontend/ && npx tsc --noEmit` passes
- [ ] `frontend/ && npm run build` succeeds → `backend/medieval_forge/static/` refreshed
- [ ] LegendCard explicitly NOT modified (per skip/defer instruction)
</success_criteria>

<output>
After completion, create `.planning/quick/260422-ktb-apply-research-result-to-canvas-color-te/260422-ktb-SUMMARY.md`
</output>
