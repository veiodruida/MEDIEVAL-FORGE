# Session Handoff — 2026-04-16 (Map Pipeline Bugs)

## Summary

Investigated 3 bugs reported by user. Bug 1 fixed, Bug 2 was a workflow issue (backend not running), Bug 3 partially fixed — **still not producing target output**. User ended session to rest.

## Bugs Status

### Bug 1 — FIXED ✓
**Symptom:** "Área do mapa" link used a hardcoded URL, ignored the bbox input boxes.
**Fix:** `frontend/src/pages/ProjectNew.tsx` — link now builds `https://bboxfinder.com/#lat_min,lon_min,lat_max,lon_max` dynamically from bbox state; falls back to plain bboxfinder if any field empty.

### Bug 2 — NO CODE BUG ✓
**Symptom:** "Criar projeto" showed "Failed to fetch".
**Diagnosis:** Vite proxy `127.0.0.1:8765` OK, CLI listens on 8765, relative paths in `client.ts`, no CORS issue. "Failed to fetch" = connection refused = backend not running.
**Resolution:** User must run `medieval-forge start` before clicking Criar projeto.

### Bug 3 — PARTIAL / STILL BROKEN ✗
**Symptom:** Generated map (see `exports/visual_condado.png`) showed thread/filament fragments instead of solid filled territory polygons like reference `exemplos/visual_condado.png`.

**Investigation journey (chronological):**

1. **First hypothesis (wrong):** 3D camera / CSS transform / isometric render. Investigated — rejected. Pipeline is pure 2D PIL top-down.

2. **Second hypothesis (partial):** Sub-pixel seams in PIL polygon rasterizer + missing ES data + no ocean framing. Debugger applied:
   - `binary_closing(iterations=8)` in `lib/map_generator.py :: build_land_mask()`
   - New `_compute_padded_bbox()` in `services/generator.py` — auto-expands render bbox to cover all territory centroids + 15% ocean padding
   - Output: `exports/visual_condado_v2.png` showed solid Portugal shape but desaturated colors, jagged east coast, stray blue diamonds in south. **User reported it was still visually wrong.**

3. **Real root cause (identified at end of session):** `services/ingest_osm.py` was fetching `admin_level=8` = **freguesias** (~3000 tiny parishes per PT). The reference pipeline used CAOP concelhos (278 polygons, ~500px each). Freguesias are 10x smaller → each ~33px at render scale → PIL leaves sub-pixel seams between adjacent ones → filament pattern. `binary_closing` was a band-aid masking symptoms while eroding coastline detail.

**Fixes applied at end of session (not yet verified):**
- `backend/medieval_forge/services/ingest_osm.py`: `admin_level=8 → 6` in 3 places (docstring, `_build_bbox_query`, `_build_country_query`). `admin_level=6` in PT = concelhos/municípios (~308), matching reference CAOP count (~278).
- `backend/medieval_forge/lib/map_generator.py`: removed the `binary_closing` call (no longer needed with concelho-sized polygons) and its unused `binary_closing` import.

**Action user must do next session:**
1. Restart backend (`medieval-forge start`) — code changes require reload
2. For the existing project, re-click **"Ingerir via OSM"** (the old `municipalities.geojson` has freguesias and must be refetched)
3. Click **"Gerar"** again
4. Compare new `exports/visual_condado.png` to `exemplos/visual_condado.png`

**If still broken after re-ingest + regen, remaining hypotheses:**
- Gaussian smoothing sigma may need tuning (reference used σ=4.5; verify `lib/map_generator.py`)
- Color saturation: v2 output was grey/desaturated vs. vibrant reference. `KINGDOM_COLORS` in territory data may need boosted saturation.
- Stray blue diamonds in southern Portugal (v2) — unknown origin. Could be river markers, settlement icons, or debug overlay bleeding into visual render. Grep for diamond / marker / capital drawing.
- Jagged east coast on Portugal crop — may indicate the Gaussian smoothing is applied but the final coastline overlay isn't smoothed.

## Related Discussion: Wikidata ingest

User asked why "Ingerir via Wikidata" always says data is insufficient.

**Answer:** `services/ingest_wikidata.py:37` uses SPARQL `wdt:P625` which returns only **point coordinates (centroids)**, no polygons. The validator `services/generator.py::_validate_municipalities` rejects point-only data because the generator needs polygons to build the land mask. To make Wikidata-only ingest work would require:
- Reworking the SPARQL query to use `OPTIONAL { ?item wdt:P3896 ?geoshape }` (P3896 = geoshape GeoJSON URL on Wikimedia Commons)
- Fetching each geoshape URL separately
- Accepting partial coverage — many municipalities lack P3896, especially outside Western Europe

Recommendation: keep Wikidata as fallback/metadata only; use OSM (now with `admin_level=6`) as primary geometry source. This matches the briefing's original design.

## Reference Material

User placed the authoritative reference material in `inicio/licoes/`:
- `BRIEFING_MEDIEVAL_FORGE.md` — full original project briefing (the intended design, ~800 lines)
- `JORNADA_CRIACAO_MAPA.md` — Claude Chat's step-by-step journey creating the reference map (~770 lines, essential reading)
- `map_generator.py` (944 lines) — the WORKING reference implementation that produced `exemplos/visual_condado.png`
- `territory_data_v3.py` — Iberia 868 AD territory definitions (91 condados, 251 baronies)
- `mountain_river_data.json` — geographic features

**Reading order for next session:** `JORNADA_CRIACAO_MAPA.md` first (it's a condensed lessons-learned from 25 iterations), then diff `inicio/licoes/map_generator.py` against `backend/medieval_forge/lib/map_generator.py` to see any drift.

## Files Modified (uncommitted changes)

```
modified:   backend/medieval_forge/lib/map_generator.py
modified:   backend/medieval_forge/services/generator.py
modified:   backend/medieval_forge/services/ingest_osm.py
modified:   frontend/src/pages/ProjectNew.tsx
```

## Files Added (untracked)

```
.planning/debug/               — Full debug session files (map-pipeline-bugs.md + this handoff)
exemplos/                      — Reference image from Claude chat
exports/                       — Generated outputs (v1 filament, v2 partial) for comparison
inicio/licoes/                 — Authoritative reference material (briefing + working map_generator.py)
```

## What to do when resuming

1. Read `.planning/debug/map-pipeline-bugs.md` (full technical trace)
2. Read this file
3. User should restart backend + re-ingest + regenerate
4. If still broken, start with diff of `inicio/licoes/map_generator.py` vs current `lib/map_generator.py` — they are both 944 lines but may have drifted on rendering details
