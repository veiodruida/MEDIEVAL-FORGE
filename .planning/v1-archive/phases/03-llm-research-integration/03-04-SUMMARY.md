---
phase: 03
plan: 04
subsystem: frontend-research-ui
tags: [frontend, react, tanstack-query, zustand, sse, radix-ui, llm-research]
dependency_graph:
  requires: [03-01, 03-02, 03-03]
  provides: [research-ui, provider-selector, auth-setup-sheet, sse-stream-hook]
  affects: [ProjectDetail, frontend/src/api/research.ts, frontend/src/hooks/useResearchStream.ts]
tech_stack:
  added: []
  patterns:
    - TanStack Query wrappers for LLM provider discovery and auth mutations
    - Zustand plain store (no temporal) for ephemeral dialog session state
    - SSE consumer via fetch + ReadableStream.getReader + TextDecoder splitting on "\n\n"
    - Radix Dialog with CSS position:fixed override to simulate right-side Sheet
key_files:
  created:
    - frontend/src/api/research.ts
    - frontend/src/hooks/useResearchStream.ts
    - frontend/src/hooks/useResearchStream.test.ts
    - frontend/src/stores/useResearchStore.ts
    - frontend/src/components/research/ProviderSelector.tsx
    - frontend/src/components/research/AuthSetupSheet.tsx
    - frontend/src/components/research/ResearchDialog.tsx
    - frontend/src/components/research/ResearchDialog.test.tsx
  modified:
    - frontend/src/pages/ProjectDetail.tsx
decisions:
  - "ResearchStore uses plain zustand create() — no temporal/zundo middleware because dialog state is ephemeral and must not pollute canvas undo stack (D-29)"
  - "AuthSetupSheet implemented via Dialog.Content with CSS position:fixed override (Radix Themes 3.x has no native Sheet component)"
  - "handleRevalidateJson is a UI stub (alert) — backend /research/validate endpoint not yet implemented; displayed correctly per D-29 spec"
  - "badgeText inference: provider.auth_methods[].type used to infer which method is active since API does not return used_method — documented in code comment"
metrics:
  duration_minutes: 45
  completed_date: "2026-04-21"
  tasks_completed: 3
  tasks_total: 4
  files_modified: 9
---

# Phase 3 Plan 4: Research UI — Dialog, Provider Selector, Auth Sheet Summary

**One-liner:** Radix Dialog research trigger + SSE stream hook + per-provider auth Sheet wired into ProjectDetail Pipeline tab, driven entirely by /api/llm/providers discovery.

---

## What Was Built

### Task 1: API wrappers + useResearchStream hook + Zustand store

**`frontend/src/api/research.ts`** — TanStack Query wrappers over the Phase 3 backend endpoints:
- `useProvidersQuery()` — GET /api/llm/providers (staleTime 10s)
- `useHealthQuery()` — GET /api/llm/health (refetchInterval 30s)
- `useCachedResultQuery(projectId, provider, enabled)` — GET /api/projects/{id}/research/cached; returns null on 404
- `useStoreCredentialMutation()` — POST /api/auth/credentials/{provider}; invalidates `["llm"]` on success
- `useClearCredentialMutation()` — DELETE /api/auth/credentials/{provider}; invalidates `["llm"]`
- `useOAuthStartMutation()` — POST /api/auth/oauth/{provider}/start; returns {authorize_url, state}

**`frontend/src/hooks/useResearchStream.ts`** — SSE consumer hook:
- `useResearchStream(projectId)` returns `{start, cancel, messages, retryNotices, result, status, error}`
- Mirrors `useIngestStream` pattern: fetch POST + ReadableStream.getReader + TextDecoder, splits on "\n\n"
- Classifies SSE lines: token | cached | RESULT | DONE | ERROR | Tentativa (retry)
- AbortController for cancellation; status transitions: idle → streaming → cached | success | error

**`frontend/src/stores/useResearchStore.ts`** — plain Zustand store (no temporal middleware):
- Manages: dialogOpen, sheetOpenForProvider, selectedProviderId, country, periodStart, periodEnd, manualJson
- Deliberately excludes zundo temporal — streaming progress is ephemeral, must not be undo-tracked

**`frontend/src/hooks/useResearchStream.test.ts`** — 4 vitest tests:
- Parses all SSE message types (token, RESULT, DONE)
- cached marker → status="cached"
- retry notices captured into retryNotices array
- ERROR message → status="error"

### Task 2: ProviderSelector + AuthSetupSheet + ResearchDialog components

**`frontend/src/components/research/ProviderSelector.tsx`**:
- RadioGroup.Root driven by useProvidersQuery + useHealthQuery
- Per-provider auth badge with badgeText inference from auth_methods (cli/oauth/api_key/session)
- Ollama: disabled RadioGroup.Item + Tooltip when health.ollama.healthy === false
- Tooltip copy verbatim per UI-SPEC: "Inicia `ollama serve` e executa `ollama pull qwen2.5` para usar LLM local."

**`frontend/src/components/research/AuthSetupSheet.tsx`**:
- Right-side panel via Dialog.Content with CSS override: position:fixed, right:0, top:0, height:100vh, width:400px
- API key TextField (type=password) + "Usar esta chave" button (useStoreCredentialMutation)
- Gemini only: "Entrar com o Google" button → useOAuthStartMutation → window.open(authorize_url)
- Claude only: "CLI detectado — token válido" green badge if auth_methods has cli AND configured
- AlertDialog confirmation for "Limpar credenciais" (destructive) with exact UI-SPEC copy
- Security (T-3-14): API key held only in local React useState, never in Zustand store

**`frontend/src/components/research/ResearchDialog.tsx`**:
- Dialog.Root controlled by useResearchStore.dialogOpen; max-width 560px
- Section 1: ProviderSelector (provider RadioGroup + auth badges)
- Section 2: Country QID TextField + period start/end TextFields with "d.C." suffix
- Section 3: 5-state progress area:
  - idle (no cache): empty state copy per UI-SPEC
  - idle (cached): "Resultado em cache" green badge + result summary counts + "Forçar nova pesquisa"
  - streaming: `<pre>` log block (style matches existing ingest log) + "Pesquisando…" label
  - success: result summary (kingdoms/duchies/condados/baronies counts) + "Fechar"
  - error (max retries, retryNotices.length >= 3): "Falha após 3 tentativas" heading + TextArea + "Revalidar JSON"
  - error (generic): inline red "Erro ao comunicar com {provider}: {message}…"
- Footer: Cancelar (Dialog.Close) + "Iniciar pesquisa" (blue, disabled during streaming)
- AuthSetupSheet mounted outside Dialog to avoid z-index conflicts

**`frontend/src/components/research/ResearchDialog.test.tsx`** — 5 vitest tests:
- Renders all 4 providers from useProvidersQuery
- Disables Ollama radio when health.ollama.healthy is false
- Disables "Iniciar pesquisa" button while streaming (shows "Pesquisando…" on both label and button)
- Shows "Resultado em cache" badge when useCachedResultQuery returns data
- Shows manual JSON editor (TextArea + "Revalidar JSON") after 3 retry notices + ERROR

### Task 3: Wire ResearchDialog into ProjectDetail Pipeline tab

- Import `ResearchDialog` and `useResearchStore` added to ProjectDetail.tsx
- `setResearchDialogOpen` consumed from useResearchStore near other store hooks
- "Pesquisa histórica" blue Button added to Pipeline tab `<Flex gap="2" mb="3" wrap="wrap">` after existing pipeline buttons
- Button `disabled={!isGenerated}` — gated by existing `isGenerated` variable (status in {generated, exported})
- `<ResearchDialog projectId={project.id} />` mounted once outside Tabs, inside `<Box p="6">`
- TypeScript: `npx tsc --noEmit` exits 0 with no error TS lines

---

## Test Results

```
Test Files  2 passed (2)
Tests       9 passed (9)
  - src/hooks/useResearchStream.test.ts    4 passed
  - src/components/research/ResearchDialog.test.tsx  5 passed
```

TypeScript: clean (0 errors)

---

## UI-SPEC Compliance

All copy from 03-UI-SPEC.md Copywriting Contract implemented verbatim:
- "Pesquisa histórica" button, "Pesquisa histórica com LLM" title, "Iniciar pesquisa" / "Pesquisando…" CTA
- All auth badge texts: "✓ via CLI (claude)", "✓ via OAuth (Google)", "✓ via variável de ambiente", "✓ via chave de sessão", "⚠ Configuração necessária"
- Ollama tooltip exact string from UI-SPEC
- Empty state, cached badge, force-refresh, max-retries heading, manual JSON labels all verbatim
- Color tokens: blue CTA, green success badges, amber Ollama warning, red destructive
- Dimensions: Dialog.Content maxWidth:560, Sheet width:400, pre log style matching ingest log

**Minor deviations:**
- `AuthSetupSheet` uses Dialog.Content with CSS override instead of a native Sheet (Radix Themes 3.x does not export Sheet; this is documented in UI-SPEC as the approved approximation)
- `badgeText` inference uses auth_methods priority order rather than API-returned used_method (API does not expose this field; documented in code comment as v1 approximation)

---

## Known Stubs

| Stub | File | Line | Reason |
|------|------|------|--------|
| `handleRevalidateJson` calls `alert(...)` | frontend/src/components/research/ResearchDialog.tsx | ~55 | Backend POST /api/projects/{id}/research/validate endpoint not yet implemented. The TextArea and button are rendered correctly per D-29; the actual re-validation wire-up requires a future backend plan. |

This stub does NOT prevent the plan goal (full research flow end-to-end) — it only affects the recovery path after 3 retry failures where the user wants to manually re-submit edited JSON.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Worktree reset --soft artifact: deleted planning + backend files**
- **Found during:** Task 1 commit
- **Issue:** The worktree branch had been reset --soft to c092f0ff, which left the git index pointing to a state where planning artifacts (03-01 through 03-04 PLAN/SUMMARY) and all backend LLM service files did not exist. The first commit accidentally deleted them from the worktree.
- **Fix:** Restored all deleted files via `git checkout c092f0ff -- <files>` in the worktree, then committed the restoration in a separate commit (51448d0).
- **Files modified:** All .planning/phases/03-llm-research-integration/ files, all backend/medieval_forge/services/llm/ files, backend API files, backend test files
- **Commit:** 51448d0

**2. [Rule 1 - Bug] Test "disables 'Iniciar pesquisa' button while streaming" matched two elements**
- **Found during:** Task 2 test run
- **Issue:** Both the streaming section label ("Pesquisando…" Text span) and the button render the same text, causing `screen.getByText("Pesquisando…")` to throw "Found multiple elements"
- **Fix:** Changed assertion to use `screen.getAllByText("Pesquisando…")` and find the button element by tagName for the disabled check
- **Files modified:** ResearchDialog.test.tsx
- **Commit:** included in 400951b

---

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced beyond those already declared in the plan's `<threat_model>`. The frontend components only consume existing backend API routes from Plans 02-03.

T-3-14 verified: `grep -c "localStorage\|sessionStorage" frontend/src/components/research/` returns 0.
T-3-14 verified: `grep -c "api_key" frontend/src/stores/useResearchStore.ts` returns 0.

---

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 4838b66 | feat(03-04): implement API wrappers + useResearchStream hook + Zustand store |
| fix | 51448d0 | fix(03-04): restore backend files deleted in prior reset (soft-reset artifact) |
| 2 | 400951b | feat(03-04): implement ProviderSelector + AuthSetupSheet + ResearchDialog components |
| 3 | 5492977 | feat(03-04): wire ResearchDialog into ProjectDetail Pipeline tab |

---

## Manual Smoke Test

Awaiting human verification (Task 4 checkpoint). No providers were exercised end-to-end in this automated execution.

**Pre-conditions for smoke test:**
1. `cd backend && uvicorn medieval_forge.main:app --reload`
2. `cd frontend && npm run dev`
3. Navigate to a project with `status="generated"`
4. Click "Pesquisa histórica" blue button in Pipeline tab
5. Follow full verification steps in Task 4 of 03-04-PLAN.md
