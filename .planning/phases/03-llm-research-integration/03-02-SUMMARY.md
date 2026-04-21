---
phase: 03
plan: 02
subsystem: backend-auth
tags: [auth, oauth, credentials, llm, security]
dependency_graph:
  requires: []
  provides: [auth-endpoints, resolve-credentials, llm-package-scaffold]
  affects: [main.py, api/auth.py, services/llm/]
tech_stack:
  added: [google-auth-oauthlib]
  patterns: [in-memory-credential-store, oauth-installed-app-flow, cli-piggyback]
key_files:
  created:
    - backend/medieval_forge/api/auth.py
    - backend/medieval_forge/services/llm/auth.py
    - backend/medieval_forge/services/llm/__init__.py
    - backend/medieval_forge/services/llm/base.py
    - backend/medieval_forge/services/llm/registry.py
    - backend/medieval_forge/services/llm/claude.py
    - backend/medieval_forge/services/llm/openai.py
    - backend/medieval_forge/services/llm/gemini.py
    - backend/medieval_forge/services/llm/ollama.py
    - backend/tests/unit/__init__.py
    - backend/tests/unit/test_auth_session.py
    - backend/tests/unit/test_oauth_flow.py
    - backend/tests/unit/test_cli_piggyback.py
  modified:
    - backend/medieval_forge/main.py
decisions:
  - "Flow.from_client_config state echo used as oauth_states dict key (not pre-generated secrets.token_urlsafe) so mock-based tests can assert predictable state key"
  - "google_auth_oauthlib.flow.Flow imported at module level (not lazy) to allow patch() in tests"
  - "Provider stubs raise NotImplementedError; full research() implementations deferred to Plan 03-03"
  - "OAUTH_STATE_TTL_SEC = 300 (5 min); cleaned on every /start call per Pitfall 5"
metrics:
  duration: "~74 minutes"
  completed_date: "2026-04-21"
  tasks_completed: 2
  files_created: 14
  files_modified: 1
---

# Phase 03 Plan 02: Auth Abstraction Layer Summary

**One-liner:** In-memory credential store with REST endpoints, Google OAuth installed-app CSRF flow, and Anthropic CLI piggyback for multi-provider LLM auth.

## What Was Built

### Endpoints Added

| Method | Path | Behavior |
|--------|------|----------|
| POST | `/api/auth/credentials/{provider}` | Stores API key in `app.state.credentials[provider]`; returns 204 (key never echoed) |
| DELETE | `/api/auth/credentials/{provider}` | Removes credential from in-memory store; returns 204 |
| POST | `/api/auth/oauth/{provider}/start` | Gemini only; generates CSRF state token, returns `{"authorize_url": "...", "state": "..."}` |
| GET | `/api/auth/oauth/{provider}/callback` | Validates state + TTL, calls `flow.fetch_token()`, stores access token |

All 4 endpoints reject unknown providers with 404.

### `resolve_credentials` Priority Chain

| Provider | Priority Order |
|----------|---------------|
| `claude` | session → `ANTHROPIC_API_KEY` env → CLI piggyback (`~/.claude/.credentials.json`) |
| `gemini` | session → `GOOGLE_API_KEY` / `GEMINI_API_KEY` env |
| `openai` | session → `OPENAI_API_KEY` env |
| `ollama` | always `{"type": "none", "source": "none"}` (no auth needed) |

### OAuth State TTL

- State tokens expire after 300 seconds
- Stale entries cleaned on every `/start` call (prevents memory leak — T-3-06 / Pitfall 5)
- Unknown or expired state in `/callback` → HTTP 400

### CLI Piggyback

`read_claude_cli_token()` reads `~/.claude/.credentials.json` (primary on Windows/Linux/macOS) and checks `claudeAiOauth.accessToken` with `expiresAt` millisecond timestamp. Falls back to `%APPDATA%\Claude\credentials.json` and `$XDG_CONFIG_HOME/claude/credentials.json`.

### Bundled OAuth `client_id` Status

**Placeholder** — `GOOGLE_CLIENT_CONFIG` in `api/auth.py` contains:
```
"client_id": "REPLACE_WITH_BUNDLED_CLIENT_ID.apps.googleusercontent.com"
"client_secret": "REPLACE_WITH_BUNDLED_CLIENT_SECRET"
```
The OAuth path is exercised via mocked `Flow` in tests. Real OAuth flows require a GCP-registered Desktop App client. Plan 04 will surface "OAuth not configured" gracefully when the placeholder is detected.

### LLM Package Scaffold

`services/llm/` package created with Protocol base, 4 provider stubs, and registry. Provider `research()` methods raise `NotImplementedError` — to be implemented in Plan 03-03.

## Test Results

- `test_auth_session.py`: 5/5 passed
- `test_oauth_flow.py`: 6/6 passed
- `test_cli_piggyback.py`: 7/7 passed
- **Total: 18/18 passed**

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Flow imported at module level instead of lazy**
- **Found during:** Task 2 (RED phase — test collection)
- **Issue:** Plan suggested `from google_auth_oauthlib.flow import Flow` inside the function body. `unittest.mock.patch("medieval_forge.api.auth.Flow")` requires the name to exist at module scope.
- **Fix:** Moved import to module top-level.
- **Files modified:** `backend/medieval_forge/api/auth.py`
- **Commit:** e183a33

**2. [Rule 1 - Bug] OAuth state key mismatch between implementation and test**
- **Found during:** Task 2 (GREEN phase — first test run)
- **Issue:** Implementation stored oauth state under `secrets.token_urlsafe(32)` (our generated key), but mock `flow.authorization_url()` returns `"state123"` which the test asserts is in `oauth_states`. The keys were different.
- **Fix:** Used `returned_state = flow.authorization_url(...)[1]` as the `oauth_states` dict key; falls back to the pre-generated token if `returned_state` is falsy. This aligns with Google's `authorization_url()` echoing back the state param it was given.
- **Files modified:** `backend/medieval_forge/api/auth.py`
- **Commit:** e183a33

## Known Stubs

| Stub | File | Lines | Reason |
|------|------|-------|--------|
| `ClaudeProvider.research()` | `services/llm/claude.py` | ~34 | Deferred to Plan 03-03 |
| `OpenAIProvider.research()` | `services/llm/openai.py` | ~27 | Deferred to Plan 03-03 |
| `GeminiProvider.research()` | `services/llm/gemini.py` | ~29 | Deferred to Plan 03-03 |
| `OllamaProvider.research()` | `services/llm/ollama.py` | ~29 | Deferred to Plan 03-03 |
| `GOOGLE_CLIENT_CONFIG.client_id` | `api/auth.py` | ~37 | Placeholder; requires GCP app registration before shipping |

These stubs do not block this plan's goal (auth abstraction layer). Plan 03-03 implements the research adapters.

## Threat Surface Scan

No new threat surface beyond what was modeled in `<threat_model>`. All T-3-01..T-3-07 mitigations implemented:
- T-3-01: Zero `open(..., "w")` / `write_text` / `write_bytes` in auth modules (grep verified)
- T-3-02: CSRF state with `secrets.token_urlsafe(32)`, TTL 300s, 400 on mismatch
- T-3-03: POST returns 204 No Content; test asserts key not in response body
- T-3-04: `client_secret` in Python module only (not frontend bundle)
- T-3-05: `read_claude_cli_token()` returns token string only; no logging of file contents
- T-3-06: Expired state cleanup on every `/start` call

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `backend/medieval_forge/api/auth.py` exists | FOUND |
| `backend/medieval_forge/services/llm/auth.py` exists | FOUND |
| `backend/medieval_forge/services/llm/registry.py` exists | FOUND |
| `backend/medieval_forge/main.py` exists | FOUND |
| `backend/tests/unit/test_auth_session.py` exists | FOUND |
| `backend/tests/unit/test_oauth_flow.py` exists | FOUND |
| `backend/tests/unit/test_cli_piggyback.py` exists | FOUND |
| commit 14f5d12 (test scaffold) | FOUND |
| commit e183a33 (implementation) | FOUND |
