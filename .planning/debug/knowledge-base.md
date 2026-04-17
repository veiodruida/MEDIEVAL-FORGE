# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## osm-multipolygon-stitching — OSM relation parser shatters multi-way boundaries into hundreds of sub-polygons
- **Date:** 2026-04-17
- **Error patterns:** MultiPolygon, shattered, outer way, linemerge, polygonize, slivers, solid ocean, black outlines
- **Root cause:** _relation_to_geojson_feature force-closed each individual OSM way member as an independent ring, producing Dordogne with 252 parts instead of 1 closed polygon
- **Fix:** Rewrote to collect outer/inner ways as LineStrings, use linemerge(list) + polygonize() to assemble closed rings, pair inners to containing outers, emit Polygon or MultiPolygon. Pass list directly to linemerge — unary_union collapses single LineString causing ValueError.
- **Files changed:** backend/medieval_forge/services/ingest_osm.py, backend/tests/test_ingest.py
---

## country-clipping — bbox OSM ingest returns features from neighboring countries
- **Date:** 2026-04-17
- **Error patterns:** French départements, Dordogne, Landes, bbox, neighboring country, clipping, Iberia, municipalities outside
- **Root cause:** _build_bbox_query returned all admin_level=6 relations whose bbox intersected the query bbox, with no country filtering. country_iso parameter was ignored when bbox was provided.
- **Fix:** Added clip_iso_codes parameter to fetch_municipalities. Fetches admin_level=2 country boundary polygon(s) via Overpass for each ISO, unions with shapely.ops.unary_union, filters features by representative_point inside union. clip_iso_codes_for_qid() in countries.py derives ISOs from project QID. Iberia preset: ["ES","PT"]. Wired through ingest_runner and api/ingest.
- **Files changed:** backend/medieval_forge/services/ingest_osm.py, backend/medieval_forge/services/ingest_runner.py, backend/medieval_forge/services/countries.py, backend/medieval_forge/api/ingest.py, backend/tests/test_ingest.py
---

## terrain-lookup-stub — terrain.png all black, no terrain_lookup.png or terrain_types.json
- **Date:** 2026-04-17
- **Error patterns:** terrain.png black, all black, terrain_lookup, terrain_types.json, mountains_mask, placeholder, unimplemented
- **Root cause:** _PREVIEW_ALIASES mapped terrain.png → mountains_mask.png (binary impassable mask). When no mountain data configured, _materialise_aliases created a solid-black placeholder. terrain_lookup.png + terrain_types.json were never implemented.
- **Fix:** Added generate_terrain_lookup() to lib/map_generator.py: classifies pixels as ocean/mountain/coast/hill/forest/plain using land mask + mtn_mask + distance_transform_edt + spatial noise. _TERRAIN_TYPES dict with RGB + movement/defense/attack. Wired as step 15 in generate_maps(). Updated generator.py: added terrain_lookup.png + terrain_types.json to outputs, changed terrain.png alias → terrain_lookup.png, removed black placeholder fallback.
- **Files changed:** backend/medieval_forge/lib/map_generator.py, backend/medieval_forge/services/generator.py, backend/tests/test_generate.py
---

