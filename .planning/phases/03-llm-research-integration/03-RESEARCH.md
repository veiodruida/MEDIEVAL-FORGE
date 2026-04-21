# Phase 3: LLM Research Integration - Research

**Researched:** 2026-04-21
**Domain:** Multi-provider LLM adapter layer, Google OAuth, Claude CLI auth piggyback, SSE streaming, Pydantic schema validation, SQLite caching
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Provider architecture (plugin-based, extensible)**
- D-01: `services/llm/` package with `base.py`, `registry.py`, `claude.py`, `openai.py`, `gemini.py`, `ollama.py`
- D-02: Each provider implements `LLMProvider` Protocol: `provider_id`, `display_name`, `auth_methods`, `async health_check(credentials) -> HealthStatus`, `async research(prompt, schema, queue) -> BaseModel`
- D-03: `AuthMethod` tagged union: `ApiKeyAuth`, `OAuthAuth(authorize_url, scopes)`, `CliAuth(cli_command, auth_file_path)`, `NoAuth`
- D-04: Registry: `PROVIDERS: dict[str, LLMProvider]` populated at import time. New provider = new file + one registry line
- D-05: `GET /api/llm/providers` returns registry as JSON; frontend auto-discovers

**LLM → condado matching**
- D-06: LLM receives condado list (id, name, centroid lon/lat), returns explicit assignment by condado id
- D-07: Prompt inlines full condado list with id, name, lon, lat; response references by id
- D-08: Drag-and-drop re-assignment is Phase 4
- D-09: Unknown condado id in LLM response = validation error → retry

**Auth per provider**
- D-10: Anthropic — (1) CLI piggyback `~/.claude/.credentials.json`, (2) env var `ANTHROPIC_API_KEY`, (3) dialog paste
- D-11: Google/Gemini — (1) env var `GOOGLE_API_KEY` or `GEMINI_API_KEY`, (2) browser OAuth installed-app flow, (3) dialog paste
- D-12: OpenAI — (1) env var `OPENAI_API_KEY`, (2) dialog paste (no OAuth)
- D-13: Ollama — no auth; healthcheck via `GET localhost:11434/api/tags`
- D-14: All credentials in-memory only; never written to disk; server restart requires re-entry
- D-15: OAuth routes: `POST /api/auth/oauth/{provider}/start` → authorize_url with state; `GET /api/auth/oauth/{provider}/callback?code=...&state=...` exchanges code
- D-16: Auth status badge per provider in UI

**Ollama UX**
- D-17: `GET /api/llm/health` returns health for all providers on dialog open
- D-18: Ollama offline → radio disabled with tooltip instructing `ollama serve` and `ollama pull qwen2.5`
- D-19: Default Ollama model: `qwen2.5:7b`; fallback `llama3.1:8b`

**Research scope / granularity**
- D-20: Single-shot call returns full hierarchy `{kingdoms, duchies, condados_assignment, baronies}`
- D-21: Target scale ~91 condados / ~250 baronies fits one LLM call
- D-22: Claude + OpenAI stream (SSE token pass-through); Gemini streams if available; Ollama blocking with spinner

**Caching**
- D-23: Cache key: `(country_qid, period_start, period_end, provider, model)`
- D-24: Re-ingesting OSM does NOT invalidate cache
- D-25: New `research_cache` SQLite table: `cache_key_hash TEXT PK, payload JSON, created_at, provider, model`
- D-26: UI shows "cached" badge; force-refresh button bypasses cache

**Retry / validation**
- D-27: Pydantic schema with `model_config = ConfigDict(extra='forbid')`
- D-28: 3 retries with validation error appended to prompt
- D-29: After 3 failures: surface raw response + error; user can abort or manually edit and re-validate

### Claude's Discretion

- Exact Pydantic schema field shapes (derive from `territory_data_v3.py`)
- Prompt engineering details (system message, few-shot, token budget)
- SDK choices: official SDKs (`anthropic`, `openai`, `google-genai`, `ollama` Python clients)
- CLI piggyback auth-file path discovery (researched below)
- OAuth app registration specifics (Google Cloud Console) — single bundled client_id acceptable
- SSE message format (match existing ingest pattern)
- SQLite migration approach (match Phase 1: Alembic)
- Research dialog styling (Radix Dialog)

### Deferred Ideas (OUT OF SCOPE)

- Anthropic browser OAuth
- Automatic provider fallback
- Token usage counter UI
- Persisted credentials
- Multi-turn agent refinement
- Drag-and-drop re-assignment (Phase 4)
- Additional providers: Mistral, Groq, DeepSeek, Together
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RESEARCH-01 | User can trigger historical research via Claude API (kingdoms/duchies/counties/baronies structured JSON) | Anthropic SDK 0.96.0 AsyncAnthropic; SSE via existing ingest pattern; tool_use for JSON |
| RESEARCH-02 | User can use Ollama as alternative provider | `ollama` Python client 0.6.1; REST API `format: "json"`, `stream: false`; blocking call |
| RESEARCH-03 | Pydantic schema validation + 3-retry loop | `ConfigDict(extra='forbid')`; retry with appended error message |
| RESEARCH-04 | Research results cached per project | New `research_cache` SQLite table; Alembic migration `0002_create_research_cache.py` |
| RESEARCH-05 | Research dialog shows progress / spinner while waiting | SSE streaming via `asyncio.Queue`; mirror `useIngestStream` hook pattern |
| RESEARCH-06 | OpenAI provider (GPT-4o/5) | `openai` 2.32.0 AsyncOpenAI; `response_format={"type": "json_schema"}`; streaming via `stream=True` |
| RESEARCH-07 | Google Gemini provider | `google-genai` 1.73.1; async client; `response_mime_type="application/json"` + `response_schema` |
| RESEARCH-08 | Browser OAuth (Google) + CLI piggyback (Anthropic) + API-key fallback | `google-auth-oauthlib InstalledAppFlow`; `~/.claude/.credentials.json` file read; in-memory only |
| RESEARCH-09 | Plugin architecture — registry + adapter pattern | Protocol + registry dict; `GET /api/llm/providers` for frontend discovery |
</phase_requirements>

---

## Summary

Phase 3 adds multi-provider LLM research to Medieval Forge, allowing a user to trigger historical territory assignment using any of four providers (Claude, OpenAI, Gemini, Ollama). The phase is self-contained — it has no canvas dependency and can proceed independently of Phase 2 completion.

The core technical challenge is normalizing four very different provider SDKs (each with different JSON-mode syntax, streaming semantics, and auth flows) behind a single `LLMProvider` Protocol. The SSE streaming pattern is already established in the codebase (ingest pipeline) and can be reused almost verbatim. The Google OAuth flow uses `google-auth-oauthlib`'s `InstalledAppFlow` with a FastAPI callback endpoint; the Anthropic CLI piggyback reads `~/.claude/.credentials.json` which has been verified to exist on this machine with an `accessToken` field inside the `claudeAiOauth` key.

The OpenAI SDK has undergone a 0.x→1.x major rewrite (module-level to client-instance pattern) and is now at 2.32.0 with a further 2.0 break around function-call output types; this phase uses `AsyncOpenAI` with `chat.completions.create`. The `google-genai` package (NOT the deprecated `google-generativeai`) is at 1.73.1 and provides a unified async client.

**Primary recommendation:** Mirror the `ingest_runner.py` + `api/ingest.py` SSE pattern for the research runner; implement the LLM package as `services/llm/` with Protocol-based adapters and a registry dict; add one Alembic migration for the cache table; use `google-auth-oauthlib` for Google OAuth with PKCE; read `~/.claude/.credentials.json` for Anthropic CLI piggyback.

---

## Standard Stack

### Core — Backend
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `anthropic` | `>=0.96,<1.0` | Anthropic Claude API | Official SDK; `AsyncAnthropic` for streaming; verified on this machine at 0.96.0 |
| `openai` | `>=2.0,<3.0` | OpenAI GPT API | Official SDK; `AsyncOpenAI`; 2.x is the current major; structured outputs via `response_format` |
| `google-genai` | `>=1.70,<2.0` | Google Gemini API | Official unified SDK (NOT deprecated `google-generativeai`); async client; JSON mode via `response_mime_type` |
| `ollama` | `>=0.6,<1.0` | Ollama local LLM REST client | Official Python client; thin wrapper over REST; version 0.6.1 current |
| `google-auth-oauthlib` | `>=1.2,<2.0` | Google OAuth 2.0 installed-app flow | Standard library for OAuth; `InstalledAppFlow` supports localhost redirect |

### Supporting — Backend
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx` | already in deps | Ollama healthcheck (direct HTTP) | Fallback if `ollama` client doesn't support async health |
| `pydantic` | already in deps (`>=2.7`) | LLM response schema validation | Retry loop uses Pydantic `ValidationError` |
| `aiosqlite` / SQLAlchemy | already in deps | Research cache persistence | New table in existing DB; same async pattern |
| `alembic` | already in deps | Cache table migration | Add `0002_create_research_cache.py` migration |

### Core — Frontend
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@tanstack/react-query` | `^5.99.0` (already) | Server state for research results + cache status | Consistent with project; `useQuery`/`useMutation` for research trigger |
| `zustand` + `zundo` | already in deps | UI state (provider selection, auth status) | Wrap LLM polling in `temporal.pause()/resume()` per CLAUDE.md |
| Radix UI Dialog + Sheet | already in deps | Research dialog + auth setup side-sheet | Consistent with existing project UI patterns |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `google-auth-oauthlib InstalledAppFlow` | `authlib` or raw `httpx` OAuth | `google-auth-oauthlib` is Google's own library; handles PKCE, token refresh automatically |
| `ollama` Python client | Direct `httpx` calls to REST | Client is thin wrapper; either works; client is cleaner |
| Alembic migration | Inline `CREATE TABLE IF NOT EXISTS` in lifespan | Phase 1 already uses Alembic; maintain consistency |

**Installation (new dependencies only):**
```bash
pip install "anthropic>=0.96,<1.0" "openai>=2.0,<3.0" "google-genai>=1.70,<2.0" "ollama>=0.6,<1.0" "google-auth-oauthlib>=1.2,<2.0"
```

**Version verification:** [VERIFIED: pip index versions on this machine — anthropic 0.96.0, openai 2.32.0, google-genai 1.73.1, ollama 0.6.1]

---

## Architecture Patterns

### Recommended Project Structure (new files only)

```
backend/medieval_forge/
├── services/
│   └── llm/
│       ├── __init__.py          # exports PROVIDERS registry + LLMProvider type
│       ├── base.py              # LLMProvider Protocol, AuthMethod union, HealthStatus, ResearchQueue
│       ├── registry.py          # PROVIDERS: dict[str, LLMProvider] = {...}
│       ├── schemas.py           # Pydantic ResearchResult (derives from territory_data_v3.py)
│       ├── claude.py            # ClaudeProvider — AsyncAnthropic, CLI piggyback, env var, dialog key
│       ├── openai.py            # OpenAIProvider — AsyncOpenAI, env var, dialog key
│       ├── gemini.py            # GeminiProvider — google-genai async, OAuth, env var, dialog key
│       └── ollama.py            # OllamaProvider — ollama client, NoAuth
├── api/
│   ├── research.py              # POST /projects/{id}/research, GET /projects/{id}/research/cached,
│   │                            #   GET /api/llm/providers, GET /api/llm/health
│   └── auth.py                  # POST /api/auth/oauth/{provider}/start
│                                #   GET /api/auth/oauth/{provider}/callback
alembic/versions/
└── 0002_create_research_cache.py

frontend/src/
├── hooks/
│   └── useResearchStream.ts     # mirrors useIngestStream.ts; consumes SSE from research endpoint
├── components/
│   └── research/
│       ├── ResearchDialog.tsx   # Radix Dialog; country+period inputs; provider selector
│       ├── ProviderSelector.tsx # Renders provider list from GET /api/llm/providers
│       └── AuthSetupSheet.tsx   # Radix Sheet; per-provider auth flow (OAuth button, API key input)
└── api/
    └── research.ts              # TanStack Query wrappers for research endpoints
```

### Pattern 1: LLMProvider Protocol (base.py)

```python
# Source: CONTEXT.md D-02 / D-03
from __future__ import annotations
import asyncio
from typing import Protocol, runtime_checkable
from pydantic import BaseModel
from .schemas import ResearchResult

class HealthStatus(BaseModel):
    healthy: bool
    message: str = ""

class ApiKeyAuth(BaseModel):
    type: str = "api_key"
    env_var: str | None = None

class OAuthAuth(BaseModel):
    type: str = "oauth"
    authorize_url: str
    scopes: list[str]

class CliAuth(BaseModel):
    type: str = "cli"
    cli_command: str
    auth_file_path: str  # e.g., "~/.claude/.credentials.json"

class NoAuth(BaseModel):
    type: str = "none"

AuthMethod = ApiKeyAuth | OAuthAuth | CliAuth | NoAuth

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
    ) -> ResearchResult: ...
```

### Pattern 2: Provider Registry (registry.py)

```python
# Source: CONTEXT.md D-04
from .claude import ClaudeProvider
from .openai import OpenAIProvider
from .gemini import GeminiProvider
from .ollama import OllamaProvider

PROVIDERS: dict[str, LLMProvider] = {
    "claude": ClaudeProvider(),
    "openai": OpenAIProvider(),
    "gemini": GeminiProvider(),
    "ollama": OllamaProvider(),
}
# To add a new provider: create adapter file + add one line here.
```

### Pattern 3: Claude Provider — streaming + tool use for JSON (claude.py)

```python
# Source: Anthropic Python SDK async streaming pattern [VERIFIED: anthropic 0.96.0]
from anthropic import AsyncAnthropic

async def research(self, prompt, schema, credentials, queue):
    api_key = self._resolve_key(credentials)
    client = AsyncAnthropic(api_key=api_key)
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
            if queue:
                await queue.put(f"data: {text}\n\n")
        final = await stream.get_final_message()
    # Extract tool input from final message
    tool_block = next(b for b in final.content if b.type == "tool_use")
    return schema.model_validate(tool_block.input)
```

### Pattern 4: CLI Auth Piggyback — reading ~/.claude/.credentials.json

```python
# Source: VERIFIED empirically on this machine (Windows 11)
import json
import pathlib

def _read_claude_cli_token() -> str | None:
    """Read Anthropic OAuth access token from Claude Code credential store.
    
    VERIFIED credential file structure on Windows:
    {
        "claudeAiOauth": {
            "accessToken": "sk-ant-oat01-...",
            "refreshToken": "sk-ant-ort01-...",
            "expiresAt": 1776790173634,   # milliseconds epoch
            "scopes": [...],
            "subscriptionType": "max",
        },
        "organizationUuid": "..."
    }
    
    The accessToken is an OAuth bearer token, NOT a regular API key.
    It can be passed as Authorization: Bearer {token} to Anthropic API.
    """
    candidates = [
        pathlib.Path.home() / ".claude" / ".credentials.json",   # Linux/macOS/Windows (Claude Code default)
        pathlib.Path(os.environ.get("APPDATA", "")) / "Claude" / "credentials.json",  # Windows alt
        pathlib.Path(os.environ.get("XDG_CONFIG_HOME", pathlib.Path.home() / ".config"))
            / "claude" / "credentials.json",  # Linux XDG alt
    ]
    for path in candidates:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                token_data = data.get("claudeAiOauth", {})
                access_token = token_data.get("accessToken")
                expires_at_ms = token_data.get("expiresAt", 0)
                import time
                if access_token and expires_at_ms > time.time() * 1000:
                    return access_token
            except (json.JSONDecodeError, OSError):
                continue
    return None
```

**IMPORTANT:** The CLI token is an OAuth bearer token (`sk-ant-oat01-...`), not a regular API key (`sk-ant-api...`). The Anthropic Python SDK accepts it via `api_key=token` but it uses a different prefix. Verify the `AsyncAnthropic` client accepts OAuth tokens the same way as API keys — if not, may need to use `Authorization: Bearer` header directly via `httpx`. [ASSUMED — needs validation during implementation]

### Pattern 5: Google OAuth Installed-App Flow

```python
# Source: google-auth-oauthlib InstalledAppFlow [CITED: googleapis.github.io/google-api-python-client/docs/oauth-installed.html]
# This is the BACKEND orchestration; the actual browser open happens client-side via redirect.

from google_auth_oauthlib.flow import Flow

CLIENT_SECRETS = {
    "installed": {
        "client_id": "{BUNDLED_CLIENT_ID}",
        "client_secret": "{BUNDLED_CLIENT_SECRET}",
        "redirect_uris": ["http://localhost:{PORT}/api/auth/oauth/gemini/callback"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

# POST /api/auth/oauth/gemini/start
async def oauth_start(request: Request, provider: str):
    state = secrets.token_urlsafe(32)
    flow = Flow.from_client_config(
        CLIENT_SECRETS,
        scopes=["https://www.googleapis.com/auth/generative-language.retriever"],
        redirect_uri=f"http://localhost:{PORT}/api/auth/oauth/gemini/callback",
    )
    flow.code_verifier = secrets.token_urlsafe(64)  # PKCE
    authorize_url, _ = flow.authorization_url(state=state, access_type="offline")
    request.app.state.oauth_states[state] = {
        "flow": flow, "provider": provider, "expires_at": time.time() + 300
    }
    return {"authorize_url": authorize_url}

# GET /api/auth/oauth/gemini/callback
async def oauth_callback(code: str, state: str, request: Request):
    stored = request.app.state.oauth_states.pop(state, None)
    if not stored:
        raise HTTPException(400, "Invalid or expired state")
    flow = stored["flow"]
    flow.fetch_token(code=code)
    creds = flow.credentials
    request.app.state.credentials["gemini"] = {
        "type": "oauth",
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }
    # Redirect back to frontend (HTML response or JSON)
    return {"status": "authenticated", "provider": "gemini"}
```

### Pattern 6: Gemini Provider — google-genai async + JSON mode

```python
# Source: google-genai 1.73.1 [CITED: googleapis.github.io/python-genai/]
from google import genai
from google.genai import types

async def research(self, prompt, schema, credentials, queue):
    token = credentials.get("access_token") if credentials else None
    api_key = credentials.get("api_key") if credentials else os.getenv("GOOGLE_API_KEY")
    
    if token:
        client = genai.Client(http_options={"headers": {"Authorization": f"Bearer {token}"}})
    else:
        client = genai.Client(api_key=api_key)
    
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,  # Pydantic model supported directly
        temperature=0.2,
    )
    response = await client.aio.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=config,
    )
    if queue:
        await queue.put(f"data: Gemini responded ({len(response.text)} chars)\n\n")
    return schema.model_validate_json(response.text)
```

**Note:** Gemini streaming via `aio.models.generate_content_stream` IS available but combined with `response_schema` may have limitations [CITED: github.com/googleapis/python-genai/issues/867]. Use non-streaming with a spinner for Gemini (per D-22).

### Pattern 7: OpenAI Provider — AsyncOpenAI + structured output

```python
# Source: openai 2.32.0 AsyncOpenAI [ASSUMED API shape — verify against 2.x docs]
from openai import AsyncOpenAI

async def research(self, prompt, schema, credentials, queue):
    api_key = credentials.get("api_key") if credentials else os.getenv("OPENAI_API_KEY")
    client = AsyncOpenAI(api_key=api_key)
    
    # Structured output: response_format with json_schema
    stream = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "research_result",
                "schema": schema.model_json_schema(),
                "strict": True,
            }
        },
        stream=True,
    )
    chunks = []
    async for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        chunks.append(delta)
        if queue and delta:
            await queue.put(f"data: {delta}\n\n")
    return schema.model_validate_json("".join(chunks))
```

### Pattern 8: Retry Loop (shared, in research runner)

```python
# Source: CONTEXT.md D-27..D-29
from pydantic import ValidationError

async def run_with_retry(
    provider: LLMProvider,
    prompt_base: str,
    schema: type[BaseModel],
    credentials: dict | None,
    queue: asyncio.Queue[str | None] | None,
    max_retries: int = 3,
) -> BaseModel:
    prompt = prompt_base
    last_error = last_raw = None
    for attempt in range(max_retries):
        try:
            return await provider.research(prompt, schema, credentials, queue)
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            last_error = str(e)
            last_raw = None  # provider should expose raw on failure
            correction = (
                f"\n\nYour previous response failed validation with: {last_error}. "
                "Return corrected JSON only, no prose."
            )
            prompt = prompt_base + correction
            if queue:
                await queue.put(f"data: Retry {attempt + 1}/{max_retries}: {last_error[:80]}...\n\n")
    # All retries exhausted
    raise ResearchValidationError(last_error, last_raw)
```

### Pattern 9: SSE Research Runner (mirrors ingest_runner.py)

The research runner follows the same producer/sentinel pattern established by `ingest_runner.py`:
- `asyncio.Queue[str | None]` for SSE messages
- `None` sentinel to signal completion
- `StreamingResponse` with `text/event-stream` media type
- `data: DONE\n\n` on success, `data: ERROR: {msg}\n\n` on failure

### Pattern 10: Research Cache Table

```python
# Alembic migration 0002_create_research_cache.py
def upgrade() -> None:
    op.create_table(
        "research_cache",
        sa.Column("cache_key_hash", sa.String(64), primary_key=True),  # SHA-256 hex
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("country_qid", sa.String(20), nullable=False),
        sa.Column("period_start", sa.Integer(), nullable=False),
        sa.Column("period_end", sa.Integer(), nullable=False),
    )
```

Cache key hash: `hashlib.sha256(f"{country_qid}:{period_start}:{period_end}:{provider}:{model}".encode()).hexdigest()`

### Anti-Patterns to Avoid

- **Never read `claudeAiOauth.accessToken` without checking `expiresAt`:** The token expires. Check `expiresAt > time.time() * 1000` before use; return "needs re-auth" if expired.
- **Never call `google-generativeai` (deprecated):** Only `google-genai`. The package names are different on PyPI.
- **Never use Pydantic `Optional[X]` with OpenAI structured outputs:** OpenAI's `strict=True` requires all fields to be `required`; use `X | None` with a `default=None`.
- **Never block the event loop in SSE generators:** All provider calls must be `await`-able. Ollama's Python client has both sync and async paths — use async.
- **Never store OAuth state in a global dict without TTL cleanup:** State params expire in 5 minutes; clean them up to prevent memory growth.
- **Never embed OAuth client_secret in the frontend bundle:** The secret stays on the Python backend; the frontend only receives the `authorize_url`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Google OAuth installed-app flow | Custom PKCE + code exchange | `google-auth-oauthlib InstalledAppFlow` | Handles PKCE, token refresh, secure state; edge cases in code exchange |
| JSON mode normalization | Custom prompt parsing | Provider-native JSON modes (tool_use, json_schema, response_mime_type, format) | LLMs reliably output valid JSON only when the API enforces it |
| Streaming SSE from LLM | Custom HTTP chunked reader | Provider SDK stream iterators | Handles partial chunks, retries, keep-alive |
| OAuth CSRF protection | Manual nonce tracking | `secrets.token_urlsafe(32)` state param + server-side TTL map | Prevents authorization code interception |
| Pydantic JSON schema for LLM | Manual schema description in prompt | `schema.model_json_schema()` | Authoritative, always in sync with validation code |

**Key insight:** Each provider's JSON mode is fundamentally different — Claude uses `tool_use`, OpenAI uses `response_format.json_schema`, Gemini uses `response_mime_type`, Ollama uses `format: "json"`. The adapter pattern is essential: without it, the retry loop would need provider-specific logic.

---

## Common Pitfalls

### Pitfall 1: Claude CLI Token is OAuth, Not API Key
**What goes wrong:** Developer treats `accessToken` from `~/.claude/.credentials.json` like a regular `ANTHROPIC_API_KEY` (`sk-ant-api...`). The Anthropic SDK may reject it or behave unexpectedly.
**Why it happens:** The file path suggests it's the same credential type, but Claude Code uses OAuth tokens (`sk-ant-oat01-...`), not API keys.
**How to avoid:** Use `AsyncAnthropic(api_key=token)` — Anthropic's SDK accepts OAuth tokens in the `api_key` field. If it fails, fall back to raw `httpx` with `Authorization: Bearer {token}`. Add a prefix check: if token starts with `sk-ant-oat01-`, it's an OAuth token.
**Warning signs:** HTTP 401 with "invalid API key" when token looks valid.

### Pitfall 2: google-generativeai vs google-genai
**What goes wrong:** Using `import google.generativeai as genai` (the deprecated package) instead of `from google import genai` (the current `google-genai` package).
**Why it happens:** Many Stack Overflow answers and tutorials still reference the old package; both are installable via pip with similar names.
**How to avoid:** In pyproject.toml, depend on `google-genai` (not `google-generativeai`). Import is `from google import genai`.
**Warning signs:** `ModuleNotFoundError: No module named 'google.generativeai'` or unexpected API shape.

### Pitfall 3: Gemini response_mime_type + response_schema Conflict with Tool Use
**What goes wrong:** Attempting to combine `response_mime_type="application/json"` with function calling / tool use in the same request.
**Why it happens:** Gemini API does not support these together (GitHub issue #867).
**How to avoid:** For Gemini, use ONLY `response_mime_type` + `response_schema` (Pydantic model). Do not add tools.
**Warning signs:** API returns 400 "GenerateContent not supported with both JSON and function calling".

### Pitfall 4: OpenAI Structured Output + Pydantic Optional Fields
**What goes wrong:** `strict=True` in OpenAI structured outputs rejects schemas with `Optional[X]` that generate `"required": false` fields.
**Why it happens:** OpenAI's strict mode requires ALL fields to be present; nullable types must use `X | None` with a JSON schema `anyOf`.
**How to avoid:** Use `field: str | None = None` syntax in Python 3.10+ (generates correct `anyOf`). Test the schema via `schema.model_json_schema()` before sending.
**Warning signs:** OpenAI returns 400 "Invalid schema: field not in required array".

### Pitfall 5: OAuth State Param Memory Leak
**What goes wrong:** `app.state.oauth_states` dict grows indefinitely if users start OAuth flows without completing them.
**Why it happens:** State entries are only removed on successful callback; abandoned flows are never cleaned up.
**How to avoid:** Store expiry timestamp with each state entry; clean expired entries on each `oauth_start` call (or a periodic background task).
**Warning signs:** Server memory slowly grows over long uptime sessions.

### Pitfall 6: SSE Connection Drop During Long LLM Call
**What goes wrong:** Client disconnects mid-stream; the background `asyncio.Task` continues running and accumulates queue messages that are never consumed, causing slow memory growth.
**Why it happens:** SSE generators don't detect client disconnection until the next `yield`; the producer task keeps running.
**How to avoid:** Mirror the existing `ingest.py` pattern — `finally: task.cancel(); await task` — to ensure the producer is cancelled when the generator exits.
**Warning signs:** Multiple orphaned LLM API calls visible in provider dashboards.

### Pitfall 7: Alembic Migration Not Including New Models
**What goes wrong:** Adding the `ResearchCache` SQLAlchemy model to `models.py` but forgetting to import it in `alembic/env.py` (via `Base.metadata`), so autogenerate doesn't detect it.
**Why it happens:** Alembic autogenerate only sees models imported before `target_metadata = Base.metadata` is evaluated.
**How to avoid:** Ensure `models.py` is imported before `Base.metadata` is captured in `env.py`. The current `env.py` already imports `from medieval_forge.models import Base` — add `ResearchCache` to `models.py` and it will be picked up.
**Warning signs:** `alembic revision --autogenerate` generates an empty migration.

---

## Code Examples

### GET /api/llm/providers Response Shape
```json
[
  {
    "provider_id": "claude",
    "display_name": "Claude (Anthropic)",
    "auth_methods": [
      {"type": "cli", "cli_command": "claude", "auth_file_path": "~/.claude/.credentials.json"},
      {"type": "api_key", "env_var": "ANTHROPIC_API_KEY"},
      {"type": "api_key", "env_var": null}
    ],
    "configured": true,
    "healthy": true
  },
  {
    "provider_id": "gemini",
    "display_name": "Gemini (Google)",
    "auth_methods": [
      {"type": "api_key", "env_var": "GOOGLE_API_KEY"},
      {"type": "oauth", "authorize_url": null, "scopes": ["..."]},
      {"type": "api_key", "env_var": null}
    ],
    "configured": false,
    "healthy": false
  }
]
```

### Pydantic ResearchResult Schema (from territory_data_v3.py)
```python
from pydantic import BaseModel, ConfigDict

class Barony(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    lon: float
    lat: float

class CondadoAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    condado_id: str           # must be in provided condado list — validated post-parse
    kingdom_id: str
    duchy_id: str

class ResearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kingdoms: dict[str, str]                # id -> display_name
    duchies: dict[str, tuple[str, str]]     # id -> (kingdom_id, display_name)
    condados_assignment: list[CondadoAssignment]
    baronies: dict[str, list[Barony]]       # condado_id -> list of baronies
```

### Credential Resolution Priority (per provider)
```python
def _resolve_credentials(self, in_memory: dict | None) -> dict:
    """Priority: in-memory (session) > env var > cli piggyback"""
    if in_memory:
        return in_memory
    env_key = os.getenv("ANTHROPIC_API_KEY")
    if env_key:
        return {"type": "api_key", "key": env_key, "source": "env"}
    cli_token = _read_claude_cli_token()
    if cli_token:
        return {"type": "oauth_token", "key": cli_token, "source": "cli"}
    return {}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `google-generativeai` package | `google-genai` package | 2024 | Old package deprecated; new one is the unified SDK |
| `openai` module-level `ChatCompletion.create()` | `AsyncOpenAI().chat.completions.create()` | openai 1.0.0 | Client-instance pattern; async via `AsyncOpenAI` |
| `openai` `response_format={"type":"json_object"}` | `response_format={"type":"json_schema", "json_schema":{...}}` | openai 1.40+ | Structured outputs with schema enforcement |
| Claude `response_format` workaround | Claude tool_use with `tool_choice="tool"` | 2024 | Guaranteed JSON output via function-calling constraint |
| OAuth `urn:ietf:wg:oauth:2.0:oob` redirect | `http://localhost:{PORT}/callback` + PKCE | ~2022 | Google deprecated OOB for security; localhost is current |

**Deprecated/outdated:**
- `google-generativeai`: Deprecated in favor of `google-genai`. Both exist on PyPI; don't install the old one.
- `openai` 0.x API: `openai.ChatCompletion.create()` is gone since 1.0.0; rewrite is total.
- OAuth `urn:ietf:wg:oauth:2.0:oob` (out-of-band): Removed by Google in 2022; `localhost` redirect is now mandatory for installed apps.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `AsyncAnthropic(api_key=oauth_token)` works with `sk-ant-oat01-` prefix tokens | Code Examples / Pitfall 1 | Would require direct httpx Authorization header; adds ~10 lines of code |
| A2 | Gemini `aio.models.generate_content` accepts `response_schema=PydanticModel` directly | Code Examples Pattern 6 | Would need `response_schema=schema.model_json_schema()` instead; minor fix |
| A3 | OpenAI 2.x `chat.completions.create` streaming with `response_format.json_schema` works as documented | Code Examples Pattern 7 | May require non-streaming call + parse; retry loop still works |
| A4 | `google-auth-oauthlib Flow.authorization_url()` accepts `code_verifier` as PKCE parameter | Code Examples Pattern 5 | May need `code_challenge` + `code_challenge_method` separate params; adjust OAuth start handler |
| A5 | Gemini model `gemini-2.0-flash` supports `response_mime_type` + `response_schema` | Standard Stack / Pattern 6 | Fall back to `gemini-1.5-pro` which is confirmed to support it |

---

## Open Questions

1. **Claude OAuth token compatibility with AsyncAnthropic SDK**
   - What we know: `~/.claude/.credentials.json` contains `claudeAiOauth.accessToken` (prefix `sk-ant-oat01-`); token is valid (not expired) on this machine
   - What's unclear: Whether `AsyncAnthropic(api_key=token)` accepts OAuth tokens vs API keys at the SDK level
   - Recommendation: Try `AsyncAnthropic(api_key=token)` first; if 401, switch to direct httpx with `Authorization: Bearer {token}` header. Add an integration test in Wave 0.

2. **Google OAuth bundled client_id / client_secret**
   - What we know: Desktop app flow allows localhost redirect; PKCE is standard since 2022
   - What's unclear: Whether a pre-registered `client_id` can be bundled in an open-source tool without violating Google's terms of service for OAuth clients
   - Recommendation: Register a single "Desktop app" OAuth client in Google Cloud Console under the project owner's account; bundle `client_id` and `client_secret` in the Python package. Document that users who fork must register their own. Mark as [ASSUMED] until GCP terms are verified.

3. **Gemini streaming + response_schema compatibility**
   - What we know: GitHub issue #867 shows `function_calling + response_mime_type` conflict; streaming separately is supported
   - What's unclear: Whether `aio.models.generate_content_stream` + `response_schema` (without function calling) works
   - Recommendation: Default to non-streaming for Gemini (spinner only, per D-22) to avoid the conflict. Streaming can be added later as a Gemini-specific enhancement.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All backend | Assumed yes (project already running) | — | — |
| `anthropic` | RESEARCH-01 | Not yet installed | Latest: 0.96.0 | Install in Wave 0 |
| `openai` | RESEARCH-06 | Not yet installed | Latest: 2.32.0 | Install in Wave 0 |
| `google-genai` | RESEARCH-07 | Not yet installed | Latest: 1.73.1 | Install in Wave 0 |
| `google-auth-oauthlib` | RESEARCH-08 OAuth | Not yet installed | Latest: 1.2.x | Install in Wave 0 |
| `ollama` Python client | RESEARCH-02 | Not yet installed | Latest: 0.6.1 | Install in Wave 0 |
| Ollama server (local) | RESEARCH-02 | Not running | — | Disable gracefully with tooltip |
| `~/.claude/.credentials.json` | RESEARCH-08 CLI piggyback | PRESENT (verified) | Token valid | API key fallback if missing/expired |
| Claude `claude` binary | RESEARCH-08 CLI piggyback | Present at `~/.local/bin/claude` | — | File-read fallback (already preferred) |

**Missing dependencies with no fallback:** None — all missing packages are pip-installable; Ollama absence is handled by graceful disable.

**Missing dependencies with fallback:**
- `ollama` server: Not running → show as unhealthy in provider list, disable radio with tooltip (D-17/D-18)
- All new Python SDKs: Must be installed via `pip install` in Wave 0 task

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio (backend); vitest 3.2.4 (frontend) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (backend); `vite.config.ts` (frontend) |
| Quick run command | `pytest backend/tests/test_research.py -x` |
| Full suite command | `pytest backend/tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RESEARCH-01 | Claude provider returns valid ResearchResult | unit (mock API) | `pytest backend/tests/test_research.py::test_claude_provider -x` | Wave 0 |
| RESEARCH-02 | Ollama provider returns valid ResearchResult | unit (mock REST) | `pytest backend/tests/test_research.py::test_ollama_provider -x` | Wave 0 |
| RESEARCH-03 | Retry loop retries 3x then raises | unit | `pytest backend/tests/test_research.py::test_retry_loop -x` | Wave 0 |
| RESEARCH-04 | Cache returns same result without second LLM call | unit (SQLite in-memory) | `pytest backend/tests/test_research.py::test_cache_hit -x` | Wave 0 |
| RESEARCH-05 | SSE endpoint streams progress messages | integration | `pytest backend/tests/test_research.py::test_sse_stream -x` | Wave 0 |
| RESEARCH-06 | OpenAI provider returns valid ResearchResult | unit (mock API) | `pytest backend/tests/test_research.py::test_openai_provider -x` | Wave 0 |
| RESEARCH-07 | Gemini provider returns valid ResearchResult | unit (mock API) | `pytest backend/tests/test_research.py::test_gemini_provider -x` | Wave 0 |
| RESEARCH-08 | CLI piggyback reads token from ~/.claude/.credentials.json | unit | `pytest backend/tests/test_research.py::test_cli_auth_piggyback -x` | Wave 0 |
| RESEARCH-08 | OAuth state param validated; expired state rejected | unit | `pytest backend/tests/test_research.py::test_oauth_state_validation -x` | Wave 0 |
| RESEARCH-09 | New provider registered → appears in GET /api/llm/providers | unit | `pytest backend/tests/test_research.py::test_provider_registry -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest backend/tests/test_research.py -x`
- **Per wave merge:** `pytest backend/tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_research.py` — covers all RESEARCH-XX requirements above
- [ ] `backend/tests/services/test_llm_providers.py` — unit tests for each provider adapter (mock SDKs)
- [ ] Framework install: `pip install "anthropic>=0.96,<1.0" "openai>=2.0,<3.0" "google-genai>=1.70,<2.0" "ollama>=0.6,<1.0" "google-auth-oauthlib>=1.2,<2.0"`
- [ ] Update `pyproject.toml` with new dependencies

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | OAuth PKCE state validation; credential source priority chain |
| V3 Session Management | yes | In-memory only credentials; TTL on OAuth state params; no disk persistence |
| V4 Access Control | no | Single-user local tool; no multi-user access |
| V5 Input Validation | yes | Pydantic `extra='forbid'` for LLM output; condado_id whitelist check |
| V6 Cryptography | no | OAuth PKCE uses `secrets.token_urlsafe`; no custom crypto |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| OAuth CSRF (state param forgery) | Spoofing | `secrets.token_urlsafe(32)` state param; server-side TTL map; reject unknown state |
| API key leakage to frontend | Information Disclosure | Keys stay in `app.state.credentials` (backend); frontend only sees `configured: bool` |
| LLM prompt injection via condado names | Tampering | Condado names from OSM (trusted source); names are data, not instructions; schema validation catches malformed output |
| Credential persistence after restart | Information Disclosure | In-memory only — `app.state.credentials` cleared on process exit; explicitly documented in D-14 |
| OAuth token bundling | Spoofing | Client_secret on backend only; never in frontend bundle or git (use env var or bundled in pkg data with .gitignore) |

---

## Sources

### Primary (HIGH confidence)
- `backend/medieval_forge/services/ingest_runner.py` — SSE queue producer pattern (verified in codebase)
- `backend/medieval_forge/api/ingest.py` — SSE endpoint wiring (verified in codebase)
- `inicio/licoes/territory_data_v3.py` — reference hierarchy shape for Pydantic schema (verified in codebase)
- `~/.claude/.credentials.json` — credential file structure verified empirically on this machine
- `pip index versions` — all SDK versions verified against PyPI on 2026-04-21

### Secondary (MEDIUM confidence)
- [googleapis.github.io/python-genai/](https://googleapis.github.io/python-genai/) — google-genai async client, response_mime_type, response_schema
- [googleapis.github.io/google-api-python-client/docs/oauth-installed.html](https://googleapis.github.io/google-api-python-client/docs/oauth-installed.html) — InstalledAppFlow with PKCE
- [google developers OAuth 2.0 native apps](https://developers.google.com/identity/protocols/oauth2/native-app) — localhost redirect, PKCE requirement
- [openai-python v1.0.0 migration guide](https://github.com/openai/openai-python/discussions/742) — module-level to client-instance breaking change
- [google-genai issue #867](https://github.com/googleapis/python-genai/issues/867) — response_mime_type + function calling conflict

### Tertiary (LOW confidence)
- OpenAI 2.32.0 structured output with `stream=True` (unverified combination) — marked [ASSUMED]
- Claude OAuth token compatibility with `AsyncAnthropic(api_key=)` — marked [ASSUMED]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified via `pip index versions` on this machine
- Architecture: HIGH — mirrors existing SSE pattern exactly; Protocol pattern is standard Python
- Auth (CLI piggyback): HIGH — credential file structure verified empirically
- Auth (Google OAuth): MEDIUM — documented flow; client_id bundling policy needs GCP console verification
- Pitfalls: HIGH — most verified via official GitHub issues or SDK documentation

**Research date:** 2026-04-21
**Valid until:** 2026-05-21 (SDK versions stable; Gemini streaming behavior may change with new releases)
