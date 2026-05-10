# Phase 04: Parameter Studio (Live Re-render) - Research

**Researched:** 2026-05-10
**Domain:** Incremental DAG pipeline cache + React slider UX + SSE cancel
**Confidence:** HIGH (all claims verified against codebase or locked decisions from CONTEXT.md)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01** — Split `cleanup_and_smooth` into 4 cacheable functions: `apply_median`, `remove_fragments`, `smooth_per_territory`, `merge_small_blobs`. Each takes `(input_array, cfg)`, returns `np.ndarray`.
- **D-02** — `version_token = sha256(stage_name + sorted_reads + sorted_upstream_tokens)[:16]`. Stage declares `reads: frozenset[str]` of cfg fields it consumes.
- **D-03** — `_STAGE_CACHE: dict[project_id, dict[stage_name, StageEntry]]`. `StageEntry = {token, array, prior_token, prior_array}`. Two versions per stage per project. Cleared on full `POST /generate`. In-memory only, no disk.
- **D-04** — `POST /api/v3/projects/{id}/render` + `GET /api/v3/projects/{id}/render/stream` SSE pair. Body: `{cfg_overrides: {smooth_sigma?, median_passes?, fragment_min_px?, blob_merge_px?, stage_view?}}`. Reuses `_RUN_QUEUES`/`_RUN_TASKS`. 409 if render or generate alive.
- **D-05** — Four sliders only: `smooth_sigma` [3.0–4.5] step 0.1, `median_passes` [1–12] step 1, `fragment_min_px` [0–2000] step 50, `blob_merge_px` [0–500] step 25.
- **D-06** — New collapsible left sidebar ~320px. Toggle button in WorkspaceToolbar. 4 SliderCards + StageViewToggle at top.
- **D-07** — 250ms `useDebouncedCallback`. On expiry: close active SSE, POST /render. Latest-wins: new debounce during in-flight render cancels the in-flight and starts new.
- **D-08** — Radix `Slider.Root` + numeric `<input type="number">` + default-tick mark + reset button per card. Numeric clamp + red flash on out-of-bounds. Reset reverts and fires re-render immediately (no debounce).
- **D-09** — Stage view is visualization only. Pipeline always runs to completion; toggle only re-points canvas hydrator at a different cached array.
- **D-10** — 5 stage views: `landmask`, `voronoi-raw`, `cleanup`, `smooth`, `render-final` (default).
- **D-11** — Toggle sits at top of left sidebar. Planner decides endpoint shape for intermediate-stage rasters.
- **D-12** — Barony name labels via Konva `Text` (planner may choose DOM overlay). Centered on barony centroid, 10px, white, 1px black halo, truncate at 12 chars. Visible when `layerVisibility.baronies === true`.
- **D-13** — Cancel = O(1) cache swap. On cancel: re-point canvas at `prior_array`, emit `stage_cancel` SSE event per affected stage carrying prior token. Frontend snaps to prior token, calls `Konva.clearCache()`, resets sliders to prior cfg values. No re-run. <50ms latency target.
- **D-14** — Cooperative `cfg.stop_event: threading.Event | None`. Each split function checks `stop_event.is_set()` at top; raises `StageCancelled`. New `POST /render/cancel` endpoint (or `DELETE /render`, planner picks) sets the stop_event.
- **D-15** — `zundo` `temporal` undo/redo does NOT land in Phase 04. Only per-slider reset (D-08) and cancel (D-13/D-14) ship.
- **D-16** — Cancel button: WorkspaceToolbar status badge becomes red Radix `Button color="red"` labeled "Cancelar" when `state ∈ {generating, rendering}`. Single-click, no confirmation modal (cancel is lossless — prior_token swap).
- **D-17** — Parity stays green at default cfg. `tests/parity/test_iberia_868.py` must produce byte-equal lookups / SSIM ≥ 0.98 visuals after D-01 split.
- **D-18** — `/render` builds a fresh `cfg = iberia_config()` + applies overrides per call. Project's persisted cfg is NOT mutated until a full `POST /generate`.

### Claude's Discretion

- Slider value persistence across sessions (ephemeral default — lost on refresh)
- Cache eviction beyond latest+prior (no LRU in Phase 04)
- Stage-view endpoint shape for non-final rasters (`GET /v3/projects/{id}/stage/{name}.png` recommended)
- `POST /render/cancel` vs `DELETE /render` (both valid)
- Stage-view ↔ LayerTogglePanel interaction when `stage_view ≠ render-final` (hide BaronyLayer/DecorationsLayer/RiversOverlay)
- Failure mode mid-`/render` (emit `stage_error`, swap to pre-render prior token)
- `Konva.clearCache()` invocation site (centralized in CanvasViewer on `cacheVersion` change recommended)
- `rendering` state extension vs `incremental` flag on existing states
- `stage_view` placement: keep off `RegionConfig` (UI selector, not pipeline param)
- Barony name labels: Konva `Text` vs DOM overlay (Konva recommended — pans/zooms natively)
- Border/hierarchy stage cacheability (compute once per project, pin in cache)

### Deferred (OUT OF SCOPE for Phase 04)

- `zundo` temporal undo/redo
- Disk-backed stage cache
- Sliders for `island_min_px`, `mountain_threshold`, `mountain_noise`, `coast_inner_width`
- Region YAML loader (Phase 05)
- Schema validation gate on incremental renders (Phase 06)
- LLM-driven parameter recommendations (Phase 07)
- Persistence of per-project slider values across sessions (default ephemeral)
- LRU eviction beyond latest+prior
- Stage-view radios for border/hierarchy/lookup/metadata/export
- Bypass-stage capability
- Concurrent `/render` requests per project
- Compound-undo button
</user_constraints>

---

## Summary

Phase 04 turns the Phase 03 read-only canvas into a parameter studio. Three independent technical problems must be solved in sequence: (1) split `cleanup_and_smooth` into 4 separately cacheable functions with a `version_token` DAG; (2) build the `POST /render` + SSE endpoint pair that walks the DAG incrementally; (3) add the ParameterSidebar with 4 sliders, 5 stage-view radios, and cancel mechanics.

All decisions are locked in CONTEXT.md D-01..D-18 plus the UI-SPEC contract. Research confirms: the codebase has all necessary scaffolding (SSE pattern, `_RUN_QUEUES`/`_RUN_TASKS`, `cfg.on_stage`, `cfg.stop_event` slot). No new library installs are needed except a debounce solution — `use-debounce` is absent from `package.json` and must be either added or hand-rolled.

**Primary recommendation:** Build the DAG abstraction first (Plan 04-01), then the backend endpoint (Plan 04-02), then the frontend sliders (Plan 04-03), then cancel mechanics (Plan 04-04), then barony labels + stage-view rasters (Plan 04-05), then UAT (Plan 04-06). SC-1 mandates the DAG commit arrives before any slider.

---

## Standard Stack

### Core (all already installed — no new installs required)
[VERIFIED: frontend/package.json, backend requirements]

| Library | Version | Purpose |
|---------|---------|---------|
| `@radix-ui/themes` | 3.3.0 | Slider.Root, Card, Button, RadioGroup — all slider chrome |
| `@radix-ui/react-icons` | 1.3.2 | UpdateIcon/ResetIcon for reset button, MixerHorizontalIcon for sidebar toggle |
| `zustand` | 5.0.12 | `useRunStore` extension + new `usePipelineParams` store |
| `@tanstack/react-query` | 5.99.0 | `useCanvasArtifacts` re-keying on `(stage_view, token)` |
| `konva` | 10.2.5 | `clearCache()` per layer; Konva `Text` for barony labels |
| `scipy.ndimage` | (pinned in requirements) | `gaussian_filter`, `median_filter`, `nd_label`, `binary_dilation` — same as cleanup.py today |
| `hashlib` (stdlib) | — | `sha256` for `version_token` derivation |
| `threading` (stdlib) | — | `threading.Event` for cooperative cancel; `threading.RLock` for `_STAGE_CACHE` |

### New Install Required

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `use-debounce` | `^10` | `useDebouncedCallback` for 250ms slider trigger | NOT in package.json [VERIFIED: package.json scan]; hand-roll alternative documented below |

**Hand-roll alternative (no install):**
```typescript
// src/hooks/useDebouncedCallback.ts
import { useRef, useCallback } from 'react'
export function useDebouncedCallback<T extends unknown[]>(
  fn: (...args: T) => void,
  delay: number,
): (...args: T) => void {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  return useCallback(
    (...args: T) => {
      if (timer.current !== null) clearTimeout(timer.current)
      timer.current = setTimeout(() => { fn(...args) }, delay)
    },
    [fn, delay],
  )
}
```
If `use-debounce@^10` is added, use `useDebouncedCallback` from it directly — same API.

---

## Architecture Patterns

### Recommended New File Layout

```
backend/medieval_forge/
├── services/pipeline/
│   ├── cleanup.py           # split: apply_median, remove_fragments,
│   │                        #        smooth_per_territory, merge_small_blobs
│   ├── cache.py             # NEW: _STAGE_CACHE, StageEntry, token helpers, RLock
│   ├── dag.py               # NEW: version_token derivation + DAG walker
│   └── __init__.py          # run_pipeline — expanded to call 4 split fns + emit
├── api/v3/
│   ├── render.py            # NEW: POST /render, GET /render/stream, POST /render/cancel
│   └── generate.py          # unchanged
frontend/src/
├── components/canvas/
│   ├── ParameterSidebar.tsx # NEW: 320px left sidebar
│   ├── SliderCard.tsx       # NEW: one slider card
│   ├── StageViewToggle.tsx  # NEW: 5-option radio group
│   └── CanvasViewer.tsx     # MODIFY: clearCache hook + stage_view routing
├── api/
│   ├── useRenderStream.ts   # NEW: sibling of useGenerateStream
│   └── render.ts            # NEW: postRender(), postRenderCancel()
├── hooks/
│   └── useDebouncedCallback.ts  # NEW (if no use-debounce install)
└── stores/
    ├── useRunStore.ts        # MODIFY: add 'rendering' state + cancel action
    └── usePipelineParams.ts  # NEW: slider values + stage_view client state
```

### Pattern 1: version_token Derivation (D-02)

Each stage function declares its reads. Token is deterministic hash of (name, read values, upstream tokens).

```python
# Source: 04-CONTEXT.md D-02 [VERIFIED]
import hashlib, json
from dataclasses import fields as dc_fields

def _serialize_cfg_field(value) -> str:
    """Stable string serialization for cfg field values."""
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True, default=str)
    return str(value)

def compute_version_token(
    stage_name: str,
    reads: frozenset[str],
    cfg,
    upstream_tokens: list[str],
) -> str:
    """sha256(name + sorted read values + sorted upstream tokens)[:16]."""
    parts = [stage_name]
    # Sort reads for determinism
    for field_name in sorted(reads):
        value = getattr(cfg, field_name, None)
        parts.append(f"{field_name}={_serialize_cfg_field(value)}")
    for tok in sorted(upstream_tokens):
        parts.append(tok)
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return digest[:16]
```

**Critical:** `RegionConfig` is a `@dataclass`, NOT pydantic. [VERIFIED: contracts.py line 46] Cannot use `.model_dump()`. Use `getattr(cfg, field_name)` + `json.dumps(value, sort_keys=True, default=str)`.

### Pattern 2: StageEntry Cache + RLock (D-03)

```python
# Source: 04-CONTEXT.md D-03 [VERIFIED against existing _RUN_QUEUES pattern]
# services/pipeline/cache.py
import threading
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

@dataclass
class StageEntry:
    token: str
    array: np.ndarray
    prior_token: Optional[str] = None
    prior_array: Optional[np.ndarray] = None

# Module-level: outer key = project_id, inner key = stage_name
_STAGE_CACHE: dict[str, dict[str, StageEntry]] = {}
_CACHE_LOCK = threading.RLock()

def cache_get(project_id: str, stage_name: str) -> Optional[StageEntry]:
    with _CACHE_LOCK:
        return _STAGE_CACHE.get(project_id, {}).get(stage_name)

def cache_put(project_id: str, stage_name: str, entry: StageEntry) -> None:
    """Swap on success only. Call ONLY when stage completes without cancel."""
    with _CACHE_LOCK:
        if project_id not in _STAGE_CACHE:
            _STAGE_CACHE[project_id] = {}
        _STAGE_CACHE[project_id][stage_name] = entry

def cache_clear_project(project_id: str) -> None:
    """Called on fresh POST /generate (D-03)."""
    with _CACHE_LOCK:
        _STAGE_CACHE.pop(project_id, None)
```

**RLock is required** because the asyncio event loop reads cache (to compute affected stages), while the worker thread writes it (after each stage completes). Numpy releases the GIL during array ops so two threads could race on the Python dict.

**Cache atomicity invariant:** Swap on success only. If the stage raises `StageCancelled` or any exception, the cache entry is NOT updated. The prior state is preserved intact. Cancel = O(1) because the prior_array already lives in the entry.

### Pattern 3: cleanup.py Split (D-01)

[VERIFIED: cleanup.py lines 39-97 read in full]

Current line ranges for the four sub-stages:
- **apply_median**: lines 40–48 (median filter loop)
- **remove_fragments**: lines 51–67 (fragment removal loop)
- **smooth_per_territory**: lines 70–83 (Gaussian smoothing, new result array allocated)
- **merge_small_blobs**: lines 86–95 (blob merge loop)

**Critical — copy semantics:** Lines 40–67 mutate `raw` in-place. Lines 69+ allocate new `result`. After split, each function must work on a copy of its input to preserve cache safety:

```python
# Source: cleanup.py analysis [VERIFIED]
def apply_median(raw: np.ndarray, land: np.ndarray, nb: int, cfg: RegionConfig) -> np.ndarray:
    """Stage 1: median filter passes. Returns new array (copy of raw, mutated)."""
    med = raw.copy()  # CRITICAL: copy to avoid mutating cached prior
    for i in range(cfg.median_passes):
        ri = med.astype(np.int32)
        ri[~land] = 9999
        sz = 11 if i < 2 else 9 if i < 4 else 7 if i < 6 else 5
        cl = median_filter(ri, size=sz).astype(np.int16)
        cl[~land] = -1
        v = (med >= 0) & (cl >= 0) & (cl < nb)
        med[v] = cl[v]
        med[~land] = -1
    return med

def remove_fragments(med: np.ndarray, land: np.ndarray, nb: int, cfg: RegionConfig) -> np.ndarray:
    """Stage 2: remove disconnected fragments. Returns new array (copy of med, mutated)."""
    frag = med.copy()  # CRITICAL: copy
    for bi in range(nb):
        # ... (verbatim fragment removal logic from lines 51-67)
    return frag

def smooth_per_territory(frag: np.ndarray, land: np.ndarray, cfg: RegionConfig) -> np.ndarray:
    """Stage 3: per-territory Gaussian smoothing. Allocates new result array."""
    # No copy needed — allocates fresh result (verbatim lines 70-83)
    h, w = frag.shape
    best = np.zeros((h, w), dtype=np.float32)
    result = np.full((h, w), -1, dtype=np.int16)
    # ... Gaussian loop
    result[~land] = -1
    return result

def merge_small_blobs(sm: np.ndarray, land: np.ndarray, nb: int, cfg: RegionConfig) -> np.ndarray:
    """Stage 4: merge tiny baronies. Returns new array (copy of sm, mutated)."""
    merged = sm.copy()  # CRITICAL: copy to preserve sm as cached 'smooth' stage output
    for bi in range(nb):
        # ... (verbatim blob merge logic from lines 86-95)
    return merged
```

**reads declarations** for each stage:
```python
STAGE_READS = {
    'median':   frozenset({'median_passes'}),
    'fragment': frozenset({'fragment_min_px'}),
    'smooth':   frozenset({'smooth_sigma'}),
    'merge':    frozenset({'blob_merge_px'}),
    'landmask': frozenset({'map_w', 'map_h', 'lon_min', 'lon_max', 'lat_min', 'lat_max'}),
    'border':   frozenset({'border_polygon', 'pt_duchies'}),
    'voronoi':  frozenset({'condados', 'rng_seed'}),
    'hierarchy':frozenset(),  # reads result array only, no cfg fields
    'render':   frozenset({'kingdom_colors', 'ocean_near', 'ocean_far', 'draw_names'}),
    'lookup':   frozenset(),
    'metadata': frozenset({'condados', 'duchies', 'kingdoms'}),
    'export':   frozenset(),
}
```

### Pattern 4: POST /render Endpoint (D-04)

Mirrors `api/v3/generate.py` [VERIFIED: generate.py read in full].

```python
# Source: 04-CONTEXT.md D-04 + generate.py template [VERIFIED]
# api/v3/render.py

@router.post("/{project_id}/render", status_code=202)
async def trigger_render(
    project_id: str,
    body: RenderRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    # 1. UUID validation + 404 check (same as generate.py)
    # 2. Single-flight gate — 409 if _RUN_TASKS[project_id] alive
    #    OR generate._RUN_TASKS[project_id] alive (cross-router check)
    # 3. Build fresh cfg = iberia_config() (D-18)
    # 4. Apply cfg_overrides from body
    # 5. Walk DAG: compute new tokens for all stages
    # 6. Identify which tokens differ from _STAGE_CACHE
    # 7. Schedule _render_producer task
    return {"run_id": ..., "affected_stages": [...], "status": "scheduled"}
```

**Key difference from generate:** `/render` walks the DAG first (sync, before scheduling) to compute `affected_stages`. Only those stages run in the producer thread.

### Pattern 5: Cooperative Cancel (D-14)

```python
# Source: 04-CONTEXT.md D-14 [VERIFIED against cleanup.py structure]

class StageCancelled(Exception):
    """Raised by a split function when stop_event is set."""

def apply_median(raw, land, nb, cfg):
    if cfg.stop_event and cfg.stop_event.is_set():
        raise StageCancelled("median cancelled")
    med = raw.copy()
    # ... rest of median logic ...
    return med

# Cancel endpoint:
@router.post("/{project_id}/render/cancel", status_code=200)
async def cancel_render(project_id: str) -> dict:
    task = _RENDER_TASKS.get(project_id)
    if task and not task.done():
        stop_event = _RENDER_STOP_EVENTS.get(project_id)
        if stop_event:
            stop_event.set()  # cooperative signal
    return {"status": "cancel_requested"}
```

**Important:** `asyncio.Task.cancel()` cannot interrupt numpy/scipy CPU work mid-call. Cooperative `stop_event.is_set()` checks between stage calls is the only reliable cancel mechanism. [VERIFIED: D-14 analysis]

**On StageCancelled in the producer:**
```python
except StageCancelled:
    # Emit stage_cancel events for all affected stages with prior_tokens
    for stage_name in affected_stages:
        entry = cache_get(project_id, stage_name)
        prior_tok = entry.prior_token if entry else None
        _emit(queue, "stage_cancel", stage_name, prior_tok or "", None)
    # DO NOT update cache — invariant: cache unchanged on cancel
    await _set_status(project_id, "generated", sf)  # revert to prior state
```

### Pattern 6: useRenderStream (Frontend)

Exact sibling of `useGenerateStream` [VERIFIED: useGenerateStream.ts read in full]. Only differences:
1. URL: `/render/stream` instead of `/generate/stream`
2. Handles new `stage_cancel` event type
3. Calls `useRunStore.getState().finishWithCancel(priorTokenMap)` on cancel

```typescript
// Source: useGenerateStream.ts pattern [VERIFIED]
case 'stage_cancel':
  // msg.stage = stage name, msg.message = prior_token
  run.revertStage(msg.stage, msg.message)
  return
```

### Pattern 7: useDebouncedCallback + Latest-Wins

```typescript
// Source: 04-CONTEXT.md D-07 [VERIFIED - no debounce lib in package.json]
function useParameterStudio(projectId: string) {
  const renderStream = useRenderStream()
  const debouncedRender = useDebouncedCallback(
    (overrides: CfgOverrides) => {
      renderStream.close()         // cancel in-flight SSE
      postRenderCancel(projectId)  // set stop_event on backend (fire-and-forget)
      postRender(projectId, overrides).then(({ run_id }) => {
        runStore.start(run_id, 'rendering')
        renderStream.subscribe(projectId)
      })
    },
    250,
  )
  return { debouncedRender }
}
```

### Pattern 8: Konva.clearCache() — Centralized Hook

[VERIFIED: CanvasViewer.tsx read — `clearCache()` is NOT currently present]

```typescript
// Source: CanvasViewer.tsx analysis + CONTEXT D-04/D-13 [VERIFIED]
// Add inside CanvasViewer after hydration completes:
useEffect(() => {
  if (stageRef.current) {
    stageRef.current.findAll('Layer').forEach((layer) => {
      ;(layer as Konva.Layer).clearCache()
    })
  }
}, [cacheVersion, stageView])  // fire on both version change AND stage view switch
```

### Pattern 9: Stage-View Intermediate Rasters

New endpoint `GET /api/v3/projects/{id}/stage/{name}.png` [RECOMMENDED per CONTEXT Claude's Discretion].

```python
# api/v3/render.py — additional route
@router.get("/{project_id}/stage/{stage_name}.png")
async def get_stage_raster(project_id: str, stage_name: str) -> Response:
    """Return a colorized PNG of the cached array for the given stage.
    Used by StageViewToggle to re-point the canvas hydrator."""
    entry = cache_get(project_id, stage_name)
    if entry is None:
        raise HTTPException(404, "stage not in cache; run /render first")
    # Colorize int16 array → PNG using matplotlib tab20 colormap
    img_bytes = _array_to_png(entry.array, colormap='tab20')
    return Response(content=img_bytes, media_type="image/png")
```

`landmask` is bool → grayscale. `voronoi-raw`, `cleanup`, `smooth` are int16 → tab20 colormap (territory IDs 0..N colored distinctly). `render-final` uses the existing `visual_condado.png` / `visual_barony.png` from artifacts — no new serializer needed for the default view.

### Pattern 10: Barony Name Labels (D-12)

[VERIFIED: UI-SPEC §BaronyLabel — Konva Text recommended]

**Use Konva `Text` inside `BaronyLayer`** (not DOM overlay). DOM overlay (HoverTooltip pattern) is for ephemeral hover state. Barony labels are persistent and need to pan/zoom natively with the Konva stage.

```typescript
// Source: UI-SPEC §BaronyLabel [VERIFIED]
// Inside BaronyLayer.tsx, when layerVisibility.baronies === true:
{baronies.features.map((f) => {
  const [cx, cy] = getCentroidPixel(f, stageSize)
  const name = f.properties?.name ?? ''
  return (
    <Text
      key={`label-${f.properties?.id}`}
      x={cx}
      y={cy}
      text={name.length > 12 ? name.slice(0, 11) + '…' : name}
      fontSize={10}
      fill="#FFFFFF"
      align="center"
      verticalAlign="middle"
      offsetX={/* half text width */}
      shadowColor="black"
      shadowBlur={1}
      shadowOffset={{ x: 0, y: 0 }}
      shadowOpacity={1}
    />
  )
})}
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Debounce | Custom timer logic | `use-debounce@^10` or hand-roll `useDebouncedCallback` | Race conditions with ref cleanup on unmount; cancel semantics |
| SHA-256 hash | Custom string hash | `hashlib.sha256` (stdlib) | Determinism, collision resistance |
| Thread-safe dict | `threading.Lock` + manual double-check | `threading.RLock` | RLock is reentrant; DAG walker may call cache from same thread |
| PNG colormap | Custom palette | `matplotlib.cm.tab20` + PIL | N territories need visually distinct colors; tab20 gives 20 cycles |
| SSE producer | New queue mechanism | Reuse `_RUN_QUEUES`/`_RUN_TASKS` from `generate.py` | Already battle-tested in Phase 03 |
| Slider component | Custom range input | Radix `Slider.Root` | Thumb sizing, keyboard nav, ARIA all built in |

---

## Common Pitfalls

### Pitfall 1: In-Place Mutation Breaks Cache
**What goes wrong:** `apply_median` and `remove_fragments` mutate their input array in-place (confirmed from cleanup.py lines 47, 67). If the cached `prior_array` reference is passed directly to the split function without `.copy()`, the prior state is silently destroyed.
**Why it happens:** numpy operations like `raw[v] = cl[v]` modify in-place. `prior_array` is a numpy array reference, not a value copy.
**How to avoid:** Each split function starts with `inp = input_array.copy()`. Never mutate the argument received from the cache.
**Warning signs:** Cancel swaps to prior_array but canvas shows the partially-mutated state; parity test fails after cancel+restore.

### Pitfall 2: version_token Derivation for `condados` List
**What goes wrong:** `cfg.condados` is a Python list of dicts. `str(cfg.condados)` produces non-deterministic output across Python versions (dict key ordering). Token differs on identical inputs.
**Why it happens:** `RegionConfig` is `@dataclass` — no `.model_dump()` or guaranteed field ordering.
**How to avoid:** Use `json.dumps(value, sort_keys=True, default=str)` for all list/dict cfg fields. Test: run `compute_version_token` twice with same cfg, assert identical output.
**Warning signs:** DAG always thinks every stage is dirty; parity regression test for incremental path fails intermittently.

### Pitfall 3: Single-Flight Gate Across Two Routers
**What goes wrong:** `/render` checks `_RENDER_TASKS[project_id]` but NOT `generate._RUN_TASKS[project_id]`. A full `/generate` plus `/render` can run concurrently, corrupting `_STAGE_CACHE`.
**Why it happens:** `_RUN_TASKS` in `generate.py` is module-level and not imported into `render.py`.
**How to avoid:** Import or re-expose `_RUN_TASKS` from `generate.py` in the 409 gate of `render.py`. Check both dicts.
**Warning signs:** Race condition artifacts; parity test passes in isolation but fails under concurrent load test.

### Pitfall 4: frontend PIPELINE_STAGES Count Mismatch
**What goes wrong:** `useRunStore.PIPELINE_STAGES` has 11 entries today [VERIFIED: useRunStore.ts lines 18-30]. After D-01 split, the backend emits 12 stage events (rename `cleanup` → `median`, insert `fragment`). The frontend `isPipelineStage()` guard silently drops unknown stage names.
**Why it happens:** `useGenerateStream` and `useRenderStream` both call `isPipelineStage()` before dispatching to the store; unknown stages fall through to `return` with no warning.
**How to avoid:** Expand `PIPELINE_STAGES` to 12 entries in the same commit that changes `__init__.py` emit points. Run vitest after.
**Warning signs:** Stage progress bar misses `fragment` stage; tests still pass (guard is silent).

### Pitfall 5: RLock vs Lock for _STAGE_CACHE
**What goes wrong:** Using `threading.Lock` causes deadlock if the DAG walker calls `cache_get` from inside a `with _CACHE_LOCK:` block in the same thread (e.g., iterative DAG walk that reads cache mid-walk).
**Why it happens:** `Lock` is not reentrant. The event loop thread reads cache for the 409 gate check while the worker thread writes.
**How to avoid:** Use `threading.RLock`. The lock is reentrant within the same thread.

### Pitfall 6: Konva.clearCache() Timing
**What goes wrong:** `clearCache()` called before the new raster data is fetched causes the layer to render a blank frame.
**Why it happens:** `useEffect([cacheVersion])` fires synchronously after the re-render that set the new cacheVersion, but TanStack Query data fetch is async.
**How to avoid:** Call `clearCache()` inside the TanStack Query `onSuccess` callback or after `useCanvasArtifacts` data is confirmed non-null for the new token, not on the cacheVersion state change alone.

### Pitfall 7: SC-3 Timing Budget Is Tight
**What goes wrong:** σ=3.0→4.5 path (smooth + merge stages, ~250 territories at 1920×1080) may exceed 500ms budget.
**Why it happens:** Per CONTEXT D-07, the budget is ≤250ms debounce + ≤200ms compute + ≤50ms canvas hydrate. Smooth stage at 250 territories is the bottleneck.
**How to avoid in Wave 1:** Add a timing fixture in `tests/unit/test_cleanup_split.py` that runs `smooth_per_territory` on the iberia_868 fixture and asserts < 300ms. If it exceeds 300ms, apply `gaussian_filter(truncate=2.0)` (reduces kernel radius from default 4σ to 2σ, ~2× speedup).
**Warning signs:** SC-3 Playwright UAT times out; backend SSE `stage_done` for smooth arrives > 350ms after `stage_start`.

### Pitfall 8: stage_view Must NOT Live on cfg
**What goes wrong:** Adding `stage_view` to `RegionConfig` causes it to participate in `version_token` derivation (unless `reads` explicitly excludes it). More importantly, it would cause parity tests to fail if `stage_view != 'render-final'` is accidentally left in cfg when a full `/generate` runs.
**Why it happens:** The DAG walker iterates all declared reads; an undeclared field that is nonetheless on cfg can be accidentally included.
**How to avoid:** Keep `stage_view` client-only. Pass as body param to `/render`; do NOT persist on project cfg. The `GET /stage/{name}.png` endpoint reads it as a path param, not from cfg.

---

## Code Examples

### version_token — Full Round-Trip Test
```python
# Source: D-02 analysis [VERIFIED against contracts.py structure]
def test_version_token_determinism():
    cfg = iberia_config()
    tok1 = compute_version_token('median', frozenset({'median_passes'}), cfg, [])
    tok2 = compute_version_token('median', frozenset({'median_passes'}), cfg, [])
    assert tok1 == tok2  # same inputs → same token

def test_version_token_isolation():
    cfg1 = iberia_config(); cfg1.smooth_sigma = 3.0
    cfg2 = iberia_config(); cfg2.smooth_sigma = 4.5
    tok_median_1 = compute_version_token('median', frozenset({'median_passes'}), cfg1, [])
    tok_median_2 = compute_version_token('median', frozenset({'median_passes'}), cfg2, [])
    assert tok_median_1 == tok_median_2  # smooth_sigma change does NOT invalidate median
    tok_smooth_1 = compute_version_token('smooth', frozenset({'smooth_sigma'}), cfg1, [tok_median_1])
    tok_smooth_2 = compute_version_token('smooth', frozenset({'smooth_sigma'}), cfg2, [tok_median_2])
    assert tok_smooth_1 != tok_smooth_2  # smooth_sigma change DOES invalidate smooth
```

### SSE envelope extension for /render
```python
# Source: generate.py _emit pattern [VERIFIED] + D-13 token field
def _emit(queue, event_type, stage, message="", progress=None, token=None):
    payload = {
        "event_type": event_type,
        "stage": stage,
        "message": message,
        "progress": progress,
        "token": token,          # Phase 04 addition — client correlates with cache
    }
    queue.put_nowait(f"data: {json.dumps(payload)}\n\n")
```

### useRunStore extension
```typescript
// Source: useRunStore.ts analysis [VERIFIED]
export type RunState = 'idle' | 'ingesting' | 'generating' | 'generated' | 'error' | 'rendering'

// Add to RunStoreState interface:
priorTokens: Record<string, string>  // stage_name → prior_token for cancel snap
startRender: (runId: string) => void
revertStage: (stage: string, priorToken: string) => void
cancelRender: () => void             // transitions rendering → generated

// In useRunStore create():
startRender: (runId) => set({ state: 'rendering', runId, priorTokens: {} }),
revertStage: (stage, priorToken) =>
  set((s) => ({ priorTokens: { ...s.priorTokens, [stage]: priorToken } })),
cancelRender: () => set({ state: 'generated', currentStage: null }),
```

### WorkspaceToolbar Cancel integration
```typescript
// Source: UI-SPEC §WorkspaceToolbar Extensions [VERIFIED]
// Per UI-SPEC: isRunning check adds 'rendering'
const isRunning = state === 'generating' || state === 'ingesting' || state === 'rendering'
const showCancel = state === 'generating' || state === 'rendering'

// Cancel button replaces status badge:
{showCancel ? (
  <Button color="red" variant="solid" onClick={handleCancel}>
    Cancelar
  </Button>
) : (
  <GenerateStatusBadge state={state} currentStage={currentStage} />
)}
```

---

## State of the Art

| Old Approach (Phase 03) | Phase 04 Approach | Impact |
|------------------------|-------------------|--------|
| Single `cleanup_and_smooth` call (1 cache entry) | 4 separately cacheable functions | σ change only reruns smooth+merge, not median |
| 11 fake emit markers (3 simultaneous for cleanup) | 12 real emit markers (one per split stage) | Accurate stage progress in UI |
| No `cfg.stop_event` (slot reserved) | `cfg.stop_event: threading.Event` wired | Cooperative cancel per D-14 |
| `PIPELINE_STAGES` has 11 entries | Expanded to 12 (rename cleanup→median, add fragment) | Stage progress panel accurate |
| `_STAGE_CACHE` absent | `services/pipeline/cache.py` with `_STAGE_CACHE` + RLock | Incremental re-render possible |
| `Konva.clearCache()` absent [VERIFIED] | Centralized `useEffect` in CanvasViewer | Geometry mutation artifacts prevented |
| No `/render` endpoint | `POST /render` + `GET /render/stream` + `POST /render/cancel` | Incremental parameter iteration |

**Deprecated after Phase 04 (within codebase):**
- The 3-rapid-emit pattern in `__init__.py` lines 125–132 (fake `cleanup/smooth/merge` markers around one call) is replaced by 4 real calls with real emits.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `use-debounce` absent from `package.json` | Standard Stack | If it is present under a different import path, the hand-roll recommendation is unnecessary but harmless |
| A2 | `smooth_per_territory` at 250 territories takes 150–300ms on target hardware | Pitfall 7 / SC-3 | If faster, 250ms debounce is sufficient; if slower, need truncate=2.0 optimization |
| A3 | `matplotlib` available in backend venv (for tab20 colormap on stage rasters) | Pattern 9 | If absent, use a hand-rolled tab20 palette array instead; or use PIL with hardcoded color cycle |

All other claims in this document are tagged `[VERIFIED]` against codebase reads or `[VERIFIED: CONTEXT.md D-NN]` against locked decisions.

---

## Open Questions

1. **Single-flight gate cross-router**
   - What we know: `_RUN_TASKS` in `generate.py` is module-level dict; `render.py` is a separate module.
   - What's unclear: Should `render.py` import `generate._RUN_TASKS` directly, or should they be moved to a shared `api/v3/_run_state.py`?
   - Recommendation: Move `_RUN_QUEUES` + `_RUN_TASKS` to `api/v3/_run_state.py` in Wave 0 (Plan 04-01 or 04-02). Both `generate.py` and `render.py` import from there. Avoids circular imports.

2. **Canvas sidecars on incremental `/render`**
   - What we know: `run_pipeline` emits `territories.geojson` + `baronies.geojson` in its final step. `/render` only runs affected stages — not necessarily the full export step.
   - What's unclear: Do barony/condado centroids change when `merge_small_blobs` reshapes baronies? If yes, the `baronies.geojson` sidecar is stale after a merge-slider change.
   - Recommendation: If `merge` or `smooth` is in `affected_stages`, re-emit the canvas sidecars after the merge stage completes. If only `median` or `fragment` stages are affected (which don't reshape final geometry), sidecars are fine unchanged.

3. **matplotlib dependency for stage-view rasters**
   - What we know: `tab20` colormap is standard matplotlib. `matplotlib` may not be in the backend venv.
   - Recommendation: Check `pip show matplotlib` before planning wave assignment. If absent, hand-roll a 20-color cycle palette using PIL directly. The palette itself is stable (matplotlib tab20 colors are public).

---

## Environment Availability

| Dependency | Required By | Available | Notes |
|------------|------------|-----------|-------|
| `use-debounce` npm package | D-07 debounced slider | Not installed [VERIFIED: package.json] | Hand-roll alternative documented above |
| `matplotlib` (Python) | Stage-view PNG colormap | Unknown — check in Wave 0 | Fallback: hardcoded 20-color PIL palette |
| `threading.Event` | D-14 cooperative cancel | Available (stdlib) | Already used in Phase 03 patterns |
| `hashlib` | D-02 version_token | Available (stdlib) | — |
| All Radix Themes components | Slider.Root, RadioGroup, etc. | Installed 3.3.0 [VERIFIED] | — |

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (backend) + vitest (frontend) |
| Config file | `pytest.ini` / `vitest.config.ts` |
| Quick run (backend) | `pytest tests/unit/test_cleanup_split.py -x -q` |
| Quick run (frontend) | `npx vitest run src/components/canvas/__tests__/` |
| Full suite (backend) | `pytest -m "unit or parity" -q` |
| Full suite (frontend) | `npx vitest run` |

### Phase Requirements → Test Map

| Req | Behavior | Test Type | Automated Command | Gap? |
|-----|----------|-----------|-------------------|------|
| SC-1 | DAG with version_token drawn before first slider | unit | `pytest tests/unit/test_dag.py -x` | Wave 0 gap |
| SC-2 | Backend incremental endpoint; in-memory cache | unit + integration | `pytest tests/unit/test_render_endpoint.py -x` | Wave 0 gap |
| D-17 | Parity stays green at default cfg | parity | `pytest tests/parity/test_iberia_868.py` | Exists — must stay green |
| D-17 | Incremental path matches full path bit-for-bit | parity | `pytest tests/parity/test_iberia_868_render_default.py` | Wave 0 gap |
| SC-3 | σ change < 500ms | e2e | Playwright: `tests/uat/test_parameter_studio.py` | Wave 0 gap |
| SC-4 | Cancel restores prior state; clearCache fires | e2e | Playwright: `tests/uat/test_cancel_render.py` | Wave 0 gap |
| D-01 | 4 split functions produce same output as monolith | unit | `pytest tests/unit/test_cleanup_split.py -x` | Wave 0 gap |

### Wave 0 Gaps (test files that must be created before implementation)
- `tests/unit/test_cleanup_split.py` — unit tests for 4 split functions + parity vs monolith at default cfg
- `tests/unit/test_dag.py` — version_token determinism + isolation (σ change doesn't invalidate median)
- `tests/unit/test_render_endpoint.py` — `/render` 202, 409 gate, affected_stages computation
- `tests/parity/test_iberia_868_render_default.py` — incremental path == full path at default cfg
- `tests/uat/test_parameter_studio.py` — SC-3 Playwright scenario
- `frontend/src/components/canvas/__tests__/ParameterSidebar.test.tsx`
- `frontend/src/api/__tests__/useRenderStream.test.ts`

---

## Security Domain

Phase 04 introduces no new authentication surfaces. The `/render` and `/render/cancel` endpoints follow the same pattern as Phase 03's `/generate`. ASVS V5 input validation applies to `cfg_overrides` body.

| ASVS Category | Applies | Control |
|---------------|---------|---------|
| V5 Input Validation | yes | Clamp overrides to D-05 bounds before applying to cfg; reject unknown field names |
| V2 Authentication | no | Local tool, no auth layer |
| V6 Cryptography | no | `hashlib.sha256` for tokens is integrity, not confidentiality |

**Threat: slider values out of bounds.** Client sends `smooth_sigma=9999` in `/render` body. Mitigation: `cfg.smooth_sigma = max(3.0, min(4.5, override.smooth_sigma))` in the endpoint before token derivation. CLAUDE.md rule #2 is the authority.

---

## Sources

### Primary (HIGH confidence — verified against codebase)
- `backend/medieval_forge/services/pipeline/cleanup.py` — split line ranges, mutation semantics
- `backend/medieval_forge/services/pipeline/contracts.py` — `RegionConfig` is `@dataclass`, four slider fields already present
- `backend/medieval_forge/services/pipeline/__init__.py` — `run_pipeline`, fake 3-emit pattern, current emit order
- `backend/medieval_forge/api/v3/generate.py` — SSE template: `_RUN_QUEUES`, `_RUN_TASKS`, `_emit`, `_make_on_stage`, 409 gate
- `frontend/src/stores/useRunStore.ts` — 11 stages, 5 states, actions interface
- `frontend/src/api/useGenerateStream.ts` — EventSource pattern, envelope schema
- `frontend/package.json` — confirmed installed packages; confirmed `use-debounce` absent
- `.planning/phases/04-parameter-studio-live-re-render/04-CONTEXT.md` — 18 locked decisions
- `.planning/phases/04-parameter-studio-live-re-render/04-UI-SPEC.md` — component specs, layout, copywriting

### Secondary (MEDIUM confidence — locked decisions from discussion session)
- `.planning/STATE.md` — Phase 03 complete, canvas infrastructure confirmed
- `.planning/ROADMAP.md` §Phase 04 — SC-1..SC-4 acceptance criteria

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified against package.json / imports
- Architecture patterns: HIGH — all templates verified against codebase reads
- Pitfalls: HIGH — all derived from concrete code analysis (cleanup.py, generate.py, etc.)
- SC-3 timing budget: MEDIUM — performance estimate is [ASSUMED] without hardware profiling

**Research date:** 2026-05-10
**Valid until:** 2026-06-10 (stable stack; 30-day window)
