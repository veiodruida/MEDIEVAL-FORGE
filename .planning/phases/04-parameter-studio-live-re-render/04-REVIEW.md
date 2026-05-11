---
phase: 04-parameter-studio-live-re-render
reviewed: 2026-05-11T00:00:00Z
depth: standard
files_reviewed: 24
files_reviewed_list:
  - backend/medieval_forge/services/pipeline/cache.py
  - backend/medieval_forge/services/pipeline/dag.py
  - backend/medieval_forge/services/pipeline/cleanup.py
  - backend/medieval_forge/services/pipeline/contracts.py
  - backend/medieval_forge/services/pipeline/__init__.py
  - backend/medieval_forge/api/v3/_run_state.py
  - backend/medieval_forge/api/v3/render.py
  - backend/medieval_forge/api/v3/generate.py
  - backend/medieval_forge/main.py
  - frontend/src/api/render.ts
  - frontend/src/api/useRenderStream.ts
  - frontend/src/stores/usePipelineParams.ts
  - frontend/src/stores/useRunStore.ts
  - frontend/src/hooks/useParameterStudioDispatch.ts
  - frontend/src/hooks/useCanvasArtifacts.ts
  - frontend/src/components/canvas/SliderCard.tsx
  - frontend/src/components/canvas/StageViewToggle.tsx
  - frontend/src/components/canvas/ParameterSidebar.tsx
  - frontend/src/components/canvas/CanvasViewer.tsx
  - frontend/src/components/canvas/BaronyLayer.tsx
  - frontend/src/components/workspace/WorkspaceToolbar.tsx
  - frontend/src/pages/ProjectDetail.tsx
  - pyproject.toml
  - frontend/playwright.config.ts
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-05-11T00:00:00Z
**Depth:** standard
**Files Reviewed:** 24
**Status:** issues_found

## Summary

Phase 04 delivers a well-structured parameter studio: the DAG version-token system is deterministic and correctly isolated per-stage, the SSE producer/consumer pair is robust for the happy path, and the cancel revert design (D-13) is sound in concept. The cooperative cancel, selective disk writes, and TanStack cache-bust chain all follow through correctly — with one exception.

One critical bug breaks the cancel path precisely when it matters most: when `stop_event` fires during the disk-write phase (which, with the SC-3 budget intentionally relaxed to 30s, is the most likely cancel point). A `TypeError` from a wrong-arity constructor call silently converts an expected `stage_cancel` SSE flow into an `error` event, bypassing the revert path entirely.

Two warnings cover a post-cancel 409 race that puts the run store in the `error` state instead of gracefully no-oping, and a `_RUN_QUEUES`/`_RUN_TASKS` leak that leaves late-arriving `GET /render/stream` consumers hanging forever. Two info items cover a dead `sf` parameter and the kernel-size schedule being silently mismatched when `median_passes` is set above 8.

---

## Critical Issues

### CR-01: `StageCancelled` called with wrong arity — cancel mid-write raises `TypeError` instead of entering the revert path

**File:** `backend/medieval_forge/services/pipeline/__init__.py:129`

**Issue:** `_write_outputs_to_disk` defines a local `_check_cancel` helper that raises `StageCancelled("write", "write_outputs")` — two positional arguments. `StageCancelled.__init__` (defined in `cleanup.py:32`) accepts exactly one: `stage_name: str`. This call raises `TypeError: __init__() takes 2 positional arguments but 3 were given`, which the producer's broad `except Exception` in `render.py:172` catches and emits as an `error` SSE event, not a `stage_cancel` event.

Consequence: when the user cancels while the render phase is writing visual PNGs (the most likely cancel point given the 30s SC-3 budget), the frontend receives `error` instead of `stage_cancel` — `usePipelineParams.revertValues()` is never called, the slider UI is left in the post-cancel position, and `useRunStore` transitions to `'error'` instead of `'generated'`. The entire D-13 cancel revert path is bypassed.

**Fix:**
```python
# backend/medieval_forge/services/pipeline/__init__.py:125-129
def _check_cancel() -> None:
    """Raise StageCancelled (a pseudo-cancel) if stop_event is set mid-write."""
    if cfg.stop_event is not None and cfg.stop_event.is_set():
        from .cleanup import StageCancelled
        raise StageCancelled("write")  # one arg only — matches __init__(self, stage_name: str)
```

---

## Warnings

### WR-01: Cancel→POST race puts the run store in `error` state instead of gracefully retrying

**File:** `frontend/src/hooks/useParameterStudioDispatch.ts:32-41` and `frontend/src/components/canvas/ParameterSidebar.tsx:37-47`

**Issue:** Both dispatch sites follow the latest-wins sequence: `postRenderCancel` → `postRender`. `postRenderCancel` returns 200 as soon as `stop_event.set()` is called, but the worker thread takes up to ~0.5s to reach the next `_check_cancel` and exit. Until the producer task's asyncio Task is `.done()`, `is_run_alive()` still returns `'render'`, and the immediately following `postRender` call receives a 409. The 409 is caught at `catch (e)` and passed to `useRunStore.getState().finish('error', 'RENDER_BUSY')`, transitioning the store to `'error'` state — requiring the user to manually recover.

`postRenderCancel` succeeding does NOT mean the pipeline task has exited. The gap between `stop_event.set()` and the task being marked done is a real window the debounce timer can fall into.

**Fix:** Add a short retry on 409 after a cancel, or treat `RENDER_BUSY` from the post-cancel POST as a non-fatal condition that schedules a retry instead of surfacing an error:

```typescript
// frontend/src/hooks/useParameterStudioDispatch.ts — wrap postRender in retry logic
try {
  const { run_id } = await postRender(projectId, diff, stageView)
  useRunStore.getState().startRender(run_id)
  usePipelineParams.getState().markRendered(values)
  onRenderStarted?.(run_id)
} catch (e) {
  const msg = (e as Error).message
  if (msg === 'RENDER_BUSY') {
    // Cancel was accepted but pipeline hasn't exited yet — re-queue debounce
    dispatch()  // dispatch is the DebouncedState ref; re-queues at 250ms
    return
  }
  useRunStore.getState().finish('error', msg)
}
```

The same fix applies to the identical catch block in `ParameterSidebar.tsx:45-47`.

---

### WR-02: `_RUN_QUEUES` and `_RUN_TASKS` never evicted — late `GET /render/stream` hangs forever

**File:** `backend/medieval_forge/api/v3/render.py:177-180` and `backend/medieval_forge/api/v3/generate.py:151-152`

**Issue:** The `finally` block in `_render_producer` pops `_RUN_STOP_EVENTS` and `_RUN_KIND` but leaves `_RUN_QUEUES[project_id]` and `_RUN_TASKS[project_id]` populated. The `stream_render` endpoint checks `queue = _RUN_QUEUES.get(project_id)` and returns 404 only when the key is absent. After a run completes, the key is still present (queue is drained, task is done). A late-arriving `GET /render/stream` call passes the 404 guard and then awaits `queue.get()` forever, because the terminal `None` was already consumed.

Same issue in `_generate_producer`/`stream_generate`. The Pitfall 9 comment in `generate.py:205` correctly documents the refresh-mid-run limitation, but the claim that a POST-run stream returns 404 is incorrect — it hangs instead.

**Fix:**
```python
# backend/medieval_forge/api/v3/render.py — extend the finally block
finally:
    await queue.put(None)  # terminal sentinel
    _RUN_STOP_EVENTS.pop(project_id, None)
    _RUN_KIND.pop(project_id, None)
    _RUN_QUEUES.pop(project_id, None)   # prevent late-subscriber hang
    _RUN_TASKS.pop(project_id, None)    # prevent stale task reference
```

Apply the same fix in `generate.py`'s `_generate_producer` finally block.

---

### WR-03: Dispatch logic duplicated between `ParameterSidebar.tsx` and `useParameterStudioDispatch.ts` — divergence risk

**File:** `frontend/src/components/canvas/ParameterSidebar.tsx:32-50` and `frontend/src/hooks/useParameterStudioDispatch.ts:27-42`

**Issue:** `ParameterSidebar` inlines a complete, independent copy of the latest-wins dispatch logic (`postRenderCancel` → diff check → `postRender` → `startRender` → `markRendered` → `subscribe`). `useParameterStudioDispatch` exports the same sequence as a reusable hook, which is only consumed by unit tests (`usePipelineParams.test.ts`). Neither imports the other. The two implementations are currently in sync, but any future fix to one (such as the WR-01 RENDER_BUSY retry) must be applied to both or the behavior will diverge silently.

**Fix:** `ParameterSidebar` should import and use `useParameterStudioDispatch` instead of duplicating the logic, or `useParameterStudioDispatch` should be removed and the canonical implementation lives in `ParameterSidebar`. The hook should be wired to `renderStream.subscribe` to handle the SSE subscription gap:

```typescript
// ParameterSidebar.tsx — replace inlined dispatchRender with:
import { useParameterStudioDispatch } from '../../hooks/useParameterStudioDispatch'

const dispatch = useParameterStudioDispatch(projectId, () => {
  renderStream.subscribe(projectId)
})
const debouncedRender = dispatch  // DebouncedState already
```

---

## Info

### IN-01: `sf` parameter in `_render_producer` is accepted but never used

**File:** `backend/medieval_forge/api/v3/render.py:108`

**Issue:** `_render_producer` accepts a fourth parameter `sf` (an `async_sessionmaker`) which is never referenced inside the function. `AsyncSessionLocal` is used directly on line 154 instead. The parameter was likely copied from `_generate_producer`'s signature but was not wired up. It is not a functional bug (the DB write works), but it is a misleading signature that creates dead code.

**Fix:**
```python
# render.py — remove the unused parameter
async def _render_producer(
    project_id: str,
    overrides: dict,
    queue: asyncio.Queue,
    # sf removed — AsyncSessionLocal is imported directly
) -> None:
```

And update the `asyncio.create_task` call at render.py:219 to match:
```python
task = asyncio.create_task(
    _render_producer(project_id, overrides, queue),
)
```

---

### IN-02: `apply_median` kernel-size schedule is hardcoded for 8 passes; passes 9-12 silently use size 5

**File:** `backend/medieval_forge/services/pipeline/cleanup.py:55`

**Issue:** The kernel-size schedule `11/11/9/9/7/7/5/5` is written as a chain of comparisons against fixed index thresholds (`i < 2`, `i < 4`, `i < 6`). When `median_passes` is set above 8 (the UI slider allows up to 12), passes 8-11 all use size 5. This is not documented and may produce unexpected smoothing behavior at non-default `median_passes` values. The CLAUDE.md canonical schedule is 8 passes, so the discrepancy only appears when a user explicitly explores the higher range via the slider.

**Fix:** Document the behavior explicitly, or clamp the useful slider range to match the designed schedule:

```python
# cleanup.py:55 — add a comment making the schedule's extent explicit
sz = 11 if i < 2 else 9 if i < 4 else 7 if i < 6 else 5
# NOTE: kernel schedule is designed for 8 passes (11,11,9,9,7,7,5,5).
# Passes i >= 8 use sz=5 (flat). median_passes up to 12 is accepted
# by the API but extra passes are identical to the last designed pass.
```

Alternatively, clamp `CfgOverrides.median_passes` upper bound to `ge=1, le=8` in `render.py:59` to match the designed schedule, or extend the schedule to cover 12 passes.

---

_Reviewed: 2026-05-11T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
