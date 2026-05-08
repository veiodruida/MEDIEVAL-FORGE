# Iberia 868 — Live Ingestion Snapshot

Committed post-adapter GeoJSON outputs that drive `tests/parity/test_iberia_868_live.py`.

**Per CONTEXT.md decisions:**
- D-09 — no network in CI; the snapshot here is the only input the live parity test reads.
- D-10 — files live at `tests/fixtures/iberia_868/live-ingestion/`.
- D-12 — snapshot is post-adapter GeoJSON, not raw Overpass JSON.

## Files

| File | Source | Producer |
|------|--------|----------|
| `pt_concelhos_live.geojson` | Live OSM admin_level=6, split-by-ISO=PT | `services/pipeline/adapters/osm.build_dataset_from_osm` |
| `es_municipalities_live.geojson` | Live OSM admin_level=6, split-by-ISO=ES | (same as above) |

The terrain input (`mountain_river_data.json`) is NOT included here — Phase 02
uses the vendored copy at `data/regions/iberia_868/inputs/mountain_river_data.json`
per D-13 (terrain stub passthrough).

## Refresh ritual

Manual, deliberate, reviewed:

```bash
py -3.14 scripts/refresh_live_snapshot.py --region iberia_868
git diff --stat tests/fixtures/iberia_868/live-ingestion/
git add tests/fixtures/iberia_868/live-ingestion/
git commit -m "docs(parity): refresh live snapshot"
```

The script does NOT auto-commit. Review the diff first.

## Waiver loop (live-parity divergence policy)

Per Plan 03 `<approach>`: if `test_iberia_868_live.py` fails, the **snapshot is wrong**,
not the golden. Refresh via the script above. **Do NOT relax SSIM thresholds.**
This mirrors the Phase 01 D-09 "deployed wins" precedent.
