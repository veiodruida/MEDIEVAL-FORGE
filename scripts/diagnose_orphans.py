"""diagnose_orphans.py — one-shot diagnostic for the territory-orphan bug.

Compares territory_metadata.json vs territories.geojson vs lookup_condado.png
+ lookup_condado_colors.json to identify which of the four hypotheses (see
.planning/quick/260426-pcy-fix-orphan-bug-13-condados-in-territory-/260426-pcy-PLAN.md)
is causing condados present in metadata to be missing from the geojson.

Usage:
    python scripts/diagnose_orphans.py <project_uuid>

Exits 0 with "no orphans" if metadata.condados.id == geojson.features.id.
Otherwise prints per-orphan evidence rows + bucket counts + a final
ROOT_CAUSE_HYPOTHESIS line (H1/H2/H3/H4 or MIXED).

Hypotheses (per PLAN):
    H1 — pc/lookup mismatch (orig_idx never landed in metadata-position;
         e.g. legacy identity-fallback path silently dropped orig_idx
         >= len(condados_meta) inside emit_territories_from_disk).
    H2 — deterministic RGB collides with cfg.ocean_far → indistinguishable
         from background after PNG roundtrip.
    H3 — rasterio.features.shapes / unary_union collapses to empty geometry
         for an index that DOES have pixels in the PNG.
    H4 — manual-provider stale research mismatch (orphan id is not in
         original_condados at all — out of scope for this quick task).

----------------------------------------------------------------------------
DIAGNOSTIC OUTPUT — ran 2026-04-26 against project
2d402c81-0b72-4cbb-8b61-21d72eff2a44 (the user-confirmed bug repro):

    project=2d402c81-0b72-4cbb-8b61-21d72eff2a44
    n_metadata=19  n_geojson=7  orphans=12

                id   orig_idx                   rgb    png_px  in_colors  meta_px  ocean_far?
    --------------------------------------------------------------------------------------------
           alcacer         62          (40,254,124)      3853       True     3853  -
              beja         64          (114,144,94)      5867       True     5867  -
             braga         10          (164,42,136)      1825       True     1825  -
          braganca         13            (19,5,219)      3802       True     3802  -
            chaves         12         (238,188,106)      3564       True     3564  -
             evora         63           (77,71,237)      6236       True     6236  -
            lamego         27              (25,3,9)      3250       True     3250  -
             porto          9          (127,225,23)       649       True      649  -
         salamanca         18          (204,114,16)       491       True      491  -
          santarem         61            (3,181,11)      5973       True     5973  -
               tui          8          (90,152,166)       445       True      445  -
             viana         11         (201,115,249)      1333       True     1333  -

    H2 ocean_far collisions: 0
    H1 pc/lookup mismatch  : 12
    H3 degenerate geometry : 0
    H4 manual mismatch     : 0

    ROOT_CAUSE_HYPOTHESIS: H1

    Interpretation: every orphan has a recorded rgb in colors.json AND a
    matching block of pixels in the lookup PNG (px == metadata pixel_count).
    But each orphan's orig_idx (e.g. tui=8, lamego=27, beja=64) does NOT
    equal its metadata position (tui meta_ci=0, lamego meta_ci=7, beja
    meta_ci=17). emit_territories_from_disk's legacy identity-fallback path
    (territories_geojson.py lines 230-239, taken when original_condados is
    None) writes pc[mask]=orig_idx; build_territories_geojson then
    enumerates condados 0..n_meta-1 and only matches features where
    orig_idx == meta_ci. Whenever they differ, the orphan is silently
    dropped — and a different metadata entry steals its pixels via the
    identity collision. Hence the 7 surviving features (viseu, coimbra,
    leiria, idanha, badajoz, lisboa, silves) actually carry the geometry
    of tui/porto/braga/viana/chaves/braganca/salamanca.

    The current production call site (services/generator.py:361) DOES pass
    original_condados — but this stale project was generated through a
    legacy code path that did not. The latent bug is the SILENT drop
    inside the fallback: future call sites or older fixtures that omit
    original_condados will recreate the symptom unnoticed. Fix branch H1
    therefore turns the silent skip into a hard failure and keeps a
    soft-assertion log in build_territories_geojson as belt + suspenders.
----------------------------------------------------------------------------
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# Allow running from repo root without installing the package.
_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "backend"))

from medieval_forge.database import DATA_DIR  # noqa: E402
from medieval_forge.lib.map_generator import RegionConfig  # noqa: E402


def _expected_rgb(orig_idx: int) -> tuple[int, int, int]:
    """Mirror map_generator.generate_lookup_map deterministic RGB formula."""
    return (
        (orig_idx * 37 + 50) % 256,
        (orig_idx * 73 + 80) % 256,
        (orig_idx * 113 + 30) % 256,
    )


def _load(generated_dir: Path) -> tuple[dict, dict, dict, np.ndarray]:
    meta = json.loads((generated_dir / "territory_metadata.json").read_text(encoding="utf-8"))
    gj = json.loads((generated_dir / "territories.geojson").read_text(encoding="utf-8"))
    colors = json.loads((generated_dir / "lookup_condado_colors.json").read_text(encoding="utf-8"))
    img = np.array(Image.open(generated_dir / "lookup_condado.png").convert("RGB"))
    return meta, gj, colors, img


def _orig_idx_for_meta_id(
    meta_id: str,
    condados_meta: list[dict],
    img: np.ndarray,
    colors: dict[str, int],
) -> int | None:
    """Infer orig_idx for a given metadata condado id.

    Strategy: each entry in colors.json is `{"r,g,b": orig_idx}`. The
    pixels of that rgb in the PNG centroid-match a condado in metadata
    (whose `pixel_center` was computed from the same pixels). We infer
    orig_idx → meta_id by matching pixel_center.

    Returns None if no rgb in colors.json matches this metadata entry's
    pixel_center (=> H4 candidate: id has no painted pixels at all).
    """
    target = next(
        (c for c in condados_meta if c["id"] == meta_id),
        None,
    )
    if target is None:
        return None
    target_xy = tuple(target.get("pixel_center", [-1, -1]))
    if target_xy == (-1, -1):
        return None

    best_match: tuple[float, int] | None = None
    for rgb_key, orig_idx in colors.items():
        try:
            r, g, b = (int(p) for p in rgb_key.split(","))
        except ValueError:
            continue
        mask = (img[:, :, 0] == r) & (img[:, :, 1] == g) & (img[:, :, 2] == b)
        if not mask.any():
            continue
        ys, xs = np.where(mask)
        cx = float(xs.mean())
        cy = float(ys.mean())
        dx = cx - target_xy[0]
        dy = cy - target_xy[1]
        d2 = dx * dx + dy * dy
        if best_match is None or d2 < best_match[0]:
            best_match = (d2, int(orig_idx))

    if best_match is None:
        return None
    # Accept the best match if within a reasonable pixel radius — anything
    # larger means the metadata id is not painted at all (H4).
    if best_match[0] > 100 * 100:  # >100 px miss => no plausible link
        return None
    return best_match[1]


def diagnose(project_uuid: str) -> int:
    generated_dir = Path(DATA_DIR) / "projects" / project_uuid / "generated"
    if not generated_dir.is_dir():
        print(f"ERROR: {generated_dir} does not exist", file=sys.stderr)
        return 2

    meta, gj, colors, img = _load(generated_dir)
    condados_meta: list[dict] = meta["condados"]
    metadata_ids = {c["id"] for c in condados_meta}
    geojson_ids = {f["id"] for f in gj["features"]}
    orphans = sorted(metadata_ids - geojson_ids)

    print(f"project={project_uuid}")
    print(f"n_metadata={len(metadata_ids)}  n_geojson={len(geojson_ids)}  orphans={len(orphans)}")
    if not orphans:
        print("no orphans")
        return 0

    # Reconstruct cfg.ocean_far the same way the run constructed it. We do
    # not have the project's generator_config here without going through the
    # async DB layer; for the purpose of H2 detection, RegionConfig defaults
    # are a sound baseline (ocean_far defaults to (70,130,180)). If the
    # caller overrode ocean_far we'd see fewer "would-collide" hits — but
    # H2 only needs to flag a SINGLE collision to be the root cause.
    ocean_far = tuple(RegionConfig().ocean_far)

    h1_hits: list[str] = []   # orig_idx in colors.json AND meta_ci-mismatch (legacy fallback drop)
    h2_hits: list[str] = []   # rgb collides with ocean_far
    h3_hits: list[str] = []   # png has pixels but no shape produced
    h4_hits: list[str] = []   # orphan has no orig_idx anywhere (not painted at all)

    print()
    print(f"{'id':>14}  {'orig_idx':>9}  {'rgb':>20}  {'png_px':>8}  in_colors  meta_px  ocean_far?")
    print("-" * 100)

    for oid in orphans:
        meta_entry = next(c for c in condados_meta if c["id"] == oid)
        orig_idx = _orig_idx_for_meta_id(oid, condados_meta, img, colors)
        if orig_idx is None:
            h4_hits.append(oid)
            print(f"{oid:>14}  {'?':>9}  {'(no painted pixels)':>20}  "
                  f"{'-':>8}  {'-':>9}  {meta_entry.get('pixel_count', 0):>7}  -")
            continue

        rgb = _expected_rgb(orig_idx)
        rgb_key = f"{rgb[0]},{rgb[1]},{rgb[2]}"
        in_colors = rgb_key in colors
        mask = (img[:, :, 0] == rgb[0]) & (img[:, :, 1] == rgb[1]) & (img[:, :, 2] == rgb[2])
        png_px = int(mask.sum())
        equals_ocean = rgb == ocean_far

        rgb_str = f"({rgb[0]},{rgb[1]},{rgb[2]})"
        print(f"{oid:>14}  {orig_idx:>9}  {rgb_str:>20}  {png_px:>8}  "
              f"{str(in_colors):>9}  {meta_entry.get('pixel_count', 0):>7}  "
              f"{'YES' if equals_ocean else '-'}")

        # Find this orphan's position in the metadata list (meta_ci).
        meta_ci = next(i for i, c in enumerate(condados_meta) if c["id"] == oid)

        if equals_ocean:
            h2_hits.append(oid)
        elif in_colors and png_px == 0:
            # rgb recorded in colors.json but no pixels carry that color in the
            # PNG — overwritten or never painted. H1 (pc/lookup mismatch).
            h1_hits.append(oid)
        elif in_colors and png_px > 0 and orig_idx != meta_ci:
            # PNG has pixels for this orphan's color, but its orig_idx differs
            # from its meta_ci position. The legacy identity-fallback inside
            # emit_territories_from_disk paints pc[mask]=orig_idx and then
            # build_territories_geojson enumerates 0..n_meta-1; whenever
            # orig_idx != meta_ci, the orphan is silently lost (and a
            # different metadata entry steals its pixels via the identity
            # collision). This is H1 (pc/lookup index-space mismatch).
            h1_hits.append(oid)
        elif in_colors and png_px > 0 and orig_idx == meta_ci:
            # Pixels exist, indices align — but no feature was produced.
            # That implies rasterio.features.shapes / unary_union collapsed
            # to empty. H3 (degenerate geometry).
            h3_hits.append(oid)
        else:
            # rgb not in colors.json at all — colour map drift; classify as H1.
            h1_hits.append(oid)

    print()
    print(f"H2 ocean_far collisions: {len(h2_hits)}")
    print(f"H1 pc/lookup mismatch  : {len(h1_hits)}")
    print(f"H3 degenerate geometry : {len(h3_hits)}")
    print(f"H4 manual mismatch     : {len(h4_hits)}")
    print()

    buckets = [(len(h2_hits), "H2"), (len(h1_hits), "H1"),
               (len(h3_hits), "H3"), (len(h4_hits), "H4")]
    nonzero = [b for b in buckets if b[0] > 0]
    if len(nonzero) == 1:
        print(f"ROOT_CAUSE_HYPOTHESIS: {nonzero[0][1]}")
    else:
        labelled = ", ".join(f"{name}={cnt}" for cnt, name in nonzero)
        print(f"ROOT_CAUSE_HYPOTHESIS: MIXED  ({labelled})")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/diagnose_orphans.py <project_uuid>", file=sys.stderr)
        return 64
    return diagnose(sys.argv[1])


if __name__ == "__main__":
    raise SystemExit(main())
