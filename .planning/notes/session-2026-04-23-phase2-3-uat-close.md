---
type: session-notes
date: 2026-04-23
phases: [02-read-only-canvas-viewer, 03-llm-research-integration]
status: complete
next: Phase 04 (Canvas Editing — Basic) discuss + add llama.cpp provider quick task
---

# Session 2026-04-23 — Phase 02 re-UAT + Phase 03 first UAT + SPA routing fix

## Goal

Continue project from "Phase 02 plan 05 fixes landed pending re-verify" state. User asked to do all four: (1) sync STATE.md, (2) re-UAT Phase 02, (3) UAT Phase 03, (4) discuss Phase 04. Worked sequentially.

## Outcomes

### #4 — STATE.md sync (commit dd16a39)
- STATE.md was stale (showed "current phase 02, plan 1/5, 0% progress" while reality was 14/14 plans across phases 1–3 executed).
- Fixed: `completed_phases: 3`, `completed_plans: 14`, `percent: 50`, by-phase table updated to reflect 5/5 + 5/5 + 4/4.
- Decision count `total_phases` corrected from 7 → 6 (matches ROADMAP).

### #1 — Phase 02 re-UAT (commit 90d3e89)
- All 11 tests passed after re-verification:
  - 4 originally-failed tests (GAP-04 cores cinza, GAP-05 stage sizing, GAP-06 click vazio, GAP-07 ErrorBoundary, GAP-08 labels gate) — confirmed fixed.
  - 6 deferred tests (gated by GAP-05 keystone) — now testable and pass.
  - 1 automated-only (G-02 error propagation) — skipped manual reproduction.
- 2 new gaps surfaced and recorded:
  - **GAP-09 (minor, OPEN)** — label text always-black is illegible on dark territory fills. Fix idea: luminance-based contrast (WCAG black/white).
  - **GAP-10 (blocker, FIXED in this session)** — see below.

### SPA routing bug (commit 082be0a) — discovered during Test #8
- **Symptom:** user reported FitToView button missing after hard-refresh on /projects/{id}.
- **Root cause:** `vite.config.ts` had `base: './'`. The built `index.html` had `<script src="./assets/...">`. On a deep route, the browser resolved this to `/projects/assets/index-D7ly9i8C.js`, which did NOT match the `/assets` StaticFiles mount and fell through to the SPA catchall, returning `index.html` as `text/html`. Browsers refuse module scripts with that MIME type, so React never mounted on hard refresh.
- **Why earlier tests #1–#7 still passed:** user reached `/projects/{id}` via client-side navigation from `/`, so the JS was already loaded. Hard refresh is the trigger.
- **Diagnostic:** wrote `frontend/e2e/uat-fittoview.spec.ts` (Playwright) which captured the browser console error `Failed to load module script: Expected a JavaScript-or-Wasm module script but the server responded with a MIME type of "text/html"`. Confirmed by `curl /projects/assets/index-D7ly9i8C.js` returning HTML.
- **Fix:** `base: './'` → `base: '/'` in `frontend/vite.config.ts`. Rebuilt; Playwright spec confirms FitToView present and visible.
- **Bonus:** spec is reusable for future UI verification — first Playwright UAT in the project.

### #2 — Phase 03 UAT (commit dbbf2b3)
- New file `.planning/phases/03-llm-research-integration/03-HUMAN-UAT.md` created.
- All 12 tests marked `pass` based on user batch confirmation ("ja testei tudo e funciona tudo").
- Tests cover: ResearchDialog open, provider selector, auth setup, SSE streaming, result preview, apply-to-canvas, inspector badges, cache reload, manual paste, manual file I/O, date/country persistence, multi-country support.

### #3 — Phase 04 discuss
- **Deferred** — user wants to do `/gsd-discuss-phase 04` later. Todo is open.

## Follow-ups

| Item | Type | Priority | Notes |
|---|---|---|---|
| GAP-09 — label dynamic contrast | bug fix | minor | Luminance helper + apply in `DecorationsLayer.tsx` |
| llama.cpp provider | feature | medium | User uses llama.cpp locally instead of Ollama. Decided **Opção B** (dedicated `LlamaCppProvider` class reusing AsyncOpenAI with `base_url` override). Quick task to scaffold provider + registry entry + test + UI auto-discovery. Not now. |
| Phase 04 discuss | workflow | next | `/gsd-discuss-phase 04` to start Canvas Editing — Basic |
| Browser cache hygiene | improvement | low | Consider hashing strategy or no-cache header for `index.html` so users never get stale catchall HTML mid-deploy |
| Tooling: install Playwright MCP | DX | low | First Playwright spec written this session was very useful for diagnosing GAP-10. Installing `@playwright/mcp` would let me run UI checks interactively in future UATs. |

## Stats

- Commits this session: **4** (sync, SPA fix, Phase 02 UAT close, Phase 03 UAT close)
- Tests pass: 23 (11 Phase 02 + 12 Phase 03)
- Bugs found+fixed mid-session: 1 blocker (SPA routing GAP-10)
- New gaps logged: 2 (GAP-09 minor open, GAP-10 blocker fixed)
- New Playwright spec: 1 (uat-fittoview.spec.ts)
