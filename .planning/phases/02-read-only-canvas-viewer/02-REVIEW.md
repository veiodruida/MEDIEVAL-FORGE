---
phase: 02-read-only-canvas-viewer
reviewed: 2026-04-18T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - backend/medieval_forge/services/territories_geojson.py
  - backend/medieval_forge/services/baronies_geojson.py
  - backend/medieval_forge/services/generator.py
  - backend/tests/test_territories_geojson.py
  - backend/tests/test_baronies_geojson.py
  - backend/tests/test_generator_e2e.py
  - frontend/src/hooks/useCanvasArtifacts.ts
  - frontend/src/components/canvas/__tests__/CanvasViewer.test.tsx
  - frontend/src/components/canvas/TerritoryLayer.tsx
  - frontend/src/components/canvas/BaronyLayer.tsx
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 02: Code Review Report — Plan 02-04 (Gap Closure G-01/G-02/G-03)

**Reviewed:** 2026-04-18T00:00:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found
**Diff Range:** `0bf5bbd..HEAD` (7 commits, plan 02-04)

## Summary

This review covers the gap-closure plan 02-04 within phase 02-read-only-canvas-viewer. It overwrites the prior REVIEW.md (which scoped plans 01–03). The diff closes three verification gaps:

- **G-01 (format mismatch):** `emit_territories_from_disk` / `emit_baronies_from_disk` now parse the real `{"r,g,b": idx}` schema written by `lib/map_generator.py` SECTION 10, instead of an imagined `{condado_id: "#hex"}` shape. New `condado_colors.json` and `barony_colors.json` sidecars are emitted alongside (frontend-consumable hex map) while the Unity-consumed `lookup_*_colors.json` keep their original schema.
- **G-02 (silent swallow):** the previous `try/except` around the emitter calls in `_run_pipeline_sync` is gone; emitter errors now propagate to `run_generation` and surface as `status='error_generating'` with `last_error` populated.
- **G-03 (missing integration test):** `test_generator_e2e.py` adds two BLOCKING-grade tests that exercise the real read-back path end-to-end and assert exception propagation.

**D-04 black-box constraint preserved:** `git diff --stat 0bf5bbd..HEAD -- backend/medieval_forge/lib/map_generator.py` shows zero changes — the vendored generator is untouched.

**Quality is high overall.** Tests cover the primary positive path, the malformed-key negative path, the out-of-range-skip behavior, the sidecar emission, and the BLOCKING e2e flow. Zero-padded hex (`#0a141e` not `#a141e`) is explicitly asserted. The `STRtree.query` usage in `territories_geojson.py:116-117` correctly relies on Shapely 2.x returning numpy int indices (verified live).

Issues found are bounded and non-blocking for the gap closure itself: one duplicate-definition code smell, one latent concurrency hazard in pre-existing code that the diff did not introduce but did not fix either, and two minor cleanups in the frontend wiring and test mock surface.

## Warnings

### WR-01: Duplicate definition of `_cleanup_territory_module`

**File:** `backend/medieval_forge/services/generator.py:89` and `backend/medieval_forge/services/generator.py:124`
**Issue:** The same function is defined twice with identical bodies. The second definition silently shadows the first. This is a real maintenance hazard — a future edit to the lines 89-90 body will be silently overridden by lines 124-125 at import time, and any reader is forced to scroll the whole module to confirm which copy is "live." The duplication appears to predate this diff but lives in a file that plan 02-04 actively edits, so it is in-scope to flag. The shim near line 124 is a no-op shadow with no other purpose.
**Fix:**
```python
# Remove the second copy at lines 124-125 entirely:
def _cleanup_territory_module(name: str) -> None:
    sys.modules.pop(name, None)
```
Keep only the definition at line 89. No call sites change.

### WR-02: `_patch_reload_for_synthetic` mutates `importlib.reload` globally — not safe for concurrent generations

**File:** `backend/medieval_forge/services/generator.py:107-121`
**Issue:** `_patch_reload_for_synthetic` does `_importlib_mod.reload = _safe_reload` and restores `_real_reload` in the `finally`. `run_generation` is invoked from `api/generate.py` as a FastAPI `BackgroundTasks` job (see `api/generate.py:57`), and the project layer offers no per-process serialization. If two generations run concurrently:

1. Thread A enters the context, captures `_real_reload = importlib.reload` (the genuine one), patches the module attribute.
2. Thread B enters, captures `_real_reload = importlib.reload` — but this is now Thread A's `_safe_reload`, not the real one. Thread B then patches the attribute again with its own `_safe_reload` that closes over A's safe reload.
3. Thread B's `finally` restores its captured `_real_reload` — which is A's safe reload, not the genuine `importlib.reload`. The genuine reload reference is now lost from the module attribute until Thread A's `finally` runs. Worse, if Thread A finishes first, its `finally` restores the genuine reload, but Thread B's later `finally` then overwrites it with A's safe reload — leaving the patched function permanently installed.

This was not introduced by plan 02-04, but plan 02-04 actively edits `_run_pipeline_sync` and the same concurrency window is now also in the path of the new emitter calls. With G-02 making the pipeline crash loudly on bad data, the chance of one generation interrupting another mid-flight goes up, not down.

**Fix:** Either serialize generation behind a per-process `threading.Lock` (or a per-project `asyncio.Lock` at the api layer), or replace the global mutation with a thread-local trampoline. Minimal patch:
```python
import threading
_RELOAD_LOCK = threading.Lock()

@contextmanager
def _patch_reload_for_synthetic(synthetic_module_name: str):
    _real_reload = importlib.reload
    def _safe_reload(module: types.ModuleType) -> types.ModuleType:
        if getattr(module, "__name__", None) == synthetic_module_name:
            return module
        return _real_reload(module)
    with _RELOAD_LOCK:
        import importlib as _importlib_mod
        _importlib_mod.reload = _safe_reload  # type: ignore[method-assign]
        try:
            yield
        finally:
            _importlib_mod.reload = _real_reload  # type: ignore[method-assign]
```
The lock makes the patch effectively serialized for the duration of `generate_maps()`, which is acceptable for a local-tool workload but should be documented. Long-term, refactor `load_territory_data` upstream so the synthetic module short-circuit lives in `_inject_territory_module` (e.g., set `mod.__spec__` to a spec whose `loader` returns `mod` from `exec_module`) — but that touches `lib/map_generator.py` and violates D-04, so the lock is the pragmatic fix.

## Info

### IN-01: `barony_colors.json` is fetched by the frontend but never consumed in the render path

**File:** `frontend/src/hooks/useCanvasArtifacts.ts:156-166` and `frontend/src/components/canvas/CanvasViewer.tsx:68`
**Issue:** `useCanvasArtifacts` returns five queries; consumer code at `CanvasViewer.tsx:68` destructures as `const [territoriesQ, baroniesQ, condadoColorsQ, , metaQ] = ...` — index 3 (the `barony_colors` query) is intentionally skipped. `BaronyLayer.tsx:26` reads the per-feature `b.fill` from `BaronyRender`, which is already resolved server-side from `baronies.geojson` properties. The sidecar fetch therefore costs one HTTP request, two TanStack-Query cache entries, and `Infinity` GC time without serving any render path. The sidecar is symmetrical with `condado_colors.json` and may be intentional future-proofing.
**Fix:** Either drop the `barony_colors.json` query from the hook (and the matching whitelist entry in `generator.py:74` if no other consumer is planned), or document the intent inline so a future cleanup pass does not delete what looks like dead code. If the symmetry with `condado_colors.json` is the design intent, a one-line comment on the query block is enough:
```ts
// Fetched for parity with condado_colors.json + future use; BaronyLayer
// currently consumes per-feature `fill` from baronies.geojson properties.
```

### IN-02: `panToGeoCenter` mocked as `vi.fn()` instead of a callable returning the right shape

**File:** `frontend/src/components/canvas/__tests__/CanvasViewer.test.tsx:24-31`
**Issue:** The test mock at line 27 does `panToGeoCenter: vi.fn()`. The real `panToGeoCenter` takes `(stage, ...)` and calls `applyPanClamp` for its side effects (no return). `vi.fn()` defaults to returning `undefined`, which happens to match the real signature, so this test passes — but the same pattern at line 28 wraps `makeWheelHandler: vi.fn(() => () => {})` with the curried-handler shape, and line 29 wraps `makeDragBoundFunc: vi.fn(() => (pos) => pos)`. The asymmetry suggests the author thought about return shapes for some mocks but not for `panToGeoCenter`. Today this is harmless; if `panToGeoCenter` ever gains a return value (e.g., the new pan offset for chained animations), the mock will silently return `undefined` and the test will keep passing while the real callsite breaks.
**Fix:** Document the void return in the mock to make intent explicit, and pin the contract:
```ts
// panToGeoCenter has no return value — side effect only (mutates Stage).
panToGeoCenter: vi.fn<typeof import('../../../hooks/useZoomPan').panToGeoCenter>(),
```
Or accept the current shape and leave a `// returns void` comment.

---

_Reviewed: 2026-04-18T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
