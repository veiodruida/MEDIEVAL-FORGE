---
phase: 07-llm-research-as-opt-in-metadata-layer
plan: 10
subsystem: frontend-export
tags: [frontend, export, i18n, dialog, ptbr, phase06-absorption, warning4]
requires:
  - 07-08 (backend D-08 envelope + dry_run=true at api/v3/export.py)
  - 06 (validator emits 6 stable codes: SCHEMA_INVALID, COLOR_COLLISION,
    OCEAN_LEAK, MISSING_ORIGINAL_IDX, TERRITORY_TOO_SMALL,
    PIXEL_CENTER_OUT_OF_RANGE)
provides:
  - frontend/src/i18n/exportErrors.ts EXPORT_ERROR_PT_BR (6 keys)
  - frontend/src/api/useExportV3.ts useExportV3 + ExportValidationError +
    ValidationEnvelope type
  - frontend/src/components/export/ExportErrorDialog.tsx (Radix Dialog renderer)
  - ProjectDetail.tsx: v3 Export-button wiring + Toast network fallback
affects:
  - frontend/src/api/client.ts (DELETED legacy useExport + ExportResponse)
  - frontend/src/pages/ProjectDetail.tsx (re-wired Export button)
tech-stack:
  added: []
  patterns:
    - "TanStack mutation with typed 422-envelope branch (ExportValidationError extends Error)"
    - "Radix Dialog + Toast.Provider co-existence (one-dialog-at-a-time per UI-SPEC §Cross-surface)"
    - "Blob download via URL.createObjectURL + revokeObjectURL try/finally (T-07-10-04)"
    - "i18n keyed-string map (EXPORT_ERROR_PT_BR[code] ?? e.message forward-compat)"
key-files:
  created:
    - frontend/src/i18n/exportErrors.ts
    - frontend/src/i18n/__tests__/exportErrors.test.ts
    - frontend/src/api/useExportV3.ts
    - frontend/src/api/__tests__/useExportV3.test.ts
    - frontend/src/components/export/ExportErrorDialog.tsx
    - frontend/src/components/export/__tests__/ExportErrorDialog.test.tsx
  modified:
    - frontend/src/api/client.ts (DELETED useExport + ExportResponse)
    - frontend/src/pages/ProjectDetail.tsx (swapped to useExportV3)
decisions:
  - "useExportV3 returns the parsed JSON metadata (ExportResponse). The blob
    download is staged in ProjectDetail.handleExport (fetch download_url →
    blob → URL.createObjectURL) so the hook itself stays composable. This
    reconciles the backend contract (201 + JSON with download_url) with the
    plan's acceptance criterion that URL.createObjectURL/revokeObjectURL
    appear in ProjectDetail."
  - "DryRunOutcome is a discriminated union ({kind: 'passed'|'failed'|'network-error'})
    so ExportErrorDialog renders without a second mutation hook inside the
    component. ProjectDetail owns the mutation; the dialog is presentational."
  - "Toast.Root mounted at the ProjectDetail level (not main.tsx) so the
    toast message is co-located with the export state machine."
  - "Comment-block placeholder left in client.ts where useExport lived,
    documenting the WARNING 4 deletion. No transitional shim — D-V3-04
    compliance. Future archaeologists find a pointer to useExportV3.ts."
metrics:
  commits: 3
  files-created: 6
  files-modified: 2
  vitest-cases: 23 (3 i18n + 7 hook + 13 dialog)
  vitest-cases-suite-passing: 49 (i18n + api + export + InspectorSidebar)
  completed-date: 2026-05-14
---

# Phase 07 Plan 10: Frontend Export Button Swap + 422 Envelope Dialog Summary

**One-liner:** Swap Export button to /api/v3/projects/{id}/export with typed
ExportValidationError on 422 envelope; render 6 PT-BR error codes in Radix
ExportErrorDialog with inline dry-run preview; delete legacy useExport hook
(WARNING 4 / D-V3-04 no transitional shims).

## What Shipped

1. **`frontend/src/i18n/exportErrors.ts`** — single named export
   `EXPORT_ERROR_PT_BR: Record<string, string>` with the 6 stable codes
   copied verbatim from 07-UI-SPEC §Surface 3 / §Copywriting:
   - `SCHEMA_INVALID`, `COLOR_COLLISION`, `OCEAN_LEAK`,
     `MISSING_ORIGINAL_IDX`, `TERRITORY_TOO_SMALL`,
     `PIXEL_CENTER_OUT_OF_RANGE`.

2. **`frontend/src/api/useExportV3.ts`** — TanStack mutation hook:
   - POSTs `/api/v3/projects/{id}/export` (no body); `?dry_run=true` when
     `mutateAsync({dryRun: true})`.
   - On `res.status === 422`: parses envelope and throws typed
     `ExportValidationError(envelope)`.
   - On any other non-OK status: throws generic `Error` with HTTP context.
   - On success (real export only — not dry-run): invalidates
     `['projects', id]`, `['projects']`, `['v3-status', id]`.
   - Exports: `useExportV3`, `ExportValidationError`, `ExportResponse`,
     `ValidationEnvelope`, `ValidationErrorEntry`, `DryRunReport`.

3. **`frontend/src/components/export/ExportErrorDialog.tsx`** — Radix
   `Dialog.Root` shell controlled by `envelope: ValidationEnvelope | null`:
   - `Dialog.Title`: `Falha ao exportar`; subtitle: envelope summary
     (or SUBTITLE_FALLBACK copy from UI-SPEC).
   - Top-right `Validar antes de exportar` button drives the dry-run
     callback. Per-row layout:
     `[<Badge color="red" variant="soft">{code}</Badge>] · <Text size="1"
     color="gray">{file}</Text> · <Text size="2">{EXPORT_ERROR_PT_BR[e.code]
     ?? e.message}</Text>`.
   - Dry-run branches:
     - passed → green `Validação OK — pronto para exportar` heading +
       `Exportar agora` CTA (closes dialog + triggers onRetryExport).
     - failed → re-renders the new envelope's rows.
     - network error → inline `Erro ao comunicar com o servidor de
       exportação: {message}. Tente novamente.`
   - Forward-compat: unknown codes fall back to server `e.message`.
   - React text children only — no `dangerouslySetInnerHTML`
     (T-07-10-01 XSS mitigation).
   - `Dialog.Description` added for a11y (silences Radix aria-describedby
     warning).

4. **`frontend/src/pages/ProjectDetail.tsx`** — rewired:
   - Replaced `useExport(id)` with `useExportV3(id)`.
   - New `handleExport`: `mutateAsync({})` → `fetch(download_url)` →
     `blob()` → `URL.createObjectURL(blob)` → anchor[download] → click →
     `URL.revokeObjectURL(url)` in `finally` block (T-07-10-04).
   - Catches `ExportValidationError` → `setExportEnvelope(err.envelope)`
     (opens dialog). Catches generic `Error` → sets toast message +
     opens `Toast.Root`.
   - New `handleDryRun` returns `DryRunOutcome` discriminated union for
     the dialog. New `handleCloseExportDialog`.
   - Mounts `<ExportErrorDialog envelope={exportEnvelope} ... />` and
     `<Toast.Root open={toastOpen} ...>` with PT-BR copy
     `Erro ao comunicar com o servidor de exportação: {message}.
     Tente novamente.`

5. **`frontend/src/api/client.ts`** — **DELETED** (WARNING 4 / D-V3-04):
   - `export interface ExportResponse` (was lines 165-170).
   - `export function useExport` (was lines 172-193).
   - Replaced with a comment block pointing to `useExportV3.ts` for
     archaeological tracing. No transitional shim.

6. **`frontend/src/components/workspace/WorkspaceToolbar.tsx`** — NOT
   modified. `onExport: () => void` prop signature preserved per plan; the
   `ProjectDetail` parent owns the new mutation.

## Tests

23 new vitest cases distributed across 3 files; 49 cases pass total in the
verification suite (`npm test -- --run src/i18n src/api src/components/export
src/components/canvas/__tests__/InspectorSidebar.test.tsx`).

- **`exportErrors.test.ts`** (3 cases) — 6 stable codes present, every
  string non-empty, no English-fallback substrings.
- **`useExportV3.test.ts`** (7 cases) — endpoint URL (`/api/v3/projects/...`,
  never v1), 201 returns ExportResponse, 422 throws ExportValidationError
  with parsed envelope, 500 throws generic Error, dryRun=true appends
  `?dry_run=true`, dryRun 422 throws ExportValidationError, undefined
  projectId throws.
- **`ExportErrorDialog.test.tsx`** (13 cases) — 6 per-code PT-BR render
  assertions, dry-run pass replaces list with passed heading + Exportar
  agora button, dry-run failed re-renders new envelope, dry-run network
  error renders inline fallback, unknown-code fallback shows server
  message, Fechar invokes onClose, Exportar agora invokes onRetryExport +
  closes, null envelope renders nothing.

## Threat Mitigations (07-PLAN §Threat Model)

| Threat ID | Mitigation in Code |
|-----------|--------------------|
| T-07-10-01 (XSS via dialog message) | React text children only; no `dangerouslySetInnerHTML`. Verified by acceptance grep returning 0 matches. |
| T-07-10-04 (Object URL not revoked) | `URL.revokeObjectURL(url)` in `finally` block after anchor click (ProjectDetail.handleExport line 129). |
| T-07-10-05 (Unknown code crashes UI) | `EXPORT_ERROR_PT_BR[e.code] ?? e.message` literal in ExportErrorDialog.tsx:62 — verified by acceptance grep. |
| T-07-10-06 (WARNING 4: stale code path) | `useExport` and `ExportResponse` DELETED from client.ts. Grep `export function useExport\\b` returns 0 matches. |

## Acceptance Criteria Status

| Criterion | Status | Notes |
|-----------|--------|-------|
| Export button calls /api/v3/projects/{id}/export | PASS | `grep -nE "/api/v3/projects" frontend/src/api/useExportV3.ts` = 4 matches |
| 422 envelope renders 6 codes in PT-BR via ExportErrorDialog | PASS | 13 vitest cases + 6 per-code PT-BR render assertions |
| Dry-run preview inline | PASS | `handleDryRun` wired to dialog `onDryRun`; 3 dry-run vitest cases (passed / failed / network) |
| Network/5xx fallback Toast | PASS | `Toast.Root` mounted with PT-BR copy; grep `Erro ao comunicar com o servidor de exportação` returns 1 match in ProjectDetail.tsx |
| Legacy useExport DELETED (WARNING 4) | PASS | `grep -nE "export function useExport\\b" frontend/src/api/client.ts` returns 0 matches |
| Phase 07 SC #1 unblocked | PASS | tsc + 49 vitest cases green; ready for Plan 11 UAT |

## Verification Commands (rerun on demand)

```bash
cd frontend && npm test -- --run src/i18n src/api/__tests__/useExportV3.test.ts src/components/export
# → 23 tests pass (3 + 7 + 13)

cd frontend && npm run build
# → tsc + vite build exit 0; 468 modules transformed

grep -cE "^\\s*[A-Z_]+:" frontend/src/i18n/exportErrors.ts
# → 6

grep -rnE "/api/projects/\\\$\\{projectId\\}/export" frontend/src/
# → 0 matches (v1 endpoint absent)

grep -nE "export function useExport\\b" frontend/src/api/client.ts
# → 0 matches (legacy hook DELETED, WARNING 4 satisfied)
```

## Deviations from Plan

**None — plan executed exactly as written.**

Three minor design choices made within plan latitude (documented in
front-matter `decisions`):

1. Blob download flow staged in `ProjectDetail.handleExport` rather than
   inside the hook (`useExportV3` returns metadata JSON only). This is
   what the plan's acceptance criteria require (URL.createObjectURL/
   revokeObjectURL grep checks point at ProjectDetail.tsx, not the hook).
2. `DryRunOutcome` discriminated union returned from dialog's `onDryRun`
   callback so the dialog stays presentational while ProjectDetail owns
   the mutation. UI-SPEC permits planner's discretion on this.
3. `Toast.Root` mounted at ProjectDetail level (not in main.tsx). Local
   state co-locates with the export state machine.

## Decisions Made During Execution

- **Symbolic link to node_modules** — the worktree had no `node_modules`
  directory. Created a PowerShell `New-Item -ItemType Junction` pointing
  at the main repo's `frontend/node_modules` so vitest + tsc could run.
  This is a worktree-local workaround; not committed (junction is not in
  git status).
- **Dialog.Description for a11y** — Radix warned about
  `Missing Description or aria-describedby` during tests. Added
  `Dialog.Description` wrappers so the warning is silenced AND screen
  readers get the summary text properly associated with the dialog.

## Self-Check

Files exist:
- FOUND: frontend/src/i18n/exportErrors.ts
- FOUND: frontend/src/i18n/__tests__/exportErrors.test.ts
- FOUND: frontend/src/api/useExportV3.ts
- FOUND: frontend/src/api/__tests__/useExportV3.test.ts
- FOUND: frontend/src/components/export/ExportErrorDialog.tsx
- FOUND: frontend/src/components/export/__tests__/ExportErrorDialog.test.tsx

Commits exist:
- FOUND: 5733212 feat(07-10): add exportErrors i18n map + useExportV3 mutation with 422 envelope
- FOUND: 6bf104b feat(07-10): add ExportErrorDialog component with dry-run + 6 PT-BR codes
- FOUND: 3f2d9b8 feat(07-10): wire ProjectDetail to useExportV3 + delete legacy useExport (WARNING 4)

## Self-Check: PASSED
