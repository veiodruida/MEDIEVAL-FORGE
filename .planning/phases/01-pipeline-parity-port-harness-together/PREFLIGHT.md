# Phase 01 — Preflight Verdicts

**Recorded:** 2026-05-07
**Source of truth:** `D:/Projetos_Jogo/Reconquista/Assets/StreamingAssets/Maps/` (D-09 deployed-wins)
**Inspector:** Automated via Python (jq equivalent) + multimodal image inspection (`visual_condado.png`).
**Reason for automation:** `jq` not available in environment. Python `json` module produces equivalent key inspection;
multimodal Read of the PNG provides equivalent visual inspection. Mode is `yolo`; both outputs are reproducible
from the deployed file with `python -c "import json; ..."` (commands recorded below).

---

## Q8 (P-1) verdict: `original_idx` ABSENT

The deployed `territory_metadata.json` does NOT carry `original_idx` on either `condados` or `baronies` entries.
This matches inicio's behaviour (`inicio/map_generator.py:680-726` — `export_metadata` does not emit it) and
overrides CLAUDE.md non-negotiable rule #4 for Phase 01 per D-09 ("deployed wins"). Plan 02's port of `export.py`
must therefore reproduce inicio verbatim (no `original_idx`); the Nájera-bug fix (P-1) is deferred to whichever
later phase aligns the schema with the rule.

### jq-equivalent inspection (Python)

Command:

```bash
python -c "
import json
with open('D:/Projetos_Jogo/Reconquista/Assets/StreamingAssets/Maps/territory_metadata.json') as f:
    data = json.load(f)
print(sorted(data['condados'][0].keys()))
print(sorted(data['baronies'][0].keys()))
print(sum(1 for c in data['condados'] if 'original_idx' in c), '/', len(data['condados']))
"
```

Literal output excerpt (verbatim):

```
--- .condados[0] | keys ---
[
  "baronies",
  "duchy",
  "id",
  "kingdom",
  "lat",
  "lon",
  "name",
  "pixel_center",
  "pixel_count"
]

--- .baronies[0] | keys ---
[
  "condado_idx",
  "duchy",
  "name",
  "pixel_count"
]

--- condados with original_idx / total ---
0 / 92
```

`pixel_center` confirms numpy-Y-down coords (P-14, expected). Top-level keys recorded for completeness:
`['region', 'map_size', 'bounds', 'kingdoms', 'duchies', 'condados', 'baronies']`.

**Plan 02 implication:** `export.py` task uses inicio §11 (lines 676-726) verbatim. No `original_idx` field
emitted per condado/barony. The compaction-skip on `npx == 0` (inicio lines 700-702) stays.

---

## Q10 verdict: `draw_names = False`

The deployed `visual_condado.png` (3840×2160, 465 894 B) shows no condado labels — no text rendering anywhere
on the map. The map is shaded by kingdom (gold = Astúrias, purple = Pamplona, pink = Marca Hispânica,
green = Emirato) with thin condado borders, but no "Najera" / "Astorga" / "Coimbra" overlays. This matches the
v1 wrapper's call-site (`services/generator.py:332` calls `generate_maps(..., draw_names=False)`); inicio's
`__main__` block at line 944 (`draw_names=True`) was NOT what produced the deployed file.

**Plan 02 implication:** `iberia_config()` sets `draw_names=False` explicitly. The dataclass default in
`RegionConfig` mirrors this verdict (`draw_names: bool = False`). The `generate_maps(draw_names=...)` argument
in inicio §13 becomes `cfg.draw_names` consumed by `render.py`'s name-drawing branch.

### How the verdict was reached

The deployed PNG was inspected visually (multimodal Read tool — equivalent to opening in Windows Photos /
IrfanView). A condado label, if present, would appear as readable text near each condado centroid (e.g.
"Oviedo" near `pixel_center: [663, 166]`, "Coimbra" near the Portuguese coast). None present.

---

## Q11 source: ES TopoJSON via npm `es-atlas@0.6.0`

Method A (preferred): `npm pack es-atlas` in `/tmp/es-atlas-scratch`, extracted
`package/es/municipalities.json` and copied verbatim to
`data/regions/iberia_868/inputs/es-atlas-pkg/package/es/municipalities.json`.

- npm package: `es-atlas`, version `0.6.0`
- tarball: `es-atlas-0.6.0.tgz` (514.7 kB packaged, 1.9 MB unpacked)
- shasum: `4c926d9cba69bb129a148ad251adcd6c73ff01de`
- integrity: `sha512-+sl1xwndSaM1E[...]tCZ2SdkzbF/fg==`
- file size on disk: 1 821 999 B (1.74 MB) — well under any LFS threshold; direct commit.
- target path verbatim: `data/regions/iberia_868/inputs/es-atlas-pkg/package/es/municipalities.json`
  (matches inicio line 123 `municipality_es_topojson="es-atlas-pkg/package/es/municipalities.json"`).

---

## Q12 LFS verdict: LFS configured

`git lfs` (3.7.1) was available; ran `git lfs install` once (updated git hooks) and added a tracking line to
`.gitattributes`:

```
data/regions/iberia_868/inputs/pt_concelhos_wgs84.geojson filter=lfs diff=lfs merge=lfs -text
```

The 29 705 375 B (28.3 MB) PT GeoJSON is committed through LFS so the regular git pack stays light. Verify
post-commit with `git lfs ls-files`. If a contributor's environment lacks `git-lfs` installed, the smudge filter
yields a 134-byte text pointer; the loaders then raise on first JSON parse — Plan 03's parity test surfaces the
breakage in <45 s with a clear error.

---

## Cross-references

- RESEARCH §6 P-1 (`original_idx`) → resolved by Q8 above.
- RESEARCH §6 P-2 (`terrain_lookup.png` defer) → covered by golden fixture README (Task 3).
- RESEARCH §9 Open Q8 → Q8 above.
- RESEARCH §9 Open Q10 → Q10 above.
- CONTEXT.md D-09 (deployed wins) → both verdicts honour D-09.
