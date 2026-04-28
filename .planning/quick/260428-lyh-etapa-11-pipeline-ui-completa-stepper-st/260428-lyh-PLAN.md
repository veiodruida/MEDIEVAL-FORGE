---
phase: quick-260428-lyh
plan: 01
type: tdd
wave: 1
depends_on: []
files_modified:
  - frontend/src/stores/usePipelineStore.ts
  - frontend/src/stores/__tests__/usePipelineStore.test.ts
  - frontend/src/components/pipeline/Stepper.tsx
  - frontend/src/components/pipeline/Stepper.test.tsx
  - frontend/src/components/pipeline/StepCard.tsx
  - frontend/src/components/pipeline/StepCard.test.tsx
  - frontend/src/components/pipeline/ProviderEffortPicker.tsx
  - frontend/src/components/pipeline/ProviderEffortPicker.test.tsx
  - frontend/src/pages/ProjectDetail.tsx
autonomous: true
requirements:
  - ETAPA-11-PIPELINE-UI
must_haves:
  truths:
    - "User sees a 5-node Stepper at the top of ProjectDetail with visual states pending/active/done/error"
    - "User sees a single active StepCard below the Stepper, matching usePipelineStore.currentStep"
    - "Each StepCard reuses the existing per-step component (BaronyGranularitySlider, AssignmentEditor, CodexViewer) — not a rewrite"
    - "Steps 3 and 5 expose a ProviderEffortPicker (provider radio + effort segmented control)"
    - "Existing pipeline handlers (ingest, generate, openResearchDialog, exportZip) keep working — wired through StepCards"
    - "usePipelineStore holds currentStep (1..5) and per-step {status, providerId?, effort?, output?} and is undo-immune (no zundo)"
  artifacts:
    - path: "frontend/src/stores/usePipelineStore.ts"
      provides: "Zustand store with currentStep + steps map"
      contains: "create<PipelineState>"
    - path: "frontend/src/components/pipeline/Stepper.tsx"
      provides: "5-node stepper with status visuals"
      min_lines: 30
    - path: "frontend/src/components/pipeline/StepCard.tsx"
      provides: "Padded card wrapper rendering active step content"
      min_lines: 20
    - path: "frontend/src/components/pipeline/ProviderEffortPicker.tsx"
      provides: "Provider radio + effort segmented control composed from ProviderSelector"
      min_lines: 30
    - path: "frontend/src/pages/ProjectDetail.tsx"
      provides: "Refactored layout using Stepper + StepCard"
      contains: "Stepper"
  key_links:
    - from: "frontend/src/pages/ProjectDetail.tsx"
      to: "usePipelineStore"
      via: "useStore selector"
      pattern: "usePipelineStore"
    - from: "frontend/src/components/pipeline/StepCard.tsx"
      to: "BaronyGranularitySlider | AssignmentEditor | CodexViewer"
      via: "child rendering per currentStep"
      pattern: "(BaronyGranularitySlider|AssignmentEditor|CodexViewer)"
    - from: "frontend/src/components/pipeline/ProviderEffortPicker.tsx"
      to: "ProviderSelector"
      via: "composition"
      pattern: "ProviderSelector"
---

<objective>
Etapa 11 do plano hazy-hatching-abelson: refatorar a UI do ProjectDetail para um pipeline visual de 5 etapas (Stepper + StepCards) com store global Zustand e ProviderEffortPicker reutilizável.

Purpose: Fechar a UI do pipeline CK3 — usuário vê claramente a etapa atual, o status de cada etapa, e escolhe provider+effort por etapa de IA. Não reescrever lógica de pipeline; apenas embrulhar handlers existentes em uma camada de layout.

Output:
- `usePipelineStore.ts` (Zustand) com currentStep e steps.
- 3 novos componentes em `components/pipeline/`: Stepper, StepCard, ProviderEffortPicker.
- ProjectDetail refatorado para consumir o store + componentes.
- Testes Vitest para store + cada componente (RED → GREEN).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/PROJECT.md
@./CLAUDE.md
@C:/Users/veio_/.claude/plans/hazy-hatching-abelson.md

# Componentes-alvo de reuso
@frontend/src/components/ingest/BaronyGranularitySlider.tsx
@frontend/src/components/research/AssignmentEditor.tsx
@frontend/src/components/codex/CodexViewer.tsx
@frontend/src/components/research/ProviderSelector.tsx

# Layout atual a refatorar
@frontend/src/pages/ProjectDetail.tsx

# Convenções de store
@frontend/src/stores/useResearchStore.ts
@frontend/src/stores/useEditorStore.ts

<interfaces>
<!-- Contracts the executor needs. Use these directly; do not re-explore the codebase. -->

## PipelineState (NEW — define in usePipelineStore.ts)

```typescript
export type StepId = 1 | 2 | 3 | 4 | 5;
export type StepStatus = 'pending' | 'active' | 'done' | 'error';
export type Effort = 'low' | 'medium' | 'high';

export interface StepBase {
  status: StepStatus;
  output?: unknown;
  error?: string;
}
export interface AIStep extends StepBase {
  providerId?: string;
  effort?: Effort;
}

export interface PipelineSteps {
  osm:       StepBase;                         // Step 1 (no AI)
  baronies:  StepBase & { granularity: number | 'all' }; // Step 2 (no AI)
  research:  AIStep & { edited?: boolean };    // Step 3 (AI)
  map:       StepBase;                         // Step 4 (no AI)
  codex:     AIStep & { sections?: Record<string, StepStatus> }; // Step 5 (AI)
}

export interface PipelineState {
  currentStep: StepId;
  steps: PipelineSteps;
  setCurrentStep: (s: StepId) => void;
  setStepStatus: (key: keyof PipelineSteps, status: StepStatus) => void;
  setStepProvider: (key: 'research' | 'codex', providerId: string, effort: Effort) => void;
  setBaroniesGranularity: (g: number | 'all') => void;
  reset: () => void;
}
```

## ProviderEffortPicker props (NEW)

```typescript
interface ProviderEffortPickerProps {
  providerId: string;
  effort: 'low' | 'medium' | 'high';
  onProviderChange: (id: string) => void;
  onEffortChange: (e: 'low' | 'medium' | 'high') => void;
}
```

## Stepper props (NEW)

```typescript
interface StepperProps {
  currentStep: 1 | 2 | 3 | 4 | 5;
  statuses: { osm: StepStatus; baronies: StepStatus; research: StepStatus; map: StepStatus; codex: StepStatus };
  onStepClick?: (s: 1 | 2 | 3 | 4 | 5) => void; // optional jump
}
```

Step labels (PT-BR, fixed):
1. "OSM"  2. "Baronies"  3. "Pesquisa"  4. "Mapa"  5. "Codex"

## StepCard props (NEW)

```typescript
interface StepCardProps {
  title: string;
  description?: string;
  children: React.ReactNode;     // step body (slider | editor | viewer | actions)
  footer?: React.ReactNode;      // action button row
}
```

## ProviderSelector (existing, reuse)

```typescript
// frontend/src/components/research/ProviderSelector.tsx
export function ProviderSelector(props: { value: string; onChange: (id: string) => void }): JSX.Element;
```

## Existing handlers in ProjectDetail (preserve)

- `useIngestStream(id).start('osm')` → Step 1
- `useGenerate(id).mutate(territory)` → Step 4
- `openResearchDialog(...)` from `useResearchStore` → Step 3 trigger
- `useExport(id).mutate()` → post-Step 5 (export not in stepper, keep existing card)
- `BaronyGranularitySlider` already exists → Step 2 body
- `AssignmentEditor` already exists → Step 3 body (after research returns)
- `CodexViewer` already exists → Step 5 body
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1 (RED + GREEN): usePipelineStore + Stepper</name>
  <files>
    frontend/src/stores/usePipelineStore.ts,
    frontend/src/stores/__tests__/usePipelineStore.test.ts,
    frontend/src/components/pipeline/Stepper.tsx,
    frontend/src/components/pipeline/Stepper.test.tsx
  </files>
  <behavior>
    usePipelineStore tests:
      - default state: currentStep=1, every step.status='pending' except none active by default
      - setCurrentStep(3) updates currentStep to 3
      - setStepStatus('research','done') sets steps.research.status='done'
      - setStepProvider('research','llamacpp','high') sets providerId+effort
      - setBaroniesGranularity(250) sets steps.baronies.granularity=250
      - reset() returns to default state

    Stepper tests:
      - renders 5 nodes with labels OSM/Baronies/Pesquisa/Mapa/Codex
      - node with status='done' shows the done indicator (data-status="done")
      - node with status='active' shows the active indicator (data-status="active")
      - node with status='error' shows the error indicator (data-status="error")
      - clicking a node calls onStepClick with that step number
      - currentStep node has aria-current="step"
  </behavior>
  <action>
    1. Write `frontend/src/stores/__tests__/usePipelineStore.test.ts` with the cases above. Run `npm test -- usePipelineStore` and confirm RED.
    2. Implement `frontend/src/stores/usePipelineStore.ts` using `zustand` (mirror conventions of `useResearchStore.ts` — no zundo middleware: pipeline state must NOT participate in undo/redo). Default state:
       - currentStep: 1
       - steps: { osm:{status:'pending'}, baronies:{status:'pending', granularity:250}, research:{status:'pending'}, map:{status:'pending'}, codex:{status:'pending', sections:{}} }
    3. Run tests → GREEN.
    4. Write `frontend/src/components/pipeline/Stepper.test.tsx` (Vitest + @testing-library/react) for the 6 cases above. Use the labels exactly as listed. Render with `<Theme>` wrapper from @radix-ui/themes only if needed by child primitives.
    5. Implement `frontend/src/components/pipeline/Stepper.tsx`:
       - Flex row with 5 nodes connected by horizontal line segments.
       - Each node = circular Box (data-status={status}) + Text label below.
       - Visual mapping: pending=gray-5, active=accent-9 with ring, done=green-9 with check, error=red-9 with cross.
       - If onStepClick provided, the node is clickable (button element, type="button").
       - Apply `aria-current="step"` to the node matching `currentStep`.
       - No external icon libs — use unicode glyphs (✓, ✕, ⚙, ○) inside the Box.
    6. Run tests → GREEN.
    7. Commit: `test(quick-260428-lyh-01): add failing tests for usePipelineStore + Stepper` then `feat(quick-260428-lyh-01): usePipelineStore + Stepper component (5-node visual pipeline)`.
  </action>
  <verify>
    <automated>cd frontend && npm test -- usePipelineStore Stepper</automated>
  </verify>
  <done>
    usePipelineStore exports the PipelineState interface. Stepper renders 5 labelled nodes with data-status attribute reflecting status. All new tests pass. Existing 200 frontend tests still pass.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2 (RED + GREEN): StepCard + ProviderEffortPicker</name>
  <files>
    frontend/src/components/pipeline/StepCard.tsx,
    frontend/src/components/pipeline/StepCard.test.tsx,
    frontend/src/components/pipeline/ProviderEffortPicker.tsx,
    frontend/src/components/pipeline/ProviderEffortPicker.test.tsx
  </files>
  <behavior>
    StepCard tests:
      - renders title text
      - renders description when provided
      - renders children content
      - renders footer slot when provided (and not when omitted)

    ProviderEffortPicker tests:
      - renders ProviderSelector with current providerId (mock useProvidersQuery to return 2 providers including 'llamacpp')
      - renders 3 effort buttons: Baixo / Médio / Alto, marking the current effort with data-active="true"
      - clicking a different effort button calls onEffortChange with the new value ('low'|'medium'|'high')
      - changing provider via ProviderSelector triggers onProviderChange
  </behavior>
  <action>
    1. Write `StepCard.test.tsx` and `ProviderEffortPicker.test.tsx` per the cases above. Run → RED.
    2. Implement `StepCard.tsx`:
       - Radix `<Card>` containing Heading (title) + optional Text (description) + Box (children) + optional Flex (footer).
       - Use existing Radix Themes primitives (Card, Heading, Text, Box, Flex) — already imported across the codebase.
    3. Implement `ProviderEffortPicker.tsx`:
       - Compose `<ProviderSelector value={providerId} onChange={onProviderChange} />` from `../research/ProviderSelector`.
       - Below it, a SegmentedControl-equivalent: 3 `<Button>` (variant 'soft' inactive / 'solid' active) with data-active attribute. Labels in PT-BR: Baixo, Médio, Alto. Map labels to 'low'|'medium'|'high'.
       - Layout: `<Flex direction="column" gap="3">` wrapping provider section and effort section.
    4. Run tests → GREEN.
    5. Commit: `test(quick-260428-lyh-01): add failing tests for StepCard + ProviderEffortPicker` then `feat(quick-260428-lyh-01): StepCard + ProviderEffortPicker (composes ProviderSelector + effort segmented control)`.
  </action>
  <verify>
    <automated>cd frontend && npm test -- StepCard ProviderEffortPicker</automated>
  </verify>
  <done>
    StepCard renders structurally as title/description/children/footer. ProviderEffortPicker exposes both provider and effort changes via callbacks. Tests pass.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3 (GREEN): Refactor ProjectDetail to use Stepper + StepCard + store</name>
  <files>
    frontend/src/pages/ProjectDetail.tsx
  </files>
  <behavior>
    Manual + smoke behavior (covered by `npm run build` + existing ProjectDetail-adjacent tests):
      - Top of page: Stepper showing 5 steps. currentStep comes from usePipelineStore.
      - Below stepper: a single StepCard rendering only the active step's body:
        * Step 1 (osm): keeps existing OSM ingest button + log block; on success → store.setStepStatus('osm','done') + setCurrentStep(2)
        * Step 2 (baronies): renders <BaronyGranularitySlider> bound to steps.baronies.granularity; "Gerar Baronies" button (existing handler if present, otherwise leaves a TODO console.warn — DO NOT touch backend)
        * Step 3 (research): renders <ProviderEffortPicker> bound to steps.research.{providerId,effort}; existing "Pesquisa histórica" button calls openResearchDialog; once research finishes (existing useResearchStore signal), shows <AssignmentEditor>
        * Step 4 (map): existing "Gerar mapa" button (generate.mutate); preview block remains rendered below as today
        * Step 5 (codex): renders <ProviderEffortPicker> bound to steps.codex.{providerId,effort}; renders <CodexViewer projectId={project.id}/>; "Gerar Codex" button is a stub that calls a TODO handler (backend wiring NOT in scope)
      - Existing post-generation Card (Mapa gerado / Exportar ZIP) and InspectorSidebar/CanvasViewer blocks remain UNCHANGED — they are below the pipeline section.
      - The legacy "Aba Pipeline / Aba Estrutura política" Tabs.Root block is REMOVED — replaced by the new pipeline UI.
      - Existing handlers (ingest, generate, exportZip, openResearchDialog) remain intact and fully wired.
  </behavior>
  <action>
    1. Refactor `frontend/src/pages/ProjectDetail.tsx`:
       a. Add import for `usePipelineStore`, `Stepper`, `StepCard`, `ProviderEffortPicker`, `BaronyGranularitySlider`, `AssignmentEditor`, `CodexViewer`.
       b. Read state: `const { currentStep, steps, setCurrentStep, setStepStatus, setStepProvider, setBaroniesGranularity } = usePipelineStore()`.
       c. Replace the existing `<Card><Tabs.Root>...</Tabs.Root></Card>` block (lines ~270-467 in current file) with:
          - `<Stepper currentStep={currentStep} statuses={...} onStepClick={setCurrentStep} />`
          - A switch on `currentStep` rendering one `<StepCard>`:
            - title PT-BR per step ("1. Ingerir OSM", "2. Gerar Baronies", "3. Pesquisa Histórica", "4. Gerar Mapa", "5. Codex Histórico")
            - description: short explanatory text per step
            - children: the per-step body described above
            - footer: the per-step primary action button (preserving the existing onClick handlers)
       d. Wire effects so existing status transitions update the store:
          - useEffect on `ingest.isStreaming` end + `ingestStatus.data?.has_polygons` → setStepStatus('osm','done')
          - useEffect on project.status==='generated' → setStepStatus('map','done')
          - On openResearchDialog success path (existing useResearchStore — read its result if exposed; otherwise leave a TODO comment and just set status='active' on click)
       e. Keep the "Mapa gerado" preview Card, EditToolbar, CanvasViewer, InspectorSidebar, and the export Card intact below the pipeline section.
       f. Remove the unused `TerritoryEditor`/`Tabs.Root` imports if no longer referenced.
    2. Run `cd frontend && npm run build` — must compile clean (TypeScript valid).
    3. Run `cd frontend && npm test` — all 200 existing tests + new ones must pass.
    4. Commit: `feat(quick-260428-lyh-01): refactor ProjectDetail to Stepper + StepCard + usePipelineStore`.
  </action>
  <verify>
    <automated>cd frontend && npm run build && npm test</automated>
  </verify>
  <done>
    ProjectDetail renders Stepper at top + single active StepCard. All existing handlers (ingest, generate, openResearchDialog, export) still fire correctly. usePipelineStore reflects status changes. `npm run build` clean. Test suite green (>= prior count + ~12 new tests).
  </done>
</task>

</tasks>

<verification>
- All Vitest tests pass: `cd frontend && npm test` — 200 prior + ~12 new = ≥212 passing.
- TypeScript build clean: `cd frontend && npm run build`.
- No backend files modified (grep `git diff --name-only` shows only `frontend/**`).
- Manual smoke (Game Designer): open existing Iberia project — sees Stepper at top with step 1 active, can click step 2/3/4/5 and StepCard body changes; existing OSM ingestion still works; existing AssignmentEditor still opens after research.
</verification>

<success_criteria>
- usePipelineStore exposes currentStep + steps with the documented shape; tests cover defaults, transitions, and reset.
- Stepper visually distinguishes pending/active/done/error states (data-status attribute) and supports onStepClick.
- StepCard is a layout primitive (title + optional description + children + optional footer).
- ProviderEffortPicker composes ProviderSelector and adds an effort segmented control with low/medium/high.
- ProjectDetail uses the new components; legacy Pipeline/Estrutura política Tabs block is removed.
- Existing handlers (ingest, generate, openResearchDialog, exportZip) remain wired; no regression in existing tests.
- 3 atomic commits: (a) test+impl store+Stepper, (b) test+impl StepCard+Picker, (c) ProjectDetail refactor — matches "3 commits, frontend tests" from hazy-hatching-abelson section H step 11.
</success_criteria>

<output>
After completion, create `.planning/quick/260428-lyh-etapa-11-pipeline-ui-completa-stepper-st/260428-lyh-SUMMARY.md` recording:
- Files created (5 src + 4 test)
- Files modified (ProjectDetail.tsx)
- Test count delta
- Commits (3 expected)
- Any deviations from this plan
</output>
</content>
</invoke>