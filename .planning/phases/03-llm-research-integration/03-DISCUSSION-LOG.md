# Phase 3: LLM Research Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-20
**Phase:** 03-llm-research-integration
**Areas discussed:** LLM→condado matching, API key UX, Ollama availability, Research scope

---

## A. LLM → condado matching

| Option | Description | Selected |
|--------|-------------|----------|
| Fuzzy-match auto | LLM names matched to closest existing condado | |
| Explicit assignment | LLM receives condado list, returns ids directly | ✓ |
| Manual drag-and-drop only | User assigns after LLM hierarchy generated | (as Phase 4 correction) |

**User's choice:** Option 2 primary + Option 3 as Phase 4 correction UI
**Notes:** Fuzzy-match rejected because historical names ("Condado de Portucale") diverge from OSM ids ("braga"). Explicit assignment gives the LLM all context it needs (ids, names, centroids).

---

## B. API key UX

| Option | Description | Selected |
|--------|-------------|----------|
| Dialog per session | User pastes key each time, lost on refresh | |
| Env var only | `ANTHROPIC_API_KEY` read at server start | |
| Hybrid | Env var at startup + dialog fallback, server-memory persistence | ✓ |

**User's choice:** Option 3
**Notes:** Constraint "keys session-memory only" satisfied. Env var for dev ergonomics, UI input for end user. Source shown as badge in dialog.

---

## C. Ollama availability UX

| Option | Description | Selected |
|--------|-------------|----------|
| Dialog-open healthcheck | Disable Ollama option with tooltip if unreachable | |
| Error on attempt | Let user try, show error if offline | |
| Healthcheck + model suggestion | Detect + suggest `qwen2.5` / `llama3.1` with setup instructions | ✓ |

**User's choice:** Option 3
**Notes:** Most helpful for non-expert users. Healthcheck proxies `GET localhost:11434/api/tags`; list installed models; fall back to tooltip with `ollama serve` + `ollama pull` hints.

---

## D. Research scope / granularity

| Option | Description | Selected |
|--------|-------------|----------|
| Single-shot | One call returns full hierarchy | ✓ |
| Progressive | Kingdoms first, drill-down on demand | |
| Hybrid | Kingdoms+duchies eager, condados/baronies lazy | |

**User's choice:** Option 1
**Notes:** Iberia 868 AD reference (~5 kingdoms, ~20 duchies, ~91 condados, ~250 baronies) fits one Claude response (~8-15k tokens). Progressive adds UX complexity without clear benefit.

---

## E. Scope expansion — multi-provider + browser auth (added 2026-04-20)

| Decision | Choice |
|----------|--------|
| Add OpenAI provider | ✓ |
| Add Gemini provider | ✓ |
| Additional future providers | Plugin architecture, not shipped in v1 |
| Auth approach | Mixture: OAuth where available + CLI piggyback + API key fallback |
| Path for change | Expand Phase 3 now (not Phase 3.5, not backlog) |

**User's choice:** Expand now; multi-provider with extensibility.
**Notes:** Provider adapter becomes genuinely pluggable via registry pattern. OpenAI: API key only (no OAuth available). Gemini: API key + Google OAuth "installed app" flow. Anthropic: API key + `claude-code` CLI piggyback for users who have that installed. Full Anthropic OAuth deferred due to app-registration overhead.

**Added requirements:** RESEARCH-06 (OpenAI), RESEARCH-07 (Gemini), RESEARCH-08 (OAuth + CLI piggyback), RESEARCH-09 (plugin architecture).

**Scope growth:** ~3 plans → ~4-5 plans (split adapter layer + auth layer + research API + UI).

---

## Implicit decisions confirmed

- **Cache key:** `(country_qid, period_start, period_end, provider, model)` — re-ingest does NOT invalidate.
- **Retry strategy:** Append Pydantic error JSON to next retry prompt ("fix it, return JSON only").
- **After 3 retries fail:** Show last raw response + error; allow manual JSON edit submission.
- **SSE progress:** Claude streaming tokens piped to SSE; Ollama blocking with spinner.

## Claude's Discretion

- Concrete Pydantic schema field shapes (derive from `territory_data_v3.py`).
- Prompt engineering details (system message, few-shot).
- SSE message format (reuse existing ingest+generate pattern).
- SQLite migration approach (inline CREATE TABLE IF NOT EXISTS vs Alembic).
- Research dialog styling (Radix Dialog).

## Deferred Ideas

- Drag-and-drop re-assignment → Phase 4.
- Multi-turn agent refinement → out of scope.
- Token counter UI → not required.
- Prompt export → out of scope.
- Auto provider fallback → explicit user choice only for this phase.
