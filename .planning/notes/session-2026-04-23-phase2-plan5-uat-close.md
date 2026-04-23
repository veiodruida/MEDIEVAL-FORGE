---
type: session-notes
date: 2026-04-23
phase: 02-read-only-canvas-viewer
plan: 05
status: complete
next: human UAT re-verification OR advance to Phase 03 LLM research integration
---

# Session 2026-04-23 — Phase 02 Plan 05 execution + post-UAT UX polish + territory data fix

## Goal

Close the 5 GAPs (GAP-04 through GAP-08) opened by the human re-test on
2026-04-18, then respond to new bugs surfaced during manual UAT on the
running pipeline.

## Work Done

### Plan 02-05 main execution (Tasks 1–5)

Ran `/gsd-execute-phase 02 --interactive`. Discovered that Tasks 1 (GAP-05
ResizeObserver callback-ref) had already been shipped by prior quick
tasks; only drift fixes, cacheVersion regression test, Tooltip/threshold,
and ErrorBoundary were new work.

- **3247177** — regression guard: `manualResult?.kingdoms` + partial
  `computeCondadoColors` shielding (recovered 13 of 16 failing tests
  introduced by quick-task 260422-ktb)
- **6f8fc2c** — GAP-04 Task 2 diagnosis: ran 3 curls against real Iberia
  project on port 8765 → 100% overlap, H4 confirmed, backend clean
- **e5dc1cb** — GAP-04 H4 regression test: asserts `?v=<cacheVersion>`
  propagation on all 5 preview URLs + absence when undefined
- **dc3d0da** — GAP-08: threshold 2.0 → 1.5 + Radix Tooltip; boundary
  tests at exact 1.5× and 1.49× for strict `>=` semantics
- **2128c30** — GAP-07: install `react-error-boundary@^4`, wrap
  `InspectorSidebarWrapper` with visible Radix Callout fallback;
  T-02-05-02 no-leak test explicitly checks absence of `err.stack`
- **3d155dc** — `02-05-SUMMARY.md` covering 5 GAPs, 101/104 vitest green,
  D-04 preserved
- **4be40d1** — HUMAN-UAT status: `gaps_found` → `fixes_landed_pending_reverify`;
  each gap annotated with `fix_landed:` commit pointer; ROADMAP 02-05 marked complete

### Post-UAT bug fixes (user ran the pipeline and reported)

- **f91af71** — Fit button invisible (covered by LegendCard at bottom-left
  since quick-task 260420-hkr). Moved Fit to bottom-right + added inline
  "(zoom ≥ 1.5×)" hint on Labels row so discoverability no longer depends
  on hover
- **fff47c0** — Coimbra + Aveiro visually merged on the Portuguese coast.
  Root cause: Aveiro was a barony of Viseu, so Viseu's Voronoi cell
  stretched from its inland centroid to the Atlantic. Split: created
  `aveiro` condado with baronies [Aveiro, Ovar, Estarreja, Águeda]; Viseu
  kept [Viseu, Mangualde, Tondela]; Coimbra kept [Coimbra, Montemor-o-Velho,
  Figueira da Foz]. JSON: 92 → 93 condados
- **c84d4b5** — todo captured: `useTerritoryTemplate` staleTime:Infinity +
  `templateLoaded` gate mean users must hard-refresh to pick up
  `territory_iberia.json` edits. Fix deferred
- **70020d5** — The real "Aveiro is unknown on click" bug:
  `InspectorSidebarWrapper` was calling `useCanvasArtifacts(projectId, …)`
  WITHOUT `cacheVersion`, while `CanvasViewer` passed
  `cacheVersion={project.updated_at}`. Two distinct TanStack cache
  entries (one ending in `updated_at`, the other in `undefined`) with
  `staleTime: Infinity` → sidebar read pre-regeneration metadata and
  couldn't find new `aveiro` condado. Fix: pass cacheVersion to both
  calls inside the wrapper
- **f509db5** — seed parked: Voronoi output historically implausible;
  user flagged but deferred. 4 options (A–D) catalogued for revisit

## Test + verification state at end of session

- Frontend vitest: **101/104 green** (3 pre-existing SSE failures in
  `useResearchStream.test.ts` and `ResearchDialog.test.tsx` — not in
  02-05 scope)
- Frontend `tsc -b`: exit 0
- Grep invariants from 02-05 plan `<verification>`: all hold
- D-04 preservation (`lib/map_generator.py`): diff empty
- Memory updated: `feedback-tests-descriptive.md` saved after user asked
  for more descriptive tests

## Known remaining debt (not in scope, captured for later)

1. **Voronoi quality** — [seed-voronoi-quality.md](./seed-voronoi-quality.md);
   user feedback: Portuguese frontier territories look geometrically
   artificial. 4 options analyzed (A–D).
2. **Territory template cache** — [todo-territory-template-cache-stale.md](./todo-territory-template-cache-stale.md);
   must hard-refresh after backend JSON edits.
3. **InspectorSidebar duchy name display** — `InspectorSidebar.tsx:87`
   treats `manualResult.duchies[id]` as `[name, …]` but actual shape is
   `{kingdom_id, name}`. Badge "Ducado" shows raw ID (`D_POR`) instead of
   name ("Portugal"). Cosmetic, small fix.
4. **`conflent` condado lost in generation** — source JSON has 93 condados,
   generated geojson has 92. `conflent` (Pyrenees) silently dropped.
   Pre-existing pipeline issue, not a 02-05 regression.
5. **Territory-research pipeline truncation** — when user pastes LLM
   response covering only part of condados (e.g. 14/92), the rest fall
   back to palette colors. Currently no UI hint that the paste was
   partial. Could validate coverage before `set_cached`.

## Next logical step

- **Human UAT closure:** user should re-test the 9 pending UAT items (#1,
  #3, #4, #5, #6, #7, #8, #9, #11) with the now-shipped fixes; then
  `/gsd-verify-phase 02` or advance the phase via `/gsd-next`.
- **OR** jump to Phase 03 (LLM research integration, partially pulled
  forward already via quick tasks 260422-*).
