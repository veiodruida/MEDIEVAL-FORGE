# Iberia 868 Golden Fixtures

Snapshot of `D:/Projetos_Jogo/Reconquista/Assets/StreamingAssets/Maps/`
captured on 2026-05-07 for parity testing.

## Contract status (Phase 01)

Phase 01 parity covers **10 of 12** contract files. The two deferred:
- `terrain_lookup.png` — defer to Phase 06; inicio's pipeline does not produce it.
- `terrain_types.json` — defer to Phase 06; companion of terrain_lookup.png.

Both are part of the 12-file Unity export contract per `CLAUDE.md > v3 Pipeline Contract`,
but reproducing them requires porting code that lives outside `inicio/map_generator.py`'s
944 lines (the v1 wrapper's `generate_terrain_lookup`), which would violate D-01 (verbatim
port). Phase 06 (export contract + validation gate) is the right home for terrain.

## File inventory

| File | Size (B) | Comparison rule (D-12) |
|------|---------:|------------------------|
| `lookup_barony.png` | 55 142 | `numpy.array_equal` (byte-equal) |
| `lookup_condado.png` | 37 974 | `numpy.array_equal` (byte-equal) |
| `lookup_barony_colors.json` | 5 094 | `json.loads` deep-equal after key-sort |
| `lookup_condado_colors.json` | 1 893 | `json.loads` deep-equal after key-sort |
| `territory_metadata.json` | 65 445 | `json.loads` deep-equal after key-sort |
| `visual_condado.png` | 465 894 | `skimage.metrics.structural_similarity ≥ 0.98` |
| `visual_barony.png` | 505 303 | `skimage.metrics.structural_similarity ≥ 0.98` |
| `mountains_mask.png` | 12 232 | `skimage.metrics.structural_similarity ≥ 0.98` |
| `rivers_overlay.png` | 47 324 | `skimage.metrics.structural_similarity ≥ 0.98` |
| `mountain_river_data.json` | 19 307 | `json.loads` deep-equal after key-sort |
| **Total** | **~1.18 MB** | All committed direct (no LFS — well under threshold) |

`mountain_river_data.json` also lives at `data/regions/iberia_868/inputs/` (D-11): it is
both an input and an output, byte-identical, copied through unchanged by the pipeline.

## Refresh policy

Updates are explicit: a single `docs(parity): refresh iberia_868 baseline` commit. Never
silently re-snapshot — PR review catches drift.
