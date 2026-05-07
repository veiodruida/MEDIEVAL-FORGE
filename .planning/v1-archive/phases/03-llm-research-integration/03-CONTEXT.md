# Phase 3: LLM Research Integration - Context

**Gathered:** 2026-04-20
**Updated:** 2026-04-20 (scope expanded: multi-provider + browser auth)
**Status:** Ready for planning

<domain>
## Phase Boundary

User triggers historical research from inside a project and receives a structured kingdoms→duchies→condados→baronies hierarchy assigned to existing canvas condados. Supports **four LLM providers out-of-the-box** (Claude, OpenAI, Gemini, Ollama) via a **plugin-style adapter registry** so additional providers can be added by dropping in a new adapter class. Each provider uses its natural auth flow — API key, browser OAuth, or local CLI piggyback — with in-memory credential storage only.

**In scope:**
- Plugin-style LLM adapter layer with 4 initial providers (Claude, OpenAI, Gemini, Ollama)
- Auth abstraction: API key (all) + OAuth (Google for Gemini) + CLI piggyback (Anthropic via `claude-code` local auth) + env-var fallbacks
- Research API with SSE progress, Pydantic schema validation, 3-retry loop, per-project SQLite cache
- Research dialog UI: provider dropdown, auth status indicator, per-provider setup flow, country+period inputs, streaming progress view, result preview
- Territory assignment from LLM output → existing OSM condado IDs (explicit assignment by id)
- Machine-readable provider registry exposed via `GET /api/llm/providers` so the frontend auto-discovers what's available

**Out of scope:**
- Drag-and-drop re-assignment of condados on the canvas (Phase 4)
- Terrain rendering (Phase 5)
- Validation gate (Phase 6)
- Multi-turn agent-style research or refinement conversations
- Fine-tuning or custom model hosting
- Automatic provider fallback (if Claude fails, try OpenAI) — providers are explicit user choice
- Persisted credentials across server restarts (session memory only — constraint)
- Full OAuth app registration for Anthropic (Google OAuth only for v1; Anthropic OAuth deferred — see Risk section below)

</domain>

<decisions>
## Implementation Decisions

### Provider architecture (plugin-based, extensible)
- **D-01:** `services/llm/` becomes a package, not a single file. Contains `base.py` (Protocol + shared types), `registry.py` (provider registry), and one module per provider: `claude.py`, `openai.py`, `gemini.py`, `ollama.py`.
- **D-02:** Each provider implements the `LLMProvider` Protocol: `provider_id: str`, `display_name: str`, `auth_methods: list[AuthMethod]`, `async health_check(credentials) -> HealthStatus`, `async research(prompt, schema, queue) -> BaseModel`. Streaming is optional — providers that don't stream show a spinner.
- **D-03:** `AuthMethod` is a tagged union: `ApiKeyAuth`, `OAuthAuth(authorize_url, scopes)`, `CliAuth(cli_command, auth_file_path)`, `NoAuth` (Ollama). Each provider declares which methods it supports in priority order.
- **D-04:** Registry pattern: `PROVIDERS: dict[str, LLMProvider] = {...}` populated at import time. Adding a new provider = create file + add one line to registry.
- **D-05:** `GET /api/llm/providers` returns the registry as JSON for frontend discovery: `[{provider_id, display_name, auth_methods: [{type, ...meta}], configured: bool, healthy: bool}, ...]`. Frontend renders UI from this — no hardcoded provider lists.

### LLM → condado matching (unchanged)
- **D-06:** LLM receives the list of existing condados in its prompt — each with OSM id, canonical name, centroid (lon, lat) — and returns an **explicit assignment by condado id** in its JSON response. No fuzzy match on historical names.
- **D-07:** Prompt format: `"Assign the following modern OSM condados to medieval historical counties. Each entry: {id, name, lon, lat}. Your response must reference condados by their id."` Full list inlined.
- **D-08:** Manual drag-and-drop re-assignment is Phase 4.
- **D-09:** If LLM returns a condado id not in the provided list, it's treated as a validation error → retry.

### Auth strategy per provider
- **D-10:** **Anthropic (Claude)** — priority order:
  1. **CLI piggyback**: if `claude-code` is installed locally, read the auth token from its credential store (typical paths: `~/.claude/.credentials.json` or `%APPDATA%\Claude\credentials.json` — exact path TBD by research agent).
  2. Env var: `ANTHROPIC_API_KEY` at server start.
  3. Dialog paste (API key input, session memory).
- **D-11:** **Google (Gemini)** — priority order:
  1. Env var: `GOOGLE_API_KEY` or `GEMINI_API_KEY` at server start.
  2. **Browser OAuth**: Google OAuth "Installed App" flow (localhost redirect allowed). User clicks "Sign in with Google", redirected to Google, returns with access token. Token cached in-memory for the session (TTL ~60 min), refresh forces re-auth.
  3. Dialog paste (API key from Google AI Studio).
- **D-12:** **OpenAI** — API key only:
  1. Env var: `OPENAI_API_KEY` at server start.
  2. Dialog paste.
  (OpenAI does not offer OAuth for API access. No browser login option exposed.)
- **D-13:** **Ollama** — no auth; healthcheck via `GET localhost:11434/api/tags`.
- **D-14:** All credentials stored in-memory only (`app.state.credentials: dict[provider_id, Credential]`). Server restart requires re-entry. OAuth tokens are NOT written to disk.
- **D-15:** OAuth callback routes: `POST /api/auth/oauth/{provider}/start` returns authorize_url with state param; `GET /api/auth/oauth/{provider}/callback?code=...&state=...` exchanges code for token. State param validated for CSRF.
- **D-16:** UI shows per-provider auth status badge: `"✓ via CLI auth"` | `"✓ via OAuth (Google)"` | `"✓ via env var"` | `"✓ via session key"` | `"⚠ setup required"`.

### Ollama availability UX (unchanged)
- **D-17:** On dialog open, frontend calls `GET /api/llm/health` which returns health for all providers. Ollama shows as unhealthy if `localhost:11434` unreachable.
- **D-18:** If Ollama offline: radio option disabled with tooltip `"Inicia \`ollama serve\` e executa \`ollama pull qwen2.5\` para usar LLM local."`
- **D-19:** Suggested default Ollama model: `qwen2.5:7b` (good JSON mode), fallback `llama3.1:8b`.

### Research scope / granularity
- **D-20:** Single-shot: one LLM call returns the full hierarchy `{kingdoms, duchies, condados_assignment, baronies}` for the given country+period.
- **D-21:** Target scale: Iberia 868 AD reference ~5 kingdoms, ~20 duchies, ~91 condados, ~250 baronies — fits any modern frontier LLM in one response.
- **D-22:** Streaming: Claude and OpenAI stream (SSE token pass-through). Gemini's streaming via SDK is used if available. Ollama: `stream: false, format: "json"` (blocking spinner).

### Caching (unchanged)
- **D-23:** Cache key: `(country_qid, period_start, period_end, provider, model)`.
- **D-24:** Re-ingesting OSM does NOT invalidate cache.
- **D-25:** Cache storage: new `research_cache` table in SQLite with `(cache_key_hash TEXT PRIMARY KEY, payload JSON, created_at, provider, model)`.
- **D-26:** UI shows "cached" badge; button to force-refresh bypasses cache.

### Retry / validation loop (unchanged)
- **D-27:** Pydantic schema with `model_config = ConfigDict(extra='forbid')`.
- **D-28:** On validation failure, retry up to 3 times with the error appended: `"Your previous response failed validation with: {error}. Return corrected JSON only, no prose."`
- **D-29:** After 3 failures, surface the last raw response + last error. User can abort OR manually edit the JSON and submit for validation-only.

### Claude's Discretion
- Exact Pydantic schema field shapes (derive from `territory_data_v3.py`).
- Prompt engineering details (system message, few-shot examples, token budget per provider).
- SDK choices: official SDKs where available (`anthropic`, `openai`, `google-genai`, `ollama` python clients). Research agent should validate current versions.
- CLI piggyback auth-file path discovery for `claude-code` (research agent task).
- OAuth app registration specifics (Google Cloud Console setup) — documented for user but single OAuth client_id bundled with the app is acceptable given local-only usage.
- SSE message format (existing ingest+generate pattern).
- SQLite migration approach (inline `CREATE TABLE IF NOT EXISTS` or Alembic — match Phase 1 approach).
- Research dialog styling (Radix Dialog).

</decisions>

<risk_notes>
## Risks / Open Questions for Research Agent

1. **Anthropic OAuth**: Anthropic's OAuth is typically reserved for managed customers and requires app registration + verification. **Decision:** v1 supports Anthropic via API key + CLI piggyback only; full Anthropic browser OAuth is deferred unless the research agent finds an accessible public flow.

2. **`claude-code` credential store location**: Needs empirical verification across Windows / macOS / Linux. Research agent should document the paths and the file format.

3. **Google OAuth client_id bundling**: The app needs an OAuth client_id registered with Google. For a local tool, the "Desktop app" flow is documented and supports `http://localhost:PORT/callback`. Research agent should confirm current Google OAuth 2.0 best practice for installed apps (PKCE required since 2022).

4. **Provider streaming capability parity**: Not all providers expose identical streaming semantics. The `LLMProvider.research` method should accept a `stream_queue: asyncio.Queue | None` — providers without streaming simply don't emit to it.

5. **JSON mode equivalence**: Claude supports native JSON via tool use; OpenAI has `response_format={"type": "json_schema"}`; Gemini has `generation_config={"response_mime_type": "application/json"}`; Ollama has `format: "json"`. The adapter must normalize these so the retry loop sees the same abstraction.

</risk_notes>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 3 scope anchors
- `.planning/ROADMAP.md` §"Phase 3: LLM Research Integration" — goal, requirements, plan breakdown, success criteria (NOTE: ROADMAP.md plan list predates scope expansion; requirements list is authoritative)
- `.planning/REQUIREMENTS.md` §"RESEARCH — Historical Research via LLM" — RESEARCH-01..09 (09 total after expansion)

### Reference output format (target hierarchy shape)
- `inicio/licoes/territory_data_v3.py` — 91 condados / 250 baronies Iberia 868 AD reference structure; the Pydantic schema should match this shape

### Tech stack constraints
- `CLAUDE.md` §"Tech Stack" — Anthropic SDK 0.94.1 (AsyncAnthropic), Ollama REST, FastAPI async, SQLite + aiosqlite. OpenAI + Gemini SDKs are NEW additions; research agent validates current stable versions (OpenAI Python SDK 1.x; Google `google-genai` package, not the deprecated `google-generativeai`).
- `CLAUDE.md` §"Potential Issues #2 zundo" — use `temporal.pause()/resume()` around LLM polling.

### Existing patterns to reuse
- `backend/medieval_forge/services/ingest_runner.py` — SSE queue+producer pattern
- `backend/medieval_forge/api/ingest.py` — SSE endpoint wiring
- `backend/medieval_forge/api/generate.py` — background task + status pattern
- `frontend/src/hooks/useIngestStream.ts` — client-side SSE consumption
- `backend/medieval_forge/services/countries.py` — `resolve_to_qid` / `qid_to_iso`

### External docs research agent should read
- Anthropic Python SDK — https://github.com/anthropics/anthropic-sdk-python (streaming, tool use)
- OpenAI Python SDK — https://github.com/openai/openai-python (structured outputs, streaming)
- Google Gen AI SDK (`google-genai`) — https://github.com/googleapis/python-genai (response_mime_type for JSON)
- Ollama Python client — https://github.com/ollama/ollama-python
- OAuth 2.0 for Installed Applications (Google) — https://developers.google.com/identity/protocols/oauth2/native-app
- Claude Code credential storage (if documented)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- SSE plumbing: `ingest_runner.py` + `api/ingest.py` — mirror for research streaming.
- Country resolution: `services/countries.py::resolve_to_qid`.
- SQLite async: `database.py` — `AsyncSessionLocal`, `get_db`.
- Radix Dialog already used in project forms.

### Established Patterns
- Async endpoints with `StreamingResponse` + SSE string queue.
- Error surfacing: stream `data: ERROR: {msg}\n\n` then close with `None`.
- Frontend state: TanStack Query (server) + Zustand with zundo temporal (UI). **Wrap LLM polling in `temporal.pause()/resume()`**.

### Integration Points
- New package: `backend/medieval_forge/services/llm/` (base.py, registry.py, claude.py, openai.py, gemini.py, ollama.py, auth.py, schemas.py).
- New file: `backend/medieval_forge/api/research.py` (POST trigger + SSE stream + GET cached + GET providers).
- New file: `backend/medieval_forge/api/auth.py` (OAuth start + callback endpoints).
- New migration: `research_cache` table.
- New hook: `frontend/src/hooks/useResearchStream.ts`.
- New components: `frontend/src/components/research/ResearchDialog.tsx`, `ProviderSelector.tsx`, `AuthSetupSheet.tsx`.
- ProjectDetail page gets "Research" button opening the dialog.

</code_context>

<specifics>
## Specific Ideas

- Reference hierarchy shape from `inicio/licoes/territory_data_v3.py`.
- Bundle a single OAuth `client_id` for Google with the app (desktop-app flow, localhost redirect) — user does NOT need to register their own OAuth app.
- `claude-code` CLI piggyback: if `claude-code --print-auth-status` or similar exists, prefer that over reading files; fall back to file-read if documented path exists.
- Frontend provider selector UI: dropdown + per-provider inline "Setup" link. Setup opens a side-sheet with the auth methods available for that provider (OAuth button, API-key input, CLI status check).

</specifics>

<deferred>
## Deferred Ideas

- Anthropic OAuth (needs app registration infrastructure not appropriate for a single-user local tool).
- Automatic provider fallback (explicit user choice only for v1).
- Token usage counter UI per project.
- Persisted credentials (explicitly prohibited by constraint — session memory only).
- Multi-turn agent refinement.
- Drag-and-drop re-assignment → Phase 4.
- Additional providers (Mistral, Groq, DeepSeek, Together) — supported by plugin architecture but not shipped in v1; documented as "add your own adapter" extension path.

</deferred>

---

*Phase: 03-llm-research-integration*
*Context gathered: 2026-04-20*
*Context expanded: 2026-04-20 — multi-provider (OpenAI, Gemini) + browser auth mixture*
