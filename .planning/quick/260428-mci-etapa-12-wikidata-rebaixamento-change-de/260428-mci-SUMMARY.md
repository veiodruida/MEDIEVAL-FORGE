---
phase: quick-260428-mci
plan: 01
subsystem: frontend-pipeline-ui, backend-ingest
tags: [ux, wikidata, osm, documentation, ui-demotion]
dependency_graph:
  requires: []
  provides: [osm-primary-cta, wikidata-demoted-advanced]
  affects: [frontend/src/pages/ProjectDetail.tsx, backend/medieval_forge/services/ingest_wikidata.py]
tech_stack:
  added: []
  patterns: [native-details-disclosure, module-docstring-deprecation]
key_files:
  modified:
    - frontend/src/pages/ProjectDetail.tsx
    - backend/medieval_forge/services/ingest_wikidata.py
decisions:
  - "Used native <details>/<summary> HTML element for Avançado disclosure (zero-dep, accessible, matches project minimal-ceremony style)"
  - "Retained ingest.start('wikidata') wiring unchanged — only UI location changed"
metrics:
  duration: ~5min
  completed: "2026-04-28"
  tasks_completed: 2
  files_modified: 2
---

# Quick Task 260428-mci: Etapa 12 — Wikidata UI Demotion + Deprecation Comment Summary

**One-liner:** OSM promoted as sole primary CTA in Step 1; Wikidata hidden behind native `<details>` Avançado disclosure + module marked DEPRECATED in ingest_wikidata.py.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Demote Wikidata button into Avançado disclosure in Step 1 | 381dd63 | frontend/src/pages/ProjectDetail.tsx |
| 2 | Add deprecation/secondary-path comment to ingest_wikidata.py | 1b60eee | backend/medieval_forge/services/ingest_wikidata.py |

## Changes Made

### Task 1 — ProjectDetail.tsx Step 1 footer

- OSM button is now the primary CTA: no `variant="soft"`, label `'1. OSM com polígonos (recomendado)'`, renders first.
- Modern map button renumbered: label changed from `'1c. Mapa moderno (validar dados)'` to `'2. Mapa moderno (validar dados)'`.
- Wikidata button wrapped in `<Box mt="2"><details><summary>Avançado</summary>...</details></Box>`:
  - Collapsed by default (native HTML behavior).
  - Label: `'Wikidata (só pontos — legado)'`.
  - Gray caption: `"Apenas pontos. Não gera polígonos. Use só se OSM falhar para a região."`.
- `ingest.start('wikidata')` wiring preserved intact.
- Status cards / callouts below the footer untouched.

### Task 2 — ingest_wikidata.py

- Module docstring expanded with deprecation block:
  - Marks `DEPRECATED (Etapa 12, 2026-04-28)`.
  - Explains Wikidata is a secondary/points-only fallback retained when OSM fails.
  - Points to `ingest_osm.py` as recommended flow.
  - Notes frontend hides provider behind Avançado disclosure.
  - Warns against re-promoting to primary CTA without addressing the all-blue maps UX issue.
- No runtime code, function signatures, or imports changed.

## Verification

- `cd frontend && npm test -- --run` → 222/222 tests passed.
- `cd backend && python -m pytest tests/ -x` → 267/267 tests passed.
- `grep -n "DEPRECATED" backend/medieval_forge/services/ingest_wikidata.py` → line 3.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — no data stubs introduced.

## Threat Flags

None — changes are UI demotion + documentation only; no new network endpoints or auth paths introduced.

## Self-Check: PASSED

- `frontend/src/pages/ProjectDetail.tsx` — exists and modified (confirmed by edit).
- `backend/medieval_forge/services/ingest_wikidata.py` — exists and modified (confirmed by edit).
- Commit `381dd63` — confirmed in git log.
- Commit `1b60eee` — confirmed in git log.
