---
phase: 07-llm-research-as-opt-in-metadata-layer
plan: 09b
type: execute
wave: 6
depends_on: [09a]
files_modified:
  - frontend/src/components/canvas/InspectorSidebar.tsx
  - frontend/src/components/canvas/__tests__/InspectorSidebar.test.tsx
  # NB (BLOCKER 3): ProjectDetail.tsx is OWNED by Plan 10. Plan 09b mounts
  # <ResearchDialog> INSIDE InspectorSidebar.tsx with `useState<boolean>` local
  # to InspectorSidebar per UI-SPEC §Interaction Contract Open-state row.
autonomous: true
requirements:
  - V3-LLM-OPT-IN
must_haves:
  truths:
    - "InspectorSidebar placeholder mode renders `Pesquisar metadados históricos` button (disabled when project.status !== 'generated')"
    - "InspectorSidebar mounts <ResearchDialog> internally (BLOCKER 3 partition — no ProjectDetail.tsx changes)"
    - "Placeholder microcopy `Última pesquisa: {provider} · {model} · {YYYY-MM-DD HH:mm}` renders when `overlay.exists && overlay.meta != null` (BLOCKER 2 D-08 fix — UI-SPEC §Surface 2 line 184)"
    - "Condado-mode + barony-mode show green `Pesquisa aplicada` badge when overlay covers the territory; `Atualizar pesquisa` link reopens dialog with forceRefresh pre-checked"
    - "Phase 03 D-16 English COPY block (lines 28-35) UNCHANGED"
    - "vitest ≥6 new cases — including microcopy render with mocked overlay-meta response"
  artifacts:
    - path: "frontend/src/components/canvas/InspectorSidebar.tsx"
      provides: "Placeholder-mode research trigger + 'Última pesquisa' microcopy + condado/barony badge + ResearchDialog mount"
      contains: "Pesquisar metadados históricos"
  key_links:
    - from: "frontend/src/components/canvas/InspectorSidebar.tsx"
      to: "frontend/src/components/research/ResearchDialog.tsx (Plan 09a)"
      via: "useState<boolean>(researchOpen) controls Dialog.Root open prop"
      pattern: "ResearchDialog"
    - from: "frontend/src/components/canvas/InspectorSidebar.tsx"
      to: "frontend/src/api/useResearchOverlay.ts (Plan 09a)"
      via: "useResearchOverlay(projectId) → {exists, covered_condado_ids, meta}"
      pattern: "useResearchOverlay"
---

<objective>
Wire Plan 09a's ResearchDialog + hooks into InspectorSidebar: placeholder-mode trigger button, "Última pesquisa" microcopy (BLOCKER 2 fix), condado/barony `Pesquisa aplicada` badge, `Atualizar pesquisa` reopen link. Pre-split from former Plan 09 per checker WARNING 2.

Purpose: D-08 trigger placement; UI-SPEC §Surface 2 + microcopy line 184; BLOCKER 2 microcopy render; BLOCKER 3 partition (ResearchDialog mounted inside InspectorSidebar).

Output:
- InspectorSidebar.tsx extensions
- vitest cases (≥6 new) including microcopy render
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@CLAUDE.md
@.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-CONTEXT.md
@.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-UI-SPEC.md
@frontend/src/components/canvas/InspectorSidebar.tsx
@frontend/src/components/research/ResearchDialog.tsx
@frontend/src/api/useResearchOverlay.ts
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: InspectorSidebar extensions — placeholder trigger + microcopy + badge + ResearchDialog mount</name>
  <files>
    frontend/src/components/canvas/InspectorSidebar.tsx
    frontend/src/components/canvas/__tests__/InspectorSidebar.test.tsx
  </files>
  <read_first>
    - frontend/src/components/canvas/InspectorSidebar.tsx (existing 3-mode dispatcher; placeholder block ~lines 187-193; English COPY block lines 28-35 LOCKED per Phase 03 D-16; condado hierarchy badge row 262-268; barony hierarchy badge row 110-117)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-UI-SPEC.md §Surface 2 (FULL — line 184 microcopy `Última pesquisa: {provider} · {model} · {YYYY-MM-DD HH:mm}`)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-UI-SPEC.md §Interaction Contract `InspectorSidebar extensions`
    - frontend/src/api/useResearchOverlay.ts (Plan 09a — returns `{exists, covered_condado_ids, meta}`)
    - frontend/src/components/research/ResearchDialog.tsx (Plan 09a)
  </read_first>
  <behavior>
    - Placeholder mode: `Pesquisar metadados históricos` button + disabled tooltip; microcopy renders when `overlay.exists && overlay.meta != null`
    - Condado/barony mode: `Pesquisa aplicada` badge when overlay covers; `Atualizar pesquisa` link reopens dialog with forceRefresh
    - <ResearchDialog> mounted ONCE at InspectorSidebar root level via local useState (BLOCKER 3)
    - Phase 03 D-16 COPY block untouched
  </behavior>
  <action>
    1. Read existing `InspectorSidebar.tsx` to understand 3-mode dispatcher.

    2. Add local `useState<boolean>(researchOpen)` + `useState<boolean>(forceRefreshPreChecked)`.

    3. Mount `<ResearchDialog open={researchOpen} onOpenChange={setResearchOpen} forceRefresh={forceRefreshPreChecked} projectId={projectId} ... />` ONCE at InspectorSidebar root (so it survives mode switches).

    4. Extend placeholder block:
       - After existing PT-BR `Clique num território para ver detalhes` text (DO NOT MODIFY), insert `<Button variant="soft" size="2">` with `<MagnifyingGlassIcon />` + label `Pesquisar metadados históricos`.
       - Disabled state: `disabled={project?.status !== 'generated'}`; Radix `Tooltip` body: `Gere o mapa antes de pesquisar metadados.`
       - **BLOCKER 2 microcopy**: BELOW the button, conditionally render the meta line:

       ```tsx
       const overlay = useResearchOverlay(projectId)
       // ...
       {overlay.data?.exists && overlay.data.meta && (
         <Text size="1" color="gray">
           {`Última pesquisa: ${overlay.data.meta.provider} · ${overlay.data.meta.model} · ${formatDate(overlay.data.meta.created_at, 'YYYY-MM-DD HH:mm')}`}
         </Text>
       )}
       ```

       Where `formatDate` is a small inline helper that takes ISO 8601 and emits `YYYY-MM-DD HH:mm` per UI-SPEC. Use `date-fns` if already in deps; otherwise inline format:

       ```typescript
       function formatDate(iso: string, _fmt: 'YYYY-MM-DD HH:mm'): string {
         const d = new Date(iso)
         const pad = (n: number) => String(n).padStart(2, '0')
         return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
       }
       ```

    5. Extend condado-mode hierarchy badge row (~lines 262-268):
       - After gray "Baronies: {n}" badge, render `<Badge color="green" variant="soft">Pesquisa aplicada</Badge>` when `overlay.data?.exists && overlay.data.covered_condado_ids.includes(condado.id)`
       - To the right of the badge: `<Text size="1" color="gray" style={{ cursor: 'pointer' }} onClick={() => { setForceRefreshPreChecked(true); setResearchOpen(true) }}>Atualizar pesquisa</Text>`

    6. Extend barony-mode hierarchy badge row (~lines 110-117): same badge + link, using parent condado id from `metadata.condados[barony.condado_idx]?.id`.

    7. DO NOT modify Phase 03 D-16 COPY block (lines 28-35).

    8. Vitest — ADD ≥6 NEW cases:
       - Placeholder shows trigger button
       - Trigger disabled when project.status !== 'generated'; tooltip body matches UI-SPEC
       - **Microcopy renders `Última pesquisa: {provider} · {model} · {YYYY-MM-DD HH:mm}` when overlay.meta present** (BLOCKER 2 — mock useResearchOverlay to return `{exists:true, covered_condado_ids:['oviedo'], meta:{provider:'claude', model:'claude-sonnet-4-6', created_at:'2026-05-14T12:30:00Z'}}`; assert text content includes substring `Última pesquisa: claude · claude-sonnet-4-6 · 2026-05-14`)
       - Microcopy ABSENT when overlay.meta is null
       - Condado-mode badge appears when overlay covers condado id
       - Barony-mode badge appears for parent condado id
       - `Atualizar pesquisa` click opens dialog with force-refresh pre-checked
  </action>
  <acceptance_criteria>
    - `grep -n "Pesquisar metadados históricos" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match
    - `grep -n "Pesquisa aplicada" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥2 matches (condado + barony)
    - `grep -n "Atualizar pesquisa" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match
    - `grep -n "Gere o mapa antes de pesquisar metadados" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match
    - `grep -n "useResearchOverlay" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match
    - `grep -n "MagnifyingGlassIcon" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match
    - `grep -n "Última pesquisa:" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match (BLOCKER 2 microcopy)
    - `grep -nE "meta\.provider|meta\.model|meta\.created_at" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥3 matches (microcopy data binding)
    - `grep -n "Clique num território para ver detalhes" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match (Phase 03 D-16 preserved)
    - `grep -n "PROJECT_OVERVIEW = 'Project overview'" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match (D-16 COPY block lines 28-35 unchanged)
    - `grep -nE "color=\"green\" variant=\"soft\"" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match
    - `grep -n "<ResearchDialog" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match (BLOCKER 3 — dialog mounted here, not in ProjectDetail)
    - `grep -l "ResearchDialog\|setResearchOpen" frontend/src/pages/ProjectDetail.tsx` returns 0 lines (BLOCKER 3 — ProjectDetail untouched by Plan 09b)
    - `grep -c "^(it|test)\(" frontend/src/components/canvas/__tests__/InspectorSidebar.test.tsx` shows ≥6 NEW cases added
    - At least one vitest case asserts the microcopy substring `Última pesquisa:` renders (BLOCKER 2)
    - `cd frontend && npm test -- --run src/components/canvas/__tests__/InspectorSidebar.test.tsx` exits 0
    - `cd frontend && npm run build` exits 0 (no TypeScript errors)
  </acceptance_criteria>
  <verify>
    <automated>cd frontend && npm test -- --run src/components/canvas/__tests__/InspectorSidebar.test.tsx && npm run build</automated>
  </verify>
  <done>InspectorSidebar extends placeholder + condado + barony modes per UI-SPEC §Surface 2; D-08 microcopy renders; ResearchDialog mounted internally (BLOCKER 3); D-16 COPY block untouched.</done>
</task>

</tasks>

<context_anchors>
- **D-08** (placeholder trigger + microcopy)
- **UI-SPEC §Surface 2** (every copy + interaction; line 184 microcopy)
- **BLOCKER 2** (microcopy "Última pesquisa: {provider} · {model} · {YYYY-MM-DD HH:mm}" renders from useResearchOverlay.meta)
- **BLOCKER 3** (ResearchDialog mounted inside InspectorSidebar; ProjectDetail untouched)
- **Phase 03 D-16** (English COPY block lines 28-35 LOCKED)
- **CLAUDE.md** (PT-BR UI)
</context_anchors>

<threat_model>

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Overlay meta from backend → microcopy render | Trusted backend response; rendered as React text (no XSS surface) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-09b-01 | XSS | microcopy renders meta.provider/model/created_at | mitigate | All values rendered as React text children; no dangerouslySetInnerHTML. Acceptance: `grep -n "dangerouslySetInnerHTML" frontend/src/components/canvas/InspectorSidebar.tsx` returns 0. |
| T-07-09b-02 | Tampering | overlay.covered_condado_ids untrusted | accept | Backend writes the overlay; tampered overlay shows extra/fewer badges — no security boundary crossed. |

</threat_model>

<verification>
- `cd frontend && npm test -- --run src/components/canvas/__tests__/InspectorSidebar.test.tsx` exits 0
- `cd frontend && npm run build` exits 0
- `grep -l "ResearchDialog\|setResearchOpen" frontend/src/pages/ProjectDetail.tsx` returns 0 matches (BLOCKER 3)
- `grep -n "Última pesquisa:" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match (BLOCKER 2)
</verification>

<success_criteria>
- Trigger button + microcopy + badge + dialog mount all in place
- D-08 microcopy renders per UI-SPEC line 184
- BLOCKER 3 partition honored (no ProjectDetail.tsx changes)
- Phase 03 D-16 COPY block untouched
</success_criteria>

<output>
After completion, create `.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-09b-SUMMARY.md` per the standard template.
</output>
