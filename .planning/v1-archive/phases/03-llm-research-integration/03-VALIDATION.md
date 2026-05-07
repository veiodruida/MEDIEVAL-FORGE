---
phase: 3
slug: llm-research-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-21
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) + vitest (frontend) |
| **Config file** | `backend/pyproject.toml` [tool.pytest] / `frontend/vite.config.ts` |
| **Quick run command** | `cd backend && pytest tests/ -x -q` |
| **Full suite command** | `cd backend && pytest tests/ && cd ../frontend && npx vitest run` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && pytest tests/ && cd ../frontend && npx vitest run`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 1 | RESEARCH-01 | — | Adapter Protocol enforced at import | unit | `pytest tests/unit/test_llm_registry.py -x` | ❌ W0 | ⬜ pending |
| 3-01-02 | 01 | 1 | RESEARCH-02 | — | Pydantic extra=forbid rejects unknown fields | unit | `pytest tests/unit/test_llm_schemas.py -x` | ❌ W0 | ⬜ pending |
| 3-01-03 | 01 | 1 | RESEARCH-03 | — | Retry loop sends corrected prompt on validation failure | unit | `pytest tests/unit/test_llm_retry.py -x` | ❌ W0 | ⬜ pending |
| 3-02-01 | 02 | 1 | RESEARCH-08 | T-3-01 | API key stored in-memory only, not written to disk | unit | `pytest tests/unit/test_auth_session.py -x` | ❌ W0 | ⬜ pending |
| 3-02-02 | 02 | 1 | RESEARCH-08 | T-3-02 | OAuth state param validated (CSRF protection) | unit | `pytest tests/unit/test_oauth_flow.py -x` | ❌ W0 | ⬜ pending |
| 3-03-01 | 03 | 2 | RESEARCH-04 | — | Cache hit returns without LLM call | unit | `pytest tests/unit/test_research_cache.py -x` | ❌ W0 | ⬜ pending |
| 3-03-02 | 03 | 2 | RESEARCH-06 | — | SSE stream emits progress events during research | integration | `pytest tests/integration/test_research_sse.py -x` | ❌ W0 | ⬜ pending |
| 3-04-01 | 04 | 2 | RESEARCH-05 | — | Provider list populated from /api/llm/providers | e2e-manual | manual: open dialog, verify dropdown | N/A | ⬜ pending |
| 3-04-02 | 04 | 2 | RESEARCH-07 | — | Unknown condado id from LLM triggers retry | unit | `pytest tests/unit/test_condado_assignment.py -x` | ❌ W0 | ⬜ pending |
| 3-04-03 | 04 | 2 | RESEARCH-09 | — | GET /api/llm/providers returns machine-readable registry | integration | `pytest tests/integration/test_providers_endpoint.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/unit/test_llm_registry.py` — stubs for RESEARCH-01 (adapter Protocol, registry lookup)
- [ ] `backend/tests/unit/test_llm_schemas.py` — stubs for RESEARCH-02 (Pydantic schema validation)
- [ ] `backend/tests/unit/test_llm_retry.py` — stubs for RESEARCH-03 (3-retry validation loop)
- [ ] `backend/tests/unit/test_auth_session.py` — stubs for RESEARCH-08 (in-memory credential storage)
- [ ] `backend/tests/unit/test_oauth_flow.py` — stubs for RESEARCH-08 (OAuth CSRF state validation)
- [ ] `backend/tests/unit/test_research_cache.py` — stubs for RESEARCH-04 (cache key hit/miss)
- [ ] `backend/tests/integration/test_research_sse.py` — stubs for RESEARCH-06 (SSE progress stream)
- [ ] `backend/tests/unit/test_condado_assignment.py` — stubs for RESEARCH-07 (condado id validation)
- [ ] `backend/tests/integration/test_providers_endpoint.py` — stubs for RESEARCH-09 (provider registry endpoint)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Google OAuth browser redirect and token exchange | RESEARCH-08 | Requires live browser + Google account | Click "Sign in with Google" in Research dialog; verify auth status badge shows "✓ via OAuth (Google)" |
| `claude-code` CLI piggyback reads `~/.claude/.credentials.json` | RESEARCH-08 | Requires `claude-code` installed + authenticated | Open dialog with ANTHROPIC_API_KEY unset; verify auth status shows "✓ via CLI auth" |
| Streaming tokens display in Research dialog | RESEARCH-05 | Requires live LLM API call | Trigger research with Claude/OpenAI; verify tokens appear progressively in the dialog |
| Research dialog does not freeze during LLM call | RESEARCH-05 | Visual/UX test | Trigger research; verify UI remains interactive (can scroll, close other modals) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
