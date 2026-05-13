"""Region YAML loader — Plan 05-01 (D-02, D-03, D-04, D-15).

Public API:
  load_region(key, regions_dir=None) -> RegionConfig
  clear_region_cache() -> None
  RegionConfigSchema  (pydantic BaseModel, extra='forbid')

Security guards (threat model T-05-01-01..T-05-01-03):
  - Key regex: ^[a-z0-9_]+$  (no ../ / \\ or non-ASCII)
  - yaml.safe_load only (never yaml.load) — T-05-01-02
  - Dataset paths resolved YAML-relative under {regions_dir}/{key}/;
    post-resolve .relative_to() guard rejects traversal — T-05-01-03

Cache (D-15 RESEARCH recommendation: explicit-only, no mtime):
  - _REGION_CACHE keyed by (key, str(regions_dir)) for isolation in tests
  - Cleared by clear_region_cache() only; mtime is NOT consulted.

Autogen (D-03): when kingdoms/duchies/condados all empty, synthesizes
  Condado_001..N from GeoJSON feature representative_points.
  Each condado dict carries unique original_idx (CLAUDE.md rule 4).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .contracts import ProjectDataset, RegionConfig

# ---------------------------------------------------------------------------
# Key validation
# ---------------------------------------------------------------------------

_REGION_KEY_RE = re.compile(r"^[a-z0-9_]+$")

# ---------------------------------------------------------------------------
# Module-level explicit-only cache (D-15)
# keyed by (key, str(regions_dir)) so tmp_path isolation works in tests
# ---------------------------------------------------------------------------

_REGION_CACHE: dict[tuple[str, str], RegionConfig] = {}

# Default regions_dir: repo_root/data/regions
# regions.py uses parents[4] for the same convention.
_DEFAULT_REGIONS_DIR = Path(__file__).resolve().parents[4] / "data" / "regions"


def clear_region_cache() -> None:
    """Empty the region cache. Must be called explicitly — mtime is NOT consulted."""
    _REGION_CACHE.clear()


# ---------------------------------------------------------------------------
# Pydantic schema
# ---------------------------------------------------------------------------


class DatasetSchema(BaseModel):
    """Dataset sub-schema.

    R-03: all fields optional so template-only YAMLs (e.g. england_1216)
    load through pydantic and surface as a clean FileNotFoundError
    ('template-only') instead of a ValidationError.
    """

    model_config = ConfigDict(extra="forbid")

    pt_geojson: str | None = None
    es_input: str | None = None
    mountain_river_json: str | None = None
    dem_raster: str | None = None


class RegionConfigSchema(BaseModel):
    """Pydantic mirror of RegionConfig dataclass.

    Mirrors EVERY YAML-serialisable field of RegionConfig (contracts.py).
    Excludes: lon_scale (derived in __post_init__), on_stage (Callable),
    stop_event (threading.Event) — not YAML-serialisable, runtime-only.

    D-02: extra='forbid' rejects unknown top-level keys.
    """

    model_config = ConfigDict(extra="forbid")

    # Core identity
    name: str
    display_name: str | None = None  # R-06 human-readable label

    # Map dimensions
    map_w: int = 1920
    map_h: int = 1080
    upscale: int = 2

    # Geographic bounds (WGS84) — required; no defaults (region-specific)
    lon_min: float
    lon_max: float
    lat_min: float
    lat_max: float

    # Paths
    output_dir: str = "../Assets/StreamingAssets/Maps"

    # Dataset (R-03: default_factory so missing dataset block uses all-None)
    dataset: DatasetSchema = Field(default_factory=DatasetSchema)

    # Territory routing
    border_polygon: list[list[float]] = Field(default_factory=list)
    pt_duchies: list[str] = Field(default_factory=list)

    # Rendering
    kingdom_colors: dict[str, list[int]] = Field(default_factory=dict)
    ocean_near: list[int] = Field(default_factory=lambda: [45, 90, 140])
    ocean_far: list[int] = Field(default_factory=lambda: [70, 130, 180])
    ocean_gradient_dist: float = 150.0
    coast_inner_width: int = 2
    coast_inner_color: list[int] = Field(default_factory=lambda: [15, 10, 5])

    # Cleanup thresholds
    island_min_px: int = 300
    fragment_min_px: int = 600
    blob_merge_px: int = 200
    median_passes: int = 8
    # CLAUDE.md rule 2: σ ∈ [3.0, 4.5] enforced at schema level
    smooth_sigma: float = Field(default=3.0, ge=3.0, le=4.5)

    # Mountain config
    mountain_threshold: int = 1500
    mountain_color_visual: list[int] = Field(default_factory=lambda: [118, 100, 80])
    mountain_color_lookup: list[int] = Field(default_factory=lambda: [50, 45, 40])
    mountain_noise: int = 20

    # River config
    river_color: list[int] = Field(default_factory=lambda: [74, 144, 217])
    river_width: int = 2

    # Territory data (D-03: empty arrays trigger autogen)
    kingdoms: list[dict] = Field(default_factory=list)
    duchies: list[dict] = Field(default_factory=list)
    condados: list[dict] = Field(default_factory=list)

    # Determinism + naming
    rng_seed: int = 42
    draw_names: bool = False


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------


def load_region(key: str, regions_dir: Optional[Path] = None) -> RegionConfig:
    """Load a region by key from its YAML file.

    Args:
        key: Region identifier matching ^[a-z0-9_]+$ (T-05-01-01).
        regions_dir: Directory containing {key}.yaml files.
                     Defaults to repo_root/data/regions.

    Returns:
        RegionConfig populated from YAML + resolved dataset paths.

    Raises:
        ValueError: invalid region key or dataset path traversal.
        FileNotFoundError: YAML missing, dataset files missing, or template-only.
        pydantic.ValidationError: schema violations (smooth_sigma, extra fields).
    """
    # --- T-05-01-01: key guard (before any filesystem access) ---
    if not _REGION_KEY_RE.match(key):
        raise ValueError(f"invalid region key: {key!r} (must match ^[a-z0-9_]+$)")

    rdir = Path(regions_dir) if regions_dir is not None else _DEFAULT_REGIONS_DIR
    cache_key = (key, str(rdir))

    if cache_key in _REGION_CACHE:
        return _REGION_CACHE[cache_key]

    yaml_path = rdir / f"{key}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(
            f"region YAML not found for key={key!r}: {yaml_path}"
        )

    # --- T-05-01-02: safe_load only (never yaml.load) ---
    with yaml_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    # Pydantic validation (D-02: extra='forbid', smooth_sigma range)
    model = RegionConfigSchema.model_validate(raw)

    # --- T-05-01-03: dataset path resolution + traversal guard ---
    region_root = (rdir / key).resolve()
    dataset = _resolve_dataset(model.dataset, region_root, key)

    # Build kwargs for RegionConfig
    kwargs = model.model_dump(exclude={"display_name", "dataset"})

    # Convert list→tuple for RGB fields (contracts.py uses tuple for these)
    for field_name in (
        "ocean_near", "ocean_far", "coast_inner_color",
        "mountain_color_visual", "mountain_color_lookup", "river_color",
    ):
        if isinstance(kwargs.get(field_name), list):
            kwargs[field_name] = tuple(kwargs[field_name])

    # Convert pt_duchies list→set (contracts.py: pt_duchies: set)
    kwargs["pt_duchies"] = set(kwargs.get("pt_duchies") or [])

    # Convert kingdom_colors: str keys → int keys, values list→tuple.
    # YAML emits str keys (pydantic dict[str,list[int]] contract); render.py
    # indexes with integer ki (kingdom index array), so keys must be int.
    kwargs["kingdom_colors"] = {
        int(k): tuple(v) for k, v in (kwargs.get("kingdom_colors") or {}).items()
    }

    # Autogen territories if empty (D-03)
    if not kwargs.get("condados"):
        kg_raw, du_raw, co_raw = _autogen_territories(dataset, kwargs["rng_seed"])
        # Route through same converter as explicit YAML data so voronoi.py receives
        # the expected positional-tuple format. _autogen_territories returns
        # list[dict] (same format _convert_territory_data consumes).
        # [Rule 3 - Blocker 05-10] autogen path previously set cfg.condados to
        # list[dict] directly, which crashed voronoi.py:41 (duchies.keys() on list).
        kwargs["kingdoms"], kwargs["duchies"], kwargs["condados"] = (
            _convert_territory_data(kg_raw, du_raw, co_raw)
        )
    else:
        # Convert list[dict] → the in-memory shapes expected by voronoi.py
        # (RESEARCH Pitfall 3: voronoi.py:setup_baronies indexes condados
        # positionally c[4]/c[5] and treats duchies/kingdoms as dicts)
        kwargs["kingdoms"], kwargs["duchies"], kwargs["condados"] = (
            _convert_territory_data(
                kwargs.get("kingdoms") or [],
                kwargs.get("duchies") or [],
                kwargs.get("condados") or [],
            )
        )

    kwargs["dataset"] = dataset

    cfg = RegionConfig(**kwargs)
    _REGION_CACHE[cache_key] = cfg
    return cfg


# ---------------------------------------------------------------------------
# Territory data converter (RESEARCH Pitfall 3)
# ---------------------------------------------------------------------------


def _convert_territory_data(
    kingdoms_raw: list,
    duchies_raw: list,
    condados_raw: list,
) -> tuple[dict, dict, list]:
    """Convert list[dict] territory data to the shapes voronoi.py expects.

    voronoi.py:setup_baronies accesses:
      - kingdoms  as dict[id, display_name]
      - duchies   as dict[id, (kingdom_id, display_name)]
      - condados  as list[tuple(id, name, lon, lat, duchy_id, [(barony_name, lon, lat), ...])]

    YAML/pydantic delivers list[dict] for all three. This converter bridges
    the gap so load_region output feeds voronoi.py without modification.
    """
    # kingdoms: list[{id, name}] → dict[str, str]
    kingdoms: dict[str, str] = {k["id"]: k["name"] for k in kingdoms_raw}

    # duchies: list[{id, kingdom_id, name}] → dict[str, tuple[str, str]]
    duchies: dict[str, tuple] = {
        d["id"]: (d["kingdom_id"], d["name"]) for d in duchies_raw
    }

    # condados: list[dict] → list[tuple(id, name, lon, lat, duchy_id, baronies[, original_idx])]
    # baronies: list[dict{name,lon,lat}] → list[tuple(name, lon, lat)]
    # original_idx preserved as 7th element when present (CLAUDE.md rule 4).
    # voronoi.py only accesses c[0..5] positionally — c[6] is ignored there.
    # export.py emits it conditionally so Iberia parity (no original_idx) stays green.
    condados: list = []
    for c in condados_raw:
        barony_list = c.get("baronies") or []
        barony_tuples = [
            (b["name"], float(b["lon"]), float(b["lat"])) for b in barony_list
        ]
        row: tuple
        if "original_idx" in c:
            row = (
                c["id"],
                c["name"],
                float(c["lon"]),
                float(c["lat"]),
                c["duchy_id"],
                barony_tuples,
                c["original_idx"],
            )
        else:
            row = (
                c["id"],
                c["name"],
                float(c["lon"]),
                float(c["lat"]),
                c["duchy_id"],
                barony_tuples,
            )
        condados.append(row)

    return kingdoms, duchies, condados


# ---------------------------------------------------------------------------
# Dataset path resolver
# ---------------------------------------------------------------------------


def _resolve_dataset(ds: DatasetSchema, region_root: Path, key: str) -> ProjectDataset:
    """Resolve and validate dataset paths from schema. Raises on template-only or missing files."""
    all_unset = (
        ds.pt_geojson is None
        and ds.es_input is None
        and ds.mountain_river_json is None
    )
    if all_unset:
        raise FileNotFoundError(
            f"Region {key!r} has no dataset on disk (template-only)"
        )

    def _resolve(rel: Optional[str]) -> Optional[Path]:
        if rel is None:
            return None
        resolved = (region_root / rel).resolve()
        # T-05-01-03: reject traversal outside region dir
        try:
            resolved.relative_to(region_root)
        except ValueError:
            raise ValueError(
                f"dataset path {rel!r} resolves outside region dir {region_root}"
            )
        if not resolved.exists():
            raise FileNotFoundError(
                f"Region {key!r} has no dataset on disk (template-only): "
                f"dataset file missing: {resolved}"
            )
        return resolved

    return ProjectDataset(
        pt_geojson=_resolve(ds.pt_geojson),
        es_input=_resolve(ds.es_input),
        mountain_river_json=_resolve(ds.mountain_river_json),
        dem_raster=_resolve(ds.dem_raster),
    )


# ---------------------------------------------------------------------------
# Autogen territories (D-03)
# ---------------------------------------------------------------------------


def _autogen_territories(
    dataset: ProjectDataset, rng_seed: int
) -> tuple[list, list, list]:
    """Synthesise condados from GeoJSON feature representative_points.

    D-03: when YAML has empty kingdoms/duchies/condados, derive N synthetic
    condados (Condado_001..N) from dataset GeoJSON centroids.

    Every condado dict carries:
      - id, name, original_idx (CLAUDE.md rule 4 — Nájera bug guard)
      - duchy_id: 'unnamed_duchy', kingdom_id: 'unnamed'
      - lon, lat from feature representative_point

    Deterministic: rng_seed provided but not consumed (centroid coordinates
    are deterministic from GeoJSON; seed kept for forward compatibility).

    Returns:
        (kingdoms, duchies, condados) as lists suitable for RegionConfig.
    """
    features: list[dict] = []
    # WR-01 fix (Plan 05-13): single-country YAMLs (France 1066, England 1216) point
    # both dataset.pt_geojson and dataset.es_input at the same file. Without dedupe,
    # every feature was appended twice, producing ~80 condados from a 40-feature
    # toy dataset. Path equality holds because _resolve (region_loader.py:332-360)
    # returns absolute resolved Paths stored in ProjectDataset. Iberia parity is
    # preserved: its pt_geojson != es_input, so seen_paths never elides either input.
    seen_paths: set[Path] = set()

    for geojson_path in (dataset.pt_geojson, dataset.es_input):
        if geojson_path is None or not geojson_path.exists():
            continue
        if geojson_path in seen_paths:
            continue
        seen_paths.add(geojson_path)
        try:
            data = json.loads(geojson_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        fc_features = data.get("features") or []
        for feat in fc_features:
            geom = feat.get("geometry") or {}
            geom_type = geom.get("type", "")
            coords = geom.get("coordinates")

            if geom_type == "Point" and coords:
                lon, lat = float(coords[0]), float(coords[1])
                features.append({"lon": lon, "lat": lat})
            elif geom_type in ("Polygon", "MultiPolygon") and coords:
                lon, lat = _representative_point(geom_type, coords)
                features.append({"lon": lon, "lat": lat})
            elif geom_type == "MultiPoint" and coords:
                lon, lat = float(coords[0][0]), float(coords[0][1])
                features.append({"lon": lon, "lat": lat})

    kingdoms = [{"id": "unnamed", "name": "Unnamed Kingdom", "color": [128, 128, 128]}]
    duchies = [{"id": "unnamed_duchy", "name": "Unnamed Duchy", "kingdom_id": "unnamed"}]

    condados = []
    for i, feat in enumerate(features, start=1):
        condados.append(
            {
                "id": f"condado_{i:03d}",
                "name": f"Condado_{i:03d}",
                "original_idx": i,  # CLAUDE.md rule 4
                "duchy_id": "unnamed_duchy",
                "kingdom_id": "unnamed",
                "lon": feat["lon"],
                "lat": feat["lat"],
                # One synthetic barony per condado so voronoi KD-trees have real
                # sample points. Without baronies, bars=[] → tp=te=None → blank map.
                "baronies": [
                    {"name": f"barony_{i:03d}", "lon": feat["lon"], "lat": feat["lat"]}
                ],
            }
        )

    return kingdoms, duchies, condados


def _representative_point(geom_type: str, coords: list) -> tuple[float, float]:
    """Return a representative lon/lat for a Polygon or MultiPolygon."""
    if geom_type == "Polygon":
        ring = coords[0]  # outer ring
        lons = [c[0] for c in ring]
        lats = [c[1] for c in ring]
        return sum(lons) / len(lons), sum(lats) / len(lats)
    else:  # MultiPolygon
        # Use centroid of first polygon's outer ring
        ring = coords[0][0]
        lons = [c[0] for c in ring]
        lats = [c[1] for c in ring]
        return sum(lons) / len(lons), sum(lats) / len(lats)


__all__ = [
    "load_region",
    "clear_region_cache",
    "RegionConfigSchema",
]
