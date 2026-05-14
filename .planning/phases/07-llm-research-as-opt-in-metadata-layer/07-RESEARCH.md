# Phase 07: LLM research as opt-in metadata layer - Research

**Researched:** 2026-05-13
**Domain:** Multi-provider LLM adapter layer (MVP 2 providers), DB-backed credential store, SSE research orchestration, non-destructive overlay merge, Phase 06 422 envelope frontend swap
**Confidence:** HIGH (verified against installed SDKs + commit `87f8aab~1` snapshots + live `claude auth status` + running Ollama instance)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**SC #3 interpretation + code reuse**
- **D-01:** Sidecar-first rebuild, not literal restore. ROADMAP "reused (moved into v3/)" is reinterpreted as "design reused, code rebuilt v3"; v1-archive 03-CONTEXT.md/03-RESEARCH.md are *templates*. The deleted files are NOT git-restored wholesale (PROJECT.md D-V3-04 prohibits namespace shims).
- **D-02:** 4 stateless artifacts literal-port from commit `87f8aab~1`:
  - `services/llm/prompt.py` (417 LOC) — `build_map_research_prompt`, rules, negative-example block, JSON-mode framing.
  - `services/llm/schemas.py` (255 LOC) — `ResearchResult`/`MapResearchResult` + `parse_research_json` (lenient).
  - `services/llm/retry.py` (65 LOC) — 3-retry loop with error-in-prompt feedback.
  - `services/llm/parse.py` (50 LOC) — fence-stripping wrapper around `schemas.parse_research_json`.
  All other v1 LLM code (provider adapters, runner, cache, credential_store, api/llm.py, api/auth.py, models.LLMCredential) is REWRITTEN under v3 patterns. Attribution comment at file head: `# Literal port from commit 87f8aab~1; see D-02 in 07-CONTEXT.md`.

**Overlay merge point**
- **D-03:** `research_overlay.json` is a per-project sidecar at `project_dir/research_overlay.json`, keyed by condado id → `{name, kingdom_owner, historical_notes}`. Pipeline output on disk stays raw with `Condado_001..N` placeholders (autogen) or curated slug names (Iberia). Unity contract stays at 12 files.
- **D-04:** Merge happens at TWO consumer points via a single pure function `services/research/overlay.py:merge_overlay(metadata: dict, overlay: dict) -> dict`:
  1. **Export zip** — `build_unity_zip` reads the overlay, merges in-memory just before serializing into the zip's `territory_metadata.json`. Disk output stays raw.
  2. **Frontend artifact endpoint** — `GET /api/v3/projects/{id}/artifacts/territory_metadata.json` applies the same `merge_overlay` on the fly when overlay exists. `useCanvasArtifacts` does NOT change. A separate `GET /api/v3/projects/{id}/research/overlay` exposes the raw overlay for debug.

**Provider scope + plugin registry**
- **D-05:** MVP day-1 providers = Claude + Ollama only. Plugin registry `services/llm/registry.py` is built to support N adapters but Phase 07 ships exactly 2. OpenAI + Gemini stay slot-ready; deferred to v3.1.
- **D-13:** Ollama defaults `qwen2.5:7b` primary, `llama3.1:8b` fallback, `format` blocking mode. Health check `GET localhost:11434/api/tags`.

**Auth + credential persistence**
- **D-06:** DB SQLite `llm_credentials` table (`provider_id TEXT PK, credential_type TEXT, payload JSON, created_at, updated_at`); inherits v1's persistence reversal (session-2026-04-21 line 66). DB lives at `~/.medieval-forge/medieval_forge.db`.
- **D-07:** Claude auth resolution chain (in order): (1) CLI piggyback → (2) DB → (3) `ANTHROPIC_API_KEY` env → (4) dialog paste (persists to DB). Ollama needs no credentials.

**UI / research dialog**
- **D-08:** Trigger lives in `InspectorSidebar.tsx` placeholder/project-summary mode (`selectedIds.length === 0`). Adds "Pesquisar metadados históricos" button + a "Pesquisa aplicada" badge once overlay exists.
- **D-09:** Radix `@radix-ui/themes` Dialog modal with form fields (País read-only from `region_key`, Período free text, Provider dropdown, Model free text, Force-refresh checkbox). On submit, POST `/api/v3/research/start` then open SSE on `/api/v3/research/stream/{run_id}`. Progress renders inside the modal as per-stage list with elapsed time. Cancel aborts stream + tells server to stop. On success: modal closes, `useCanvasArtifacts` invalidates, inspector re-renders with historical names.

**Phase 06 UI absorption**
- **D-10:** Phase 07 absorbs the deferred Phase 06 frontend swap: (i) swap Export button from v1 `/api/projects/{id}/export` to `POST /api/v3/projects/{id}/export`; (ii) render the structured 422 envelope (5 stable error codes — *but see RESEARCH §Phase 06 Absorption: validator actually emits 6 codes*) in a modal/toast with per-code PT-BR i18n. Optional "Validar antes de exportar" dry-run link.

**Cache**
- **D-11:** SQLite `research_cache` table `(cache_key TEXT PK, payload JSON, provider, model, created_at)`. Key = SHA-256(`country_qid|period_label|provider|model`). Re-ingestion does NOT invalidate (v1 D-24 carried). Force-refresh checkbox in dialog bypasses cache.

**Test pyramid + parity guarantee**
- **D-12:** Non-skippable parity assertion in `tests/parity/test_iberia_868_yaml.py` proves the pipeline WITHOUT any research overlay produces byte-identical output to Phase 06 baseline. Merge guarded by `if research_overlay_path.exists()` — absence is the default.

### Claude's Discretion

1. Credential payload encoding (plaintext vs base64 vs Fernet+OS-keyring).
2. CLI piggyback file path discovery + whether `claude auth status` CLI invocation exists.
3. Anthropic SDK version + streaming API.
4. Ollama Python client vs raw `httpx`.
5. SSE message format.
6. Migration mechanism (Alembic vs inline `CREATE TABLE IF NOT EXISTS`).
7. Pydantic schema field shape for territories.
8. Error-code i18n keys for Phase 06 envelope.
9. Dialog visual treatment.
10. Plugin registry import-time vs lazy.

### Deferred Ideas (OUT OF SCOPE)

- **OpenAI provider** — v3.1 backlog (plugin slot ready).
- **Gemini provider + Google OAuth installed-app flow** — v3.1.
- **Anthropic OAuth** — deferred indefinitely; CLI piggyback + API key cover all access.
- **Drag-and-drop condado re-assignment** — separate future phase.
- **Automatic provider fallback** — explicit user choice only.
- **Multi-turn agent-style refinement** — v1 rejected; stays out.
- **Token usage UI per project** — v1 deferred; still deferred.
- **Manual overlay editing via UI** — overlay is read-only; force-refresh is the regen path.
- **Region-key promotion of overlay to YAML default** — overlay is per-project, never global.
- **Re-ingestion invalidating cache** — v1 D-24 carried.
- **Per-project credential override** — credentials are global per-provider.
- **At-rest credential encryption** — v3.1 hardening item.
- **Streaming SSE for very large research outputs** — Iberia scale fits one response.
- **OpenAI/Gemini-specific JSON-mode normalization** — Phase 07 ships Claude (tool-use) + Ollama (format) only.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| V3-LLM-OPT-IN | Sidecar metadata; pipeline runs end-to-end with zero LLM calls; opt-in dialog populates `name`/`kingdom_owner`/`historical_notes` non-destructively | (1) `merge_overlay()` pure function (D-03/D-04) gated on `if research_overlay_path.exists()`; (2) Parity test `tests/parity/test_iberia_868_yaml.py` extended with zero-overlay byte-identical assertion (D-12); (3) Anthropic `0.97.0` `AsyncAnthropic.messages.stream` + `ollama 0.6.1 AsyncClient` for the 2 MVP providers; (4) 4 literal-port stateless artifacts from `87f8aab~1` (verified line counts); (5) DB-backed credential chain (`llm_credentials` table) + auth resolution order; (6) SSE pattern mirrored from `api/v3/generate.py`; (7) Radix Themes Dialog + `InspectorSidebar` placeholder-mode extension. |
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

The planner MUST honor every constraint below. Each is a hard rule already encoded in the v3 project — Phase 07 cannot violate any of them.

| Constraint | Source | Phase 07 implication |
|------------|--------|----------------------|
| Three-layer test pyramid: `tests/unit/` + `tests/parity/` + `tests/uat/playwright/` for any UI surface; ≥85% backend / ≥80% frontend coverage in `v3/` | CLAUDE.md §Conventions | Phase 07 ships unit tests for `overlay.merge`, `credential_store`, `cache`, schema/retry/parse; parity test extension; Playwright UAT for ResearchDialog + Export 422 envelope. |
| Atomic commits per task: `feat(07-NN): ...`, `chore(07-NN): ...`, `test(07-NN): ...` | CLAUDE.md §Conventions + v3 phase history | One commit per task. Literal-port commits use `chore(07-NN): literal port from 87f8aab~1` per D-02. |
| Determinism: `np.random.default_rng(42)` locked in `RegionConfig` | CLAUDE.md §Constraints | Research is non-geometric and orthogonal to the seed; D-12 enforces byte-determinism still passes WITHOUT overlay. Merge does NOT touch any geometric field. |
| 12-file Unity export contract (file 7 = `territory_metadata.json`) | CLAUDE.md §v3 Pipeline Contract | D-03 keeps the contract at exactly 12 files. `research_overlay.json` is a sidecar IN the project dir, NOT in the zip. MANIFEST gains `research_overlay_applied: bool` (schema_version bump 2→3). |
| Rule 4: `original_idx` in every condado | CLAUDE.md §Non-negotiable rules | `merge_overlay` MUST preserve `original_idx` on every touched condado. Validator (Phase 06) runs BEFORE overlay merge — verified by reading `services/export/zip.py:128` (validate_export → if pass → write zip with merge). |
| Rule 7: Unity uses `byOriginalIdx` as canonical key | CLAUDE.md §Non-negotiable rules | Overlay key = condado `id` (the writer-emitted `c[0]` slug like `"oviedo"` for Iberia or `"Condado_001"` for autogen) — same key the metadata uses. Overlay never touches `original_idx`. |
| No LLM-mandatory pipeline; LLM is opt-in metadata only | CLAUDE.md §What v3 explicitly is NOT | D-12 enforced via non-skippable parity assertion. |
| PT-BR UI strings, English code/commits/PRs | feedback-language-pt + user memory | Dialog labels, error envelope i18n, retry messages — all PT-BR. Code/comments/commit messages in English. |
| Tests with descriptive names + explicit numeric fixtures | feedback-tests-descriptive | All Phase 07 unit tests follow `test_merge_overlay_preserves_original_idx_when_condado_has_overlay_entry` style with explicit dict literals. |
| Server restart before UAT | feedback-server-restart-before-test | Every UAT step in Phase 07 (research dialog flow, Phase 06 button swap) must include `shutdown → build → restart → ask user to UAT in browser`. |
| Pipeline output stays byte-deterministic across re-runs | CLAUDE.md §Conventions | Merge is in-memory only at consumer boundaries. Pipeline never reads the overlay; pipeline never writes to it. Re-running `run_pipeline` produces byte-equal raw `territory_metadata.json`. |

---

## Summary

Phase 07 builds the opt-in LLM research layer that populates `name`, `kingdom_owner`, and `historical_notes` on the geometrically-fixed condados produced by the v3 pipeline, without ever blocking or modifying the 12-file Unity export. The phase delivers (a) a 2-provider plugin registry (Claude + Ollama) under `services/llm/`, (b) a research orchestrator + cache under `services/research/`, (c) a DB-backed credential store + auth chain, (d) two new FastAPI routers (`api/v3/research.py` + `api/v3/credentials.py`), (e) a Radix Dialog UI extension to `InspectorSidebar` placeholder mode + an SSE consumer hook, and (f) the deferred Phase 06 frontend swap (Export button + structured 422 envelope rendering).

The key architectural commitment is **non-destructive merge**: pipeline output on disk stays raw forever; merge happens twice (export-time and artifact-serving-time) via a single pure function `merge_overlay(metadata, overlay)` in `services/research/overlay.py`. This guarantees the Phase 06 byte-deterministic parity test stays green with zero LLM calls — verified by D-12's non-skippable parity assertion.

Four files (`prompt.py`, `schemas.py`, `retry.py`, `parse.py`, totaling 787 LOC verified at commit `87f8aab~1`) are literal-ported from v1 because they are pure/stateless and represent weeks of bug-fix iteration the team paid for during v1 Phase 03 (see session-2026-04-21-phase3-execute.md lessons table). All other v1 LLM code is rewritten under v3 patterns per D-01.

The literal-port `prompt.py` builds `build_map_research_prompt` which expects the geometric condado list (id + centroid) to be injected at call time — this is the v3 anchor that lets the LLM produce assignments by id rather than inventing slugs. The matcher + overlay-writer (`services/research/matcher.py`?, `overlay.py`) are net-new v3 code; v1's `territory_builder.py` (deleted, 292 LOC) is design template only.

**Primary recommendation:** Literal-port the 4 stateless artifacts in task-ordered sequence (`base.py` new → `schemas.py` port → `retry.py` port → `parse.py` port → `prompt.py` port → providers); use Alembic migration `0006_create_llm_credentials_and_research_cache.py` (matches established pattern); use `anthropic 0.97.0 AsyncAnthropic.messages.stream` with `tool_use`/`tool_choice` for guaranteed-JSON Claude output; use `ollama 0.6.1 AsyncClient.chat(format=schema.model_json_schema())` for structured-output Ollama; resolve Claude auth via `claude auth status` shell-out (verified to exist) and `~/.claude/.credentials.json` file-read as fallback; store credentials as plaintext JSON in `llm_credentials.payload` (matches v1 precedent + user pattern "mesmo modelo do gh/git", with OS-keyring escrow as v3.1 hardening); mirror `api/v3/generate.py`'s SSE envelope `{"event_type", "stage", "message", "progress"}` exactly so the frontend hook reuses the existing structured-payload parser.

---

## Standard Stack

### Core — Backend (Phase 07 net-new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `anthropic` | `>=0.94,<1.0` (pyproject) — installed `0.97.0` | Anthropic Claude API + streaming | Official SDK; `AsyncAnthropic.messages.stream` verified present in 0.97 [VERIFIED via `python -c "from anthropic import AsyncAnthropic; c=AsyncAnthropic(api_key='dummy'); print(hasattr(c.messages, 'stream'))"` → `True`]. No SDK bump needed (pyproject pin already accommodates). |
| `ollama` | `>=0.3,<1.0` (pyproject) — installed `0.6.1` | Ollama local LLM client | Official Python client. `AsyncClient.chat(format=...)` already used in v1 `ollama.py`; same usage carries to v3 [VERIFIED via `pip show ollama` → 0.6.1]. |

### Supporting — Backend (already in pyproject, reused)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx[http2]` | `>=0.27,<0.30` | Ollama health check via `GET localhost:11434/api/tags` if not using SDK's `client.list()` | SDK's `client.list()` is the primary path (v1 pattern); raw `httpx` is the backup if SDK ever becomes problematic. |
| `pydantic` | `>=2.7,<3.0` | Research schema validation + retry loop | Reused for `MapResearchResult` (literal port from `87f8aab~1:schemas.py`) AND for the new `ResearchOverlay` model. |
| SQLAlchemy + `aiosqlite` | already in deps | `llm_credentials` + `research_cache` tables | Same async pattern as `Project`. Tables created via Alembic migration 0006 (consistent with established 0001..0005 pattern). |
| `alembic` | `>=1.13,<2.0` | New migration `0006_create_llm_credentials_and_research_cache.py` | Established pattern; SQLite batch-mode (Phase 05 0005 is the template). |

### NOT to be installed (v3.1 deferral discipline)

| Library | Version | Why deferred |
|---------|---------|--------------|
| `openai` | already in pyproject (`>=1.30,<2.0`) but UNUSED in Phase 07 | D-05 keeps provider scope at Claude + Ollama. Dependency stays declared (Phase 03 purge removed code, not deps); provider adapter not shipped. |
| `google-genai` | already in pyproject (`>=1.0,<2.0`) but UNUSED | Same — slot-ready for v3.1. |
| `google-auth-oauthlib` | already in pyproject (`>=1.2,<2.0`) but UNUSED | OAuth not shipped (Gemini deferred). |
| `keyring` | NOT installed | At-rest credential encryption is v3.1 hardening; v1 plaintext precedent applies (Discretion #1). |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `ollama` Python SDK | Raw `httpx` to `localhost:11434/api/chat` | SDK is already declared in pyproject + v1 used it; dropping earns no benefit. Pick SDK (Discretion #4 resolved). |
| Alembic 0006 migration | Inline `CREATE TABLE IF NOT EXISTS` in `main.py` lifespan | Both already wired (lifespan does `Base.metadata.create_all`; Alembic owns versioned migrations 0001..0005). Established pattern is Alembic for new tables (Discretion #6 resolved). |
| `claude auth status` CLI shell-out | File-only read of `~/.claude/.credentials.json` | CLI gives a structured "logged in / not logged in / expired" verdict without parsing the file; falls back to file-read if `claude` binary missing (Discretion #2 resolved). |
| Anthropic `tool_use` JSON | Plain `messages.create` with prompt-side JSON instructions | `tool_use` + `tool_choice={"type":"tool","name":"submit_research"}` guarantees JSON; v1 pattern (verified in `87f8aab~1:claude.py`); production-proven. |
| Plugin registry import-time | Lazy on first `GET /providers` | Import-time was v1 pattern; Phase 07 has only 2 adapters — load cost is trivial; keep import-time for predictable startup behavior (Discretion #10 resolved). |

**Installation (Phase 07 — verification only, no new installs needed):**
```bash
# Already in pyproject.toml; verify resolved:
python -c "import anthropic; print(anthropic.__version__)"   # → 0.97.0
python -c "import ollama; from ollama import AsyncClient; print('ok')"  # → ok
```

**Version verification:** [VERIFIED]
- `anthropic 0.97.0` installed (PyPI latest: 0.102.0 as of 2026-05-13). `AsyncAnthropic.messages.stream` confirmed present.
- `ollama 0.6.1` installed (PyPI latest: 0.6.2). `AsyncClient` confirmed importable.
- `claude` CLI present at `/c/Users/veio_/.local/bin/claude` with subcommand `auth status` confirmed via `claude auth --help` [VERIFIED].
- `~/.claude/.credentials.json` present at 528 bytes; structure: `{"claudeAiOauth": {"accessToken", "refreshToken", "expiresAt", "scopes", "subscriptionType", "rateLimitTier"}, "organizationUuid"}` [VERIFIED via `python -c "import json,...; json.load(...)"`].
- Ollama server reachable at `localhost:11434`; installed models on this machine: `gemma4:26b`, `qwen2.5-coder:14b`, `deepseek-r1:14b` — **none match D-13 default `qwen2.5:7b`** [VERIFIED via `curl localhost:11434/api/tags`]. See §Open Questions Q3.

---

## Architecture Patterns

### Recommended Project Structure (new files only)

```
backend/medieval_forge/
├── services/
│   ├── llm/                              # 2-provider plugin registry
│   │   ├── __init__.py                   # exports PROVIDERS registry + LLMProvider type
│   │   ├── base.py                       # NEW: LLMProvider Protocol, AuthMethod union, HealthStatus
│   │   ├── registry.py                   # NEW: PROVIDERS: dict[str, LLMProvider]
│   │   ├── claude.py                     # NEW: AsyncAnthropic + tool_use + CLI piggyback
│   │   ├── ollama.py                     # NEW: AsyncClient + format=schema
│   │   ├── prompt.py                     # LITERAL PORT from 87f8aab~1 (417 LOC)
│   │   ├── schemas.py                    # LITERAL PORT from 87f8aab~1 (255 LOC)
│   │   ├── retry.py                      # LITERAL PORT from 87f8aab~1 (65 LOC)
│   │   └── parse.py                      # LITERAL PORT from 87f8aab~1 (50 LOC)
│   ├── research/                         # research orchestration + overlay merge
│   │   ├── __init__.py                   # exports merge_overlay + runner + cache
│   │   ├── runner.py                     # NEW: SSE orchestration (mirrors api/v3/generate.py pattern)
│   │   ├── cache.py                      # NEW: SQLite-backed cache (research_cache table)
│   │   ├── overlay.py                    # NEW: merge_overlay() pure function — D-03/D-04
│   │   └── matcher.py                    # NEW: pipeline-condado-id → LLM-output-condado-id matcher
│   └── credential_store.py               # NEW: DB-backed llm_credentials table + auth chain
├── api/v3/
│   ├── research.py                       # NEW: POST /start, GET /stream/{run_id}, GET /providers, GET /health, GET /overlay
│   └── credentials.py                    # NEW: GET /credentials, POST /credentials/{provider}, DELETE /credentials/{provider}
└── tests/
    ├── unit/
    │   ├── test_overlay_merge.py         # Wave 0: merge function with explicit numeric fixtures
    │   ├── test_credential_store.py      # Wave 0: DB persistence + auth chain resolution
    │   ├── test_llm_schemas.py           # Wave 0: parse_research_json lenient + strict paths
    │   ├── test_llm_retry.py             # Wave 0: 3-retry loop with appended error
    │   ├── test_llm_parse.py             # Wave 0: fence-stripping wrapper
    │   ├── test_research_cache.py        # Wave 0: cache key SHA-256 + hit/miss
    │   └── test_matcher.py               # Wave 0: condado id matching (Iberia curated + autogen Condado_NNN)
    ├── parity/
    │   └── test_iberia_868_yaml.py       # EXTENDED: zero-overlay byte-equal assertion (D-12)
    └── e2e/
        ├── test_research_overlay_iberia.py    # Run pipeline → write fixture overlay → export → assert merged names in zip
        ├── test_export_button_v3.py           # Playwright UAT for Phase 06 button swap + 422 envelope
        └── test_research_dialog.py            # Playwright UAT for ResearchDialog flow

alembic/versions/
└── 0006_create_llm_credentials_and_research_cache.py    # NEW

frontend/src/
├── components/research/
│   ├── ResearchDialog.tsx                # NEW: Radix Dialog modal (D-09)
│   ├── ProviderSelector.tsx              # NEW: Provider dropdown from /api/v3/research/providers
│   └── ResearchProgress.tsx              # NEW: SSE event list inside dialog
├── components/export/
│   └── ExportErrorDialog.tsx             # NEW (Phase 06 absorption): 422 envelope renderer
├── hooks/
│   └── useResearchStream.ts              # NEW: SSE consumer mirroring useRenderStream / api/v3/generate.py
├── i18n/
│   └── exportErrors.ts                   # NEW (Phase 06 absorption): 6 PT-BR strings keyed by error code
└── tests/uat/playwright/
    ├── research_dialog.spec.ts           # NEW
    └── export_v3_error_envelope.spec.ts  # NEW
```

### Pattern 1: `LLMProvider` Protocol (services/llm/base.py — NEW)

```python
# Source: v1 87f8aab~1:base.py design template; v3 simplified for 2-provider MVP.
from __future__ import annotations
import asyncio
from typing import Protocol, runtime_checkable
from pydantic import BaseModel

class HealthStatus(BaseModel):
    healthy: bool
    message: str = ""

class ApiKeyAuth(BaseModel):
    type: str = "api_key"
    env_var: str | None = None

class CliAuth(BaseModel):
    type: str = "cli"
    cli_command: str           # e.g., "claude"
    auth_file_path: str        # e.g., "~/.claude/.credentials.json"

class NoAuth(BaseModel):
    type: str = "none"

AuthMethod = ApiKeyAuth | CliAuth | NoAuth   # OAuthAuth dropped (v3.1)

@runtime_checkable
class LLMProvider(Protocol):
    provider_id: str
    display_name: str
    auth_methods: list[AuthMethod]

    async def health_check(self, credentials: dict | None) -> HealthStatus: ...
    async def research(
        self,
        prompt: str,
        schema: type[BaseModel],
        credentials: dict | None,
        queue: asyncio.Queue[str | None] | None,
    ) -> BaseModel: ...
```

### Pattern 2: Plugin Registry (services/llm/registry.py — NEW)

```python
# Source: D-04 / D-05 — exactly 2 adapters today; OpenAI/Gemini slot-ready for v3.1.
from .base import LLMProvider
from .claude import ClaudeProvider
from .ollama import OllamaProvider

PROVIDERS: dict[str, LLMProvider] = {
    "claude": ClaudeProvider(),
    "ollama": OllamaProvider(),
}
# To add a new provider in v3.1: create adapter file + add one line here.
```

### Pattern 3: Claude Provider — auth chain + tool_use (services/llm/claude.py — NEW)

```python
# Source: D-07 auth chain; v1 87f8aab~1:claude.py shape; pyrojects.toml anthropic 0.97.0 verified.
# v1 PT-BR retry messages preserved by literal-port retry.py (Tentativa N/M).
from __future__ import annotations
import asyncio, json, os, pathlib, subprocess, time
from anthropic import AsyncAnthropic
from pydantic import BaseModel
from .base import ApiKeyAuth, CliAuth, HealthStatus

SYSTEM_PROMPT = "You are a historical-research assistant. Return JSON via the submit_research tool."

def _read_claude_cli_token() -> str | None:
    """D-07 step 1: try `claude auth status` shell-out; fall back to direct file read.

    `claude auth status` returns 0 + 'You are logged in as ...' on success.
    Verified on Windows 2026-05-13: `/c/Users/veio_/.local/bin/claude` has subcommand
    `auth status`. File at `~/.claude/.credentials.json` carries OAuth tokens with
    expiresAt epoch-ms; consumer auth (claude.ai) may NOT grant API access — see
    Open Question Q1 for empirical risk.
    """
    # Try CLI first — cleanest, version-stable
    try:
        result = subprocess.run(
            ["claude", "auth", "status"],
            capture_output=True, text=True, timeout=3.0,
        )
        # CLI exits 0 if logged in; if exit non-zero, fall through to file read.
        if result.returncode != 0:
            return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass   # claude binary not installed — fall through to file read

    # File read (cross-platform):
    candidates = [
        pathlib.Path.home() / ".claude" / ".credentials.json",
        pathlib.Path(os.environ.get("APPDATA", "")) / "Claude" / "credentials.json",
        pathlib.Path(os.environ.get("XDG_CONFIG_HOME", str(pathlib.Path.home() / ".config")))
            / "claude" / "credentials.json",
    ]
    for path in candidates:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                token_data = data.get("claudeAiOauth", {})
                access_token = token_data.get("accessToken")
                expires_at_ms = token_data.get("expiresAt", 0)
                if access_token and expires_at_ms > time.time() * 1000:
                    return access_token
            except (json.JSONDecodeError, OSError):
                continue
    return None


class ClaudeProvider:
    provider_id = "claude"
    display_name = "Claude (Anthropic)"
    auth_methods = [
        CliAuth(cli_command="claude", auth_file_path="~/.claude/.credentials.json"),
        ApiKeyAuth(env_var="ANTHROPIC_API_KEY"),
        ApiKeyAuth(env_var=None),   # dialog paste; payload persists to DB
    ]

    def _resolve_key(self, db_payload: dict | None) -> str | None:
        """D-07 resolution order: (1) CLI → (2) DB → (3) env → (4) dialog (= db_payload after paste)."""
        cli_token = _read_claude_cli_token()
        if cli_token:
            return cli_token
        if db_payload and db_payload.get("key"):
            return db_payload["key"]
        env_key = os.getenv("ANTHROPIC_API_KEY")
        if env_key:
            return env_key
        return None

    async def health_check(self, credentials: dict | None) -> HealthStatus:
        key = self._resolve_key(credentials)
        if not key:
            return HealthStatus(healthy=False, message="No credentials (CLI/DB/env/dialog all empty)")
        return HealthStatus(healthy=True, message="Credentials present")

    async def research(self, prompt, schema, credentials, queue):
        key = self._resolve_key(credentials)
        if not key:
            raise ValueError("No Anthropic credentials available")
        client = AsyncAnthropic(api_key=key)
        async with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            tools=[{
                "name": "submit_research",
                "description": "Submit structured research result",
                "input_schema": schema.model_json_schema(),
            }],
            tool_choice={"type": "tool", "name": "submit_research"},
        ) as stream:
            async for text in stream.text_stream:
                if queue is not None and text:
                    await queue.put(f"data: {json.dumps({'event_type':'token','message':text})}\n\n")
            final = await stream.get_final_message()
        tool_block = next(b for b in final.content if getattr(b, "type", None) == "tool_use")
        return schema.model_validate(tool_block.input)
```

### Pattern 4: Ollama Provider — format=schema JSON enforcement (services/llm/ollama.py — NEW)

```python
# Source: v1 87f8aab~1:ollama.py; ollama 0.6.1 AsyncClient.chat(format=...) verified.
# D-13: qwen2.5:7b default, llama3.1:8b fallback. UI dropdown is populated by
# /api/v3/research/providers reading the local model list (see Open Question Q3).
from __future__ import annotations
import asyncio, json
from ollama import AsyncClient
from pydantic import BaseModel
from .base import HealthStatus, NoAuth

OLLAMA_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:7b"
FALLBACK_MODEL = "llama3.1:8b"


class OllamaProvider:
    provider_id = "ollama"
    display_name = "Ollama (local)"
    auth_methods = [NoAuth()]

    async def health_check(self, credentials: dict | None) -> HealthStatus:
        try:
            client = AsyncClient(host=OLLAMA_HOST)
            await asyncio.wait_for(client.list(), timeout=3.0)
            return HealthStatus(healthy=True, message=f"Reachable at {OLLAMA_HOST}")
        except asyncio.TimeoutError:
            return HealthStatus(healthy=False, message="Unreachable: timeout after 3s")
        except Exception as exc:
            return HealthStatus(healthy=False, message=f"Unreachable: {exc}")

    async def research(self, prompt, schema, credentials, queue):
        client = AsyncClient(host=OLLAMA_HOST)
        model = (credentials or {}).get("model") or DEFAULT_MODEL
        if queue is not None:
            await queue.put(f"data: {json.dumps({'event_type':'started','message':f'Aguardando Ollama ({model})...'})}\n\n")

        # Heartbeat task — blocking call may take 30-120s on local hw
        async def heartbeat() -> None:
            elapsed = 0
            while queue is not None:
                await asyncio.sleep(3.0)
                elapsed += 3
                await queue.put(f"data: {json.dumps({'event_type':'heartbeat','elapsed_s':elapsed})}\n\n")

        hb_task = asyncio.create_task(heartbeat()) if queue is not None else None
        try:
            response = await client.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                format=schema.model_json_schema(),
                stream=False,
            )
        finally:
            if hb_task is not None:
                hb_task.cancel()
                try:
                    await hb_task
                except (asyncio.CancelledError, Exception):
                    pass

        content = response["message"]["content"]
        # Lenient parser (literal-port schemas.parse_research_json) handles small-model
        # tendency to add extra top-level keys.
        from .schemas import parse_research_json, ResearchResult
        if schema is ResearchResult:
            return parse_research_json(content)
        return schema.model_validate_json(content)
```

### Pattern 5: Overlay merge function (services/research/overlay.py — NEW; CORE of D-03/D-04)

**Field semantics (resolves CONTEXT D-03 ambiguity):**
- `name`: historical display name in period vernacular (e.g., "Condado de Castela" for the territory whose pipeline-emitted `name` is `Condado_037`). Replaces `metadata.condados[i].name` directly.
- `kingdom_owner`: **historical ruling power at the chosen period** (e.g., "Reino de Asturias", "Califato de Córdoba"). This is **distinct from `condado.kingdom`** which is the pipeline-derived hierarchical kingdom-id assignment from the geometric clustering (`services/pipeline/export.py:60`). Both fields coexist on the merged condado — geometric `kingdom` stays as the cluster id (used by Unity rendering); LLM-derived `kingdom_owner` is a separate informational string (used by the Inspector and game-side historical context). Naming them differently is intentional.
- `historical_notes`: free-form PT-BR or English prose (cap at 2KB per condado; see Open Q4). Display-only; not consumed by Unity rendering.

**Q2 verification dependency (Wave 0 gate, NOT deferred):** Before this pattern lands, the planner runs a Wave 0 task that reads the Reconquista Unity C# loader (path enumerated in canonical_refs: `D:\Projetos_Jogo\Reconquista\Assets\Scripts\...`) and verifies whether it tolerates unknown JSON keys on condado entries. Two outcomes:
1. **Tolerant** (Newtonsoft default, `MissingMemberHandling.Ignore`): emit all 3 fields (`name`, `kingdom_owner`, `historical_notes`) into the zip's `territory_metadata.json` via merge.
2. **Strict** (`MissingMemberHandling.Error` or equivalent): merge writes ONLY `name` into the zip. `kingdom_owner` and `historical_notes` stay UI-served-only via the artifact endpoint (Pattern 12). The overlay file on disk still carries all 3.

The Wave 0 task report flips a single constant in `services/research/overlay.py:_ZIP_BOUND_FIELDS` (Tolerant: `{"name", "kingdom_owner", "historical_notes"}`; Strict: `{"name"}`). This MUST resolve before the merge function is wired into `build_unity_zip`.

```python
# Source: D-03 + D-04 + CLAUDE.md rule 4 (preserve original_idx).
# This is THE contract. Both export-zip and artifact-serving endpoints call this
# via the same merge_overlay() function — no duplicate merge logic anywhere.
from __future__ import annotations
import json
from pathlib import Path
from pydantic import BaseModel, ConfigDict, RootModel


class CondadoOverlayEntry(BaseModel):
    """Per-condado overlay payload — exactly 3 mergeable fields."""
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    kingdom_owner: str | None = None         # see field semantics above
    historical_notes: str | None = None      # capped at 2KB; see Open Q4


class ResearchOverlay(RootModel[dict[str, CondadoOverlayEntry]]):
    """Top-level overlay JSON contract: {[condado_id]: CondadoOverlayEntry, ...}.

    Keyed by `id` field of each condado in territory_metadata.json (the writer-emitted
    c[0] slug; e.g., 'oviedo' for Iberia, 'Condado_001' for autogen).

    RootModel because the JSON top-level is a flat dict, not an object with named
    fields. `ResearchOverlay.model_validate(parsed_json)` returns the validated
    wrapper; `.root` gives the inner dict.
    """


# Q2 Wave 0 gate flips this set; default = all 3 (tolerant Unity loader).
# If verification reports strict loader, change to frozenset({"name"}) ONLY
# (other 2 fields stay UI-served-only via api/v3/artifacts.py).
_ZIP_BOUND_FIELDS: frozenset[str] = frozenset({"name", "kingdom_owner", "historical_notes"})
_ALL_OVERLAY_FIELDS: frozenset[str] = frozenset({"name", "kingdom_owner", "historical_notes"})


def merge_overlay(
    metadata: dict,
    overlay: dict,
    allowed_fields: frozenset[str] = _ALL_OVERLAY_FIELDS,
) -> dict:
    """Pure function. Return a NEW dict with overlay fields applied to metadata.condados.

    INVARIANTS (enforced via unit tests):
    1. metadata is NOT mutated (defensive deepcopy at top).
    2. Every condado.original_idx is preserved unchanged (CLAUDE.md rule 4).
    3. Every condado.pixel_center / pixel_count / lon / lat / duchy / kingdom is preserved.
    4. Only fields in `allowed_fields` (subset of name/kingdom_owner/historical_notes) may change.
    5. If overlay has a condado_id NOT present in metadata.condados, it is SILENTLY IGNORED
       (re-keyed overlay survives pipeline re-run with different territory set; non-destructive principle).
    6. Baronies are untouched (overlay does NOT key by barony).

    Args:
        metadata: parsed territory_metadata.json dict.
        overlay: parsed + validated research_overlay.json dict (see load_overlay_if_exists);
            shape {[condado_id]: {name?, kingdom_owner?, historical_notes?}}.
        allowed_fields: which overlay fields actually write into the merged dict. Defaults to
            all 3 fields (used by the artifact endpoint, Pattern 12). build_unity_zip
            (Pattern 11) passes _ZIP_BOUND_FIELDS which Q2 Wave 0 verification controls
            (strict Unity loader -> frozenset({"name"}) only).

    Returns:
        New dict identical to `metadata` except condados[*] may have overlay fields applied.
    """
    import copy
    merged = copy.deepcopy(metadata)
    for condado in merged["condados"]:
        entry = overlay.get(condado["id"])
        if entry is None:
            continue
        if "name" in allowed_fields and entry.get("name"):
            condado["name"] = entry["name"]
        if "kingdom_owner" in allowed_fields and entry.get("kingdom_owner"):
            condado["kingdom_owner"] = entry["kingdom_owner"]      # historical ruling power
        if "historical_notes" in allowed_fields and entry.get("historical_notes"):
            condado["historical_notes"] = entry["historical_notes"]
    return merged


def load_overlay_if_exists(overlay_path: Path) -> dict | None:
    """Return parsed + Pydantic-validated overlay dict, or None if file absent.

    Guards D-12 zero-LLM parity (absent file -> None -> merge skipped).
    Defense-in-depth: validates via ResearchOverlay before returning so a corrupted
    or version-drifted overlay file fails loudly with ValidationError at load time
    instead of producing silently-wrong merged output downstream.

    Returns a dict[str, dict] (the inner shape after .model_dump()) so callers don't
    need to know about RootModel internals.
    """
    if not overlay_path.exists():
        return None
    raw = json.loads(overlay_path.read_text(encoding="utf-8"))
    validated = ResearchOverlay.model_validate(raw)
    # .root is the inner dict[str, CondadoOverlayEntry]; .model_dump() yields plain dict.
    return {k: v.model_dump(exclude_none=False) for k, v in validated.root.items()}
```

**Note on schemas.py extra='forbid' compatibility:** `TerritoryMetadataSchema` (Phase 06 `services/export/schemas.py:97`) already has `model_config = ConfigDict(extra="forbid")`. Adding `kingdom_owner` and `historical_notes` to condados WILL fail that schema. **The planner MUST extend `CondadoEntrySchema`** with `kingdom_owner: str | None = None` and `historical_notes: str | None = None` so the merge output still validates. Alternatively, run merge AFTER validation in `build_unity_zip`. Recommend: extend the schema (forward-compatible; v3.1 reads them too).

### Pattern 6: SSE Research Runner (services/research/runner.py — NEW)

Mirror `api/v3/generate.py` exactly. Key elements verified in that file:
- `asyncio.Queue[str | None]` with `None` sentinel termination.
- `StreamingResponse` with `media_type="text/event-stream"`.
- SSE payload envelope: `f"data: {json.dumps({'event_type', 'stage', 'message', 'progress'})}\n\n"` — see `api/v3/generate.py:54-63`.
- Per-(project_id) `_RUN_QUEUES` map + 409 if alive (single-flight gate).
- `finally:` block evicts `_RUN_QUEUES.pop(project_id, None)` + `_RUN_TASKS.pop(project_id, None)` to prevent late-subscriber hang (WR-02 fix carried).
- Producer task wrapped in `try/except/finally` always puts `None` before evictions.

Research-specific differences:
- 4 conceptual stages: `kingdoms → duchies → condados → baronies` (one SSE event per stage, plus per-token streaming inside Claude provider, plus heartbeat for Ollama).
- Producer reads pipeline's `territory_metadata.json` to extract the condado list to inject into the prompt (the matcher anchor — see Pattern 7).
- Producer checks cache before calling provider; cache hit short-circuits to `done` event with `cached: true`.
- On success: write `project_dir/research_overlay.json` atomically (`tmp.write_text() + tmp.replace(...)` — reuse `paths._write_geojson_atomic` pattern at `paths.py:69`).

### Pattern 7: Matcher — LLM output → pipeline condado id (services/research/matcher.py — NEW)

```python
# The LLM is prompted with the pipeline's geometric condado list:
#   [{"id": "oviedo", "lon": -5.84, "lat": 43.36}, {"id": "braga", "lon": -8.43, "lat": 41.55}, ...]
# and is REQUIRED to return assignments keyed by exactly those ids.
#
# v1 strategy (territory_builder.py, 292 LOC, deleted in 87f8aab) embedded fuzzy matching
# on names — that approach was prone to drift. v3 uses ID-by-construction: the LLM cannot
# return an unknown id (retry loop catches it via the literal-port retry.py).
#
# For autogen regions (France, England, future toy maps), the pipeline-emitted ids are
# `Condado_001..N` — the LLM still gets the list, just with placeholder ids; output entries
# carry historically-attested NAMES that the merge applies as `metadata.condados[i].name`.

from __future__ import annotations
from pydantic import ValidationError

def build_pipeline_condado_list(metadata: dict) -> list[dict]:
    """Extract {id, lon, lat} per condado for prompt injection.

    The LLM prompt template (prompt.py:build_map_research_prompt) expects this list to be
    inlined as the source of truth. The LLM must NOT invent condado ids — it must use these.
    """
    return [
        {"id": c["id"], "lon": c["lon"], "lat": c["lat"]}
        for c in metadata["condados"]
    ]


def llm_output_to_overlay(
    llm_result: dict,
    pipeline_condado_ids: set[str],
) -> dict:
    """Convert validated LLM result into research_overlay.json shape.

    Drops any LLM-output condado id NOT in pipeline_condado_ids (defensive — retry loop
    should have prevented this via schema, but belt-and-braces).
    Maps kingdoms→ to per-condado `kingdom_owner` string via duchy.kingdom_id lookup.
    Concatenates inheritable fields into historical_notes (TBD — planner decides shape;
    initial pass can leave historical_notes empty and only fill name + kingdom_owner).

    Returns:
        dict[str, {name, kingdom_owner, historical_notes}] suitable for merge_overlay().
    """
    # ... planner fills in based on MapResearchResult shape from schemas.py literal port
```

### Pattern 8: Credential store + auth chain (services/credential_store.py — NEW)

```python
# Source: D-06 + D-07 + session-2026-04-21 line 66 (v1 reversal rationale).
# Plaintext payload per Discretion #1 resolution (v1 precedent; OS-keyring is v3.1).
from __future__ import annotations
import json, os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import LLMCredential   # rewritten model, NOT git-restored (D-01)


async def get_credentials(session: AsyncSession, provider_id: str) -> dict | None:
    """Read credentials from DB. Returns None if not stored.

    NB: This is one link in the chain. For Claude, the full chain (D-07) is composed in
    services/llm/claude.py:_resolve_key — DB is step 2 of 4.
    """
    row = await session.scalar(
        select(LLMCredential).where(LLMCredential.provider_id == provider_id)
    )
    if row is None:
        return None
    return json.loads(row.payload) if isinstance(row.payload, str) else row.payload


async def store_credentials(session: AsyncSession, provider_id: str, payload: dict) -> None:
    """Upsert credentials. Payload stored as plaintext JSON per Discretion #1."""
    existing = await session.scalar(
        select(LLMCredential).where(LLMCredential.provider_id == provider_id)
    )
    if existing:
        existing.payload = payload
        existing.credential_type = payload.get("type", "api_key")
    else:
        session.add(LLMCredential(
            provider_id=provider_id,
            credential_type=payload.get("type", "api_key"),
            payload=payload,
        ))
    await session.commit()


async def clear_credentials(session: AsyncSession, provider_id: str) -> None:
    row = await session.scalar(
        select(LLMCredential).where(LLMCredential.provider_id == provider_id)
    )
    if row:
        await session.delete(row)
        await session.commit()
```

### Pattern 9: SQLAlchemy models (extend models.py — NEW models)

```python
# v3 rewrite of v1 LLMCredential + ResearchCache; NOT git-restored from 87f8aab~1.
from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from .models import Base, _utcnow


class LLMCredential(Base):
    __tablename__ = "llm_credentials"
    provider_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    credential_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )


class ResearchCache(Base):
    __tablename__ = "research_cache"
    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)   # SHA-256 hex
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
```

### Pattern 10: Alembic migration (0006_create_llm_credentials_and_research_cache.py — NEW)

Match the 0005 pattern (SQLite batch-mode). Idempotent `Base.metadata.create_all` in `main.py` lifespan will ALSO create these tables on fresh DB — both paths converge.

```python
revision = "0006"
down_revision = "0005"

def upgrade() -> None:
    op.create_table(
        "llm_credentials",
        sa.Column("provider_id", sa.String(50), primary_key=True),
        sa.Column("credential_type", sa.String(50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "research_cache",
        sa.Column("cache_key", sa.String(64), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("research_cache")
    op.drop_table("llm_credentials")
```

### Pattern 11: build_unity_zip merge integration (services/export/zip.py — MODIFY)

Insertion point: between line 128 (`report, sha256_by_file = validate_export(...)`) and the manifest-writing block at line 144. The merge runs AFTER validation passes — that order means the validator sees raw geometric output (which is what it must validate); merge then applies non-destructive metadata before the zip is assembled.

```python
# AFTER (Phase 07 modification — pseudocode for planner reference):
report, sha256_by_file = validate_export(generated, cfg)
if not report.passed:
    raise ValidationFailedError(report)

# NEW (Phase 07 D-03/D-04): load overlay and prepare merged metadata for the zip.
# CRITICAL: merge_overlay() is the SINGLE source of truth -- ALSO called from
# api/v3/artifacts.py (Pattern 12). The two callers MUST stay in sync; no duplicate
# merge logic anywhere. If you find yourself writing a second merge, stop and route
# through services/research/overlay.merge_overlay() instead.
from ..research.overlay import merge_overlay, load_overlay_if_exists, _ZIP_BOUND_FIELDS
overlay_path = project_dir(project_id) / "research_overlay.json"
overlay = load_overlay_if_exists(overlay_path)
research_overlay_applied = overlay is not None

# When assembling territory_metadata.json into the zip:
if fname == "territory_metadata.json" and overlay is not None:
    raw_metadata = json.loads((generated / fname).read_bytes())
    # _ZIP_BOUND_FIELDS is set by Q2 Wave 0 verification:
    #   Tolerant Unity loader -> {"name", "kingdom_owner", "historical_notes"}
    #   Strict Unity loader   -> {"name"}  (other 2 are UI-served-only via Pattern 12)
    merged_metadata = merge_overlay(raw_metadata, overlay, allowed_fields=_ZIP_BOUND_FIELDS)
    data = json.dumps(merged_metadata).encode("utf-8")
    sha = hashlib.sha256(data).hexdigest()   # rehash because content changed
else:
    # ... existing code path

# Pattern 12 (artifact endpoint) calls the same merge_overlay() WITHOUT allowed_fields
# (default = all 3 fields), since the UI always sees the full overlay regardless of
# the Unity loader's tolerance.
```

The MANIFEST gains `research_overlay_applied: bool` (D-CONTEXT.md `canonical_refs` — "MANIFEST schema bump v2→v3"). Bump `MANIFEST_SCHEMA_VERSION: 2 → 3` in `services/export/schemas.py:15`.

### Pattern 12: Merged-on-the-fly artifact endpoint (api/v3/artifacts.py — MODIFY)

Current `artifacts.py:serve_artifact` returns a raw `FileResponse`. Phase 07 special-cases `territory_metadata.json` when an overlay exists:

```python
@router.get("/{project_id}/artifacts/{file_name}")
async def serve_artifact(project_id: str, file_name: str):
    # ... existing UUID + allowlist + path containment checks
    if file_name == "territory_metadata.json":
        overlay_path = project_dir(project_id) / "research_overlay.json"
        if overlay_path.exists():
            from ...services.research.overlay import merge_overlay
            raw = json.loads(target.read_bytes())
            overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
            return JSONResponse(content=merge_overlay(raw, overlay))
    return FileResponse(target, ...)
```

A separate `GET /api/v3/projects/{id}/research/overlay` exposes the raw overlay for debug (returns 404 if absent).

### Pattern 13: ResearchDialog placement (frontend — D-08 + D-09)

In `frontend/src/components/canvas/InspectorSidebar.tsx`, extend the `selectedIds.length === 0` branch (lines 187-193). Add:
- "Pesquisar metadados históricos" button (Radix `Button color="blue"`) that opens `ResearchDialog`.
- "Pesquisa aplicada" badge (Radix `Badge color="green"`) when overlay exists (fetched via `GET /api/v3/projects/{id}/research/overlay` → 200/404 indicates presence).

In the condado-detail branch (lines 243+), add the same green "Pesquisa aplicada" badge when the selected condado has an overlay entry — clicking the badge re-opens the dialog with force-refresh checked.

### Pattern 14: useResearchStream hook (frontend — NEW)

Mirror the existing SSE consumer pattern. Look at `useRenderStream` / `useIngestStream` (existing hooks under `frontend/src/hooks/`) for the exact EventSource pattern. Wrap the SSE loop in `useUIStore.temporal.pause() / .resume()` per CLAUDE.md "What v3 is NOT" zundo discipline (no compound undo pollution from streaming events).

### Anti-Patterns to Avoid

- **Never write to `project_dir/output/territory_metadata.json`** with merged content. Pipeline output stays raw; D-12 parity test depends on this.
- **Never call `claude` CLI with arbitrary arguments inside the running server.** The shell-out is restricted to `claude auth status` (3-second timeout) only. Larger shell-outs reintroduce supply-chain risk.
- **Never trust LLM-returned condado ids without cross-checking against `pipeline_condado_ids`.** Even with `tool_use` schema enforcement, defensive `llm_output_to_overlay()` must drop unknown ids.
- **Never store the OAuth `accessToken` as the dialog-pasted credential** — they have different lifecycle (CLI token auto-refreshes via `claude` daemon; dialog token is static). Keep them in separate auth-chain rungs.
- **Never enrich `historical_notes` from arbitrary LLM prose without size cap.** Cap at e.g. 2KB per condado to prevent runaway response sizes from inflating `research_overlay.json`.
- **Never override `Konva.clearCache()` discipline** when overlay-merged metadata triggers an inspector re-render. The InspectorSidebar re-render is React-only (no Konva mutation), so the existing `useCanvasArtifacts` invalidation pattern is sufficient.
- **Never split the 4 literal-port files into separate commits** without preserving dependency order: `base.py` (new) → `schemas.py` → `retry.py` (depends on `.base`) → `parse.py` (depends on `.schemas`) → `prompt.py` (pure, standalone). Order verified by `grep "from \\.base\\|from \\.schemas" 87f8aab~1:retry.py 87f8aab~1:parse.py`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Anthropic streaming + JSON-mode | Custom prompt parsing for JSON | `anthropic 0.97 AsyncAnthropic.messages.stream` + `tool_use` with `tool_choice={"type":"tool","name":"submit_research"}` | SDK guarantees JSON via the tool_use API; verified in v1 87f8aab~1:claude.py for 6+ months of production. |
| Ollama JSON-mode | Manual response parsing | `ollama 0.6.1 AsyncClient.chat(format=schema.model_json_schema())` | SDK's `format` parameter accepts a JSON schema dict (verified in v1 ollama.py); local models follow the schema constraint more reliably. |
| 3-retry validation loop with error-in-prompt | Custom retry orchestration | `services/llm/retry.py` literal port from `87f8aab~1` (65 LOC) | Weeks of bug-fix iteration baked in; PT-BR retry messages preserved for end-user visibility (Tentativa N/M). |
| Lenient JSON parser for small local models | Custom regex extraction | `services/llm/schemas.py:parse_research_json` literal port (handles extra top-level keys like "regions"/"historical_names"; documented in `87f8aab~1` comments) | Small models (qwen2.5:7b) routinely add extra keys; lenient parser strips them while preserving strict-mode rejection signal. |
| Markdown-fence stripping for pasted LLM output | Custom fence regex | `services/llm/parse.py` literal port (50 LOC) | Handles ```json fences from web UIs (Claude.ai, ChatGPT, Gemini web). |
| Pydantic JSON schema for LLM tool definition | Hand-written JSON schema dict | `schema.model_json_schema()` | Stays in sync with Pydantic class; mistakes caught at validate-time, not at LLM-call-time. |
| SSE producer/consumer plumbing | New SSE framework | Mirror `api/v3/generate.py` (`_RUN_QUEUES` + `asyncio.Queue` + `None` sentinel + `StreamingResponse`) | Single-flight gating + WR-02 finally-block eviction pattern already production-hardened in Phase 04.1. |
| DB migration for new tables | Inline `CREATE TABLE IF NOT EXISTS` in lifespan | Alembic migration `0006_create_llm_credentials_and_research_cache.py` (mirrors `0005` SQLite batch-mode pattern) | 5 migrations already wired; consistency matters. `Base.metadata.create_all` ALSO creates them — both paths converge. |
| Overlay merge ordering vs schema validation | Merge before validate, then validate merged | Validate raw geometric output FIRST, then merge for the zip-write step only (Pattern 11) | Phase 06 validator catches drift in raw pipeline output; merging first would mask geometric regressions behind metadata changes. |
| Cross-platform Claude credential file discovery | Custom path enumeration | Try `claude auth status` shell-out FIRST (verified to exist with subcommand `status`); fall back to ordered candidate paths | CLI gives a stable "logged in / not logged in / expired" verdict without needing to parse file fields whose schema may change between Claude Code versions. |

**Key insight:** The literal-port + adapter strategy means Phase 07 ships ~787 LOC of production-hardened code (4 stateless artifacts) verbatim from `87f8aab~1`, plus ~600-800 LOC of net-new v3 code for the orchestration layer. Compare to "rewrite everything from scratch" which discards 4 phases of LLM-prompt iteration.

---

## Common Pitfalls

### Pitfall 1: Pipeline output drift via overlay
**What goes wrong:** Developer reads `project_dir/output/territory_metadata.json` from the merge endpoint, applies overlay, and writes it back to the same path.
**Why it happens:** "I want the canvas to show historical names" → reaches for the simplest fix → mutates raw pipeline output.
**How to avoid:** Merge ONLY at consumer boundaries (zip-write + artifact-endpoint response). Pipeline output on disk is read-only from research's perspective. D-12 parity test catches the regression but only on subsequent runs — better to enforce by code review.
**Warning signs:** Any commit in Phase 07 that writes to `output/territory_metadata.json`.

### Pitfall 2: Validator runs after merge, breaks Phase 06
**What goes wrong:** Developer puts `merge_overlay()` call before `validate_export()` in `build_unity_zip`, so validator sees merged metadata (which has `kingdom_owner` field not in the Phase 06 schema).
**Why it happens:** "Validate the final output" — natural ordering instinct.
**How to avoid:** Validator runs on raw pipeline output; merge happens between validation pass and zip assembly. Verified the correct order in Pattern 11 (line 128 → merge → line 144 manifest-write). Phase 06 `validator.py` is NOT modified.
**Warning signs:** Phase 06 parity test fails after Phase 07 lands while Phase 06 isolated test still passes.

### Pitfall 3: Iberia condado ids are slugs, not `Condado_NNN`
**What goes wrong:** Developer assumes pipeline ALWAYS emits `Condado_001..N` placeholders, builds matcher around regex parsing.
**Why it happens:** Phase 05 autogen branch emits placeholders; Iberia branch emits curated slugs like `oviedo`, `braga`. Documentation conflates them.
**How to avoid:** The matcher consumes whatever ids the pipeline writes (`metadata.condados[i].id`). For Iberia those are slugs from `territory_data_v3.py`; for autogen they are `Condado_001..N`. The LLM is given the actual list — no regex. Verified by reading `services/pipeline/export.py:50-71` (`c[0]` is the source).
**Warning signs:** `test_iberia_868_yaml.py` shows overlay applied to 0 condados despite a valid research run.

### Pitfall 4: Claude CLI token is consumer-OAuth, not API
**What goes wrong:** `~/.claude/.credentials.json` provides `claudeAiOauth.accessToken` for the claude.ai consumer subscription (`subscriptionType: max`, `authMethod: claude.ai`); using it as an Anthropic API bearer returns 401/403 because the consumer token does NOT grant API access.
**Why it happens:** Naming is misleading — the file IS in the "Claude" namespace. v1 hit this and the session notes (line 73) record the resolution: "Usuário precisa criar key API separada em console.anthropic.com". v1 RESEARCH flagged it as `[ASSUMED A1]` and never empirically resolved.
**How to avoid:** Try the OAuth bearer first (it works for users who used `claude auth login` against an API account, not claude.ai). On 401/403 from Anthropic's API, **silently degrade to the next chain link** (DB → env → dialog). Surface "CLI token rejected — falling back to API key" in the SSE stream as a debug event so the user sees what happened. See Open Question Q1.
**Warning signs:** Claude returns 401 on the first call while `claude auth status` exits 0.

### Pitfall 5: Ollama default model not installed
**What goes wrong:** D-13 locks `qwen2.5:7b` as the default. Dialog auto-fills the Model field. User clicks "Iniciar pesquisa" → Ollama returns 404 `model not found`.
**Why it happens:** Different users install different models. Verified on this machine: only `gemma4:26b`, `qwen2.5-coder:14b`, `deepseek-r1:14b` — D-13 default is absent.
**How to avoid:** `GET /api/v3/research/providers` enriches each provider with `available_models: list[str]` from `client.list()`. The dialog Model field is a dropdown populated by that list, with D-13 default ("qwen2.5:7b") shown only if it IS present; otherwise an info hint "Modelo padrão `qwen2.5:7b` não instalado — escolha um dos disponíveis ou execute `ollama pull qwen2.5:7b`". v1 fixed this same bug in commit `18901da` (session-2026-04-21 line 54).
**Warning signs:** "Ollama: qwen2.5:7b not found" error on first research run.

### Pitfall 6: Cache key collision across periods
**What goes wrong:** Cache key uses `period_label` as free text. Two projects with periods "868 AD" and "868" hash differently; the user expects them to hit the same cache.
**Why it happens:** D-11 says "country_qid|period_label|provider|model" — no normalization spec.
**How to avoid:** Lowercase + strip whitespace before hashing. Document the canonical form (e.g., `"q29|868 ad|claude|claude-sonnet-4-6"`). Unit-test the cache key derivation.
**Warning signs:** Two near-identical projects make duplicate LLM calls.

### Pitfall 7: SSE late-subscriber hangs (WR-02 territory carry)
**What goes wrong:** User opens ResearchDialog, the SSE connection drops momentarily, browser auto-reconnects to `/api/v3/research/stream/{run_id}` — and the queue has already been drained.
**Why it happens:** Producer's `finally` block evicts `_RUN_QUEUES[project_id]` after putting the `None` sentinel; late subscribers get 404.
**How to avoid:** Mirror Phase 04.1-01's WR-02 fix in `api/v3/generate.py:161-166` — eviction is in `finally`, sentinel goes in first, late subscribers receive 404 with a clear message ("no active research run; POST /research/start to begin"). This is intentional, not a bug.
**Warning signs:** Frontend stuck on "Pesquisando..." despite server having completed.

### Pitfall 8: Pydantic ConfigDict(extra='forbid') rejects overlay fields
**What goes wrong:** Phase 06 `services/export/schemas.py:CondadoEntrySchema` declares `model_config = ConfigDict(extra="forbid")`. Adding `kingdom_owner`/`historical_notes` via merge → schema validation REJECTS the merged metadata.
**Why it happens:** `extra='forbid'` is strict by design.
**How to avoid:** Extend `CondadoEntrySchema` (lines 65-76) with optional `kingdom_owner: str | None = None` and `historical_notes: str | None = None`. Both fields are forward-compatible (any consumer that doesn't know them ignores them; serialization order is deterministic via Pydantic). Alternative: run merge OUTSIDE the validator's purview (only at zip-write boundary). Recommend: extend the schema.
**Warning signs:** Validator passes on raw output; fails on merged output when planner wires merge into a schema-validated path.

### Pitfall 9: PT-BR retry message AND SSE envelope-shape mismatch in literal-port retry.py
**What goes wrong:** Literal port `87f8aab~1:retry.py:48` carries `f"data: Tentativa {attempt}/{max_retries}: ..."` (Portuguese raw SSE line) into the backend SSE stream. Two issues stack:
  1. PT-BR string in backend code (apparent English-code-convention violation).
  2. The literal port emits raw `data: ...\n\n` lines, NOT the v3 structured envelope `{event_type, stage, message, progress}` JSON-wrapped that `api/v3/generate.py:_emit` produces and `useResearchStream` will expect.
**Why it happens:** v1 had no JSON envelope yet; retry.py was the message author. v3 generate.py introduced the envelope after `87f8aab`.
**How to avoid:** Accept BOTH as documented exceptions. PT-BR convention applies (SSE events ARE de facto user-facing). For the envelope mismatch: keep the literal port unchanged (D-02 contract — `chore`, not `feat`). The frontend SSE handler in `useResearchStream.ts` MUST tolerate BOTH shapes: try `JSON.parse(eventData)` first; on parse error treat the raw text as `{event_type: "raw", message: <text>}`. Document the dual-shape parser in the hook. The planner SHOULD NOT rewrite retry.py to match the envelope.
**Warning signs:** Code review changes "Tentativa" -> "Attempt"; or planner "fixes" retry.py to use `json.dumps({...})` and breaks the literal-port guarantee.

---

## Code Examples

Verified patterns from official sources + this codebase.

### Example 1: SSE structured payload (mirror api/v3/generate.py)

```python
# Source: api/v3/generate.py:47-63 (verified 2026-05-13)
def _emit(queue, event_type, stage, message="", progress=None):
    payload = {
        "event_type": event_type,
        "stage": stage,
        "message": message,
        "progress": progress,
    }
    queue.put_nowait(f"data: {json.dumps(payload)}\n\n")
```

### Example 2: Cache key derivation (Pattern from D-11)

```python
# Source: D-11 + canonicalized per Pitfall 6.
import hashlib

def cache_key(country_qid: str, period_label: str, provider: str, model: str) -> str:
    canonical = f"{country_qid.lower()}|{period_label.strip().lower()}|{provider}|{model}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

### Example 3: Atomic overlay write (reuse paths._write_geojson_atomic pattern)

```python
# Source: services/paths.py:69-79 (verified 2026-05-13)
def write_overlay_atomic(overlay_path: Path, overlay: dict) -> None:
    tmp = overlay_path.with_suffix(overlay_path.suffix + ".tmp")
    tmp.write_text(json.dumps(overlay, indent=2), encoding="utf-8")
    tmp.replace(overlay_path)
```

### Example 4: 422 envelope renderer in PT-BR (frontend — Phase 06 absorption)

```typescript
// frontend/src/i18n/exportErrors.ts — 6 PT-BR strings keyed by stable error code.
// CONTEXT additional_context lists 5 codes; validator.py actually emits 6 (verified
// via grep: SCHEMA_INVALID + COLOR_COLLISION + OCEAN_LEAK + MISSING_ORIGINAL_IDX +
// TERRITORY_TOO_SMALL + PIXEL_CENTER_OUT_OF_RANGE). Cover all 6.
export const EXPORT_ERROR_PT_BR: Record<string, string> = {
  SCHEMA_INVALID: 'Arquivo JSON inválido — pipeline gerou conteúdo malformado',
  COLOR_COLLISION: 'Duas regiões compartilham a mesma cor — exportação inválida para o Unity',
  OCEAN_LEAK: 'Pixels de oceano contêm cor de território — vazamento de máscara',
  MISSING_ORIGINAL_IDX: 'Condado sem original_idx — o jogo não consegue identificá-lo',
  TERRITORY_TOO_SMALL: 'Território com menos de 200 pixels — abaixo do mínimo do contrato',
  PIXEL_CENTER_OUT_OF_RANGE: 'Coordenada de centro fora dos limites do mapa',
}
```

```tsx
// frontend/src/components/export/ExportErrorDialog.tsx — renders the D-08 envelope.
import { Dialog, Badge, Flex, Text, Button } from '@radix-ui/themes'
import { EXPORT_ERROR_PT_BR } from '../../i18n/exportErrors'

interface ValidationErrorEntry {
  code: string
  severity: 'error' | 'warning'
  file: string | null
  context: Record<string, unknown>
  message: string
}

interface ErrorEnvelope {
  detail: {
    summary: string
    errors: ValidationErrorEntry[]
    warnings: ValidationErrorEntry[]
  }
}

export function ExportErrorDialog({ envelope, onClose }: { envelope: ErrorEnvelope; onClose: () => void }) {
  const { summary, errors } = envelope.detail
  return (
    <Dialog.Root open onOpenChange={(o) => !o && onClose()}>
      <Dialog.Content>
        <Dialog.Title>Falha ao exportar</Dialog.Title>
        <Text size="2" color="gray">{summary}</Text>
        <Flex direction="column" gap="2" mt="3">
          {errors.map((e, i) => (
            <Flex key={i} gap="2" align="center">
              <Badge color="red" variant="soft">{e.code}</Badge>
              {e.file && <Text size="1" color="gray">{e.file}</Text>}
              <Text size="2">{EXPORT_ERROR_PT_BR[e.code] ?? e.message}</Text>
            </Flex>
          ))}
        </Flex>
        <Flex justify="end" mt="4">
          <Button onClick={onClose}>Fechar</Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  )
}
```

### Example 5: Export button swap

```typescript
// frontend/src/api/client.ts:172-193 — current useExport hook.
// PHASE 07 CHANGE: line 177 swaps `/api/projects/${projectId}/export` →
// `/api/v3/projects/${projectId}/export` and adds 422 envelope handling.
export function useExport(projectId: string | undefined) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const res = await fetch(`/api/v3/projects/${projectId}/export`, { method: 'POST' })
      if (res.status === 422) {
        const envelope = await res.json()
        throw new ExportValidationError(envelope)
      }
      if (!res.ok) throw new Error('EXPORT_FAILED')
      return res.json() as Promise<ExportResponse>
    },
    onSuccess: (data) => { /* unchanged download flow */ },
    onError: (err) => {
      if (err instanceof ExportValidationError) {
        // Surface via UI (modal/toast) — see ExportErrorDialog
      }
    },
  })
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| In-memory only credentials (v1 D-14) | DB-persisted `llm_credentials` (D-06) | v1 Phase 03 final week (commit `8b76e92`, 2026-04-21) | User-driven reversal; "mesmo modelo do gh/git" — Phase 07 inherits. |
| Hardcoded Ollama model | Auto-discovery via `client.list()` (v1 commit `18901da`) | v1 Phase 03 polish | Phase 07 carries forward; D-13 default shown only if installed. |
| OOB OAuth redirect | localhost redirect + PKCE (Google deprecated OOB 2022) | Pre-v3 | N/A for Phase 07 (Gemini deferred). |
| `google-generativeai` package | `google-genai` package | 2024 | N/A for Phase 07. |
| 4 providers shipped at once | 2 providers MVP (Claude + Ollama); slot-ready registry | v3 Phase 07 (D-05) | Frontier + zero-cost ends of spectrum cover all access patterns; OpenAI/Gemini follow when v3.1 prioritizes. |

**Deprecated/outdated within v3 history:**
- v1 `services/llm/*` (15 files): deleted in commit `87f8aab`. Phase 07 rebuilds 4 of those literally + 4 from scratch.
- v1 `services/research_runner.py`, `research_cache.py`, `credential_store.py`, `territory_builder.py`: deleted same commit. Phase 07 rebuilds all from scratch under v3 patterns.
- v1 `api/research.py`, `api/auth.py`, `api/llm.py`, `api/codex.py`, `api/edit.py`: deleted same commit. Phase 07 ships `api/v3/research.py` + `api/v3/credentials.py` only.
- v1 4-provider parity (OpenAI, Gemini, Claude, Ollama): contracts to 2 (Claude, Ollama) for v3 MVP.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong | Mitigation |
|---|-------|---------|---------------|------------|
| A1 | `~/.claude/.credentials.json` consumer-OAuth token (`authMethod: claude.ai`) MIGHT NOT work as an Anthropic API bearer | Pattern 3 / Pitfall 4 / Open Q1 | High — CLI piggyback is THE zero-setup affordance for D-07 | Try the token first; on 401/403, silently degrade to the next chain link (DB → env → dialog). Surface "CLI token rejected" as a debug SSE event. Wave 0 task: integration test that exercises the degrade path. |
| A2 | Matcher strategy = prompt-injection of pipeline's `condados[*].id` + `lon` + `lat` is sufficient (no fuzzy name match) | Pattern 7 | Medium — wrong shape could leak unknown ids into overlay | Belt-and-braces: `llm_output_to_overlay` drops any unknown id. Retry loop's appended-error-feedback steers the LLM to use only provided ids. v1 territory_builder (deleted, 292 LOC) used fuzzy name matching — v3 simpler approach is the natural progression. |
| A3 | `anthropic 0.97.0` `AsyncAnthropic.messages.stream` shape matches v1 87f8aab~1 usage (`stream.text_stream`, `await stream.get_final_message()`, `final.content` list with `tool_use` blocks) | Pattern 3 | Low — verified `hasattr(client.messages, 'stream') == True`; exact shape carried from v1's working code | If shape drifts, adjust to current SDK docs at https://github.com/anthropics/anthropic-sdk-python. |
| A4 | MANIFEST `schema_version` bump 2→3 is the right place to signal overlay applicability | Pattern 11 / CONTEXT canonical_refs | Low — internal contract; only Forge tooling consumes it | Document in `services/export/schemas.py:15` with comment "v3: added research_overlay_applied". |
| A5 | Pure `merge_overlay()` function is sufficient — no LRU cache needed for repeat artifact fetches | Pattern 5 | Low — deepcopy + dict iteration is microsecond-scale for ~91 condados | Profile if e2e latency becomes a concern; LRU on the endpoint side is a trivial follow-up. |
| A6 | The pipeline's `metadata.condados[i].id` is stable across re-runs (same project, same region_key, same seed) | Pattern 7 + D-12 | Low — Iberia parity test enforces byte-equal output across re-runs; ids cannot drift without breaking parity | D-12 already covers via byte-equal assertion. |
| A7 | Adding `kingdom_owner` and `historical_notes` to `CondadoEntrySchema` (extra='forbid') does NOT break Reconquista Unity loader | Pitfall 8 / Pattern 11 | Medium — game contract change | Unity loader reads keys it knows; ignores unknown keys per `byOriginalIdx` lookup (CLAUDE.md rule 7). Verify by reading Reconquista loader code; if loader uses strict schema, gate via UAT before merging. |
| A8 | Cache key normalization (lowercase + strip) is forward-compatible | Pitfall 6 | Low — pure function; deterministic | Unit-test the normalization across edge cases. |

---

## Open Questions

1. **Does the consumer-OAuth token from `~/.claude/.credentials.json` (authMethod: claude.ai) work as an Anthropic API bearer?**
   - What we know: Session-2026-04-21 line 73 records v1's empirical finding "Usuário precisa criar key API separada em console.anthropic.com / aistudio.google.com com billing" — consumer Pro tokens don't grant API access. `claude auth status` confirms `apiProvider: firstParty, authMethod: claude.ai, subscriptionType: max`.
   - What's unclear: Whether ANY Claude Code users have an API-account-backed CLI (i.e., `claude auth login` against an API key rather than claude.ai) — if so, their token IS API-bearer compatible.
   - Recommendation: Implement the chain with the degrade-on-401 fallback (Pattern 3). Document in dialog UX: "Configurar credenciais — Claude" sheet shows "CLI detectado (claude.ai) — pode ser rejeitado pela API; usa chave API ANTHROPIC_API_KEY se necessário." Wave 0 integration test exercises both the 401-degrade path and the success path (mocked).

2. **Will Reconquista Unity loader reject new keys (`kingdom_owner`, `historical_notes`) on condado entries? — WAVE 0 GATE, not deferred**
   - What we know: Unity loader reads `territory_metadata.json` and consumes `original_idx` + `name` (CLAUDE.md rule 7). The schema is JSON — loaders generally tolerate extra keys.
   - What's unclear: Whether the Unity loader uses a strict schema (e.g., Newtonsoft `MissingMemberHandling.Error`) that rejects unknown keys.
   - **Required action (Wave 0):** Before the `merge_overlay` task fires, the planner runs an explicit Wave 0 verification task that reads the Reconquista C# loader at `D:\Projetos_Jogo\Reconquista\Assets\Scripts\...` and reports tolerant-vs-strict in writing. The outcome flips `services/research/overlay.py:_ZIP_BOUND_FIELDS` (see Pattern 5 "Q2 verification dependency"). This MUST resolve before merge code is wired into `build_unity_zip` — discovering it during e2e testing would force a rewrite. Conservative fallback if verification is blocked: emit ONLY `name` in the zip; serve `kingdom_owner`/`historical_notes` via the artifact endpoint only (still satisfies SC #2 "territories show historical names instead of Condado_001").

3. **Should the Ollama model dropdown default to D-13 `qwen2.5:7b` even when not installed?**
   - What we know: Verified on this machine — only `gemma4:26b`, `qwen2.5-coder:14b`, `deepseek-r1:14b` installed. v1 commit `18901da` (session line 54) auto-discovered local models in the UI.
   - What's unclear: Whether the planner should pre-populate the dropdown with the D-13 default (potentially misleading) OR auto-discover-only (loses the "blessed" default signal).
   - Recommendation: Auto-discover via `client.list()`; if D-13 default is present, mark it "Recomendado"; if absent, surface a hint "Modelo padrão `qwen2.5:7b` não instalado — execute `ollama pull qwen2.5:7b` ou escolha um dos disponíveis". Honors D-13 while not breaking on real-world installs.

4. **What's the canonical schema for the `historical_notes` field?**
   - What we know: D-03 says "historical_notes" is one of the 3 mergeable fields. Length unbounded.
   - What's unclear: Whether to cap size, support markdown, etc.
   - Recommendation: Treat as plain string, cap at 2KB per condado (defensive against runaway LLM output inflating `research_overlay.json`). Display in Inspector as a collapsible `<details>` block (matches Phase 04.1 "Sobre o método" pattern at InspectorSidebar.tsx:163).

5. **Should the v1 `territory_builder.py` matcher logic be salvaged?**
   - What we know: 292 LOC, deleted in `87f8aab`, used fuzzy name matching. v3 simpler approach (ID-by-construction via prompt injection) is documented in Pattern 7.
   - What's unclear: Whether the simpler approach handles all edge cases v1 hit (e.g., LLM returning a typo'd id).
   - Recommendation: Don't salvage. The retry loop with appended error feedback (`87f8aab~1:retry.py`) already handles typo'd ids — the LLM gets "id 'oviedoo' not in provided list" and corrects on retry. If empirical Wave 4 testing shows >2/3 retries firing, revisit.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All backend | ✓ | (project-wide) | — |
| `anthropic` Python SDK | Claude provider | ✓ | 0.97.0 (pyproject `>=0.94,<1.0`; PyPI latest 0.102.0) | — |
| `ollama` Python SDK | Ollama provider | ✓ | 0.6.1 (pyproject `>=0.3,<1.0`; PyPI latest 0.6.2) | Raw `httpx` to `localhost:11434/api/chat` |
| `claude` CLI binary | D-07 CLI piggyback (step 1) | ✓ | Present at `/c/Users/veio_/.local/bin/claude` | File-read of `~/.claude/.credentials.json` (step 1b) |
| `claude auth status` subcommand | D-07 CLI piggyback (preferred check) | ✓ | Verified via `claude auth --help` (shows `status [options]`) | File-read of credentials JSON |
| `~/.claude/.credentials.json` | D-07 CLI piggyback (step 1 fallback) | ✓ | Present (528 bytes; valid token; consumer-OAuth — see Q1) | DB → env → dialog (chain steps 2-4) |
| Ollama server | Ollama provider | ✓ | Running (responds at `localhost:11434/api/tags`) | UI shows provider as `unhealthy` with tooltip "Inicia `ollama serve`..." (v1 pattern) |
| Ollama default model `qwen2.5:7b` | D-13 default | ✗ | Not on this machine | Auto-discover + surface install hint (Q3) |
| `alembic` | Migration 0006 | ✓ | `>=1.13,<2.0` (already wired; 5 migrations in repo) | `Base.metadata.create_all` lifespan path (also wired) |
| SQLite (via aiosqlite) | `llm_credentials` + `research_cache` tables | ✓ | (project-wide) | — |
| `@radix-ui/themes` 3.x Dialog | ResearchDialog (D-09) | ✓ | Already in use (InspectorSidebar, others) | — |
| TanStack Query v5 | Provider list query, credentials mutations | ✓ | Already in use (useCanvasArtifacts) | — |
| Existing `useUIStore` + zundo | Pause undo during SSE | ✓ | Already wired with `temporal.pause()/resume()` | — |
| Reconquista Unity loader source | Q2 verification | Unknown | At `D:\Projetos_Jogo\Reconquista\Assets\Scripts\...` | Conservative: emit only `name` in merge, skip new fields (still satisfies D-03 SC #2 — historical names shown) |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:**
- Ollama default model `qwen2.5:7b`: surface install hint in dialog; let user pick from installed models.
- Anthropic API account (vs claude.ai consumer): degrade chain; clear "credentials needed" message if all 4 chain steps fail.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Backend framework | pytest 8.x (already in `pyproject.toml [project.optional-dependencies] dev`); `pytest-asyncio` for SSE tests |
| Frontend framework | vitest 3.2.4 (already wired); Playwright (existing UAT suite under `frontend/tests/uat/playwright/`) |
| Backend config | `pyproject.toml [tool.pytest.ini_options]` (markers: `unit`, `parity`, `integration`) |
| Frontend config | `vite.config.ts` + `playwright.config.ts` (testDir includes `./tests`) |
| Quick run (backend) | `pytest backend/tests/unit/test_overlay_merge.py -x` |
| Quick run (frontend) | `npm test -- --run frontend/src/components/research` |
| Full backend | `pytest backend/tests/ -x` |
| Full frontend | `npm test` + `npm run test:uat` |
| Phase gate | All three green; parity 11/11 unchanged; new e2e gates pass |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | Surface |
|--------|----------|-----------|-------------------|---------|
| V3-LLM-OPT-IN | `merge_overlay()` preserves `original_idx` on every condado | unit | `pytest backend/tests/unit/test_overlay_merge.py::test_merge_overlay_preserves_original_idx_when_condado_has_overlay_entry -x` | `services/research/overlay.py` |
| V3-LLM-OPT-IN | `merge_overlay()` does NOT mutate the input metadata dict | unit | `pytest backend/tests/unit/test_overlay_merge.py::test_merge_overlay_returns_new_dict_input_unchanged -x` | `services/research/overlay.py` |
| V3-LLM-OPT-IN | Unknown condado_id in overlay is silently ignored | unit | `pytest backend/tests/unit/test_overlay_merge.py::test_merge_overlay_ignores_unknown_condado_id_in_overlay -x` | `services/research/overlay.py` |
| V3-LLM-OPT-IN | Pipeline runs end-to-end with zero LLM calls (no overlay exists) | parity | `pytest backend/tests/parity/test_iberia_868_yaml.py::test_iberia_868_yaml_byte_equal_without_overlay -x` | Pipeline + zip writer (D-12) |
| V3-LLM-OPT-IN | Iberia pipeline produces raw `Condado_001..N` names without research | parity | `pytest backend/tests/parity/test_iberia_868_yaml.py::test_iberia_868_raw_metadata_uses_pipeline_slugs -x` | Pipeline output |
| V3-LLM-OPT-IN | Research overlay applied to Iberia produces merged names in zip | e2e | `pytest backend/tests/e2e/test_research_overlay_iberia.py::test_iberia_overlay_yields_historical_names_in_zip -x` | `build_unity_zip` + merge_overlay |
| V3-LLM-OPT-IN | Frontend artifact endpoint serves merged metadata when overlay exists | e2e | `pytest backend/tests/e2e/test_research_overlay_iberia.py::test_artifact_endpoint_serves_merged_metadata -x` | `api/v3/artifacts.py` |
| V3-LLM-OPT-IN | DB-backed credentials persist across server restart | unit | `pytest backend/tests/unit/test_credential_store.py::test_credentials_survive_simulated_restart -x` | `services/credential_store.py` |
| V3-LLM-OPT-IN | Claude auth chain falls through CLI → DB → env → dialog | unit | `pytest backend/tests/unit/test_credential_store.py::test_claude_auth_chain_falls_through_when_cli_token_rejected_with_401 -x` | `services/llm/claude.py:_resolve_key` + 401 mock |
| V3-LLM-OPT-IN | SHA-256 cache key derivation is deterministic + canonical | unit | `pytest backend/tests/unit/test_research_cache.py::test_cache_key_sha256_normalizes_case_and_whitespace -x` | `services/research/cache.py` |
| V3-LLM-OPT-IN | Cache hit short-circuits LLM call | unit | `pytest backend/tests/unit/test_research_cache.py::test_cache_hit_returns_payload_without_calling_provider -x` | `services/research/runner.py` |
| V3-LLM-OPT-IN | Force-refresh checkbox bypasses cache | unit | `pytest backend/tests/unit/test_research_cache.py::test_force_refresh_overwrites_cache_entry_on_success -x` | `services/research/runner.py` |
| V3-LLM-OPT-IN | Literal-port `parse_research_json` handles small-model extra keys | unit | `pytest backend/tests/unit/test_llm_schemas.py::test_parse_research_json_strips_extra_top_level_keys -x` | `services/llm/schemas.py` |
| V3-LLM-OPT-IN | Literal-port `retry.py` retries 3x then raises ResearchValidationError | unit | `pytest backend/tests/unit/test_llm_retry.py::test_run_with_retry_raises_after_3_consecutive_validation_errors -x` | `services/llm/retry.py` |
| V3-LLM-OPT-IN | Literal-port `parse.py` strips markdown code fences | unit | `pytest backend/tests/unit/test_llm_parse.py::test_parse_research_json_strips_json_code_fences -x` | `services/llm/parse.py` |
| V3-LLM-OPT-IN | Matcher injects pipeline condado list into prompt | unit | `pytest backend/tests/unit/test_matcher.py::test_build_pipeline_condado_list_extracts_id_lon_lat_per_condado -x` | `services/research/matcher.py` |
| V3-LLM-OPT-IN | Matcher drops LLM-output id not in pipeline list | unit | `pytest backend/tests/unit/test_matcher.py::test_llm_output_to_overlay_drops_unknown_condado_ids -x` | `services/research/matcher.py` |
| V3-LLM-OPT-IN | Provider unhealthy → dialog disables radio | UAT | `npx playwright test frontend/tests/uat/playwright/research_dialog.spec.ts -g "ollama unhealthy"` | `ResearchDialog` |
| V3-LLM-OPT-IN | Research dialog SSE flow shows per-stage progress | UAT | `npx playwright test frontend/tests/uat/playwright/research_dialog.spec.ts -g "sse stages"` | `useResearchStream` + `ResearchProgress` |
| V3-LLM-OPT-IN | "Pesquisa aplicada" badge appears after research run | UAT | `npx playwright test frontend/tests/uat/playwright/research_dialog.spec.ts -g "badge appears"` | `InspectorSidebar` |
| V3-LLM-OPT-IN (Phase 06 absorption) | Export button calls v3 endpoint | UAT | `npx playwright test frontend/tests/uat/playwright/export_v3_error_envelope.spec.ts -g "happy path"` | `client.ts:useExport` |
| V3-LLM-OPT-IN (Phase 06 absorption) | 422 envelope renders PT-BR for each of 6 error codes | UAT | `npx playwright test frontend/tests/uat/playwright/export_v3_error_envelope.spec.ts -g "code"` | `ExportErrorDialog` + `i18n/exportErrors.ts` (6 codes × 1 test each) |
| V3-LLM-OPT-IN (Phase 06 absorption) | Dry-run preview shows report without zip download | UAT | `npx playwright test frontend/tests/uat/playwright/export_v3_error_envelope.spec.ts -g "dry run"` | `api/v3/export.py:dry_run=true` + `ExportErrorDialog` |

### Sampling Rate

- **Per task commit:** `pytest backend/tests/unit/test_<changed_module>.py -x` + `npm test -- --run <changed_dir>`
- **Per wave merge:** `pytest backend/tests/ -x` + `npm test`
- **Phase gate:** All three test layers green; parity 11/11 unchanged; new e2e + UAT gates pass; `/gsd-verify-work` checklist clean.

### Wave 0 Gaps

Files that MUST exist before any wave-1 task can be marked complete:

- [ ] `backend/tests/unit/test_overlay_merge.py` — covers `merge_overlay()` invariants (5 tests minimum: input not mutated, original_idx preserved, unknown id ignored, partial overlay applied, all 3 fields merge correctly)
- [ ] `backend/tests/unit/test_credential_store.py` — covers DB CRUD + auth chain (3 tests: store/get/delete; falls through chain on missing; 401-degrade integration)
- [ ] `backend/tests/unit/test_research_cache.py` — covers cache key + hit/miss/force-refresh (3 tests)
- [ ] `backend/tests/unit/test_llm_schemas.py` — covers literal-port `parse_research_json` lenient + strict paths (3 tests)
- [ ] `backend/tests/unit/test_llm_retry.py` — covers literal-port retry loop (2 tests: success on retry 2; raises after 3)
- [ ] `backend/tests/unit/test_llm_parse.py` — covers literal-port fence-stripping (2 tests: with fences, without)
- [ ] `backend/tests/unit/test_matcher.py` — covers prompt injection + unknown-id drop (3 tests)
- [ ] `backend/tests/e2e/test_research_overlay_iberia.py` — covers SC #2 (3 tests: zip merge, artifact-endpoint merge, no overlay = raw)
- [ ] `frontend/tests/uat/playwright/research_dialog.spec.ts` — covers SC #2 from UI side (3 scenarios)
- [ ] `frontend/tests/uat/playwright/export_v3_error_envelope.spec.ts` — covers Phase 06 absorption D-10 (6 codes + dry-run)
- [ ] No framework install needed — pytest, vitest, Playwright already wired across 4 phases.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | DB-backed credential store; auth resolution chain documented (D-07); CLI shell-out timeout-bounded (3s); OAuth token from `~/.claude/.credentials.json` validated for expiresAt before use |
| V3 Session Management | yes | Per-(project_id) SSE single-flight gate (mirrors `_RUN_QUEUES` pattern from `api/v3/generate.py`); WR-02 finally-block eviction prevents late-subscriber hang |
| V4 Access Control | no | Single-user local tool; no multi-user access (matches Phase 03 D-20 posture) |
| V5 Input Validation | yes | Pydantic `extra='forbid'` on `ResearchResult` (literal port); `extra='forbid'` on `ResearchOverlay`; condado_id whitelist check in `llm_output_to_overlay` (Pattern 7); period_label normalized before hash |
| V6 Cryptography | no | SHA-256 cache key via stdlib `hashlib`; no custom crypto; plaintext at-rest payload per Discretion #1 (v3.1 hardening: OS-keyring escrow) |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key leakage to frontend | Information Disclosure | Keys stay in DB (`llm_credentials`); `GET /api/v3/research/providers` only returns `configured: bool` + `healthy: bool`, never the payload |
| LLM prompt injection via region YAML | Tampering | Region YAML is `data/regions/<key>.yaml` checked into git; not user-uploadable. Prompt template (`prompt.py`) treats injected condado list as data, schema-validates output |
| LLM output schema bypass | Tampering | `model_config = ConfigDict(extra='forbid')` + 3-retry loop with appended error; lenient parser strips extras but still rejects malformed-shape output |
| Pipeline output drift via overlay | Tampering | D-12 parity test (byte-equal without overlay); merge is at consumer boundaries only; pipeline never reads overlay |
| Cache poisoning across providers | Tampering | Cache key includes `provider|model` — Claude and Ollama results never collide |
| CLI shell injection via credentials | Command Injection | `claude auth status` shell-out uses `subprocess.run([...], shell=False)` with hardcoded args; no user input flows to argv |
| SSE event flooding | DoS | Heartbeat is 3s-period (rate-limited by Ollama provider); per-token streaming is bounded by Claude SDK; queue is unbounded but producer exits via `None` sentinel on completion |
| Credential persistence on shared machine | Information Disclosure | DB lives at `~/.medieval-forge/medieval_forge.db` (user-scoped per `DATA_DIR` in `database.py:14`); plaintext payload is documented v3.1 hardening item |
| Path traversal via overlay file | Tampering | `project_dir(project_id)` enforces UUID + path containment per `services/paths.py:36-52`; overlay path derived from validated project_dir |

---

## Phase 06 Absorption (D-10)

### Scope verified against repo state

The Phase 06 endpoint is LIVE: `POST /api/v3/projects/{id}/export` (verified at `backend/medieval_forge/api/v3/export.py:39`). The v1 endpoint `api/export.py` has been DELETED (verified at `main.py:40` comment "v1 export_router REMOVED in Phase 06 Plan 03 (D-04)"). The frontend Export button still calls v1 via `frontend/src/api/client.ts:177` — confirmed broken by `grep`.

### Validator emits 6 stable codes, not 5

CONTEXT.md `additional_context` lists 5 codes (`COLOR_COLLISION`, `OCEAN_LEAK`, `MISSING_ORIGINAL_IDX`, `TERRITORY_TOO_SMALL`, `PIXEL_CENTER_OUT_OF_RANGE`). The actual validator (verified via `grep -rn "SCHEMA_INVALID\|COLOR_COLLISION\|..." backend/medieval_forge/services/export/validator.py`) emits **6 codes**: the 5 above PLUS `SCHEMA_INVALID` (verified at lines 139, 152, 192). The i18n keys file MUST cover all 6 — see Example 4 above for the PT-BR strings.

### Required swap

In `frontend/src/api/client.ts:172-193`:
- Line 177: `/api/projects/${projectId}/export` → `/api/v3/projects/${projectId}/export`.
- Replace `jsonFetch` with a custom `fetch` that branches on `res.status === 422`, parses the envelope, and throws a typed `ExportValidationError(envelope)`.
- `onError` handler surfaces the envelope via `ExportErrorDialog` (new component, see Example 4).

### Dry-run preview

Add a "Validar antes de exportar" link in `ExportErrorDialog` (or as a secondary button next to Export). On click, call `POST /api/v3/projects/${id}/export?dry_run=true` and render the same envelope renderer. The 200-passing case shows "Sem problemas — pronto para exportar"; the 422-failing case shows the same per-code list. Endpoint is already wired at `api/v3/export.py:78-105`.

### Status-state handling

`useExport` retains current download flow on 201. Status flips to `exported` on success (handled backend-side in `api/v3/export.py`). Frontend invalidates `['projects', projectId]` and `['projects']` queries.

### i18n keys

PT-BR strings keyed by code in `frontend/src/i18n/exportErrors.ts` (planner picks: there is currently NO `frontend/src/i18n/` directory — verified via `ls`). Each key is stable per D-08 of Phase 06 CONTEXT. See Example 4.

---

## Sources

### Primary (HIGH confidence)

- `backend/medieval_forge/api/v3/generate.py` — SSE producer/consumer pattern (verified 2026-05-13).
- `backend/medieval_forge/services/export/zip.py` — `build_unity_zip` extension point at line 128 / 144 (verified 2026-05-13).
- `backend/medieval_forge/services/export/schemas.py` — `MANIFEST_SCHEMA_VERSION = 2` bump target + `CondadoEntrySchema` extension target (verified 2026-05-13).
- `backend/medieval_forge/services/export/validator.py` — 6 stable error codes confirmed (verified via grep 2026-05-13).
- `backend/medieval_forge/services/paths.py` — `project_dir`, `ensure_project_dirs`, `_write_geojson_atomic` pattern (verified 2026-05-13).
- `backend/medieval_forge/services/pipeline/export.py:50-71` — condado id is `c[0]` slug; baronies use `condado_idx` (verified 2026-05-13).
- `backend/medieval_forge/database.py` + `alembic/versions/0001..0005_*.py` — established migration pattern (verified 2026-05-13).
- `backend/medieval_forge/main.py:22-30` — lifespan also runs `Base.metadata.create_all` (verified 2026-05-13).
- `frontend/src/components/canvas/InspectorSidebar.tsx` — placeholder mode at lines 187-193; barony detail extension pattern at lines 130-185 (verified 2026-05-13).
- `frontend/src/hooks/useCanvasArtifacts.ts` — consumer of `territory_metadata.json` URL (verified 2026-05-13).
- `frontend/src/api/client.ts:172-193` — Export button hook (verified to call v1 endpoint 2026-05-13).
- Commit `87f8aab` + `87f8aab~1` — verified line counts for 4 literal-port files: `prompt.py` 417, `schemas.py` 255, `retry.py` 65, `parse.py` 50.
- `~/.claude/.credentials.json` — file structure verified empirically (`{claudeAiOauth: {accessToken, refreshToken, expiresAt, ...}, organizationUuid}`) on Windows 2026-05-13.
- `claude auth status` subcommand presence verified via `claude auth --help` 2026-05-13.
- `localhost:11434/api/tags` — Ollama running with 3 local models (none matching D-13 default) on Windows 2026-05-13.
- `python -c "from anthropic import AsyncAnthropic; c=AsyncAnthropic(api_key='dummy'); print(hasattr(c.messages, 'stream'))"` → `True` (verified 2026-05-13).
- `inicio/licoes/territory_data_v3.py` — target hierarchy shape (kingdoms → duchies → condados → baronies); MapResearchResult mirrors this.
- `.planning/notes/session-2026-04-21-phase3-execute.md` line 66 — D-06 DB persistence reversal rationale (verified 2026-05-13).
- `.planning/notes/session-2026-04-21-phase3-execute.md` line 73 — consumer Pro token vs API key empirical finding (verified 2026-05-13).
- `.planning/v1-archive/phases/03-llm-research-integration/03-CONTEXT.md` + `03-RESEARCH.md` + `03-UI-SPEC.md` — design templates per D-01 (verified 2026-05-13).

### Secondary (MEDIUM confidence)

- `87f8aab~1:backend/medieval_forge/services/llm/claude.py` — v1 Claude provider shape (verified via `git show`).
- `87f8aab~1:backend/medieval_forge/services/llm/ollama.py` — v1 Ollama provider shape (verified via `git show`).
- v1 RESEARCH.md (commit-frozen) — confirms v1 SDK API shapes; assumes carried forward unchanged in 0.97.

### Tertiary (LOW confidence)

- Claude SDK `messages.stream` API ergonomics in 0.102+ (current installed 0.97 known-working; PyPI latest is 0.102 — not verified).
- Reconquista Unity loader strictness on unknown keys (Pitfall 8 / Q2) — [ASSUMED tolerant; verify via Wave 0 task].

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified against installed pyproject + PyPI; CLI present.
- Architecture: HIGH — mirrors existing `api/v3/generate.py` + `services/export/zip.py` patterns exactly; merge function is microscale pure Python.
- Auth chain (Claude): MEDIUM — CLI piggyback works for API-account-backed users; consumer-OAuth tokens may degrade (Q1 documented).
- Pitfalls: HIGH — most verified via codebase grep + v1 session notes.
- Phase 06 absorption: HIGH — endpoint code, error-code list, and frontend swap location all empirically verified.

**Research date:** 2026-05-13
**Valid until:** 2026-06-12 (30 days; SDK versions stable; CLI subcommand presence stable; rev v3.1 if Anthropic deprecates `messages.stream` or `tool_use`).
