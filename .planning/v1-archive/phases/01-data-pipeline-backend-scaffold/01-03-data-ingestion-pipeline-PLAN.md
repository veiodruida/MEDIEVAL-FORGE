---
phase: 01
plan: 03
type: execute
wave: 3
depends_on:
  - 01-02
files_modified:
  - backend/medieval_forge/services/ingest_wikidata.py
  - backend/medieval_forge/services/ingest_osm.py
  - backend/medieval_forge/services/ingest_runner.py
  - backend/medieval_forge/api/ingest.py
  - backend/medieval_forge/main.py
  - backend/tests/test_ingest.py
  - frontend/src/api/client.ts
  - frontend/src/pages/ProjectDetail.tsx
autonomous: true
requirements:
  - INGEST-01
  - INGEST-02
  - INGEST-03
  - INGEST-04

must_haves:
  truths:
    - "ingest_wikidata.fetch_municipalities(country_qid, queue) paginates SPARQL with LIMIT 500/OFFSET (RESEARCH Pitfall 5: 60s timeout per page; loop terminates when fewer than page_size results returned)"
    - "ingest_osm.fetch_municipalities(country_iso, queue) calls Overpass with admin_level=8; ISO code validated as `^[A-Z]{2}$` before the request (T-SSRF mitigation)"
    - "Wikidata QID is validated as `^Q\\d+$` BEFORE composing the SPARQL query (T-SSRF mitigation)"
    - "Endpoint URLs (https://query.wikidata.org/sparql, https://overpass-api.de/api/interpreter) are HARDCODED CONSTANTS — never assembled from user input (T-SSRF mitigation)"
    - "Ingestion writes raw GeoJSON FeatureCollection to {project_dir}/raw/municipalities.geojson (INGEST-03)"
    - "Ingestion updates project.status to 'ingested' on success"
    - "POST /api/projects/{id}/ingest?source=wikidata returns StreamingResponse(media_type='text/event-stream') that emits messages from an asyncio.Queue while the producer task runs (INGEST-04)"
    - "Frontend ProjectDetail's Ingest button is wired: clicking it streams SSE messages into the #ingest-log <pre> element (D-09 — append text per event, no progress bar)"
  artifacts:
    - path: "backend/medieval_forge/services/ingest_wikidata.py"
      provides: "async paginated SPARQL ingestion + per-feature transform to GeoJSON"
      exports: ["fetch_municipalities", "WIKIDATA_ENDPOINT", "validate_qid"]
    - path: "backend/medieval_forge/services/ingest_osm.py"
      provides: "async Overpass ingestion + GeoJSON conversion"
      exports: ["fetch_municipalities", "OVERPASS_ENDPOINT", "validate_iso_country"]
    - path: "backend/medieval_forge/services/ingest_runner.py"
      provides: "orchestration glue — runs producer, writes file, updates project.status"
      exports: ["run_ingest"]
    - path: "backend/medieval_forge/api/ingest.py"
      provides: "POST /projects/{id}/ingest SSE endpoint"
      exports: ["router"]
  key_links:
    - from: "backend/medieval_forge/api/ingest.py"
      to: "backend/medieval_forge/services/paths.py"
      via: "is_valid_uuid + ensure_project_dirs"
      pattern: "is_valid_uuid|ensure_project_dirs"
    - from: "backend/medieval_forge/api/ingest.py"
      to: "backend/medieval_forge/services/ingest_wikidata.py"
      via: "asyncio.create_task(producer(queue))"
      pattern: "create_task.*ingest"
    - from: "frontend/src/pages/ProjectDetail.tsx"
      to: "/api/projects/{id}/ingest"
      via: "EventSource"
      pattern: "new EventSource"
    - from: "backend/medieval_forge/main.py"
      to: "backend/medieval_forge/api/ingest.py"
      via: "app.include_router(ingest_router, prefix=\"/api\")"
      pattern: "ingest_router"
---

<objective>
Wire the data ingestion pipeline: a single SSE endpoint that, given a project_id and source (`wikidata` | `osm`), streams real-time progress messages to the browser while paginated fetching of administrative-area polygons happens in the background, then writes the consolidated GeoJSON FeatureCollection to `{project_dir}/raw/municipalities.geojson` and flips `project.status` to `"ingested"`. Frontend wires the existing placeholder Ingest button to consume the stream and append every event message into the existing `#ingest-log` panel (D-09).

Purpose: INGEST-01..04 produce the raw geographic data that Plan 04's map generator wrapper consumes. The SSE pattern (RESEARCH Pattern 3) is the only safe way to give Game Designers visibility while a 60-90 second paginated SPARQL fetch runs (Spain has ~8000 municipalities, requires 16+ pages). Per CONTEXT D-09, no percentage bar — just live text events; this matches the SSE producer/consumer model perfectly.

Output: 4 new backend files (ingest_wikidata.py, ingest_osm.py, ingest_runner.py, api/ingest.py), 1 backend file edit (main.py wires router), 2 frontend files edited (api/client.ts adds SSE helper, ProjectDetail.tsx wires Ingest button), 1 test file (test_ingest.py with 4 PROJ-tested behaviors plus T-SSRF guard tests).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md
@.planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md
@.planning/phases/01-data-pipeline-backend-scaffold/01-VALIDATION.md
@.planning/phases/01-data-pipeline-backend-scaffold/01-02-sqlite-schema-project-crud.md
@CLAUDE.md
@backend/medieval_forge/main.py
@backend/medieval_forge/services/paths.py
@backend/medieval_forge/api/projects.py
@frontend/src/pages/ProjectDetail.tsx
@frontend/src/api/client.ts

<interfaces>
<!-- Contracts THIS plan defines and downstream plans (04, 05) consume -->

backend/medieval_forge/services/ingest_wikidata.py:
```python
import asyncio, re

WIKIDATA_ENDPOINT: str = "https://query.wikidata.org/sparql"     # constant — no SSRF
USER_AGENT: str = "MedievalForge/0.1 (https://github.com/user/medieval-forge)"
QID_RE: re.Pattern  # ^Q\d+$

def validate_qid(value: str) -> str:    # raises ValueError if not ^Q\d+$
    ...

async def fetch_municipalities(
    country_qid: str,
    queue: asyncio.Queue[str | None],
    page_size: int = 500,
    *,
    client_factory=None,    # injectable for tests (httpx.AsyncClient by default)
) -> dict:
    """Returns GeoJSON FeatureCollection: {"type":"FeatureCollection","features":[...]}."""
```

backend/medieval_forge/services/ingest_osm.py:
```python
OVERPASS_ENDPOINT: str = "https://overpass-api.de/api/interpreter"   # constant — no SSRF
ISO_RE: re.Pattern  # ^[A-Z]{2}$

def validate_iso_country(value: str) -> str: ...

async def fetch_municipalities(
    country_iso: str,
    queue: asyncio.Queue[str | None],
    *,
    client_factory=None,
) -> dict:                                # GeoJSON FeatureCollection
    ...
```

backend/medieval_forge/services/ingest_runner.py:
```python
async def run_ingest(
    project_id: str,
    source: str,           # "wikidata" | "osm"
    country: str,          # QID for wikidata, ISO for osm
    queue: asyncio.Queue[str | None],
    db_session_factory,    # AsyncSessionLocal by default; injectable for tests
) -> None:
    """Producer: calls the appropriate fetch_*, writes raw/municipalities.geojson,
    updates project.status='ingested' or 'error', then puts None sentinel into queue."""
```

backend/medieval_forge/api/ingest.py:
```python
router = APIRouter(prefix="/projects", tags=["ingest"])

@router.post("/{project_id}/ingest")
async def trigger_ingest(
    project_id: str,
    source: str = Query("wikidata", regex="^(wikidata|osm)$"),
    country: str | None = Query(None, description="Override project.country_qid for OSM ISO code"),
) -> StreamingResponse:    # text/event-stream
    """Validates project_id, looks up project.country_qid, kicks off run_ingest,
    streams queue messages as SSE."""
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Wave 0 — test_ingest.py stubs (INGEST-01..04 + T-SSRF) registering 7 test names</name>
  <files>backend/tests/test_ingest.py</files>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-VALIDATION.md
    - backend/tests/conftest.py
  </read_first>
  <action>
    Create `backend/tests/test_ingest.py` with passing skip-stubs:
    ```python
    """Tests for INGEST-01..04 and T-SSRF guards.

    Stubs in Wave 0 of Plan 01-03; implemented in Tasks 2, 3, 4.
    """
    import pytest


    @pytest.mark.skip(reason="Implemented by Plan 01-03 Task 2")
    async def test_wikidata_pagination():
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-03 Task 2")
    def test_validate_qid_rejects_non_qid_strings():
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-03 Task 2")
    async def test_osm_fallback():
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-03 Task 2")
    def test_validate_iso_country_rejects_bad_format():
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-03 Task 3")
    async def test_geojson_written(client, tmp_path):
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-03 Task 4")
    async def test_sse_stream(client):
        pass


    @pytest.mark.skip(reason="Implemented by Plan 01-03 Task 4")
    async def test_sse_stream_invalid_uuid_returns_400(client):
        pass
    ```
  </action>
  <verify>
    <automated>py -m pytest backend/tests/test_ingest.py -q</automated>
  </verify>
  <done>7 tests collected, all skipped, 0 errors.</done>
  <acceptance_criteria>
    - backend/tests/test_ingest.py exists
    - Contains exactly 7 test functions (test_wikidata_pagination, test_validate_qid_rejects_non_qid_strings, test_osm_fallback, test_validate_iso_country_rejects_bad_format, test_geojson_written, test_sse_stream, test_sse_stream_invalid_uuid_returns_400)
    - py -m pytest backend/tests/test_ingest.py -q exits 0 with "7 skipped" in output
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: ingest_wikidata.py + ingest_osm.py — pure async fetchers with T-SSRF validators + tests</name>
  <files>
    backend/medieval_forge/services/ingest_wikidata.py,
    backend/medieval_forge/services/ingest_osm.py,
    backend/tests/test_ingest.py
  </files>
  <behavior>
    - Wikidata fetcher: paginates with LIMIT 500/OFFSET; emits queue messages "Fetching page offset=N (got M items, total=K)..." per page; terminates when a page returns < page_size items; returns GeoJSON FeatureCollection where each feature has `properties.qid`, `properties.label`, and `geometry.type=="Point"` with `[lon, lat]` from the SPARQL response
    - OSM fetcher: single Overpass POST with admin_level=8; converts the `elements[*]` with `type=="relation"` and `tags.boundary=="administrative"` into GeoJSON Polygon/MultiPolygon features (use a minimal inline converter — do NOT add osm2geojson dep; per RESEARCH Don't Hand-Roll table only HTTP and SSE format are listed, OSM-to-GeoJSON conversion is acceptable inline)
    - Both validators (`validate_qid`, `validate_iso_country`) raise ValueError on bad input — the API layer turns this into HTTP 400
    - Tests use `client_factory` injection (no real network calls): provide a fake AsyncClient class whose `.get()` / `.post()` return a stub Response with `.json()` returning predetermined payloads
  </behavior>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md (Wikidata SPARQL Paginated query example, lines ~558-605; OSM Overpass query example, lines ~610-635; Pitfall 5 — 60s timeout; Security Domain — T-SSRF)
    - .planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md (specifics — Wikidata QIDs)
    - backend/tests/test_ingest.py
  </read_first>
  <action>
    1. CREATE `backend/medieval_forge/services/ingest_wikidata.py`:
       ```python
       """INGEST-01: Wikidata SPARQL paginated municipality fetcher.

       T-SSRF mitigation: validate_qid enforces ^Q\\d+$ before composing the query;
       endpoint URL is a hardcoded constant — never assembled from user input.
       """
       from __future__ import annotations

       import asyncio
       import re
       from typing import Any, Callable

       import httpx

       WIKIDATA_ENDPOINT: str = "https://query.wikidata.org/sparql"
       USER_AGENT: str = (
           "MedievalForge/0.1 (https://github.com/user/medieval-forge; "
           "local map authoring tool)"
       )
       QID_RE: re.Pattern[str] = re.compile(r"^Q\d+$")

       _PAGE_TIMEOUT_S: float = 70.0  # Wikidata hard limit is 60s; client timeout ~70s


       def validate_qid(value: str) -> str:
           """Raise ValueError if `value` is not a Wikidata QID (`Q` followed by digits)."""
           if not isinstance(value, str) or not QID_RE.match(value):
               raise ValueError(f"invalid Wikidata QID: {value!r} (expected pattern ^Q\\d+$)")
           return value


       def _build_query(country_qid: str, limit: int, offset: int) -> str:
           # Note: country_qid is interpolated only AFTER validate_qid has run.
           return f"""
           SELECT ?item ?itemLabel ?lat ?lon WHERE {{
             ?item wdt:P31/wdt:P279* wd:Q15284 .
             ?item wdt:P17 wd:{country_qid} .
             ?item wdt:P625 ?coords .
             BIND(geof:latitude(?coords) AS ?lat)
             BIND(geof:longitude(?coords) AS ?lon)
             SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
           }}
           LIMIT {limit}
           OFFSET {offset}
           """


       def _binding_to_feature(b: dict[str, Any]) -> dict[str, Any]:
           qid_url = b.get("item", {}).get("value", "")
           qid = qid_url.rsplit("/", 1)[-1] if qid_url else ""
           label = b.get("itemLabel", {}).get("value", "")
           lat = float(b.get("lat", {}).get("value", "nan"))
           lon = float(b.get("lon", {}).get("value", "nan"))
           return {
               "type": "Feature",
               "properties": {"qid": qid, "label": label},
               "geometry": {"type": "Point", "coordinates": [lon, lat]},
           }


       async def fetch_municipalities(
           country_qid: str,
           queue: asyncio.Queue[str | None],
           page_size: int = 500,
           *,
           client_factory: Callable[[], httpx.AsyncClient] | None = None,
       ) -> dict[str, Any]:
           """Paginate SPARQL; return GeoJSON FeatureCollection.

           T-SSRF: country_qid validated before query composition.
           """
           validate_qid(country_qid)
           if page_size < 1 or page_size > 1000:
               raise ValueError("page_size must be between 1 and 1000")

           features: list[dict[str, Any]] = []
           offset = 0

           def _factory() -> httpx.AsyncClient:
               if client_factory is not None:
                   return client_factory()
               return httpx.AsyncClient(timeout=_PAGE_TIMEOUT_S)

           async with _factory() as client:
               while True:
                   await queue.put(
                       f"data: Fetching Wikidata page offset={offset} "
                       f"(running total={len(features)})...\n\n"
                   )
                   query = _build_query(country_qid, page_size, offset)
                   resp = await client.get(
                       WIKIDATA_ENDPOINT,
                       params={"query": query, "format": "json"},
                       headers={
                           "User-Agent": USER_AGENT,
                           "Accept": "application/sparql-results+json",
                       },
                   )
                   resp.raise_for_status()
                   bindings = resp.json().get("results", {}).get("bindings", [])
                   features.extend(_binding_to_feature(b) for b in bindings)
                   if len(bindings) < page_size:
                       break
                   offset += page_size

           await queue.put(
               f"data: Wikidata fetch complete: {len(features)} features.\n\n"
           )
           return {"type": "FeatureCollection", "features": features}
       ```

    2. CREATE `backend/medieval_forge/services/ingest_osm.py`:
       ```python
       """INGEST-02: OSM Overpass municipality fetcher (admin_level=8).

       T-SSRF: validate_iso_country enforces 2-letter uppercase ISO 3166-1 code.
       """
       from __future__ import annotations

       import asyncio
       import re
       from typing import Any, Callable

       import httpx

       OVERPASS_ENDPOINT: str = "https://overpass-api.de/api/interpreter"
       ISO_RE: re.Pattern[str] = re.compile(r"^[A-Z]{2}$")
       _TIMEOUT_S: float = 130.0  # Overpass internal timeout 120s; client 130s


       def validate_iso_country(value: str) -> str:
           if not isinstance(value, str) or not ISO_RE.match(value):
               raise ValueError(
                   f"invalid ISO 3166-1 alpha-2 country code: {value!r} "
                   "(expected pattern ^[A-Z]{2}$)"
               )
           return value


       def _build_query(country_iso: str, admin_level: int = 8) -> str:
           return f"""
           [out:json][timeout:120];
           area["ISO3166-1"="{country_iso}"]->.country;
           (
             relation["admin_level"="{admin_level}"]["boundary"="administrative"](area.country);
           );
           out geom;
           """


       def _relation_to_geojson_feature(rel: dict[str, Any]) -> dict[str, Any] | None:
           """Convert an OSM relation with geometry into a GeoJSON Polygon/MultiPolygon feature.

           Outer/inner classification: each member.role == "outer" forms a ring of
           a polygon; "inner" rings are holes. This is a minimal conversion adequate
           for Phase 1 (Plan 06 / Phase 6 polish may swap in osm2geojson if needed).
           """
           members = rel.get("members", [])
           outers: list[list[list[float]]] = []
           inners: list[list[list[float]]] = []
           for m in members:
               geom = m.get("geometry") or []
               if not geom:
                   continue
               ring = [[pt["lon"], pt["lat"]] for pt in geom if "lon" in pt and "lat" in pt]
               if len(ring) < 3:
                   continue
               # Close ring if not already closed.
               if ring[0] != ring[-1]:
                   ring.append(ring[0])
               role = m.get("role", "")
               if role == "outer":
                   outers.append(ring)
               elif role == "inner":
                   inners.append(ring)
           if not outers:
               return None

           tags = rel.get("tags", {})
           if len(outers) == 1:
               coords = [outers[0]] + inners
               geometry = {"type": "Polygon", "coordinates": coords}
           else:
               # Naive: each outer is its own polygon; ignore inner-to-outer assignment
               # for Phase 1. Phase 6 polish can reassign inners by point-in-polygon.
               geometry = {
                   "type": "MultiPolygon",
                   "coordinates": [[o] for o in outers],
               }
           return {
               "type": "Feature",
               "properties": {
                   "osm_id": rel.get("id"),
                   "name": tags.get("name", ""),
                   "admin_level": tags.get("admin_level", ""),
               },
               "geometry": geometry,
           }


       async def fetch_municipalities(
           country_iso: str,
           queue: asyncio.Queue[str | None],
           *,
           client_factory: Callable[[], httpx.AsyncClient] | None = None,
       ) -> dict[str, Any]:
           validate_iso_country(country_iso)

           def _factory() -> httpx.AsyncClient:
               if client_factory is not None:
                   return client_factory()
               return httpx.AsyncClient(timeout=_TIMEOUT_S)

           query = _build_query(country_iso)
           await queue.put("data: Querying OSM Overpass API (this may take ~2 min)...\n\n")
           async with _factory() as client:
               resp = await client.post(OVERPASS_ENDPOINT, data={"data": query})
               resp.raise_for_status()
               payload = resp.json()

           features: list[dict[str, Any]] = []
           for el in payload.get("elements", []):
               if el.get("type") != "relation":
                   continue
               feat = _relation_to_geojson_feature(el)
               if feat is not None:
                   features.append(feat)
           await queue.put(
               f"data: OSM fetch complete: {len(features)} features.\n\n"
           )
           return {"type": "FeatureCollection", "features": features}
       ```

    3. REPLACE relevant tests in `backend/tests/test_ingest.py` (the Wave 0 stubs) — implement 4 of the 7:
       ```python
       """Tests for INGEST-01..04 and T-SSRF guards."""
       from __future__ import annotations

       import asyncio
       import json
       from typing import Any

       import pytest


       # ---------- T-SSRF: validators reject malformed input ----------

       def test_validate_qid_rejects_non_qid_strings():
           from medieval_forge.services.ingest_wikidata import validate_qid

           validate_qid("Q29")  # ok
           validate_qid("Q1234567")  # ok
           for bad in ["q29", "spain", "29", "Q", "../etc/passwd", "Q29; DROP TABLE"]:
               with pytest.raises(ValueError):
                   validate_qid(bad)


       def test_validate_iso_country_rejects_bad_format():
           from medieval_forge.services.ingest_osm import validate_iso_country

           validate_iso_country("ES")
           validate_iso_country("PT")
           for bad in ["es", "ESP", "E", "12", "../", "ES; DROP"]:
               with pytest.raises(ValueError):
                   validate_iso_country(bad)


       # ---------- INGEST-01: Wikidata pagination ----------

       class _FakeResponse:
           def __init__(self, payload: dict[str, Any]):
               self._payload = payload
               self.status_code = 200

           def raise_for_status(self):
               pass

           def json(self):
               return self._payload


       class _FakeClient:
           """Yields a sequence of fake JSON payloads for successive .get() calls."""

           def __init__(self, payloads: list[dict[str, Any]]):
               self._payloads = list(payloads)
               self.calls: list[dict[str, Any]] = []

           async def __aenter__(self):
               return self

           async def __aexit__(self, *exc):
               return None

           async def get(self, url, params=None, headers=None):
               self.calls.append({"url": url, "params": params, "headers": headers})
               if not self._payloads:
                   return _FakeResponse({"results": {"bindings": []}})
               return _FakeResponse(self._payloads.pop(0))

           async def post(self, url, data=None):
               return _FakeResponse(self._payloads.pop(0) if self._payloads else {})


       def _binding(qid_num: int):
           return {
               "item": {"value": f"http://www.wikidata.org/entity/Q{qid_num}"},
               "itemLabel": {"value": f"Place {qid_num}"},
               "lat": {"value": "40.0"},
               "lon": {"value": "-3.0"},
           }


       async def test_wikidata_pagination():
           from medieval_forge.services.ingest_wikidata import fetch_municipalities

           # Two pages: first 500 items, second 200 items (terminates).
           page1 = {"results": {"bindings": [_binding(i) for i in range(500)]}}
           page2 = {"results": {"bindings": [_binding(500 + i) for i in range(200)]}}
           fake = _FakeClient([page1, page2])
           queue: asyncio.Queue[str | None] = asyncio.Queue()

           result = await fetch_municipalities(
               "Q29", queue, page_size=500, client_factory=lambda: fake
           )

           assert result["type"] == "FeatureCollection"
           assert len(result["features"]) == 700
           # SSE messages: 2 "Fetching page" + 1 "complete" = 3 puts (plus possibly intermediate)
           assert queue.qsize() >= 3
           # Verify pagination params advanced.
           assert len(fake.calls) == 2
           assert "OFFSET 0" in fake.calls[0]["params"]["query"]
           assert "OFFSET 500" in fake.calls[1]["params"]["query"]
           # T-SSRF: query contains ONLY validated QID, never raw user input.
           assert "wd:Q29" in fake.calls[0]["params"]["query"]


       # ---------- INGEST-02: OSM fallback ----------

       async def test_osm_fallback():
           from medieval_forge.services.ingest_osm import fetch_municipalities

           overpass_payload = {
               "elements": [
                   {
                       "type": "relation",
                       "id": 1,
                       "tags": {"name": "Province A", "admin_level": "8", "boundary": "administrative"},
                       "members": [
                           {
                               "role": "outer",
                               "geometry": [
                                   {"lon": 0.0, "lat": 0.0},
                                   {"lon": 1.0, "lat": 0.0},
                                   {"lon": 1.0, "lat": 1.0},
                                   {"lon": 0.0, "lat": 1.0},
                               ],
                           }
                       ],
                   },
                   {
                       "type": "node",  # Should be filtered out
                       "id": 2,
                   },
               ]
           }
           fake = _FakeClient([overpass_payload])
           queue: asyncio.Queue[str | None] = asyncio.Queue()
           result = await fetch_municipalities(
               "ES", queue, client_factory=lambda: fake
           )

           assert result["type"] == "FeatureCollection"
           assert len(result["features"]) == 1
           feat = result["features"][0]
           assert feat["geometry"]["type"] == "Polygon"
           assert feat["properties"]["name"] == "Province A"
           assert feat["geometry"]["coordinates"][0][0] == feat["geometry"]["coordinates"][0][-1]  # closed
       ```

       Leave the other 3 tests (`test_geojson_written`, `test_sse_stream`, `test_sse_stream_invalid_uuid_returns_400`) as `@pytest.mark.skip` — they're implemented in Tasks 3 and 4. Use this approach: keep the 4 implemented tests at the top of the file and the 3 skip-stubs below them.

    Run: `py -m pytest backend/tests/test_ingest.py -x -q`. Expected: 4 passed, 3 skipped.
  </action>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md
    - backend/tests/test_ingest.py
  </read_first>
  <verify>
    <automated>py -m pytest backend/tests/test_ingest.py -x -q</automated>
  </verify>
  <done>4 passed (the 4 fetcher + validator tests), 3 skipped (the runner + endpoint tests).</done>
  <acceptance_criteria>
    - backend/medieval_forge/services/ingest_wikidata.py contains "WIKIDATA_ENDPOINT: str = \"https://query.wikidata.org/sparql\""
    - backend/medieval_forge/services/ingest_wikidata.py contains "validate_qid(country_qid)" or equivalent invocation BEFORE any URL composition (verify by reading; the test enforces that the query contains "wd:Q29" only — so the QID was used)
    - backend/medieval_forge/services/ingest_wikidata.py contains "QID_RE" with pattern "^Q\\d+$"
    - backend/medieval_forge/services/ingest_wikidata.py contains "page_size: int = 500"
    - backend/medieval_forge/services/ingest_osm.py contains "OVERPASS_ENDPOINT: str = \"https://overpass-api.de/api/interpreter\""
    - backend/medieval_forge/services/ingest_osm.py contains "ISO_RE" with pattern "^[A-Z]{2}$"
    - py -m pytest backend/tests/test_ingest.py::test_validate_qid_rejects_non_qid_strings -x exits 0
    - py -m pytest backend/tests/test_ingest.py::test_validate_iso_country_rejects_bad_format -x exits 0
    - py -m pytest backend/tests/test_ingest.py::test_wikidata_pagination -x exits 0
    - py -m pytest backend/tests/test_ingest.py::test_osm_fallback -x exits 0
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 3: ingest_runner.py — orchestrator that writes GeoJSON + updates project.status (INGEST-03) + test</name>
  <files>
    backend/medieval_forge/services/ingest_runner.py,
    backend/tests/test_ingest.py
  </files>
  <behavior>
    - `run_ingest(project_id, source, country, queue, db_session_factory)` calls the appropriate fetch_*, writes the result to `{project_dir}/raw/municipalities.geojson` (atomic: write to `.tmp` then rename), then opens an AsyncSession via the factory to update `project.status = "ingested"`, then puts `None` sentinel into the queue
    - On exception: emits `data: ERROR: {msg}\n\n` and updates status to `"error_ingesting"`, then puts None sentinel (UI can detect end-of-stream regardless of success/failure)
    - File is valid JSON parseable as GeoJSON (test_geojson_written verifies)
  </behavior>
  <read_first>
    - backend/medieval_forge/services/paths.py
    - backend/medieval_forge/services/ingest_wikidata.py (created in Task 2)
    - backend/medieval_forge/services/ingest_osm.py (created in Task 2)
    - backend/medieval_forge/database.py
    - backend/medieval_forge/models.py
    - backend/tests/test_ingest.py
  </read_first>
  <action>
    1. CREATE `backend/medieval_forge/services/ingest_runner.py`:
       ```python
       """Orchestration glue for ingestion: fetch → write GeoJSON → update status."""
       from __future__ import annotations

       import asyncio
       import json
       import logging
       from pathlib import Path
       from typing import Awaitable, Callable

       from sqlalchemy.ext.asyncio import async_sessionmaker

       from ..database import AsyncSessionLocal
       from ..models import Project
       from . import ingest_osm, ingest_wikidata
       from .paths import ensure_project_dirs

       logger = logging.getLogger(__name__)


       async def _set_status(
           project_id: str,
           status: str,
           session_factory: async_sessionmaker,
       ) -> None:
           async with session_factory() as session:
               proj = await session.get(Project, project_id)
               if proj is not None:
                   proj.status = status
                   await session.commit()


       def _write_geojson_atomic(path: Path, payload: dict) -> None:
           tmp = path.with_suffix(path.suffix + ".tmp")
           tmp.write_text(json.dumps(payload), encoding="utf-8")
           tmp.replace(path)


       async def run_ingest(
           project_id: str,
           source: str,
           country: str,
           queue: asyncio.Queue[str | None],
           db_session_factory: async_sessionmaker | None = None,
       ) -> None:
           """Producer task. ALWAYS puts None sentinel before returning."""
           factory = db_session_factory or AsyncSessionLocal
           try:
               await queue.put(
                   f"data: Starting {source} ingest for project {project_id} "
                   f"(country={country})...\n\n"
               )
               dirs = ensure_project_dirs(project_id)
               raw_path = dirs["raw"] / "municipalities.geojson"

               if source == "wikidata":
                   payload = await ingest_wikidata.fetch_municipalities(country, queue)
               elif source == "osm":
                   payload = await ingest_osm.fetch_municipalities(country, queue)
               else:
                   raise ValueError(f"unknown source: {source!r}")

               _write_geojson_atomic(raw_path, payload)
               await queue.put(
                   f"data: Wrote {len(payload['features'])} features to {raw_path.name}.\n\n"
               )
               await _set_status(project_id, "ingested", factory)
               await queue.put("data: DONE\n\n")
           except Exception as exc:  # noqa: BLE001 — runner is top-of-task
               logger.exception("ingest failed")
               await queue.put(f"data: ERROR: {exc}\n\n")
               try:
                   await _set_status(project_id, "error_ingesting", factory)
               except Exception:  # noqa: BLE001
                   logger.exception("failed to update status to error_ingesting")
           finally:
               await queue.put(None)
       ```

    2. REPLACE the `test_geojson_written` skip-stub in `backend/tests/test_ingest.py` with a real test (keep other skip-stubs untouched). Append/edit (the structure of test_ingest.py: 4 implemented at top from Task 2, then this one, then 2 still-skipped):
       ```python
       async def test_geojson_written(client, tmp_path, monkeypatch):
           """run_ingest writes raw/municipalities.geojson and updates project.status."""
           from medieval_forge.services import ingest_runner, ingest_wikidata, paths as paths_mod
           from medieval_forge.database import AsyncSessionLocal

           # Redirect PROJECTS_ROOT.
           fake_root = tmp_path / "projects"
           monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", fake_root)

           # Create a project via the API.
           created = (await client.post("/api/projects", json={
               "name": "ingest-test",
               "country_qid": "Q29",
               "period_start": 800,
               "period_end": 1000,
           })).json()
           pid = created["id"]

           # Stub the wikidata fetcher to avoid network.
           async def fake_fetch(country_qid, queue, page_size=500, *, client_factory=None):
               await queue.put("data: stub fetching...\n\n")
               return {
                   "type": "FeatureCollection",
                   "features": [{
                       "type": "Feature",
                       "properties": {"qid": "Q1", "label": "Stub"},
                       "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
                   }],
               }
           monkeypatch.setattr(ingest_wikidata, "fetch_municipalities", fake_fetch)

           queue = asyncio.Queue()
           # Use the test's session factory so the status update lands in the same in-memory DB.
           # The `client` fixture overrides get_db to share `db_session`; here we need to
           # write directly via that same session. Pull the override target.
           from medieval_forge.main import app
           from medieval_forge.database import get_db
           dep = app.dependency_overrides[get_db]

           class _SharedSessionFactory:
               """Adapter so run_ingest can call factory() and get a context-managed session."""

               def __call__(self):
                   gen = dep()
                   sess = gen.__anext__().__await__()
                   # Awkward but works in pytest-asyncio context — easier path: use AsyncSessionLocal but on same in-memory DB? No. Skip status-update assertion in this isolated test variant; only assert file written.
                   raise NotImplementedError

           # Simpler approach: build a NEW session factory pointed at the SAME engine the conftest uses.
           # Easiest: just use AsyncSessionLocal — the `projects` table won't exist there, so the
           # status update will fail silently (the runner catches Exception and updates to
           # error_ingesting, but BOTH the file write AND the original status update happen
           # in different orders). This tests the file write half.

           import sqlalchemy as sa
           from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
           from medieval_forge.models import Base
           engine = create_async_engine("sqlite+aiosqlite:///:memory:")
           async with engine.begin() as conn:
               await conn.run_sync(Base.metadata.create_all)
           sf = async_sessionmaker(engine, expire_on_commit=False)
           # Insert a project row mirroring the API-created one.
           async with sf() as session:
               session.add(__import__("medieval_forge.models", fromlist=["Project"]).Project(
                   id=pid, name="ingest-test", country_qid="Q29",
                   period_start=800, period_end=1000, status="created",
               ))
               await session.commit()

           await ingest_runner.run_ingest(pid, "wikidata", "Q29", queue, db_session_factory=sf)

           # Verify file written.
           geojson_path = fake_root / pid / "raw" / "municipalities.geojson"
           assert geojson_path.exists()
           data = json.loads(geojson_path.read_text(encoding="utf-8"))
           assert data["type"] == "FeatureCollection"
           assert len(data["features"]) == 1

           # Verify status updated in the dedicated engine.
           async with sf() as session:
               proj = await session.get(__import__("medieval_forge.models", fromlist=["Project"]).Project, pid)
               assert proj.status == "ingested"

           await engine.dispose()
       ```

       Note: this test is intentionally self-contained on its own engine to avoid coupling to the conftest fixture lifecycle for status updates. The point of the test is INGEST-03 (file written) plus the side effect of status update being plumbed through the runner.

    3. Run: `py -m pytest backend/tests/test_ingest.py -x -q`. Expected: 5 passed, 2 skipped.
  </action>
  <read_first>
    - backend/medieval_forge/services/paths.py
    - backend/medieval_forge/services/ingest_wikidata.py
    - backend/medieval_forge/services/ingest_osm.py
    - backend/medieval_forge/database.py
    - backend/medieval_forge/models.py
    - backend/tests/test_ingest.py
  </read_first>
  <verify>
    <automated>py -m pytest backend/tests/test_ingest.py -x -q</automated>
  </verify>
  <done>5 passed (4 from Task 2 + test_geojson_written), 2 skipped.</done>
  <acceptance_criteria>
    - backend/medieval_forge/services/ingest_runner.py contains "ensure_project_dirs(project_id)"
    - backend/medieval_forge/services/ingest_runner.py contains "raw\" / \"municipalities.geojson" OR equivalent path concatenation
    - backend/medieval_forge/services/ingest_runner.py contains "proj.status = \"ingested\""
    - backend/medieval_forge/services/ingest_runner.py contains "await queue.put(None)" inside a finally block
    - backend/medieval_forge/services/ingest_runner.py contains "tmp.replace(path)" (atomic write)
    - py -m pytest backend/tests/test_ingest.py::test_geojson_written -x exits 0
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 4: api/ingest.py SSE endpoint + main.py wires router + 2 endpoint tests (INGEST-04, T-PATH on project_id)</name>
  <files>
    backend/medieval_forge/api/ingest.py,
    backend/medieval_forge/main.py,
    backend/tests/test_ingest.py
  </files>
  <behavior>
    - `POST /api/projects/{project_id}/ingest?source=wikidata` (or `?source=osm`) returns `StreamingResponse` with `media_type="text/event-stream"`, `headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}`
    - `project_id` is validated via `is_valid_uuid` → 400 on bad UUID (T-PATH defence in depth)
    - Looks up the project (404 if missing); if `project.status == "generating"` returns 409 (anti-DoS — RESEARCH Security Domain T-DOS, also relevant to ingest to prevent overlapping fetches)
    - Spawns `asyncio.create_task(run_ingest(...))`; SSE generator drains the queue until None sentinel
    - Source defaults to `"wikidata"`; `country` query param overrides `project.country_qid` (used for OSM ISO codes since project stores QIDs)
  </behavior>
  <read_first>
    - .planning/phases/01-data-pipeline-backend-scaffold/01-RESEARCH.md (Pattern 3 — SSE Progress Stream; Pitfall 8 — mount order; Security Domain — T-DOS)
    - backend/medieval_forge/main.py (current)
    - backend/medieval_forge/api/projects.py (router pattern reference)
    - backend/medieval_forge/services/ingest_runner.py
    - backend/medieval_forge/services/paths.py
    - backend/tests/test_ingest.py
  </read_first>
  <action>
    1. CREATE `backend/medieval_forge/api/ingest.py`:
       ```python
       """INGEST-04: SSE-streamed ingestion endpoint.

       Per RESEARCH Pattern 3 — asyncio.Queue producer + SSE consumer.
       T-PATH: project_id validated via is_valid_uuid before DB lookup.
       T-DOS:  reject if project.status == 'generating' (anti-overlap).
       """
       from __future__ import annotations

       import asyncio
       import logging

       from fastapi import APIRouter, Depends, HTTPException, Query, status
       from fastapi.responses import StreamingResponse
       from sqlalchemy.ext.asyncio import AsyncSession

       from ..database import AsyncSessionLocal, get_db
       from ..models import Project
       from ..services.ingest_runner import run_ingest
       from ..services.paths import is_valid_uuid

       logger = logging.getLogger(__name__)
       router = APIRouter(prefix="/projects", tags=["ingest"])


       async def _sse_generator(
           project_id: str,
           source: str,
           country: str,
           session_factory,
       ):
           queue: asyncio.Queue[str | None] = asyncio.Queue()
           task = asyncio.create_task(
               run_ingest(project_id, source, country, queue, session_factory)
           )
           try:
               while True:
                   msg = await queue.get()
                   if msg is None:
                       break
                   yield msg
           finally:
               # Ensure the producer task is awaited so exceptions propagate to logs.
               if not task.done():
                   task.cancel()
                   try:
                       await task
                   except (asyncio.CancelledError, Exception):  # noqa: BLE001
                       pass


       @router.post("/{project_id}/ingest")
       async def trigger_ingest(
           project_id: str,
           source: str = Query("wikidata", regex="^(wikidata|osm)$"),
           country: str | None = Query(
               None,
               description="Override country code. For wikidata: QID (Q\\d+); for osm: ISO 3166-1 alpha-2.",
           ),
           db: AsyncSession = Depends(get_db),
       ) -> StreamingResponse:
           if not is_valid_uuid(project_id):
               raise HTTPException(
                   status_code=400,
                   detail="project_id must be a valid UUID",
               )
           project = await db.get(Project, project_id)
           if project is None:
               raise HTTPException(status_code=404, detail="project not found")
           if project.status == "generating":
               raise HTTPException(
                   status_code=409,
                   detail="project is currently generating; wait for that to finish",
               )

           effective_country = country or project.country_qid

           return StreamingResponse(
               _sse_generator(project_id, source, effective_country, AsyncSessionLocal),
               media_type="text/event-stream",
               headers={
                   "Cache-Control": "no-cache",
                   "X-Accel-Buffering": "no",
                   "Connection": "keep-alive",
               },
           )
       ```

    2. EDIT `backend/medieval_forge/main.py`. Add the ingest router import and registration AFTER the projects router and BEFORE the SPA catch-all:
       ```python
       from .api.ingest import router as ingest_router

       app.include_router(ingest_router, prefix="/api")
       ```

    3. REPLACE the two skip-stubs in `backend/tests/test_ingest.py` with real implementations (`test_sse_stream` and `test_sse_stream_invalid_uuid_returns_400`):
       ```python
       async def test_sse_stream_invalid_uuid_returns_400(client):
           resp = await client.post("/api/projects/not-a-uuid/ingest?source=wikidata")
           assert resp.status_code == 400


       async def test_sse_stream(client, tmp_path, monkeypatch):
           """Endpoint streams SSE messages from the runner queue end-to-end."""
           from medieval_forge.services import ingest_runner, ingest_wikidata, paths as paths_mod

           # Isolate filesystem.
           fake_root = tmp_path / "projects"
           monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", fake_root)

           # Stub the network fetch.
           async def fake_fetch(country_qid, queue, page_size=500, *, client_factory=None):
               await queue.put("data: stub page 1\n\n")
               await queue.put("data: stub page 2\n\n")
               return {"type": "FeatureCollection", "features": []}
           monkeypatch.setattr(ingest_wikidata, "fetch_municipalities", fake_fetch)

           created = (await client.post("/api/projects", json={
               "name": "sse",
               "country_qid": "Q29",
               "period_start": 800,
               "period_end": 1000,
           })).json()
           pid = created["id"]

           # Stream the SSE response and collect events.
           async with client.stream("POST", f"/api/projects/{pid}/ingest?source=wikidata") as resp:
               assert resp.status_code == 200
               assert resp.headers["content-type"].startswith("text/event-stream")
               body_chunks: list[str] = []
               async for chunk in resp.aiter_text():
                   body_chunks.append(chunk)
           full_body = "".join(body_chunks)
           # Verify expected event substrings (the producer emits Starting, stub page 1/2, Wrote, DONE).
           assert "Starting wikidata ingest" in full_body
           assert "stub page 1" in full_body
           assert "stub page 2" in full_body
           assert "DONE" in full_body
       ```

       Run: `py -m pytest backend/tests/test_ingest.py -x -q`. Expected: 7 passed, 0 skipped.
  </action>
  <read_first>
    - backend/medieval_forge/main.py
    - backend/medieval_forge/api/projects.py
    - backend/medieval_forge/services/ingest_runner.py
    - backend/medieval_forge/services/paths.py
    - backend/tests/test_ingest.py
  </read_first>
  <verify>
    <automated>py -m pytest backend/tests/test_ingest.py -x -q</automated>
  </verify>
  <done>7 passed; main.py registers ingest_router before the SPA catch-all; SSE smoke via test_sse_stream confirms text/event-stream content-type and real event flow.</done>
  <acceptance_criteria>
    - backend/medieval_forge/api/ingest.py contains "router = APIRouter(prefix=\"/projects\""
    - backend/medieval_forge/api/ingest.py contains "media_type=\"text/event-stream\""
    - backend/medieval_forge/api/ingest.py contains "is_valid_uuid(project_id)"
    - backend/medieval_forge/api/ingest.py contains "asyncio.create_task("
    - backend/medieval_forge/api/ingest.py contains "regex=\"^(wikidata|osm)$\"" OR equivalent pattern restriction
    - backend/medieval_forge/api/ingest.py contains "project.status == \"generating\"" (T-DOS)
    - backend/medieval_forge/main.py contains "from .api.ingest import router as ingest_router"
    - backend/medieval_forge/main.py contains "app.include_router(ingest_router, prefix=\"/api\")"
    - py -m pytest backend/tests/test_ingest.py -x -q exits 0 with "7 passed"
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 5: Frontend wires Ingest button — useIngestStream hook + ProjectDetail integration (D-09)</name>
  <files>
    frontend/src/api/client.ts,
    frontend/src/pages/ProjectDetail.tsx
  </files>
  <behavior>
    - New helper `useIngestStream(projectId)` exposes `{start: (source: 'wikidata'|'osm') => void, lines: string[], isStreaming: boolean, error: Error | null}`
    - Implementation uses `fetch()` with `POST` and reads the streaming `Response.body` reader (NOT `EventSource`, because EventSource only supports GET — and our endpoint is POST per RESEARCH Pattern 3). Decodes `text/event-stream` chunks line-by-line, strips the `data: ` prefix, appends to lines state.
    - On stream end, calls `qc.invalidateQueries(['projects', projectId])` so the project status display refreshes (will now show "ingested")
    - ProjectDetail: replaces the disabled "Ingest (Plan 1.3)" button with TWO buttons: "Ingest from Wikidata" and "Ingest from OSM" (both call `start('wikidata')` / `start('osm')`); buttons disabled while `isStreaming`; the existing `<pre id="ingest-log">` element renders `lines.join('')` (the SSE text, which already contains `\n\n` between events)
  </behavior>
  <read_first>
    - frontend/src/api/client.ts (current state from Plan 02)
    - frontend/src/pages/ProjectDetail.tsx (current state from Plan 02; #ingest-log placeholder)
    - .planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md (D-09)
  </read_first>
  <action>
    1. APPEND to `frontend/src/api/client.ts` (do not remove existing exports):
       ```typescript
       import { useCallback, useState } from 'react'

       export interface IngestStreamHandle {
         lines: string[]
         start: (source: 'wikidata' | 'osm') => Promise<void>
         isStreaming: boolean
         error: Error | null
       }

       export function useIngestStream(projectId: string | undefined): IngestStreamHandle {
         const qc = useQueryClient()
         const [lines, setLines] = useState<string[]>([])
         const [isStreaming, setStreaming] = useState(false)
         const [error, setError] = useState<Error | null>(null)

         const start = useCallback(
           async (source: 'wikidata' | 'osm') => {
             if (!projectId) return
             setLines([])
             setError(null)
             setStreaming(true)
             try {
               const res = await fetch(
                 `/api/projects/${projectId}/ingest?source=${source}`,
                 { method: 'POST' },
               )
               if (!res.ok || !res.body) {
                 throw new Error(`HTTP ${res.status}`)
               }
               const reader = res.body.getReader()
               const decoder = new TextDecoder()
               let buf = ''
               while (true) {
                 const { value, done } = await reader.read()
                 if (done) break
                 buf += decoder.decode(value, { stream: true })
                 // SSE events are separated by blank lines (\n\n).
                 let idx
                 while ((idx = buf.indexOf('\n\n')) !== -1) {
                   const eventBlock = buf.slice(0, idx)
                   buf = buf.slice(idx + 2)
                   // Strip the "data: " prefix from each line in the block.
                   const text = eventBlock
                     .split('\n')
                     .map((l) => (l.startsWith('data: ') ? l.slice(6) : l))
                     .join('\n')
                   setLines((prev) => [...prev, text + '\n'])
                 }
               }
             } catch (e) {
               setError(e as Error)
             } finally {
               setStreaming(false)
               qc.invalidateQueries({ queryKey: ['projects', projectId] })
               qc.invalidateQueries({ queryKey: ['projects'] })
             }
           },
           [projectId, qc],
         )

         return { lines, start, isStreaming, error }
       }
       ```

    2. EDIT `frontend/src/pages/ProjectDetail.tsx`. Locate the "Pipeline actions" Card and the disabled "Ingest (Plan 1.3)" button. Replace that single disabled button with two real ones, and wire the existing `<pre id="ingest-log">` to render the streamed lines:

       Add at top of the file (after existing imports):
       ```typescript
       import { useIngestStream } from '../api/client'
       ```

       In the component body (after the existing `useUpdateProject` line), add:
       ```typescript
       const ingest = useIngestStream(id)
       ```

       Replace the existing `<Flex gap="2" mb="3">...3 disabled buttons...</Flex>` block with:
       ```typescript
       <Flex gap="2" mb="3" wrap="wrap">
         <Button
           onClick={() => ingest.start('wikidata')}
           disabled={ingest.isStreaming}
         >
           {ingest.isStreaming ? 'Ingesting…' : 'Ingest from Wikidata'}
         </Button>
         <Button
           variant="soft"
           onClick={() => ingest.start('osm')}
           disabled={ingest.isStreaming}
         >
           Ingest from OSM
         </Button>
         <Button disabled title="Will be wired by Plan 1.4 (map generation)">Generate (Plan 1.4)</Button>
         <Button disabled title="Will be wired by Plan 1.5 (Unity export)">Export ZIP (Plan 1.5)</Button>
       </Flex>
       {ingest.error && (
         <Text color="red" size="2">Ingest error: {ingest.error.message}</Text>
       )}
       ```

       Replace the existing `<pre id="ingest-log" ... />` empty element with one that renders the streamed text:
       ```typescript
       <pre
         id="ingest-log"
         style={{
           marginTop: 4,
           padding: 8,
           background: '#f5f5f5',
           borderRadius: 4,
           maxHeight: 240,
           overflow: 'auto',
           fontSize: 12,
           whiteSpace: 'pre-wrap',
         }}
       >
         {ingest.lines.join('')}
       </pre>
       ```

    3. Rebuild and verify:
       ```bash
       cd frontend && npm run build
       ```

       Verify the bundle still produces `backend/medieval_forge/static/index.html` and the source contains the new code paths:
       ```bash
       grep -l "useIngestStream" frontend/src/pages/ProjectDetail.tsx
       ```
  </action>
  <read_first>
    - frontend/src/api/client.ts
    - frontend/src/pages/ProjectDetail.tsx
    - .planning/phases/01-data-pipeline-backend-scaffold/01-CONTEXT.md
  </read_first>
  <verify>
    <automated>cd frontend && npm run build && grep -l "useIngestStream" src/pages/ProjectDetail.tsx</automated>
  </verify>
  <done>npm run build succeeds with the new code; ProjectDetail.tsx imports useIngestStream; the file contains "Ingest from Wikidata" button text.</done>
  <acceptance_criteria>
    - frontend/src/api/client.ts contains "export function useIngestStream"
    - frontend/src/api/client.ts contains "/api/projects/${projectId}/ingest?source="
    - frontend/src/api/client.ts contains "res.body.getReader()"
    - frontend/src/api/client.ts contains "data: " (the prefix being stripped)
    - frontend/src/pages/ProjectDetail.tsx contains "useIngestStream"
    - frontend/src/pages/ProjectDetail.tsx contains "Ingest from Wikidata"
    - frontend/src/pages/ProjectDetail.tsx contains "Ingest from OSM"
    - frontend/src/pages/ProjectDetail.tsx contains "ingest.lines.join"
    - frontend/src/pages/ProjectDetail.tsx still contains "id=\"ingest-log\"" (preserved per D-09)
    - frontend/src/pages/ProjectDetail.tsx still contains "Plan 1.4" AND "Plan 1.5" (placeholders for downstream plans)
    - cd frontend && npm run build exits 0
  </acceptance_criteria>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Browser → POST /api/projects/{project_id}/ingest | Untrusted query params (source, country) and path param (project_id); validated before any external network call |
| FastAPI ingest service → Wikidata SPARQL endpoint | Outbound request; URL is constant; only validated QID is interpolated |
| FastAPI ingest service → OSM Overpass endpoint | Outbound request; URL is constant; only validated 2-letter ISO code is interpolated |
| FastAPI ingest service → filesystem (project raw/) | Path computed via project_dir() (already T-PATH validated); atomic temp+rename write |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-SSRF (Wikidata) | Spoofing | ingest_wikidata.fetch_municipalities | mitigate | `validate_qid` enforces `^Q\d+$` BEFORE composing the SPARQL query. WIKIDATA_ENDPOINT is a hardcoded module constant. The api/ingest.py layer ALSO validates the source param via `regex="^(wikidata|osm)$"` (defence in depth — even if the runner gained a code-injection bug, FastAPI's Query regex blocks bad source values at the route layer). |
| T-SSRF (OSM) | Spoofing | ingest_osm.fetch_municipalities | mitigate | `validate_iso_country` enforces `^[A-Z]{2}$` BEFORE composing the Overpass query. OVERPASS_ENDPOINT is a hardcoded module constant. |
| T-PATH | Tampering | api/ingest.py path-bound project_id | mitigate | `is_valid_uuid(project_id)` → 400 before any fs/db access; `ensure_project_dirs(project_id)` re-validates AND verifies the resolved path is within PROJECTS_ROOT. |
| T-DOS (overlap) | Denial of Service | api/ingest.py | mitigate | If `project.status == "generating"` the endpoint returns 409. (When Plan 04 lands, the symmetric guard in /generate will check for "ingesting" status — out of scope for this plan but noted.) |
| T-DOS (queue size) | Denial of Service | asyncio.Queue between producer and SSE consumer | accept | Single-user local tool; queue grows linearly with SSE messages (~1 per page = ~16 per Spain ingest), bounded in practice. Acceptable. |
| T-03-01 | Information Disclosure | SSE error messages contain raw exception strings | mitigate | The `ERROR: {exc}` message includes the exception's `str()` form. For Wikidata/OSM errors this reveals only HTTP status + URL fragment — no secrets in this code path. ASVS V7 satisfied (no stack traces). |
| T-03-02 | Tampering | OSM relation→GeoJSON conversion ignores inner-ring assignment | accept | Phase 1 ingestion is "best-effort"; geometric correctness for nested rings is polished in Phase 6 (or with osm2geojson dep). Documented in code as Phase 1 limitation. |
</threat_model>

<verification>
After all 5 tasks complete, run the per-wave verification command from VALIDATION.md:

```bash
py -m pytest backend/tests/ -v --tb=short --ignore=backend/tests/test_generate.py
```

Expected: 21 passing tests (5 cli + 1 packaging + 9 projects + 7 ingest = 22... but 1 packaging-slow is excluded by default so 21). Plan 04 and 05 stub files don't exist yet.

Manual end-to-end smoke (one-off, requires network):
```bash
medieval-forge start --no-browser
# Browser: http://localhost:8765/projects/new — create project country_qid=Q45 (Portugal — small enough for fast smoke test)
# On detail page: click "Ingest from Wikidata" → log panel populates with "Fetching Wikidata page offset=0..." messages, eventually "DONE"
# After completion, refresh — project status should display "ingested"
# Verify on disk:
ls ~/.medieval-forge/projects/{the-uuid}/raw/municipalities.geojson
medieval-forge stop
```
</verification>

<success_criteria>
- `py -m pytest backend/tests/test_ingest.py -x -q` passes 7/7.
- `py -m pytest backend/tests/ -x -q --ignore=backend/tests/test_generate.py` passes cumulative 21/21.
- Manual smoke: triggering Wikidata ingest for a small country (Portugal Q45) populates `~/.medieval-forge/projects/{uuid}/raw/municipalities.geojson` with valid GeoJSON FeatureCollection, project.status flips to "ingested".
- Frontend Ingest buttons stream live text into the existing `#ingest-log` panel (D-09 satisfied — no progress bar, just live text).
- T-SSRF guards prove their value via the validator unit tests; the api layer's `regex="^(wikidata|osm)$"` plus `is_valid_uuid` provides defence in depth.
- ROADMAP success criteria #3 (trigger Wikidata ingestion + see real-time progress + GeoJSON written) is now exercisable end-to-end.
</success_criteria>

<output>
After completion, create `.planning/phases/01-data-pipeline-backend-scaffold/01-03-SUMMARY.md` per the standard summary template. Note: (a) any tuning of page_size or timeout based on observed Wikidata behavior, (b) decision on whether to add osm2geojson dep in Phase 6 vs keeping the inline converter, (c) any additional buttons/labels added to ProjectDetail that Plans 04/05 should integrate with rather than duplicate.
</output>
