---
phase: "08"
plan: "01"
subsystem: pipeline-dag-backend
tags: [wave-1, dag, manual_edit, token-derivation, D-17, D-18, BLOCKER-2]
dependency_graph:
  requires:
    - 08-00 (wave-0 test scaffolds)
    - backend/medieval_forge/services/pipeline/dag.py (Phase 04 DAG)
    - backend/medieval_forge/services/pipeline/contracts.py (RegionConfig)
  provides:
    - backend/medieval_forge/services/pipeline/manual_edit.py
    - DAG_ORDER 13-entry with manual_edit between merge and hierarchy
    - STAGE_TOKEN_OVERRIDES dispatch in both orchestrators
    - RegionConfig.manual_edit_log_hash + manual_edit_log_count fields
    - test_dag_manual_edit.py (8 unit tests, un-skipped)
  affects:
    - 08-02 (cache key extension — manual_edit token now stable)
    - 08-04+ (frontend editor store — DAG contract established)
    - 08-06a/b/07 (vertex/polygon replay — identity slot wired)
tech_stack:
  added: []
  patterns:
    - "STAGE_TOKEN_OVERRIDES: dict[str, Callable] — override map for out-of-band token sources"
    - "D-18 token formula: sha256('manual_edit'|count|loghash|sorted(upstream))[:16]"
    - "_token()/_compute_token() dispatch: STAGE_TOKEN_OVERRIDES.get(stage) before compute_version_token"
key_files:
  created:
    - backend/medieval_forge/services/pipeline/manual_edit.py
  modified:
    - backend/medieval_forge/services/pipeline/dag.py
    - backend/medieval_forge/services/pipeline/contracts.py
    - backend/medieval_forge/services/pipeline/__init__.py
    - backend/tests/unit/test_dag_manual_edit.py
decisions:
  - "STAGE_TOKEN_OVERRIDES dispatch wired in BOTH run_pipeline and run_pipeline_incremental immediately (not deferred to 08-02) — closes Pitfall #5 from RESEARCH"
  - "Wave-0 test stub functions replaced entirely (not renamed) with 8 new tests matching plan spec"
  - "count term is explicit in D-18 formula as f'count={N}', separate from f'loghash={hash}' — BLOCKER-2 fix"
  - "manual_edit.compute() identity path returns same array object (not a copy) so parity byte-equality holds"
metrics:
  duration_minutes: 25
  completed_date: "2026-05-27"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 4
  tests_added: 8
---

# Phase 08 Plan 01: manual_edit DAG Stage + D-18 Token Foundation Summary

**One-liner:** `manual_edit` stage inserted between merge and hierarchy in 13-entry DAG_ORDER with D-18 sha256(count|loghash|upstream) token formula; STAGE_TOKEN_OVERRIDES dispatch wired in both run_pipeline orchestrators; Iberia parity byte-equal (identity pass-through on empty log_hash).

---

## What Was Built

### Task 1: RegionConfig extension + manual_edit.py + DAG extension

**`contracts.py`** — Two new fields added to RegionConfig immediately after `stop_event`:
- `manual_edit_log_hash: str = ""` — 16-hex hash of the edit-op log (D-18 + RESEARCH Open Q1). Full log lives in `snapshots` table; cfg carries only the hash so cache lookups stay cheap. Empty string = identity pass-through (D-17 carry-forward).
- `manual_edit_log_count: int = 0` — explicit count of edit ops (BLOCKER-2 fix). Together with `loghash` forms the D-18 token so different edit sequences with the same hash still produce distinct tokens.

**`manual_edit.py`** — New stage module (67 lines):
- `compute(input_array, cfg) -> np.ndarray` — identity pass-through when `log_hash == ""`. Returns the same array object (no copy) to preserve byte-equality for parity tests. Non-empty replay path deferred to plans 08-06+/07.
- `manual_edit_token(cfg, upstream_tokens) -> str` — D-18 formula: `sha256("manual_edit"|f"count={N}"|f"loghash={H}"|sorted(upstream))[:16]`. Count term is explicit and separate, not derived from hash, per BLOCKER-2 fix.

**`dag.py`** — Four atomic updates:
- `DAG_ORDER` grows 12→13: `"manual_edit"` inserted between `"merge"` and `"hierarchy"`
- `STAGE_READS["manual_edit"] = frozenset()` — no cfg fields read (inputs are out-of-band)
- `DAG_PARENTS["manual_edit"] = ("merge",)` and `DAG_PARENTS["hierarchy"] = ("manual_edit",)` — re-parents hierarchy
- `STAGE_TOKEN_OVERRIDES: dict[str, Callable]` — new dispatch map; `"manual_edit"` → `manual_edit.manual_edit_token`

**`test_dag_manual_edit.py`** — Wave-0 skip removed; 4 stub functions replaced with 8 new tests:
1. `test_dag_order_contains_manual_edit_between_merge_and_hierarchy` — DAG_ORDER structure
2. `test_dag_parents_manual_edit_is_merge` — parent/child chain
3. `test_stage_reads_manual_edit_is_empty_frozenset` — out-of-band inputs
4. `test_stage_token_overrides_manual_edit_is_callable` — override registered
5. `test_manual_edit_token_empty_hash_is_stable_across_two_calls` — determinism
6. `test_manual_edit_token_differs_with_non_empty_log_hash` — hash sensitivity
7. `test_manual_edit_token_differs_when_only_count_changes` — **BLOCKER-2 fix**
8. `test_manual_edit_compute_empty_hash_returns_input_byte_equal` — identity path

### Task 2: Orchestrator wiring + parity validation

**`__init__.py`** — Four changes:
- `run_pipeline._token()` — imports `STAGE_TOKEN_OVERRIDES`; dispatches override before `compute_version_token`
- `run_pipeline` body — `manual_edit` block inserted between merge and hierarchy: `_emit` start/done, `_token`, `_manual_edit.compute()`, `_cache_put`
- `run_pipeline_incremental._compute_token()` — same `STAGE_TOKEN_OVERRIDES` dispatch
- `run_pipeline_incremental` body — `manual_edit` dirty-check block with `cache_get`/`cache_put` wired

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] STAGE_TOKEN_OVERRIDES dispatch added immediately to both orchestrators**
- **Found during:** Task 2 — parity test failed with `KeyError: 'manual_edit'` in `_compute_token` because `tokens["manual_edit"]` was never populated (DAG_PARENTS["hierarchy"] now points to "manual_edit" but the orchestrator had no block for it)
- **Fix:** Added `manual_edit` block in `run_pipeline_incremental` AND updated both `_token()` / `_compute_token()` to dispatch via `STAGE_TOKEN_OVERRIDES.get(stage)` before falling back to `compute_version_token`. The plan's Task 2 action described adding the block but didn't explicitly call out fixing the `_compute_token` dispatch — this was required to keep parity green.
- **Files modified:** `backend/medieval_forge/services/pipeline/__init__.py`
- **Commit:** `7d3f18c`

**2. [Rule 2 - Missing critical] STAGE_TOKEN_OVERRIDES dispatch wired now (not deferred to 08-02)**
- **Found during:** Task 2 — advisor flagged that leaving dispatch deferred to 08-02 would leave Pitfall #5 open
- **Fix:** Override dispatch added to both `_token()` (run_pipeline) and `_compute_token()` (run_pipeline_incremental) in this plan
- **Closes:** RESEARCH §Common Pitfalls #5 "manual_edit token derivation breaks STAGE_READS pattern"

---

## Known Stubs

- `manual_edit.compute()` — returns input array unchanged for all cases in Wave 1 (both empty and non-empty log_hash). Non-empty replay (vertex move, polygon split/merge) lands in plans 08-06a/06b/07. This is intentional — the identity path is the contract established by D-17; replay is additive.

---

## Threat Flags

None — this plan introduces only backend pipeline internals with no new API surface, no DB writes, and no network endpoints. The two threat entries from the plan's threat model (T-08-01-01 hash on RegionConfig, T-08-01-02 token leak) are both "accept" with no mitigation required at this stage.

---

## Self-Check: PASSED

**Files exist:**
- FOUND: `backend/medieval_forge/services/pipeline/manual_edit.py`
- FOUND: `backend/medieval_forge/services/pipeline/dag.py` (STAGE_TOKEN_OVERRIDES present)
- FOUND: `backend/medieval_forge/services/pipeline/contracts.py` (manual_edit_log_count present)
- FOUND: `backend/medieval_forge/services/pipeline/__init__.py` (manual_edit wired)
- FOUND: `backend/tests/unit/test_dag_manual_edit.py` (no pytestmark skip)

**Commits:**
- FOUND: `98040d4` — feat(08-01): add manual_edit stage to DAG + RegionConfig D-18 fields
- FOUND: `7d3f18c` — feat(08-01): wire manual_edit stage into run_pipeline orchestrators

**Test results:**
- Unit tests: 8 passed, 0 failed, 0 skipped
- Parity tests: 17 passed, 2 skipped, 6 xfailed, 4 xpassed (all green)
