---
phase: "08"
plan: "07c"
subsystem: pipeline-manual-edit-replay
tags: [blocker-1, d-17, rasterio, snapshot-loader, compute-replay, parity]
dependency_graph:
  requires:
    - 08-01 (manual_edit DAG stage + identity contract)
    - 08-07 (replay_split / replay_merge / replay_translate pure functions)
    - 08-03b (snapshot blob format: edit_log list in snapshot dict)
  provides:
    - compute() replay path: vectorize int16 raster → apply edit log → rasterize back
    - RegionConfig.snapshot_loader: Optional[Callable[[str], dict]] field
    - orchestrator wiring: try/finally preserve+restore snapshot_loader (T-08-07c-02)
    - test_manual_edit_compute_replay.py: 6 unit tests (Wave-0 stubs replaced)
    - test_phase08_edit_visible_in_lookup.py: 2 parity tests (Wave-0 stubs replaced)
  affects:
    - 08-09 (vertex move ops extend same replay path)
    - 08-11 (full pipeline integration — snapshot_loader wired from API layer)
tech_stack:
  added: []
  patterns:
    - "rasterio.features.shapes + rasterize: vectorize int16 raster → per-barony Polygon dict → rasterize back"
    - "all_touched=False: explicit cell-centroid semantics (Gemini LOW); prevents sub-pixel aliasing"
    - "snapshot_loader: Optional[Callable[[str], dict]]: injected by caller; never serialised (STAGE_READS frozenset)"
    - "try/finally preserve+restore cfg.snapshot_loader: T-08-07c-02 serialisability"
    - "ocean=-1 / ignore=9999 sentinel preservation post-rasterize (CLAUDE.md rule #5)"
key_files:
  created: []
  modified:
    - backend/medieval_forge/services/pipeline/manual_edit.py
    - backend/medieval_forge/services/pipeline/contracts.py
    - backend/medieval_forge/services/pipeline/__init__.py
    - backend/tests/unit/test_manual_edit_compute_replay.py
    - backend/tests/parity/test_phase08_edit_visible_in_lookup.py
decisions:
  - "Used cfg.branch_id (existing field from 08-01/contracts.py) instead of adding active_branch_id — advisor flagged duplicate; cfg.branch_id already carries the branch context"
  - "snapshot_loader is Optional[Callable[[str], dict]] on RegionConfig; not a new separate field — injected by caller, never in cache key (STAGE_READS=frozenset)"
  - "Orchestrator uses try/finally preserve+restore pattern instead of unconditional injection — allows test callers to pre-inject stub loaders without being overwritten"
  - "Production DB loader (async branches service) NOT wired in this plan — orchestrators are sync, branches service is async; API layer wiring deferred to 08-11 (Known Stub)"
  - "9999 sentinel also excluded from vectorize (value == 9999 skip) for symmetry with CLAUDE.md rule #5"
metrics:
  duration_minutes: 30
  completed_date: "2026-05-27"
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 5
  tests_added: 8
---

# Phase 08 Plan 07c: BLOCKER-1 Closure — compute() Replay Path Summary

**One-liner:** `manual_edit.compute()` now vectorises the upstream int16 raster via `rasterio.features.shapes`, applies the branch edit log (split/merge/translate) in order via 08-07 replay helpers, and rasterises back via `rasterio.features.rasterize(all_touched=False)`; lookup_barony.png SHA-256 provably differs after a single translate op (parity test asserts `!=`).

---

## What Was Built

### Task 1: RegionConfig.snapshot_loader + compute() replay path

**`contracts.py`** — One new field added to RegionConfig after `branch_id`:
- `snapshot_loader: Optional[Callable[[str], dict]] = field(default=None)` — injected by DAG walker / orchestrator before `compute()` invocation. Excluded from all serialisation paths: `STAGE_READS["manual_edit"] = frozenset()` means it never enters any version_token computation. Non-pickleable callable; orchestrators restore it to `None` via try/finally after compute.

**`manual_edit.py`** — `compute()` fully reimplemented (identity stub replaced):
- Empty `log_hash` → identity pass-through, same object returned (D-17 carry-forward).
- Non-empty `log_hash` + `snapshot_loader=None` → `RuntimeError("snapshot_loader required when manual_edit_log_hash is set")` — explicit failure, not silent identity.
- Non-empty `log_hash` + loader set → full replay path:
  1. `rasterio.features.shapes(input_array, transform=from_bounds(0,0,W,H,W,H))` to vectorise int16 raster into per-barony Shapely Polygons.
  2. Skips `value < 0` (ocean) and `value == 9999` (ignore) sentinels per CLAUDE.md rule #5.
  3. Applies edit log ops in order via `replay_split`, `replay_merge`, `replay_translate` (pure functions from 08-07).
  4. `rasterio.features.rasterize(shapes, fill=-1, dtype=np.int16, all_touched=False)` — explicit `all_touched=False` per Gemini LOW review; prevents sub-pixel aliasing that would break Unity byOriginalIdx shader.
  5. Restores `ocean=-1` and `ignore=9999` from input after rasterize (sentinel preservation contract).

**`test_manual_edit_compute_replay.py`** — 6 tests replacing Wave-0 skip stubs:
1. `test_compute_empty_hash_returns_input_byte_equal` — identity carry-forward
2. `test_compute_raises_when_hash_set_but_loader_missing` — explicit RuntimeError guard
3. `test_compute_single_translate_op_mutates_raster` — at least 1 pixel differs after translate
4. `test_compute_empty_edit_log_from_loader_returns_identity` — empty list → byte-equal
5. `test_compute_is_deterministic_same_result_across_two_calls` — determinism
6. `test_compute_rasterize_invoked_with_all_touched_false` — monkey-patch spy verifies kwarg

**6 unit tests green.**

### Task 2: Orchestrator wiring + parity test

**`__init__.py`** — Both `run_pipeline` and `run_pipeline_incremental` updated:
- Added `try/finally` preserve+restore block around `_manual_edit.compute(result, cfg)`.
- Pattern: `_prev_loader = cfg.snapshot_loader; try: ...; finally: cfg.snapshot_loader = _prev_loader`.
- Semantics: if caller already injected a `snapshot_loader` (test or API layer), it is honoured and NOT overwritten. After `compute()` returns, the field is restored to what it was before (keeps cfg serialisable — T-08-07c-02 mitigation).

**`test_phase08_edit_visible_in_lookup.py`** — 2 parity tests replacing Wave-0 skip stubs:
1. `test_one_vertex_translate_mutates_lookup_barony_png` — NOVEL POLARITY (`!=`): runs Iberia 868 baseline (empty log), then edited run with stub loader returning 1 translate op; asserts SHA-256 differs. Proves edits propagate through manual_edit → hierarchy → render → lookup_barony.png.
2. `test_empty_edit_log_preserves_lookup_barony_png` — IDENTITY (`==`): two runs with empty log must be byte-equal. Optionally checks against canonical Reconquista baseline if path accessible.

**2 parity tests green (164s total run time for 3 pipeline executions).**

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan specified `active_branch_id` as new field; `branch_id` already exists**
- **Found during:** Task 1 implementation (advisor review before coding)
- **Issue:** Plan 08-07c action says "Add `active_branch_id: str | None = None` to RegionConfig". `contracts.py` already has `branch_id: str = "main"` added in 08-01/08-08 (`Phase 08 D-23`). Adding a second field would duplicate the concept.
- **Fix:** Used `cfg.branch_id` directly in `compute()` for the loader key. Did NOT add `active_branch_id`.
- **Files modified:** `backend/medieval_forge/services/pipeline/manual_edit.py`
- **Commit:** a69a940

**2. [Rule 1 - Bug] Plan's `manual_edit.py` example had self-import that would cause ImportError**
- **Found during:** Task 1 implementation (advisor review before coding)
- **Issue:** Plan action included `from .manual_edit import replay_split, replay_merge, replay_translate` inside `manual_edit.py` — self-import that would trigger circular ImportError.
- **Fix:** Removed the self-import; `replay_split/replay_merge/replay_translate` are used directly since they are defined in the same module file.
- **Files modified:** `backend/medieval_forge/services/pipeline/manual_edit.py`
- **Commit:** a69a940

**3. [Rule 2 - Missing critical] Plan's orchestrator injection would overwrite test-injected loaders**
- **Found during:** Task 2 implementation (advisor review)
- **Issue:** Plan's `__init__.py` action sets `cfg.snapshot_loader = lambda branch_id: ...` unconditionally, which would silently overwrite the stub loader injected by the parity test (`cfg_edited.snapshot_loader = lambda _branch_id: one_op_log`). The mutation parity test would then try to call a production DB function and fail.
- **Fix:** Used `try/finally preserve+restore` pattern: `_prev_loader = cfg.snapshot_loader` before, `cfg.snapshot_loader = _prev_loader` in finally. Caller-injected loaders are honoured.
- **Files modified:** `backend/medieval_forge/services/pipeline/__init__.py`
- **Commit:** b1515d7

---

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| Production DB loader not wired in orchestrator | `backend/medieval_forge/services/pipeline/__init__.py` | `run_pipeline` is synchronous; `branches.service` methods are all `async`. Wiring requires the API layer (`api/v3/render.py` or `api/v3/generate.py`) to inject `cfg.snapshot_loader` before calling the pipeline. This is deferred to plan 08-11 (full pipeline integration). For now, tests inject stub loaders directly, and Iberia parity uses empty `log_hash` (identity path — no loader needed). |
| `vertex-level ops` (move/add/delete) in edit log | `backend/medieval_forge/services/pipeline/manual_edit.py` | Only `split`, `merge`, `translate` ops are handled in the compute() replay loop. Vertex-level ops reconstruct geometry from `snapshot.vertices` dict (frontend-side geometry) — deferred to follow-up plans per plan spec comment. |

---

## Threat Flags

None — this plan adds no new API surface, no new DB tables, and no new network endpoints. The two threat entries from the plan's threat model are handled:
- T-08-07c-02 (snapshot_loader serialisation): mitigated by `try/finally` restore pattern in both orchestrators + `STAGE_READS["manual_edit"] = frozenset()` (08-01) ensuring field is never in any cache key.
- T-08-07c-01 (malicious edit_log): accept disposition per plan — local-only single-user tool; `/editor/apply` (08-07) validates server-side before persisting.

---

## Self-Check: PASSED

**Files exist:**
- FOUND: `backend/medieval_forge/services/pipeline/manual_edit.py` (rasterio.features used 5 times)
- FOUND: `backend/medieval_forge/services/pipeline/contracts.py` (snapshot_loader field present)
- FOUND: `backend/medieval_forge/services/pipeline/__init__.py` (snapshot_loader appears 6 times)
- FOUND: `backend/tests/unit/test_manual_edit_compute_replay.py` (6 tests, no pytestmark skip)
- FOUND: `backend/tests/parity/test_phase08_edit_visible_in_lookup.py` (2 tests, no skip)

**Acceptance criteria verified:**
- `grep -c "rasterio.features" manual_edit.py` → 5 (≥ 2 ✓)
- `grep -c "snapshot_loader" contracts.py` → 1 ✓
- `grep -c "active_branch_id" contracts.py` → 0 ✓ (used branch_id instead)
- `grep -c "snapshot_loader" dag.py` → 0 ✓ (not in STAGE_READS)
- `grep -nE "all_touched\s*=\s*False" manual_edit.py` → 3 occurrences ✓
- `grep -c "!= baseline_sha" test_phase08_edit_visible_in_lookup.py` → 1 ✓
- `grep -n "snapshot_loader" __init__.py` → 6 occurrences (≥ 2 ✓)

**Commits:**
- FOUND: `a69a940` — feat(08-07c): BLOCKER-1 closure — compute() replay path + snapshot_loader field
- FOUND: `b1515d7` — feat(08-07c): wire snapshot_loader in orchestrators + BLOCKER-1 parity tests

**Test results:**
- Unit tests (6): 6 passed, 0 failed, 0 skipped
- Parity tests (2): 2 passed, 0 failed, 0 skipped
- Existing Iberia 868 render parity: 1 passed (green — identity carry-forward preserved)
