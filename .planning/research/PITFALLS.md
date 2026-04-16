# PITFALLS.md — Medieval Forge

> Known pitfalls from the PROJECT.md briefing (land mask resolution, NEAREST upscale, smoothing σ, merge threshold, ByOriginalIdx lookup, Y-axis flip, PPU) are treated as solved and are NOT repeated here. This file covers the eight unknown areas surfaced by greenfield research.

---

## [Packaging] — Vite Build Not Included in Wheel

**What goes wrong:** The `dist/` folder produced by `npm run build` is a build artifact that git ignores and pip packaging tools never see unless you explicitly declare it. Running `pip install .` succeeds silently, but `medieval-forge start` then serves a 404 because the static directory is empty or missing.

**Warning signs:**
- `package_data` or `MANIFEST.in` lists `medieval_forge/frontend/dist/**` but the directory does not exist at wheel-build time because the frontend was never built in CI
- `pip install medieval-forge` from PyPI works locally but the installed package has no `dist/`
- `importlib.resources.files("medieval_forge").joinpath("frontend/dist/index.html")` raises `FileNotFoundError` on a clean machine

**Prevention:**
- Add a `build` step to `pyproject.toml` via a custom setuptools `BuildPy` subclass that runs `npm ci && npm run build` before the wheel is assembled. Alternatively use a `Makefile` / `hatch` build hook
- Declare explicitly: `package_data = {"medieval_forge": ["frontend/dist/**/*", "frontend/dist/assets/**/*"]}` — glob `**/*` alone does NOT recurse in older setuptools versions; list both levels
- Lock the Vite `base` option to `"./"` (relative) in `vite.config.ts` — the default `"/"` produces absolute asset URLs that break when FastAPI serves the app from any sub-path
- Add a startup assertion in the CLI entry point: if `dist/index.html` is missing, print a clear error "Frontend not bundled — run `npm run build` or reinstall the package" and exit 1 rather than silently serving an empty stage

**Phase:** Packaging / CLI entry point (late phase, but must be decided at project scaffold)

---

## [Packaging] — SPA 404 on Deep-Link / Browser Refresh

**What goes wrong:** FastAPI's `StaticFiles(directory=..., html=True)` serves `index.html` only for the exact root path. Any React Router route deeper than `/` (e.g. `/project/3/canvas`) returns a raw 404 from the file server on hard refresh, breaking the entire app for users who bookmark or share URLs.

**Warning signs:**
- Navigating in-app works; hitting F5 or pasting a URL returns `{"detail": "Not Found"}`
- The issue is invisible in development (Vite dev server handles it) and only appears in the packaged build

**Prevention:**
- Mount the API router first, then add a catch-all route at the very end of the FastAPI app that returns `FileResponse(dist_dir / "index.html")` for any path that does not start with `/api`
- Do NOT rely on `StaticFiles(html=True)` alone for SPA routing — it does not forward unknown paths to index.html
- Order matters: `app.mount("/api", api_router)` before `app.mount("/", StaticFiles(...))`, with the catch-all added via `@app.get("/{full_path:path}")`

**Phase:** Packaging / FastAPI setup

---

## [Packaging] — Stale Vite Asset Hashes After Rebuild

**What goes wrong:** Vite content-hashes JS/CSS chunks on every build (`main-Bx3kLpQr.js`). If a user has the app open, navigates away, and the server was restarted with a new build, the browser fetches `index.html` (which the Python server sends with `Cache-Control: no-cache`) but then tries to load the old hashed chunk URLs — which no longer exist — producing `Failed to fetch dynamically imported module` errors.

**Warning signs:**
- Works after force-refresh, fails after soft navigation to a new tab
- Errors appear only in users who keep the tab open across a `medieval-forge` restart

**Prevention:**
- Set `Cache-Control: no-cache, no-store` on the `index.html` response in FastAPI (the static chunks themselves can be cached forever since their hash changes with content)
- For a local tool with one user, acceptable mitigation is simply documenting "restart the tab after upgrading"
- Avoid `base: "/"` in vite.config — use `base: "./"` so chunk imports are relative and immune to path-prefix changes

**Phase:** Packaging

---

## [Konva] — Full Layer Redraw on Every State Update

**What goes wrong:** In React-Konva, every Zustand state change that touches a territory (e.g., moving a capital) triggers a React re-render of the entire `<Layer>` containing all 500–1000 `<Line>` polygons. Konva redraws the whole layer canvas, causing visible jank (>16ms per frame) even when only one polygon changed.

**Warning signs:**
- Moving a capital is smooth at 50 territories, sluggish at 300, and drops to <10 FPS at 800
- React DevTools profiler shows all `<TerritoryPolygon>` components re-rendering on every drag tick
- `layer.batchDraw()` is not being called; instead raw `.draw()` is called on shape change

**Prevention:**
- Wrap each `<TerritoryPolygon>` in `React.memo` with a custom comparator that checks only `territory.id` and `territory.points`; unaffected polygons must not re-render at all
- Separate the canvas into at minimum three layers: `backgroundLayer` (terrain, static), `territoriesLayer` (polygon fills and borders), `interactionLayer` (drag handles, vertex editors, hover highlights). Set `listening(false)` on background and territories layers when no edit mode is active
- For the active drag operation, lift the dragged shape to a dedicated top layer to avoid re-drawing 999 other polygons per tick
- Use `shape.cache()` on territories that are not being edited; invalidate cache only when that specific territory's geometry changes
- Set `perfectDrawEnabled(false)` and `shadowEnabled(false)` on all polygon shapes — the shadow compositing pass is expensive and not needed for territory fills

**Phase:** Canvas Editor (Phase 2 / Phase 3)

---

## [Konva] — Hit Detection Accuracy on Complex Polygon Shapes

**What goes wrong:** Konva's default hit detection for `<Line closed>` polygon shapes uses a separate hidden canvas. For territories with many vertices (50–200 points from Voronoi + Wikidata municipality outlines), the hit canvas rendering is accurate but slow. The second trap is pointer events firing on the bounding box, not the actual polygon — Konva computes hit by reading a pixel from the hit canvas, which is correct only if the hit canvas is in sync with the scene canvas.

**Warning signs:**
- Clicking near but outside a narrow peninsula registers a hit
- After a `.cache()` call without a `.clearCache()`, the hit region no longer matches the visual shape
- `shape.listening(false)` set on a layer disables hit for ALL shapes including ones that should be interactive

**Prevention:**
- Never call `.cache()` on a shape without also invalidating the hit cache when geometry changes: `shape.clearCache()` then `shape.cache()`
- For complex polygons, provide a simplified `hitFunc` that uses a convex hull or bounding box for coarse hit, then a point-in-polygon JS test for fine precision. This dramatically reduces per-pixel hit canvas work
- Track which layer has `listening(true)` explicitly — when switching between View mode and Edit mode, toggle listening on the correct layer, not the stage
- Use `Konva.hitOnDragEnabled = true` if drag-start miss-fires on mobile/trackpad

**Phase:** Canvas Editor

---

## [Konva] — Memory Leak from Orphaned Tween / Shape References

**What goes wrong:** When territory polygons are removed (merge, split, project reload), Konva shapes are destroyed but React-Konva refs and Konva Tween objects may hold references keeping them in memory. In a long session with many merge/split operations this accumulates.

**Warning signs:**
- Chrome DevTools heap snapshot grows across merge/split cycles even when the territory count stays constant
- `Konva.stages[0]._getIntersection()` traverses destroyed shapes

**Prevention:**
- Always call `shape.destroy()` explicitly on removal, or ensure React-Konva handles it by unmounting the component (it does, but only if the component tree actually unmounts — conditional renders that just hide shapes do not destroy them)
- Any `Konva.Tween` must be `.destroy()`ed in a `useEffect` cleanup
- Do not store Konva shape instances in Zustand state — store only data; let React-Konva create/destroy the Konva nodes from the data

**Phase:** Canvas Editor

---

## [Wikidata] — 60-Second Hard Timeout Kills Municipality Ingestion

**What goes wrong:** The Wikidata public SPARQL endpoint enforces a hard 60-second query deadline. A single query fetching all municipalities of a large country (Spain: ~8000 municipalities, France: ~35000 communes) with labels and coordinates in multiple languages will reliably time out. There is no way to extend the timeout on the public endpoint; only OAuth "trusted" users get 5 minutes (not applicable here).

**Warning signs:**
- Query works for Portugal (308 municipalities) but silently returns empty or errors for Spain
- Adding `rdfs:label` with `LANG()` filtering to a large result set jumps from 3s to 65s+
- Bounding-box geographic queries for countries >3° latitude/longitude span time out

**Prevention:**
- Paginate with `LIMIT` + `OFFSET` in batches of 500–1000 items maximum; never attempt a full-country fetch in one request
- Fetch labels and coordinates in a second pass query keyed on the QIDs retrieved in the first pass (two-phase fetch)
- Strip `OPTIONAL { ?item rdfs:label ... }` from the main structural query; labels are a separate call
- Implement exponential backoff: first retry after 2s, second after 8s, third after 30s. The endpoint is rate-limited at 60 CPU-seconds/minute per IP+UserAgent; a single slow query can exhaust the budget and cause subsequent fast queries to also fail
- Set a descriptive `User-Agent` header (`medieval-forge/0.1 contact@example.com`) — Wikimedia blocks user agents that omit this, and a proper UA helps with rate limit bucket separation
- Cache raw SPARQL results to SQLite immediately on successful fetch so re-ingestion is never needed for the same country/period combination

**Phase:** Ingestion (Phase 1)

---

## [Wikidata] — SPARQL Pagination with OFFSET Is Inconsistent on Live Data

**What goes wrong:** Wikidata's SPARQL endpoint (Blazegraph) does not guarantee stable ordering across paginated `LIMIT/OFFSET` queries when the underlying data is being updated (it always is). Pages may contain duplicates or skip items if a write occurs between page 1 and page 2.

**Warning signs:**
- Total ingested count from paginated fetch is consistently ~5% lower than the known number of municipalities
- Duplicate QIDs appear in the merged results

**Prevention:**
- Use `ORDER BY ?item` on every paginated query to pin the sort key against the QID URI (which is stable)
- After all pages are fetched, deduplicate by QID before inserting to SQLite
- Compare total fetched count against a single `SELECT (COUNT(DISTINCT ?item) AS ?count)` preflight query; if difference is >2%, log a warning and offer a retry

**Phase:** Ingestion (Phase 1)

---

## [SQLAlchemy/aiosqlite] — Alembic Migrations Fail Silently with Async Engine

**What goes wrong:** Alembic's auto-generated `env.py` uses the synchronous `engine_from_config()`. When pointed at an `aiosqlite://` URL it either throws a cryptic driver error at startup or (worse) runs successfully but generates empty migration files because `Base.metadata` was never populated — model modules were not imported before `autogenerate` ran.

**Warning signs:**
- `alembic revision --autogenerate -m "init"` produces a migration with empty `upgrade()` and `downgrade()` bodies
- The error `asyncio driver not supported in synchronous context` appears only during `alembic upgrade head`, not during `alembic revision`

**Prevention:**
- Wrap migrations with `asyncio.run()` and `connection.run_sync(do_migrations)` using `async_engine_from_config`
- In `env.py`, import every model module explicitly before calling `target_metadata = Base.metadata` — autogenerate silently produces no-ops if models are not in the Python import graph at migration time
- Test the migration chain on a clean SQLite file in CI: `rm -f test.db && alembic upgrade head`

**Phase:** Backend scaffold (Phase 1)

---

## [SQLAlchemy/aiosqlite] — Implicit BEGIN / SAVEPOINT Desync

**What goes wrong:** SQLite with `aiosqlite` defers `BEGIN` statements further than expected. Calling `session.begin_nested()` (SAVEPOINT) inside an `async with session.begin()` block can fail or silently not create the savepoint because the outer BEGIN was never actually emitted to the connection. The symptom is a rollback that rolls back more than intended, corrupting merge/split operations.

**Warning signs:**
- An exception inside a territory merge rolls back changes that were committed in a previous operation within the same request
- Log shows `BEGIN (implicit)` was never emitted; the first statement in the transaction is the actual DML
- Tests with `pytest-anyio` and shared sessions pass but production requests have inconsistent rollback scope

**Prevention:**
- Disable aiosqlite's automatic BEGIN management by setting `isolation_level = None` on the raw DBAPI connection via an event listener on `connect`, then manually emit `BEGIN` in a `begin` event listener
- Prefer explicit `async with session.begin(): ...` blocks for every database operation rather than relying on autocommit/autobegin
- For merge/split operations specifically, use a single top-level transaction and avoid `begin_nested()` unless the SQLite savepoint workaround is applied; otherwise use application-level rollback logic

**Phase:** Backend (territory merge/split operations)

---

## [SQLAlchemy/aiosqlite] — Hanging Thread from Unclosed aiosqlite Connection

**What goes wrong:** aiosqlite v0.22.0 introduced a regression where the dialect's `close()` method is never called on the underlying connection object. If the FastAPI app shuts down without explicit engine disposal, the aiosqlite background thread stays alive, causing the process to hang instead of exiting cleanly. This affects `medieval-forge start` — the CLI process will not return to the shell prompt after Ctrl+C.

**Warning signs:**
- `medieval-forge start` does not exit after Ctrl+C; requires `kill -9`
- The Python process shows an extra thread in `threading.enumerate()` named `aiosqlite_X`

**Prevention:**
- Register a shutdown event on the FastAPI app: `@app.on_event("shutdown") async def shutdown(): await engine.dispose()`
- Pin `aiosqlite>=0.20,<0.22` until the fix is confirmed in a release, OR upgrade past the patch release that resolves issue #13039 in sqlalchemy

**Phase:** Backend scaffold

---

## [Zustand/zundo] — Entire State Snapshot Per Undo Step

**What goes wrong:** zundo's default behavior stores a full deep copy of the Zustand state object on every state change. For Medieval Forge, the state includes all territory polygons (each with 50–200 lat/lon coordinate pairs), the full GeoJSON for each territory, terrain paint data, and UI state. With 800 territories, one state snapshot can be 2–5 MB. At 50 undo steps that is 100–250 MB allocated in the browser — triggering GC pauses and eventual tab crashes on low-memory machines.

**Warning signs:**
- Chrome Memory tab shows heap growing linearly with edit operations
- Undo/redo becomes slower over a long session
- The `temporalStore.pastStates.length` is exactly 50 but memory is not bounded

**Prevention:**
- Use the `partialize` option to exclude everything that is not user-editable from the undo history: exclude `selectedTerritoryId`, `hoveredTerritoryId`, `zoom`, `panOffset`, `isLoading`, `llmStatus`, and all other transient UI state
- Use the `diff` option to store only the changed keys rather than full snapshots. For territory edits this means storing `{ territories: { [id]: newGeometry } }` not the entire territory map
- Set `limit: 50` explicitly and verify memory stays bounded with `performance.measureUserAgentSpecificMemory()` in dev
- Do NOT store Konva shape instances, Blob URLs, or canvas references anywhere in Zustand state — these are unserializable and will cause zundo to capture them in snapshots, making undo non-functional after serialization round-trips

**Phase:** Canvas Editor (undo/redo implementation)

---

## [Zustand/zundo] — Undo Steps Firing on Non-User Interactions

**What goes wrong:** Zustand state updates triggered by API responses (Wikidata ingestion completing, LLM research finishing, Voronoi recalc returning) are indistinguishable to zundo from user edits. Without filtering, the user's Ctrl+Z undoes a background Voronoi recalculation instead of their last drag operation.

**Warning signs:**
- Ctrl+Z after an ingestion operation reverts the just-loaded territory list, not any user edit
- The `pastStates` stack fills up with LLM polling status updates

**Prevention:**
- Wrap all non-user-initiated state updates in a `temporal.pause()` / `temporal.resume()` bracket: `useMyStore.temporal.getState().pause(); setState({ territories: newData }); useMyStore.temporal.getState().resume()`
- Alternatively use `partialize` to include only the fields that represent user-editable canvas state (geometry, terrain paint, capital positions) and exclude everything else at the zundo level
- Add a `handleUndoableAction()` wrapper in the store that explicitly gates what goes into history

**Phase:** Canvas Editor

---

## [LLM] — Ollama Returns Streaming Text, Not JSON Object

**What goes wrong:** The Claude API (`claude-sonnet-4-6`) supports structured output with `response_format` enforcing JSON schema. Ollama's REST API (`/api/generate`) returns a streaming text response by default. When using the Ollama adapter to extract kingdom/duchy hierarchies, the response is a stream of JSON delta objects, not a single parseable JSON blob. Naive `response.json()` on the full response body fails because the body is newline-delimited JSON (NDJSON), not a single object.

**Warning signs:**
- Ollama requests return `200 OK` but `json.loads(response.text)` throws `JSONDecodeError: Extra data`
- The structured response is split across 20–50 streaming chunks

**Prevention:**
- For Ollama, either use `stream: false` in the request body (supported since Ollama 0.1.14) for non-streaming responses, OR set `format: "json"` to enable JSON mode (supported since Ollama 0.1.9 for models that support it)
- When using Ollama `format: "json"`, the model still needs a system prompt explicitly telling it to produce valid JSON matching the schema — JSON mode prevents non-JSON output but does not enforce the schema structure
- Implement the adapter interface as: Claude path uses `anthropic` SDK with `response_format`; Ollama path uses `httpx` with `stream=False` and `format="json"`, with schema in system prompt

**Phase:** LLM Research feature

---

## [LLM] — Nested JSON Extraction Fails on Large Hierarchy Responses

**What goes wrong:** For a country with many historical divisions (Iberian Peninsula 868 AD has 90+ condados nested under kingdoms and duchies), the LLM response is a large deeply-nested JSON object. Common failure modes beyond the briefing's 3-retry approach:

1. **Key renaming**: The model returns `"duchy_name"` instead of `"name"` or `"territories"` instead of `"children"` — this passes a `json.loads()` check but fails Pydantic validation
2. **Phantom fields**: The model adds fields not in the schema (`"population"`, `"capital_city"`, `"notes"`) which Pydantic allows by default unless `model_config = ConfigDict(extra="forbid")`
3. **Empty array hallucination prevention**: When a kingdom has no sub-duchies (common in the briefing's data), the LLM often hallucinates sub-entities rather than returning `"children": []`
4. **Integer vs string QIDs**: Wikidata QIDs returned by the model may be `45` (int) instead of `"Q45"` (string with prefix)

**Warning signs:**
- Pydantic validation passes but downstream code fails on `KeyError`
- Territory count after LLM research is consistently ~20% higher than Wikidata count (hallucinated sub-territories)

**Prevention:**
- Use `model_config = ConfigDict(extra="forbid")` on all Pydantic models for LLM output — fail fast on unexpected fields
- Add a post-validation check: total leaf node count must be within 20% of the Wikidata municipality count; if outside this range, reject the response as hallucinated and retry with a more constrained prompt
- Normalize QID format in a post-processing step: `str(qid).lstrip("Q").strip()` then `f"Q{clean}"` to handle both int and string variants
- For the retry prompt, include the Pydantic validation error message verbatim — models correct key-naming issues when shown the exact error

**Phase:** LLM Research feature

---

## [Geometry] — `shapely.set_precision()` Silently Reverses Winding Order

**What goes wrong:** `shapely.set_precision(geom, grid_size=0.0001)` is commonly used to snap coordinates to a grid before Voronoi operations or before storing GeoJSON. As a confirmed Shapely bug (issue #1950, unfixed as of 2.1.x), `set_precision()` always returns coordinates in clockwise order regardless of the input's orientation. RFC 7946 GeoJSON requires exterior rings to be counter-clockwise. The result is GeoJSON that many validators and some Unity importers reject as invalid.

**Warning signs:**
- `geojson-validator` reports "exterior ring not counter-clockwise" on all territories after a precision snap step
- Shapely `is_valid` returns `True` (Shapely does not check winding order for validity)
- The issue is invisible until GeoJSON is consumed by a downstream tool that enforces RFC 7946

**Prevention:**
- Always call `shapely.orient(geom, sign=1.0)` immediately after any `set_precision()` call — this enforces counter-clockwise exterior rings and clockwise holes
- `shapely.to_geojson()` does NOT enforce winding order — use `orient()` before calling it, or use the `geojson` Python library's `Feature` serialization which will enforce it
- Add a post-serialization assertion in the export pipeline: `assert geojson_polygon["coordinates"][0]` area via the shoelace formula is positive (counter-clockwise)

**Phase:** Geometry operations (Voronoi, merge, split, export)

---

## [Geometry] — Coordinate Drift Between Geo and Canvas Pixels Across Zoom Levels

**What goes wrong:** A territory centroid stored as `(lon=-7.4521, lat=39.8832)` is converted to canvas pixels at zoom level Z using a linear bounding-box projection: `px = (lon - bbox.minLon) / (bbox.maxLon - bbox.minLon) * canvasWidth`. At zoom level 1 this gives `px=1024.3`. At zoom level 3 (canvas 4x larger) the same formula gives `px=4097.2`. If the zoom transform is applied to the Konva stage rather than re-projecting the coordinates, the centroid stays at `1024.3` in Konva's local coordinate space and is correctly scaled by the stage transform — no drift.

The drift happens when: (a) coordinates are re-projected at each zoom level (accumulated rounding), or (b) the bounding box used for projection is different from the one used to build the polygons (off-by-one on bbox edges).

**Warning signs:**
- Territory labels or capitals visually drift from their polygon centers as zoom increases
- After a pan-zoom cycle, clicking on a territory hits a different territory than the one under the cursor
- The mismatch is small at zoom 1x (~0.5px) but grows to 3–5px at zoom 8x

**Prevention:**
- Compute geo-to-pixel projection ONCE at page load using a fixed reference bounding box (the project's `bbox` stored in SQLite). Store the resulting pixel coordinates as the canonical representation on the frontend
- Use Konva's built-in stage scale/position for all zoom and pan — never re-project coordinates on zoom; let the stage transform handle it
- The bounding box projection must use the same `(minLon, minLat, maxLon, maxLat)` on both Python backend (where polygons are computed) and TypeScript frontend (where they are rendered). Pass this bbox explicitly in the API response alongside GeoJSON, do not re-derive it from the GeoJSON envelope
- Use `float64` for all coordinate storage in SQLite (not `REAL` which is float32 in some ORM mappings). Shapely, scipy, and numpy all default to float64; losing precision on SQLite write and re-read introduces a 6th decimal place error (~10cm) that is invisible but accumulates across polygon vertices

**Phase:** Canvas Editor (coordinate system setup, Phase 1 scaffold)

---

## [Geometry] — Voronoi Adjacency Breaks After Territory Merge

**What goes wrong:** When two territories are merged, the Voronoi seed point (capital) of one is deleted. The `scipy.spatial.Voronoi` adjacency information (`ridge_points`, `ridge_vertices`) is indexed by the original point array indices. After a merge removes index `i`, all indices `>i` shift by one, making every stored adjacency reference stale. A partial Voronoi recalculation for "affected neighbors only" then operates on wrong neighbor lists.

**Warning signs:**
- After the first merge, the next capital drag causes a neighbor territory to snap to a wrong position
- `KeyError` in the `*ByOriginalIdx` lookup (even with the known fix applied) after multiple sequential merges

**Prevention:**
- After any merge or split, rebuild the full neighbor lookup from scratch using the current point array — do not attempt incremental index patching
- Assign stable UUIDs to territories and maintain a `uuid → point_array_index` mapping that is rebuilt fresh on every Voronoi computation, never mutated in place
- The briefing's `*ByOriginalIdx` fix addresses a lookup offset bug; this pitfall is separate — it concerns the rebuild trigger, not the lookup direction

**Phase:** Canvas Editor (merge/split operations)
