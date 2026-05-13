# Phase 07: LLM research as opt-in metadata layer - Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Optional LLM-driven research that populates `name`, `kingdom_owner`,
and `historical_notes` on geometrically-fixed territories. Never
mandatory: the 12-file Unity pipeline runs end-to-end with zero LLM
calls (`Condado_001..N` placeholders survive untouched if no research
ran). When research runs, the result is merged into
`territory_metadata.json` at export time, non-destructively, so
re-running without research never overwrites geometric output.

Deliverables:

- Backend: new `services/llm/` package with `base.py` (Protocol),
  `registry.py` (plugin registry), `claude.py`, `ollama.py`, plus
  literal copies of `prompt.py`, `schemas.py`, `retry.py`, `parse.py`
  from commit `87f8aab` (only imports adjusted).
- Backend: new `services/research/` subpackage with `runner.py`
  (SSE orchestration), `cache.py` (SQLite-backed), `overlay.py`
  (writes `research_overlay.json` to `project_dir/`).
- Backend: new `services/credential_store.py` with SQLite-backed
  `llm_credentials` table; resolves Claude credentials in order
  CLI piggyback → DB → env → dialog paste.
- Backend: new `api/v3/research.py` (`POST /start`,
  `GET /stream` SSE, `GET /providers`, `GET /health`,
  `GET /overlay`).
- Backend: new `api/v3/credentials.py` (`GET /credentials`,
  `POST /credentials/{provider}`, `DELETE /credentials/{provider}`).
- Backend: refactor `services/export/zip.py` (Phase 06)
  `build_unity_zip` to read `research_overlay.json` from
  `project_dir/` (if present) and merge `name`, `kingdom_owner`,
  `historical_notes` into `territory_metadata.json` before assembling
  the zip. Merge is non-destructive: pipeline output stays raw on disk.
- Backend: new endpoint to serve merged metadata to the frontend
  (e.g., `GET /api/v3/projects/{id}/artifacts/territory_metadata.json`
  serves merged-on-the-fly when overlay exists; raw otherwise).
- Backend: DB migration adds `llm_credentials` + `research_cache`
  tables.
- Frontend: new `components/research/` (`ResearchDialog.tsx` Radix
  Dialog modal, `ProviderSelector.tsx`, `ResearchProgress.tsx`).
- Frontend: extend `InspectorSidebar.tsx` placeholder/project-summary
  mode with a "Pesquisar metadados históricos" button + a
  "Pesquisa aplicada" badge once overlay exists.
- Frontend: new `hooks/useResearchStream.ts` (SSE consumer mirroring
  the existing run-stream pattern).
- Frontend (Phase 06 absorption): swap the Export button to call
  `/api/v3/projects/{id}/export`; render the 5-code structured 422
  envelope (`COLOR_COLLISION`, `OCEAN_LEAK`, `MISSING_ORIGINAL_IDX`,
  `TERRITORY_TOO_SMALL`, `PIXEL_CENTER_OUT_OF_RANGE`) in a modal/toast
  with per-code i18n.
- Tests: three-layer pyramid per CLAUDE.md conventions:
  - `tests/unit/test_overlay_merge.py` — merge function with explicit
    numeric fixtures.
  - `tests/unit/test_llm_*.py` — schema validation, retry loop, parse
    leniency (subset of v1 tests adapted to the v3 namespace).
  - `tests/unit/test_credential_store.py` — DB persistence + auth chain
    resolution.
  - `tests/parity/test_iberia_868_yaml.py` — extends with assertion
    that pipeline still produces raw `Condado_001..N` names when no
    research runs (zero LLM in geometric path).
  - `tests/e2e/test_research_overlay_iberia.py` — Iberia run → fixture
    overlay → export → assert merged names in zip.
  - `tests/e2e/test_export_button_v3.py` — Playwright UAT for
    Phase 06 button swap + 422 envelope rendering.

Out of scope for Phase 07:

- OpenAI + Gemini providers (deferred to v3.1 — plugin registry slot
  ready, adapters not shipped).
- Anthropic OAuth (deferred indefinitely; CLI piggyback covers
  zero-setup, API key covers the rest).
- Drag-and-drop re-assignment of condados (deferred — separate phase).
- Automatic provider fallback (explicit user choice only).
- Multi-turn refinement / agent-style research conversation.
- Token usage UI per project.
- Manual editing of overlay JSON via UI (overlay is read-only output
  from research run; force-refresh button is the regen path).
- Region-key promotion of the overlay to a per-region YAML default
  (overlay is per-project, never global).
- Re-ingestion does NOT invalidate cache (D-24 v1 carried).

</domain>

<decisions>
## Implementation Decisions

### SC #3 interpretation + code reuse

- **D-01 (sidecar-first rebuild, not literal restore):** ROADMAP SC #3
  says LLM modules "are reused (moved into `v3/` namespace)" but
  Phase 03 deleted them in commit `87f8aab` and PROJECT.md D-V3-04
  prohibits namespace transitional shims. Reading: the *design* is
  reused (architecture, prompts, schemas, retry semantics); the *code*
  is built fresh under v3 patterns. v1-archive
  `03-CONTEXT.md`/`03-RESEARCH.md` are templates; the deleted files
  are NOT git-restored wholesale.

- **D-02 (copy 4 stateless artifacts literally from `87f8aab`):**
  These four files are pure / stateless (no `app.state.credentials`,
  no `LLMCredential` model coupling, no OAuth state) and represent
  weeks of bug-fix iteration that we don't want to repeat:
  - `services/llm/prompt.py` (417 LOC) — `build_map_research_prompt`,
    coverage rules, negative-example block, JSON-mode framing.
  - `services/llm/schemas.py` (255 LOC) — `ResearchResult` /
    `MapResearchResult` Pydantic models, `validate_barony_assignments`
    cross-ref check.
  - `services/llm/retry.py` (65 LOC) — 3-retry loop with error-in-prompt
    feedback ("Your previous response failed validation with: {error}").
  - `services/llm/parse.py` (50 LOC) — lenient JSON parser (strip extra
    top-level keys; quick fix 03-04).

  Planner runs `git show 87f8aab:backend/medieval_forge/services/llm/<file>`,
  pipes through `git apply --3way` or rewrites import lines, and commits
  with attribution comment at file head: `# Literal port from commit 87f8aab;
  see D-02 in 07-CONTEXT.md`.

  All other v1 LLM code (provider adapters, runner, cache, credential_store,
  api/llm.py, api/auth.py, models.LLMCredential) is REWRITTEN from scratch
  under v3 patterns. No git restore for those.

### Overlay merge point

- **D-03 (research_overlay.json is a project sidecar; merged into
  territory_metadata.json pre-zip):** Research run writes
  `project_dir/research_overlay.json` keyed by condado id with
  `{name, kingdom_owner, historical_notes}`. Pipeline geometric output
  (`generated/territory_metadata.json`) stays untouched and keeps
  `Condado_001..N` placeholders for autogen regions / curated names for
  Iberia. `services/export/zip.py:build_unity_zip` reads the overlay
  if it exists and applies the merge on the in-memory dict before
  serializing into the zip's `territory_metadata.json`. Unity loader
  never sees a 13th file; `EXPORT_FILE_CONTRACT` stays 12.

- **D-04 (merge happens at export time; frontend uses a merged-serving
  endpoint):** Pipeline never rewrites its own output. Two consumers
  see the merge:
  1. **Export zip:** `build_unity_zip` merges in-memory just before
     writing the metadata file into the zip stream. Raw output on disk
     stays raw; re-running the pipeline without overlay produces
     byte-identical raw output (deterministic invariant preserved).
  2. **Frontend canvas:** the artifact endpoint
     (`GET /api/v3/projects/{id}/artifacts/territory_metadata.json`)
     applies the same merge function on-the-fly when overlay exists.
     `useCanvasArtifacts` already fetches this URL — no new hook,
     `InspectorSidebar` reads `name` and sees the historical name.
     A separate `GET /api/v3/projects/{id}/research/overlay` endpoint
     exposes the raw overlay JSON for diagnostic/debug UI.

  Merge function lives in `services/research/overlay.py:merge_overlay(metadata: dict, overlay: dict) -> dict`
  — pure, exhaustively unit-tested, called from both the export zip
  and the artifact endpoint.

### Provider scope + plugin registry

- **D-05 (MVP day-1 providers: Claude + Ollama):** Two adapters cover
  the extremes — Claude is frontier quality with CLI-piggyback
  zero-setup; Ollama is zero-cost / zero-auth local. Plugin registry
  (`services/llm/registry.py`) is built to support N adapters, but
  Phase 07 ships exactly 2. OpenAI + Gemini stay slot-ready (the
  `GET /api/v3/research/providers` endpoint enumerates only registered
  adapters; adding an OpenAI adapter later = one file + one registry
  line, no other code touched). Deferred to v3.1 backlog.

- **D-13 (Ollama defaults: `qwen2.5:7b` primary, `llama3.1:8b`
  fallback; `format: "json"` blocking mode):** v1 defaults (D-19,
  D-22). Ollama health-check is `GET localhost:11434/api/tags`; UI
  shows the adapter as disabled with a tooltip if unreachable.

### Auth + credential persistence

- **D-06 (DB SQLite `llm_credentials` table; keep v1's
  persistence reversal):** v1 originally set credentials to
  session-memory only, then reverted to DB after user request
  (session-2026-04-21-phase3-execute.md line 66; rationale: "local
  single-user tool, mesmo modelo do gh/git"). Phase 07 inherits the
  reversal. DB file: `~/.medieval-forge/medieval_forge.db` (existing
  project DB). New table `llm_credentials` with columns:
  `(provider_id TEXT PRIMARY KEY, credential_type TEXT, payload JSON,
  created_at, updated_at)`. Payload encoding TBD — see Claude's
  Discretion #1 below.

- **D-07 (Claude auth chain: CLI piggyback → DB → env → dialog
  paste):** Resolution order at request time:
  1. **CLI piggyback** — check for `claude-code` credential file
     (cross-platform path discovery is Claude's Discretion #2).
     If a fresh non-expired token is present, use it. Zero setup
     for users who already use Claude Code.
  2. **DB** — `SELECT payload FROM llm_credentials WHERE provider_id='claude'`.
  3. **Env** — `ANTHROPIC_API_KEY`.
  4. **Dialog paste** — UI prompts; selection persists to DB
     (matches D-06).

  Ollama needs no credentials (D-05); auth chain is Claude-only.

### UI / research dialog

- **D-08 (trigger lives in `InspectorSidebar` placeholder mode):**
  When `selectedIds.length === 0`, `InspectorSidebar` already renders
  the project-summary mode (D-16 from Phase 03). Phase 07 adds a
  "Pesquisar metadados históricos" button to that summary panel.
  When a territory IS selected, `InspectorSidebar` shows the
  (potentially merged) historical name; if the overlay applies to
  that condado, a small badge reads "Pesquisa aplicada" + a link to
  reopen the dialog for force-refresh.

- **D-09 (Radix Dialog modal + SSE stream rendered inside):**
  Trigger opens a Radix Dialog (`<Dialog.Root>` from
  `@radix-ui/themes`). Form fields:
  - **País**: auto-filled from project's `region_key` (read-only —
    pipeline determines country).
  - **Período**: free text (default seeded from region YAML
    `display_name`, e.g., "Iberia 868 AD").
  - **Provider**: dropdown populated from
    `GET /api/v3/research/providers`. Disabled options for unhealthy
    providers with tooltip explaining why.
  - **Model**: free text, provider-conditional placeholder
    (Claude → `claude-sonnet-4-6`; Ollama → `qwen2.5:7b`).
  - **Force refresh checkbox** — bypasses cache (D-11).

  On submit, the dialog POSTs to `/api/v3/research/start` and opens
  an SSE connection to `/api/v3/research/stream/{run_id}`. Progress
  renders inside the modal as a per-stage list
  (`kingdoms → duchies → condados → baronies`) with elapsed time per
  stage. Cancel button aborts the stream + tells the server to stop.
  On success, modal closes, `useCanvasArtifacts` invalidates,
  inspector re-renders with historical names. On failure, modal stays
  open with the error + last raw response visible for debug.

### Phase 06 UI absorption

- **D-10 (Phase 07 absorbs the deferred Phase 06 frontend swap):**
  Phase 06 D-19 deferred (i) swapping the Export button from the
  deleted v1 endpoint to `/api/v3/projects/{id}/export`, and (ii)
  rendering the structured 422 envelope (D-08 of Phase 06 CONTEXT)
  with 5 stable error codes. Phase 06.1 does NOT exist in the roadmap
  (verified via `grep -n "06.1" .planning/ROADMAP.md`); rather than
  create a single-task phase, Phase 07 absorbs both items. Trigger
  is the same Phase 07 frontend work scope (research dialog already
  touches the UI). Required because SC #1 of Phase 07 ("project
  without API key generates and exports successfully") cannot be
  validated end-to-end while the Export button is broken.

  Sub-scope (Phase 06 absorption):
  - Locate the existing Export button(s) in
    `frontend/src/pages/ProjectDetail.tsx` /
    `frontend/src/components/...` (planner discovers exact location)
    and swap to `POST /api/v3/projects/{id}/export`.
  - On 422: render the error envelope (`detail.summary`,
    `detail.errors[]`) in a Radix Dialog/AlertDialog with one row
    per error: `[code badge] · [file] · [PT-BR translation]`. Each
    code has a stable PT-BR string (no English fallback; PT-BR-only
    UI per project memory).
  - Optional dry-run preview: a "Validar antes de exportar" link in
    the modal posts `?dry_run=true` and shows the report without
    creating a zip.

### Cache

- **D-11 (SQLite `research_cache` table; cache key matches v1):**
  Same DB as `llm_credentials` (D-06). Table `research_cache`:
  `(cache_key TEXT PRIMARY KEY, payload JSON, provider TEXT,
  model TEXT, created_at TIMESTAMP)`. Cache key derived from
  `(country_qid, period_label, provider, model)`, hashed with SHA-256
  for fixed-width storage. Re-ingestion of OSM does NOT invalidate
  the cache (D-24 from v1; the cache key is country+period+provider,
  not project-id). UI shows a "cached" badge in the dialog before
  running; the force-refresh checkbox (D-09) bypasses the cache and
  overwrites on success.

### Test pyramid + parity guarantee

- **D-12 (zero-LLM parity test stays green):** A non-skippable
  parity assertion in `tests/parity/test_iberia_868_yaml.py` proves
  that running the pipeline WITHOUT any research overlay produces
  byte-identical output to the Phase 06 baseline. Phase 07 cannot
  regress geometric determinism. The merge code path is guarded by
  `if research_overlay_path.exists()` — absence is the default.

### Folded Todos

None — `gsd-tools todo match-phase 07` returned `todo_count=0`.

### Claude's Discretion

1. **Credential payload encoding.** API keys and OAuth tokens in
   `llm_credentials.payload` — store plaintext JSON, base64, or
   Fernet-encrypted at-rest? Local-only tool; user controls disk
   access. v1 used plaintext. Planner picks; if at-rest encryption
   is added, the master key lives in the OS keyring, not the DB.
2. **CLI piggyback file path discovery.** Cross-platform
   `claude-code` credential location. Research agent verifies
   current paths (typical: `~/.claude/.credentials.json` on Unix,
   `%APPDATA%\Claude\credentials.json` on Windows). If
   `claude-code --print-auth-status` exists, prefer the CLI invocation
   over file-read.
3. **Anthropic SDK version + streaming API.** `anthropic` Python SDK
   1.x — research agent confirms current stable; uses `AsyncAnthropic`
   with `messages.stream` for SSE token pass-through.
4. **Ollama Python client vs raw REST.** Either is fine; Phase 07
   is single-purpose enough that raw `httpx` is acceptable to drop
   the SDK dependency.
5. **SSE message format for research stream.** Reuse the existing
   pipeline-stream pattern (`data: {"stage":"...", "elapsed_ms":N}\n\n`).
6. **Migration mechanism.** Whether to add a third Alembic
   revision (after Phase 01/02 migrations) or use
   `CREATE TABLE IF NOT EXISTS` inline. Planner picks based on what's
   already established in `database.py`.
7. **Pydantic schema field shape for territories.** Derive from
   `inicio/licoes/territory_data_v3.py`. Some fields in v1's
   `MapResearchResult` may have evolved; planner verifies against
   current `territory_metadata.json` shape (Phase 06 schema).
8. **Error code i18n keys for Phase 06 envelope.** PT-BR strings live
   in `frontend/src/i18n/` or inline in the error modal component.
   Planner picks layout; keys are stable per D-08 of Phase 06 CONTEXT.
9. **Dialog visual treatment.** Radix Themes Dialog defaults are
   acceptable; planner styles to match `ParameterSidebar` aesthetic.
10. **Plugin registry import-time vs lazy.** v1 used import-time
    registry population. Phase 07 keeps that pattern unless lazy
    loading is cheaper.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope anchors
- `.planning/ROADMAP.md` §"Phase 07: LLM research as opt-in metadata
  layer" — goal, depends on Phase 06, three success criteria.
- `.planning/PROJECT.md` §"Key Decisions" — D-V3-04 (delete v1 dead
  code, no namespace shims; drives D-01 sidecar-first reading) and
  D-V3-07 (LLM as opt-in sidecar `research_overlay.json`; zero LLM
  in geometric path).
- `.planning/PROJECT.md` §"Out of Scope (v3)" — multi-language UI
  excluded (PT-BR only; drives D-10 i18n note); compound cross-stage
  undo excluded (irrelevant here but referenced).

### Pipeline contract
- `CLAUDE.md` §"v3 Pipeline Contract" — 12-file Unity export; D-03
  preserves this exactly (no 13th file).
- `CLAUDE.md` §"Non-negotiable rules" — rule 4 (`original_idx`),
  rule 7 (`byOriginalIdx`); overlay merge MUST preserve
  `original_idx` on all condados it touches.
- `CLAUDE.md` §"Conventions" — three-layer test pyramid (drives
  test plan in `<domain>`); atomic commits; descriptive test names.
- `CLAUDE.md` §"What v3 explicitly is NOT" — "No LLM-mandatory
  pipeline. The v1.0 Phase 3 LLM dependency is gone; LLM is opt-in
  metadata only." D-12 enforces this.

### v1 archive (design template per D-01)
- `.planning/v1-archive/phases/03-llm-research-integration/03-CONTEXT.md`
  — full v1 decisions: 4 providers (D-01..D-05), LLM→condado matching
  (D-06..D-09), auth per provider (D-10..D-16), Ollama UX
  (D-17..D-19), research scope (D-20..D-22), cache (D-23..D-26),
  retry/validation (D-27..D-29). Phase 07 inherits D-06..D-09,
  D-13, D-17..D-19, D-20..D-29; supersedes D-01..D-05, D-10..D-16
  per Phase 07 D-05 (Claude+Ollama only) and D-06..D-07
  (DB persistence + new auth chain).
- `.planning/v1-archive/phases/03-llm-research-integration/03-RESEARCH.md`
  — provider SDK research, OAuth specifics, JSON-mode equivalence,
  CLI piggyback discovery. Phase 07 inherits the Claude + Ollama
  sections; OpenAI/Gemini sections become v3.1 backlog reference.
- `.planning/v1-archive/phases/03-llm-research-integration/03-UI-SPEC.md`
  — research dialog wireframe + provider selector. Phase 07's
  Radix Dialog modal (D-09) is a simplified single-provider-tab
  rendition.

### Phase carry-forward
- `.planning/phases/06-export-contract-validation-gate/06-CONTEXT.md`
  — D-08 (structured 422 envelope shape; 5 stable error codes), D-19
  (frontend swap deferred to "Phase 06.1 or 07"; Phase 07 D-10
  absorbs). `services/export/zip.py:build_unity_zip` is the
  extension point for D-03 / D-04 merge.
- `.planning/phases/03-read-only-canvas-redesign/03-CONTEXT.md` — D-16
  (`InspectorSidebar` placeholder/project-summary mode); D-08 of
  Phase 07 extends that mode with the research trigger.
- `.planning/phases/04-parameter-studio-live-re-render/04-CONTEXT.md`
  — `ParameterSidebar` panel pattern (Phase 07 D-09 uses a separate
  Radix Dialog, not the panel).

### Code under modification
- `backend/medieval_forge/services/export/zip.py` (Phase 06) —
  `build_unity_zip` is extended to load + merge overlay (D-03).
- `backend/medieval_forge/services/export/schemas.py` (Phase 06) —
  add `research_overlay_applied: bool` to the MANIFEST schema (bump
  `schema_version: 2 → 3`).
- `backend/medieval_forge/services/export/validator.py` (Phase 06) —
  unchanged; validator runs BEFORE overlay merge. Overlay never
  affects geometric validation.
- `backend/medieval_forge/api/v3/__init__.py` — register
  `research_router` and `credentials_router`.
- `backend/medieval_forge/main.py` — include the new routers.
- `backend/medieval_forge/models.py` — extend with `LLMCredential`
  + `ResearchCache` SQLAlchemy models (NOT git-restored from
  `87f8aab`; rewritten under v3 patterns per D-01).
- `backend/medieval_forge/database.py` — migration / table creation
  for `llm_credentials` + `research_cache`.

### Reconquista contract (read-only ground truth)
- `D:\Projetos_Jogo\Reconquista\Assets\StreamingAssets\Maps\*` —
  unchanged. Reconquista loader reads `territory_metadata.json` and
  consumes whatever `name` is present; merged historical names will
  surface in the game once a project ships an overlay.
- `inicio/licoes/territory_data_v3.py` — target schema shape for
  `MapResearchResult`; Pydantic models in D-02 schema port mirror
  this hierarchy (kingdoms → duchies → condados → baronies).

### Session notes
- `.planning/notes/session-2026-04-21-phase3-execute.md` line 66 —
  rationale for D-06 (DB persistence reversal). Cite when planner
  designs the schema.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`services/export/zip.py:build_unity_zip` (Phase 06)** —
  extension point for D-03/D-04. Currently calls `validate_export()`
  then writes 12 files. Phase 07 adds: load
  `project_dir/research_overlay.json` if present, call
  `merge_overlay()` on the in-memory `territory_metadata` dict, then
  write the (possibly merged) version into the zip.
- **Pydantic v2 + `model_validate`** — established by
  `services/pipeline/region_loader.py` (Phase 05) and
  `services/export/schemas.py` (Phase 06). Phase 07
  `ResearchResult` / `MapResearchResult` models reuse the same
  patterns (D-02 port).
- **SSE pattern (run-stream)** —
  `backend/medieval_forge/api/v3/generate.py` and the corresponding
  frontend `useRunStore`/SSE wiring. Phase 07 `useResearchStream`
  mirrors this exactly; `api/v3/research.py` mirrors `generate.py`
  shape.
- **`services/paths.py`** — `is_valid_uuid`, `project_dir`,
  `ensure_project_dirs`. Reused for `research_overlay.json` path
  resolution (`project_dir(project_id) / "research_overlay.json"`).
- **`InspectorSidebar.tsx`** — 3-mode dispatcher (placeholder /
  condado / barony). Phase 07 D-08 extends only the placeholder mode;
  condado mode already reads `name` from metadata and gets merged
  names for free (D-04 endpoint serves merged).
- **`useCanvasArtifacts.ts`** — fetches
  `/api/v3/projects/{id}/artifacts/territory_metadata.json`.
  Phase 07 makes the endpoint merge on the fly when overlay exists;
  the hook does NOT change.
- **Radix Themes Dialog (`@radix-ui/themes`)** — already in stack
  (CLAUDE.md). Phase 07 `ResearchDialog.tsx` uses `<Dialog.Root>`
  + `<Dialog.Content>` + `<Dialog.Title>` per existing patterns.
- **TanStack Query v5** — `useQuery` + `useMutation` patterns
  established in `useCanvasArtifacts` and `useParameterStudioDispatch`.
  Research dialog uses the same.
- **Zustand v5 + zundo `temporal.pause()/resume()`** —
  `CLAUDE.md` says LLM polling should pause undo. Phase 07
  `useResearchStream` wraps the SSE loop in `temporal.pause()` to
  prevent partial-state pollution of the undo stack.

### Established Patterns

- **`services/<package>/<submodule>.py` flat split** — Phase 02
  `adapters/`, Phase 06 `export/`. Phase 07 introduces
  `services/llm/` (flat) + `services/research/` (flat).
- **Atomic commits per task**: `feat(07-NN): ...`, `chore(07-NN): ...`,
  `test(07-NN): ...`.
- **Tests with descriptive names + explicit numeric fixtures** —
  user preference; carries to `test_overlay_merge.py`,
  `test_credential_chain_*.py`, etc.
- **Server restart before UAT** — user preference; applies to all
  frontend tasks in Phase 07 (research dialog + Phase 06 button
  swap).
- **PT-BR UI strings, English code/commits/PRs** — per user memory.
  All error code translations + dialog labels in PT-BR.
- **Status state machine** for projects (`created → ingested →
  generating → generated → exporting → exported`) — Phase 07 does
  NOT add a new state. Research is orthogonal: an overlay can exist
  on any project regardless of pipeline status.

### Integration Points

**Backend new files:**
- `backend/medieval_forge/services/llm/__init__.py`
- `backend/medieval_forge/services/llm/base.py` (Protocol + types)
- `backend/medieval_forge/services/llm/registry.py`
- `backend/medieval_forge/services/llm/claude.py`
- `backend/medieval_forge/services/llm/ollama.py`
- `backend/medieval_forge/services/llm/prompt.py` (literal port D-02)
- `backend/medieval_forge/services/llm/schemas.py` (literal port D-02)
- `backend/medieval_forge/services/llm/retry.py` (literal port D-02)
- `backend/medieval_forge/services/llm/parse.py` (literal port D-02)
- `backend/medieval_forge/services/research/__init__.py`
- `backend/medieval_forge/services/research/runner.py`
- `backend/medieval_forge/services/research/cache.py`
- `backend/medieval_forge/services/research/overlay.py` (merge fn)
- `backend/medieval_forge/services/credential_store.py`
- `backend/medieval_forge/api/v3/research.py`
- `backend/medieval_forge/api/v3/credentials.py`
- `backend/tests/unit/test_overlay_merge.py`
- `backend/tests/unit/test_credential_store.py`
- `backend/tests/unit/test_llm_schemas.py`
- `backend/tests/unit/test_llm_retry.py`
- `backend/tests/unit/test_llm_parse.py`
- `backend/tests/unit/test_research_cache.py`
- `backend/tests/e2e/test_research_overlay_iberia.py`
- `backend/tests/e2e/test_export_button_v3.py` (Phase 06 absorption)

**Backend modifications:**
- `backend/medieval_forge/services/export/zip.py` — load + merge
  overlay before assembling zip.
- `backend/medieval_forge/services/export/schemas.py` — MANIFEST
  schema gains `research_overlay_applied: bool`; bump
  `schema_version: 2 → 3`.
- `backend/medieval_forge/api/v3/artifacts.py` (or wherever
  `territory_metadata.json` is served) — merge on-the-fly when
  overlay exists.
- `backend/medieval_forge/models.py` — add `LLMCredential` +
  `ResearchCache` (rewritten, not restored).
- `backend/medieval_forge/database.py` — table creation.
- `backend/medieval_forge/main.py` — mount `research_router` +
  `credentials_router`.
- `backend/pyproject.toml` — add `anthropic` (Claude SDK);
  Ollama via raw `httpx` (no SDK dep unless planner picks).
- `backend/tests/parity/test_iberia_868_yaml.py` — assert raw output
  byte-identical to Phase 06 baseline when no overlay exists (D-12).

**Frontend new files:**
- `frontend/src/components/research/ResearchDialog.tsx`
- `frontend/src/components/research/ProviderSelector.tsx`
- `frontend/src/components/research/ResearchProgress.tsx`
- `frontend/src/hooks/useResearchStream.ts`
- `frontend/src/stores/useResearchStore.ts` (only if state needs
  exceed TanStack Query — planner's call)
- `frontend/src/components/export/ExportErrorDialog.tsx` (Phase 06
  absorption — renders 422 envelope)
- `frontend/src/i18n/exportErrors.ts` (Phase 06 absorption — PT-BR
  strings keyed by code)
- `frontend/tests/uat/playwright/research_dialog.spec.ts`
- `frontend/tests/uat/playwright/export_v3_error_envelope.spec.ts`

**Frontend modifications:**
- `frontend/src/components/canvas/InspectorSidebar.tsx` — D-08
  trigger in placeholder mode; "Pesquisa aplicada" badge on
  condado/barony modes when overlay covers selected territory.
- The Export button location (planner discovers; likely
  `ProjectDetail.tsx` or a workspace toolbar component) — swap to
  `/api/v3/projects/{id}/export`.

</code_context>

<specifics>
## Specific Ideas

- **"Sidecar-first, design reused not code restored"** — D-01.
  v1-archive 03-CONTEXT.md is the bible for *what* to build;
  `87f8aab` is the source for the 4 pure artifacts (D-02). Everything
  else is rewritten v3.
- **"Zero LLM in geometric path stays inviolable"** — D-12. Parity
  test catches any regression. Merge code path is guarded by overlay
  file existence.
- **"Non-destructive merge"** — D-03 + D-04. Pipeline output on
  disk never overwritten by research. Re-running pipeline always
  produces deterministic raw output. Overlay sits alongside.
- **"MVP Claude + Ollama covers the two ends"** — D-05. Frontier +
  zero-cost. OpenAI/Gemini wait for v3.1 (plugin slot ready; not
  shipped).
- **"CLI piggyback first"** — D-07. Users who already have
  `claude-code` installed get zero-setup research.
- **"DB persistence reversal stays"** — D-06. v1 reverted from
  memory-only because users wanted persistence. Phase 07 inherits
  the decision; same DB file as the rest of the project.
- **"Phase 07 absorbs the Phase 06 frontend leftover"** — D-10.
  Export button is broken today (v1 endpoint deleted). Phase 07
  already touches the frontend; absorbing avoids a single-task
  06.1 phase.
- **"PT-BR strings, code in English"** — established preference.
  Stable error codes from Phase 06 D-08 make i18n trivial.
- **"Plugin registry pattern from v1"** — even with 2 adapters,
  the registry is the right shape; adding OpenAI later = one file
  + one line.

</specifics>

<deferred>
## Deferred Ideas

- **OpenAI provider** — v3.1 backlog. Plugin slot ready in
  `services/llm/registry.py`; adapter is one file.
- **Gemini provider + Google OAuth installed-app flow** — v3.1.
  Requires OAuth client_id bundling and PKCE infrastructure;
  not justified by single-provider MVP.
- **Anthropic OAuth** — deferred indefinitely. CLI piggyback +
  API key cover all access patterns today.
- **Drag-and-drop condado re-assignment on canvas** — separate
  phase if/when manual override of LLM output is wanted.
- **Automatic provider fallback** (Claude fails → try Ollama) —
  v1 explicitly rejected; user choice only.
- **Multi-turn agent-style refinement** — v1 explicitly rejected.
- **Token usage UI per project** — v1 deferred; still deferred.
- **Manual overlay editing via UI** — overlay is read-only output
  from research; force-refresh is the regen path. Editing JSON
  by hand is supported via the filesystem (the file is just there
  in `project_dir/`).
- **Region-key promotion of overlay to YAML default** — overlay
  is per-project, never global. If a region grows curated names
  worth sharing, promote to `data/regions/<region>.yaml` `condados:`
  curated entries (Phase 05 mechanism).
- **Re-ingestion invalidating cache** — v1 D-24 (re-ingest does NOT
  invalidate); Phase 07 inherits.
- **Per-project credential override** — credentials are global
  (per-provider). If a user needs multiple Claude accounts per
  project, add a `project_id` column later.
- **At-rest credential encryption** — Claude's Discretion #1.
  v1 plaintext; OS keyring escrow possible later.
- **Streaming SSE for very large research outputs** — Iberia
  scale (5 kingdoms, 91 condados, 250 baronies) fits a single
  response. If a region needs splitting, add chunked SSE.
- **OpenAI/Gemini-specific JSON-mode work** — v1 had three
  different JSON-mode flavors normalized in the adapter. Phase 07
  ships Claude (tool-use or `messages.create` with JSON instructions)
  + Ollama (`format: "json"`); the normalization layer stays simple.

### Reviewed Todos (not folded)

None — `gsd-tools todo match-phase 07` returned `todo_count=0`.

</deferred>

---

*Phase: 07-llm-research-as-opt-in-metadata-layer*
*Context gathered: 2026-05-13*
