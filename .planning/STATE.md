---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Phase 5 UI-SPEC approved
last_updated: "2026-04-27T11:44:19.755Z"
last_activity: 2026-04-27 -- Phase 05 execution started
progress:
  total_phases: 7
  completed_phases: 4
  total_plans: 29
  completed_plans: 27
  percent: 93
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-16)

**Core value:** A Game Designer can go from "country + historical period" to a validated, Unity-ready map package without manual pixel editing or blind iteration.
**Current focus:** Phase 05 — canvas-editing-advanced

## Current Position

Phase: 05 (canvas-editing-advanced) — EXECUTING
Plan: 1 of 3
Status: Executing Phase 05
Last activity: 2026-04-28 - Completed quick task 260428-h1t: Etapa 8 (PATCH /research/assignments backend)

Progress: [█████░░░░░] 50% (3 of 6 phases plan-complete; verification pending)

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Data Pipeline + Backend Scaffold | 5/5 | — | — |
| 2. Read-Only Canvas Viewer | 5/5 | — | — |
| 3. LLM Research Integration | 4/4 | — | — |
| 4. Canvas Editing — Basic | 0/4 | — | — |
| 5. Canvas Editing — Advanced | 0/2 | — | — |
| 6. Validation Gate + Export Polish | 0/3 | — | — |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 02 P04 | 25 | 3 tasks | 10 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Initialization]: React 19 + react-konva 19.2.x (not React 18 — peer-dep alignment)
- [Initialization]: Vite 6 (not v5 — two majors behind, migration is smooth)
- [Initialization]: zundo 2.3.0 (not v3 — does not exist on npm; v2 uses `temporal` middleware)
- [Initialization]: rasterio pinned `>=1.4,<1.5` (1.5+ requires Python 3.12; project targets 3.11)
- [Initialization]: aiosqlite pinned `>=0.20,<0.22` (v0.22.0 hanging thread regression — issue #13039)
- [Initialization]: Tailwind v4 CSS-first config (`@theme` in CSS, no `tailwind.config.js`; Radix CSS must import before Tailwind `@import`)
- [Initialization]: Phase 3 (LLM) has no canvas dependency — can run in parallel with Phase 2 if bandwidth allows
- [Initialization]: EXPORT-01/02 delivered headlessly in Phase 1; EXPORT-03/04 (polish + dialog) deferred to Phase 6
- [Phase 02]: Plan 02-04 closed gaps G-01/G-02/G-03 via service-layer adapter rewrite (D-04 black-box preserved); added condado_colors.json and barony_colors.json sidecars for frontend consumption

### Pending Todos

None yet.

### Blockers/Concerns

**Pre-Phase 1 items to verify immediately:**

- `map_generator.py` importability: must confirm it has `if __name__ == "__main__"` guards before building `services/generator.py` wrapper
- Tailwind v4 + Radix UI transparency bug (GitHub #17137): plan a UI component smoke-test early in Phase 2

**Phase 4 research flag:**

- zundo partialize+diff at real scale: spike with real Iberia GeoJSON (~91 territories) to measure actual snapshot size before committing to diff strategy

**Phase 6 research flag:**

- Unity 12-file spec: verify against current Unity 6 grand strategy community practice during Phase 6 planning

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260417-hpt | remove rivers generation from pipeline | 2026-04-17 | 4ea6444 | [260417-hpt-remove-rivers-generation-from-pipeline](./quick/260417-hpt-remove-rivers-generation-from-pipeline/) |
| 260417-jq1 | Carregar centroids curados de territory_data_v3 no template Iberia | 2026-04-17 | 2eec56e | [260417-jq1-carregar-centroids-curados-de-territory-](./quick/260417-jq1-carregar-centroids-curados-de-territory-/) |
| 260420-hkr | fix blank-page on territory click (hoist neighbors) + ErrorBoundary + rename layers + color legend card | 2026-04-20 | 6d8b9e9 | [260420-hkr-fix-blank-page-on-territory-click-hoist-](./quick/260420-hkr-fix-blank-page-on-territory-click-hoist-/) |
| 260420-hkr+ | encoding fix + neighbors bug + borders layer + km² area + capital fallback | 2026-04-20 | 075b98c | [260420-hkr-fix-blank-page-on-territory-click-hoist-](./quick/260420-hkr-fix-blank-page-on-territory-click-hoist-/) |
| 260422-eue | Add google-auth-oauthlib to pyproject.toml | 2026-04-22 | 6eab700 | [260422-eue-add-google-auth-oauthlib-to-pyproject-to](./quick/260422-eue-add-google-auth-oauthlib-to-pyproject-to/) |
| 260422-f0s | Add anthropic SDK to pyproject.toml | 2026-04-22 | 279b9d5 | [260422-f0s-add-anthropic-sdk-to-pyproject-toml-depe](./quick/260422-f0s-add-anthropic-sdk-to-pyproject-toml-depe/) |
| 260422-f6f | Add all missing LLM provider deps (google-genai, ollama, openai, google-auth-oauthlib) | 2026-04-22 | b1e683f | [260422-f6f-add-all-missing-llm-provider-deps-to-pyp](./quick/260422-f6f-add-all-missing-llm-provider-deps-to-pyp/) |
| 260422-fzh | Fix Ollama structured output: format=schema.model_json_schema() instead of format=json | 2026-04-22 | 7081547 | [260422-fzh-fix-ollama-provider-to-use-grammar-const](./quick/260422-fzh-fix-ollama-provider-to-use-grammar-const/) |
| 260422-eue | Add google-auth-oauthlib to pyproject.toml dependencies | 2026-04-22 | 6eab700 | [260422-eue-add-google-auth-oauthlib-to-pyproject-to](./quick/260422-eue-add-google-auth-oauthlib-to-pyproject-to/) |
| 260422-f0s | Add anthropic SDK to pyproject.toml dependencies | 2026-04-22 | 279b9d5 | [260422-f0s-add-anthropic-sdk-to-pyproject-toml-depe](./quick/260422-f0s-add-anthropic-sdk-to-pyproject-toml-depe/) |
| 260422-gts | Fix mocked Ollama unit test: correct Duchy payload shape and update format assertion to grammar-constrained schema dict | 2026-04-22 | 81353e0 | [260422-gts-fix-mocked-ollama-unit-test-correct-duch](./quick/260422-gts-fix-mocked-ollama-unit-test-correct-duch/) |
| 260422-h24 | Add manual paste provider: copy generated prompt, paste response from any external chat to populate territories | 2026-04-22 | be38a86 | [260422-h24-add-manual-paste-provider-copy-generated](./quick/260422-h24-add-manual-paste-provider-copy-generated/) |
| 260422-hl9 | Fix UTF-8 encoding bug: write_text() without encoding=utf-8 corrupts non-ASCII chars on Windows | 2026-04-22 | df0cc8b | [260422-hl9-fix-utf-8-encoding-bug-write-text-withou](./quick/260422-hl9-fix-utf-8-encoding-bug-write-text-withou/) |
| 260422-i0q | Manual provider file I/O (download prompt, upload response) + stronger baronies prompt with centroids | 2026-04-22 | 45bb03a | [260422-i0q-manual-provider-file-i-o-download-prompt](./quick/260422-i0q-manual-provider-file-i-o-download-prompt/) |
| 260422-k6e | Remove baronies limit + require historical documentation refs + rebuild frontend | 2026-04-22 | 3a48164 | [260422-k6e-remove-baronies-limit-require-historical](./quick/260422-k6e-remove-baronies-limit-require-historical/) |
| 260422-ktb | Apply research result to canvas: color territories by kingdom + auto-load cached research + inspector badges | 2026-04-22 | 00fc737 | [260422-ktb-apply-research-result-to-canvas-color-te](./quick/260422-ktb-apply-research-result-to-canvas-color-te/) |
| 260422-l7g | Fix research flow: dates persist to project + country_qid supports multi-country (Q29,Q45) | 2026-04-22 | acd858b | [260422-l7g-fix-research-flow-date-changes-must-pers](./quick/260422-l7g-fix-research-flow-date-changes-must-pers/) |
| 260422-m1f | Fix MultiPolygon territories rendering as white and non-clickable on canvas | 2026-04-22 | d96c9a4 | [260422-m1f-fix-multipolygon-territories-rendering-a](./quick/260422-m1f-fix-multipolygon-territories-rendering-a/) |
| 260426-pcy | Fix orphan bug: 13 condados in territory_metadata.json missing from territories.geojson — generation pipeline drops territories without OSM polygon match | 2026-04-26 | 3095107 | [260426-pcy-fix-orphan-bug-13-condados-in-territory-](./quick/260426-pcy-fix-orphan-bug-13-condados-in-territory-/) |
| 260426-q3v | Fix orphan bug: Gerar mapa uses stale 4-condado research file instead of rich cached research from DB | 2026-04-26 | 29a31f1 | [260426-q3v-fix-orphan-bug-gerar-mapa-uses-stale-4-c](./quick/260426-q3v-fix-orphan-bug-gerar-mapa-uses-stale-4-c/) |
| 260426-qc0 | Fix orphan bug: vertex-handles endpoint ignores target parameter — decimate_polygon is no-op | 2026-04-26 | e1228fc | [260426-qc0-fix-orphan-bug-vertex-handles-endpoint-i](./quick/260426-qc0-fix-orphan-bug-vertex-handles-endpoint-i/) |
| 260426-qlo | Fix orphan bug: recalc_neighbors does not clip Voronoi cells to land mask after capital move | 2026-04-26 | 6e252ba | [260426-qlo-fix-orphan-bug-recalc-neighbors-does-not](./quick/260426-qlo-fix-orphan-bug-recalc-neighbors-does-not/) |
| 260426-qvu | Fix orphan bug: project.updated_at not bumped on edit endpoints | 2026-04-26 | 30aee4d | [260426-qvu-fix-orphan-bug-project-updated-at-not-bu](./quick/260426-qvu-fix-orphan-bug-project-updated-at-not-bu/) |
| 260428-elq | Etapa 2: Baronies Builder + endpoint /baronies + slider UI | 2026-04-28 | e807714 | [260428-elq-etapa-2-baronies-builder-endpoint-baroni](./quick/260428-elq-etapa-2-baronies-builder-endpoint-baroni/) |
| 260428-ewx | Etapa 3: schemas split — MapResearchResult + barony_assignments + cross-ref validator | 2026-04-28 | 3c914b8 | [260428-ewx-etapa-3-schemas-split-mapresearchresult-](./quick/260428-ewx-etapa-3-schemas-split-mapresearchresult-/) |
| 260428-f9x | Etapa 4: model routing — TASK_MODEL_TIERS / TASK_DEFAULT_EFFORT / resolve_model + research_runner integration | 2026-04-28 | 883f5eb | [260428-f9x-etapa-4-model-routing-multi-modelo-model](./quick/260428-f9x-etapa-4-model-routing-multi-modelo-model/) |
| 260428-fjc | Etapa 5: Llama.cpp provider local — LlamaCppProvider + registry + AuthSetupSheet panel | 2026-04-28 | b5c7130 | [260428-fjc-etapa-5-llama-cpp-provider-local-llamacp](./quick/260428-fjc-etapa-5-llama-cpp-provider-local-llamacp/) |
| 260428-fuy | Etapa 6: Adapt research pipeline — build_map_research_prompt(baronies) + validate_barony_assignments self-consistency | 2026-04-28 | 07733a2 | [260428-fuy-etapa-6-adapt-research-pipeline-build-ma](./quick/260428-fuy-etapa-6-adapt-research-pipeline-build-ma/) |
| 260428-g5g | Etapa 7: Territory builder reconstruído — assemble_territory_data_from_baronies aggregates baronies into condados via barony_assignments (4 tests) | 2026-04-28 | 2189315 | [260428-g5g-etapa-7-reconstruir-territory-builder-py](./quick/260428-g5g-etapa-7-reconstruir-territory-builder-py/) |
| 260428-h0p | Etapa 7b: wire build_map_research_prompt + assignments validation + cache dispatch into research_runner (6 tests) | 2026-04-28 | 153fca8 | [260428-h0p-etapa-7b-wire-map-research-runner](./quick/260428-h0p-etapa-7b-wire-map-research-runner/) |
| 260428-h1t | Etapa 8: PATCH /research/assignments — backend endpoint + condado renames + cache persistence (6 tests) | 2026-04-28 | ae6d341 | [260428-h1t-etapa-8-patch-research-assignments-endpo](./quick/260428-h1t-etapa-8-patch-research-assignments-endpo/) |

## Session Continuity

Last session: 2026-04-28
Stopped at: Etapa 8 (PATCH /research/assignments backend) complete — 246 tests passing
Resume file: C:\Users\veio_\.claude\plans\hazy-hatching-abelson.md (Etapa 8b — AssignmentEditor.tsx frontend; or Etapa 9 — Codex schema + runner + endpoint)
