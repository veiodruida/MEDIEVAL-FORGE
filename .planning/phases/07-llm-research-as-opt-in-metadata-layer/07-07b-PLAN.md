---
phase: 07-llm-research-as-opt-in-metadata-layer
plan: 07b
type: execute
wave: 4
depends_on: [01, 04, 05, 06, 07a]
files_modified:
  - backend/medieval_forge/services/research/runner.py
  - backend/medieval_forge/services/research/__init__.py
  - backend/medieval_forge/api/v3/research.py
  - backend/medieval_forge/api/v3/credentials.py
  - backend/medieval_forge/main.py
  - backend/tests/integration/test_research_sse.py
autonomous: true
requirements:
  - V3-LLM-OPT-IN
must_haves:
  truths:
    - "services/research/runner.py mirrors api/v3/generate.py SSE pattern exactly: _RUN_QUEUES per (project_id) + single-flight 409 gate + finally-block eviction (Pitfall 7 / WR-02 carry)"
    - "Runner writes BOTH research_overlay.json AND research_overlay.meta.json atomically (BLOCKER 2 D-08 microcopy fix — UI-SPEC §Surface 2 depends on meta sidecar)"
    - "Meta sidecar carries `generated_at` (from cache row OR fresh runner timestamp) AND `applied_at` (always the runner-write timestamp) per REVIEWS fix #2 — two timestamps disambiguate cache-hit reuse from fresh-generation"
    - "api/v3/research.py exposes POST /start, GET /stream/{run_id}, GET /providers (returns available_models from Ollama per REVIEWS fix #5), GET /health, GET /overlay (returns {exists, covered_condado_ids, meta with both timestamps}), POST /stop/{run_id}"
    - "api/v3/credentials.py exposes GET /credentials, POST /credentials/{provider}, DELETE /credentials/{provider}"
    - "main.py mounts research_router + credentials_router with /api prefix"
    - "research_overlay.json + research_overlay.meta.json are written ATOMICALLY via tmp+replace pattern (RESEARCH §Pitfall 1 + Example 3)"
  artifacts:
    - path: "backend/medieval_forge/services/research/runner.py"
      provides: "SSE orchestration mirroring api/v3/generate.py + atomic overlay + meta-sidecar writes with generated_at + applied_at (REVIEWS fix #2)"
      contains: "_RUN_QUEUES"
    - path: "backend/medieval_forge/api/v3/research.py"
      provides: "FastAPI router for research start/stream/stop/providers/health/overlay endpoints (overlay returns {exists, covered_condado_ids, meta with both timestamps})"
      contains: "router = APIRouter"
    - path: "backend/medieval_forge/api/v3/credentials.py"
      provides: "FastAPI router for credential CRUD per provider"
      contains: "router = APIRouter"
    - path: "backend/tests/integration/test_research_sse.py"
      provides: "Wave 0 gate — SSE shape per stage + cancel abort + meta sidecar atomic write + dual timestamps"
      contains: "test_research_stream"
  key_links:
    - from: "backend/medieval_forge/services/research/runner.py"
      to: "backend/medieval_forge/services/llm/registry.py:PROVIDERS"
      via: "Plan 04 PROVIDERS dict lookup by provider_id"
      pattern: "PROVIDERS\\[.*provider"
    - from: "backend/medieval_forge/main.py"
      to: "backend/medieval_forge/api/v3/research.py + credentials.py"
      via: "app.include_router(research_router, prefix='/api'); app.include_router(credentials_router, prefix='/api')"
      pattern: "include_router"
---

<objective>
Land the research orchestration layer: SSE runner mirroring api/v3/generate.py, two new FastAPI routers (research + credentials), and the meta-sidecar that enables UI-SPEC §Surface 2 microcopy. Pre-split from former Plan 07 per checker WARNING 1.

Purpose: D-09 endpoints; D-11 cache consumption; Pattern 6 SSE runner; Pitfall 7 (WR-02); Pitfall 1 atomic write; D-08 microcopy support (BLOCKER 2 fix — meta sidecar).

REVIEWS replan 2026-05-14 deltas:
- **Fix #2 (Codex)**: meta sidecar carries BOTH `generated_at` and `applied_at`. On cache-hit path, `generated_at` is read from `ResearchCache.generated_at` (Plan 07a). On fresh-run path, both equal `datetime.now()`. The UI (Plan 09b) chooses the microcopy form based on whether they match.
- **Fix #5 (OpenCode)**: `/providers` endpoint returns `available_models: list[str]` for Ollama (via `client.list()`), enabling the frontend ProviderSelector to default to whichever installed model best matches the ordered preference list `['qwen2.5:7b', 'qwen2.5-coder:14b', 'gemma4:26b', 'deepseek-r1:14b']`. No credential payload leaks.

Output:
- runner.py (with atomic overlay + meta-sidecar dual timestamps)
- api/v3/research.py (with overlay endpoint returning `meta` field carrying both timestamps + /providers returning available_models)
- api/v3/credentials.py
- main.py router mounts
- integration test_research_sse.py
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@CLAUDE.md
@.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-CONTEXT.md
@.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-RESEARCH.md
@.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-UI-SPEC.md
@.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-REVIEWS.md
@backend/medieval_forge/api/v3/generate.py
@backend/medieval_forge/api/v3/_run_state.py
@backend/medieval_forge/services/llm/__init__.py
@backend/medieval_forge/services/research/overlay.py
@backend/medieval_forge/services/research/matcher.py
@backend/medieval_forge/services/research/cache.py
@backend/medieval_forge/services/credential_store.py
@backend/medieval_forge/services/paths.py
@backend/medieval_forge/main.py

<interfaces>
<!-- Existing SSE pattern to mirror exactly (api/v3/generate.py) -->

From backend/medieval_forge/api/v3/generate.py:
  - _RUN_QUEUES: dict[str, asyncio.Queue[str | None]]
  - _RUN_TASKS: dict[str, asyncio.Task]
  - def _emit(queue, event_type, stage, message="", progress=None) — payload {event_type, stage, message, progress}
  - 409 if alive (single-flight gate)
  - finally: _RUN_QUEUES.pop(project_id, None) + _RUN_TASKS.pop(project_id, None) (WR-02)

From backend/medieval_forge/services/paths.py:
  - project_dir(project_id) returns validated Path (UUID + containment)
  - _write_geojson_atomic(path, data_str) — tmp.write_text + tmp.replace(path)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: services/research/runner.py — SSE producer/consumer + atomic overlay + meta-sidecar with generated_at+applied_at (REVIEWS fix #2)</name>
  <files>
    backend/medieval_forge/services/research/runner.py
    backend/medieval_forge/services/research/__init__.py
    backend/tests/integration/test_research_sse.py
  </files>
  <read_first>
    - backend/medieval_forge/api/v3/generate.py (CANONICAL pattern reference — mirror EXACTLY; especially _RUN_QUEUES + _emit + finally-block eviction)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-RESEARCH.md §Pattern 6 (SSE Research Runner)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-RESEARCH.md §Pitfall 7 (WR-02 — late-subscriber 404 is intentional)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-RESEARCH.md §Pitfall 1 + §Example 3 (atomic overlay write)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-UI-SPEC.md §Surface 2 microcopy
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-REVIEWS.md "Recommended Action Before Execution" #2 (generated_at + applied_at split)
    - backend/medieval_forge/services/paths.py
    - backend/medieval_forge/services/llm/__init__.py (PROVIDERS registry)
    - backend/medieval_forge/services/research/matcher.py (Plan 06)
    - backend/medieval_forge/services/research/cache.py (Plan 07a — exposes cache_get_with_generated_at)
  </read_first>
  <behavior>
    - Test 1: `test_research_stream_emits_4_stage_events_kingdoms_duchies_condados_baronies` — start a research run with mocked LLM provider; consume SSE stream; assert 4 stage events.
    - Test 2: `test_research_stream_returns_409_when_run_already_in_flight_for_project` — single-flight gate.
    - Test 3: `test_research_stop_aborts_in_flight_run_and_evicts_queue` — /stop + WR-02 finally eviction.
    - Test 4: `test_research_cache_hit_short_circuits_provider_call` — cached path; provider.research() NOT called.
    - Test 5: `test_research_overlay_written_atomically_via_tmp_replace` — atomic semantics.
    - Test 6 (BLOCKER 2): `test_research_overlay_meta_sidecar_written_with_provider_model_timestamps` — after runner success, assert `research_overlay.meta.json` exists alongside `research_overlay.json` with keys `{provider, model, generated_at, applied_at, prompt_digest, schema_version, country, period}`, atomic.
    - **Test 7 (REVIEWS fix #2 — fresh-run path)**: `test_meta_sidecar_generated_at_equals_applied_at_on_fresh_run` — fresh research run (no cache hit); assert `meta.generated_at == meta.applied_at` (both equal `datetime.now()` to seconds precision).
    - **Test 8 (REVIEWS fix #2 — cache-hit path)**: `test_meta_sidecar_generated_at_predates_applied_at_on_cache_hit` — seed cache row with `generated_at = T0`; trigger runner at `T1 > T0`; assert `meta.generated_at == T0` (from cache) AND `meta.applied_at == T1` (from runner-write); these are DIFFERENT timestamps.
  </behavior>
  <action>
    1. Create `backend/medieval_forge/services/research/runner.py`. Mirror `api/v3/generate.py` exactly. Key additions vs former Plan 07:

       **Generalize atomic write to `_write_json_atomic`** (handles both overlay + meta sidecar):

       ```python
       def _write_json_atomic(path: Path, data: dict) -> None:
           """Pitfall 1 + Example 3 — atomic write via tmp+replace."""
           tmp = path.with_suffix(path.suffix + ".tmp")
           tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
           tmp.replace(path)
       ```

       **REVIEWS fix #2 — dual-timestamp meta sidecar**:

       ```python
       from datetime import datetime, timezone
       from ..research.cache import cache_get_with_generated_at, cache_put, cache_key, PROMPT_DIGEST, SCHEMA_VERSION

       async def _run_research(...):
           # ... build canonical cache_key per Plan 07a ...
           applied_at = datetime.now(timezone.utc)

           if not force_refresh:
               cached = await cache_get_with_generated_at(session, ck)
               if cached is not None:
                   payload, generated_at = cached  # REVIEWS fix #2 — generated_at from DB row
               else:
                   payload = None
                   generated_at = applied_at
           else:
               payload = None
               generated_at = applied_at

           if payload is None:
               # Fresh run: call provider, store in cache
               payload = await PROVIDERS[provider_id].research(...)
               generated_at = applied_at  # fresh run: both timestamps equal
               await cache_put(session, ck, payload, provider=provider_id, model=model)

           # Convert payload → overlay
           overlay = llm_output_to_overlay(payload, condado_list=condado_ids)

           # Atomic dual write
           overlay_path = project_dir(project_id) / "research_overlay.json"
           meta_path = project_dir(project_id) / "research_overlay.meta.json"
           _write_json_atomic(overlay_path, overlay)
           meta = {
               "provider": provider_id,
               "model": model,
               "generated_at": generated_at.isoformat(timespec="seconds"),  # REVIEWS fix #2
               "applied_at": applied_at.isoformat(timespec="seconds"),      # REVIEWS fix #2
               "prompt_digest": PROMPT_DIGEST,
               "schema_version": SCHEMA_VERSION,
               "country": country_qid,
               "period": period_label,
           }
           _write_json_atomic(meta_path, meta)
       ```

       NB: `applied_at` is COMPUTED ONCE at the top of the runner and reused on both
       branches (cache-hit and fresh-run), so the SSE stream events and the meta sidecar
       all carry a single coherent "when this runner ran" timestamp.

    2. Full runner skeleton mirrors former Plan 07 Task 2 (single-flight gate, _emit envelope, finally eviction, cache check, provider call via PROVIDERS, matcher.llm_output_to_overlay, cache_put). Structural changes vs former Plan 07:
       - `_write_geojson_atomic` → `_write_json_atomic` (or both names, your call)
       - Sibling meta sidecar write on every successful overlay write (cache-hit AND fresh-run)
       - **REVIEWS fix #2**: meta sidecar now has BOTH `generated_at` and `applied_at`

    3. UPDATE `backend/medieval_forge/services/research/__init__.py`:

       ```python
       from .overlay import merge_overlay, load_overlay_if_exists, ResearchOverlay, CondadoOverlayEntry, _ZIP_BOUND_FIELDS
       from .matcher import build_pipeline_condado_list, llm_output_to_overlay
       from .cache import cache_key, cache_get, cache_get_with_generated_at, cache_put, PROMPT_DIGEST, PROMPT_VERSION, SCHEMA_VERSION
       from .runner import start_research, get_stream, stop_research, _RUN_QUEUES, _RUN_TASKS
       ```

    4. Create `backend/tests/integration/test_research_sse.py` with the 8 cases from <behavior>. Use httpx.AsyncClient or call start_research/get_stream/stop_research directly with mocked PROVIDERS.

       Test 8 example:
       ```python
       async def test_meta_sidecar_generated_at_predates_applied_at_on_cache_hit(session, tmp_project_dir):
           # Seed cache row with T0 timestamp via direct INSERT
           t0 = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
           # ... insert ResearchCache(..., generated_at=t0)
           # Run research (no force_refresh)
           t_before = datetime.now(timezone.utc)
           await start_research(project_id=..., provider="claude", model="claude-sonnet-4-6",
                               country_qid="Q29", period_label="868 AD", force_refresh=False, ...)
           # Read meta sidecar
           meta = json.loads((tmp_project_dir / "research_overlay.meta.json").read_text())
           assert meta["generated_at"] == t0.isoformat(timespec="seconds")  # from cache
           assert meta["applied_at"] >= t_before.isoformat(timespec="seconds")  # from runner
           assert meta["generated_at"] != meta["applied_at"]
       ```
  </action>
  <acceptance_criteria>
    - File `backend/medieval_forge/services/research/runner.py` EXISTS
    - `grep -n "_RUN_QUEUES" backend/medieval_forge/services/research/runner.py` returns ≥3 matches
    - `grep -n "_RUN_TASKS" backend/medieval_forge/services/research/runner.py` returns ≥3 matches
    - `grep -n "finally:" backend/medieval_forge/services/research/runner.py` returns ≥1 match
    - `grep -n "queue.put_nowait(None)" backend/medieval_forge/services/research/runner.py` returns ≥1 match
    - `grep -n "tmp.replace" backend/medieval_forge/services/research/runner.py` returns ≥1 match
    - `grep -n "def _emit" backend/medieval_forge/services/research/runner.py` returns 1 match
    - `grep -n '"event_type"' backend/medieval_forge/services/research/runner.py` returns ≥1 match
    - `grep -n 'research_overlay.json' backend/medieval_forge/services/research/runner.py` returns ≥1 match
    - `grep -n 'research_overlay.meta.json' backend/medieval_forge/services/research/runner.py` returns ≥1 match (BLOCKER 2)
    - `grep -nE '"provider":|"model":' backend/medieval_forge/services/research/runner.py` returns ≥2 matches
    - `grep -n '"generated_at":' backend/medieval_forge/services/research/runner.py` returns ≥1 match (REVIEWS fix #2)
    - `grep -n '"applied_at":' backend/medieval_forge/services/research/runner.py` returns ≥1 match (REVIEWS fix #2)
    - `grep -n "cache_get_with_generated_at" backend/medieval_forge/services/research/runner.py` returns ≥1 match (REVIEWS fix #2 — cache-hit propagates generated_at)
    - File `backend/tests/integration/test_research_sse.py` EXISTS with ≥8 test functions
    - `grep -n "test_research_overlay_meta_sidecar_written_with_provider_model_timestamps" backend/tests/integration/test_research_sse.py` returns 1 match
    - `grep -n "test_meta_sidecar_generated_at_equals_applied_at_on_fresh_run" backend/tests/integration/test_research_sse.py` returns 1 match (REVIEWS fix #2)
    - `grep -n "test_meta_sidecar_generated_at_predates_applied_at_on_cache_hit" backend/tests/integration/test_research_sse.py` returns 1 match (REVIEWS fix #2)
    - `cd backend && pytest tests/integration/test_research_sse.py -x -q` exits 0
  </acceptance_criteria>
  <verify>
    <automated>cd backend && pytest tests/integration/test_research_sse.py -x -q</automated>
  </verify>
  <done>SSE runner lands; WR-02 eviction tested; atomic overlay + meta sidecar (with dual timestamps per REVIEWS fix #2) both verified.</done>
</task>

<task type="auto">
  <name>Task 2: api/v3/research.py + api/v3/credentials.py + main.py mounts — overlay endpoint returns {exists, covered_condado_ids, meta with both timestamps} + /providers returns available_models (REVIEWS fix #5)</name>
  <files>
    backend/medieval_forge/api/v3/research.py
    backend/medieval_forge/api/v3/credentials.py
    backend/medieval_forge/main.py
  </files>
  <read_first>
    - backend/medieval_forge/api/v3/generate.py (router pattern + dependency injection)
    - backend/medieval_forge/api/v3/export.py (Phase 06 — db_session injection pattern)
    - backend/medieval_forge/main.py (router mounting pattern)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-CONTEXT.md (D-09 endpoint list)
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-UI-SPEC.md §Surface 2
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-REVIEWS.md "Recommended Action Before Execution" #2, #5
    - backend/medieval_forge/services/research/runner.py (Task 1)
    - backend/medieval_forge/services/credential_store.py (Plan 01)
    - backend/medieval_forge/services/llm/__init__.py (PROVIDERS)
    - backend/medieval_forge/services/llm/ollama.py (Plan 04 — `OllamaProvider.health()` returns `{ok, available_models}` per REVIEWS fix #5)
  </read_first>
  <action>
    1. Create `backend/medieval_forge/api/v3/research.py` with endpoints per D-09 + UI-SPEC. Standard endpoints: POST /start, GET /stream/{run_id}, POST /stop/{run_id}, GET /providers, GET /health (alias).

    **REVIEWS fix #5 — `/providers` endpoint shape**:

    ```python
    @router.get("/providers")
    async def get_providers():
        """Returns provider list with health + Ollama available_models (REVIEWS fix #5).

        No credential payload leaks: only {provider_id, display_name, healthy, message,
        configured, available_models?}.
        """
        out = []
        for pid, provider in PROVIDERS.items():
            health = await provider.health()  # {ok, message, available_models?}
            entry = {
                "provider_id": pid,
                "display_name": provider.display_name,
                "healthy": health.get("ok", False),
                "message": health.get("message", ""),
                "configured": provider.is_configured(),
            }
            if "available_models" in health:
                entry["available_models"] = health["available_models"]  # REVIEWS fix #5
            out.append(entry)
        return out
    ```

    For Ollama specifically: `OllamaProvider.health()` (Plan 04) calls `client.list()` and
    returns `{"ok": True, "available_models": ["qwen2.5-coder:14b", "gemma4:26b", "deepseek-r1:14b"]}`.
    The frontend ProviderSelector (Plan 09a) consumes `available_models` and applies the
    ordered preference `['qwen2.5:7b', 'qwen2.5-coder:14b', 'gemma4:26b', 'deepseek-r1:14b']`
    to pick a default.

    **BLOCKER 2 + REVIEWS fix #2 — overlay endpoint shape**:

    ```python
    overlay_router = APIRouter(prefix="/v3/projects", tags=["research"])

    @overlay_router.get("/{project_id}/research/overlay")
    async def get_overlay(project_id: str):
        """Returns {exists, covered_condado_ids, meta} or {exists:false, covered_condado_ids:[], meta:null}.

        REVIEWS fix #2: meta carries BOTH `generated_at` (original LLM-output timestamp,
        possibly older than applied_at on cache-hit paths) AND `applied_at` (when the
        runner wrote this overlay to the project). Plan 09b microcopy renders single-line
        when they match, two-line when they differ.
        """
        overlay_path = project_dir(project_id) / "research_overlay.json"
        if not overlay_path.exists():
            return {"exists": False, "covered_condado_ids": [], "meta": None}
        overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
        covered = list(overlay.keys())

        meta_path = project_dir(project_id) / "research_overlay.meta.json"
        meta = None
        if meta_path.exists():
            raw_meta = json.loads(meta_path.read_text(encoding="utf-8"))
            # Trim to UI-bound subset (don't leak prompt_digest / schema_version internals to UI)
            meta = {
                "provider": raw_meta.get("provider"),
                "model": raw_meta.get("model"),
                "generated_at": raw_meta.get("generated_at"),  # REVIEWS fix #2
                "applied_at": raw_meta.get("applied_at"),      # REVIEWS fix #2
            }
        return {"exists": True, "covered_condado_ids": covered, "meta": meta}
    ```

    Note: the legacy "return raw JSON" variant is GONE. Plan 09a's `useResearchOverlay` consumes this shape directly.

    2. Create `backend/medieval_forge/api/v3/credentials.py` per former Plan 07 Task 3 (GET / POST /{provider} / DELETE /{provider} returning {configured: bool} only — no payload leakage).

    3. UPDATE `backend/medieval_forge/main.py` to mount both routers + overlay_router under `/api`.

    Verify final paths:
    - `/api/v3/research/start`, `/stream/{run_id}`, `/stop/{run_id}`, `/providers`, `/health`
    - `/api/v3/projects/{id}/research/overlay` (returns {exists, covered_condado_ids, meta with both timestamps})
    - `/api/v3/credentials`, `/credentials/{provider}` (POST/DELETE)
  </action>
  <acceptance_criteria>
    - File `backend/medieval_forge/api/v3/research.py` EXISTS
    - `grep -n "@router.post(\"/start\")" backend/medieval_forge/api/v3/research.py` returns 1 match
    - `grep -nE "@router.get\(\"/stream/\{run_id\}\"\)" backend/medieval_forge/api/v3/research.py` returns 1 match
    - `grep -n "@router.post(\"/stop/{run_id}\")" backend/medieval_forge/api/v3/research.py` returns 1 match
    - `grep -n "@router.get(\"/providers\")" backend/medieval_forge/api/v3/research.py` returns 1 match
    - `grep -n "media_type=\"text/event-stream\"" backend/medieval_forge/api/v3/research.py` returns 1 match
    - `grep -n "research_overlay.meta.json" backend/medieval_forge/api/v3/research.py` returns ≥1 match (BLOCKER 2 — meta sidecar consumed)
    - `grep -nE "\"meta\": meta|\"meta\":\s*None|\"meta\": None" backend/medieval_forge/api/v3/research.py` returns ≥2 matches (overlay response includes meta on both branches)
    - `grep -n "\"covered_condado_ids\":" backend/medieval_forge/api/v3/research.py` returns ≥2 matches
    - `grep -n "\"generated_at\":" backend/medieval_forge/api/v3/research.py` returns ≥1 match (REVIEWS fix #2)
    - `grep -n "\"applied_at\":" backend/medieval_forge/api/v3/research.py` returns ≥1 match (REVIEWS fix #2)
    - `grep -n "available_models" backend/medieval_forge/api/v3/research.py` returns ≥1 match (REVIEWS fix #5)
    - File `backend/medieval_forge/api/v3/credentials.py` EXISTS
    - `grep -n "@router.post(\"/{provider}\")" backend/medieval_forge/api/v3/credentials.py` returns 1 match
    - `grep -n "@router.delete(\"/{provider}\")" backend/medieval_forge/api/v3/credentials.py` returns 1 match
    - `grep -nE "include_router\(research_router" backend/medieval_forge/main.py` returns 1 match
    - `grep -nE "include_router\(credentials_router" backend/medieval_forge/main.py` returns 1 match
    - `cd backend && python -c "from medieval_forge.main import app; routes = {r.path for r in app.routes}; assert '/api/v3/research/start' in routes; assert '/api/v3/credentials' in routes"` exits 0
    - Endpoint shape `GET /api/v3/research/providers` returns `[{provider_id, display_name, healthy, message, configured, available_models?}]` with NO `payload` / `key` fields (T-07-07b-01)
  </acceptance_criteria>
  <verify>
    <automated>cd backend && python -c "from medieval_forge.main import app; routes = {r.path for r in app.routes}; assert '/api/v3/research/start' in routes; assert '/api/v3/credentials' in routes"</automated>
  </verify>
  <done>Routers mounted; overlay endpoint returns {exists, covered_condado_ids, meta with both timestamps} per BLOCKER 2 + REVIEWS fix #2; /providers surfaces available_models per REVIEWS fix #5; no credential payload leaks.</done>
</task>

</tasks>

<context_anchors>
- **D-08** (microcopy "Última pesquisa: {provider} · {model} · {timestamp}" — meta sidecar enables it; REVIEWS fix #2 splits into generated_at + applied_at)
- **D-09** (Radix Dialog + SSE)
- **D-11** (cache table consumed by runner)
- **Discretion #5** (SSE envelope mirrors generate.py)
- **RESEARCH §Pattern 6** (SSE runner)
- **RESEARCH §Pitfall 1** (atomic overlay write)
- **RESEARCH §Pitfall 7** (WR-02 finally eviction)
- **UI-SPEC §Surface 2** (microcopy)
- **Checker BLOCKER 2** (meta sidecar)
- **REVIEWS fix #2** (generated_at + applied_at split)
- **REVIEWS fix #5** (Ollama available_models surfaced on /providers)
</context_anchors>

<threat_model>

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| HTTP request → research/start | Untrusted body |
| HTTP request → SSE stream | Late-subscribers may read drained queue |
| HTTP request → /providers | Must NOT return credential payload |
| Disk write → research_overlay.json + .meta.json | Must be atomic |
| LLM provider → SSE queue | Untrusted LLM tokens streamed to client |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-07b-01 | Information Disclosure | /providers leaks credentials | mitigate | Endpoint returns `{provider_id, display_name, healthy, message, configured, available_models?}` only — no payload/key. Acceptance: `grep -n "payload\|\"key\"" backend/medieval_forge/api/v3/research.py` returns 0 in providers builder. |
| T-07-07b-02 | Tampering | Path traversal via project_id | mitigate | `project_dir(project_id)` enforces UUID + path containment (Phase 03 paths.py). |
| T-07-07b-03 | Tampering | Torn overlay or meta write | mitigate | Both files use _write_json_atomic via tmp+replace. Test 5 + Test 6. |
| T-07-07b-04 | Tampering | LLM prompt injection via period_label | mitigate | Pydantic-validated `period: str`; literal-port prompt.py uses safe-format; retry loop schema-validates output. |
| T-07-07b-05 | DoS | SSE event flood | mitigate | 3s heartbeat (Ollama); Claude bounded by SDK. |
| T-07-07b-06 | DoS | Single-flight gate bypass | mitigate | _RUN_QUEUES check at start; 409 on concurrent /start. Test 2. |
| T-07-07b-07 | Tampering | Late subscriber to drained queue | mitigate | GET /stream returns 404 when no active run. |
| T-07-07b-08 | Information Disclosure | Meta sidecar leaks prompt_digest / schema_version internals | mitigate | Overlay endpoint trims meta to {provider, model, generated_at, applied_at} — does NOT echo prompt_digest / schema_version / country / period to UI consumers. |
| T-07-07b-09 | CSRF | SSE channel origin check | accept | Single-user local tool; CORS localhost-only. |
| T-07-07b-10 (REVIEWS fix #2) | Tampering | Timestamp confusion between cache-hit and fresh-run | mitigate | Two explicit fields (generated_at vs applied_at). Test 7 + Test 8 in integration suite assert correctness on both branches. |

</threat_model>

<verification>
- `cd backend && pytest tests/integration/test_research_sse.py -x -q` exits 0
- `cd backend && python -c "from medieval_forge.main import app; routes = {r.path for r in app.routes}; assert '/api/v3/research/start' in routes"` exits 0
- `cd backend && python -c "from medieval_forge.services.research import start_research, get_stream, stop_research, _RUN_QUEUES, _RUN_TASKS"` exits 0
- `curl -s http://localhost:8000/api/v3/research/providers` returns JSON array with NO payload/key fields AND with `available_models` for Ollama (manual UAT Plan 11)
- `curl -s http://localhost:8000/api/v3/projects/{id}/research/overlay` returns `{exists, covered_condado_ids, meta with generated_at + applied_at}` shape (manual UAT)
</verification>

<success_criteria>
- 6 research endpoints + 3 credentials endpoints reachable
- Overlay endpoint shape `{exists, covered_condado_ids, meta with generated_at + applied_at}` per BLOCKER 2 + REVIEWS fix #2
- /providers surfaces Ollama available_models per REVIEWS fix #5
- Meta sidecar written atomically alongside overlay with both timestamps
- WR-02 eviction tested; cache-hit path short-circuits provider + propagates generated_at from DB
</success_criteria>

<output>
After completion, create `.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-07b-SUMMARY.md` per the standard template.
</output>
