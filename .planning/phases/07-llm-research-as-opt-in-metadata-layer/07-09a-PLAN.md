---
phase: 07-llm-research-as-opt-in-metadata-layer
plan: 09a
type: execute
wave: 5
depends_on: [03, 07a, 07b, 08]
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
  - frontend/tests/uat/playwright/research_cancel.spec.ts
autonomous: true
requirements:
  - V3-LLM-OPT-IN
must_haves:
  truths:
    - "useProviders polls /api/v3/research/providers every 15s while dialog open (UI-SPEC §Interaction Contract)"
    - "ProviderSelector reads `available_models` from /providers and applies ordered preference list ['qwen2.5:7b', 'qwen2.5-coder:14b', 'gemma4:26b', 'deepseek-r1:14b'] to pick a default (REVIEWS fix #5); falls back to first available when none match; surfaces hint when qwen2.5:7b is missing"
    - "useResearchOverlay returns `{exists, covered_condado_ids, meta}` where meta = `{provider, model, generated_at, applied_at} | null` (BLOCKER 2 + REVIEWS fix #2 — both timestamps consumed)"
    - "ResearchDialog renders the 4-field form per UI-SPEC §Surface 1 + 1.2s auto-close on success"
    - "useResearchStream consumes SSE; dual-shape tolerance is CONDITIONAL on Plan 03 verdict file — verdict (b) drops the raw-PT-BR branch and keeps only structured-envelope path (REVIEWS fix #3)"
    - "useResearchStream wraps the SSE loop in `temporal.pause()/resume()` per CLAUDE.md zundo discipline"
    - "useResearchStream maps `AbortError` to terminal state `{phase: 'failed', error_code: 'aborted', error_message: 'Pesquisa cancelada pelo usuário.'}` (REVIEWS fix #7 Qwen3 — Cancel UI must not stick in 'running')"
    - "Claude CLI piggyback microcopy says 'Tentando token do Claude CLI…' with explicit fallback hint, not 'auto-detected' (REVIEWS soft codex)"
    - "PT-BR strings match UI-SPEC §Copywriting exactly"
  artifacts:
    - path: "frontend/src/api/useProviders.ts"
      provides: "TanStack Query hook for /api/v3/research/providers (15s refetch when enabled)"
      contains: "refetchInterval"
    - path: "frontend/src/api/useResearchOverlay.ts"
      provides: "TanStack Query hook returning {exists, covered_condado_ids, meta with generated_at + applied_at}"
      contains: "applied_at"
    - path: "frontend/src/components/research/ResearchDialog.tsx"
      provides: "Radix Dialog modal — 4-field form + SSE-progress + auto-close + softened CLI-piggyback microcopy"
      contains: "Dialog.Root"
    - path: "frontend/src/components/research/ProviderSelector.tsx"
      provides: "Provider dropdown + ordered-preference model default + missing-model hint (REVIEWS fix #5)"
      contains: "available_models"
    - path: "frontend/src/components/research/ResearchProgress.tsx"
      provides: "Per-stage list (kingdoms→duchies→condados→baronies) + Cancelada terminal state (REVIEWS fix #7)"
      contains: "Cancelada"
    - path: "frontend/src/hooks/useResearchStream.ts"
      provides: "EventSource consumer; AbortError → failed terminal state; conditional dual-shape SSE based on Plan 03 verdict"
      contains: "AbortError"
    - path: "frontend/tests/uat/playwright/research_cancel.spec.ts"
      provides: "REVIEWS fix #7 Qwen3 — cancel mid-stream → ProgressUI shows 'Cancelada' not 'Erro'"
      contains: "Cancelada"
  key_links:
    - from: "frontend/src/components/research/ResearchDialog.tsx"
      to: "/api/v3/research/start + /stream/{run_id} + /stop/{run_id}"
      via: "fetch POST /start; EventSource /stream; useResearchStream"
      pattern: "/api/v3/research/(start|stream|stop)"
---

<objective>
Land the TanStack hooks + ResearchDialog + sub-components + useResearchStream. Pre-split from former Plan 09 per checker WARNING 2. 09a covers hooks + dialog UI; 09b covers InspectorSidebar wiring + microcopy.

Purpose: D-09 Radix Dialog modal + SSE; UI-SPEC §Surface 1 lock; Pitfall 9 dual-shape SSE tolerance (now conditional); BLOCKER 2 D-08 microcopy data plumbing through `meta`.

REVIEWS replan 2026-05-14 deltas:
- **Fix #2 (Codex)**: `useResearchOverlay` returns meta with BOTH `generated_at` and `applied_at` (per Plan 07b runner + 07b overlay endpoint).
- **Fix #3 (Codex+OpenCode) — wave/depends_on**: `depends_on` adds `03` explicitly so Plan 09a executor reads Plan 03's WARNING 3 verdict from `07-03-SUMMARY.md` BEFORE writing useResearchStream. If verdict is (b) (retry.py only raises), the dual-shape SSE parser drops the raw-PT-BR branch and keeps only structured-envelope handling. Wave 5 retained (08 is wave 3; 07b is wave 4 and 09a consumes the overlay endpoint shape from 07b — wave 5 is correct).
- **Fix #5 (OpenCode) — `available_models` consumed by ProviderSelector**: read the list from /providers response; apply ordered preference `['qwen2.5:7b', 'qwen2.5-coder:14b', 'gemma4:26b', 'deepseek-r1:14b']`; fall back to first available when none match; display PT-BR hint `Modelo padrão qwen2.5:7b não encontrado — execute "ollama pull qwen2.5:7b" para o melhor resultado.` when the preferred model is missing.
- **Fix #7 (Qwen3) — `AbortError` → terminal `failed` state**: useResearchStream reducer maps `AbortError` to `{phase: 'failed', error_code: 'aborted', error_message: 'Pesquisa cancelada pelo usuário.'}`. The UI distinguishes "Cancelada" (intentional) from "Erro" (unexpected). New Playwright spec `research_cancel.spec.ts` exercises mid-stream cancel.
- **Soft codex**: CLI-piggyback microcopy softened. Replace "Token do Claude CLI auto-detectado" with "Tentando token do Claude CLI… (se rejeitado, voltamos para a chave salva no DB)".

Output:
- 2 TanStack hooks (useProviders + useResearchOverlay with meta dual timestamps)
- 4 components/hook (ResearchDialog, ProviderSelector with available_models, ResearchProgress with Cancelada state, useResearchStream with AbortError handler + conditional dual-shape)
- 7 vitest test files (6 + new cancel spec)
- 1 Playwright spec: research_cancel.spec.ts
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
@.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-REVIEWS.md
@.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-03-SUMMARY.md
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

REVIEWS fix #3 — WARNING 3 reconciliation:
1. BEFORE writing useResearchStream, READ `.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-03-SUMMARY.md` and find the `## WARNING 3 — retry.py emission verdict` section.
2. If verdict is **(a) retry.py writes to queue/stream**: keep DUAL-SHAPE SSE tolerance (structured envelope OR raw PT-BR "Tentativa N/M" line).
3. If verdict is **(b) retry.py only raises**: drop the raw-PT-BR branch entirely. useResearchStream consumes ONLY structured envelopes (`event_type: "retry"` events emitted by Plan 07b runner). Code becomes simpler and tests narrow accordingly.

Default if Plan 03 SUMMARY not yet present (Wave 1 not run): assume verdict (b) and use structured-envelope-only path. Re-test against (a) only if SUMMARY ends up reporting (a).
</dependency_note>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: TanStack hooks — useProviders + useResearchOverlay (with meta.generated_at + meta.applied_at per REVIEWS fix #2)</name>
  <files>
    frontend/src/api/useProviders.ts
    frontend/src/api/useResearchOverlay.ts
    frontend/src/api/__tests__/useProviders.test.ts
    frontend/src/api/__tests__/useResearchOverlay.test.ts
  </files>
  <read_first>
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-UI-SPEC.md §Interaction Contract `Provider health refresh` row (15s refetchInterval)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-UI-SPEC.md §Surface 2 (microcopy — depends on meta fields)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-REVIEWS.md "Recommended Action Before Execution" #2 (generated_at + applied_at split)
    - frontend/src/hooks/useCanvasArtifacts.ts (TanStack Query pattern)
    - backend/medieval_forge/api/v3/research.py (Plan 07b — overlay endpoint returns `{exists, covered_condado_ids, meta: {provider, model, generated_at, applied_at} | null}`; /providers returns `[{..., available_models?: string[]}]`)
  </read_first>
  <behavior>
    - useProviders: 15s refetchInterval while enabled; returns ProviderEntry[] with optional available_models per entry
    - useResearchOverlay: 30s staleTime; returns `{exists, covered_condado_ids, meta}`; meta carries both `generated_at` AND `applied_at`; meta=null when overlay or sidecar missing
  </behavior>
  <action>
    1. Create `frontend/src/api/useProviders.ts`:

       ```typescript
       import { useQuery } from '@tanstack/react-query'

       export interface ProviderEntry {
         provider_id: string
         display_name: string
         healthy: boolean
         message: string
         configured: boolean
         available_models?: string[]   // REVIEWS fix #5 — present for Ollama
       }

       export function useProviders(enabled: boolean = true) {
         return useQuery<ProviderEntry[]>({
           queryKey: ['v3', 'research', 'providers'],
           queryFn: async () => {
             const res = await fetch('/api/v3/research/providers')
             if (!res.ok) throw new Error(`providers fetch failed: ${res.status}`)
             return res.json()
           },
           enabled,
           refetchInterval: enabled ? 15_000 : false,
         })
       }
       ```

    2. Create `frontend/src/api/useResearchOverlay.ts` consuming the NEW Plan 07b shape (BLOCKER 2 + REVIEWS fix #2):

       ```typescript
       import { useQuery } from '@tanstack/react-query'

       export interface ResearchOverlayMeta {
         provider: string
         model: string
         generated_at: string   // REVIEWS fix #2 — ISO 8601, original LLM-output timestamp
         applied_at: string     // REVIEWS fix #2 — ISO 8601, when runner wrote this overlay
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
             if (res.status === 404) return { exists: false, covered_condado_ids: [], meta: null }
             return res.json()
           },
           enabled: !!projectId,
           staleTime: 30_000,
         })
       }
       ```

    3. Vitest tests — useProviders ≥3 cases (incl. one with available_models populated); useResearchOverlay ≥5 cases:
       - exists:false + meta:null when endpoint returns that shape
       - exists:true + meta populated with BOTH generated_at AND applied_at
       - exists:true + meta:null when overlay exists but sidecar missing (graceful degrade)
       - 30s staleTime respected
       - **REVIEWS fix #2 test**: meta.generated_at and meta.applied_at can differ (cache-hit scenario)
  </action>
  <acceptance_criteria>
    - File `frontend/src/api/useProviders.ts` EXISTS
    - File `frontend/src/api/useResearchOverlay.ts` EXISTS
    - `grep -n "refetchInterval: enabled ? 15_000 : false" frontend/src/api/useProviders.ts` returns 1 match
    - `grep -n "available_models" frontend/src/api/useProviders.ts` returns ≥1 match (REVIEWS fix #5)
    - `grep -n "staleTime: 30_000" frontend/src/api/useResearchOverlay.ts` returns 1 match
    - `grep -n "ResearchOverlayMeta" frontend/src/api/useResearchOverlay.ts` returns ≥1 match
    - `grep -nE "provider:\s*string|model:\s*string" frontend/src/api/useResearchOverlay.ts` returns ≥2 matches
    - `grep -n "generated_at:\s*string" frontend/src/api/useResearchOverlay.ts` returns 1 match (REVIEWS fix #2)
    - `grep -n "applied_at:\s*string" frontend/src/api/useResearchOverlay.ts` returns 1 match (REVIEWS fix #2)
    - `grep -nE "meta:\s*ResearchOverlayMeta\s*\|\s*null" frontend/src/api/useResearchOverlay.ts` returns ≥1 match
    - `grep -n "covered_condado_ids" frontend/src/api/useResearchOverlay.ts` returns ≥1 match
    - `grep -n "/api/v3/research/providers" frontend/src/api/useProviders.ts` returns 1 match
    - `grep -c "^(it|test)\(" frontend/src/api/__tests__/useProviders.test.ts` returns ≥3
    - `grep -c "^(it|test)\(" frontend/src/api/__tests__/useResearchOverlay.test.ts` returns ≥5
    - `cd frontend && npm test -- --run src/api/__tests__/useProviders.test.ts src/api/__tests__/useResearchOverlay.test.ts` exits 0
  </acceptance_criteria>
  <verify>
    <automated>cd frontend && npm test -- --run src/api/__tests__/useProviders.test.ts src/api/__tests__/useResearchOverlay.test.ts</automated>
  </verify>
  <done>2 TanStack hooks land; meta with dual timestamps consumed; available_models surfaced; vitest covers happy paths + graceful degrade + cache-hit timestamp asymmetry.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: ResearchDialog + ProviderSelector (with REVIEWS fix #5 ordered preference) + ResearchProgress (with REVIEWS fix #7 Cancelada) + useResearchStream (with REVIEWS fix #7 AbortError + REVIEWS fix #3 conditional dual-shape + soft codex CLI piggyback microcopy)</name>
  <files>
    frontend/src/components/research/ResearchDialog.tsx
    frontend/src/components/research/ProviderSelector.tsx
    frontend/src/components/research/ResearchProgress.tsx
    frontend/src/hooks/useResearchStream.ts
    frontend/src/components/research/__tests__/ResearchDialog.test.tsx
    frontend/src/components/research/__tests__/ProviderSelector.test.tsx
    frontend/src/components/research/__tests__/ResearchProgress.test.tsx
    frontend/src/hooks/__tests__/useResearchStream.test.ts
    frontend/tests/uat/playwright/research_cancel.spec.ts
  </files>
  <read_first>
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-UI-SPEC.md §Surface 1 (FULL)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-UI-SPEC.md §Component Inventory
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-RESEARCH.md §Pattern 14
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-RESEARCH.md §Pitfall 9 (dual-shape SSE — see REVIEWS fix #3 conditional)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-REVIEWS.md "Recommended Action Before Execution" #3 #5 #7 + soft codex
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-03-SUMMARY.md (WARNING 3 verdict — drives REVIEWS fix #3 conditional)
    - frontend/src/hooks/useRenderStream.ts
    - frontend/src/components/projects/NewProjectModal.tsx
    - frontend/src/stores/uiStore.ts (temporal.pause/resume)
    - frontend/src/api/useProviders.ts (Task 1)
  </read_first>
  <behavior>
    - useResearchStream:
      - Conditional dual-shape per Plan 03 verdict (REVIEWS fix #3); default to structured-envelope-only path
      - Wraps in temporal.pause/resume
      - **REVIEWS fix #7**: maps `AbortError` to terminal `{phase: 'failed', error_code: 'aborted', error_message: 'Pesquisa cancelada pelo usuário.'}` — distinct from network errors
      - Subscribe/unsubscribe API
    - ResearchDialog:
      - 4 fields + cache-hit microcopy + CTA state machine + 1.2s auto-close on success
      - **REVIEWS soft codex**: Claude CLI piggyback microcopy reads `Tentando token do Claude CLI…` followed by fallback hint `Se rejeitado, voltamos para a chave salva no DB.` (NOT "auto-detected")
    - ProviderSelector:
      - Disabled state + tooltip
      - **REVIEWS fix #5**: reads `available_models` from useProviders; applies ordered preference `['qwen2.5:7b', 'qwen2.5-coder:14b', 'gemma4:26b', 'deepseek-r1:14b']`; first match wins; falls back to first available when none match; shows PT-BR hint when preferred missing
    - ResearchProgress:
      - 4 stage rows + retry inline notice
      - **REVIEWS fix #7**: terminal `failed`+`aborted` state renders label `Cancelada` (NOT `Erro`); other failure error_codes still render `Erro`
  </behavior>
  <action>
    1. Create `frontend/src/hooks/useResearchStream.ts` per RESEARCH §Pattern 14 with REVIEWS fixes:

       ```typescript
       import { useTemporalStore } from '../stores/temporalAccess'  // existing pattern

       export type StreamPhase = 'idle' | 'starting' | 'running' | 'succeeded' | 'failed'

       export interface StreamState {
         phase: StreamPhase
         currentStage?: 'kingdoms' | 'duchies' | 'condados' | 'baronies'
         retryAttempt?: { current: number; max: number }
         error_code?: string                     // REVIEWS fix #7 — 'aborted' | 'network' | 'validation' | ...
         error_message?: string                  // REVIEWS fix #7 — human-readable PT-BR
       }

       export function useResearchStream(runId: string | undefined) {
         // ... EventSource lifecycle ...

         // REVIEWS fix #7 — AbortError → failed/aborted terminal state
         const handleStreamError = (e: Event) => {
           if (e instanceof DOMException && e.name === 'AbortError') {
             setState({
               phase: 'failed',
               error_code: 'aborted',
               error_message: 'Pesquisa cancelada pelo usuário.',
             })
             return
           }
           // Other errors → network/unknown
           setState({
             phase: 'failed',
             error_code: 'network',
             error_message: 'Falha de rede durante a pesquisa.',
           })
         }

         // REVIEWS fix #3 — conditional dual-shape based on Plan 03 verdict
         // Default path: structured-envelope only (verdict b). If WARNING 3 in
         // 07-03-SUMMARY.md says (a), add a fallback parser branch.
         const handleMessage = (ev: MessageEvent) => {
           try {
             const data = JSON.parse(ev.data)
             // structured envelope: {event_type, stage, message, progress, ...}
             dispatchStructured(data)
           } catch {
             // REVIEWS fix #3 path (verdict a only): raw PT-BR "Tentativa N/M" passthrough.
             // If Plan 03 SUMMARY confirms verdict (b), DELETE this branch.
             // (Default: keep as structured-only; this branch unreachable.)
           }
         }
       }
       ```

    2. Create ResearchDialog with softened CLI-piggyback microcopy:

       ```tsx
       // REVIEWS soft codex — softened CLI-piggyback microcopy
       {provider === 'claude' && (
         <Text size="1" color="gray">
           Tentando token do Claude CLI… <em>Se rejeitado, voltamos para a chave salva no DB.</em>
         </Text>
       )}
       ```

       Plus all existing behaviors: Dialog.Root + 4 fields + auto-close on success + temporal.pause/resume integration via useResearchStream.

    3. Create ProviderSelector with REVIEWS fix #5 ordered-preference default selection:

       ```tsx
       const MODEL_PREFERENCE_ORDER = ['qwen2.5:7b', 'qwen2.5-coder:14b', 'gemma4:26b', 'deepseek-r1:14b']

       function pickDefaultModel(availableModels: string[] | undefined): { model: string; hint?: string } {
         if (!availableModels || availableModels.length === 0) {
           return { model: '', hint: 'Nenhum modelo Ollama instalado. Execute "ollama pull qwen2.5:7b".' }
         }
         for (const pref of MODEL_PREFERENCE_ORDER) {
           if (availableModels.includes(pref)) {
             const hint = pref !== MODEL_PREFERENCE_ORDER[0]
               ? `Modelo padrão qwen2.5:7b não encontrado — usando ${pref}. Execute "ollama pull qwen2.5:7b" para o melhor resultado.`
               : undefined
             return { model: pref, hint }
           }
         }
         return {
           model: availableModels[0],
           hint: `Nenhum modelo da lista de preferência encontrado — usando ${availableModels[0]}. Execute "ollama pull qwen2.5:7b" para o melhor resultado.`,
         }
       }
       ```

       Consume `useProviders()` to obtain the Ollama entry's `available_models`, then call `pickDefaultModel(ollama.available_models)`. Render the hint as a `<Text size="1" color="orange">` below the model TextField.

    4. Create ResearchProgress with REVIEWS fix #7 Cancelada terminal state:

       ```tsx
       // Failure rendering — distinguish Cancelada (intentional) from Erro (unexpected)
       {state.phase === 'failed' && state.error_code === 'aborted' && (
         <Text size="2" color="gray">Cancelada</Text>
       )}
       {state.phase === 'failed' && state.error_code !== 'aborted' && (
         <Text size="2" color="red">Erro: {state.error_message ?? 'desconhecido'}</Text>
       )}
       ```

    5. Vitest tests:
       - ResearchDialog ≥8 cases (incl. softened CLI-piggyback microcopy assertion)
       - ProviderSelector ≥5 cases (incl. REVIEWS fix #5: prefers qwen2.5:7b, falls back to qwen2.5-coder:14b when 7b missing, shows hint when first preference missing)
       - ResearchProgress ≥6 cases (incl. REVIEWS fix #7: aborted → "Cancelada", network error → "Erro")
       - useResearchStream ≥7 cases (incl. REVIEWS fix #7: AbortError event maps to `{phase:'failed', error_code:'aborted'}`)

    6. Create Playwright spec `frontend/tests/uat/playwright/research_cancel.spec.ts` (REVIEWS fix #7):

       ```typescript
       import { test, expect } from '@playwright/test'

       test('cancel mid-stream shows Cancelada not Erro', async ({ page }) => {
         // Setup: mock /api/v3/research/start to return runId; mock /stream to emit 2 events then pause
         await page.route('**/api/v3/research/start', async (route) => {
           await route.fulfill({ json: { run_id: 'test-run-1' } })
         })
         // ... emit kingdoms event ...
         // ... navigate to project, open dialog, submit ...
         await page.getByRole('button', { name: 'Iniciar pesquisa' }).click()
         // Wait for first progress event
         await expect(page.getByText('Reinos')).toBeVisible()
         // Cancel mid-stream
         await page.getByRole('button', { name: 'Cancelar pesquisa' }).click()
         // Assert ResearchProgress shows "Cancelada", NOT "Erro"
         await expect(page.getByText('Cancelada')).toBeVisible()
         await expect(page.getByText(/Erro:/)).not.toBeVisible()
       })
       ```
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
    - `grep -n "/api/v3/research/stop" frontend/src/components/research/ResearchDialog.tsx` returns ≥1 match
    - `grep -nE "weight=\"bold\"" frontend/src/components/research/ResearchDialog.tsx` returns 0 matches
    - `grep -n "Tentando token do Claude CLI" frontend/src/components/research/ResearchDialog.tsx` returns ≥1 match (REVIEWS soft codex — softened CLI microcopy)
    - `grep -n "auto-detectado\|auto-detected" frontend/src/components/research/ResearchDialog.tsx` returns 0 matches (REVIEWS soft codex — old language removed)
    - `grep -n "MODEL_PREFERENCE_ORDER" frontend/src/components/research/ProviderSelector.tsx` returns ≥1 match (REVIEWS fix #5)
    - `grep -nE "'qwen2.5:7b'|'qwen2.5-coder:14b'|'gemma4:26b'|'deepseek-r1:14b'" frontend/src/components/research/ProviderSelector.tsx` returns ≥4 matches (REVIEWS fix #5 — ordered preference list)
    - `grep -n "AbortError" frontend/src/hooks/useResearchStream.ts` returns ≥1 match (REVIEWS fix #7)
    - `grep -n "error_code: 'aborted'" frontend/src/hooks/useResearchStream.ts` returns ≥1 match (REVIEWS fix #7)
    - `grep -n "Pesquisa cancelada pelo usuário" frontend/src/hooks/useResearchStream.ts` returns ≥1 match (REVIEWS fix #7)
    - `grep -n "Cancelada" frontend/src/components/research/ResearchProgress.tsx` returns ≥1 match (REVIEWS fix #7)
    - File `frontend/tests/uat/playwright/research_cancel.spec.ts` EXISTS
    - `grep -n "Cancelada" frontend/tests/uat/playwright/research_cancel.spec.ts` returns ≥1 match (REVIEWS fix #7)
    - `cd frontend && npm test -- --run src/components/research src/hooks/__tests__/useResearchStream.test.ts` exits 0
  </acceptance_criteria>
  <verify>
    <automated>cd frontend && npm test -- --run src/components/research src/hooks/__tests__/useResearchStream.test.ts</automated>
  </verify>
  <done>4 components/hook land; PT-BR strings match UI-SPEC + REVIEWS softened CLI microcopy; ordered model-preference selection per REVIEWS fix #5; AbortError → Cancelada terminal state per REVIEWS fix #7 + Playwright cancel spec; conditional dual-shape SSE per Plan 03 verdict per REVIEWS fix #3; ≥21 vitest cases green.</done>
</task>

</tasks>

<context_anchors>
- **D-08** (placeholder trigger placement — wiring in Plan 09b)
- **D-09** (Radix Dialog + 4 fields + SSE)
- **UI-SPEC §Surface 1** (every copy + interaction)
- **RESEARCH §Pattern 14** (useResearchStream)
- **RESEARCH §Pitfall 9** (dual-shape SSE — now CONDITIONAL per Plan 03 verdict)
- **CLAUDE.md** (zundo temporal.pause; PT-BR UI)
- **BLOCKER 2** (meta field in useResearchOverlay)
- **BLOCKER 3** (Plan 09 does NOT touch ProjectDetail.tsx)
- **REVIEWS fix #2** (generated_at + applied_at in useResearchOverlay)
- **REVIEWS fix #3** (explicit depends_on:[03,...]; conditional dual-shape SSE driven by Plan 03 verdict)
- **REVIEWS fix #5** (ProviderSelector consumes available_models; ordered preference; missing-model hint)
- **REVIEWS fix #7** (AbortError → terminal failed/aborted; Cancelada UI; Playwright cancel spec)
- **REVIEWS soft codex** (softened CLI-piggyback microcopy)
</context_anchors>

<threat_model>

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| User input → paste-API-key field | Untrusted text typed into the dialog |
| /providers response → ProviderSelector | Trusted backend payload (incl. available_models) |
| SSE stream → useResearchStream | Untrusted LLM tokens to UI; abort handling distinct from network errors |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-09a-01 | Information Disclosure | Paste-API-key field echo | mitigate | `<TextField.Root type="password">`. Acceptance: `grep -nE "type=\"password\"" frontend/src/components/research/ResearchDialog.tsx` returns ≥1. |
| T-07-09a-02 | Information Disclosure | API key persistence | mitigate | No localStorage/sessionStorage of key. Acceptance: grep returns 0 matches. |
| T-07-09a-03 | XSS via SSE content | ResearchProgress | mitigate | All stage labels rendered as React text. `grep -n "dangerouslySetInnerHTML"` returns 0. |
| T-07-09a-04 | DoS | EventSource auto-reconnect storm | mitigate | useResearchStream explicit subscribe/unsubscribe; cleanup on unmount tested. |
| **T-07-09a-05 (REVIEWS fix #7)** | Denial of Service (UX-level) | Stuck "running" state after AbortError | mitigate | useResearchStream maps `AbortError` to terminal `{phase:'failed', error_code:'aborted'}`. ResearchProgress renders `Cancelada`. Playwright spec `research_cancel.spec.ts` exercises mid-stream cancel. Acceptance: `grep -n "AbortError"`, `grep -n "error_code: 'aborted'"`, Playwright spec passes. |

</threat_model>

<verification>
- `cd frontend && npm test -- --run src/api src/components/research src/hooks/__tests__/useResearchStream.test.ts` exits 0
- `cd frontend && npm run build` exits 0 (after Plan 09b lands)
- `cd frontend && npx playwright test research_cancel.spec.ts` exits 0 (REVIEWS fix #7)
- `grep -n "weight=\"bold\"" frontend/src/components/research/*.tsx` returns 0 matches
- `grep -n "dangerouslySetInnerHTML" frontend/src/components/research/*.tsx` returns 0 matches
- `grep -nE "type=\"password\"" frontend/src/components/research/ResearchDialog.tsx` returns ≥1 match
- `grep -n "AbortError" frontend/src/hooks/useResearchStream.ts` returns ≥1 match (REVIEWS fix #7)
- `grep -n "available_models" frontend/src/components/research/ProviderSelector.tsx` returns ≥1 match (REVIEWS fix #5)
- `grep -n "generated_at" frontend/src/api/useResearchOverlay.ts` returns 1 match (REVIEWS fix #2)
- `grep -n "applied_at" frontend/src/api/useResearchOverlay.ts` returns 1 match (REVIEWS fix #2)
</verification>

<success_criteria>
- Hooks + dialog + sub-components ready for Plan 09b to mount
- PT-BR strings verbatim from UI-SPEC §Copywriting + REVIEWS soft codex softened CLI microcopy
- useResearchOverlay returns meta with both timestamps per REVIEWS fix #2
- ProviderSelector applies ordered model preference per REVIEWS fix #5
- AbortError mapped to terminal failed/aborted with Cancelada UI per REVIEWS fix #7
- Conditional dual-shape SSE driven by Plan 03 verdict per REVIEWS fix #3
- Playwright research_cancel.spec.ts passes
</success_criteria>

<output>
After completion, create `.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-09a-SUMMARY.md` per the standard template.
</output>
