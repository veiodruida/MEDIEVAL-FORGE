---
phase: quick-260428-mci
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/src/pages/ProjectDetail.tsx
  - backend/medieval_forge/services/ingest_wikidata.py
autonomous: true
requirements:
  - QUICK-260428-mci
must_haves:
  truths:
    - "OSM is the visible/default ingestion path for new users"
    - "Wikidata ingestion button is hidden behind an 'Avançado' (Advanced) disclosure in Step 1 — not removed, just demoted"
    - "ingest_wikidata.py contains a docstring/comment explaining that Wikidata is a legacy/secondary path retained only for points-only fallback (kept for backward compatibility, not the recommended flow)"
    - "Frontend tests still pass after the UI change"
  artifacts:
    - path: "frontend/src/pages/ProjectDetail.tsx"
      provides: "Step 1 UI with OSM as primary CTA and Wikidata hidden inside an 'Avançado' collapsible"
      contains: "Avançado"
    - path: "backend/medieval_forge/services/ingest_wikidata.py"
      provides: "Wikidata ingestion module with deprecation/secondary-path comment"
      contains: "DEPRECATED"
  key_links:
    - from: "frontend/src/pages/ProjectDetail.tsx (Step 1 StepCard footer)"
      to: "ingest.start('wikidata')"
      via: "Button rendered only inside Avançado disclosure"
      pattern: "ingest\\.start\\('wikidata'\\)"
---

<objective>
Etapa 12 — Demote Wikidata ingestion in the UI and document its secondary status in code.

Purpose: The OSM ingestion path is the recommended flow (provides polygons; Wikidata is points-only and produces unusable all-blue maps). Currently the Wikidata button "1a. Wikidata (só pontos)" sits next to OSM as a peer CTA, confusing new users. This task hides it behind an "Avançado" (Advanced) disclosure and adds a code-level note in `ingest_wikidata.py` so future maintainers understand it is a legacy/secondary path retained for points-only fallback.

Output:
- `ProjectDetail.tsx` Step 1 footer: OSM button stays primary; Wikidata button moved inside an "Avançado" collapsible (Radix details/disclosure).
- `ingest_wikidata.py`: top-of-file comment marking Wikidata as a secondary/deprecated path.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md

@frontend/src/pages/ProjectDetail.tsx
@backend/medieval_forge/services/ingest_wikidata.py

<interfaces>
<!-- Current Step 1 footer (ProjectDetail.tsx ~lines 176-201) -->
```tsx
footer={
  <>
    <Button variant="soft" onClick={() => ingest.start('wikidata')} disabled={ingest.isStreaming}>
      {ingest.isStreaming ? 'Ingerindo…' : '1a. Wikidata (só pontos)'}
    </Button>
    <Button onClick={() => ingest.start('osm')} disabled={ingest.isStreaming}>
      {ingest.isStreaming ? 'Ingerindo…' : '1b. OSM com polígonos (recomendado)'}
    </Button>
    <Button variant="soft" color="blue" onClick={() => renderModern.mutate(...)} ...>
      {renderModern.isPending ? 'Renderizando…' : '1c. Mapa moderno (validar dados)'}
    </Button>
  </>
}
```

<!-- ingest_wikidata.py top of file -->
```python
"""INGEST-01: Wikidata SPARQL paginated municipality fetcher.

T-SSRF mitigation: validate_qid enforces ^Q\\d+$ before composing the query;
endpoint URL is a hardcoded constant — never assembled from user input.
"""
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Demote Wikidata button into 'Avançado' disclosure in Step 1</name>
  <files>frontend/src/pages/ProjectDetail.tsx</files>
  <action>
In the Step 1 `StepCard` footer (~lines 176-201 of `frontend/src/pages/ProjectDetail.tsx`):

1. Reorder so that the OSM button (`'1. OSM com polígonos (recomendado)'`) becomes the primary CTA — it must render first and use the default Button variant (no `variant="soft"`). Drop the "1b." prefix from the label since it is now the primary path; final label: `'1. OSM com polígonos (recomendado)'`.
2. Keep the "Mapa moderno (validar dados)" button visible as before. Renumber its label from `'1c.'` to `'2. Mapa moderno (validar dados)'`.
3. Move the Wikidata button into a Radix UI disclosure labelled "Avançado". Use a native `<details>` element styled with Radix `Text`/`Box`, OR Radix `Collapsible` if the project already imports it. Inside the disclosure, render the Wikidata button with label `'Wikidata (só pontos — legado)'` and a small caption `<Text size="1" color="gray">` explaining: "Apenas pontos. Não gera polígonos. Use só se OSM falhar para a região.".
4. The disclosure must be COLLAPSED by default.
5. Do NOT remove or alter `ingest.start('wikidata')` wiring — only relocate the button.
6. Do NOT touch the existing status-cards / callouts below the footer (the "Dados Wikidata guardados" message and the "Sem dados geográficos" callout remain unchanged — they are factual status, not CTAs).
7. Run `npm run build` (or the project's typecheck) to confirm no TS errors. Run frontend tests.

Implementation note: prefer a plain `<details><summary>Avançado</summary>...</details>` block — it is zero-dep, accessible, and matches the project's "minimal ceremony" style. Wrap with `<Box mt="2">` for spacing.
  </action>
  <verify>
    <automated>cd frontend && npm test -- --run</automated>
  </verify>
  <done>
- OSM button is the first/primary CTA in Step 1 footer (no soft variant).
- Wikidata button no longer appears at top level of Step 1 footer.
- Clicking "Avançado" expands a section that reveals the Wikidata button.
- Wikidata click still triggers `ingest.start('wikidata')`.
- All 222 frontend tests still pass.
- Typecheck/build succeeds.
  </done>
</task>

<task type="auto">
  <name>Task 2: Add deprecation/secondary-path comment to ingest_wikidata.py</name>
  <files>backend/medieval_forge/services/ingest_wikidata.py</files>
  <action>
Edit the module docstring at the top of `backend/medieval_forge/services/ingest_wikidata.py` (lines 1-5). Replace it with:

```python
"""INGEST-01: Wikidata SPARQL paginated municipality fetcher.

DEPRECATED (Etapa 12, 2026-04-28): Wikidata is now a SECONDARY ingestion path,
retained only as a points-only fallback when OSM fails for a given bounding box.
The recommended flow is OSM (see ingest_osm.py) which provides real polygons.
The frontend hides this provider behind an "Avançado" (Advanced) disclosure in
Step 1 of ProjectDetail. Do NOT promote this back to a primary CTA without
revisiting the points-only / no-polygons UX limitation that produces all-blue
maps downstream.

T-SSRF mitigation: validate_qid enforces ^Q\\d+$ before composing the query;
endpoint URL is a hardcoded constant — never assembled from user input.
"""
```

Do NOT touch any function bodies, signatures, or runtime behaviour — this is a documentation-only change. Run the backend test suite to confirm no regressions (the docstring change should be inert).
  </action>
  <verify>
    <automated>cd backend && python -m pytest tests/ -x --no-header -q 2>&1 | tail -20</automated>
  </verify>
  <done>
- File starts with the new docstring containing the word "DEPRECATED" and a clear note that Wikidata is a secondary/legacy path.
- No code (function bodies, imports, constants) was modified.
- Backend test suite passes (no regressions from docstring edit — should be a no-op for runtime).
  </done>
</task>

</tasks>

<verification>
- Visual: open project detail page → Step 1 → confirm OSM is the primary button and Wikidata is hidden under "Avançado".
- Click "Avançado" → Wikidata button appears → clicking it still triggers ingestion.
- `grep -n "DEPRECATED" backend/medieval_forge/services/ingest_wikidata.py` returns the new comment.
- `cd frontend && npm test -- --run` → all tests pass (222+).
- `cd backend && python -m pytest tests/ -x` → all tests pass.
</verification>

<success_criteria>
- OSM is the visible/default ingestion CTA; Wikidata requires expanding "Avançado" to access.
- `ingest_wikidata.py` documents its secondary/legacy status at the top of the file.
- No regressions in frontend or backend test suites.
- No changes to runtime behaviour of either provider — only UI demotion + code documentation.
</success_criteria>

<output>
After completion, create `.planning/quick/260428-mci-etapa-12-wikidata-rebaixamento-change-de/260428-mci-SUMMARY.md`.
</output>
