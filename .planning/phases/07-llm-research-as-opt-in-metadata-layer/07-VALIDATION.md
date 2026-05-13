---
phase: 07
slug: llm-research-as-opt-in-metadata-layer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-13
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (backend) + vitest (frontend unit) + Playwright (frontend UAT) |
| **Config file** | `backend/pyproject.toml` (pytest section) + `frontend/vitest.config.ts` + `frontend/playwright.config.ts` |
| **Quick run command** | `cd backend && pytest tests/unit -x -q` (~10 s) |
| **Full suite command** | `cd backend && pytest tests/ -x` + `cd frontend && npm run test:unit && npm run test:e2e` |
| **Estimated runtime** | ~120 seconds full suite (backend unit ~10 s, parity ~40 s, e2e ~30 s, Playwright UAT ~40 s) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/unit -x -q` (or `cd frontend && npm run test:unit -- --run` for frontend tasks)
- **After every plan wave:** Run full suite
- **Before `/gsd-verify-work`:** Full suite must be green AND parity test green
- **Max feedback latency:** ~10 seconds (unit), ~120 seconds (full)

---

## Per-Task Verification Map

> Filled out by the planner once PLAN.md task IDs are assigned. RESEARCH.md `## Validation Architecture` enumerates the observable surfaces and required failure-mode coverage; rows below align to those surfaces.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-00-W0-Q2 | 00 | 0 | V3-LLM-OPT-IN | — | Resolve Reconquista Unity loader strictness on unknown JSON keys (flips `_ZIP_BOUND_FIELDS`) | manual+unit | `pytest tests/unit/test_overlay_merge_strict_bound.py` | ❌ W0 | ⬜ pending |
| 07-00-W0-AUTH | 00 | 0 | V3-LLM-OPT-IN | — | Anthropic `AsyncAnthropic.messages.stream` end-to-end: 401-degrade path + success path | integration | `pytest tests/integration/test_claude_auth_chain.py -m anthropic` | ❌ W0 | ⬜ pending |
| 07-XX-PARITY | parity | last | V3-LLM-OPT-IN, V3-PIPELINE-PARITY | — | Pipeline produces byte-identical output WITHOUT overlay (zero-LLM stays green) | parity | `pytest tests/parity/test_iberia_868_yaml.py::test_zero_llm_byte_identical` | ❌ W0 | ⬜ pending |
| 07-XX-MERGE | overlay | early | V3-LLM-OPT-IN | — | `merge_overlay()` is pure + non-destructive + preserves `original_idx` on every condado it touches | unit | `pytest tests/unit/test_overlay_merge.py` | ❌ W0 | ⬜ pending |
| 07-XX-CACHE-HIT | cache | mid | V3-LLM-OPT-IN | — | SHA-256 cache key hit returns persisted payload; miss runs provider; force-refresh bypasses | unit | `pytest tests/unit/test_research_cache.py` | ❌ W0 | ⬜ pending |
| 07-XX-CRED | cred | mid | V3-LLM-OPT-IN | T-07-CRED-LEAK | Claude auth chain falls through CLI → DB → env → dialog when each source empty | unit | `pytest tests/unit/test_credential_store.py` | ❌ W0 | ⬜ pending |
| 07-XX-SSE | research-api | mid | V3-LLM-OPT-IN | — | `GET /api/v3/research/stream/{run_id}` emits `data: {"stage":...,"elapsed_ms":N}\n\n` per stage; cancel aborts | integration | `pytest tests/integration/test_research_sse.py` | ❌ W0 | ⬜ pending |
| 07-XX-OLLAMA-HEALTH | ollama | mid | V3-LLM-OPT-IN | — | `GET /api/v3/research/providers` reports Ollama disabled when localhost:11434 unreachable | unit | `pytest tests/unit/test_ollama_health.py` | ❌ W0 | ⬜ pending |
| 07-XX-EXPORT-MERGE | export-zip | late | V3-LLM-OPT-IN | — | `build_unity_zip` merges overlay in-memory; raw on-disk metadata untouched; MANIFEST records `research_overlay_applied: true` | e2e | `pytest tests/e2e/test_research_overlay_iberia.py` | ❌ W0 | ⬜ pending |
| 07-XX-UI-RESEARCH | frontend | late | V3-LLM-OPT-IN | — | InspectorSidebar placeholder shows "Pesquisar metadados históricos"; dialog opens; SSE renders per-stage progress; success closes dialog and refreshes canvas with merged names | playwright | `cd frontend && npx playwright test research_dialog.spec.ts` | ❌ W0 | ⬜ pending |
| 07-XX-UI-EXPORT-422 | frontend-export | late | V3-LLM-OPT-IN, V3-EXPORT-GATE | — | Phase 06 absorption — Export button calls `/api/v3/projects/{id}/export`; each of 6 stable codes (`COLOR_COLLISION`, `OCEAN_LEAK`, `MISSING_ORIGINAL_IDX`, `TERRITORY_TOO_SMALL`, `PIXEL_CENTER_OUT_OF_RANGE`, `SCHEMA_INVALID`) renders with PT-BR translation | playwright | `cd frontend && npx playwright test export_v3_error_envelope.spec.ts` | ❌ W0 | ⬜ pending |
| 07-XX-UI-BADGE | frontend | late | V3-LLM-OPT-IN | — | InspectorSidebar condado/barony mode shows "Pesquisa aplicada" badge when overlay covers selected territory | playwright | `cd frontend && npx playwright test research_badge.spec.ts` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

> Each unique observable surface enumerated in RESEARCH.md `## Validation Architecture` is represented by at least one row above; planner expands each row into concrete task IDs and confirms `File Exists` once Wave 0 lands the test scaffolds.

---

## Wave 0 Requirements

- [ ] `backend/tests/unit/test_overlay_merge.py` — `merge_overlay` non-destructive, preserves `original_idx`, idempotent
- [ ] `backend/tests/unit/test_overlay_merge_strict_bound.py` — verifies `_ZIP_BOUND_FIELDS` actually drops unknown keys from zip-bound dict
- [ ] `backend/tests/unit/test_credential_store.py` — fixtures for each auth-chain branch (CLI / DB / env / dialog) with explicit byte content
- [ ] `backend/tests/unit/test_research_cache.py` — explicit SHA-256 cache-key fixtures (country_qid, period, provider, model)
- [ ] `backend/tests/unit/test_ollama_health.py` — mocked httpx responses for healthy / unreachable Ollama
- [ ] `backend/tests/unit/test_llm_schemas.py` — `ResearchResult` / `MapResearchResult` validation with explicit numeric fixtures
- [ ] `backend/tests/unit/test_llm_retry.py` — 3-retry loop with error-in-prompt feedback
- [ ] `backend/tests/unit/test_llm_parse.py` — lenient JSON parser (strip extra top-level keys)
- [ ] `backend/tests/integration/test_claude_auth_chain.py` — anthropic `AsyncAnthropic.messages.stream` integration; 401-degrade path + success path; gated by `pytest -m anthropic` (skipped when no creds available)
- [ ] `backend/tests/integration/test_research_sse.py` — SSE shape per stage + cancel abort
- [ ] `backend/tests/e2e/test_research_overlay_iberia.py` — Iberia run → fixture overlay → export → assert merged names + `research_overlay_applied: true` in MANIFEST
- [ ] `backend/tests/parity/test_iberia_868_yaml.py` — extend with `test_zero_llm_byte_identical` non-skippable assertion
- [ ] `frontend/tests/uat/playwright/research_dialog.spec.ts` — open dialog → submit → assert SSE progress + post-success refresh
- [ ] `frontend/tests/uat/playwright/research_badge.spec.ts` — overlay present → assert "Pesquisa aplicada" badge on covered condado
- [ ] `frontend/tests/uat/playwright/export_v3_error_envelope.spec.ts` — Phase 06 absorption: 422 envelope renders each of 6 codes in PT-BR
- [ ] `backend/tests/conftest.py` — shared fixtures: tmp `project_dir` with optional `research_overlay.json`, mocked Anthropic client, mocked Ollama client
- [ ] `frontend/tests/uat/playwright/fixtures/research_overlay.json` — canned overlay covering 3 condados for badge + dialog tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Reconquista Unity loader tolerance for unknown JSON keys (Open Q2 / Wave 0 gate) | V3-LLM-OPT-IN | Requires loading a Reconquista build with a sample merged `territory_metadata.json` in the Unity editor / play mode | (1) `pytest tests/unit/test_overlay_merge_strict_bound.py` to produce both strict and tolerant outputs in `tests/fixtures/`; (2) copy each into a `Reconquista/Assets/StreamingAssets/Maps/...` test build; (3) open Reconquista, attempt to load the map; (4) record whether the loader accepts/rejects unknown keys. Outcome flips `_ZIP_BOUND_FIELDS` constant. |
| `claude auth status` parsing on real Anthropic API-account user (Open Q1) | V3-LLM-OPT-IN | Cannot ship a real consumer-OAuth token to CI; pitfall 4 documents the consumer-OAuth-vs-API-key ambiguity | Run `claude auth status` on a fresh Anthropic-API-account machine; record exit code + stdout shape; confirm degrade-on-401 path triggers expected fall-through to DB / env / dialog |
| CLI piggyback file path discovery on Windows vs macOS vs Linux | V3-LLM-OPT-IN | Cross-platform file probe; CI runs Linux only by default | On Windows: confirm `%APPDATA%\Claude\.credentials.json` is the location; on macOS: confirm `~/.claude/.credentials.json`; on Linux: same. Record per-OS path in `services/credential_store.py`. |
| PT-BR dialog copy review with a native speaker | V3-LLM-OPT-IN | Translation quality is subjective | Review each PT-BR string in `i18n/exportErrors.ts` + ResearchDialog labels with native PT-BR speaker (user) before UAT sign-off |
| Visual fidelity of Radix Dialog vs ParameterSidebar aesthetic | V3-LLM-OPT-IN | Subjective visual judgment | Side-by-side screenshot review during UAT |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (test scaffolds + parity extension + Q2 strict-bound test + Q1 anthropic integration test)
- [ ] No watch-mode flags
- [ ] Feedback latency < 10 s (unit) / < 120 s (full suite)
- [ ] `nyquist_compliant: true` set in frontmatter once planner fills concrete task IDs

**Approval:** pending
