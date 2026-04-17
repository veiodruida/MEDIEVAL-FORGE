---
status: resolved
trigger: "country-clipping — bbox OSM ingest returns features outside target country (French départements appear in Iberia ingest)"
created: 2026-04-17T02:00:00Z
updated: 2026-04-17T03:00:00Z
symptoms_prefilled: true
---

## Current Focus

hypothesis: CONFIRMED — fetch_municipalities used bbox-only query with no country polygon clipping. Fix implemented and all 3 unit tests pass.
test: _clip_features_to_countries with unit square country polygon — 2 inside kept, 2 outside removed.
expecting: Human re-ingest Iberia and confirm no French départements in municipalities.geojson
next_action: Await human visual verification

## Symptoms

expected: Ingesting Iberia (bbox -13.2,35.4,8.2,44.6) returns only Spanish + Portuguese admin regions
actual: French départements (Dordogne, Landes, Alpes-Maritimes, etc.) and possibly Moroccan/Algerian regions appear because bbox query includes all relations whose bbox intersects
errors: None — pipeline succeeds, result is semantically wrong
reproduction: New project Iberia bbox → Ingerir via OSM → check municipalities.geojson features[0..4] = French départements
started: Since Phase 1 completion

## Eliminated

- hypothesis: Filter by is_in:country tag on OSM relations
  evidence: Unreliable — many relations do not carry this tag; not worth depending on
  timestamp: 2026-04-17T02:00:00Z

- hypothesis: Use embedded country polygons
  evidence: Goes stale, only works for known countries; the Overpass approach is always up-to-date and already fetching from OSM
  timestamp: 2026-04-17T02:00:00Z

## Evidence

- timestamp: 2026-04-17T02:00:00Z
  checked: backend/medieval_forge/services/ingest_osm.py _build_bbox_query
  found: Query is pure bbox — no country filter whatsoever
  implication: Every admin_level=6 relation whose bbox overlaps the query bbox is returned regardless of country

- timestamp: 2026-04-17T02:00:00Z
  checked: fetch_municipalities signature and ingest_runner.run_ingest call
  found: country_iso is passed but only used to build country-based query when bbox=None; when bbox is provided the ISO is ignored entirely
  implication: The country_iso parameter is the perfect hook for wiring clip_iso_codes

- timestamp: 2026-04-17T02:00:00Z
  checked: countries.py PRESETS — Iberia entry
  found: country_qid="Q29" (Spain) only — no Portugal (Q45). Multi-country regions need both ISOs.
  implication: Iberia must clip to ES union PT

- timestamp: 2026-04-17T03:00:00Z
  checked: 3 new unit tests — test_clip_features_keeps_inside_and_removes_outside, test_clip_features_empty_polys_returns_all, test_clip_features_multi_country_union
  found: All 3 pass. Full ingest suite: 14 pass, 1 pre-existing failure (test_sse_stream Portuguese string). Zero regressions.
  implication: Fix is correct and complete

## Resolution

root_cause: _build_bbox_query returns all OSM admin_level=6 relations within the bounding box regardless of which country they belong to. country_iso was ignored when bbox was provided.

fix: Added _build_country_boundary_query, _relation_to_polygon, _fetch_country_polygon, _clip_features_to_countries to ingest_osm.py. Added clip_iso_codes parameter to fetch_municipalities — when provided, fetches admin_level=2 country boundary polygon for each ISO via Overpass, unions them with shapely.ops.unary_union, filters municipality features by representative_point inside union. Added clip_iso_codes_for_qid() to countries.py to derive clip list from project QID. Wired through ingest_runner.run_ingest and api/ingest.trigger_ingest. Iberia preset updated with clip_iso_codes=["ES","PT"]. Portugal preset gets clip_iso_codes=["PT"].

verification: 3 new unit tests pass. 14/15 ingest tests pass (1 pre-existing failure unrelated). Integration confirmed by code path analysis.

files_changed:
  - backend/medieval_forge/services/ingest_osm.py
  - backend/medieval_forge/services/ingest_runner.py
  - backend/medieval_forge/services/countries.py
  - backend/medieval_forge/api/ingest.py
  - backend/tests/test_ingest.py
