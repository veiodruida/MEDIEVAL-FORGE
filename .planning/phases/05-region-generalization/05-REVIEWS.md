---
phase: 05
reviewers: [gemini, opencode, deepseek-v4-flash]
reviewed_at: 2026-05-12T09:59:05Z
deepseek_appended_at: 2026-05-12T10:08:00Z
plans_reviewed: [05-01-PLAN.md, 05-02-PLAN.md, 05-03-PLAN.md, 05-04-PLAN.md, 05-05-PLAN.md, 05-06-PLAN.md, 05-07-PLAN.md, 05-08-PLAN.md, 05-09-PLAN.md, 05-10-PLAN.md]
skipped: [claude (self), codex (TOML hooks parse error in user config + 401 auth in fallback)]
---

# Cross-AI Plan Review — Phase 05

## Gemini Review

This is a high-quality, comprehensive, and low-risk set of plans. The detailed breakdown, adherence to a safe migration pattern ("structure -> migrate -> delete"), and extensive, multi-layered testing strategy provide high confidence in a successful outcome.

### 1. Summary

The plans for Phase 05 ("Region Generalization") are exceptionally well-crafted. They outline a robust strategy to refactor a hard-coded configuration into a flexible, data-driven YAML system. The core strength lies in the rigorous, safety-first sequencing, which ensures the existing "Iberia" functionality remains verifiable and regression-free throughout the migration via a hard parity gate. The plans demonstrate deep integration with the preceding research, systematically addressing identified pitfalls and security concerns. By breaking the work into ten discrete, verifiable steps, the phase is manageable, and its success is measurable at every stage.

### 2. Strengths

*   **Risk Mitigation**: The "parity gate stays green" principle is brilliantly executed. Establishing the YAML parity test (Plan 05-03) *before* deleting the legacy code (Plan 05-05) is a textbook example of a safe refactoring pattern. The pre-deletion audit in Plan 05-05 further exemplifies this safety-first approach.
*   **Attention to Detail**: The plans address subtle but critical implementation details that are often missed. This includes using `op.batch_alter_table` for SQLite compatibility (Plan 05-04), preventing singleton mutation of cached objects with `dataclasses.replace` (Plan 05-04), and correcting file-path anchor logic across different modules (Plans 05-04, 05-07).
*   **Comprehensive Testing**: The validation strategy is outstanding. It covers the full testing pyramid: unit tests for new logic and error paths (05-01, 05-06, 05-09), a critical parity test for regression (05-03), integration tests for API and database changes (05-04), and a final E2E contract test complemented by a manual Playwright UAT (05-10).
*   **Excellent Documentation & Traceability**: The plans are tightly linked to the `CONTEXT.md` decisions and `RESEARCH.md` findings. For instance, Plan 05-01 adds the missing `PyYAML` dependency, and Plan 05-04 creates a new v3 project route, directly resolving issues flagged in research. This ensures decisions are implemented and knowledge is not lost.

### 3. Concerns

*   **MEDIUM: Incomplete Initial Audit**: The `RESEARCH.md` document initially missed several test files that imported the symbols targeted for deletion. Plan 05-05 correctly identifies and migrates these files after a more thorough audit. While the plan itself is now correct, this points to a potential weakness in the initial investigation process. An incomplete audit could lead to breakage if not caught by such a diligent execution plan.
*   **LOW: Inconsistent `wave` Metadata**: The `wave` numbers across the plans (e.g., 2, 3, 4, 5) do not strictly follow a linear sequence, which can be slightly confusing for a human reviewer. The `depends_on` array correctly enforces the execution order, making this a minor clerical issue with no technical impact.
*   **LOW: Ambiguity in UI Legacy Path**: Plan 05-08 gives the executor discretion on how to handle the UI link to the legacy project creation page. This could result in an "orphaned" page that is still accessible via URL but has no UI entry point. While low-impact, it leaves a piece of the old implementation in an ambiguous state.

### 4. Suggestions

*   **Formalize Pre-Refactor Audits**: Incorporate mandatory, repo-wide `grep` searches for all symbols targeted for deletion or modification into the `RESEARCH.md` template. This would make the discovery process more robust and prevent corrective actions like the one seen in Plan 05-05.
*   **Clarify Wave Terminology**: For future milestones, either enforce a strict sequential numbering for `waves` or add a sentence to the planning template clarifying that waves are for logical grouping and the `depends_on` field is the sole source of truth for scheduling.
*   **Prescribe UI Legacy Fate**: Update Plan 05-08 to include a specific instruction for the legacy link, such as: "The `<Link to=\"/projects/new\">` component should be removed from the `ProjectList` page. The route and its backing component (`ProjectNew.tsx`) must remain untouched for now."

### 5. Risk Assessment

**Overall Risk: LOW**

This phase is a significant architectural change, yet the execution risk is remarkably low. The planning methodology is the primary mitigating factor. By building a safety net (the parity test) before touching the high wire, the process ensures that the most valuable existing functionality is never compromised. The detailed, incremental nature of the plans, combined with continuous verification, security-mindedness, and direct mitigation of researched pitfalls, leaves very little room for error. The identified concerns are minor and do not materially affect the probability of a successful outcome.

### Per-Plan Notes (Gemini)

**05-02 (MEDIUM risk)** — `CONDADOS` transformation for YAML output (RESEARCH Pitfall 3) is not adequately addressed in the script outline. Manual field mapping introduces risk of functional discrepancy if not precisely handled by executor.

**05-03 (LOW)** — `dataclasses.replace` enforcement should be explicit instruction rather than conditional suggestion.

**05-04 (LOW)** — `_autogen_territories` reliability for france_1066/england_1216 depends on Plan 05-01.

**05-05 (LOW)** — `backend/medieval_forge/data/regions/iberia_868/__init__.py` fate not definitively prescribed.

**05-06 (MEDIUM)** — Voronoi `_voronoi_polygons` drops infinite regions (~6–10 of N=50). Acceptance criteria `>=40 and <=50` accommodates, but acknowledge in code comment (RESEARCH Pitfall 10).

**05-07 (LOW)** — Endpoint re-parses all YAMLs per request; `display_name` fallback to `key` is not always user-friendly.

**05-08 (LOW)** — `useCreateV3Project` vs extending `useCreateProject`: noted as a deliberate choice consistent with new v3 endpoint in 05-04.

**05-09 (LOW)** — Missing `display_name: England 1216 AD` in YAML.

**05-10 (LOW)** — Playwright text selectors (`'Novo projeto'`, `/concluído|complete|done/i`) fragile; prefer `data-test-id`. Confirm `run_pipeline` import path.

---

## OpenCode Review (minimax-m2.5-free)

### Summary

Phase 05 is a well-structured, dependency-order-aware migration with strong parity gates and clear contract tests. The 17 locked decisions constrain the phase tightly, the D-17 sequencing rule (parity gate before deletion) is correctly implemented, and the architecture (loader → YAML → deletion) follows the proven migrate-before-delete pattern. The main risks are subtle: France E2E async handling, migration script `dataset` dict construction, and a few test scaffold gaps that need filling before green runs are meaningful.

### Strengths

- **D-17 sequencing enforced**: Plans 05-03 (parity gate) → 05-04 (callsite swap) → 05-05 (deletion) is correctly ordered. The parity gate exists *before* `iberia_config()` disappears.
- **Security-first loader design**: regex key validation, `yaml.safe_load` only, path-escape guard via `relative_to()`, explicit-only cache — all five security layers are unit-tested in Plan 05-01.
- **Idempotent migration scripts**: France generator + Iberia migrator both re-run safely, verified by sha256 roundtrip tests.
- **Correct empty-input behavior verified**: RESEARCH confirmed `empty border_polygon` → all-False mask and `empty pt_duchies` → single global KD-tree require zero code changes.
- **SC-3 contract test correctly scoped**: France E2E asserts file presence + dimensions + JSON validity + `original_idx` uniqueness, NOT pixel content.
- **England YAML-only contract**: no `inputs/` directory created; `has_dataset: false` exercised through both loader error path and GET endpoint.
- **Frontend/Backend separation maintained**: `useCreateV3Project` is additive; `useCreateProject` + `ProjectNew.tsx` stay untouched.
- **`dataclasses.replace()` at every swap**: RESEARCH Pitfall 9 (cached singleton mutation) is explicitly mitigated in both `generate.py` and `render.py`.

### Concerns

**HIGH**

1. **Migration script `dataset` dict construction (05-02 Task 1)** — If script uses `cfg.dataset` (dataclass) directly instead of `{"pt_geojson": ..., ...}` dict, `yaml.safe_dump` would serialize as `!!python/object:apply:...` → pydantic validation fails → parity gate red. Fix: always construct the dict explicitly from `cfg.dataset.pt_geojson.name` (or path string).

2. **France E2E async handling (05-10 Task 1)** — `run_pipeline` is `async def`; calling synchronously raises `TypeError: coroutine was never awaited`. Fix: use `httpx.AsyncClient` / FastAPI `TestClient` hitting `POST /api/v3/projects/{id}/generate`, or `@pytest.mark.asyncio` + `await run_pipeline(cfg)`.

**MEDIUM**

3. **`output_dir` type in migration script (05-02)** — `RegionConfigSchema.output_dir: str` is required; if `iberia_config().output_dir` is `None` pre `__post_init__`, dataclass constructor fails. Fix: assert and extract explicitly: `assert cfg.output_dir, "must be set"`.

4. **`original_idx` in migrated `CONDADOS` (05-02)** — `TerritorySchema.original_idx: int` required. If `CONDADOS` positional tuples don't include it, migration fails or YAML omits → `ValidationError`. Fix: add `original_idx=i+1` in migration script (CLAUDE.md rule 4).

5. **`DatasetSchema.pt_geojson` required vs optional (05-01 Task 2)** — Required field means future regions accidentally omitting `dataset` raise `ValidationError` at load time rather than clear "no dataset" message. Fix: make `pt_geojson`, `es_input`, `mountain_river_json` optional with `None` default, then raise `FileNotFoundError` if all `None`.

6. **`parents[4]` depth verification missing explicit comment (05-04 Task 2, 05-07 Task 1)** — Brief comment risks future maintainers reverting. Fix: add permanent anchor comment: `# Path depth: .../api/v3/X.py → parents[4] = repo root. DO NOT change to parents[3].`

**LOW**

7. **`useCreateV3Project` query-key invalidation (05-08 Task 1)** — Plan says invalidates `['projects']`; if actual key is `['v3', 'projects']` or `['projects', 'list']`, invalidation misses. Fix: confirm exact query key in `client.ts`.

8. **Wave headers don't reflect execution order** — 05-07 (wave 3) executes before 05-05 (wave 5) but dependencies are correct. Could confuse orchestrators. Fix: align wave numbers with dependency depth, or note that waves are organizational only.

9. **Playwright UAT human checkpoint blocking (05-10 Task 2)** — `checkpoint:human-verify` blocks auto-advance. Mitigation: define explicit visual pass/fail criteria (e.g., "≥90% of map area non-white, no single-pixel artifacts at 100% zoom").

10. **France `es_input` self-reference (05-06 Task 1)** — `es_input: inputs/france_municipalities_toy.geojson` same as pt_geojson works (single-country fallback) but undocumented. Fix: add comment `# single-country fallback: same file as pt_geojson`.

11. **`test_iberia_868.py` retirement timing (05-05)** — "retire after one CI cycle confirms equivalence" delayed by unrelated flakes. Fix: retire unconditionally — D-14's `test_iberia_868_yaml.py` is canonical.

### Suggestions

| # | Plan | Suggestion |
|---|------|------------|
| S1 | 05-01 | Add a test for `dataclasses.replace()` immutability: mutate returned `cfg.output_dir`, reload, assert unchanged. |
| S2 | 05-02 | Test that emitted YAML key set matches `set(RegionConfigSchema.model_fields.keys()) ∪ {'dataset', 'kingdoms', 'duchies', 'condados', 'key'}`. |
| S3 | 05-03 | Add comment in `test_iberia_868_yaml.py` noting it supersedes `test_iberia_868.py` after 05-05. |
| S4 | 05-04 | Extract `_make_pipeline_cfg(project, **overrides)` helper to DRY `replace()` calls in generate.py/render.py. |
| S5 | 05-05 | CI grep gate: `grep -rn "iberia_config\b" backend/medieval_forge/ --include="*.py"` must return 0. |
| S6 | 05-06 | Add `data/regions/france_1066/README.md` noting GeoJSON is synthetic, deterministic, committed fixture. |
| S7 | 05-08 | Add `data-testid="new-project-modal"` to `Dialog.Content` root for resilient Playwright selectors. |
| S8 | 05-10 | Extract the 12-file contract into shared constant in `backend/medieval_forge/services/pipeline/contracts.py`. |

### Risk Assessment

**Overall: MEDIUM**

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Migration script `dataset` dict is a dataclass | HIGH | HIGH | Explicit dict construction in script |
| France E2E test async handling wrong | HIGH | HIGH | Use `TestClient` (sync) or `@pytest.mark.asyncio` |
| `original_idx` missing from migrated CONDADOS | MEDIUM | HIGH | Add `original_idx=i+1` in migration script |
| `output_dir` uninitialized in `iberia_config()` | MEDIUM | HIGH | Assert and extract explicitly |
| UI modal text mismatch with Playwright selectors | LOW | MEDIUM | Add `data-testid` attributes |
| `regions.py` deletion breaks undiscovered callsite | LOW | HIGH | Pre-deletion audit (05-05 Task 1) + CI grep gate |
| England `has_dataset: false` UX not tested in Playwright | LOW | LOW | England disabled state tested in vitest; UAT focus is France |

### Verdict

**Execute with fixes for HIGH concerns (#1 migration script `dataset` dict, #2 France E2E async pattern) before their respective plans run.** Dependency graph is sound, security model complete, parity-gate-stays-green invariant correctly enforced.

---

## Consensus Summary

### Agreed Strengths (Gemini ∩ OpenCode)

- **D-17 sequencing**: Parity gate (05-03) before deletion (05-05) is correctly enforced and verified.
- **`dataclasses.replace()` at every swap**: RESEARCH Pitfall 9 mitigation explicit in both generate.py and render.py.
- **Security model**: Loader uses `yaml.safe_load`, regex key validation, path-escape guard via `relative_to()`.
- **Testing pyramid**: Unit + parity + integration + E2E + Playwright UAT all present.
- **`parents[4]` path anchor**: Both plans correctly fix the depth bug in 05-04 and 05-07.
- **`batch_alter_table` for SQLite**: Migration 0004 wraps add_column correctly.
- **Frontend additive**: `useCreateV3Project` does not break legacy `useCreateProject` / `ProjectNew.tsx`.

### Agreed Concerns (raised by both)

| Concern | Plans | Highest severity |
|---------|-------|------------------|
| Wave numbers don't reflect strict execution order | 05-06, 05-07, 05-09 | LOW (clerical) |
| Plan 05-09 missing `display_name` for england_1216 | 05-09 | LOW |
| Playwright selectors fragile (text/regex over data-testid) | 05-08, 05-10 | LOW |
| `parents[4]` depth needs permanent anchor comment | 05-04, 05-07 | LOW–MEDIUM |
| 05-05 has scope gaps in audit coverage (Gemini flagged process; OpenCode flagged retirement timing) | 05-05 | LOW–MEDIUM |

### Divergent Views

- **Overall risk**: Gemini = LOW; OpenCode = MEDIUM. OpenCode is more concerned about migration-script details (#1 `dataset` dict construction) and France E2E async pattern (#2) — both **HIGH likelihood / HIGH impact** in OpenCode's matrix. Gemini also flagged 05-02 as MEDIUM for `CONDADOS` transformation but did not surface the dataclass-serialization or async-test concerns explicitly.
- **05-02 risk**: Gemini = MEDIUM (manual field mapping risk); OpenCode = HIGH (dataclass-serialization risk + `original_idx` missing + `output_dir` None). OpenCode's analysis is more concrete and actionable.
- **05-10 async**: only OpenCode raised it. Worth investigating before execution — if `run_pipeline` is sync, no fix needed; if async, the test will break immediately.

### Top Priorities for `/gsd-plan-phase 05 --reviews`

1. **HIGH — 05-02 migration script**: lock `dataset` dict construction (explicit, not `cfg.dataset`); assert `cfg.output_dir` populated; add `original_idx=i+1` to each migrated condado.
2. **HIGH — 05-10 E2E**: verify `run_pipeline` signature; if async, use `TestClient` or `@pytest.mark.asyncio`.
3. **MEDIUM — 05-01 schema**: make `pt_geojson`, `es_input`, `mountain_river_json` optional (None default) for cleaner template-only error path; raise explicit `FileNotFoundError` when all None.
4. **MEDIUM — 05-04 / 05-07**: add permanent anchor comment for `parents[4]` to prevent regression.
5. **LOW — 05-08 / 05-10**: add `data-testid` attributes; confirm TanStack query key for `useProjects`.
6. **LOW — 05-09**: add `display_name: England 1216 AD`.
7. **LOW — 05-08**: prescribe legacy `/projects/new` link fate (remove from ProjectList; keep route+page).

### Reviewer Failures

- **Claude CLI**: skipped (orchestrator runs inside Claude Code; running claude again would not be an independent perspective).
- **Codex CLI**: failed twice — first due to `[[hooks]]` TOML structure incompatible with current codex schema (`invalid type: sequence, expected struct HooksToml`); fallback via `CODEX_HOME=$HOME/codex_empty` failed with 401 Unauthorized (no auth.json). User config repair needed: change `[[hooks]]` to a single `[hooks]` struct in `~/.codex/config.toml`, or upgrade codex to a version that accepts the array form.

---

## DeepSeek-v4-flash Review (appended 2026-05-12)

> ⚠️ **Reviewer quality caveat**: deepseek-v4-flash was given a smaller prompt asking it to read the plan files from disk (args-too-long blocked the full prompt). The output below contains **several hallucinations** where the reviewer projected ML-pipeline semantics onto this geometric map pipeline. Hallucinations are annotated inline; treat them as **dismiss**, not actionable.

### Summary

The Phase 05 plans provide a solid architecture for region-level multi-country 2-mask generation, building on a proven per-country pipeline. The work correctly centralizes config in `data/regions/`, respects the non-negotiables (NEAREST upscale, σ range, original_idx, ocean/ignore sentinels), and includes a clear France 1066 demonstration. However, the review identifies several unreported gaps: potential thread-safety issues in the KD-tree query stage when using a single-region-wide index, missing deterministic seeding for all data-loading splits, incomplete path-traversal hardening on user-supplied YAML keys, and an unvalidated assumption that the v3 "per-country" KD-tree requirement is satisfied by a region-wide tree that uses a country-prefix mapping. These issues, while mostly medium severity, could silently degrade reproducibility and correctness in multi-region production runs.

### Strengths

- Config externalisation complete — `data/regions/iberia_868.yaml` exists and drives the pipeline (SC-1).
- Templates ship as promised — `france_1066.yaml` and `england_1216.yaml` are present.
- France 1066 demo well-scoped — 12 contract files (not parity).
- Non-negotiables explicitly checked — NEAREST upscaling, σ ∈ [3.0,4.5], original_idx, ocean = -1, ignore = 9999, independent 2× masks.
- Dependency ordering reasonable.

### Concerns

1. **Per-country KD-tree vs. region-wide index — semantic gap (HIGH, claimed)**
   `[HALLUCINATION — DISMISS]` Claims 05-04 plans a single region-wide KD-tree with a "country prefix" mapping that violates the per-country invariant. **No plan does this.** CONTEXT.md D-04 and RESEARCH explicitly preserve per-country KD-trees (one tree per country, built from that country's baronies). 05-04 is the alembic migration + region_key wiring plan; it does not touch KD-tree construction at all. This concern is fabricated.

2. **Thread-safety of KD-tree queries (MEDIUM, claimed)**
   `[HALLUCINATION — DISMISS]` Claims 05-04 mentions parallel mask tile generation. It does not. Phase 05 does not introduce parallelism beyond what Phase 01–04 already established with scipy `cKDTree` (which is thread-safe for read-only queries). No race condition exists.

3. **Deterministic seeding not enforced across all stochastic steps (MEDIUM, claimed)**
   `[HALLUCINATION — DISMISS]` Lists "train/test split", "coordinate jitter in KD-tree building", "data augmentation in preprocessing". **None of these exist** in this pipeline — Medieval Forge is a deterministic geometric pipeline (Voronoi + Shapely), not an ML training pipeline. The single `rng_seed=42` in `RegionConfig` controls every stochastic step (synthetic toy data generation only). No additional seeding needed.

4. **YAML loading lacks explicit `SafeLoader` in all code paths (MEDIUM, claimed)**
   `[ALREADY MITIGATED]` Plan 05-01 mandates `yaml.safe_load` with explicit acceptance grep `grep -nE "yaml\.safe_load" region_loader.py` returning ≥1. Threat model T-05-01-01 covers this. DeepSeek's hedge "need to check REVIEWS.md" suggests it didn't fully read the file.

5. **Path traversal via region name in file paths (LOW, claimed)**
   `[ALREADY MITIGATED]` Plan 05-01 enforces region_key regex `^[a-z0-9_]+$` (rejects `..`, `/`, `\`, etc.) plus `relative_to(region_root)` guard before any path concatenation. T-05-01-02 + T-05-07-02 cover this.

6. **No verification that France 1066 demo uses independent 2× masks (MEDIUM, claimed)**
   `[MISREADING — DISMISS]` "Independent 2× masks" in CLAUDE.md rule 6 means *independent renders at 2× resolution* (mountains_mask.png and rivers_overlay.png rendered fresh at 3840×2160, NOT upscaled from the 1× lookup). It does NOT mean train/test statistical independence. DeepSeek imported ML semantics. 05-10 already asserts the 12 files exist with correct dimensions; no statistical independence test applies.

### Net actionable from DeepSeek

**Zero new actionable findings.** All 6 concerns are either hallucinated (1, 2, 3, 6) or already mitigated in the plans deepseek did not read carefully (4, 5).

### Suggestions

DeepSeek suggests a "concurrency test" and "pixel-wise correlation near zero between the two masks" — both follow from the hallucinated concerns and should not be implemented.

### Risk Assessment

DeepSeek-v4-flash overall: MEDIUM — based on hallucinated KD-tree replacement. Confidence in this verdict: **very low**. The reviewer apparently inferred a generic ML/spatial-ML pipeline from the file names and did not anchor on CONTEXT.md or RESEARCH.md content.

### Lesson Learned

DeepSeek-v4-flash via `deepseek exec` reads files as an agent but does not appear to deeply ingest CONTEXT/RESEARCH content within the prompt budget for this kind of long-form plan review. For future runs:
- Provide the full prompt (not a file-pointer prompt) so the model sees the verbatim invariants.
- Prefer `deepseek-v4-pro` (default model) over `-v4-flash` for review tasks where the cost of hallucination > the cost of tokens.
- Alternatively, restrict deepseek's scope to one plan at a time so it can't confuse cross-plan semantics.

---

## Updated Consensus (after DeepSeek)

DeepSeek's review adds **zero new actionable items** to the prior consensus. The HIGH-priority list for `/gsd-plan-phase 05 --reviews` remains:

1. HIGH — 05-02 migration script: dataset dict construction, `cfg.output_dir` assert, `original_idx=i+1` per condado.
2. HIGH — 05-10 E2E: verify `run_pipeline` async signature.
3. MEDIUM — 05-01 schema: dataset fields optional with explicit FileNotFoundError.
4. MEDIUM — 05-04 / 05-07: permanent `parents[4]` anchor comment.
5. LOW — 05-08 / 05-10 / 05-09 / 05-08 minor items as previously listed.
