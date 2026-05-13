---
status: complete
phase: 05-region-generalization
source: [05-01-SUMMARY.md, 05-04-SUMMARY.md, 05-06-SUMMARY.md, 05-07-SUMMARY.md, 05-08-SUMMARY.md, 05-09-SUMMARY.md, 05-10-SUMMARY.md, 05-11-SUMMARY.md, 05-14-SUMMARY.md]
started: 2026-05-13T17:00:00Z
updated: 2026-05-13T17:10:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running medieval-forge / uvicorn / vite processes. Start `medieval-forge start` from scratch. Server boots without errors, migrations run, and `GET /api/v3/regions` returns HTTP 200 with a JSON array containing at least iberia_868 and france_1066. Frontend at http://localhost:5173 loads without console errors. No regression from Plans 04/07 edits to main.py (alembic 0004/0005, v3/projects + v3/regions router registration).
result: pass
notes: backend on port 8765, /api/v3/regions returned 3 regions (england_1216 has_dataset:false, france_1066 has_dataset:true, iberia_868 has_dataset:true). Frontend loaded at 5173. Only console errors are favicon.ico 404 (pre-existing, unrelated to Phase 05).

### 2. New Project button opens modal (not navigates)
expected: On the Project List page, clicking the "Novo projeto" button opens an in-page dialog modal — it does NOT navigate to /projects/new. The modal contains a name text field and a region dropdown. The URL stays on / (or /projects) while the modal is open.
result: pass
notes: Playwright confirmed URL stayed at /projects after click. Dialog "Novo projeto" appeared with name textbox, region combobox, disabled "Criar projeto" button.

### 3. Region dropdown shows available regions with correct states
expected: Inside the New Project modal, the region dropdown lists at least 3 entries: "Iberia 868 AD" (enabled), "France 1066" (enabled), "England 1216" (disabled, shows "(sem dataset)" suffix). Default selection is iberia_868. Loading state shows "Carregando regiões..." while fetching. If the API call fails, a toast appears with a "Tentar novamente" retry button.
result: pass
notes: Playwright snapshot confirmed — "England 1216 AD (sem dataset)" [disabled], "France 1066 AD" enabled, "Iberia 868 AD" [active][selected] by default.

### 4. Create a new project with France 1066 region
expected: In the modal, enter any project name (e.g. "UAT France 1066"), select "France 1066" from the dropdown, click "Criar projeto". The button is disabled until both name (1–64 chars) and a has_dataset:true region are selected. After submit, the modal closes and the browser navigates to /projects/{uuid}. The project workspace (workspace-toolbar) is visible on that page.
result: pass
notes: Selected France 1066, typed "UAT France 1066" — button became enabled. After click navigated to /projects/e7d6f693-f333-4f66-9bae-5fb5bfadec0e. workspace-toolbar visible with project name + "Gerar Mapa" + "Exportar ZIP" buttons.

### 5. England 1216 is disabled and cannot be submitted
expected: In the New Project modal, selecting "England 1216" (the disabled item with "(sem dataset)") should not be possible — clicking it has no effect or the item is visually disabled and unselectable. The "Criar projeto" submit button remains disabled if no enabled region is selected.
result: pass
notes: Playwright snapshot showed England 1216 option as [disabled] in the listbox — unselectable per Radix Select behavior.

### 6. France 1066 pipeline produces 12-file export via API
expected: With a project created using france_1066 region_key, calling `POST /api/v3/projects/{id}/export` returns a ZIP containing all 12 Unity contract files + MANIFEST.json. Confirmed via backend pytest.
result: pass
notes: `pytest backend/tests/e2e/test_france_1066_export_contract.py -v` → 8 passed in 6.99s. Tests cover always-present files, lookup/visual/mask dimensions, JSON schema validity, terrain_types schema, terrain palette, original_idx uniqueness.

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]
