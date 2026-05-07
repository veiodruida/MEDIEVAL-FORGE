"""Region registry per D-04: REGIONS = {"iberia_868": iberia_config}.

Verbatim port of inicio/map_generator.py §1 lines 115-145 (`iberia_config`)
with these substitutions per CONTEXT.md / RESEARCH:
  - municipality_pt_geojson  -> data/regions/iberia_868/inputs/pt_concelhos_wgs84.geojson  (D-11)
  - municipality_es_topojson -> data/regions/iberia_868/inputs/es-atlas-pkg/package/es/municipalities.json  (D-11)
  - mountain_river_json      -> data/regions/iberia_868/inputs/mountain_river_data.json  (D-11)
  - kingdoms/duchies/condados loaded statically from the package (D-13, D-14)
  - rng_seed=42 promoted onto cfg per CLAUDE.md determinism rule
  - draw_names=False per PREFLIGHT.md Q10 verdict
output_dir kept at inicio's default; Plan 03 conftest overrides at runtime.

The 38-point border_polygon, 4-color kingdom_colors, and 3-element pt_duchies
set are copied verbatim from inicio lines 125-143 (no reformatting).
"""

from .contracts import RegionConfig
from ...data.regions.iberia_868.territory_data import (
    KINGDOMS,
    DUCHIES,
    CONDADOS,
)


def iberia_config() -> RegionConfig:
    """Default configuration for the Iberian Peninsula (868 AD)."""
    cfg = RegionConfig(
        name="iberia",
        map_w=1920, map_h=1080, upscale=2,
        lon_min=-13.2, lon_max=8.2, lat_min=35.4, lat_max=44.6,
        output_dir="../Assets/StreamingAssets/Maps",
        municipality_pt_geojson="data/regions/iberia_868/inputs/pt_concelhos_wgs84.geojson",
        municipality_es_topojson="data/regions/iberia_868/inputs/es-atlas-pkg/package/es/municipalities.json",
        mountain_river_json="data/regions/iberia_868/inputs/mountain_river_data.json",
        pt_duchies={"d_portucale", "d_gharb", "d_fronteira"},
        kingdom_colors={
            0: (190, 158, 82),   # Astúrias — gold
            1: (148, 88, 168),   # Pamplona — purple
            2: (198, 108, 128),  # Marca Hispânica — pink
            3: (68, 158, 62),    # Emirato — green
        },
        border_polygon=[
            (-9.50,42.20),(-8.85,41.88),(-8.16,41.82),(-7.92,41.88),
            (-7.40,41.87),(-7.17,41.97),(-6.93,41.94),(-6.81,41.95),
            (-6.55,41.68),(-6.38,41.65),(-6.19,41.57),(-6.54,41.37),
            (-6.80,41.13),(-6.93,41.03),(-6.86,40.89),(-6.86,40.27),
            (-6.90,40.11),(-6.96,39.91),(-7.04,39.67),(-7.02,39.47),
            (-7.26,39.21),(-7.42,39.18),(-7.30,39.05),(-7.16,38.96),
            (-7.07,38.81),(-7.06,38.65),(-7.17,38.44),(-7.25,38.24),
            (-7.35,38.14),(-7.42,38.00),(-7.48,37.82),(-7.44,37.65),
            (-7.50,37.50),(-7.46,37.38),(-7.43,37.26),(-7.41,37.18),
            (-7.38,37.08),(-7.40,36.90),(-9.50,36.90),(-9.50,42.20),
        ],
        # New fields the port adds (D-13, D-14, CLAUDE.md, PREFLIGHT.md Q10)
        kingdoms=KINGDOMS,
        duchies=DUCHIES,
        condados=CONDADOS,
        rng_seed=42,
        draw_names=False,
    )
    return cfg


# D-04: factory callables (NOT pre-built configs). Phase 05 swaps for YAML loader.
REGIONS = {"iberia_868": iberia_config}


__all__ = ["REGIONS", "iberia_config"]
