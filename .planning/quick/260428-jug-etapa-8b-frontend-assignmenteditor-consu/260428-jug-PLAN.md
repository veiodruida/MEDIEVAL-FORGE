---
phase: quick-260428-jug
plan: 01
type: execute
wave: 1
depends_on: []
subsystem: frontend-research
tags: [research, assignments, edit, etapa-8b, frontend, radix-themes, tdd]
files_modified:
  - frontend/src/api/edit.ts
  - frontend/src/components/research/AssignmentEditor.tsx
  - frontend/src/components/research/AssignmentEditor.test.tsx
  - frontend/src/components/research/ResearchDialog.tsx
autonomous: true
requirements:
  - quick-260428-jug — Etapa 8b: Frontend AssignmentEditor consumes PATCH /api/projects/{id}/research/assignments
must_haves:
  truths:
    - "User clicks 'Editar assignments' in ResearchDialog success state and AssignmentEditor opens"
    - "User sees current barony→condado mappings (each barony row shows correct condado in Select)"
    - "User sees current condado names + duchy_id (TextField + Select per row)"
    - "Changing a barony's condado selection enables Salvar button"
    - "Clicking Salvar builds delta payload (only changed fields), calls PATCH endpoint"
    - "On success: useResearchStore.setManualResult(result) updates store with returned result; dialog closes"
    - "On backend error: Callout displays error message (truncated to 600 chars to match backend)"
    - "When no changes made: Salvar button disabled"
  artifacts:
    - path: "frontend/src/api/edit.ts"
      provides: "patchResearchAssignments(projectId, body) function"
      contains: "patchResearchAssignments"
    - path: "frontend/src/components/research/AssignmentEditor.tsx"
      provides: "AssignmentEditor dialog component (Radix Dialog.Root)"
      contains: "AssignmentEditor"
    - path: "frontend/src/components/research/AssignmentEditor.test.tsx"
      provides: "5 vitest+RTL tests covering render/move/rename/error/success"
      contains: "describe"
    - path: "frontend/src/components/research/ResearchDialog.tsx"
      provides: "Editar assignments button wired to AssignmentEditor when manualResult exists"
      contains: "AssignmentEditor"
  key_links:
    - from: "frontend/src/components/research/AssignmentEditor.tsx"
      to: "frontend/src/api/edit.ts"
      via: "import { patchResearchAssignments }"
      pattern: "patchResearchAssignments"
    - from: "frontend/src/components/research/AssignmentEditor.tsx"
      to: "frontend/src/stores/useResearchStore.ts"
      via: "useResearchStore.setManualResult on success"
      pattern: "setManualResult"
    - from: "frontend/src/components/research/ResearchDialog.tsx"
      to: "frontend/src/components/research/AssignmentEditor.tsx"
      via: "conditional render in success/cached state"
      pattern: "<AssignmentEditor"
---

<objective>
Build the frontend AssignmentEditor that consumes the backend PATCH /research/assignments endpoint
delivered in Etapa 8 (quick-260428-h1t). Game Designer can now edit barony→condado assignments and
rename/reparent condados without leaving the canvas; edits flow back to the cache row and feed
subsequent /generate calls.

Purpose: Close the loop on Etapa 8 — backend endpoint is live but unused without UI. After this
plan, the manual research flow + LLM research flow both have post-research editability.

Output:
- API client: `patchResearchAssignments` in `frontend/src/api/edit.ts`
- New component: `AssignmentEditor.tsx` (Radix Dialog) + tests
- Wiring: `ResearchDialog.tsx` mounts an "Editar assignments" button when result exists
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/quick/260428-h1t-etapa-8-patch-research-assignments-endpo/260428-h1t-SUMMARY.md
@frontend/src/api/edit.ts
@frontend/src/api/research.ts
@frontend/src/stores/useResearchStore.ts
@frontend/src/components/research/ResearchDialog.tsx
@frontend/src/components/research/ResearchDialog.test.tsx
@backend/medieval_forge/schemas.py
@backend/medieval_forge/services/llm/schemas.py

<interfaces>
<!-- Contracts the executor needs. Embedded so no codebase scavenger hunt. -->

Backend request/response (Etapa 8 — quick-260428-h1t):
PATCH /api/projects/{project_id}/research/assignments
Request body (at least one field required):
```json
{
  "barony_assignments": { "B_2": "C_BURGOS" },                       // optional: barony_id -> condado_id delta
  "condado_renames": {                                                // optional: condado_id -> {name?, duchy_id?}
    "C_LEON": { "name": "Reino de León", "duchy_id": "D_LEON" }
  }
}
```
Response 200: `{"result": <MapResearchResult dict>}` — extract `.result`.
Errors: 400 (unknown barony id, unknown duchy_id, MapResearchResult validation — body up to 600 chars
of truncated Pydantic error). 404 (no cache row). 422 (bad request shape).

MapResearchResult shape (the `result` field — backend/medieval_forge/services/llm/schemas.py):
```ts
type Duchy = { kingdom_id: string; name: string };
type MapCondado = { id: string; name: string; kingdom_id: string; duchy_id: string };
type MapResearchResult = {
  kingdoms: Record<string, string>;            // id -> display_name
  duchies: Record<string, Duchy>;              // id -> Duchy
  condados: MapCondado[];                       // NO coords (centroids derived later)
  barony_assignments: Record<string, string>;  // barony_id -> condado_id
};
```

NOTE: The existing `ResearchResult` type in `frontend/src/api/research.ts` was the OLD pre-Etapa-3
shape (`condados_assignment` + per-condado `baronies`). It is now stale relative to
`MapResearchResult`. For this plan we DO NOT refactor `useResearchStore.manualResult` — instead the
new `AssignmentEditor` accepts a `MapResearchResult`-shaped prop, and we add a local type alias
`MapResearchResult` in `frontend/src/api/research.ts` (or in the component file). The store-wide
type unification is out of scope (deferred to a follow-up quick task).

Existing patchJson pattern (frontend/src/api/edit.ts lines 41-52):
```ts
async function patchJson<TReq, TRes>(path: string, body: TReq): Promise<TRes> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new EditApiError(res.status, text);
  }
  return res.json() as Promise<TRes>;
}
```

useResearchStore relevant slice:
```ts
manualResult: ResearchResult | null;
setManualResult: (result: ResearchResult | null) => void;
```

Test wrapper pattern (from ResearchDialog.test.tsx, lines 10-20):
```tsx
function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <Theme>{children}</Theme>
    </QueryClientProvider>
  );
  return { Wrapper, qc };
}
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: RED — write 5 failing AssignmentEditor tests + add patchResearchAssignments stub</name>
  <files>
    frontend/src/api/edit.ts,
    frontend/src/components/research/AssignmentEditor.tsx,
    frontend/src/components/research/AssignmentEditor.test.tsx
  </files>
  <behavior>
    Test fixture (use these exact ids/values — descriptive + numeric per project memory):
    ```ts
    const FIXTURE: MapResearchResult = {
      kingdoms: { K_LEON: "Reino de León" },
      duchies: {
        D_LEON: { kingdom_id: "K_LEON", name: "Ducado de León" },
        D_BURGOS: { kingdom_id: "K_LEON", name: "Ducado de Burgos" },
      },
      condados: [
        { id: "C_LEON", name: "Condado de León", kingdom_id: "K_LEON", duchy_id: "D_LEON" },
        { id: "C_BURGOS", name: "Condado de Burgos", kingdom_id: "K_LEON", duchy_id: "D_BURGOS" },
      ],
      barony_assignments: { B_1: "C_LEON", B_2: "C_LEON", B_3: "C_BURGOS" },
    };
    ```

    Tests (each describes WHAT and uses explicit numeric fixtures — per CLAUDE.md memory feedback):

    - Test 1 — `renders all barony rows with correct current condado in Select`:
      Render `<AssignmentEditor open={true} onOpenChange={vi.fn()} projectId="p1" researchResult={FIXTURE} />`.
      Assert each barony row (B_1, B_2, B_3) is visible AND each Select shows the correct current condado
      label — B_1 → "Condado de León", B_2 → "Condado de León", B_3 → "Condado de Burgos".

    - Test 2 — `changing a barony's condado then Salvar calls PATCH with only the changed barony`:
      Mock `global.fetch` returning `{ result: { ...FIXTURE, barony_assignments: { B_1: "C_LEON", B_2: "C_BURGOS", B_3: "C_BURGOS" } } }`.
      User changes B_2's Select from "C_LEON" to "C_BURGOS"; clicks Salvar.
      Assert `fetch` called with `/api/projects/p1/research/assignments`, method `PATCH`,
      and JSON body deep-equals `{ barony_assignments: { B_2: "C_BURGOS" } }` — only the delta, not full map.

    - Test 3 — `renaming a condado then Salvar sends only that rename`:
      User edits the TextField for C_LEON from "Condado de León" to "Reino Antigo de León"; clicks Salvar.
      Assert fetch body deep-equals `{ condado_renames: { C_LEON: { name: "Reino Antigo de León" } } }` —
      duchy_id NOT included because unchanged.

    - Test 4 — `backend 400 displays Callout with truncated error`:
      Mock fetch returning `Response(text="barony_assignments reference unknown ids: ['B_99']", status=400)`.
      User makes any change, clicks Salvar.
      Assert a Radix Callout (role="alert" or `data-radix-themes` Callout) renders containing the
      error text. Assert dialog stays open. Assert truncation: passing a 1000-char error string,
      rendered text length ≤ 600 chars.

    - Test 5 — `success calls setManualResult with returned result and onOpenChange(false)`:
      Mock fetch 200 with `{ result: <updated FIXTURE> }`.
      Spy on `useResearchStore.getState().setManualResult` (or pass via store). User makes a change,
      clicks Salvar. After awaiting, assert `setManualResult` was called once with the returned
      `result` object (deep-equal to mocked response.result), and `onOpenChange(false)` was called.

    Additional invariant covered implicitly: Salvar disabled before any change (assert button
    `disabled` in initial render — Test 1 extension or as Test 0 sub-assertion).
  </behavior>
  <action>
    1. Add the `patchResearchAssignments` STUB to `frontend/src/api/edit.ts` (only signature
       + body that calls `patchJson`) so tests can import the symbol — leave it functionally
       complete in this task; the test failures will come from the missing component, not the API.
       Place AFTER `paintTerrain`. Reuse existing `patchJson` (already exported in scope of file).

       Also export a TypeScript type for `MapResearchResult` (mirroring the backend shape — see
       interfaces block). Place near the function. The store-wide `ResearchResult` type stays
       unchanged for now.

       ```ts
       export type MapResearchResult = {
         kingdoms: Record<string, string>;
         duchies: Record<string, { kingdom_id: string; name: string }>;
         condados: Array<{ id: string; name: string; kingdom_id: string; duchy_id: string }>;
         barony_assignments: Record<string, string>;
       };

       export type CondadoRename = { name?: string; duchy_id?: string };

       export interface PatchAssignmentsRequest {
         barony_assignments?: Record<string, string>;
         condado_renames?: Record<string, CondadoRename>;
       }

       /**
        * PATCH /api/projects/{id}/research/assignments — Etapa 8 (quick-260428-h1t).
        * Sends a delta (only changed barony assignments and/or condado renames).
        * Returns the updated MapResearchResult (server unwraps `{ result: ... }`).
        */
       export async function patchResearchAssignments(
         projectId: string,
         body: PatchAssignmentsRequest,
       ): Promise<MapResearchResult> {
         const res = await patchJson<PatchAssignmentsRequest, { result: MapResearchResult }>(
           `/projects/${projectId}/research/assignments`,
           body,
         );
         return res.result;
       }
       ```

    2. Create `frontend/src/components/research/AssignmentEditor.tsx` as a STUB that exports the
       symbol but renders only `null` (or a single Dialog with no content). This makes tests fail
       on assertion (RED), not on import.
       ```tsx
       import type { MapResearchResult } from "../../api/edit";
       export interface AssignmentEditorProps {
         open: boolean;
         onOpenChange: (open: boolean) => void;
         projectId: string;
         researchResult: MapResearchResult;
       }
       export function AssignmentEditor(_props: AssignmentEditorProps) {
         return null; // RED — implementation in Task 2
       }
       ```

    3. Create `frontend/src/components/research/AssignmentEditor.test.tsx` with the 5 tests
       described in <behavior>. Use the `makeWrapper()` pattern from `ResearchDialog.test.tsx`
       (QueryClientProvider + Radix Theme). Mock `global.fetch` per test (use `vi.fn()` and
       `vi.stubGlobal('fetch', ...)`); restore in `afterEach`. Use `@testing-library/user-event`
       if already a dep, else `fireEvent`.

       For Radix Select assertions: Radix renders the trigger as a button — assert via
       `screen.getByRole('combobox', { name: /barony B_2/i })` or similar accessible label. Use
       `data-testid` if Radix Select labelling proves brittle.

       For the truncation test (#4): pre-build a 1000-char error string `"x".repeat(1000)`. After
       firing Salvar, find the Callout element and assert `.textContent.length <= 600`. Component
       must explicitly slice: `errorMessage.slice(0, 600)`.

    4. Run tests — expect 5 failures (component renders null, no UI to interact with). Verify the
       failures are assertion failures (RED), not import/syntax errors.
  </action>
  <verify>
    <automated>cd frontend && npm test -- AssignmentEditor.test.tsx --run 2>&1 | tail -40</automated>
  </verify>
  <done>
    - patchResearchAssignments + types exported from frontend/src/api/edit.ts.
    - AssignmentEditor.tsx exists with prop type + null-return stub.
    - AssignmentEditor.test.tsx contains 5 tests with explicit fixtures (B_1, B_2, B_3, C_LEON, C_BURGOS).
    - npm test on the file shows 5 failing tests (RED) with assertion-style errors (not import errors).
    - Commit: `test(quick-260428-jug-01): add 5 failing tests for AssignmentEditor (RED)`
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: GREEN — implement AssignmentEditor + wire ResearchDialog button</name>
  <files>
    frontend/src/components/research/AssignmentEditor.tsx,
    frontend/src/components/research/ResearchDialog.tsx
  </files>
  <behavior>
    All 5 tests from Task 1 pass. Plus the existing ResearchDialog test suite remains green
    (no regression in ResearchDialog.test.tsx).
  </behavior>
  <action>
    1. Implement `AssignmentEditor.tsx` using Radix Themes primitives (Dialog.Root, Dialog.Content,
       Dialog.Title, Flex, Heading, Text, Button, TextField.Root, Select.Root/Trigger/Content/Item,
       Callout.Root/Text). Match ResearchDialog.tsx's styling cadence: `direction="column"` Flex,
       `gap="3"` between sections, max-width ~640.

       State (useState):
       ```ts
       // Initialize from props.researchResult; reset when researchResult identity changes
       const [draftAssignments, setDraftAssignments] = useState<Record<string, string>>(
         () => ({ ...researchResult.barony_assignments })
       );
       const [draftCondados, setDraftCondados] = useState<MapCondado[]>(
         () => researchResult.condados.map(c => ({ ...c }))
       );
       const [submitting, setSubmitting] = useState(false);
       const [error, setError] = useState<string | null>(null);
       ```

       Diff computation (only the delta is sent — Tests 2 + 3):
       ```ts
       function computeDelta(): PatchAssignmentsRequest {
         const ba: Record<string, string> = {};
         for (const [bid, cid] of Object.entries(draftAssignments)) {
           if (researchResult.barony_assignments[bid] !== cid) ba[bid] = cid;
         }
         const cr: Record<string, CondadoRename> = {};
         const original = new Map(researchResult.condados.map(c => [c.id, c]));
         for (const c of draftCondados) {
           const orig = original.get(c.id);
           if (!orig) continue; // creating new condados out of scope here
           const rename: CondadoRename = {};
           if (orig.name !== c.name) rename.name = c.name;
           if (orig.duchy_id !== c.duchy_id) rename.duchy_id = c.duchy_id;
           if (Object.keys(rename).length > 0) cr[c.id] = rename;
         }
         const out: PatchAssignmentsRequest = {};
         if (Object.keys(ba).length > 0) out.barony_assignments = ba;
         if (Object.keys(cr).length > 0) out.condado_renames = cr;
         return out;
       }
       const hasChanges = useMemo(
         () => Object.keys(computeDelta().barony_assignments ?? {}).length +
               Object.keys(computeDelta().condado_renames ?? {}).length > 0,
         [draftAssignments, draftCondados]
       );
       ```

       UI sections:
       - Heading "Atribuições de baronies" → list rendered via Flex direction="column" gap="2".
         Each row: Text (barony_id) + Select.Root (value=draftAssignments[bid], onValueChange).
         Select.Content lists all condados with label `${condado.name} (${condado.id})`.
       - Heading "Renomear condados" → list of rows. Each row: TextField.Root (name) + Select.Root
         (duchy_id) listing all duchies labeled `${duchy.name} (${duchy_id})`.
       - Footer: Callout.Root color="red" (only when error) showing `error.slice(0, 600)`. Then
         Flex justify="end" gap="2" with Cancel button (calls onOpenChange(false)) and Salvar
         button (color="blue", disabled when !hasChanges || submitting).

       Salvar handler:
       ```ts
       async function handleSave() {
         setSubmitting(true);
         setError(null);
         try {
           const result = await patchResearchAssignments(projectId, computeDelta());
           // Cast: store currently uses legacy ResearchResult — cast pragmatically;
           // unification is a separate quick task.
           useResearchStore.getState().setManualResult(result as unknown as ResearchResult);
           onOpenChange(false);
         } catch (e) {
           const raw = e instanceof Error ? e.message : String(e);
           setError(raw.slice(0, 600));
         } finally {
           setSubmitting(false);
         }
       }
       ```

       Use `data-testid` on critical elements to make tests resilient against Radix internals:
       - `data-testid="barony-row-${bid}"` on each barony row Select trigger
       - `data-testid="condado-name-${cid}"` on each TextField
       - `data-testid="condado-duchy-${cid}"` on duchy Select trigger
       - `data-testid="save-button"` on Salvar
       - `data-testid="error-callout"` on Callout when error
       Update Task 1's test selectors to match these test ids — adjust the test file as part of
       this task to use the testids (this is the GREEN convergence step).

    2. Wire `ResearchDialog.tsx`:
       - Import `AssignmentEditor` and `MapResearchResult` type from the api.
       - Add local `useState<boolean>(false)` named `editorOpen`.
       - In the "success" and "cached" render branches, after the existing summary `<Text>`, render
         a `<Button variant="soft" onClick={() => setEditorOpen(true)}>Editar assignments</Button>`
         that is enabled only when a result exists. Place it BEFORE the existing "Fechar" / "Forçar
         nova pesquisa" buttons.
       - Outside the `<Dialog.Root>` tree (next to `<AuthSetupSheet />` mount, line 427), mount:
         ```tsx
         {(stream.result || cachedQuery.data || manualResult) && (
           <AssignmentEditor
             open={editorOpen}
             onOpenChange={setEditorOpen}
             projectId={projectId}
             researchResult={(stream.result ?? cachedQuery.data ?? manualResult) as unknown as MapResearchResult}
           />
         )}
         ```
         The cast bridges legacy `ResearchResult` and new `MapResearchResult` shapes — acceptable
         because the backend has emitted the new shape since Etapa 3 (260428-ewx).
       - Add `manualResult` selector to the existing `useResearchStore` selectors at top of component.

    3. Run tests until green:
       - `npm test -- AssignmentEditor.test.tsx --run` — expect 5/5 passing.
       - `npm test -- ResearchDialog.test.tsx --run` — expect prior tests still passing.
       - `npm test --run` (full suite) — expect no regressions.

    4. Run typecheck: `npx tsc --noEmit` — expect zero errors.
  </action>
  <verify>
    <automated>cd frontend && npm test -- --run 2>&1 | tail -30 && npx tsc --noEmit 2>&1 | tail -10</automated>
  </verify>
  <done>
    - All 5 AssignmentEditor tests pass (GREEN).
    - ResearchDialog.test.tsx still passes (no regression).
    - Full frontend test suite passes.
    - `npx tsc --noEmit` clean.
    - "Editar assignments" button visible in ResearchDialog success/cached states.
    - Commit: `feat(quick-260428-jug-01): implement AssignmentEditor + wire ResearchDialog (GREEN, 5 tests)`
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser → backend PATCH /research/assignments | User-controlled barony/condado IDs cross here (already mitigated server-side by Etapa 8: T-h1t-01..08) |
| user keyboard → component state | Free-text condado renames (no validation in UI; backend enforces) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-jug-01 | Tampering | computeDelta diff logic | mitigate | Diff is read-only over `researchResult` prop; deep-copy initial drafts via spread to avoid mutating the prop. Tests assert delta payload shape for changed-only fields (Tests 2, 3). |
| T-jug-02 | Information Disclosure | error Callout | mitigate | Truncate error to 600 chars (matches backend T-h1t-06) so a verbose Pydantic stack does not flood the UI; explicit `.slice(0, 600)` covered by Test 4. |
| T-jug-03 | Denial of Service | unbounded condado/barony lists in UI | accept | UI rendering of ~10-100 baronies and ~10-30 condados is well within React's comfort. No virtualization needed for v1. Document for v2 if real datasets exceed ~500 rows. |
| T-jug-04 | Repudiation | optimistic state update on success | mitigate | Only call `setManualResult(result)` AFTER `await patchResearchAssignments` resolves with server-confirmed result. No local-only optimistic write — backend is the source of truth. |
| T-jug-05 | Tampering (XSS) | rendering condado names from result | accept | Radix Themes Text/TextField escape children by default; React's JSX rendering is safe. Backend already validated MapResearchResult shape. No `dangerouslySetInnerHTML`. |
</threat_model>

<verification>
- 5 AssignmentEditor tests pass (vitest).
- Existing 16 ResearchDialog/canvas tests still pass (no regression).
- `npx tsc --noEmit` exits 0.
- Manual smoke (out of automated scope but listed for retro): open dialog, change a barony's
  condado, click Salvar, confirm canvas color update reflects new assignment after dialog closes.
</verification>

<success_criteria>
- patchResearchAssignments delegates to existing patchJson and returns `result.result`.
- AssignmentEditor renders correct current assignments + supports edits + sends DELTA only.
- Backend errors surface as truncated Callout (≤600 chars) without closing the dialog.
- On success: store updated, dialog closed, parent ResearchDialog reflects new manualResult.
- Salvar disabled until at least one change is made.
- ResearchDialog gains an "Editar assignments" button visible in success/cached states.
</success_criteria>

<output>
After completion, create `.planning/quick/260428-jug-etapa-8b-frontend-assignmenteditor-consu/260428-jug-SUMMARY.md`
following the standard SUMMARY template, including:
- One-liner
- What Was Built (api client + component + wiring)
- Behavior Coverage table (5 tests)
- Test Run Results (frontend test counts before/after)
- Threat Mitigations Verified
- Out of Scope (drag-drop UI, kingdom/duchy renames, ResearchResult type unification)
- Commits
</output>
