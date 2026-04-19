"""GEN-01..04: wrapper around medieval_forge.lib.map_generator.

D-04: map_generator is treated as a vendored black box. We do NOT modify it.
D-05: synchronous pipeline runs in asyncio.to_thread.
Pitfall 6 mitigation: territory data is injected via sys.modules patching
                       before generate_maps invokes load_territory_data.

Reload mitigation: load_territory_data calls importlib.reload(mod) after
import_module. For a synthetic module (no file on disk), _find_spec returns
None and reload raises ModuleNotFoundError. We patch importlib.reload in the
map_generator module's own namespace for the duration of the pipeline call so
that reload on our synthetic module is a no-op. Real modules are unaffected.
"""
from __future__ import annotations

import asyncio
import importlib
import io
import logging
import shutil
import sys
import types
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from typing import Any

from ..lib import map_generator
from .paths import ensure_project_dirs

logger = logging.getLogger(__name__)

# Files map_generator produces (per RESEARCH Critical Integration section).
_GENERATOR_OUTPUTS: tuple[str, ...] = (
    "visual_condado.png",
    "visual_barony.png",
    "lookup_condado.png",
    "lookup_barony.png",
    "lookup_condado_colors.json",
    "lookup_barony_colors.json",
    "territory_metadata.json",
    "mountains_mask.png",
    "terrain_lookup.png",
    "terrain_types.json",
)

# Aliases the UI uses for headline previews (GEN-02). Each alias is a copy
# of one of the generator outputs, written post-generation under a stable name.
# terrain.png now aliases terrain_lookup.png (the real per-pixel terrain type map).
# Previously it aliased mountains_mask.png which produced an all-black placeholder
# when no mountain data was configured — Bug B fix.
_PREVIEW_ALIASES: dict[str, str] = {
    "terrain.png": "terrain_lookup.png",
    "territories.png": "visual_condado.png",
    "borders.png": "lookup_condado.png",
}

# Ficheiros adicionais gerados por outros renderizadores (ex: render_modern)
_AUXILIARY_OUTPUTS: tuple[str, ...] = (
    "modern_map.png",
    "modern_map_colors.json",
)

GENERATED_FILE_WHITELIST: frozenset[str] = frozenset(
    list(_GENERATOR_OUTPUTS)
    + list(_PREVIEW_ALIASES.keys())
    + list(_AUXILIARY_OUTPUTS)
    + [
        "territories.geojson",
        "baronies.geojson",
        # CANVAS-01 / plan 02-04 sidecars for the frontend (D-04 preserved:
        # the Unity-consumed lookup_*_colors.json files keep their original
        # {"r,g,b": idx} shape; these sidecars are {id: "#rrggbb"}).
        "condado_colors.json",
        "barony_colors.json",
    ]
)


def _inject_territory_module(name: str, data: dict[str, Any]) -> types.ModuleType:
    """Create a synthetic module with KINGDOMS/DUCHIES/CONDADOS and register in sys.modules."""
    mod = types.ModuleType(name)
    mod.KINGDOMS = data.get("kingdoms", {})
    mod.DUCHIES = data.get("duchies", {})
    mod.CONDADOS = data.get("condados", [])
    sys.modules[name] = mod
    return mod


def _cleanup_territory_module(name: str) -> None:
    sys.modules.pop(name, None)


@contextmanager
def _patch_reload_for_synthetic(synthetic_module_name: str):
    """Patch importlib.reload in map_generator's namespace to be a no-op for
    our synthetic module only.

    load_territory_data does:
        mod = importlib.import_module(name)
        importlib.reload(mod)

    For a synthetic module (no backing .py file), Python's reload calls
    _bootstrap._find_spec which returns None, raising ModuleNotFoundError.
    We intercept reload *only* for our synthetic module; real modules are
    reloaded normally.
    """
    _real_reload = importlib.reload

    def _safe_reload(module: types.ModuleType) -> types.ModuleType:
        if getattr(module, "__name__", None) == synthetic_module_name:
            return module  # no-op for our synthetic module
        return _real_reload(module)

    # Patch in map_generator's importlib reference (the module uses
    # `import importlib` at the top, so we patch via its module dict).
    import importlib as _importlib_mod
    _importlib_mod.reload = _safe_reload  # type: ignore[method-assign]
    try:
        yield
    finally:
        _importlib_mod.reload = _real_reload  # type: ignore[method-assign]


def _cleanup_territory_module(name: str) -> None:
    sys.modules.pop(name, None)


def _compute_padded_bbox(
    config: dict[str, Any],
    padding_pct: float = 0.05,
) -> dict[str, float]:
    """Compute a render bbox that:

    1. Covers all territory centroid coordinates from territory_data (so no
       condado/barony falls outside the canvas).
    2. Adds a symmetric padding margin (default 5 %) around that envelope so
       the territory is framed by a thin border of visible ocean — tight enough
       that the peninsula fills the viewport without a dominant ocean halo.

    If the caller already supplied explicit lon/lat bounds in *config* AND
    those bounds already encompass every centroid, they are respected as-is
    (after padding expansion if needed).  The project-level bbox is used only
    as a *starting* hint, never as a hard ceiling.
    """
    td = config.get("territory_data") or {}
    condados: list = td.get("condados", [])

    # Collect all centroid coordinates from condados and baronies.
    lons: list[float] = []
    lats: list[float] = []
    for c in condados:
        # condado tuple: (id, name, lon, lat, duchy_id, [(barony, lon, lat), ...])
        if isinstance(c, (list, tuple)) and len(c) >= 4:
            lons.append(float(c[2]))
            lats.append(float(c[3]))
            for b in (c[5] if len(c) > 5 else []):
                if isinstance(b, (list, tuple)) and len(b) >= 3:
                    lons.append(float(b[1]))
                    lats.append(float(b[2]))

    # Determine the caller-supplied bbox (may come from project.bbox_* via the
    # API layer, or from generator_config overrides).
    cfg_lon_min = config.get("lon_min")
    cfg_lon_max = config.get("lon_max")
    cfg_lat_min = config.get("lat_min")
    cfg_lat_max = config.get("lat_max")

    if lons and lats:
        data_lon_min = min(lons)
        data_lon_max = max(lons)
        data_lat_min = min(lats)
        data_lat_max = max(lats)

        # Expand the caller-supplied bbox to contain all centroids.
        lon_min = min(cfg_lon_min, data_lon_min) if cfg_lon_min is not None else data_lon_min
        lon_max = max(cfg_lon_max, data_lon_max) if cfg_lon_max is not None else data_lon_max
        lat_min = min(cfg_lat_min, data_lat_min) if cfg_lat_min is not None else data_lat_min
        lat_max = max(cfg_lat_max, data_lat_max) if cfg_lat_max is not None else data_lat_max
    else:
        # No territory data — fall back to caller-supplied values (may be None,
        # in which case RegionConfig defaults apply).
        return {}

    # Apply symmetric padding so there is visible ocean around the territory.
    lon_span = lon_max - lon_min
    lat_span = lat_max - lat_min
    pad_lon = lon_span * padding_pct
    pad_lat = lat_span * padding_pct

    return {
        "lon_min": lon_min - pad_lon,
        "lon_max": lon_max + pad_lon,
        "lat_min": lat_min - pad_lat,
        "lat_max": lat_max + pad_lat,
    }


# Hardcoded PT/ES border polygon (same as map_generator.iberia_config).
# Used as fallback when caller does not supply border_polygon in config.
# Points define the Portuguese side (west); municipalities whose centroid
# falls inside this polygon are routed to the PT rasterisation path.
_IBERIA_PT_BORDER: list[tuple[float, float]] = [
    (-9.50, 42.20), (-8.85, 41.88), (-8.16, 41.82), (-7.92, 41.88),
    (-7.40, 41.87), (-7.17, 41.97), (-6.93, 41.94), (-6.81, 41.95),
    (-6.55, 41.68), (-6.38, 41.65), (-6.19, 41.57), (-6.54, 41.37),
    (-6.80, 41.13), (-6.93, 41.03), (-6.86, 40.89), (-6.86, 40.27),
    (-6.90, 40.11), (-6.96, 39.91), (-7.04, 39.67), (-7.02, 39.47),
    (-7.26, 39.21), (-7.42, 39.18), (-7.30, 39.05), (-7.16, 38.96),
    (-7.07, 38.81), (-7.06, 38.65), (-7.17, 38.44), (-7.25, 38.24),
    (-7.35, 38.14), (-7.42, 38.00), (-7.48, 37.82), (-7.44, 37.65),
    (-7.50, 37.50), (-7.46, 37.38), (-7.43, 37.26), (-7.41, 37.18),
    (-7.38, 37.08), (-7.40, 36.90), (-9.50, 36.90), (-9.50, 42.20),
]


def _geojson_centroid(feature: dict[str, Any]) -> tuple[float, float] | None:
    """Return (lon, lat) representative centroid for a GeoJSON feature.

    Uses the arithmetic mean of the outer ring vertices — fast and sufficient
    for the PT/ES classification task (no need for shapely here).
    """
    geom = feature.get("geometry") or {}
    gt = geom.get("type", "")
    coords = geom.get("coordinates")
    if not coords:
        return None
    try:
        if gt == "Polygon":
            ring = coords[0]
        elif gt == "MultiPolygon":
            # Largest polygon by vertex count
            ring = max((p[0] for p in coords), key=len)
        else:
            return None
        if not ring:
            return None
        lon = sum(c[0] for c in ring) / len(ring)
        lat = sum(c[1] for c in ring) / len(ring)
        return lon, lat
    except Exception:
        return None


def _point_in_polygon(lon: float, lat: float, polygon: list) -> bool:
    """Ray-casting point-in-polygon (mirrors map_generator.point_in_polygon)."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _geojson_to_topojson(features: list[dict[str, Any]]) -> dict[str, Any]:
    """Convert a list of GeoJSON Polygon/MultiPolygon features to minimal TopoJSON.

    Uses identity transform (scale=[1,1], translate=[0,0]) so arc coordinates
    are plain lon/lat values encoded as delta sequences, which
    decode_topojson_municipalities in map_generator can parse correctly.

    Each polygon ring becomes one arc (arc sharing is not required by the
    decoder). The resulting structure matches what decode_topojson_municipalities
    expects: topo['objects']['municipalities']['geometries'][i] with type
    Polygon/MultiPolygon and arcs referencing topo['arcs'].
    """
    arcs: list[list[list[float]]] = []
    geometries: list[dict[str, Any]] = []

    def _ring_to_arc(ring: list) -> int:
        """Encode one ring as a delta arc, append to arcs[], return arc index."""
        deltas: list[list[float]] = []
        prev_x, prev_y = 0.0, 0.0
        for pt in ring:
            dx = pt[0] - prev_x
            dy = pt[1] - prev_y
            deltas.append([dx, dy])
            prev_x, prev_y = pt[0], pt[1]
        arcs.append(deltas)
        return len(arcs) - 1

    for feat in features:
        geom = feat.get("geometry") or {}
        gt = geom.get("type", "")
        coords = geom.get("coordinates")
        if not coords:
            continue
        if gt == "Polygon":
            arc_refs = [[_ring_to_arc(ring)] for ring in coords if ring]
            if arc_refs:
                geometries.append({"type": "Polygon", "arcs": arc_refs})
        elif gt == "MultiPolygon":
            # TopoJSON MultiPolygon arcs: [polygon1_rings, polygon2_rings, ...]
            # Each polygon_rings: [[ring1_arc_idx, ...], [ring2_arc_idx, ...], ...]
            # Each ring uses a single arc here (one arc per ring, no arc sharing).
            # So: [[[arc0]], [[arc1]], ...]  — one polygon per sub-list, one ring
            # per inner list, one arc index in the innermost list.
            arc_refs = [
                [[_ring_to_arc(ring)] for ring in poly if ring]
                for poly in coords
            ]
            arc_refs = [r for r in arc_refs if r]
            if arc_refs:
                geometries.append({"type": "MultiPolygon", "arcs": arc_refs})

    return {
        "type": "Topology",
        "transform": {"scale": [1.0, 1.0], "translate": [0.0, 0.0]},
        "arcs": arcs,
        "objects": {
            "municipalities": {
                "type": "GeometryCollection",
                "geometries": geometries,
            }
        },
    }


def _split_municipalities_pt_es(
    raw_geojson: Path,
    generated_dir: Path,
    border_polygon: list | None,
) -> tuple[Path, Path] | None:
    """Split municipalities.geojson into PT and ES subsets.

    Uses border_polygon to classify each feature by its centroid.
    Features inside the polygon → PT GeoJSON.
    Features outside → ES TopoJSON (format expected by map_generator).

    Returns (pt_path, es_path) or None if no border_polygon is available.

    Raises ValueError if either split is empty (safety guard against
    silently reintroducing a zero-ES or zero-PT configuration).
    """
    import json as _json

    polygon = border_polygon if border_polygon else _IBERIA_PT_BORDER
    if not polygon:
        logger.warning(
            "split_municipalities: no border_polygon available — "
            "skipping PT/ES split, all municipalities go to PT path"
        )
        return None

    with raw_geojson.open(encoding="utf-8") as f:
        fc = _json.load(f)

    all_features: list[dict[str, Any]] = fc.get("features", [])
    pt_features: list[dict[str, Any]] = []
    es_features: list[dict[str, Any]] = []

    for feat in all_features:
        centroid = _geojson_centroid(feat)
        if centroid is None:
            # No geometry — keep on PT side (safe default, will be filtered later)
            pt_features.append(feat)
            continue
        lon, lat = centroid
        if _point_in_polygon(lon, lat, polygon):
            pt_features.append(feat)
        else:
            es_features.append(feat)

    logger.info(
        "split_municipalities: %d total → %d PT, %d ES",
        len(all_features), len(pt_features), len(es_features),
    )

    if len(pt_features) == 0:
        raise ValueError(
            f"split_municipalities: PT bucket is empty after split "
            f"({len(all_features)} total features). "
            "Check border_polygon — all features landed on the ES side."
        )
    if len(es_features) == 0:
        raise ValueError(
            f"split_municipalities: ES bucket is empty after split "
            f"({len(all_features)} total features). "
            "Check border_polygon — all features landed on the PT side. "
            "This would reintroduce the ghost-condado bug."
        )

    pt_path = generated_dir / "pt_municipalities.geojson"
    es_path = generated_dir / "es_municipalities_topo.json"

    pt_fc = {"type": "FeatureCollection", "features": pt_features}
    pt_path.write_text(_json.dumps(pt_fc, ensure_ascii=False), encoding="utf-8")

    es_topo = _geojson_to_topojson(es_features)
    es_path.write_text(_json.dumps(es_topo, ensure_ascii=False), encoding="utf-8")

    logger.info(
        "split_municipalities: wrote %s (%d features) and %s (%d geometries)",
        pt_path.name, len(pt_features),
        es_path.name, len(es_topo["objects"]["municipalities"]["geometries"]),
    )
    return pt_path, es_path


def _build_region_config(generated_dir: Path, config: dict[str, Any]) -> Any:
    """Construct a RegionConfig from caller-supplied overrides, defaulting output_dir.

    Bbox handling (in order of precedence):
      1. Explicit lon/lat fields in *config* (caller override) — used as the
         *minimum* canvas; may be expanded to fit all territory centroids.
      2. Auto-expansion to cover all condado/barony centroids in territory_data.
      3. 5 % ocean-framing padding added around the expanded envelope.

    Se existir municipalities.geojson ingerido no projeto, aponta automaticamente
    municipality_pt_geojson para esse arquivo — necessário para construir a land mask.
    """
    valid_fields = set(map_generator.RegionConfig.__dataclass_fields__.keys())

    # Compute padded bbox that covers all territory centroids.
    padded = _compute_padded_bbox(config)

    kwargs: dict[str, Any] = {"output_dir": str(generated_dir)}

    # Start with padded bbox so it can be overridden below only if the caller
    # explicitly supplied tighter/different bounds AND we want to respect them.
    # Actually we ALWAYS want the padded bbox to win (it already incorporates
    # the caller's values as a minimum envelope), so apply it first.
    kwargs.update(padded)

    # Apply all other valid RegionConfig fields from config (skip bbox keys —
    # they were already handled above via padded bbox logic).
    _bbox_keys = {"lon_min", "lon_max", "lat_min", "lat_max"}
    for k, v in config.items():
        if k in valid_fields and k not in _bbox_keys and k != "output_dir":
            kwargs[k] = v

    # Apontar municipality_pt_geojson para o GeoJSON ingerido se não foi
    # fornecido explicitamente e o arquivo existir.
    # Se municipality_es_topojson também não estiver definido, faz o split
    # PT/ES do GeoJSON completo antes de injectar nos caminhos — corrige o bug
    # de "ghost condados" onde municípios espanhóis eram rasterizados via KD-tree
    # PT em vez do ES (root cause: generator enviava o GeoJSON completo apenas para
    # municipality_pt_geojson; municipality_es_topojson ficava None → es_municipalities=[]).
    if "municipality_pt_geojson" not in kwargs:
        raw_geojson = generated_dir.parent / "raw" / "municipalities.geojson"
        if raw_geojson.exists():
            if "municipality_es_topojson" not in kwargs:
                _split_result = _split_municipalities_pt_es(
                    raw_geojson, generated_dir, kwargs.get("border_polygon")
                )
                if _split_result is not None:
                    pt_path, es_path = _split_result
                    kwargs["municipality_pt_geojson"] = str(pt_path)
                    kwargs["municipality_es_topojson"] = str(es_path)
                else:
                    # Fall back to original behaviour (no border_polygon available)
                    kwargs["municipality_pt_geojson"] = str(raw_geojson)
            else:
                kwargs["municipality_pt_geojson"] = str(raw_geojson)

    # Wire bundled mountain/river data for templates that ship it.
    # The Iberia template ships mountain_river_data_iberia.json alongside
    # territory_iberia.json in the services/ package directory.
    # If the caller has not explicitly set mountain_river_json, resolve it
    # from the bundled file so render_mountains() has real geographic polygon
    # data to work with. (render_rivers is disconnected from the pipeline but
    # its function and data are preserved for future reactivation.)
    if "mountain_river_json" not in kwargs:
        _bundled = Path(__file__).parent / "mountain_river_data_iberia.json"
        if _bundled.exists():
            kwargs["mountain_river_json"] = str(_bundled)

    return map_generator.RegionConfig(**kwargs)


def _materialise_aliases(generated_dir: Path) -> None:
    """Copy underlying generator outputs to their alias names (terrain.png etc).

    terrain_lookup.png is always generated by the pipeline (no mountain data
    dependency), so no black placeholder is needed for terrain.png any more.
    For other aliases, if the source does not exist the alias is simply skipped.
    """
    for alias, source_name in _PREVIEW_ALIASES.items():
        source = generated_dir / source_name
        target = generated_dir / alias
        if source.exists():
            shutil.copyfile(source, target)


def _validate_municipalities(raw_geojson_path: Path) -> None:
    """Verifica se o GeoJSON contém polígonos suficientes para gerar o mapa.

    Lança ValueError com mensagem amigável se os dados forem inadequados.
    """
    import json as _json
    if not raw_geojson_path.exists():
        raise ValueError(
            "Nenhum dado geográfico encontrado.\n"
            "Execute 'Ingerir via OSM' antes de gerar o mapa."
        )
    with raw_geojson_path.open(encoding="utf-8") as f:
        data = _json.load(f)
    features = data.get("features", [])
    if not features:
        raise ValueError(
            "O arquivo de municípios está vazio.\n"
            "Execute 'Ingerir via OSM' novamente."
        )
    polygon_types = {"Polygon", "MultiPolygon"}
    n_polygons = sum(
        1 for feat in features
        if feat.get("geometry", {}).get("type") in polygon_types
    )
    n_points = len(features) - n_polygons
    if n_polygons == 0:
        raise ValueError(
            f"Os dados ingeridos contêm apenas {n_points} pontos (centroides do Wikidata) "
            "e nenhum polígono de fronteira.\n"
            "O gerador precisa de polígonos para construir a máscara de terra — "
            "o resultado seria um ecrã azul (oceano).\n\n"
            "Solução: execute 'Ingerir via OSM' (botão 1b) para obter dados com polígonos reais."
        )
    logger.info(
        "municipalities validation OK: %d polygons, %d points", n_polygons, n_points
    )


def _run_pipeline_sync(
    project_id: str,
    generated_dir: Path,
    config: dict[str, Any],
) -> dict[str, str]:
    territory_data = config.get("territory_data")
    if not isinstance(territory_data, dict):
        raise ValueError(
            "config['territory_data'] must be a dict with keys {kingdoms, duchies, condados}"
        )
    # Validar dados geográficos ANTES de iniciar o pipeline
    raw_geojson = generated_dir.parent / "raw" / "municipalities.geojson"
    _validate_municipalities(raw_geojson)

    module_name = f"_mf_territory_{project_id.replace('-', '_')}"
    _inject_territory_module(module_name, territory_data)
    try:
        region_cfg = _build_region_config(generated_dir, config)
        # Redirect map_generator's progress prints to a UTF-8 StringIO buffer.
        # map_generator uses Unicode characters (→, —) in its print statements
        # that fail on Windows cp1252 console encoding when running as a
        # background thread. The captured output is logged at DEBUG level.
        _buf = io.StringIO()
        with _patch_reload_for_synthetic(module_name), redirect_stdout(_buf):
            map_generator.generate_maps(
                region_cfg,
                territory_module=module_name,
                draw_names=False,
            )
        logger.debug("map_generator output for %s:\n%s", project_id, _buf.getvalue())
        _materialise_aliases(generated_dir)
        # CANVAS-01 + D-02: build GeoJSON artifacts by reading back the generator's
        # lookup PNGs + territory_metadata.json from disk. Keeps inicio/map_generator.py
        # as an untouched black box (D-04 in this module's docstring).
        import math as _math
        from .territories_geojson import emit_territories_from_disk, _ProjCfg
        from .baronies_geojson import emit_baronies_from_disk
        _center_lat = (region_cfg.lat_min + region_cfg.lat_max) / 2
        _lon_scale = region_cfg.lon_scale if region_cfg.lon_scale is not None else _math.cos(_math.radians(_center_lat))
        cfg_shim = _ProjCfg(
            lon_min=region_cfg.lon_min, lon_max=region_cfg.lon_max,
            lat_min=region_cfg.lat_min, lat_max=region_cfg.lat_max,
            map_w=region_cfg.map_w,     map_h=region_cfg.map_h,
            upscale=region_cfg.upscale, lon_scale=_lon_scale,
        )
        # CANVAS-01 + D-02 (plan 02-04): emission must succeed or the whole
        # generation fails. Previously this was wrapped in try/except that
        # swallowed the format-mismatch crash from G-01 for days. Any
        # exception here propagates to run_generation, which lets
        # api/generate.py's background task set status='error_generating'
        # with last_error. (G-02: no silent swallow.)
        # Pass the FULL original condados list (all entries, including those with
        # 0 pixels) so emit_territories_from_disk can remap generate_lookup_map's
        # ORIGINAL indices to the METADATA positions that build_territories_geojson
        # expects.  Without this, surviving condados whose original index >= number
        # of survivors are silently lost (Problem B root cause).
        _original_condados = territory_data.get("condados", [])
        emit_territories_from_disk(
            project_id, generated_dir, cfg_shim,
            original_condados=_original_condados,
        )
        emit_baronies_from_disk(project_id, generated_dir, cfg_shim)
    finally:
        _cleanup_territory_module(module_name)

    manifest: dict[str, str] = {}
    for fname in GENERATED_FILE_WHITELIST:
        p = generated_dir / fname
        if p.exists():
            manifest[fname] = f"generated/{fname}"
    return manifest


async def run_generation(project_id: str, config: dict[str, Any]) -> dict[str, str]:
    """Async entry point. Schedules the synchronous pipeline in a thread.

    Returns a manifest of {filename: relative_path}. Caller is responsible for
    updating project.status (the api layer does this).
    """
    dirs = ensure_project_dirs(project_id)
    generated_dir = dirs["generated"]
    logger.info("starting generation for %s into %s", project_id, generated_dir)
    manifest = await asyncio.to_thread(
        _run_pipeline_sync, project_id, generated_dir, config
    )
    logger.info("generation done for %s: %d files", project_id, len(manifest))
    return manifest
