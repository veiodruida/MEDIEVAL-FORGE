---
phase: 08
plan: 07c
type: execute
wave: 7
depends_on: [08-07, 08-01, 08-03b]
autonomous: true
requirements: [EDIT-POLYGON-01, EDIT-POLYGON-02, EDIT-POLYGON-03, DAG-01, DAG-02]
files_modified:
  - backend/medieval_forge/services/pipeline/manual_edit.py
  - backend/medieval_forge/services/pipeline/contracts.py
  - backend/medieval_forge/services/pipeline/__init__.py
  - backend/tests/parity/test_phase08_edit_visible_in_lookup.py
  - backend/tests/unit/test_manual_edit_compute_replay.py

must_haves:
  truths:
    - "BLOCKER-1 fix (D-17 enforcement): manual_edit.compute() is now the SINGLE producer of edited geometry; lookup PNGs + Unity export reflect user edits"
    - "compute() with non-empty manual_edit_log_hash loads active branch's snapshot blob via cfg.snapshot_loader, vectorises the int16 raster via rasterio.features.shapes, applies edit log via replay_split/replay_merge/replay_translate (08-07 Step 2), re-rasterises via rasterio.features.rasterize, returns edited int16 array"
    - "compute() with empty manual_edit_log_hash is identity (byte-equal, D-17 carry-forward — Iberia parity stays green)"
    - "Parity test (one-vertex-move fixture): after applying a single vertex move op, lookup_barony.png SHA-256 DIFFERS from pre-edit baseline — proves edits propagate to the canonical raster"
    - "Identity parity (no edits): lookup_barony.png SHA-256 EQUALS pre-edit baseline (zero regression)"
    - "snapshot_loader is a Callable injected by the DAG walker (or run_pipeline orchestrator) and is EXCLUDED from any serialisation/cache-key path (non-pickleable)"
  artifacts:
    - path: "backend/medieval_forge/services/pipeline/manual_edit.py"
      provides: "compute() replay path: vectorize → apply edit log → rasterize"
      contains: "rasterio.features.shapes"
    - path: "backend/medieval_forge/services/pipeline/contracts.py"
      provides: "RegionConfig.snapshot_loader: Callable | None field (non-serialisable)"
      contains: "snapshot_loader"
    - path: "backend/tests/parity/test_phase08_edit_visible_in_lookup.py"
      provides: "parity test proving one vertex move mutates lookup_barony.png"
      contains: "assert.*!=.*sha256"
  key_links:
    - from: "manual_edit.compute() non-empty branch"
      to: "rasterio.features.shapes + rasterize"
      via: "vectorise int16 raster → apply Shapely ops from edit log → rasterise back"
      pattern: "rasterio.features"
    - from: "run_pipeline orchestrator"
      to: "snapshot_loader injection"
      via: "before invoking manual_edit.compute(), orchestrator sets cfg.snapshot_loader = lambda branch_id: snapshots_service.load_active(project_id, branch_id) so compute() can fetch the edit log without leaking DB dependencies into cfg"
      pattern: "snapshot_loader"
---

<objective>
**BLOCKER-1 closure** — make D-17 real. Plan 08-01 established the DAG contract (identity-only compute); plan 08-07 added replay helpers + persistence endpoint. But until this plan lands, compute() is identity-only in both branches, so user edits never reach lookup_barony.png + the 12-file Unity export.

This plan fills the gap: compute() loads the active branch's snapshot blob via an injected loader, vectorises the upstream int16 raster, applies the edit log in order using the Shapely replay helpers, and re-rasterises back to int16. Adds a parity test that asserts visible mutation in lookup_barony.png after a single vertex move (opposite polarity from existing D-17 identity tests — easy to write the wrong direction; the test is explicit about asserting !=).

Purpose: close the BLOCKER-1 contract gap surfaced by the checker. Without this plan, D-17 is documented but not implemented.
Output: compute() replay path + snapshot_loader cfg field + 1 parity test + 1 unit test.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/REQUIREMENTS.md
@.planning/STATE.md
@.planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-CONTEXT.md
@.planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-RESEARCH.md
@.planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-01-PLAN.md
@.planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-07-PLAN.md
@backend/medieval_forge/services/pipeline/dag.py
@backend/medieval_forge/services/pipeline/manual_edit.py
@backend/medieval_forge/services/pipeline/contracts.py
@backend/medieval_forge/services/pipeline/__init__.py

<interfaces>
rasterio 1.3+ (verify `import rasterio.features` works in current backend env):
  rasterio.features.shapes(int16_raster, mask=None, transform=affine)
    → iterator of (geom_geojson_dict, value_int)
  rasterio.features.rasterize(
    shapes=[(geom, value), ...],
    out_shape=(H, W),
    transform=affine,
    fill=0,
    dtype=np.int16,
  ) → np.ndarray int16

shapely.geometry.shape(geojson_dict) → Polygon/MultiPolygon

From plan 08-07 Step 2 (will land before this plan executes):
  replay_split(parent: Polygon, cut: LineString) -> list[Polygon]
  replay_merge(a: Polygon, b: Polygon) -> Polygon
  replay_translate(poly: Polygon, dLat: float, dLon: float) -> Polygon

Snapshot blob shape (from 08-03b):
  {
    "edit_log": [{"op": "split"|"merge"|"translate"|...,
                  "ts": int,
                  "parentId"/"firstId"/"secondId"/"polygonId": str,
                  "cutLineCoords"/"dLat"/"dLon": ...,
                  "allocated_original_idx": int | None}, ...],
    "vertices": {...},  # frontend-only; backend ignores
    "branch_id": "...",
  }
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: RegionConfig.snapshot_loader + compute() replay path</name>
  <files>backend/medieval_forge/services/pipeline/contracts.py, backend/medieval_forge/services/pipeline/manual_edit.py, backend/tests/unit/test_manual_edit_compute_replay.py</files>
  <read_first>
    - backend/medieval_forge/services/pipeline/contracts.py (RegionConfig + existing stop_event field for pattern)
    - backend/medieval_forge/services/pipeline/manual_edit.py (from 08-01 + 08-07)
    - backend/medieval_forge/services/pipeline/cleanup.py (rasterize patterns if any; otherwise PIL Image)
    - .planning/phases/08-RESEARCH.md (§rasterization patterns if present)
  </read_first>
  <behavior>
    - Test: compute(input_array, cfg with hash="" and loader=None) returns input byte-equal (identity carry-forward)
    - Test: compute(input_array, cfg with hash="abc" but loader=None) raises RuntimeError("snapshot_loader required when manual_edit_log_hash is set") — explicit failure, not silent identity
    - Test: compute with a stub loader returning a 1-op edit log (translate by dLat=0.001) mutates a single-polygon int16 raster — at least 1 pixel differs from input
    - Test: compute with empty edit log (loader returns {"edit_log":[]}) returns input byte-equal
    - Test: compute is deterministic — same cfg + same input → same output across 2 calls
    - Test (Gemini review: raster-vector roundtrip artifacts): rasterio.features.rasterize is invoked with all_touched=False OR with the all_touched arg omitted (default is False). Verify by monkey-patching rasterio.features.rasterize with a spy that records kwargs; assert spy.kwargs.get('all_touched', False) is False. Prevents sub-pixel border leakage that would break Unity byOriginalIdx shader.
  </behavior>
  <action>
**Step 1 — `contracts.py`:** Add to RegionConfig dataclass, immediately after `manual_edit_log_count` (added in 08-01):
```python
# Phase 08 BLOCKER-1 fix (D-17 closure): snapshot loader injected by the DAG walker
# so manual_edit.compute() can fetch the active branch's edit log without leaking DB
# dependencies into cfg. CRITICAL — exclude from any pickling/serialisation path:
# Callable is non-pickleable. If RegionConfig is ever passed to multiprocessing or
# stored in a cache key, set this field to None first.
from typing import Callable as _Callable, Optional as _Optional
snapshot_loader: _Optional[_Callable[[str], dict]] = None  # branch_id → snapshot dict
```
(Use string-quoted forward refs or local type imports as needed to avoid circular imports; the dag.py token computation MUST NOT include this field — its STAGE_READS is already `frozenset()` per 08-01, so this is automatic.)

**Step 2 — `manual_edit.py`:** Replace the identity-only `compute()` body with the replay path:
```python
from __future__ import annotations
import hashlib
import json
from typing import Iterable

import numpy as np
import rasterio.features
from rasterio.transform import from_bounds
from shapely.geometry import LineString, Polygon, shape as shapely_shape

from .contracts import RegionConfig

# replay_split / replay_merge / replay_translate were added in 08-07 Task 1 Step 2
from .manual_edit import replay_split, replay_merge, replay_translate  # noqa: F401
# (If module is being rewritten in this plan, define them inline at top of file.
#  Keep them exported so tests in 08-07 still pass.)


def compute(input_array: np.ndarray, cfg: RegionConfig) -> np.ndarray:
    """D-17 closure: edits are the OUTPUT of this stage.

    Empty log → identity (D-17 carry-forward + Phase 01 D-09; Iberia parity stays green).
    Non-empty log → vectorise input raster, apply replay helpers, rasterise back.
    """
    if not cfg.manual_edit_log_hash:
        return input_array

    if cfg.snapshot_loader is None:
        raise RuntimeError(
            "snapshot_loader required when manual_edit_log_hash is set "
            "(BLOCKER-1 fix: DAG walker must inject cfg.snapshot_loader before "
            "invoking manual_edit.compute())"
        )

    # Loader is keyed by branch_id; cfg must carry branch context (see Step 3).
    snapshot = cfg.snapshot_loader(cfg.active_branch_id)
    edit_log = snapshot.get("edit_log", [])
    if not edit_log:
        return input_array

    # 1) Vectorise int16 raster into per-barony polygons.
    #    Use an identity affine — pipeline operates in raster coordinates throughout.
    H, W = input_array.shape
    transform = from_bounds(0, 0, W, H, W, H)  # identity-equivalent for our use
    shapes_iter = rasterio.features.shapes(input_array.astype(np.int16), transform=transform)
    polygons_by_id: dict[int, list[Polygon]] = {}
    for geom_dict, value in shapes_iter:
        value = int(value)
        if value < 0:  # ocean sentinel (-1) — preserve as-is, do not vectorise
            continue
        poly = shapely_shape(geom_dict)
        if isinstance(poly, Polygon) and poly.area > 0:
            polygons_by_id.setdefault(value, []).append(poly)

    # 2) Apply edit log in order. Replay helpers raise on invalid ops; the
    #    /editor/apply endpoint (08-07) already validates server-side BEFORE
    #    persisting, so any exception here is a bug — propagate it.
    for op in edit_log:
        op_type = op["op"]
        if op_type == "split":
            parent_id = int(op["parentId"])
            cut = LineString(op["cutLineCoords"])
            parents = polygons_by_id.get(parent_id, [])
            if not parents:
                continue  # parent already merged away in a later op — skip
            new_pieces = replay_split(parents[0], cut)
            child_id = int(op["allocated_original_idx"])
            polygons_by_id[parent_id] = [new_pieces[0]]
            polygons_by_id.setdefault(child_id, []).append(new_pieces[1])
        elif op_type == "merge":
            a_id, b_id = int(op["firstId"]), int(op["secondId"])
            a_polys = polygons_by_id.get(a_id, [])
            b_polys = polygons_by_id.get(b_id, [])
            if not a_polys or not b_polys:
                continue
            merged = replay_merge(a_polys[0], b_polys[0])
            polygons_by_id[a_id] = [merged]
            polygons_by_id[b_id] = []  # D-08: loser idx freed but NEVER reused
        elif op_type == "translate":
            poly_id = int(op["polygonId"])
            dLat, dLon = float(op["dLat"]), float(op["dLon"])
            polys = polygons_by_id.get(poly_id, [])
            polygons_by_id[poly_id] = [replay_translate(p, dLat, dLon) for p in polys]
        # vertex-level ops (move/add/delete) are handled by upstream geometry
        # rebuild from snapshot.vertices in a follow-up; for split/merge/translate
        # this scaffolds the contract.

    # 3) Rasterise back to int16 with NEAREST semantics (rasterize defaults to all-touched=False;
    #    fill=ocean sentinel -1 to preserve ocean pixels not covered by any polygon).
    shapes_to_rasterise = [
        (poly, idx)
        for idx, polys in polygons_by_id.items()
        for poly in polys
        if poly is not None and not poly.is_empty
    ]
    out = rasterio.features.rasterize(
        shapes=shapes_to_rasterise,
        out_shape=(H, W),
        transform=transform,
        fill=-1,  # ocean sentinel per CLAUDE.md rule #5
        dtype=np.int16,
        all_touched=False,  # Gemini review (LOW): explicit; standard cell-centroid semantics.
                            # Prevents sub-pixel aliasing / orphan border pixels that would
                            # break Unity byOriginalIdx shader. Default is False but we make
                            # it explicit so a future API change cannot silently flip semantics.
    )
    # Preserve ocean (-1) and ignore (9999) sentinels from input where rasterise produced fill.
    ocean_mask = (input_array == -1)
    ignore_mask = (input_array == 9999)
    out[ocean_mask] = -1
    out[ignore_mask] = 9999
    return out
```

(If `manual_edit.py` already has the replay helpers from 08-07, the import at the top of `compute` becomes redundant — just reference them directly within the same module. The plan executor decides based on the current file state.)

**Step 3 — Add `active_branch_id: str | None = None` to RegionConfig** (next to snapshot_loader). The orchestrator (Step injected in Task 2) sets it before invoking compute().

**Step 4 — `test_manual_edit_compute_replay.py`:** Fill the 5 behaviour tests above. Use explicit numeric fixtures:
- Build a 10×10 int16 raster with values: top-left 4×4 = barony_id=1, top-right 4×4 = barony_id=2, rest = -1 (ocean)
- Stub loader returns `{"edit_log": [{"op":"translate","polygonId":1,"dLat":1.0,"dLon":0.0,"ts":0}]}` (translate barony 1 down by 1 raster cell)
- Assert at least 1 pixel differs (use `np.any(out != input_array)`)
- For identity test: empty edit_log returns array such that `np.array_equal(out, input_array)`
  </action>
  <verify>
    <automated>cd backend && python -m pytest tests/unit/test_manual_edit_compute_replay.py -v -x</automated>
  </verify>
  <acceptance_criteria>
    - All 5 unit tests pass
    - `grep -c "rasterio.features" backend/medieval_forge/services/pipeline/manual_edit.py` returns 2+
    - `grep -c "snapshot_loader" backend/medieval_forge/services/pipeline/contracts.py` returns 1+
    - `grep -c "active_branch_id" backend/medieval_forge/services/pipeline/contracts.py` returns 1+
    - `grep -c "snapshot_loader" backend/medieval_forge/services/pipeline/dag.py` returns 0 (must NOT be in STAGE_READS — non-serialisable callable)
    - `grep -nE "all_touched\s*=\s*False" backend/medieval_forge/services/pipeline/manual_edit.py` returns 1+ (Gemini LOW concern: explicit raster semantics)
    - Unit test asserts rasterio.features.rasterize is called with all_touched=False OR with no all_touched kwarg (default). Verified via monkey-patch spy on the unit-test fixture (see new behaviour test above).
    - Iberia parity stays green (empty edit log → identity)
  </acceptance_criteria>
  <done>compute() replay path live; Iberia parity carry-forward confirmed.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Wire snapshot_loader in run_pipeline orchestrator + parity test (one-vertex-move mutates lookup_barony.png)</name>
  <files>backend/medieval_forge/services/pipeline/__init__.py, backend/tests/parity/test_phase08_edit_visible_in_lookup.py</files>
  <read_first>
    - backend/medieval_forge/services/pipeline/__init__.py (run_pipeline body; find the manual_edit invocation added in 08-01 Task 2 — around the merge→hierarchy transition)
    - backend/medieval_forge/services/branches/service.py (from 08-03a — snapshot load API)
    - backend/tests/parity/test_iberia_868.py (parity pattern — compare lookup_barony.png SHA-256)
  </read_first>
  <behavior>
    - Test (parity, NOVEL POLARITY): build Iberia 868 once with empty edit log → record lookup_barony.png SHA-256 as baseline. Then re-build with cfg.manual_edit_log_hash set + cfg.snapshot_loader returning a 1-op translate fixture for a single Iberia barony → assert lookup_barony.png SHA-256 DIFFERS from baseline (NOT equals — easy to write the wrong direction; the assertion is explicitly !=)
    - Test (parity, IDENTITY): build with cfg.manual_edit_log_hash="" → lookup_barony.png SHA-256 EQUALS baseline (zero regression vs pre-Phase-8)
    - Test (orchestrator wiring): run_pipeline sets cfg.snapshot_loader before invoking manual_edit.compute(); after invocation, the orchestrator clears it (sets back to None) so cfg can be safely passed to any downstream code that may serialise it
  </behavior>
  <action>
**Step 1 — `__init__.py`:** Locate the manual_edit invocation added in 08-01 Task 2 (around the merge→hierarchy transition; see grep result `_emit(cfg, "merge", "done")` at line 410 + `manual_edit` block immediately after). Wrap it with snapshot_loader injection:

```python
# Phase 08 BLOCKER-1 fix: inject snapshot loader so compute() can fetch the edit log.
# Cleared on the other side so cfg stays serialisable for downstream code.
_prev_loader = cfg.snapshot_loader
_prev_branch_id = cfg.active_branch_id
try:
    from ..branches import service as _branches_service
    cfg.snapshot_loader = lambda branch_id: _branches_service.load_active_snapshot(
        project_id=cfg.project_id, branch_id=branch_id
    )
    cfg.active_branch_id = getattr(cfg, "active_branch_id", None)  # set by API layer
    from . import manual_edit as _manual_edit
    post_merge_array = _manual_edit.compute(merged_array, cfg)
finally:
    cfg.snapshot_loader = _prev_loader
    cfg.active_branch_id = _prev_branch_id
if cfg.on_stage:
    cfg.on_stage("manual_edit", {"event_type": "stage_done", "progress": 1.0})
```

(Variable names — `merged_array` is a guess; read the actual orchestrator file. `cfg.project_id` may need to be sourced differently; adjust to match the actual cfg/orchestrator shape. The key invariant is: loader injected ONLY around compute(), cleared after, never persisted.)

**Step 2 — `test_phase08_edit_visible_in_lookup.py`:** New parity test in `backend/tests/parity/`:
```python
"""BLOCKER-1 closure parity test (D-17 enforcement).

Asserts that a single user edit (one translate op) propagates all the way
through the DAG to the canonical lookup_barony.png — opposite polarity from
the existing Iberia identity parity test, which is the easy mistake to make.
"""
import hashlib
import pathlib
import pytest
from medieval_forge.services.pipeline import run_pipeline
# ... import iberia_config helper

def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

@pytest.mark.parity
def test_one_vertex_translate_mutates_lookup_barony_png(tmp_path):
    cfg_baseline = iberia_868_config(output_dir=tmp_path / "baseline")
    cfg_baseline.manual_edit_log_hash = ""  # identity
    run_pipeline(cfg_baseline)
    baseline_sha = _sha256(tmp_path / "baseline" / "lookup_barony.png")

    cfg_edited = iberia_868_config(output_dir=tmp_path / "edited")
    # Stub loader returning a single translate op for a known Iberia barony idx
    one_op_log = {"edit_log": [{
        "op": "translate",
        "polygonId": 1,  # pick a known barony idx from territory_data_v3.py
        "dLat": 1.0,
        "dLon": 0.0,
        "ts": 0,
    }]}
    cfg_edited.manual_edit_log_hash = hashlib.sha256(
        repr(one_op_log["edit_log"]).encode()
    ).hexdigest()[:16]
    cfg_edited.manual_edit_log_count = 1
    cfg_edited.snapshot_loader = lambda _branch_id: one_op_log
    cfg_edited.active_branch_id = "test-branch"
    run_pipeline(cfg_edited)
    edited_sha = _sha256(tmp_path / "edited" / "lookup_barony.png")

    # CRITICAL: assertion is != not == — proves the edit propagated.
    assert edited_sha != baseline_sha, (
        f"BLOCKER-1 regression: lookup_barony.png unchanged after translate op. "
        f"Edits are not flowing through manual_edit.compute() → DAG → lookup."
    )

@pytest.mark.parity
def test_empty_edit_log_preserves_lookup_barony_png(tmp_path):
    cfg = iberia_868_config(output_dir=tmp_path / "identity")
    cfg.manual_edit_log_hash = ""
    cfg.snapshot_loader = None
    run_pipeline(cfg)
    # Compare against the canonical Reconquista baseline (existing parity fixture)
    canonical = pathlib.Path("D:/Projetos_Jogo/Reconquista/Assets/StreamingAssets/Maps/lookup_barony.png")
    if canonical.exists():
        assert _sha256(tmp_path / "identity" / "lookup_barony.png") == _sha256(canonical), \
            "D-17 carry-forward regression: identity path no longer byte-equal to canonical"
```
  </action>
  <verify>
    <automated>cd backend && python -m pytest tests/parity/test_phase08_edit_visible_in_lookup.py -v -x && python -m pytest tests/parity/test_iberia_868.py -x</automated>
  </verify>
  <acceptance_criteria>
    - Both parity tests pass (mutation + identity)
    - Existing Iberia 868 parity test stays green
    - `grep -n "snapshot_loader" backend/medieval_forge/services/pipeline/__init__.py` returns 2+ (inject + clear)
    - `grep -c "!= baseline_sha" backend/tests/parity/test_phase08_edit_visible_in_lookup.py` returns 1 (correct polarity)
  </acceptance_criteria>
  <done>D-17 enforced end-to-end; BLOCKER-1 closed.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| edit_events row → snapshot_loader → compute() | DB-persisted op log read into pipeline geometry |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-08-07c-01 | Tampering | Malicious edit_log smuggled in via DB | accept | Local-only single-user tool per RESEARCH §Security Domain; /editor/apply already validates ops server-side before persisting (08-07 Step 3); compute() trusts what's in the DB. |
| T-08-07c-02 | Information Disclosure | snapshot_loader Callable accidentally serialised in cache key | mitigate | dag.py STAGE_READS["manual_edit"] is `frozenset()` (no cfg fields read for token); snapshot_loader is explicitly excluded. Orchestrator clears `cfg.snapshot_loader = None` after compute() returns. |
| T-08-07c-03 | DoS | Pathologically large edit_log replayed every cache miss | mitigate | D-37 auto-snapshot caps edit_log size at 25 ops; older snapshots become the new baseline raster (compute starts from upstream merge output → applies at most 25 ops). |
</threat_model>

<verification>
- compute() identity path stays green (Iberia parity)
- compute() replay path mutates lookup_barony.png in parity test
- snapshot_loader injected and cleared per orchestrator invocation
- snapshot_loader NEVER serialised (not in STAGE_READS, cleared after compute)
- rasterio.features.shapes + rasterize used (not PIL, not hand-rolled)
- 5 unit tests + 2 parity tests pass
</verification>

<success_criteria>
**BLOCKER-1 closed.** D-17 enforced end-to-end: manual edits become the output of the manual_edit stage; lookup PNGs + Unity 12-file export reflect user edits. Identity carry-forward preserved.
</success_criteria>

<output>
After completion, create `.planning/phases/08-border-vertex-editor-manual-svg-style-vertex-editing-of-terr/08-07c-SUMMARY.md`.
</output>
