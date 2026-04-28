---
phase: quick-260428-lka
plan: 01
subsystem: frontend
tags: [codex, sse, react, radix-tabs, react-markdown, tdd]
dependency_graph:
  requires:
    - quick-260428-l0l  # Etapa 9 backend: /codex SSE + cached + prompt endpoints
  provides:
    - CodexViewer component (12-category Radix Tabs with markdown rendering)
    - useCodexStream SSE hook
    - codex API client (fetchCachedCodex, fetchCodexPrompt)
  affects:
    - frontend bundle size (+react-markdown dependency, 78 transitive packages)
tech_stack:
  added:
    - react-markdown (ESM, renders markdown entry descriptions as HTML)
  patterns:
    - TDD RED→GREEN with atomic commits
    - Radix Themes Tabs.Root (already installed, no new dep)
    - SSE hook pattern mirrors useResearchStream contract exactly
    - Pointer event sequence (pointerDown+mouseDown+pointerUp+mouseUp+click) for Radix tab interaction in jsdom
key_files:
  created:
    - frontend/src/api/codex.ts
    - frontend/src/hooks/useCodexStream.ts
    - frontend/src/hooks/useCodexStream.test.ts
    - frontend/src/components/codex/CodexViewer.tsx
    - frontend/src/components/codex/CodexViewer.test.tsx
  modified:
    - frontend/package.json   (react-markdown added to dependencies)
    - frontend/package-lock.json
decisions:
  - Used @radix-ui/themes Tabs primitive (already installed) instead of adding @radix-ui/react-tabs separately — avoids duplicate Radix install and uses the project's existing themed component set
  - Backend schemas.py category keys (currency, attributes, health, traits, feudal, politics, dynasty, religion, culture, economy, military, events) used as the 12 tab keys — superseding planning prompt names (mental_physical, feudal_system, political_power, demographics, scholarship) per the plan's explicit "source of truth = schemas.py" constraint; "scholarship" has no counterpart in the schema and was not added as a 13th tab
  - Pointer event sequence fix: Radix Tabs.Trigger requires pointerDown to switch tabs in jsdom; plain fireEvent.click does not activate the tab; documented as clickRadixTab() helper in test file
metrics:
  completed_date: "2026-04-28"
  test_count_before: 191
  test_count_after: 200
  test_count_delta: 9
---

# Quick Task 260428-lka: Etapa 10 — Codex Viewer Frontend Summary

**One-liner:** 12-category Codex viewer with Radix Tabs, react-markdown rendering, and SSE hook mirroring useResearchStream contract.

## What Was Built

### `frontend/src/api/codex.ts`
Typed API client mirroring `backend/medieval_forge/services/llm/schemas.py`:
- `CODEX_CATEGORY_KEYS` — the 12 backend keys as a `const` tuple
- `CODEX_CATEGORY_LABELS` — Portuguese display labels for each key
- `CodexEntity`, `CodexCategory`, `CodexResult` TypeScript interfaces
- `fetchCachedCodex(projectId, provider, model?, focus?)` — GET /codex/cached, returns null on 404
- `fetchCodexPrompt(projectId, focus?)` — GET /codex/prompt

### `frontend/src/hooks/useCodexStream.ts`
SSE hook for POST /api/projects/:id/codex, directly mirroring `useResearchStream`:
- Same `Status` union (`idle | streaming | cached | success | error | cancelled`)
- Same `StreamMessage` type with `text + ts`
- Parses: `DONE`, `cached`, `ERROR:`, `RESULT:`, `Tentativa` retry notices
- Exposes: `start(provider, forceRefresh)`, `cancel`, `messages`, `retryNotices`, `result`, `status`, `error`, `elapsedMs`

### `frontend/src/components/codex/CodexViewer.tsx`
Radix `Tabs.Root` component:
- 12 `Tabs.Trigger` elements, each with `data-testid="codex-tab-{key}"`
- Each tab content renders `entry.name` as `<Heading size="3">` and `entry.description` via `<ReactMarkdown>` — `**bold**` becomes `<strong>Bold</strong>` in the DOM
- Empty-state: `"Nenhuma entrada nesta categoria"` when `entries.length === 0`
- Header: `ProviderSelector` + "Gerar Codex" button (disabled while streaming) + status badge
- Streaming log area shows SSE text tokens live
- Error state: `<Text color="red">{stream.error}</Text>` when status==="error"
- On mount: `useQuery` fetches `/codex/cached` via `fetchCachedCodex`; result feeds the tabs immediately without clicking "Gerar Codex"

## Exact 12 Category Keys Consumed

The following keys mirror `CodexResult` in `backend/medieval_forge/services/llm/schemas.py` (lines 203–217) exactly:

| Backend Key  | Portuguese Tab Label |
|-------------|---------------------|
| `currency`  | Moeda               |
| `attributes`| Atributos           |
| `health`    | Saúde               |
| `traits`    | Traços              |
| `feudal`    | Feudalismo          |
| `politics`  | Política            |
| `dynasty`   | Dinastias           |
| `religion`  | Religião            |
| `culture`   | Cultura             |
| `economy`   | Economia            |
| `military`  | Militar             |
| `events`    | Eventos             |

## Key Decisions

### 1. @radix-ui/themes Tabs vs @radix-ui/react-tabs
Used the themed `Tabs` from `@radix-ui/themes` (already installed at v3.3.0) rather than adding `@radix-ui/react-tabs` separately. This avoids a redundant install — `@radix-ui/themes` already re-exports the Tabs primitive with project theming applied.

### 2. Category key source of truth
The planning prompt listed `mental_physical`, `feudal_system`, `political_power`, `demographics`, `scholarship` as narrative concept names. These were superseded by the actual schema keys from `schemas.py`. Specifically:
- `mental_physical` → `health` (schema key)
- `feudal_system` → `feudal`
- `political_power` → `politics`
- `demographics` → `economy` (closest match)
- `scholarship` — has **no counterpart** in the 12-key schema; treated as an overlap/synonym rather than a 13th tab, per the explicit plan constraint that schemas.py is the source of truth.

### 3. Radix Tabs jsdom interaction fix
`fireEvent.click` on a `Tabs.Trigger` does not switch tabs in jsdom because Radix uses `pointerdown` internally. Tests 2 and 3 were initially failing with "Unable to find Latin Christianity / no `<strong>` found" for this reason. Fixed by dispatching the full pointer event sequence via a `clickRadixTab()` helper in the test file. This is documented inline so future tests on Radix tabs use the correct approach.

## Test Count

| Metric | Value |
|--------|-------|
| Tests before | 191 |
| Tests added | 9 |
| Tests after | 200 |
| New test files | 2 |

### Tests Added

`useCodexStream.test.ts` (4 tests):
1. Parses SSE messages and classifies tokens, cached, RESULT, DONE, ERROR
2. Handles cached marker and sets status to cached
3. Captures retry notices into retryNotices array (literal "Tentativa 1/3: ValidationError: missing field 'dynasty'")
4. Captures ERROR messages and sets status to error

`CodexViewer.test.tsx` (5 tests):
1. Renders one tab for each of the 12 codex category keys
2. Clicking a tab shows that category's entries and hides others
3. Renders markdown bold in entry description as a strong tag
4. Shows empty-state message when the active category has zero entries
5. Renders error UI when SSE stream emits ERROR token

## Commit Hashes

| Commit | Type | Message |
|--------|------|---------|
| `f23a985` | RED | `test(quick-260428-lka-01): add failing tests for codex viewer + SSE hook` |
| `dd0992d` | GREEN | `feat(quick-260428-lka-01): codex viewer (12 tabs + markdown), useCodexStream SSE hook, codex API client + react-markdown dep` |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Radix Tabs pointer event sequence for jsdom**
- **Found during:** Task 2 (GREEN) — tests 2 and 3 failing after implementing CodexViewer
- **Issue:** `fireEvent.click` on Radix `Tabs.Trigger` does not change `data-state` in jsdom because Radix's tab switching logic runs in a `pointerdown` handler, not `click`. Plain `fireEvent.click` skips this.
- **Fix:** Added `clickRadixTab()` helper in `CodexViewer.test.tsx` that dispatches `pointerDown → mouseDown → pointerUp → mouseUp → click` sequence. This matches what a real browser interaction generates and activates the Radix tab state machine correctly.
- **Files modified:** `frontend/src/components/codex/CodexViewer.test.tsx`
- **Commit:** `dd0992d` (included in GREEN commit — test file updated alongside implementation)

## Known Stubs

None. The `CodexViewer` component is fully wired:
- `useQuery` fetches real cached data via `fetchCachedCodex` on mount
- `useCodexStream.start()` fires the real SSE endpoint on button click
- All 12 category tabs render real data from the CodexResult payload

## Threat Flags

None. This is a read-only display component consuming existing backend endpoints. No new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check

### Files exist:
- `frontend/src/api/codex.ts` — FOUND
- `frontend/src/hooks/useCodexStream.ts` — FOUND
- `frontend/src/hooks/useCodexStream.test.ts` — FOUND
- `frontend/src/components/codex/CodexViewer.tsx` — FOUND
- `frontend/src/components/codex/CodexViewer.test.tsx` — FOUND

### Commits exist:
- `f23a985` — FOUND (RED commit)
- `dd0992d` — FOUND (GREEN commit)

### Test results: 200/200 passed (0 regressions)
### Build: `npm run build` exits 0 (TypeScript strict + Vite build successful)
### Backend unchanged: `git diff backend/` returns empty

## Self-Check: PASSED
