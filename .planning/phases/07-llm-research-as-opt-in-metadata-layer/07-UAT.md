---
phase: 07
plan: 11
type: uat-checklist
status: awaiting-user
created: 2026-05-14
---

# Phase 07 — Manual UAT Checklist

> Task 3 (`checkpoint:human-verify`). Executor performed the server-restart
> sequence per project memory `feedback-server-restart-before-test` before
> presenting this checklist. User exercises each scenario in the running
> app and types `approved` to resume the executor.

---

## Pre-flight (executor-performed)

- [ ] Backend killed + reinstalled + restarted on :8000
- [ ] Frontend `npm run build` + dev server restarted on :5173
- [ ] Both health-checks responsive
- [ ] Iberia 868 project generated and selected in the UI

---

## Scenarios

### 1. Zero-LLM Export (SC #1)

Action: click **Exportar ZIP** with NO LLM credentials configured anywhere.
Expected: ZIP downloads with raw slugs / `Condado_NNN` names; no LLM names
appear. The `MANIFEST.research_overlay_applied` is `false`.

Result: ⬜ pending / ✅ pass / ❌ fail
Notes:

---

### 2. Research dialog open

Action: clear selection → click **Pesquisar metadados históricos** in
InspectorSidebar.
Expected: Radix Dialog opens with 4 fields (country / period / provider /
model).

Result: ⬜ pending / ✅ pass / ❌ fail
Notes:

---

### 3. Submit + SSE per-stage progress

Action: pick Ollama provider + model → click **Iniciar pesquisa**.
Expected: per-stage progress renders; success Toast appears; dialog
auto-closes ~1.2 s after completion.

Result: ⬜ pending / ✅ pass / ❌ fail
Notes:

---

### 4. Pesquisa aplicada badge

Action: click a covered condado on the canvas.
Expected: InspectorSidebar shows the historical name + a green
**Pesquisa aplicada** badge + an **Atualizar pesquisa** link.

Result: ⬜ pending / ✅ pass / ❌ fail
Notes:

---

### 5. Microcopy (BLOCKER 2 + REVIEWS fix #2)

Action: clear selection. Observe placeholder microcopy.
Expected: EITHER single-line `Última pesquisa: {provider} · {model} ·
{YYYY-MM-DD HH:mm}` (fresh-run case) OR two-line `Pesquisa gerada: ... ·
aplicada: ...` (cache-hit case). To verify the cache-hit branch: re-run
research with force-refresh OFF on a previously researched country+period.

Result: ⬜ pending / ✅ pass / ❌ fail
Notes:

---

### 6. Export with overlay (SC #2)

Action: click **Exportar ZIP** while overlay is active → unzip.
Expected: `condados[*].name` reflects historical names from overlay;
`MANIFEST.research_overlay_applied == true`.

Result: ⬜ pending / ✅ pass / ❌ fail
Notes:

---

### 7. Export 422 envelope (D-10)

Action: deliberately break a project's pipeline output (e.g., delete or
corrupt `territory_metadata.json`) → click **Exportar ZIP**.
Expected: **Falha ao exportar** dialog with PT-BR rows; **Validar antes
de exportar** inline preview also surfaces the errors.

Result: ⬜ pending / ✅ pass / ❌ fail
Notes:

---

### Subjective review

- PT-BR copy quality across dialog + badge + export envelope: ⬜ / ✅ / ❌
- Visual fidelity vs `ParameterSidebar` / `NewProjectModal`: ⬜ / ✅ / ❌

---

## User Sign-off

When all 7 scenarios pass (including microcopy at #5), type `approved` in
chat so the orchestrator can resume and write `07-11-SUMMARY.md`.

If any scenario fails, describe the issue inline — the executor will
diagnose and resume with a fix before re-asking for UAT.
