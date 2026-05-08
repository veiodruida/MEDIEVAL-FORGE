# Iberia 868 Golden Fixtures

Originally captured from `D:\Unity_Projects\Reconquista\Assets\StreamingAssets\Maps\` on
2026-05-07; **refreshed on 2026-05-08** from a fresh, deterministic run of the verbatim
Phase 01 port (`python -m medieval_forge.services.pipeline --region iberia_868 --out X`).
See [D-09-WAIVER.md](../../../.planning/phases/01-pipeline-parity-port-harness-together/D-09-WAIVER.md)
for why D-09 ("deployed wins") was set aside in favour of the verbatim-port output.

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
| `lookup_barony.png` | 53 924 | `numpy.array_equal` (byte-equal) |
| `lookup_condado.png` | 38 769 | `numpy.array_equal` (byte-equal) |
| `lookup_barony_colors.json` | 5 346 | `json.loads` deep-equal after key-sort |
| `lookup_condado_colors.json` | 1 873 | `json.loads` deep-equal after key-sort |
| `territory_metadata.json` | 65 104 | `json.loads` deep-equal after key-sort |
| `visual_condado.png` | 604 048 | `skimage.metrics.structural_similarity ≥ 0.98` |
| `visual_barony.png` | 643 658 | `skimage.metrics.structural_similarity ≥ 0.98` |
| `mountains_mask.png` | 11 976 | `skimage.metrics.structural_similarity ≥ 0.98` |
| `rivers_overlay.png` | 47 240 | `skimage.metrics.structural_similarity ≥ 0.98` |
| `mountain_river_data.json` | 20 543 | `json.loads` deep-equal after key-sort |
| **Total** | **~1.49 MB** | All committed direct (no LFS — well under threshold) |

`mountain_river_data.json` also lives at `data/regions/iberia_868/inputs/` (D-11): it is
both an input and an output, byte-identical, copied through unchanged by the pipeline.

## Refresh policy

**Use the in-repo refresh tool — never copy files by hand.** The tool is a pytest plugin
flag in `backend/tests/parity/conftest.py`:

```bash
# Dry-run (default): just shows what WOULD change. Safe to run anytime.
py -3.14 -m pytest backend/tests/parity/ -m parity --refresh-baseline

# Actually overwrite the golden fixtures:
py -3.14 -m pytest backend/tests/parity/ -m parity --refresh-baseline --confirm
```

The flag re-routes the fixture so each test writes its actual pipeline output to
`tests/fixtures/iberia_868/golden/` instead of asserting equality. Without `--confirm`
the tool only reports the diff; `--confirm` is required for the actual write to prevent
accidental clobbering of committed fixtures.

**Every refresh ships as an explicit commit** of the form `docs(parity): refresh
iberia_868 baseline — <reason>` with a justification doc under
`.planning/phases/.../D-09-WAIVER-*.md` (initial waiver lives at
`.planning/phases/01-pipeline-parity-port-harness-together/D-09-WAIVER.md`).

**Determinism check before refresh:** run the pipeline twice into separate dirs and
`diff -rq` the outputs — must be byte-identical. If not, the port has a non-determinism
bug and refresh would mask it. The refresh tool's unit test enforces this on the
test path; humans running the CLI must do this check manually.
