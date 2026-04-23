---
status: complete
phase: 03-llm-research-integration
source: [03-01-SUMMARY.md, 03-02-SUMMARY.md, 03-03-SUMMARY.md, 03-04-SUMMARY.md, quick tasks 260422-eue/f0s/f6f/fzh/h24/i0q/k6e/ktb/l7g]
started: 2026-04-23
updated: 2026-04-23
reverified_date: 2026-04-23
---

## Current Test

[testing complete — user confirmed all 12 tests pass in batch]

## Tests

### 1. Open ResearchDialog from ProjectDetail Pipeline tab
expected: User opens a generated project, switches to Pipeline tab (or wherever the research trigger lives), and a button opens the Radix Dialog ResearchDialog with provider selector, country/period inputs, and a "Run research" CTA.
result: pass
reverified: 2026-04-23 (user batch UAT)

### 2. ProviderSelector lists 4 providers + status badges
expected: ProviderSelector shows Claude, OpenAI, Gemini, Ollama (auto-discovered from /api/llm/providers). Each provider shows configured/healthy status badges driven by /api/llm/health.
result: pass
reverified: 2026-04-23

### 3. Configure API key auth for one provider
expected: Click "Setup auth" → AuthSetupSheet opens with the right form per provider (API key field, OAuth button, or CLI piggyback). Submitting an API key fires POST /api/auth/credentials/{provider} and the badge flips to "configured" without a page reload.
result: pass
reverified: 2026-04-23

### 4. Run research with SSE streaming
expected: Click "Run research" → POST /api/projects/{id}/research?provider=X starts; the dialog shows live streaming progress (token chunks or progress messages) via SSE.
result: pass
reverified: 2026-04-23

### 5. Result preview shows kingdoms→duchies→condados→baronies hierarchy
expected: After streaming completes, the dialog renders the parsed ResearchResult: kingdoms grouping duchies grouping condados, with baronies listed under condados.
result: pass
reverified: 2026-04-23

### 6. Apply result to canvas — condados colored by kingdom
expected: User confirms/applies the result; the CanvasViewer recolors condado polygons by their assigned kingdom hue (research overrides file colors per spec).
result: pass
reverified: 2026-04-23

### 7. InspectorSidebar shows kingdom/duchy badges after apply
expected: Selecting a condado after research-apply shows kingdom name + duchy name in the InspectorSidebar (badges or labeled fields).
result: pass
reverified: 2026-04-23

### 8. Cached result auto-loads on dialog reopen
expected: Closing the dialog and reopening it (or refreshing) → dialog auto-loads cached result via GET /api/projects/{id}/research/cached without re-running.
result: pass
reverified: 2026-04-23

### 9. Manual paste provider works (copy prompt → paste response)
expected: Selecting "Manual paste" provider exposes the generated prompt to copy; user pastes a response from any external chat into a textarea, submits, and the system parses + applies as if it came from a real provider.
result: pass
reverified: 2026-04-23 (covers quick task 260422-h24)

### 10. Manual file I/O (download prompt, upload response)
expected: "Download prompt" emits a `.txt`/`.md` file with the prompt; "Upload response" accepts a `.json` file with the model output and applies it.
result: pass
reverified: 2026-04-23 (covers quick task 260422-i0q)

### 11. Date+country changes in dialog persist to project
expected: Changing period_start, period_end, or country_qid in the ResearchDialog inputs fires PATCH /api/projects/{id} before the research call, so the project record is updated and subsequent runs use the new values.
result: pass
reverified: 2026-04-23 (covers quick task 260422-l7g)

### 12. Multi-country support (Q29,Q45) in research
expected: country_qid accepts comma-separated list (e.g., "Q29,Q45" for Spain+France); research runs with both countries' territory data joined.
result: pass
reverified: 2026-04-23 (covers quick task 260422-l7g)

## Summary

total: 12
passed: 12
issues: 0
pending: 0
skipped: 0

## Gaps

[none — all tests pass]

## New feature request — llama.cpp provider

User wants to use llama.cpp's `llama-server` as a local LLM backend (alternative to Ollama). See repo todos / future quick task for proposed integration paths.
