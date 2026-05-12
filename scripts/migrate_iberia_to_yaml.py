"""One-shot: extract iberia_config() + territory_data into data/regions/iberia_868.yaml.

Idempotent: re-running overwrites with byte-equal output (sort_keys=False,
default_flow_style=False, deterministic ordering of dict keys).
Usage: `python scripts/migrate_iberia_to_yaml.py`

Data-shape notes (R-01 review, Rule 1 deviation from plan literal):
  - KINGDOMS is dict[str, str] in territory_data.py → emitted as list[dict] to
    match RegionConfigSchema.kingdoms: list[dict]
  - DUCHIES is dict[str, tuple[str, str]] → emitted as list[dict] with id/kingdom_id/name
  - CONDADOS is list[tuple(id, name, lon, lat, duchy_id, baronies)] → converted to
    list[dict] with all fields + original_idx (CLAUDE.md rule 4, Nájera bug guard)
  - kingdom_colors int keys (0..3) → emitted as str keys because RegionConfigSchema
    declares dict[str, list[int]] and pydantic v2 rejects int keys
"""
import sys
import yaml
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from medieval_forge.services.pipeline.regions import iberia_config
from medieval_forge.data.regions.iberia_868.territory_data import KINGDOMS, DUCHIES, CONDADOS

OUT = REPO / "data" / "regions" / "iberia_868.yaml"


def main() -> None:
    cfg = iberia_config()

    # R-01 (review): dataset_dict contains ONLY str values (or None for optional
    # fields). NEVER pass cfg.dataset directly to yaml.safe_dump — that would emit
    # !!python/object:apply:...ProjectDataset tags and break pydantic validation in
    # load_region. Sanity-capture first via str(cfg.dataset.*) to assert non-empty:
    _captured = {
        "pt_geojson": str(cfg.dataset.pt_geojson),
        "es_input": str(cfg.dataset.es_input),
        "mountain_river_json": str(cfg.dataset.mountain_river_json) if cfg.dataset.mountain_river_json else None,
    }
    assert _captured["pt_geojson"] and _captured["es_input"], (
        "iberia_config() dataset paths must be populated before migration"
    )
    # Dataset paths stored as YAML-relative under data/regions/iberia_868/
    dataset_dict = {
        "pt_geojson": "inputs/pt_concelhos_wgs84.geojson",
        "es_input": "inputs/es-atlas-pkg/package/es/municipalities.json",
        "mountain_river_json": "inputs/mountain_river_data.json",
    }

    # KINGDOMS: dict[str, str] → list[dict] (matches RegionConfigSchema.kingdoms: list[dict])
    kingdoms_out = [{"id": k, "name": v} for k, v in KINGDOMS.items()]

    # DUCHIES: dict[str, tuple[str, str]] → list[dict]
    duchies_out = [
        {"id": did, "kingdom_id": kid, "name": dname}
        for did, (kid, dname) in DUCHIES.items()
    ]

    # CONDADOS: list[tuple(id, name, lon, lat, duchy_id, baronies)] → list[dict]
    # R-01 (review): CONDADOS migration MUST include original_idx for every entry —
    # CLAUDE.md non-negotiable rule 4 (Nájera bug guard). Sequential original_idx
    # starting at 1; assert uniqueness.
    condados_out = []
    seen_idx: set[int] = set()
    for i, raw_condado in enumerate(CONDADOS, start=1):
        cid, cname, lon, lat, duchy_id = raw_condado[0], raw_condado[1], raw_condado[2], raw_condado[3], raw_condado[4]
        baronies_raw = raw_condado[5]
        kingdom_id = DUCHIES[duchy_id][0]
        baronies_out = [
            {"name": bn, "lon": float(blon), "lat": float(blat)}
            for bn, blon, blat in baronies_raw
        ]
        entry = {
            "id": cid,
            "name": cname,
            "lon": float(lon),
            "lat": float(lat),
            "duchy_id": duchy_id,
            "kingdom_id": kingdom_id,
            "original_idx": i,
            "baronies": baronies_out,
        }
        assert entry["original_idx"] not in seen_idx, (
            f"duplicate original_idx={entry['original_idx']} in CONDADOS — Najera bug guard"
        )
        seen_idx.add(entry["original_idx"])
        condados_out.append(entry)

    # kingdom_colors: int keys (0..3) → str keys because RegionConfigSchema declares
    # dict[str, list[int]] and pydantic v2 rejects int dict keys at validation time.
    kingdom_colors_out = {str(k): list(v) for k, v in cfg.kingdom_colors.items()}

    assert cfg.output_dir, "iberia_config() output_dir must be populated before migration"

    doc = {
        "name": cfg.name,
        "display_name": "Iberia 868 AD",  # R-06 (review): human-readable label
        "map_w": cfg.map_w,
        "map_h": cfg.map_h,
        "upscale": cfg.upscale,
        "lon_min": cfg.lon_min,
        "lon_max": cfg.lon_max,
        "lat_min": cfg.lat_min,
        "lat_max": cfg.lat_max,
        "output_dir": cfg.output_dir,
        "dataset": dataset_dict,
        "border_polygon": [list(p) for p in cfg.border_polygon],
        "pt_duchies": sorted(cfg.pt_duchies),
        "kingdom_colors": kingdom_colors_out,
        # Rendering
        "ocean_near": list(cfg.ocean_near),
        "ocean_far": list(cfg.ocean_far),
        "ocean_gradient_dist": cfg.ocean_gradient_dist,
        "coast_inner_width": cfg.coast_inner_width,
        "coast_inner_color": list(cfg.coast_inner_color),
        # Cleanup
        "island_min_px": cfg.island_min_px,
        "fragment_min_px": cfg.fragment_min_px,
        "blob_merge_px": cfg.blob_merge_px,
        "median_passes": cfg.median_passes,
        "smooth_sigma": cfg.smooth_sigma,
        # Mountain config
        "mountain_threshold": cfg.mountain_threshold,
        "mountain_color_visual": list(cfg.mountain_color_visual),
        "mountain_color_lookup": list(cfg.mountain_color_lookup),
        "mountain_noise": cfg.mountain_noise,
        # River config
        "river_color": list(cfg.river_color),
        "river_width": cfg.river_width,
        # Determinism + naming
        "rng_seed": cfg.rng_seed,
        "draw_names": cfg.draw_names,
        # Territory data
        "kingdoms": kingdoms_out,
        "duchies": duchies_out,
        "condados": condados_out,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, sort_keys=False, default_flow_style=False, allow_unicode=True)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
