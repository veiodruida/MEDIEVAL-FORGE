---
phase: quick-260428-lka
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/package.json
  - frontend/package-lock.json
  - frontend/src/api/codex.ts
  - frontend/src/hooks/useCodexStream.ts
  - frontend/src/hooks/useCodexStream.test.ts
  - frontend/src/components/codex/CodexViewer.tsx
  - frontend/src/components/codex/CodexViewer.test.tsx
autonomous: true
requirements:
  - ETAPA-10-CODEX-VIEWER
user_setup: []

must_haves:
  truths:
    - "User can click a 'Gerar Codex' button and watch SSE progress messages stream live."
    - "On completion (or when a cached payload exists), the viewer renders 12 tabs — one per CodexCategory key from backend schemas.py — and clicking a tab swaps the visible entries."
    - "Each entry's `description` markdown is rendered as HTML (e.g. `**bold**` becomes a `<strong>` tag) — not displayed as raw markdown text."
    - "Loading, error, and empty-category states each render their own visible UI affordance."
  artifacts:
    - path: "frontend/src/api/codex.ts"
      provides: "Typed CodexResult/CodexCategory/CodexEntity types + fetchCachedCodex/fetchCodexPrompt helpers mirroring backend schemas.py"
      exports: ["CodexResult", "CodexCategory", "CodexEntity", "CodexCategoryKey", "CODEX_CATEGORY_KEYS", "fetchCachedCodex", "fetchCodexPrompt"]
    - path: "frontend/src/hooks/useCodexStream.ts"
      provides: "SSE hook for POST /api/projects/:id/codex mirroring useResearchStream's contract"
      exports: ["useCodexStream"]
    - path: "frontend/src/hooks/useCodexStream.test.ts"
      provides: "Vitest coverage of SSE parsing — token, RESULT, DONE, ERROR, cached"
    - path: "frontend/src/components/codex/CodexViewer.tsx"
      provides: "Radix Tabs component, 12 tabs, react-markdown rendering of entry descriptions, provider picker, Gerar Codex button"
      exports: ["CodexViewer"]
    - path: "frontend/src/components/codex/CodexViewer.test.tsx"
      provides: "Vitest + Testing Library coverage of all 12 tabs + tab swap + markdown render + loading/error/empty states"
    - path: "frontend/package.json"
      contains: "\"react-markdown\""
  key_links:
    - from: "frontend/src/components/codex/CodexViewer.tsx"
      to: "frontend/src/hooks/useCodexStream.ts"
      via: "useCodexStream(projectId).start(provider)"
      pattern: "useCodexStream"
    - from: "frontend/src/components/codex/CodexViewer.tsx"
      to: "frontend/src/api/codex.ts"
      via: "fetchCachedCodex on mount via useQuery"
      pattern: "fetchCachedCodex|CODEX_CATEGORY_KEYS"
    - from: "frontend/src/hooks/useCodexStream.ts"
      to: "/api/projects/:id/codex"
      via: "fetch POST with SSE body reader"
      pattern: "/api/projects/.*/codex"
    - from: "frontend/src/components/codex/CodexViewer.tsx"
      to: "react-markdown"
      via: "<ReactMarkdown>{entry.description}</ReactMarkdown>"
      pattern: "react-markdown|ReactMarkdown"
---

<objective>
Etapa 10 — implement the Codex viewer frontend that consumes the backend Codex
SSE/cached/prompt endpoints (delivered in Etapa 9, quick-260428-l0l) and renders
the 12-category narrative payload as Radix Tabs with markdown-rendered entries.

Purpose: closes the Etapa 10 milestone in master plan
`C:\Users\veio_\.claude\plans\hazy-hatching-abelson.md` § Etapa 10 (line 483) and
§ E.3 components (line 320). Backend is complete; this is a frontend-only task.

Output:
- New typed API client `frontend/src/api/codex.ts`
- New SSE hook `frontend/src/hooks/useCodexStream.ts` (+ test)
- New component `frontend/src/components/codex/CodexViewer.tsx` (+ test)
- `react-markdown` added to frontend dependencies
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md

<!-- Master plan reference for Etapa 10 -->
@C:\Users\veio_\.claude\plans\hazy-hatching-abelson.md

<!-- Backend source of truth — DO NOT MODIFY, only mirror types -->
@backend/medieval_forge/services/llm/schemas.py
@backend/medieval_forge/api/codex.py

<!-- Frontend patterns to mirror -->
@frontend/src/api/research.ts
@frontend/src/hooks/useResearchStream.ts
@frontend/src/hooks/useResearchStream.test.ts
@frontend/src/components/research/ResearchDialog.tsx
@frontend/src/components/research/ResearchDialog.test.tsx
@frontend/src/components/research/AssignmentEditor.tsx
@frontend/package.json

<interfaces>
<!-- Extracted from backend/medieval_forge/services/llm/schemas.py.
     Frontend TS types in api/codex.ts MUST mirror these exactly. -->

```python
# Each CodexEntity:
class CodexEntity(BaseModel):
    id: str
    name: str
    description: str  # markdown

# Each CodexCategory (12 distinct subclasses, identical shape):
class CodexCategory(BaseModel):
    summary: str = ""
    entries: list[CodexEntity] = []

# CodexResult — top-level keys are EXACTLY these 12 (from schemas.py lines 206-217):
class CodexResult(BaseModel):
    currency:   CodexCurrency
    attributes: CodexAttributes
    health:     CodexHealth
    traits:     CodexTraits
    feudal:     CodexFeudal
    politics:   CodexPolitics
    dynasty:    CodexDynasty
    religion:   CodexReligion
    culture:    CodexCulture
    economy:    CodexEconomy
    military:   CodexMilitary
    events:     CodexEvents
```

NOTE on category keys: the user-facing description in the planning prompt
mentioned `mental_physical, feudal_system, political_power, demographics, scholarship`
but those names are the *narrative concept*. The backend `schemas.py` uses
`health, feudal, politics, economy, traits` (etc.) as the 12 actual JSON keys —
that file is the source of truth (per the planning constraint that says so
explicitly). Use the schema keys above. Display labels (Portuguese, for tab UI)
are the planner's responsibility; map them in CODEX_CATEGORY_LABELS.

<!-- Extracted from backend/medieval_forge/api/codex.py — endpoint contracts: -->
POST /api/projects/{project_id}/codex?provider={p}&force_refresh={bool}&focus={csv}
  → SSE stream: "data: <text>\n\n", terminated by "data: DONE\n\n".
  → Special tokens (mirror useResearchStream): "cached", "RESULT: <json>",
    "ERROR: <msg>", "Tentativa N/3: ..." (retry notices).

GET /api/projects/{project_id}/codex/cached?provider={p}&model={m?}&focus={csv?}
  → 200 with CodexResult JSON, or 404 if no cache row.

GET /api/projects/{project_id}/codex/prompt?focus={csv?}
  → 200 { "prompt": string }.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: RED — failing tests for codex API client, SSE hook, and CodexViewer (5+ tests with descriptive names + literal fixtures)</name>
  <files>
    frontend/src/hooks/useCodexStream.test.ts,
    frontend/src/components/codex/CodexViewer.test.tsx
  </files>
  <behavior>
    Per memory feedback (`feedback-tests-descriptive.md`): test names are full
    sentences describing the behavior; fixtures use explicit numeric/string
    literals (no helpers that hide values). Mirror the structure of
    `frontend/src/hooks/useResearchStream.test.ts` and
    `frontend/src/components/research/ResearchDialog.test.tsx`.

    Required tests in `useCodexStream.test.ts` (mirror useResearchStream.test.ts
    line-for-line, swap endpoint to `/api/projects/:id/codex`):
      1. `parses SSE messages and classifies tokens, cached, RESULT, DONE, ERROR`
         — uses `makeStream` helper identical to research test; mock RESULT is a
         literal CodexResult with one entry in `dynasty` category:
         ```ts
         {
           currency:{summary:"",entries:[]}, attributes:{summary:"",entries:[]},
           health:{summary:"",entries:[]},   traits:{summary:"",entries:[]},
           feudal:{summary:"",entries:[]},   politics:{summary:"",entries:[]},
           dynasty:{summary:"House of Aviz", entries:[
             {id:"D_AVIZ", name:"House of Aviz", description:"**Royal** dynasty of Portugal."}
           ]},
           religion:{summary:"",entries:[]}, culture:{summary:"",entries:[]},
           economy:{summary:"",entries:[]},  military:{summary:"",entries:[]},
           events:{summary:"",entries:[]},
         }
         ```
         Asserts `result.current.status === "success"`, deep-equals the result.
      2. `handles cached marker and sets status to cached`.
      3. `captures retry notices into retryNotices array` (use literal
         "Tentativa 1/3: ValidationError: missing field 'dynasty'").
      4. `captures ERROR messages and sets status to error`.

    Required tests in `CodexViewer.test.tsx` (use `Theme` + `QueryClientProvider`
    wrapper, mirror `ResearchDialog.test.tsx` setup):
      1. `renders one tab for each of the 12 codex category keys`
         — render with cached fixture (200 from /codex/cached returning the
         literal CodexResult above); assert all 12 tab triggers are in the
         document, identified via `data-testid="codex-tab-{key}"` for each of:
         currency, attributes, health, traits, feudal, politics, dynasty,
         religion, culture, economy, military, events.
      2. `clicking a tab shows that category's entries and hides others`
         — fixture: `dynasty` has entry id `D_AVIZ` name `"House of Aviz"`;
         `religion` has entry id `R_CATH` name `"Latin Christianity"`.
         Click tab `religion`, assert `"Latin Christianity"` is visible and
         `"House of Aviz"` is not (use `queryByText` for negative).
      3. `renders markdown bold in entry description as a strong tag`
         — fixture: dynasty entry `description: "**Royal** dynasty of Portugal."`.
         Click dynasty tab. Use `container.querySelector("strong")` and assert
         its textContent is `"Royal"`. (This proves react-markdown ran — plain
         text would yield no `<strong>`.)
      4. `shows empty-state message when the active category has zero entries`
         — fixture: cached result where `events` has `entries: []`. Click
         events tab. Assert text `"Nenhuma entrada nesta categoria"` is visible.
      5. `renders error UI when SSE stream emits ERROR token`
         — POST /codex returns SSE chunks: `"data: ERROR: provider unreachable\n\n"`.
         User clicks "Gerar Codex". Assert `"provider unreachable"` is in document.

    All tests MUST currently FAIL (files under test don't exist yet). Run
    `cd frontend && npm test -- --run useCodexStream CodexViewer` to confirm RED.
  </behavior>
  <action>
    1. Create `frontend/src/hooks/useCodexStream.test.ts` — copy structure from
       `useResearchStream.test.ts`, adapt endpoint to `/api/projects/.*/codex`,
       use the literal CodexResult fixture above. Imports
       `from "./useCodexStream"` (file does NOT exist yet — that's the RED).
    2. Create `frontend/src/components/codex/CodexViewer.test.tsx` — copy
       wrapper helpers from `ResearchDialog.test.tsx` (QueryClient + Theme).
       Import `{ CodexViewer }` from `"./CodexViewer"` (does not exist yet).
       Mock `globalThis.fetch` per-test as in ResearchDialog.test.tsx.
       For tab interaction, use `fireEvent.click` on the tab trigger element.
    3. Mark all expectations with literal numeric/string values (no shared
       fixture builders). Each `it()` title is a full sentence per the memory
       feedback file.
    4. RED commit:
       ```
       cd frontend
       git add src/hooks/useCodexStream.test.ts src/components/codex/CodexViewer.test.tsx
       git commit -m "test(quick-260428-lka-01): add failing tests for codex viewer + SSE hook"
       ```
       Tests must fail at this point (files-under-test missing). Do NOT skip
       this verification — run `npm test -- --run useCodexStream CodexViewer`
       and confirm failures are import-resolution errors, not assertion errors.
  </action>
  <verify>
    <automated>cd frontend && npx vitest run src/hooks/useCodexStream.test.ts src/components/codex/CodexViewer.test.tsx 2&gt;&amp;1 | grep -E "FAIL|Cannot find module"</automated>
  </verify>
  <done>
    Two new test files committed in a single RED commit. Vitest reports module
    resolution failure for `./useCodexStream` and `./CodexViewer` (proving
    nothing under test exists yet). Test count includes ≥4 useCodexStream cases
    and ≥5 CodexViewer cases, each with a sentence-style name.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: GREEN — install react-markdown, implement codex.ts + useCodexStream + CodexViewer until all tests pass</name>
  <files>
    frontend/package.json,
    frontend/package-lock.json,
    frontend/src/api/codex.ts,
    frontend/src/hooks/useCodexStream.ts,
    frontend/src/components/codex/CodexViewer.tsx
  </files>
  <behavior>
    All tests from Task 1 turn GREEN. No new tests added in this task — only
    implementation. `npm test` for the two new test files reports 100% pass.
    `npm run build` succeeds (TypeScript strict).
  </behavior>
  <action>
    Step 1 — Install react-markdown:
    ```
    cd frontend
    npm install react-markdown
    ```
    Verify it lands in `dependencies` (not devDependencies). The peer-dep on
    React 19 is satisfied; this project already runs `react@^19.2.0`.

    Step 2 — Create `frontend/src/api/codex.ts`:
    ```ts
    // CodexResult TS types mirroring backend/medieval_forge/services/llm/schemas.py
    // (lines 134-217). The 12 category keys are fixed by the backend Pydantic
    // schema with extra='forbid'.
    export const CODEX_CATEGORY_KEYS = [
      "currency", "attributes", "health", "traits",
      "feudal",   "politics",   "dynasty","religion",
      "culture",  "economy",    "military","events",
    ] as const;
    export type CodexCategoryKey = typeof CODEX_CATEGORY_KEYS[number];

    // Portuguese display labels for the tab UI (per CLAUDE.md ResearchDialog
    // pattern of pt-BR copy). Map keys are the 12 backend keys above.
    export const CODEX_CATEGORY_LABELS: Record<CodexCategoryKey, string> = {
      currency: "Moeda",      attributes: "Atributos",
      health:   "Saúde",      traits:     "Traços",
      feudal:   "Feudalismo", politics:   "Política",
      dynasty:  "Dinastias",  religion:   "Religião",
      culture:  "Cultura",    economy:    "Economia",
      military: "Militar",    events:     "Eventos",
    };

    export interface CodexEntity { id: string; name: string; description: string }
    export interface CodexCategory { summary: string; entries: CodexEntity[] }
    export type CodexResult = Record<CodexCategoryKey, CodexCategory>;

    export async function fetchCachedCodex(
      projectId: string, provider: string, model?: string, focus?: string[],
    ): Promise<CodexResult | null> {
      const params = new URLSearchParams({ provider });
      if (model) params.set("model", model);
      if (focus && focus.length) params.set("focus", focus.join(","));
      const r = await fetch(`/api/projects/${projectId}/codex/cached?${params}`);
      if (r.status === 404) return null;
      if (!r.ok) throw new Error(`cached ${r.status}`);
      return r.json();
    }

    export async function fetchCodexPrompt(
      projectId: string, focus?: string[],
    ): Promise<string> {
      const params = new URLSearchParams();
      if (focus && focus.length) params.set("focus", focus.join(","));
      const url = `/api/projects/${projectId}/codex/prompt${
        params.toString() ? `?${params}` : ""
      }`;
      const r = await fetch(url);
      if (!r.ok) {
        const body = await r.json().catch(() => ({ detail: r.statusText }));
        throw new Error(body.detail ?? `prompt ${r.status}`);
      }
      const d = await r.json();
      return d.prompt as string;
    }
    ```

    Step 3 — Create `frontend/src/hooks/useCodexStream.ts`:
    Copy the entire body of `frontend/src/hooks/useResearchStream.ts` verbatim,
    then change exactly TWO things:
      a. import: `import type { CodexResult } from "../api/codex";`
      b. fetch URL inside `start`:
         `/api/projects/${projectId}/codex?provider=${provider}&force_refresh=${forceRefresh}`
    Keep the same Status union, the same StreamMessage type, the same
    DONE/cached/ERROR/RESULT/Tentativa parsing — that's the contract Task 1
    tested against.

    Step 4 — Create `frontend/src/components/codex/CodexViewer.tsx`:
    Build a Radix Themes `Tabs.Root` (use `@radix-ui/themes`'s `Tabs` — it's
    already installed; do NOT `npm install @radix-ui/react-tabs` since the
    themed primitive is already available in the bundle). Required structure:

    ```tsx
    import { Tabs, Box, Text, Flex, Button, Heading, Badge } from "@radix-ui/themes";
    import ReactMarkdown from "react-markdown";
    import { useQuery } from "@tanstack/react-query";
    import { useCodexStream } from "../../hooks/useCodexStream";
    import {
      CODEX_CATEGORY_KEYS, CODEX_CATEGORY_LABELS,
      fetchCachedCodex, type CodexResult, type CodexCategoryKey,
    } from "../../api/codex";
    import { ProviderSelector } from "../research/ProviderSelector";

    interface CodexViewerProps { projectId: string }

    export function CodexViewer({ projectId }: CodexViewerProps) {
      // selected provider state (default "claude" — same default as ResearchDialog).
      const [providerId, setProviderId] = useState<string>("claude");
      const stream = useCodexStream(projectId);

      const cachedQuery = useQuery<CodexResult | null>({
        queryKey: ["codex", "cached", projectId, providerId],
        queryFn: () => fetchCachedCodex(projectId, providerId),
      });

      const result: CodexResult | null = stream.result ?? cachedQuery.data ?? null;

      // Render: header (provider picker + Gerar Codex button + status badge),
      // streaming log area (when status==="streaming"), error box (when ERROR),
      // and Tabs.Root with 12 Tabs.Trigger + 12 Tabs.Content.
      // Each Tabs.Trigger has data-testid={`codex-tab-${key}`}.
      // Each Tabs.Content lists category.entries — for each entry render:
      //   <Heading size="3">{entry.name}</Heading>
      //   <ReactMarkdown>{entry.description}</ReactMarkdown>
      // If category.entries.length === 0, show
      //   <Text>Nenhuma entrada nesta categoria</Text>.
      // If `result` is null and not streaming, show an idle hint.
      // If stream.status==="error", show <Text color="red">{stream.error}</Text>.
    }
    ```

    Implementation notes:
    - Default active tab: `"currency"` (first in CODEX_CATEGORY_KEYS).
    - "Gerar Codex" button calls `stream.start(providerId, false)`; disable
      while `stream.status === "streaming"`.
    - For per-entry rendering inside a tab use `<Box key={entity.id}>` and the
      heading/markdown pair shown above.
    - Empty state copy is the literal string `"Nenhuma entrada nesta categoria"`
      (Task 1 test 4 asserts this exact text).
    - DO NOT auto-trigger the stream on mount — Task 1 test 5 fires it via a
      button click whose accessible label is `"Gerar Codex"`.

    Step 5 — Run tests until all pass:
    ```
    cd frontend && npx vitest run src/hooks/useCodexStream.test.ts src/components/codex/CodexViewer.test.tsx
    cd frontend && npm run build   # confirm TS strict passes
    ```

    Step 6 — GREEN commit (single atomic commit per memory feedback workflow):
    ```
    git add frontend/package.json frontend/package-lock.json \
            frontend/src/api/codex.ts \
            frontend/src/hooks/useCodexStream.ts \
            frontend/src/components/codex/CodexViewer.tsx
    git commit -m "feat(quick-260428-lka-01): codex viewer (12 tabs + markdown), useCodexStream SSE hook, codex API client + react-markdown dep"
    ```
  </action>
  <verify>
    <automated>cd frontend &amp;&amp; npx vitest run src/hooks/useCodexStream.test.ts src/components/codex/CodexViewer.test.tsx &amp;&amp; npm run build</automated>
  </verify>
  <done>
    1. `react-markdown` is in `frontend/package.json` `dependencies`.
    2. `frontend/src/api/codex.ts`, `useCodexStream.ts`, and `CodexViewer.tsx`
       exist with the exports listed in `must_haves.artifacts`.
    3. All 9+ tests added in Task 1 pass (RED → GREEN). No test was modified
       to make this happen.
    4. `npm run build` succeeds — TypeScript strict mode passes.
    5. Two atomic commits exist on the branch:
       `test(quick-260428-lka-01): ...` followed by `feat(quick-260428-lka-01): ...`.
    6. CodexViewer component renders 12 Radix Tabs (one per backend category
       key), entry descriptions are processed by react-markdown so `**bold**`
       becomes `<strong>` in the DOM.
  </done>
</task>

</tasks>

<verification>
- `cd frontend && npx vitest run` — entire frontend suite passes (existing tests not regressed; 9+ new tests added).
- `cd frontend && npm run build` — TypeScript strict + Vite build succeeds.
- Manual smoke (optional, no commit): mount `<CodexViewer projectId="..." />` somewhere, confirm 12 tabs visible with Portuguese labels, click through each tab.
- Backend untouched: `git diff backend/` returns empty.
</verification>

<success_criteria>
- All tests in Task 1 (≥9 cases) pass after Task 2 implementation.
- 12 tab triggers render with `data-testid="codex-tab-{key}"` for each of:
  currency, attributes, health, traits, feudal, politics, dynasty, religion,
  culture, economy, military, events.
- A `**bold**` substring inside any entry's `description` field renders as a
  `<strong>` element in the DOM (proven by Task 1 test 3).
- `frontend/package.json` `dependencies` includes `"react-markdown"`.
- Two atomic commits exist: one RED (`test(...)`), one GREEN (`feat(...)`).
- `npm run build` exits 0.
</success_criteria>

<output>
After completion, create
`.planning/quick/260428-lka-etapa-10-codex-viewer-frontend-codexview/260428-lka-SUMMARY.md`
documenting:
- Test count delta (added: 9+; expected total frontend tests after merge).
- The exact 12 backend category keys consumed (mirrored from schemas.py).
- The decision to use `@radix-ui/themes`'s `Tabs` primitive (already installed)
  rather than installing `@radix-ui/react-tabs` separately.
- Confirmation that the user-prompt category names
  (`mental_physical`, `feudal_system`, `political_power`, `demographics`,
  `scholarship`) were superseded by the schemas.py keys
  (`health`, `feudal`, `politics`, `economy`, `traits` — note `scholarship`
  has no schema counterpart and was treated as a synonym overlap, not a 13th
  tab) per the constraint "your source of truth for field names = schemas.py".
- Two commit hashes (RED + GREEN).
</output>
