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
    - "REVIEWS fix #2 microcopy: when `overlay.meta.generated_at === overlay.meta.applied_at` (or within 1s), render single line `Última pesquisa: {provider} · {model} · {generated_at YYYY-MM-DD HH:mm}`; when they differ (cache-hit scenario), render two lines: `Pesquisa gerada: {generated_at YYYY-MM-DD HH:mm}` and `· aplicada: {applied_at YYYY-MM-DD HH:mm}`"
    - "Condado-mode + barony-mode show green `Pesquisa aplicada` badge when overlay covers the territory; `Atualizar pesquisa` link reopens dialog with forceRefresh pre-checked"
    - "Phase 03 D-16 English COPY block (lines 28-35) UNCHANGED"
    - "vitest ≥7 new cases — including REVIEWS fix #2 single-line AND two-line microcopy renders"
  artifacts:
    - path: "frontend/src/components/canvas/InspectorSidebar.tsx"
      provides: "Placeholder-mode research trigger + dual-timestamp microcopy (REVIEWS fix #2) + condado/barony badge + ResearchDialog mount"
      contains: "Pesquisar metadados históricos"
  key_links:
    - from: "frontend/src/components/canvas/InspectorSidebar.tsx"
      to: "frontend/src/components/research/ResearchDialog.tsx (Plan 09a)"
      via: "useState<boolean>(researchOpen) controls Dialog.Root open prop"
      pattern: "ResearchDialog"
    - from: "frontend/src/components/canvas/InspectorSidebar.tsx"
      to: "frontend/src/api/useResearchOverlay.ts (Plan 09a)"
      via: "useResearchOverlay(projectId) → {exists, covered_condado_ids, meta with generated_at + applied_at}"
      pattern: "useResearchOverlay"
---

<objective>
Wire Plan 09a's ResearchDialog + hooks into InspectorSidebar: placeholder-mode trigger button, REVIEWS fix #2 dual-timestamp microcopy, condado/barony `Pesquisa aplicada` badge, `Atualizar pesquisa` reopen link. Pre-split from former Plan 09 per checker WARNING 2.

Purpose: D-08 trigger placement; UI-SPEC §Surface 2 + microcopy line 184; BLOCKER 2 microcopy render; BLOCKER 3 partition (ResearchDialog mounted inside InspectorSidebar).

REVIEWS replan 2026-05-14 deltas:
- **Fix #2 (Codex)**: microcopy now consumes BOTH `overlay.meta.generated_at` and `overlay.meta.applied_at`. Render single-line when they match (fresh-run case) and two-line when they differ (cache-hit case). Disambiguates "when was this research originally produced" vs "when was it applied to this project".

Output:
- InspectorSidebar.tsx extensions
- vitest cases (≥7 new) including REVIEWS fix #2 single-line + two-line microcopy renders
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
@.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-REVIEWS.md
@frontend/src/components/canvas/InspectorSidebar.tsx
@frontend/src/components/research/ResearchDialog.tsx
@frontend/src/api/useResearchOverlay.ts
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: InspectorSidebar extensions — placeholder trigger + REVIEWS fix #2 dual-timestamp microcopy + badge + ResearchDialog mount</name>
  <files>
    frontend/src/components/canvas/InspectorSidebar.tsx
    frontend/src/components/canvas/__tests__/InspectorSidebar.test.tsx
  </files>
  <read_first>
    - frontend/src/components/canvas/InspectorSidebar.tsx (existing 3-mode dispatcher; placeholder block ~lines 187-193; English COPY block lines 28-35 LOCKED per Phase 03 D-16; condado hierarchy badge row 262-268; barony hierarchy badge row 110-117)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-UI-SPEC.md §Surface 2 (FULL — line 184 microcopy)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-UI-SPEC.md §Interaction Contract `InspectorSidebar extensions`
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-REVIEWS.md "Recommended Action Before Execution" #2 (generated_at + applied_at — dual microcopy)
    - frontend/src/api/useResearchOverlay.ts (Plan 09a — returns `{exists, covered_condado_ids, meta with generated_at + applied_at}`)
    - frontend/src/components/research/ResearchDialog.tsx (Plan 09a)
  </read_first>
  <behavior>
    - Placeholder mode: `Pesquisar metadados históricos` button + disabled tooltip
    - **REVIEWS fix #2 microcopy** (rendered below the trigger button when `overlay.exists && overlay.meta != null`):
      - When `generated_at` and `applied_at` match within 1 second: single line `Última pesquisa: {provider} · {model} · {generated_at YYYY-MM-DD HH:mm}` (fresh-run case)
      - When they differ (cache-hit case): two lines `Pesquisa gerada: {generated_at YYYY-MM-DD HH:mm}` and `· aplicada: {applied_at YYYY-MM-DD HH:mm}` (also showing provider · model on the first line)
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
       - **REVIEWS fix #2 dual-timestamp microcopy**: BELOW the button, render conditionally:

       ```tsx
       const overlay = useResearchOverlay(projectId)
       const meta = overlay.data?.meta

       // REVIEWS fix #2 — distinguish fresh-run (timestamps match) from cache-hit (timestamps differ).
       // Same-instant tolerance: within 1 second is treated as "fresh" to absorb seconds-precision rounding.
       function timestampsMatch(generatedAt: string, appliedAt: string): boolean {
         const g = new Date(generatedAt).getTime()
         const a = new Date(appliedAt).getTime()
         return Math.abs(a - g) < 1000
       }

       {overlay.data?.exists && meta && (() => {
         const sameInstant = timestampsMatch(meta.generated_at, meta.applied_at)
         if (sameInstant) {
           return (
             <Text size="1" color="gray">
               {`Última pesquisa: ${meta.provider} · ${meta.model} · ${formatDate(meta.generated_at)}`}
             </Text>
           )
         }
         return (
           <Flex direction="column" gap="0">
             <Text size="1" color="gray">
               {`Pesquisa gerada: ${meta.provider} · ${meta.model} · ${formatDate(meta.generated_at)}`}
             </Text>
             <Text size="1" color="gray">
               {`· aplicada: ${formatDate(meta.applied_at)}`}
             </Text>
           </Flex>
         )
       })()}
       ```

       Inline `formatDate` (date-fns is NOT in package.json — confirmed in REVIEWS replan; use inline format per UTC-deterministic spec):

       ```typescript
       function formatDate(iso: string): string {
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

    8. Vitest — ADD ≥7 NEW cases:
       - Placeholder shows trigger button
       - Trigger disabled when project.status !== 'generated'; tooltip body matches UI-SPEC
       - **REVIEWS fix #2 single-line microcopy renders when timestamps match** (mock useResearchOverlay to return generated_at=applied_at=`2026-05-14T12:30:00Z`; assert text content includes substring `Última pesquisa: claude · claude-sonnet-4-6 · 2026-05-14`)
       - **REVIEWS fix #2 two-line microcopy renders when timestamps differ** (mock generated_at=`2026-05-01T12:00:00Z`, applied_at=`2026-05-14T15:00:00Z`; assert text contains `Pesquisa gerada:` AND `· aplicada:`)
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
    - `grep -n "Última pesquisa:" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match (REVIEWS fix #2 single-line)
    - `grep -n "Pesquisa gerada:" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match (REVIEWS fix #2 two-line cache-hit)
    - `grep -n "· aplicada:" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match (REVIEWS fix #2 two-line)
    - `grep -nE "meta\.provider|meta\.model" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥2 matches
    - `grep -n "meta.generated_at" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match (REVIEWS fix #2)
    - `grep -n "meta.applied_at" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match (REVIEWS fix #2)
    - `grep -n "timestampsMatch" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match (REVIEWS fix #2 — same-instant tolerance helper)
    - `grep -n "Clique num território para ver detalhes" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match (Phase 03 D-16 preserved)
    - `grep -n "PROJECT_OVERVIEW = 'Project overview'" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match (D-16 COPY block lines 28-35 unchanged)
    - `grep -nE "color=\"green\" variant=\"soft\"" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match
    - `grep -n "<ResearchDialog" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match (BLOCKER 3 — dialog mounted here, not in ProjectDetail)
    - `grep -l "ResearchDialog\|setResearchOpen" frontend/src/pages/ProjectDetail.tsx` returns 0 lines (BLOCKER 3 — ProjectDetail untouched by Plan 09b)
    - `grep -c "^(it|test)\(" frontend/src/components/canvas/__tests__/InspectorSidebar.test.tsx` shows ≥7 NEW cases added
    - At least one vitest case asserts the SINGLE-LINE microcopy substring `Última pesquisa:` renders when timestamps match (REVIEWS fix #2)
    - At least one vitest case asserts BOTH `Pesquisa gerada:` AND `· aplicada:` render when timestamps differ (REVIEWS fix #2)
    - `cd frontend && npm test -- --run src/components/canvas/__tests__/InspectorSidebar.test.tsx` exits 0
    - `cd frontend && npm run build` exits 0 (no TypeScript errors)
  </acceptance_criteria>
  <verify>
    <automated>cd frontend && npm test -- --run src/components/canvas/__tests__/InspectorSidebar.test.tsx && npm run build</automated>
  </verify>
  <done>InspectorSidebar extends placeholder + condado + barony modes per UI-SPEC §Surface 2; REVIEWS fix #2 dual-timestamp microcopy renders; ResearchDialog mounted internally (BLOCKER 3); D-16 COPY block untouched.</done>
</task>

</tasks>

<context_anchors>
- **D-08** (placeholder trigger + microcopy)
- **UI-SPEC §Surface 2** (every copy + interaction; line 184 microcopy)
- **BLOCKER 2** (microcopy renders from useResearchOverlay.meta)
- **BLOCKER 3** (ResearchDialog mounted inside InspectorSidebar; ProjectDetail untouched)
- **Phase 03 D-16** (English COPY block lines 28-35 LOCKED)
- **CLAUDE.md** (PT-BR UI)
- **REVIEWS fix #2** (generated_at + applied_at dual-timestamp microcopy: single-line when match, two-line when differ)
</context_anchors>

<threat_model>

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Overlay meta from backend → microcopy render | Trusted backend response; rendered as React text (no XSS surface) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-09b-01 | XSS | microcopy renders meta.provider/model/generated_at/applied_at | mitigate | All values rendered as React text children; no dangerouslySetInnerHTML. Acceptance: `grep -n "dangerouslySetInnerHTML" frontend/src/components/canvas/InspectorSidebar.tsx` returns 0. |
| T-07-09b-02 | Tampering | overlay.covered_condado_ids untrusted | accept | Backend writes the overlay; tampered overlay shows extra/fewer badges — no security boundary crossed. |
| T-07-09b-03 (REVIEWS fix #2) | Tampering | Timestamp display confusion | mitigate | Dual-microcopy renders disambiguate fresh-run vs cache-hit. Same-instant tolerance window absorbs seconds-precision rounding. Vitest cases assert both render paths. |

</threat_model>

<verification>
- `cd frontend && npm test -- --run src/components/canvas/__tests__/InspectorSidebar.test.tsx` exits 0
- `cd frontend && npm run build` exits 0
- `grep -l "ResearchDialog\|setResearchOpen" frontend/src/pages/ProjectDetail.tsx` returns 0 matches (BLOCKER 3)
- `grep -n "Última pesquisa:" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match (REVIEWS fix #2)
- `grep -n "Pesquisa gerada:" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥1 match (REVIEWS fix #2)
- `grep -n "meta.generated_at\|meta.applied_at" frontend/src/components/canvas/InspectorSidebar.tsx` returns ≥2 matches (REVIEWS fix #2)
</verification>

<success_criteria>
- Trigger button + dual-timestamp microcopy + badge + dialog mount all in place
- REVIEWS fix #2 single-line AND two-line microcopy paths covered by vitest
- BLOCKER 3 partition honored (no ProjectDetail.tsx changes)
- Phase 03 D-16 COPY block untouched
</success_criteria>

<output>
After completion, create `.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-09b-SUMMARY.md` per the standard template.
</output>
