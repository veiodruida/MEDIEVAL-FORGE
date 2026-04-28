---
phase: quick-260428-elq
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/medieval_forge/services/baronies_builder.py
  - backend/medieval_forge/api/ingest.py
  - backend/tests/services/test_baronies_builder.py
  - backend/tests/api/test_baronies_endpoint.py
  - frontend/src/components/ingest/BaronyGranularitySlider.tsx
  - frontend/src/api/client.ts
autonomous: true
requirements:
  - ETAPA-2-BARONIES-BUILDER
must_haves:
  truths:
    - "POST /api/projects/{id}/baronies?count=all writes raw/baronies.geojson with 1 feature per município"
    - "POST /api/projects/{id}/baronies?count=N writes raw/baronies.geojson with exactly N clustered features"
    - "Each output feature has properties.id, properties.name, properties.centroid, properties.municipality_ids and a Polygon/MultiPolygon geometry equal to the union of its member municipalities"
    - "Endpoint returns 404 when raw/municipalities.geojson does not exist for the project"
    - "Endpoint returns 422 when count is not in {all, 50, 250, 1000} or otherwise invalid"
    - "Frontend BaronyGranularitySlider exposes 50 / 250 / 1000 / Todos presets and reports the chosen count via onChange"
    - "Frontend api/client.ts exposes buildBaronies(projectId, count) hitting POST /api/projects/{id}/baronies?count=..."
  artifacts:
    - path: "backend/medieval_forge/services/baronies_builder.py"
      provides: "build_baronies_from_osm(municipalities_geojson_path, target_count) -> dict"
      contains: "def build_baronies_from_osm"
    - path: "backend/medieval_forge/api/ingest.py"
      provides: "POST /projects/{id}/baronies endpoint"
      contains: "/baronies"
    - path: "frontend/src/components/ingest/BaronyGranularitySlider.tsx"
      provides: "BaronyGranularitySlider React component"
    - path: "frontend/src/api/client.ts"
      provides: "buildBaronies API client function"
      contains: "buildBaronies"
    - path: "backend/tests/services/test_baronies_builder.py"
      provides: "5 unit tests for builder service"
    - path: "backend/tests/api/test_baronies_endpoint.py"
      provides: "5 endpoint integration tests"
  key_links:
    - from: "backend/medieval_forge/api/ingest.py"
      to: "backend/medieval_forge/services/baronies_builder.py"
      via: "build_baronies_from_osm() call inside the new POST /baronies handler"
      pattern: "build_baronies_from_osm"
    - from: "frontend/src/components/ingest/BaronyGranularitySlider.tsx"
      to: "frontend/src/api/client.ts (buildBaronies)"
      via: "consumer wires onChange → buildBaronies(projectId, count)"
      pattern: "buildBaronies"
    - from: "backend/medieval_forge/services/baronies_builder.py"
      to: "<project>/raw/municipalities.geojson"
      via: "reads same path as ingest_osm output (paths.project_dir/raw/municipalities.geojson)"
      pattern: "municipalities.geojson"
---

<objective>
Implement Etapa 2 of the master plan (`hazy-hatching-abelson.md`): the **Baronies Builder**. Convert raw OSM municipality polygons into a configurable number of "baronies" — either 1:1 (each município becomes one barony) or N clusters via scipy KMeans on município centroids — and persist the result as `<project>/raw/baronies.geojson`. Expose a POST endpoint, a frontend slider, and an API client function. Add unit + integration tests.

Purpose: Foundational data layer for the CK3-style architecture. Baronies are the organic permanent unit derived from OSM; downstream phases (research, map generation) will consume `raw/baronies.geojson`.

Output:
- New service module `baronies_builder.py`
- New endpoint `POST /api/projects/{id}/baronies?count=...`
- New frontend slider component + API client function
- 10 new tests (5 unit + 5 endpoint)
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md
@C:\Users\veio_\.claude\plans\hazy-hatching-abelson.md

# Reuse references
@backend/medieval_forge/services/ingest_osm.py
@backend/medieval_forge/services/country_boundaries.py
@backend/medieval_forge/api/ingest.py
@backend/medieval_forge/services/paths.py

<interfaces>
<!-- Path convention (from ingest.py:72): -->
<!-- raw municipalities path = project_dir(project_id) / "raw" / "municipalities.geojson" -->
<!-- The new baronies.geojson MUST live at project_dir(project_id) / "raw" / "baronies.geojson" -->

<!-- From paths.py: -->
def is_valid_uuid(project_id: str) -> bool
def project_dir(project_id: str) -> Path

<!-- Existing endpoint pattern (ingest.py:98): -->
<!-- - validates UUID -> 400 -->
<!-- - loads Project from db -> 404 if missing -->
<!-- - rejects status == "generating" -> 409 -->

<!-- Município feature shape (from ingest_osm.py:_relation_to_geojson_feature): -->
<!-- { -->
<!--   type: "Feature", -->
<!--   properties: { osm_id: int, name: str, admin_level: str }, -->
<!--   geometry: Polygon | MultiPolygon -->
<!-- } -->

<!-- Output barony feature shape (NEW — defined by this plan): -->
<!-- { -->
<!--   type: "Feature", -->
<!--   properties: { -->
<!--     id: str,                       # "B_{osm_id}" if 1:1, "B_C{cluster_idx:04d}" if clustered -->
<!--     name: str,                     # município name when 1:1, "Barony {idx}" when clustered (or member-derived) -->
<!--     centroid: [lon: float, lat: float], -->
<!--     municipality_ids: list[int]    # OSM ids of member municipalities -->
<!--   }, -->
<!--   geometry: Polygon | MultiPolygon  # shapely.ops.unary_union of member municipality geometries -->
<!-- } -->
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: baronies_builder service + unit tests</name>
  <files>
    backend/medieval_forge/services/baronies_builder.py,
    backend/tests/services/test_baronies_builder.py
  </files>
  <behavior>
    Tests in test_baronies_builder.py (write FIRST, deterministic, no network):

    Fixture: build a small in-memory FeatureCollection with N municipalities (use 6 simple square Polygons placed at known lon/lat so centroids are predictable). Write to a tmp_path file as GeoJSON; pass the Path to the builder.

    - test_baronies_1_to_1_when_granularity_is_all:
        result = build_baronies_from_osm(path, "all")
        assert len(result["features"]) == 6
        assert every feature has properties.id == f"B_{osm_id}"
        assert every feature.properties.municipality_ids == [its single osm_id]
        assert geometry is the original município polygon (equal area)

    - test_baronies_clustered_kdtree_when_target_count_specified:
        result = build_baronies_from_osm(path, 3)  # cluster 6 → 3
        assert len(result["features"]) == 3
        assert sum(len(f["properties"]["municipality_ids"]) for f in result["features"]) == 6
        # Use a fixed numpy seed inside the builder (np.random.seed via kmeans2 seed param) so this is deterministic.

    - test_baronies_preserve_municipality_ids_per_cluster:
        result = build_baronies_from_osm(path, 3)
        all_ids = sorted(mid for f in result["features"] for mid in f["properties"]["municipality_ids"])
        assert all_ids == sorted([all 6 osm_ids in fixture])  # no loss, no duplication

    - test_baronies_centroid_is_average_of_member_municipalities:
        # Build 2 baronies from 4 municipalities at known coords; assert each centroid
        # equals the mean of its members' centroids within 1e-6.

    - test_baronies_polygon_is_union_of_member_municipality_polygons:
        # Build 1 barony from 2 adjacent square polygons sharing an edge.
        # Assert resulting geometry.area == sum of inputs' areas (within 1e-9)
        # Assert geometry.geom_type in ("Polygon", "MultiPolygon")
  </behavior>
  <action>
    1. Create `backend/medieval_forge/services/baronies_builder.py` with the function:

       ```python
       """Etapa 2: Baronies Builder — converts OSM município polygons into baronies.

       Two modes:
       - target_count == "all": 1 município = 1 barony (id = B_{osm_id})
       - target_count == int (e.g. 50, 250, 1000): scipy KMeans on município centroids;
         each município assigned to nearest cluster; output polygon is unary_union of members.
       """
       from __future__ import annotations

       import json
       from pathlib import Path
       from typing import Any

       import numpy as np
       from scipy.cluster.vq import kmeans2
       from shapely.geometry import mapping, shape
       from shapely.ops import unary_union


       def _feature_centroid(feat: dict[str, Any]) -> tuple[float, float]:
           geom = shape(feat["geometry"])
           c = geom.representative_point()  # robust against weird MultiPolygons
           return (float(c.x), float(c.y))


       def build_baronies_from_osm(
           municipalities_geojson_path: Path,
           target_count: int | str,
       ) -> dict[str, Any]:
           """Return GeoJSON FeatureCollection of baronies built from município polygons.

           Args:
               municipalities_geojson_path: Path to raw/municipalities.geojson
                   (output of ingest_osm.fetch_municipalities).
               target_count: "all" or positive int. "all" → 1:1 mode.

           Raises:
               FileNotFoundError: if path does not exist.
               ValueError: if target_count invalid or input has no Polygon/MultiPolygon features.
           """
           if not municipalities_geojson_path.exists():
               raise FileNotFoundError(f"municipalities geojson not found: {municipalities_geojson_path}")

           data = json.loads(municipalities_geojson_path.read_text(encoding="utf-8"))
           feats = [
               f for f in data.get("features", [])
               if f.get("geometry", {}).get("type") in ("Polygon", "MultiPolygon")
           ]
           if not feats:
               raise ValueError("no Polygon/MultiPolygon features in input geojson")

           # Validate target_count
           if isinstance(target_count, str):
               if target_count != "all":
                   raise ValueError(f"target_count str must be 'all', got {target_count!r}")
               return _build_one_to_one(feats)

           if not isinstance(target_count, int) or target_count < 1:
               raise ValueError(f"target_count must be 'all' or positive int, got {target_count!r}")

           if target_count >= len(feats):
               # Asking for more clusters than municípios → just do 1:1.
               return _build_one_to_one(feats)

           return _build_clustered(feats, target_count)


       def _build_one_to_one(feats: list[dict[str, Any]]) -> dict[str, Any]:
           out: list[dict[str, Any]] = []
           for f in feats:
               osm_id = f["properties"].get("osm_id")
               name = f["properties"].get("name", "") or f"Barony {osm_id}"
               lon, lat = _feature_centroid(f)
               out.append({
                   "type": "Feature",
                   "properties": {
                       "id": f"B_{osm_id}",
                       "name": name,
                       "centroid": [lon, lat],
                       "municipality_ids": [osm_id],
                   },
                   "geometry": f["geometry"],
               })
           return {"type": "FeatureCollection", "features": out}


       def _build_clustered(feats: list[dict[str, Any]], k: int) -> dict[str, Any]:
           centroids = np.array([_feature_centroid(f) for f in feats], dtype=float)
           # Deterministic seed for reproducible tests. kmeans2 uses np.random under the hood;
           # passing seed via numpy default RNG to be safe across scipy versions.
           rng = np.random.default_rng(seed=42)
           # kmeans2 minit='++' = k-means++ init; deterministic given the seed
           # (scipy.cluster.vq.kmeans2 accepts seed param in 1.11+; fallback: set np.random.seed(42))
           np.random.seed(42)
           cluster_centers, labels = kmeans2(centroids, k, minit="++", seed=42)

           # Group features by cluster label
           groups: dict[int, list[dict[str, Any]]] = {}
           for feat, label in zip(feats, labels):
               groups.setdefault(int(label), []).append(feat)

           out: list[dict[str, Any]] = []
           for cluster_idx in sorted(groups.keys()):
               members = groups[cluster_idx]
               muni_ids = [m["properties"].get("osm_id") for m in members]
               # Centroid = mean of member centroids
               member_centroids = np.array([_feature_centroid(m) for m in members])
               c_lon = float(member_centroids[:, 0].mean())
               c_lat = float(member_centroids[:, 1].mean())
               # Geometry = unary_union of member polygons
               geoms = [shape(m["geometry"]) for m in members]
               merged = unary_union(geoms)
               out.append({
                   "type": "Feature",
                   "properties": {
                       "id": f"B_C{cluster_idx:04d}",
                       "name": f"Barony {cluster_idx + 1}",
                       "centroid": [c_lon, c_lat],
                       "municipality_ids": muni_ids,
                   },
                   "geometry": mapping(merged),
               })
           return {"type": "FeatureCollection", "features": out}
       ```

    2. Create `backend/tests/services/test_baronies_builder.py` per the <behavior> spec.
       Use `tmp_path` pytest fixture. Build fixture geojson with shapely Polygons (squares of size 1deg
       at lon offsets 0,2,4,6,8,10 lat=40 so centroids are well-separated and clustering is deterministic).
       Use osm_ids 101..106. Write to tmp_path / "municipalities.geojson" via json.dumps + mapping().

    3. Run tests: `python -m pytest backend/tests/services/test_baronies_builder.py -v`
       All 5 must pass.
  </action>
  <verify>
    <automated>cd backend && python -m pytest tests/services/test_baronies_builder.py -v</automated>
  </verify>
  <done>
    - baronies_builder.py exists with build_baronies_from_osm
    - All 5 unit tests pass deterministically (no flaky clustering due to fixed seed)
    - 1:1 mode preserves osm_id in feature id (B_{osm_id}) and uses original geometry
    - Clustered mode produces exactly N features and preserves all municipality_ids
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: POST /baronies endpoint + endpoint tests</name>
  <files>
    backend/medieval_forge/api/ingest.py,
    backend/tests/api/test_baronies_endpoint.py
  </files>
  <behavior>
    Tests in test_baronies_endpoint.py (write FIRST):

    Use the existing test pattern: TestClient + temp project dir + seed a project row.
    Look at backend/tests/api/test_research_manual.py or test_generate_validation.py for the canonical
    fixture pattern (project_id, project_dir, seeded Project row in test DB).

    For each test, pre-populate `project_dir/raw/municipalities.geojson` with the same fixture as Task 1
    (or simpler: 6 squares).

    - test_post_baronies_with_all_returns_n_features:
        response = client.post(f"/api/projects/{pid}/baronies?count=all")
        assert response.status_code == 200
        body = response.json()
        assert body["baronies_count"] == 6
        assert body["municipalities_count"] == 6

    - test_post_baronies_with_count_returns_n_clusters:
        response = client.post(f"/api/projects/{pid}/baronies?count=3")
        assert response.status_code == 200
        assert response.json()["baronies_count"] == 3

    - test_post_baronies_404_when_no_municipalities:
        # project exists but raw/municipalities.geojson does NOT
        response = client.post(f"/api/projects/{pid}/baronies?count=all")
        assert response.status_code == 404
        assert "municipalities" in response.json()["detail"].lower()

    - test_post_baronies_422_when_invalid_count:
        # count=foo (not 'all' and not an int) → FastAPI/Pydantic 422
        response = client.post(f"/api/projects/{pid}/baronies?count=foo")
        assert response.status_code == 422

    - test_post_baronies_writes_raw_baronies_geojson:
        client.post(f"/api/projects/{pid}/baronies?count=all")
        baronies_path = project_dir(pid) / "raw" / "baronies.geojson"
        assert baronies_path.exists()
        data = json.loads(baronies_path.read_text(encoding="utf-8"))
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 6
  </behavior>
  <action>
    1. Add to `backend/medieval_forge/api/ingest.py` (do NOT modify the existing `/ingest` endpoint):

       ```python
       from fastapi import Body  # if not already imported
       from ..services.baronies_builder import build_baronies_from_osm
       import asyncio

       def _parse_count(raw: str) -> int | str:
           """Validate and parse the ?count= query param.

           Accepts: 'all' (case-insensitive) or a positive integer string.
           Raises HTTPException 422 on invalid input.
           """
           if raw is None:
               raise HTTPException(status_code=422, detail="count query param is required")
           lowered = raw.strip().lower()
           if lowered == "all":
               return "all"
           try:
               n = int(lowered)
           except ValueError:
               raise HTTPException(
                   status_code=422,
                   detail=f"count must be 'all' or positive integer, got {raw!r}",
               )
           if n < 1:
               raise HTTPException(status_code=422, detail="count must be >= 1")
           return n


       @router.post("/{project_id}/baronies")
       async def build_baronies(
           project_id: str,
           count: str = Query(..., description="'all' or positive integer (e.g. 50, 250, 1000)"),
           db: AsyncSession = Depends(get_db),
       ) -> dict:
           """Etapa 2: build baronies from raw/municipalities.geojson.

           - count='all' → 1 município = 1 barony
           - count=N (int) → KMeans cluster municípios into N baronies
           Writes <project>/raw/baronies.geojson and returns metadata.
           """
           if not is_valid_uuid(project_id):
               raise HTTPException(status_code=400, detail="project_id must be a valid UUID")
           project = await db.get(Project, project_id)
           if project is None:
               raise HTTPException(status_code=404, detail="project not found")

           target_count = _parse_count(count)

           muni_path = project_dir(project_id) / "raw" / "municipalities.geojson"
           if not muni_path.exists():
               raise HTTPException(
                   status_code=404,
                   detail="raw/municipalities.geojson not found — run /ingest first",
               )

           # Run sync builder in thread pool (scipy/shapely are CPU-bound, blocking).
           result = await asyncio.to_thread(build_baronies_from_osm, muni_path, target_count)

           baronies_path = muni_path.parent / "baronies.geojson"
           baronies_path.write_text(
               json.dumps(result, ensure_ascii=False),
               encoding="utf-8",
           )

           # Count municipalities for metadata response
           muni_data = json.loads(muni_path.read_text(encoding="utf-8"))
           muni_count = sum(
               1 for f in muni_data.get("features", [])
               if f.get("geometry", {}).get("type") in ("Polygon", "MultiPolygon")
           )

           return {
               "baronies_count": len(result["features"]),
               "municipalities_count": muni_count,
           }
       ```

    2. Create `backend/tests/api/test_baronies_endpoint.py` per <behavior>.
       Mirror fixture style from `backend/tests/api/test_research_manual.py` for client + seeded project.
       For the 422 test: since `count: str = Query(...)` accepts any string, the 422 comes from
       our `_parse_count` raising HTTPException 422 — verify status_code accordingly.
       Note: if the existing test fixtures use a different status convention for our raise, adjust to match.

    3. Run: `python -m pytest backend/tests/api/test_baronies_endpoint.py -v`

    4. Frontend pieces (small):

       4a. Add to `frontend/src/api/client.ts`:
       ```ts
       export async function buildBaronies(
         projectId: string,
         count: number | "all"
       ): Promise<{ baronies_count: number; municipalities_count: number }> {
         const params = new URLSearchParams({ count: String(count) });
         const res = await fetch(`/api/projects/${projectId}/baronies?${params}`, {
           method: "POST",
         });
         if (!res.ok) {
           const err = await res.json().catch(() => ({ detail: res.statusText }));
           throw new Error(err.detail || `buildBaronies failed: ${res.status}`);
         }
         return res.json();
       }
       ```

       4b. Create `frontend/src/components/ingest/BaronyGranularitySlider.tsx`:
       ```tsx
       import { useState } from "react";

       export type BaronyCount = 50 | 250 | 1000 | "all";

       const PRESETS: { value: BaronyCount; label: string }[] = [
         { value: 50, label: "50" },
         { value: 250, label: "250" },
         { value: 1000, label: "1000" },
         { value: "all", label: "Todos" },
       ];

       interface Props {
         value?: BaronyCount;
         onChange: (count: BaronyCount) => void;
       }

       export function BaronyGranularitySlider({ value = 250, onChange }: Props) {
         const [selected, setSelected] = useState<BaronyCount>(value);
         const handleClick = (v: BaronyCount) => {
           setSelected(v);
           onChange(v);
         };
         return (
           <div className="flex flex-col gap-2">
             <label className="text-sm font-medium">Granularidade de baronies</label>
             <div className="flex gap-2">
               {PRESETS.map((p) => (
                 <button
                   key={String(p.value)}
                   type="button"
                   onClick={() => handleClick(p.value)}
                   className={
                     "px-3 py-1 rounded border text-sm " +
                     (selected === p.value
                       ? "bg-blue-600 text-white border-blue-600"
                       : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50")
                   }
                 >
                   {p.label}
                 </button>
               ))}
             </div>
             <p className="text-xs text-gray-500">
               Selecionado: <strong>{selected === "all" ? "Todos os municípios" : selected}</strong>
             </p>
           </div>
         );
       }
       ```

    5. Run frontend typecheck: `cd frontend && npx tsc --noEmit` — should pass.
  </action>
  <verify>
    <automated>cd backend && python -m pytest tests/api/test_baronies_endpoint.py tests/services/test_baronies_builder.py -v</automated>
  </verify>
  <done>
    - POST /api/projects/{id}/baronies?count=all|N exists in api/ingest.py
    - Existing /ingest endpoint unchanged (no breakage)
    - All 5 endpoint tests + all 5 builder tests pass (10 new tests)
    - Frontend client.ts exports buildBaronies
    - BaronyGranularitySlider.tsx renders 4 preset buttons (50/250/1000/Todos) and fires onChange
    - Frontend typecheck passes (no new TS errors)
  </done>
</task>

</tasks>

<verification>
Run from project root:

```bash
# Backend tests (10 new + existing must still pass)
cd backend && python -m pytest tests/services/test_baronies_builder.py tests/api/test_baronies_endpoint.py -v
# Confirm no regression in pre-existing ingest tests
cd backend && python -m pytest tests/api/ tests/services/ -q -m "not slow"
# Frontend typecheck
cd frontend && npx tsc --noEmit
```

Manual smoke (optional, after backend running):
```bash
# Assuming a project pid with raw/municipalities.geojson already ingested:
curl -X POST "http://localhost:8000/api/projects/$pid/baronies?count=all"
# → {"baronies_count": N, "municipalities_count": N}
ls .data/projects/$pid/raw/baronies.geojson
```
</verification>

<success_criteria>
- `backend/medieval_forge/services/baronies_builder.py` implements `build_baronies_from_osm` with both 'all' and int modes
- `POST /api/projects/{id}/baronies` endpoint exists in `api/ingest.py`, returns `{baronies_count, municipalities_count}` on success
- Endpoint returns 404 when raw/municipalities.geojson missing, 422 on invalid count, 200 on success
- `<project>/raw/baronies.geojson` is written with valid FeatureCollection (each feature has id, name, centroid, municipality_ids properties + Polygon/MultiPolygon geometry)
- `frontend/src/api/client.ts` exports `buildBaronies`
- `frontend/src/components/ingest/BaronyGranularitySlider.tsx` exposes 50/250/1000/"Todos" presets
- 10 new tests pass deterministically (KMeans seeded with `seed=42` + `np.random.seed(42)`)
- No modification to existing `/ingest` endpoint, `map_generator.py`, or `research_runner.py`
- Frontend `tsc --noEmit` clean
</success_criteria>

<output>
After completion, create `.planning/quick/260428-elq-etapa-2-baronies-builder-endpoint-baroni/260428-elq-SUMMARY.md`
</output>
