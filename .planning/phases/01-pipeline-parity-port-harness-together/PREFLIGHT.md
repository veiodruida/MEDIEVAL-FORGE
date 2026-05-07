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

## Q11 source: ES TopoJSON (Task 2)

ES TopoJSON `municipalities.json` is sourced via npm (`npm pack es-atlas`) — preferred for reproducibility per
RESEARCH §4.b. Method to be exercised in Task 2; final source SHA recorded inline in this file at completion of
Task 2.

---

## Q12 LFS verdict (Task 2)

To be filled by Task 2: either "LFS configured" (`pt_concelhos_wgs84.geojson` tracked via `.gitattributes`) or
"direct commit fallback" (with reason — e.g. `git lfs` unavailable). Default plan: LFS.

---

## Cross-references

- RESEARCH §6 P-1 (`original_idx`) → resolved by Q8 above.
- RESEARCH §6 P-2 (`terrain_lookup.png` defer) → covered by golden fixture README (Task 3).
- RESEARCH §9 Open Q8 → Q8 above.
- RESEARCH §9 Open Q10 → Q10 above.
- CONTEXT.md D-09 (deployed wins) → both verdicts honour D-09.
