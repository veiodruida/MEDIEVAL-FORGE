---
phase: quick-260422-i0q
plan: 01
subsystem: frontend/research + backend/llm
tags: [manual-provider, file-io, prompt-engineering, ux]
dependency_graph:
  requires: [260422-h24]
  provides: [prompt-download, response-file-upload, stronger-baronies-prompt]
  affects: [ManualResearchPanel, build_research_prompt]
tech_stack:
  added: []
  patterns: [Blob+createObjectURL download, FileReader.readAsText upload]
key_files:
  created: []
  modified:
    - frontend/src/components/research/ManualResearchPanel.tsx
    - backend/medieval_forge/services/llm/prompt.py
decisions:
  - Used fragment <></> to wrap Copiar + Baixar prompt inside existing {prompt && (...)} conditional — avoids rendering download button before prompt exists
  - Used ChangeEvent<HTMLInputElement> import form (not React.ChangeEvent) — consistent with file's existing named-import style
  - Pre-existing test failures (test_llm_retry, test_llm_schemas, etc.) confirmed out-of-scope; not introduced by this task
metrics:
  duration: 15m
  completed: "2026-04-22"
  tasks_completed: 3
  files_modified: 2
---

# Quick 260422-i0q: Manual Provider File I/O + Download Prompt — Summary

**One-liner:** Added `prompt.txt` download button and `FileReader`-based file upload to `ManualResearchPanel`, plus three Portuguese LLM directive rules enforcing per-condado barony coverage, realistic coordinates, and plausible historical names.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Frontend: download-prompt + upload-response | 8ca20e7 | ManualResearchPanel.tsx |
| 2 | Backend: strengthen baronies prompt rules 9-11 | 45bb03a | prompt.py |
| 3 | Run backend unit tests (verification only) | — (no files changed) | — |

## What Was Built

### Task 1 — Frontend ergonomics

`ManualResearchPanel.tsx` gains two new capabilities:

- **"Baixar prompt" button** (next to "Copiar", inside `{prompt && ...}` conditional): uses `Blob` + `URL.createObjectURL` + synthetic anchor to trigger a `prompt.txt` download. Button only renders after a prompt is generated — no extra disabled state needed.

- **"Carregar arquivo" file input** (above the response `TextArea`): wrapped in a `Button asChild` + `label` pattern (Radix idiom for styled file inputs). Uses `FileReader.readAsText(file, "utf-8")` to populate the `response` state. Input value is reset after each read so the same file can be reselected. Manual paste into the TextArea continues to work unchanged.

Import updated: `import { useState, type ChangeEvent } from "react"` — consistent with existing named-import style.

### Task 2 — Prompt robustness

`build_research_prompt()` in `prompt.py` gains three new rules appended to `RULES`:

- **Rule 9 (Coverage):** `Gere EXATAMENTE 1-3 baronias para CADA condado listado. NÃO omita nenhum condado.` — forces `baronies` to have one key per `condado_id`.
- **Rule 10 (Coordinates):** `NUNCA use coordenadas 0.0, 0.0.` — references condado centroid `lon`/`lat` fields for realistic placement (±0.2° tolerance).
- **Rule 11 (Names):** Prohibits `"Baronia de <condado>"` lazy naming; requires historically documented locality/village/noble family names.

The condados-list framing line was updated to explicitly call out `lon`/`lat` centroid fields as barony coordinate references.

No schema change — `ResearchResult` top-level keys (`kingdoms`, `duchies`, `condados_assignment`, `baronies`) unchanged.

### Task 3 — Backend unit test verification

All pre-existing passing tests still pass (25/25). Pre-existing failures (8 tests across `test_llm_retry.py`, `test_llm_schemas.py`, `test_condado_assignment.py`, `test_auth_session.py`, `test_oauth_flow.py`, `test_llm_registry.py`) confirmed identical before and after these changes — zero regressions introduced.

## Deviations from Plan

None — plan executed exactly as written. The pre-existing test failures are out-of-scope per deviation rules and documented below.

## Known Pre-existing Test Failures (Out of Scope)

| Test file | Count | Notes |
|-----------|-------|-------|
| test_llm_retry.py | 1 (collection error) | Pydantic `ValidationError` on module-level `_VALID_RESULT` fixture — `Duchy` expects dict, receives list |
| test_llm_schemas.py | 1 | Related `ResearchResult` schema test |
| test_condado_assignment.py | 3 | Pre-existing condado assignment test failures |
| test_auth_session.py | 1 | Credentials in-memory vs disk source mismatch |
| test_oauth_flow.py | 1 | OAuth callback `source` field mismatch |
| test_llm_registry.py | 1 | Provider count assertion |

These failures exist on the commit before this task (`45bb03a~1`) and are unrelated to prompt.py or ManualResearchPanel.tsx changes.

## Self-Check: PASSED

- `frontend/src/components/research/ManualResearchPanel.tsx` — exists, modified
- `backend/medieval_forge/services/llm/prompt.py` — exists, modified
- Commit `8ca20e7` — verified in git log
- Commit `45bb03a` — verified in git log
- `npx tsc --noEmit` — zero errors related to ManualResearchPanel
- `build_research_prompt()` assertion check — `OK`
