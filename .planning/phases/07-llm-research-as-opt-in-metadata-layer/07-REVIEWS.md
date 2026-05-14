---
phase: 07
reviewers: [codex, opencode, gemini-unavailable]
reviewed_at: 2026-05-14T09:59:33Z
plans_reviewed:
  - 07-00-PLAN.md
  - 07-01-PLAN.md
  - 07-02-PLAN.md
  - 07-03-PLAN.md
  - 07-04-PLAN.md
  - 07-05-PLAN.md
  - 07-06-PLAN.md
  - 07-07a-PLAN.md
  - 07-07b-PLAN.md
  - 07-08-PLAN.md
  - 07-09a-PLAN.md
  - 07-09b-PLAN.md
  - 07-10-PLAN.md
  - 07-11-PLAN.md
---

# Cross-AI Plan Review — Phase 07 (LLM research as opt-in metadata layer)

## Gemini Review

_Unavailable — Gemini CLI returned HTTP 429 (Too Many Requests) on all retries during this review window. Re-run `/gsd-review --phase 07 --gemini` after quota resets to capture this perspective._

---

## Codex Review

## Summary

The Phase 07 plan set is unusually thorough and mostly coherent. The core architecture is sound: LLM research is isolated as a per-project sidecar, raw pipeline output remains deterministic, merge happens only at consumer boundaries, and the zero-LLM path is explicitly protected by parity tests. The plans also do a good job incorporating prior v1 lessons without reviving v1 dead code wholesale. Main risks are scope size, some dependency-order inconsistencies, literal-port fragility, and a few places where implementation instructions are too prescriptive or internally inconsistent with earlier decisions.

## Strengths

- Clear separation between geometry and research metadata. `research_overlay.json` as a sidecar is the right boundary for preserving determinism.
- Strong parity posture. D-12, zero-overlay tests, sha256 no-write checks, and validate-before-merge ordering directly target the most important regression class.
- Good consumer-boundary design. Reusing one `merge_overlay()` function for both zip export and artifact serving avoids duplicated merge semantics.
- Provider scope is pragmatic. Claude + Ollama gives one high-quality option and one local/offline option without exploding provider complexity.
- Security thinking is present. Credential payload leakage, SSE content rendering, shell-out restrictions, and path traversal are all called out.
- The Plan 00 Unity-loader verdict gate is valuable. It prevents silently breaking the downstream Unity consumer with extra metadata fields.
- Frontend integration is split better after 09a/09b. Keeping `ResearchDialog` creation separate from `InspectorSidebar` wiring reduces blast radius.
- Phase 06 export-button absorption is justified. Phase 07 success criterion #1 depends on export working without API keys.

## Concerns

- **HIGH: Scope is very large for one phase.** Backend LLM providers, DB migrations, cache, SSE orchestration, overlay export merge, artifact merge, credentials UI, research dialog, InspectorSidebar integration, export UI repair, Playwright UAT, and manual UAT are all in one phase. Even with split plans, this is close to a mini-release.
- **HIGH: Plan 11 depends on `07b`, `09a`, `09b` but uses mixed numeric dependency notation.** Some plans use `depends_on: [07a, 07b]`, others use numeric-like `[01, 02]`. If tooling expects integers or fixed `{NN}` names, the split suffixes may break ordering unless the checker explicitly supports them.
- **HIGH: Plan 05 extends export schema with `kingdom_owner` and `historical_notes` even if Plan 00 verdict is Strict.** That is probably fine internally, but it partially weakens the "Strict means only name goes zip-bound" story. The schema will accept fields even if zip merge excludes them. This is not a functional bug, but the contract should be explicit: schema tolerance is broader than zip-bound emission.
- **HIGH: Claude CLI piggyback may be over-promised.** The plans correctly include 401 fallback, but the UI/UX still risks implying CLI auth is a supported zero-setup path. If consumer Claude tokens reliably fail Anthropic API access, this becomes a confusing dead first step.
- **MEDIUM: Literal-port byte-identical enforcement conflicts with import normalization and behavioral adaptation.** Plans 02/03 demand byte-identical ports while also allowing import changes and later requiring SSE-shape compatibility decisions. That is brittle. A strict diff gate may waste time if Pydantic, package paths, or app conventions require small changes.
- **MEDIUM: `research_cache` key may not include enough geography context.** It uses `country_qid`, period, provider, model, prompt version. If two regions share country/period but have different condado geometry or different region YAML curation, cached assignments could mismatch current project condado IDs. The matcher drops unknown IDs, but that could produce low coverage.
- **MEDIUM: `prompt_version = "v1"` is too manual.** The plan says bump when prompt changes, but human discipline is weak. A prompt hash or schema hash would reduce stale-cache risk.
- **MEDIUM: Overlay meta sidecar is written on cache hit using current request metadata.** That is useful for UI, but it can blur whether `created_at` means "research originally generated" or "overlay applied from cache." The UI copy says "Última pesquisa", so a cache-hit timestamp could be misleading.
- **MEDIUM: SSE single-flight keyed only by project may block legitimate retry/replace behavior.** The stop endpoint handles cancellation, but plans should define behavior if a start request arrives after a crashed producer but before cleanup.
- **MEDIUM: Plan 07b endpoint shape says `/providers` returns health.** If `GET /providers` health-checks Claude/Ollama every 15s while dialog is open, CLI checks, DB reads, and Ollama network probes could become noisy. Cache provider health for a short TTL or make health checks cheap.
- **MEDIUM: Frontend tests rely heavily on implementation details.** Many grep-based acceptance criteria check exact strings, inline styles, and component internals. Useful as guardrails, but they can make harmless refactors painful.
- **LOW: `historical_notes` max length is mentioned in threat model but not fully propagated.** Plan 05 says add `Field(max_length=2048)`, Plan 06 matcher just passes through `condado.get("historical_notes")`. Make sure validation occurs before write, not only during later load.
- **LOW: Date formatting in Plan 09b is timezone-sensitive.** Formatting ISO UTC with local browser time may make Playwright assertions brittle. Use a stable formatting expectation or explicitly accept local timezone.
- **LOW: Manifest version bump to 3 may affect existing consumers.** This is likely acceptable, but tests should include any manifest parser that expects version 2.

## Suggestions

- Add a short dependency graph sanity check before execution:
  - 00 before 05/08
  - 01 before 04/07a/07b
  - 02 before 03/05/06
  - 03 before 04/09a SSE decision
  - 05 before 06/07b/08
  - 07b before 09a
  - 09a before 09b
  - 10 independent after 08
  - 11 last
- Split Phase 07 delivery into two merge gates:
  - Backend gate: plans 00-08 plus parity/e2e.
  - Frontend gate: plans 09a-11.
  This reduces integration risk and makes rollback easier.
- Change cache key to include a stable geometry or condado-list digest:
  `sha256(country_qid|period|provider|model|prompt_version|condado_ids_digest)`.
  This prevents cache reuse across incompatible region geometries.
- Treat Claude CLI piggyback as "detected, attempted, may require API key" in UI copy. Avoid promising zero-setup unless an actual API call succeeds.
- Add explicit overlay coverage metrics:
  - runner meta: `covered_count`, `total_condados`, `coverage_ratio`
  - UI can warn if research only covered a subset.
  This helps catch cache mismatch and LLM partial failures.
- Make `created_at` semantics explicit:
  - `generated_at` for original LLM/cache payload creation
  - `applied_at` for when project overlay was written
  This avoids misleading "Última pesquisa" copy on cache hits.
- Replace the manual `PROMPT_VERSION = "v1"` discipline with a prompt/schema digest if practical.
- In Plan 05, validate `historical_notes` max length at overlay creation time and load time. The runner should truncate or reject oversized notes before atomic write.
- In Plan 09a, conditionally simplify dual-shape SSE parsing based on Plan 03's verdict instead of keeping both forever if unnecessary.
- Add a test for "corrupt overlay file does not break zero-LLM export unexpectedly" or deliberately define that corrupt overlay makes export fail loudly. Current plan says validation error fails loudly, which is defensible, but the UX should be intentional.
- Add one test that validates no provider is called during normal pipeline generation/export without overlay. This directly protects SC #1 beyond byte parity.

## Risk Assessment

**Overall risk: MEDIUM-HIGH.**

The architecture is strong and directly protects the phase's most important invariant: zero-LLM deterministic generation/export. The remaining risk comes from implementation volume and integration breadth rather than a flawed design. The largest technical risks are cache reuse against mismatched condado sets, Claude CLI auth ambiguity, and frontend/backend SSE/overlay contract drift. With the suggested cache-key hardening, explicit metadata semantics, and a two-gate execution strategy, this plan would drop closer to **MEDIUM** risk.

---

## OpenCode Review

## Phase 07 Plan Review

### Summary

This is a structurally sound plan set implementing an opt-in LLM research layer for Medieval Forge v3. The architecture is clean: non-destructive overlay merge via a single `merge_overlay()` function, SQLite-backed credential/cache persistence, SSE orchestration mirroring existing `generate.py` patterns, and a three-layer test pyramid with explicit parity gates. The literal-port strategy for the 4 stateless artifacts from `87f8aab~1` is well-justified. The most significant risks are (1) the Q2 Wave 0 verdict being an unresolved human checkpoint on the critical path, (2) Ollama's default model not being installed on the machine, and (3) a dual-shape SSE tolerance that adds complexity but may be unnecessary.

### Strengths

- **Literal-port discipline** — 4 stateless files ported verbatim from `87f8aab~1` with attribution comments; behavioral modifications explicitly prohibited. NIT 2 enforces byte-identity via diff.
- **Non-destructive merge architecture** — `merge_overlay()` is the single source of truth called at two consumer boundaries (zip + artifact endpoint). `deepcopy` at top guarantees input immutability. Phase 06 parity (11/11) stays green.
- **D-12 parity lock** — `test_zero_llm_byte_identical` is non-skippable; any commit that regresses zero-LLM geometric determinism fails CI.
- **Blocking gates correct** — Plan 00 Q2 verdict gates Plan 05's `_ZIP_BOUND_FIELDS`; Plan 01 DB foundation gates Plans 04/07a/07b.
- **Auth chain is well-specified** — 4-step chain (CLI → DB → env → dialog) with 401-degrade in `ClaudeProvider.research()`; no credential payload leaks via `/providers`.
- **Pitfall mitigations explicit** — Pitfall 4 (consumer-OAuth) handled with explicit retry-on-401; Pitfall 5 (model not installed) handled with auto-discovery + hint; Pitfall 9 documented with dual-shape SSE tolerance.
- **Test pyramid is comprehensive** — 14 test files across unit/integration/parity/e2e/UAT layers with descriptive names + explicit numeric fixtures.
- **DRY enforcement** — Test 4 in `test_overlay_merge_strict_bound.py` cross-checks the `_ZIP_BOUND_FIELDS` constant against the verdict file, catching drift.
- **Phase 06 absorption is explicit** — D-10 scoped cleanly; WARNING 4 deletes the legacy `useExport` hook from `client.ts` (no transitional shims per D-V3-04).
- **Threat model covers the surface** — subprocess shell=False, no key exfiltration, Pydantic `extra='forbid'`, path containment via `project_dir()`.

### Concerns

**HIGH**

1. **Q2 verdict is a human checkpoint on the critical path.** Plan 00 → human-approve → Plan 05 cannot start until approved. If the user is unavailable or defers, the entire Phase 07 execution stalls. The conservative fallback (`Unverifiable-default-Strict`) is safe but ships the minimal feature (only `name` in zip; `kingdom_owner`/`historical_notes` UI-only). *Mitigation: clarify in the checkpoint prompt that the fallback is production-safe; require explicit rejection, not explicit approval.*
2. **Ollama default model `qwen2.5:7b` is not installed** (verified in RESEARCH §Environment Availability). Available models: `gemma4:26b`, `qwen2.5-coder:14b`, `deepseek-r1:14b`. The hint text ("execute `ollama pull qwen2.5:7b`") is good, but Plan 04's OllamaProvider won't actually work on this machine out of the box. The `qwen2.5-coder:14b` model is installed and could serve as the effective default, but there's no plan to detect/suggest it. *Mitigation: Plan 04's `/providers` endpoint should surface `available_models` from `client.list()` and the UI should recommend from that list.*

**MEDIUM**

3. **Dual-shape SSE tolerance may be unnecessary.** WARNING 3 verdict (captured in Plan 03 SUMMARY) determines whether `retry.py` emits raw PT-BR text to a queue or raises exceptions that the runner catches to emit structured envelopes. If verdict is (b) (retry only raises), the dual-shape parser in `useResearchStream` is defensive-but-redundant. The current default (dual-shape) is conservative, but it means Plans 09a/09b ship more complex SSE parsing than strictly necessary. *Suggestion: Plan 03 should run BEFORE Plan 09a's `useResearchStream` implementation so the verdict is known before the SSE consumer is written.*
4. **`_write_json_atomic` vs `_write_geojson_atomic` mismatch.** Plan 07b's runner implements `_write_json_atomic` (its own function), while `paths.py` already has `_write_geojson_atomic`. These are conceptually identical (tmp+replace), but they are separate implementations. If `_write_geojson_atomic` gains a signature change in a future phase, `_write_json_atomic` won't track it. *Suggestion: runner.py should import and call `paths._write_geojson_atomic` (renamed conceptually if needed), not reimplement.*
5. **`date-fns` availability not confirmed.** Plan 09b assumes `date-fns` is available (used in the `formatDate` helper) but doesn't verify it against `package.json`. The inline implementation is a fine fallback, but if `date-fns` IS available, the inline code is dead weight. *Suggestion: check `frontend/package.json` for `date-fns` before writing the inline formatter.*
6. **Test 6 in `test_overlay_merge.py` (corrupt file → `ValidationError`)**: `load_overlay_if_exists` validates via `ResearchOverlay.model_validate()` before returning. However, if `json.loads()` fails first (malformed JSON, not schema-invalid), the exception is uncaught and propagates. The test should cover both: (a) `JSONDecodeError` for malformed JSON, (b) `ValidationError` for schema-invalid JSON. The current Test 7 only covers schema-invalid.

**LOW**

7. **`historical_notes` size cap not enforced in `CondadoOverlayEntry`.** RESEARCH §Field Semantics says "cap at 2KB per condado" and T-07-05-05 suggests `Field(default=None, max_length=2048)`. But the code in `overlay.py` Pattern 5 does not show the `Field()` constraint. If the cap isn't in the Pydantic model, an LLM can return unbounded notes and inflate `research_overlay.json`. *Fix: add `from pydantic import Field` and `historical_notes: str | None = Field(default=None, max_length=2048)` to `CondadoOverlayEntry`.*
8. **Ollama heartbeat is 3s period** — `asyncio.sleep(3.0)` in the heartbeat task. For a research run that takes 60-120s, this is 20-40 heartbeat events emitted. This is fine for Ollama (already running), but the heartbeat events (`event_type: heartbeat`) need to be rendered in `ResearchProgress` or silently ignored. The UI spec doesn't mention heartbeat rendering. *Suggestion: document whether heartbeat events are visible to the user or handled silently.*
9. **`PROVIDERS` empty during wave 1.** Plan 03 lands the registry skeleton with `PROVIDERS: dict[str, LLMProvider] = {}`. Plan 04 (wave 2) populates it via `register()` calls in `__init__.py`. If an intermediate task or test imports `services.llm` during wave 1-2 and expects providers, it gets an empty dict. This is intentional (deferred-population shim) but worth noting. The test `test_llm_registry.py` is in Plan 04 (wave 2), not Plan 03, which is correct — it won't run until providers exist.
10. **Retry exhaustion is not explicitly tested.** Plan 04's `test_claude_auth_chain_falls_through_to_db_when_cli_token_rejected_with_401` tests the skip-CLI retry path. But `test_claude_research_raises_when_both_cli_and_db_keys_yield_401` tests the "chain exhausted" path. However, the behavior when ANTHROPIC_API_KEY is set AND yields 401 is not explicitly tested. The chain says "env → dialog" but a 401 from env key would also exhaust. The retry-with-skip-CLI only skips the CLI step, not the env step. *Suggestion: add test case for env-key-401 → raises after chain exhaustion.*

### Suggestions

1. **Add a `TestCache: research_overlay.json grows unbounded`** — A fixture with 91 condados each with `historical_notes = "x" * 2048` (~185KB) passed through `merge_overlay()` should complete in <10ms. Profile to confirm.
2. **Plan 07b Task 2**: The overlay endpoint at `GET /api/v3/projects/{id}/research/overlay` returns `{exists, covered_condado_ids, meta}`. The `meta` field is trimmed to `{provider, model, created_at}` — but `created_at` is ISO 8601. The UI formats it as `YYYY-MM-DD HH:mm`. Consider also returning `country` and `period` in `meta` so the microcopy can render "Pesquisa: Iberia 868 AD · claude · 2026-05-14" instead of just "claude". Currently the microcopy only shows `{provider} · {model}` per UI-SPEC §Surface 2 line 184.
3. **Plan 07-00 task description**: The NIT 1 retry guidance says "run `grep` on D:/ drive yourself." If the user is remote, they may not have the D:/ drive mapped. Consider adding a Windows network path alternative or clarifying that the conservative fallback is acceptable.
4. **Plan 09b Task 1**: The `formatDate` inline helper assumes UTC. If the server is in a different timezone, `created_at` (stored as UTC ISO 8601) will render as the correct UTC time, not the user's local time. Consider using `Intl.DateTimeFormat` or a local timezone-aware formatter. Low severity (UTC is deterministic and unambiguous).
5. **Add rollback guidance to Plans 01 and 05**: If the Alembic migration 0006 is applied and then Phase 07 is abandoned, rolling back the migration drops the tables. This is fine. But if Plan 05's schema extension (`kingdom_owner`/`historical_notes`) is rolled back after data has been written to those columns, the columns persist (SQLite doesn't enforce schema-at-insert-time). Add a note that dropping Phase 07 requires a migration to drop the new columns, not just reverting the Python code.

### Risk Assessment

**MEDIUM**

The plan set is architecturally sound and the test coverage is thorough. The primary risks are execution-order dependencies (Q2 verdict → human checkpoint) and the Ollama default-model mismatch. The dual-shape SSE tolerance is a defensive over-engineering that adds test surface but isn't wrong. The plaintext credential storage is a documented and accepted risk. The phase can be completed successfully with the suggestions above incorporated, but the human checkpoint in Plan 00 creates a sequential dependency that could stall the wave-based parallelization if the user is unavailable.

**Confidence in plan quality: HIGH.** Confidence in execution smoothness: MEDIUM (human checkpoint + Ollama model gap).

---

## Consensus Summary

Two independent reviewers (Codex, OpenCode) converged on the same architectural verdict: the plan set is structurally sound, the merge/overlay/parity story is correctly designed, and the principal risks are execution-side rather than design-side. Both rate overall risk in the **MEDIUM** band (Codex: MEDIUM-HIGH leaning to MEDIUM with suggested mitigations; OpenCode: MEDIUM). Gemini perspective is missing due to 429 rate-limit.

### Agreed Strengths

- Single-source-of-truth `merge_overlay()` called at both consumer boundaries (zip + artifact endpoint) — preserves Phase 06 parity.
- D-12 non-skippable zero-LLM parity test directly defends Success Criterion #1.
- Plan 00 Unity-loader verdict as a hard gate before Plan 05's `_ZIP_BOUND_FIELDS`.
- Literal-port discipline on the 4 stateless artifacts from `87f8aab~1` (with diff-enforced byte-identity).
- 4-step Claude auth chain (CLI → DB → env → dialog) with explicit 401-skip-CLI retry.
- Phase 06 export-button absorption is correctly scoped into Plan 10 with deletion (no shims).
- Threat model covers credential leakage, prompt injection, path containment, subprocess hardening.

### Agreed Concerns (highest priority — raised by both reviewers)

1. **Plan 05 schema vs. `_ZIP_BOUND_FIELDS` semantics (HIGH/MEDIUM).** Both flag that the Pydantic schema's tolerance for `kingdom_owner` / `historical_notes` is broader than what the zip emits under Strict; contract needs to be explicit. Codex frames it as a contract-clarity gap; OpenCode adds the missing `Field(max_length=2048)` enforcement on `CondadoOverlayEntry`.
2. **Date / `created_at` semantics ambiguity (MEDIUM/LOW).** Both worry the microcopy "Última pesquisa: …" conflates generated-time vs applied-from-cache time. Codex suggests `generated_at` + `applied_at`; OpenCode flags timezone formatting brittleness in Plan 09b.
3. **Dual-shape SSE / WARNING 3 over-engineering (MEDIUM).** Both want Plan 03's verdict to land before frontend SSE parser commits to dual-shape. Codex: conditional simplification post-verdict. OpenCode: reorder so Plan 03 runs before Plan 09a's `useResearchStream`.
4. **`historical_notes` 2KB cap propagation (LOW).** Both note validation must occur at write-time on the Pydantic model, not only at later load.

### Divergent Views (worth investigating)

- **Scope size:** Codex calls Phase 07 a near-mini-release and recommends splitting into two merge gates (backend 00–08, frontend 09a–11). OpenCode treats the 14-plan split as adequate and does not flag scope itself as HIGH risk.
- **Cache key geography:** Codex flags `country_qid|period|provider|model|prompt_version` as insufficient and recommends adding a `condado_ids_digest`. OpenCode does not raise cache-key fragility; it accepts the matcher's drop-unknown-IDs as enough.
- **Claude CLI piggyback UX:** Codex calls it "over-promised" as zero-setup and wants UI copy softened. OpenCode rates the 4-step auth chain as a strength and does not flag UX framing.
- **`PROMPT_VERSION = "v1"` discipline:** Codex wants a prompt/schema digest replacing manual bumps. OpenCode does not raise this.
- **Q2 Wave 0 human-checkpoint risk:** OpenCode rates this as a HIGH execution risk (blocks wave parallelization) and asks the checkpoint copy be reframed to "require explicit rejection, not approval." Codex does not flag the checkpoint as a HIGH risk per se.
- **Ollama default model gap:** OpenCode flags HIGH that `qwen2.5:7b` is not installed and Plan 04 won't run out-of-box on this machine; recommends surfacing `available_models` in `/providers`. Codex does not raise the missing-model gap.
- **Test brittleness:** Codex flags many grep-based acceptance criteria as making refactors painful. OpenCode treats the same as DRY enforcement and a strength.

### Recommended Action Before Execution

1. Make `_ZIP_BOUND_FIELDS` contract explicit in Plan 05 (schema-accepted vs zip-emitted) and add the `Field(max_length=2048)` constraint on `CondadoOverlayEntry`.
2. Split `created_at` semantics into `generated_at` + `applied_at`; update microcopy in 09b.
3. Reorder so Plan 03 verdict is fixed before Plan 09a `useResearchStream` implementation.
4. Adopt Codex's cache-key digest suggestion if cross-region/cross-curation cache reuse is plausible.
5. Adopt OpenCode's `/providers` `available_models` surfacing for Ollama, and confirm `qwen2.5:7b` install (or change default) before Plan 04 executes.
6. Decide on the two-gate merge strategy (Codex) vs single phase merge before kicking off the execute-phase run.

To feed this back into planning:

    /gsd-plan-phase 07 --reviews
