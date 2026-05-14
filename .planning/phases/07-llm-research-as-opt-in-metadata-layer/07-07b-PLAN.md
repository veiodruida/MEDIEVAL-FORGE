---
phase: 07-llm-research-as-opt-in-metadata-layer
plan: 07b
type: execute
wave: 3
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
    - "Runner writes BOTH research_overlay.json AND research_overlay.meta.json atomically (BLOCKER 2 D-08 microcopy fix — UI-SPEC §Surface 2 'Última pesquisa: {provider} · {model} · {YYYY-MM-DD HH:mm}' depends on meta sidecar)"
    - "api/v3/research.py exposes POST /start, GET /stream/{run_id}, GET /providers, GET /health, GET /overlay (returns {exists, covered_condado_ids, meta}), POST /stop/{run_id}"
    - "api/v3/credentials.py exposes GET /credentials, POST /credentials/{provider}, DELETE /credentials/{provider}"
    - "main.py mounts research_router + credentials_router with /api prefix"
    - "research_overlay.json + research_overlay.meta.json are written ATOMICALLY via tmp+replace pattern (RESEARCH §Pitfall 1 + Example 3)"
  artifacts:
    - path: "backend/medieval_forge/services/research/runner.py"
      provides: "SSE orchestration mirroring api/v3/generate.py (per-(project_id) _RUN_QUEUES + finally eviction) + atomic overlay + meta-sidecar writes"
      contains: "_RUN_QUEUES"
    - path: "backend/medieval_forge/api/v3/research.py"
      provides: "FastAPI router for research start/stream/stop/providers/health/overlay endpoints (overlay returns {exists, covered_condado_ids, meta})"
      contains: "router = APIRouter"
    - path: "backend/medieval_forge/api/v3/credentials.py"
      provides: "FastAPI router for credential CRUD per provider"
      contains: "router = APIRouter"
    - path: "backend/tests/integration/test_research_sse.py"
      provides: "Wave 0 gate — SSE shape per stage + cancel abort + meta sidecar atomic write"
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

Output:
- runner.py (with atomic overlay + meta-sidecar writes)
- api/v3/research.py (with overlay endpoint returning `meta` field)
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
  <name>Task 1: services/research/runner.py — SSE producer/consumer + atomic overlay + meta-sidecar write (BLOCKER 2 fix)</name>
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
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-UI-SPEC.md §Surface 2 ("Última pesquisa: {provider} · {model} · {YYYY-MM-DD HH:mm}" microcopy — meta sidecar enables this)
    - backend/medieval_forge/services/paths.py
    - backend/medieval_forge/services/llm/__init__.py (PROVIDERS registry)
    - backend/medieval_forge/services/research/matcher.py (Plan 06)
    - backend/medieval_forge/services/research/cache.py (Plan 07a)
  </read_first>
  <behavior>
    - Test 1: `test_research_stream_emits_4_stage_events_kingdoms_duchies_condados_baronies` — start a research run with mocked LLM provider; consume SSE stream; assert 4 stage events.
    - Test 2: `test_research_stream_returns_409_when_run_already_in_flight_for_project` — single-flight gate.
    - Test 3: `test_research_stop_aborts_in_flight_run_and_evicts_queue` — /stop + WR-02 finally eviction.
    - Test 4: `test_research_cache_hit_short_circuits_provider_call` — cached path; provider.research() NOT called.
    - Test 5: `test_research_overlay_written_atomically_via_tmp_replace` — atomic semantics.
    - Test 6 (BLOCKER 2): `test_research_overlay_meta_sidecar_written_with_provider_model_created_at` — after runner success, assert `research_overlay.meta.json` exists alongside `research_overlay.json` with keys {provider, model, created_at, prompt_version, country, period}, atomic.
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

       **On runner success, write BOTH files** (BLOCKER 2):

       ```python
       overlay_path = project_dir(project_id) / "research_overlay.json"
       meta_path = project_dir(project_id) / "research_overlay.meta.json"
       _write_json_atomic(overlay_path, overlay)
       meta = {
           "provider": provider_id,
           "model": model,
           "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "prompt_version": PROMPT_VERSION,
           "country": country_qid,
           "period": period_label,
       }
       _write_json_atomic(meta_path, meta)
       ```

       Apply BOTH on cache-hit path and on fresh-run path (so the meta sidecar is always in sync with the overlay file).

    2. Full runner skeleton mirrors former Plan 07 Task 2 (single-flight gate, _emit envelope, finally eviction, cache check, provider call via PROVIDERS, matcher.llm_output_to_overlay, cache_put). The only structural changes vs former Plan 07 are:
       - `_write_geojson_atomic` → `_write_json_atomic` (or both names, your call — see <action> step 1)
       - Sibling meta sidecar write on every successful overlay write (cache-hit AND fresh-run)

    3. UPDATE `backend/medieval_forge/services/research/__init__.py`:

       ```python
       from .overlay import merge_overlay, load_overlay_if_exists, ResearchOverlay, CondadoOverlayEntry, _ZIP_BOUND_FIELDS
       from .matcher import build_pipeline_condado_list, llm_output_to_overlay
       from .cache import cache_key, cache_get, cache_put, PROMPT_VERSION
       from .runner import start_research, get_stream, stop_research, _RUN_QUEUES, _RUN_TASKS
       ```

    4. Create `backend/tests/integration/test_research_sse.py` with the 6 cases from <behavior>. Use httpx.AsyncClient or call start_research/get_stream/stop_research directly with mocked PROVIDERS.
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
    - `grep -n 'research_overlay.meta.json' backend/medieval_forge/services/research/runner.py` returns ≥1 match (BLOCKER 2 — meta sidecar)
    - `grep -nE '"provider":|"model":|"created_at":' backend/medieval_forge/services/research/runner.py` returns ≥3 matches (meta sidecar fields)
    - File `backend/tests/integration/test_research_sse.py` EXISTS with ≥6 test functions
    - `grep -n "test_research_overlay_meta_sidecar_written_with_provider_model_created_at" backend/tests/integration/test_research_sse.py` returns 1 match
    - `cd backend && pytest tests/integration/test_research_sse.py -x -q` exits 0
  </acceptance_criteria>
  <verify>
    <automated>cd backend && pytest tests/integration/test_research_sse.py -x -q</automated>
  </verify>
  <done>SSE runner lands; WR-02 eviction tested; atomic overlay + meta sidecar both verified.</done>
</task>

<task type="auto">
  <name>Task 2: api/v3/research.py + api/v3/credentials.py + main.py mounts — overlay endpoint returns {exists, covered_condado_ids, meta} (BLOCKER 2 fix)</name>
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
    - .planning/phases/07-llm-research-as-opt-in-metadata-layer/07-UI-SPEC.md §Surface 2 (microcopy depends on meta field in overlay response)
    - backend/medieval_forge/services/research/runner.py (Task 1)
    - backend/medieval_forge/services/credential_store.py (Plan 01)
    - backend/medieval_forge/services/llm/__init__.py (PROVIDERS)
  </read_first>
  <action>
    1. Create `backend/medieval_forge/api/v3/research.py` with endpoints per D-09 + UI-SPEC. Standard endpoints: POST /start, GET /stream/{run_id}, POST /stop/{run_id}, GET /providers, GET /health (alias).

    **BLOCKER 2 fix — overlay endpoint shape:**

    ```python
    overlay_router = APIRouter(prefix="/v3/projects", tags=["research"])

    @overlay_router.get("/{project_id}/research/overlay")
    async def get_overlay(project_id: str):
        """Returns {exists, covered_condado_ids, meta} or {exists:false, covered_condado_ids:[], meta:null}.

        UI-SPEC §Surface 2 microcopy 'Última pesquisa: {provider} · {model} · {timestamp}'
        consumes the meta field. Meta = null when overlay missing OR meta sidecar
        missing (graceful degrade for hand-placed fixtures).
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
            # Trim to UI-bound subset (don't leak prompt_version internals to UI)
            meta = {
                "provider": raw_meta.get("provider"),
                "model": raw_meta.get("model"),
                "created_at": raw_meta.get("created_at"),
            }
        return {"exists": True, "covered_condado_ids": covered, "meta": meta}
    ```

    Note: the legacy "return raw JSON" variant is GONE. Plan 09a's `useResearchOverlay` consumes this shape directly.

    2. Create `backend/medieval_forge/api/v3/credentials.py` per former Plan 07 Task 3 (GET / POST /{provider} / DELETE /{provider} returning {configured: bool} only — no payload leakage).

    3. UPDATE `backend/medieval_forge/main.py` to mount both routers + overlay_router under `/api`.

    Verify final paths:
    - `/api/v3/research/start`, `/stream/{run_id}`, `/stop/{run_id}`, `/providers`, `/health`
    - `/api/v3/projects/{id}/research/overlay` (returns {exists, covered_condado_ids, meta})
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
    - File `backend/medieval_forge/api/v3/credentials.py` EXISTS
    - `grep -n "@router.post(\"/{provider}\")" backend/medieval_forge/api/v3/credentials.py` returns 1 match
    - `grep -n "@router.delete(\"/{provider}\")" backend/medieval_forge/api/v3/credentials.py` returns 1 match
    - `grep -nE "include_router\(research_router" backend/medieval_forge/main.py` returns 1 match
    - `grep -nE "include_router\(credentials_router" backend/medieval_forge/main.py` returns 1 match
    - `cd backend && python -c "from medieval_forge.main import app; routes = {r.path for r in app.routes}; assert '/api/v3/research/start' in routes; assert '/api/v3/credentials' in routes"` exits 0
    - Endpoint shape `GET /api/v3/research/providers` returns `[{provider_id, display_name, healthy, message, configured}]` with NO `payload` / `key` fields (T-07-07b-01)
  </acceptance_criteria>
  <verify>
    <automated>cd backend && python -c "from medieval_forge.main import app; routes = {r.path for r in app.routes}; assert '/api/v3/research/start' in routes; assert '/api/v3/credentials' in routes"</automated>
  </verify>
  <done>Routers mounted; overlay endpoint returns {exists, covered_condado_ids, meta} per BLOCKER 2; no credential payload leaks.</done>
</task>

</tasks>

<context_anchors>
- **D-08** (microcopy "Última pesquisa: {provider} · {model} · {timestamp}" — meta sidecar enables it)
- **D-09** (Radix Dialog + SSE)
- **D-11** (cache table consumed by runner)
- **Discretion #5** (SSE envelope mirrors generate.py)
- **RESEARCH §Pattern 6** (SSE runner)
- **RESEARCH §Pitfall 1** (atomic overlay write)
- **RESEARCH §Pitfall 7** (WR-02 finally eviction)
- **UI-SPEC §Surface 2** (microcopy)
- **Checker BLOCKER 2** (meta sidecar)
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
| T-07-07b-01 | Information Disclosure | /providers leaks credentials | mitigate | Endpoint returns `{provider_id, display_name, healthy, message, configured}` only — no payload/key. Acceptance: `grep -n "payload\|\"key\"" backend/medieval_forge/api/v3/research.py` returns 0 in providers builder. |
| T-07-07b-02 | Tampering | Path traversal via project_id | mitigate | `project_dir(project_id)` enforces UUID + path containment (Phase 03 paths.py). |
| T-07-07b-03 | Tampering | Torn overlay or meta write | mitigate | Both files use _write_json_atomic via tmp+replace. Test 5 + Test 6. |
| T-07-07b-04 | Tampering | LLM prompt injection via period_label | mitigate | Pydantic-validated `period: str`; literal-port prompt.py uses safe-format; retry loop schema-validates output. |
| T-07-07b-05 | DoS | SSE event flood | mitigate | 3s heartbeat (Ollama); Claude bounded by SDK. |
| T-07-07b-06 | DoS | Single-flight gate bypass | mitigate | _RUN_QUEUES check at start; 409 on concurrent /start. Test 2. |
| T-07-07b-07 | Tampering | Late subscriber to drained queue | mitigate | GET /stream returns 404 when no active run. |
| T-07-07b-08 | Information Disclosure | Meta sidecar leaks prompt_version internals | mitigate | Overlay endpoint trims meta to {provider, model, created_at} — does NOT echo prompt_version/country/period to UI consumers. |
| T-07-07b-09 | CSRF | SSE channel origin check | accept | Single-user local tool; CORS localhost-only. |

</threat_model>

<verification>
- `cd backend && pytest tests/integration/test_research_sse.py -x -q` exits 0
- `cd backend && python -c "from medieval_forge.main import app; routes = {r.path for r in app.routes}; assert '/api/v3/research/start' in routes"` exits 0
- `cd backend && python -c "from medieval_forge.services.research import start_research, get_stream, stop_research, _RUN_QUEUES, _RUN_TASKS"` exits 0
- `curl -s http://localhost:8000/api/v3/research/providers` returns JSON array with NO payload/key fields (manual UAT Plan 11)
- `curl -s http://localhost:8000/api/v3/projects/{id}/research/overlay` returns `{exists, covered_condado_ids, meta}` shape (manual UAT)
</verification>

<success_criteria>
- 6 research endpoints + 3 credentials endpoints reachable
- Overlay endpoint shape `{exists, covered_condado_ids, meta}` per BLOCKER 2
- Meta sidecar written atomically alongside overlay
- WR-02 eviction tested; cache-hit path short-circuits provider
</success_criteria>

<output>
After completion, create `.planning/phases/07-llm-research-as-opt-in-metadata-layer/07-07b-SUMMARY.md` per the standard template.
</output>
