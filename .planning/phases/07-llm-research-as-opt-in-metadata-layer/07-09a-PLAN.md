---
phase: 07-llm-research-as-opt-in-metadata-layer
plan: 09a
type: execute
wave: 5
depends_on: [07a, 07b, 08]
files_modified:
  - frontend/src/api/useProviders.ts
  - frontend/src/api/useResearchOverlay.ts
  - frontend/src/components/research/ResearchDialog.tsx
  - frontend/src/components/research/ProviderSelector.tsx
  - frontend/src/components/research/ResearchProgress.tsx
  - frontend/src/hooks/useResearchStream.ts
  - frontend/src/api/__tests__/useProviders.test.ts
  - frontend/src/api/__tests__/useResearchOverlay.test.ts
  - frontend/src/components/research/__tests__/ResearchDialog.test.tsx
  - frontend/src/components/research/__tests__/ProviderSelector.test.tsx
  - frontend/src/components/research/__tests__/ResearchProgress.test.tsx
  - frontend/src/hooks/__tests__/useResearchStream.test.ts
autonomous: true
requirements:
  - V3-LLM-OPT-IN
must_haves:
  truths:
    - "useProviders polls /api/v3/research/providers every 15s while dialog open (UI-SPEC §Interaction Contract)"
    - "useResearchOverlay returns `{exists, covered_condado_ids, meta}` where meta = `{provider, model, created_at} | null` (BLOCKER 2 fix — consumes Plan 07b overlay endpoint shape)"
    - "ResearchDialog renders the 4-field form per UI-SPEC §Surface 1 + 1.2s auto-close on success"
    - "useResearchStream consumes SSE with dual-shape tolerance (structured envelope OR raw `Tentativa N/M` line) per Pitfall 9 + WARNING 3"
    - "useResearchStream wraps the SSE loop in `temporal.pause()/resume()` per CLAUDE.md zundo discipline"
    - "PT-BR strings match UI-SPEC §Copywriting exactly"
  artifacts:
    - path: "frontend/src/api/useProviders.ts"
      provides: "TanStack Query hook for /api/v3/research/providers (15s refetch when enabled)"
      contains: "refetchInterval"
    - path: "frontend/src/api/useResearchOverlay.ts"
      provides: "TanStack Query hook returning {exists, covered_condado_ids, meta}"
      contains: "meta"
    - path: "frontend/src/components/research/ResearchDialog.tsx"
      provides: "Radix Dialog modal — 4-field form + SSE-progress + auto-close"
      contains: "Dialog.Root"
    - path: "frontend/src/components/research/ProviderSelector.tsx"
      provides: "Provider dropdown with disabled state + tooltip"
      contains: "Select.Root"
    - path: "frontend/src/components/research/ResearchProgress.tsx"
      provides: "Per-stage list (kingdoms→duchies→condados→baronies)"
      contains: "ScrollArea"
    - path: "frontend/src/hooks/useResearchStream.ts"
      provides: "EventSource consumer; dual-shape SSE tolerant"
      contains: "temporal.pause"
  key_links:
    - from: "frontend/src/components/research/ResearchDialog.tsx"
      to: "/api/v3/research/start + /stream/{run_id} + /stop/{run_id}"
      via: "fetch POST /start; EventSource /stream; useResearchStream"
      pattern: "/api/v3/research/(start|stream|stop)"
---

<objective>
Land the TanStack hooks + ResearchDialog + sub-components + useResearchStream. Pre-split from former Plan 09 per checker WARNING 2. 09a covers hooks + dialog UI; 09b covers InspectorSidebar wiring + microcopy.

Purpose: D-09 Radix Dialog modal + SSE; UI-SPEC §Surface 1 lock; Pitfall 9 dual-shape SSE tolerance; BLOCKER 2 D-08 microcopy data plumbing through `meta`.

Output:
- 2 TanStack hooks (useProviders + useResearchOverlay with meta)
- 4 components/hook (ResearchDialog, ProviderSelector, ResearchProgress, useResearchStream)
- 6 vitest test files
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
@.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-RESEARCH.md
@.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-UI-SPEC.md
@frontend/src/components/projects/NewProjectModal.tsx
@frontend/src/hooks/useRenderStream.ts
@frontend/src/hooks/useCanvasArtifacts.ts
@frontend/src/stores/uiStore.ts
@frontend/src/main.tsx

<dependency_note>
Per BLOCKER 3 partition: ResearchDialog is MOUNTED by Plan 09b inside InspectorSidebar.tsx
(`useState<boolean>` local to InspectorSidebar per UI-SPEC §Interaction Contract Open-state row).
Plan 09a creates the component; Plan 09b mounts it. Plan 09a's `files_modified` does NOT include
ProjectDetail.tsx — Plan 10 owns ProjectDetail.tsx exclusively.

WARNING 3 reconciliation: Plan 03 must verify retry.py's emission path. If retry.py only
RAISES exceptions and the runner (Plan 07b) catches them to emit structured `event_type:retry`
events, drop dual-shape SSE tolerance (only structured envelope is needed). If retry.py
writes `Tentativa N/M` raw to a queue/stream directly, keep dual-shape. Plan 03 documents the
verdict in its <dependency_note>. Default in this plan: dual-shape tolerance (defensive).
</dependency_note>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: TanStack hooks — useProviders + useResearchOverlay (with meta field per BLOCKER 2)</name>
  <files>
    frontend/src/api/useProviders.ts
    frontend/src/api/useResearchOverlay.ts
    frontend/src/api/__tests__/useProviders.test.ts
    frontend/src/api/__tests__/useResearchOverlay.test.ts
  </files>
  <read_first>
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-UI-SPEC.md §Interaction Contract `Provider health refresh` row (15s refetchInterval)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-UI-SPEC.md §Surface 2 (microcopy "Última pesquisa: {provider} · {model} · {YYYY-MM-DD HH:mm}" — depends on meta field)
    - frontend/src/hooks/useCanvasArtifacts.ts (TanStack Query pattern)
    - backend/medieval_forge/api/v3/research.py (Plan 07b — overlay endpoint returns `{exists, covered_condado_ids, meta: {provider, model, created_at} | null}`)
  </read_first>
  <behavior>
    - useProviders: 15s refetchInterval while enabled; returns ProviderEntry[]
    - useResearchOverlay: 30s staleTime; returns `{exists, covered_condado_ids, meta}`; meta=null when overlay or sidecar missing
  </behavior>
  <action>
    1. Create `frontend/src/api/useProviders.ts` (unchanged from former Plan 09 Task 1).

    2. Create `frontend/src/api/useResearchOverlay.ts` consuming the NEW Plan 07b shape (BLOCKER 2):

       ```typescript
       import { useQuery } from '@tanstack/react-query'

       export interface ResearchOverlayMeta {
         provider: string
         model: string
         created_at: string
       }

       export interface ResearchOverlay {
         exists: boolean
         covered_condado_ids: string[]
         meta: ResearchOverlayMeta | null
       }

       export function useResearchOverlay(projectId: string | undefined) {
         return useQuery<ResearchOverlay>({
           queryKey: ['v3', 'projects', projectId, 'research', 'overlay'],
           queryFn: async () => {
             const res = await fetch(`/api/v3/projects/${projectId}/research/overlay`)
             if (!res.ok && res.status !== 404) throw new Error(`overlay fetch failed: ${res.status}`)
             // Plan 07b endpoint always returns the structured shape; 404 unreachable in current impl
             // but defensive fallback retained for fixture/dev cases
             if (res.status === 404) return { exists: false, covered_condado_ids: [], meta: null }
             return res.json()
           },
           enabled: !!projectId,
           staleTime: 30_000,
         })
       }
       ```

    3. Vitest tests — useProviders ≥3 cases; useResearchOverlay ≥4 cases:
       - exists:false + meta:null when endpoint returns that shape
       - exists:true + meta populated when overlay + sidecar present
       - exists:true + meta:null when overlay exists but sidecar missing (graceful degrade)
       - 30s staleTime respected
  </action>
  <acceptance_criteria>
    - File `frontend/src/api/useProviders.ts` EXISTS
    - File `frontend/src/api/useResearchOverlay.ts` EXISTS
    - `grep -n "refetchInterval: enabled ? 15_000 : false" frontend/src/api/useProviders.ts` returns 1 match
    - `grep -n "staleTime: 30_000" frontend/src/api/useResearchOverlay.ts` returns 1 match
    - `grep -n "ResearchOverlayMeta" frontend/src/api/useResearchOverlay.ts` returns ≥1 match (BLOCKER 2)
    - `grep -nE "provider:\s*string|model:\s*string|created_at:\s*string" frontend/src/api/useResearchOverlay.ts` returns ≥3 matches
    - `grep -nE "meta:\s*ResearchOverlayMeta\s*\|\s*null" frontend/src/api/useResearchOverlay.ts` returns ≥1 match
    - `grep -n "covered_condado_ids" frontend/src/api/useResearchOverlay.ts` returns ≥1 match
    - `grep -n "/api/v3/research/providers" frontend/src/api/useProviders.ts` returns 1 match
    - `grep -c "^(it|test)\(" frontend/src/api/__tests__/useProviders.test.ts` returns ≥3
    - `grep -c "^(it|test)\(" frontend/src/api/__tests__/useResearchOverlay.test.ts` returns ≥4
    - `cd frontend && npm test -- --run src/api/__tests__/useProviders.test.ts src/api/__tests__/useResearchOverlay.test.ts` exits 0
  </acceptance_criteria>
  <verify>
    <automated>cd frontend && npm test -- --run src/api/__tests__/useProviders.test.ts src/api/__tests__/useResearchOverlay.test.ts</automated>
  </verify>
  <done>2 TanStack hooks land; meta field consumed; vitest covers happy paths + graceful degrade.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: ResearchDialog + ProviderSelector + ResearchProgress + useResearchStream</name>
  <files>
    frontend/src/components/research/ResearchDialog.tsx
    frontend/src/components/research/ProviderSelector.tsx
    frontend/src/components/research/ResearchProgress.tsx
    frontend/src/hooks/useResearchStream.ts
    frontend/src/components/research/__tests__/ResearchDialog.test.tsx
    frontend/src/components/research/__tests__/ProviderSelector.test.tsx
    frontend/src/components/research/__tests__/ResearchProgress.test.tsx
    frontend/src/hooks/__tests__/useResearchStream.test.ts
  </files>
  <read_first>
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-UI-SPEC.md §Surface 1 (FULL)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-UI-SPEC.md §Component Inventory
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-RESEARCH.md §Pattern 14
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-RESEARCH.md §Pitfall 9 (dual-shape SSE)
    - frontend/src/hooks/useRenderStream.ts
    - frontend/src/components/projects/NewProjectModal.tsx
    - frontend/src/stores/uiStore.ts (temporal.pause/resume)
    - frontend/src/api/useProviders.ts (Task 1)
  </read_first>
  <behavior>
    - useResearchStream: dual-shape tolerant; wraps in temporal.pause/resume; subscribe/unsubscribe API
    - ResearchDialog: 4 fields + cache-hit microcopy + CTA state machine + 1.2s auto-close on success
    - ProviderSelector: disabled state + tooltip
    - ResearchProgress: 4 stage rows + retry inline notice
  </behavior>
  <action>
    Same content as former Plan 09 Task 2 (full ResearchDialog + sub-components + useResearchStream + 4 test files). NO CHANGES from BLOCKER 1 here — only Task 1 changed (overlay hook).

    Key behaviors preserved:
    - Dialog.Root open/onOpenChange with maxWidth: 560
    - PT-BR title `Pesquisar metadados históricos`
    - Forçar checkbox `Forçar nova pesquisa (ignorar cache)`
    - `Iniciar pesquisa` / `Cancelar pesquisa` CTAs
    - `setTimeout(() => setOpen(false), 1200)` on terminal success
    - useResearchStream: dual-shape parse via try/catch JSON.parse
    - useResearchStream: `temporal.pause()` on stream start, `temporal.resume()` on terminal/cleanup
    - vitest: ≥8 ResearchDialog cases, ≥3 ProviderSelector, ≥5 ResearchProgress, ≥5 useResearchStream
  </action>
  <acceptance_criteria>
    - All 4 new component/hook files EXIST
    - `grep -n "Dialog.Root" frontend/src/components/research/ResearchDialog.tsx` returns ≥1 match
    - `grep -n "Pesquisar metadados históricos" frontend/src/components/research/ResearchDialog.tsx` returns ≥1 match
    - `grep -n "Forçar nova pesquisa (ignorar cache)" frontend/src/components/research/ResearchDialog.tsx` returns ≥1 match
    - `grep -n "Cancelar pesquisa" frontend/src/components/research/ResearchDialog.tsx` returns ≥1 match
    - `grep -n "Iniciar pesquisa" frontend/src/components/research/ResearchDialog.tsx` returns ≥1 match
    - `grep -nE "setTimeout\([^,]+,\s*1200\)" frontend/src/components/research/ResearchDialog.tsx` returns 1 match
    - `grep -n "style={{ maxWidth: 560 }}" frontend/src/components/research/ResearchDialog.tsx` returns 1 match
    - `grep -nE "Reinos\|Ducados\|Condados\|Baronias" frontend/src/components/research/ResearchProgress.tsx` returns ≥4 matches
    - `grep -n "maxHeight: 240" frontend/src/components/research/ResearchProgress.tsx` returns ≥1 match
    - `grep -n "temporal.pause" frontend/src/hooks/useResearchStream.ts` returns ≥1 match
    - `grep -nE "JSON.parse|try \{" frontend/src/hooks/useResearchStream.ts` returns ≥1 match
    - `grep -n "/api/v3/research/stop" frontend/src/components/research/ResearchDialog.tsx` returns ≥1 match
    - `grep -nE "weight=\"bold\"" frontend/src/components/research/ResearchDialog.tsx` returns 0 matches
    - `cd frontend && npm test -- --run src/components/research src/hooks/__tests__/useResearchStream.test.ts` exits 0
  </acceptance_criteria>
  <verify>
    <automated>cd frontend && npm test -- --run src/components/research src/hooks/__tests__/useResearchStream.test.ts</automated>
  </verify>
  <done>4 components/hook land; PT-BR strings match UI-SPEC; dual-shape SSE; ≥21 vitest cases green.</done>
</task>

</tasks>

<context_anchors>
- **D-08** (placeholder trigger placement — wiring in Plan 09b)
- **D-09** (Radix Dialog + 4 fields + SSE)
- **UI-SPEC §Surface 1** (every copy + interaction)
- **RESEARCH §Pattern 14** (useResearchStream)
- **RESEARCH §Pitfall 9** (dual-shape SSE)
- **CLAUDE.md** (zundo temporal.pause; PT-BR UI)
- **BLOCKER 2** (meta field in useResearchOverlay)
- **BLOCKER 3** (Plan 09 does NOT touch ProjectDetail.tsx)
</context_anchors>

<threat_model>

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| User input → paste-API-key field | Untrusted text typed into the dialog |
| /providers response → ProviderSelector | Trusted backend payload |
| SSE stream → useResearchStream | Untrusted LLM tokens to UI |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-09a-01 | Information Disclosure | Paste-API-key field echo | mitigate | `<TextField.Root type="password">`. Acceptance: `grep -nE "type=\"password\"" frontend/src/components/research/ResearchDialog.tsx` returns ≥1. |
| T-07-09a-02 | Information Disclosure | API key persistence | mitigate | No localStorage/sessionStorage of key. Acceptance: grep returns 0 matches. |
| T-07-09a-03 | XSS via SSE content | ResearchProgress | mitigate | All stage labels rendered as React text. `grep -n "dangerouslySetInnerHTML"` returns 0. |
| T-07-09a-04 | DoS | EventSource auto-reconnect storm | mitigate | useResearchStream explicit subscribe/unsubscribe; cleanup on unmount tested. |

</threat_model>

<verification>
- `cd frontend && npm test -- --run src/api src/components/research src/hooks/__tests__/useResearchStream.test.ts` exits 0
- `cd frontend && npm run build` exits 0 (after Plan 09b lands)
- `grep -n "weight=\"bold\"" frontend/src/components/research/*.tsx` returns 0 matches
- `grep -n "dangerouslySetInnerHTML" frontend/src/components/research/*.tsx` returns 0 matches
- `grep -nE "type=\"password\"" frontend/src/components/research/ResearchDialog.tsx` returns ≥1 match
</verification>

<success_criteria>
- Hooks + dialog + sub-components ready for Plan 09b to mount
- PT-BR strings verbatim from UI-SPEC §Copywriting
- useResearchOverlay returns meta field per BLOCKER 2
- Dual-shape SSE tolerance (WARNING 3 default; may simplify after Plan 03 verdict)
</success_criteria>

<output>
After completion, create `.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-09a-SUMMARY.md` per the standard template.
</output>
