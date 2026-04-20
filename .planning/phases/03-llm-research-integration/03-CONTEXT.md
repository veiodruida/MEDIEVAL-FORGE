# Phase 3: LLM Research Integration - Context

**Gathered:** 2026-04-20
**Status:** Ready for planning

<domain>
## Phase Boundary

User triggers historical research from inside a project and receives a structured kingdoms→duchies→condados→baronies hierarchy assigned to existing canvas condados. Supports Claude API and Ollama, with SSE progress, schema-validated JSON, 3-retry on invalid output, and per-project caching.

**In scope:** LLM adapter service (Claude async streaming + Ollama REST), research API with SSE, Pydantic schema validation, retry loop, SQLite cache, research trigger dialog UI, progress display, territory assignment from LLM output → existing OSM condado IDs.

**Out of scope:** Editing the LLM output on the canvas (that's Phase 4 editing), terrain rendering (Phase 5), validation gate (Phase 6), agent-style multi-turn reasoning, fine-tuning models.

</domain>

<decisions>
## Implementation Decisions

### LLM → condado matching (the hard part)
- **D-01:** LLM receives the list of existing condados in its prompt — each with OSM id, canonical name, centroid (lon, lat) — and returns an **explicit assignment by condado id** in its JSON response. No fuzzy match on historical names.
- **D-02:** Prompt format: `"Assign the following modern OSM condados to medieval historical counties. Each entry: {id, name, lon, lat}. Your response must reference condados by their id."` Full list inlined.
- **D-03:** Manual drag-and-drop re-assignment is available as a correction UI in Phase 4 (editing phase). Phase 3 produces the first-pass automatic assignment only.
- **D-04:** If LLM returns a condado id not in the provided list, it's treated as a validation error → retry.

### API key UX
- **D-05:** On server start, read `ANTHROPIC_API_KEY` env var if present — this becomes the default key for all projects in the session.
- **D-06:** If no env var, the research dialog shows a password-type input field. Key is stored in server memory only (module-level variable or FastAPI `app.state`), never written to disk or SQLite.
- **D-07:** Key persists across research calls within a single server process. Server restart requires re-entry.
- **D-08:** UI shows "using env var" vs "session key" badge so user knows the source.

### Ollama availability UX
- **D-09:** When the research dialog opens, frontend does `GET /api/llm/health?provider=ollama` which the backend proxies to `http://localhost:11434/api/tags`.
- **D-10:** If Ollama offline: the Ollama radio option is disabled with a tooltip `"Inicia \`ollama serve\` e executa \`ollama pull qwen2.5\` para usar LLM local."`
- **D-11:** If Ollama online but no model available: show list of installed models; if empty, same tooltip as offline.
- **D-12:** Suggested default model: `qwen2.5:7b` (good JSON mode) or `llama3.1:8b` as fallback. User can override.

### Research scope / granularity
- **D-13:** Single-shot: one LLM call returns the full hierarchy `{kingdoms, duchies, condados_assignment, baronies}` for the given country+period.
- **D-14:** Target scale: Iberia 868 AD reference is ~5 kingdoms, ~20 duchies, ~91 condados, ~250 baronies — fits comfortably in one Claude response (~8-15k tokens).
- **D-15:** Ollama: `stream: false`, `format: "json"`. Claude: streaming enabled for progress tokens in SSE.

### Caching
- **D-16:** Cache key: `(country_qid, period_start, period_end, provider, model)` — e.g. `("Q29", 711, 1492, "claude", "claude-sonnet-4-6")`.
- **D-17:** Re-ingesting OSM does NOT invalidate cache — the LLM output references condado ids that are stable as long as ingest covers the same region. If condado set changes drastically (different country), cache key changes anyway.
- **D-18:** Cache storage: new `research_cache` table in SQLite with `(cache_key_hash TEXT PRIMARY KEY, payload JSON, created_at)`.
- **D-19:** UI shows "cached" badge next to results that came from cache; button to force-refresh (bypasses cache).

### Retry / validation loop
- **D-20:** Pydantic schema with `model_config = ConfigDict(extra='forbid')` so unexpected fields fail validation.
- **D-21:** On validation failure, retry up to 3 times. Each retry prompt appends: `"Your previous response failed validation with: {pydantic_error_json}. Return corrected JSON only, no prose."`
- **D-22:** After 3 failures, surface the last raw response + last error to the user in a copy-pasteable block. User can: (a) abort, (b) manually edit the JSON into a text field and submit for validation-only (skip LLM).

### Claude's Discretion
- Concrete Pydantic schema field shapes (`Kingdom`, `Duchy`, `Condado`, `Barony` — derive from `territory_data_v3.py` structure).
- Prompt engineering details (system message, few-shot examples, token budget).
- SSE message format (existing pattern from ingest + generate flows is fine).
- SQLite migration approach (use Alembic per Phase 1 pattern, or inline `CREATE TABLE IF NOT EXISTS`).
- UI styling of the research dialog (Radix Dialog primitive per existing conventions).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 3 scope anchors
- `.planning/ROADMAP.md` §"Phase 3: LLM Research Integration" — goal, requirements, plan breakdown, success criteria
- `.planning/REQUIREMENTS.md` §"RESEARCH — Historical Research via LLM" — RESEARCH-01..05

### Reference output format (target hierarchy shape)
- `inicio/licoes/territory_data_v3.py` — 91 condados / 250 baronies Iberia 868 AD reference structure; the Pydantic schema should match this shape (kingdom/duchy/condado/barony tuples with ids + names + centroids)

### Tech stack constraints
- `CLAUDE.md` §"Tech Stack" — Anthropic SDK 0.94.1 (AsyncAnthropic), Ollama REST, FastAPI async, SQLite + aiosqlite
- `CLAUDE.md` §"Potential Issues #2 zundo" — use `temporal.pause()/resume()` around LLM polling to prevent creating undo steps (RESEARCH plan 3.2 note)

### Existing patterns to reuse
- `backend/medieval_forge/services/ingest_runner.py` — SSE queue+producer pattern for streaming progress to frontend
- `backend/medieval_forge/api/ingest.py` — SSE endpoint wiring via `StreamingResponse` + `asyncio.Queue[str|None]`
- `backend/medieval_forge/api/generate.py` — long-running background task + polling status pattern
- `frontend/src/hooks/useIngestStream.ts` — client-side SSE consumption pattern
- `backend/medieval_forge/services/countries.py` — `resolve_to_qid` / `qid_to_iso` for country input normalization

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **SSE plumbing**: `ingest_runner.py` + `api/ingest.py` — Mirror the pattern for research streaming (queue → StreamingResponse).
- **Country resolution**: `services/countries.py::resolve_to_qid` — research dialog country field reuses this for QID normalization.
- **SQLite async**: `backend/medieval_forge/database.py` — `AsyncSessionLocal`, `get_db` dependency already in place; `research_cache` table plugs into existing Base.
- **TanStack Query cache**: Frontend already invalidates queries on status change — same approach for research result cache.
- **Radix Dialog**: already used in project forms; research dialog follows same modal pattern.

### Established Patterns
- Async endpoints with `StreamingResponse` + SSE string queue for progress updates.
- Background tasks via `asyncio.to_thread` for CPU-bound; direct async for I/O like LLM calls.
- Error surfacing: stream final message `data: ERROR: {msg}\n\n` then close queue with `None`.
- Frontend state: TanStack Query for server state, Zustand (with zundo temporal) for UI state. **Wrap LLM polling in `temporal.pause()/resume()`** (per roadmap plan 3.2 note and CLAUDE.md zundo gotcha).

### Integration Points
- New file: `backend/medieval_forge/services/llm.py` (adapter interface + Claude/Ollama impls + validation+retry).
- New file: `backend/medieval_forge/api/research.py` (POST trigger + SSE stream + GET cached result).
- New migration: `research_cache` table (can be inline `CREATE TABLE IF NOT EXISTS` at startup, matching how project status column was handled, OR Alembic if that was adopted in Phase 1).
- New hook: `frontend/src/hooks/useResearchStream.ts` — clone of `useIngestStream` with research-specific messages.
- New component: `frontend/src/components/research/ResearchDialog.tsx` — Radix Dialog, provider radio, country+period inputs, progress view, result preview.
- ProjectDetail page gets a "Research" button that opens the dialog; saves result via `PATCH /api/projects/{id}` into territory_data slot (or a new field).

</code_context>

<specifics>
## Specific Ideas

- Reference hierarchy shape from `inicio/licoes/territory_data_v3.py` — the LLM output should match this structure so it flows directly into the existing generation pipeline without transformation.
- Use Claude streaming (`AsyncAnthropic` with `stream=True`) so the UI shows tokens as they arrive — mirrors the ingest SSE UX users already know.
- For Ollama, `format: "json"` is critical (forces JSON mode in recent versions) — without it, retry rate spikes.
- Suggested default Ollama model: `qwen2.5:7b` (benchmarked good at structured JSON on 16GB VRAM); `llama3.1:8b` as documented alternative.

</specifics>

<deferred>
## Deferred Ideas

- Drag-and-drop re-assignment of condados to duchies/kingdoms in the inspector — belongs in Phase 4 (Canvas Editing — Basic).
- Multi-turn agent-style research ("refine this condado further") — out of scope for this phase; current scope is single-shot full hierarchy.
- Budget / token counter UI per project — nice to have, not required by RESEARCH-01..05.
- Exporting the research prompt as a text file for audit — out of scope.
- Automatic provider fallback (Claude fails → try Ollama) — explicit user choice only for this phase; auto-fallback can be revisited later.

</deferred>

---

*Phase: 03-llm-research-integration*
*Context gathered: 2026-04-20*
