"""CANVAS-01 data dependency: emit territories.geojson with per-condado
polygon + neighbors adjacency.

VENDORED BLACK BOX CONSTRAINT: inicio/map_generator.py is not modified.
This module runs AFTER generate_maps() has written its files to disk and
reconstructs the condado raster from lookup_condado.png + lookup_condado_colors.json.

T-PATH: project_id is validated via paths.project_dir() (ValueError on bad UUID).
V5 input validation: filename 'territories.geojson' is appended to
GENERATED_FILE_WHITELIST in generator.py; the existing /preview/{filename}
route handles the actual serving — no new route is introduced.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import rasterio.features
from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

from .paths import project_dir

logger = logging.getLogger(__name__)


class _ProjCfg:
    """Minimal cfg-like shim holding the fields we need for lon/lat inversion.
    Populated from territory_metadata.json + lookup_condado.png shape.
    """
    __slots__ = ("lon_min", "lon_max", "lat_min", "lat_max", "map_w", "map_h", "upscale", "lon_scale")

    def __init__(self, lon_min, lon_max, lat_min, lat_max, map_w, map_h, upscale, lon_scale):
        self.lon_min = lon_min
        self.lon_max = lon_max
        self.lat_min = lat_min
        self.lat_max = lat_max
        self.map_w = map_w
        self.map_h = map_h
        self.upscale = upscale
        self.lon_scale = lon_scale


def pixel_polygon_to_lonlat(geom: dict, cfg: _ProjCfg, W: int, H: int) -> dict:
    """Apply the inverse of map_generator.geo_to_pixel to every vertex.

    W and H must be the actual pixel dimensions of the raster array that
    rasterio.features.shapes was run on (i.e. pc.shape[1] and pc.shape[0]).
    These come from lookup_condado.png / lookup_barony.png which are written at
    map_w × map_h (NOT map_w*upscale × map_h*upscale) by map_generator.py.
    Do NOT substitute cfg.map_w * cfg.upscale here — that is the upscaled
    terrain resolution, not the lookup raster resolution.
    """
    span = (cfg.lon_max - cfg.lon_min) * cfg.lon_scale

    def px_to_lonlat(px: float, py: float) -> tuple[float, float]:
        lon = px / W * span / cfg.lon_scale + cfg.lon_min
        lat = cfg.lat_max - py / H * (cfg.lat_max - cfg.lat_min)
        return (lon, lat)

    def ring(coords):
        return [list(px_to_lonlat(x, y)) for x, y in coords]

    if geom["type"] == "Polygon":
        return {"type": "Polygon", "coordinates": [ring(r) for r in geom["coordinates"]]}
    if geom["type"] == "MultiPolygon":
        return {
            "type": "MultiPolygon",
            "coordinates": [[ring(r) for r in poly] for poly in geom["coordinates"]],
        }
    raise ValueError(f"unsupported geometry type: {geom['type']}")


def build_territories_geojson(
    project_id: str,
    pc: np.ndarray,
    condados: list[list[Any]],
    cfg: _ProjCfg,
) -> Path:
    """Write territories.geojson with per-condado polygon + neighbors."""
    out_dir = project_dir(project_id) / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)

    pc32 = pc.astype(np.int32)
    pc_H, pc_W = pc32.shape  # actual raster dims — lookup PNG is map_w × map_h (NOT upscaled)
    shapes_per_idx: dict[int, list] = {}
    for geom, idx in rasterio.features.shapes(pc32, mask=(pc32 >= 0)):
        i = int(idx)
        shapes_per_idx.setdefault(i, []).append(shape(geom))

    features: list[dict] = []
    unioned: dict[int, Any] = {}
    for ci, c in enumerate(condados):
        geoms = shapes_per_idx.get(ci, [])
        if not geoms:
            continue
        u = unary_union(geoms)
        unioned[ci] = u
        lonlat_geojson = pixel_polygon_to_lonlat(mapping(u), cfg, pc_W, pc_H)
        features.append({
            "type": "Feature",
            "id": c[0],
            "geometry": lonlat_geojson,
            "properties": {"id": c[0], "name": c[1], "neighbors": []},
        })

    idx_to_id = {ci: condados[ci][0] for ci in unioned}
    id_to_ci = {v: k for k, v in idx_to_id.items()}
    tree_geoms = list(unioned.values())
    tree = STRtree(tree_geoms)
    ci_by_geom_idx = list(unioned.keys())

    for feat in features:
        ci = id_to_ci[feat["id"]]
        g = unioned[ci]
        neigh_ids: set[str] = set()
        for qi in tree.query(g):
            other_ci = ci_by_geom_idx[qi]
            if other_ci == ci:
                continue
            if g.touches(unioned[other_ci]):
                neigh_ids.add(idx_to_id[other_ci])
        feat["properties"]["neighbors"] = sorted(neigh_ids)

    # quick-260426-pcy soft-assertion: every metadata condado MUST have a
    # corresponding feature in the geojson we are about to write. The previous
    # silent drop (Problem B + the H1 fallback skip) hid 12 missing condados
    # for an entire UAT round. We log loudly on any future regression so the
    # symptom is visible without raising — legitimate generation failures
    # (degenerate geom, unrecoverable upstream error) still produce a usable
    # file, but the orphan list shows up in the server log.
    meta_ids = {c[0] for c in condados}
    feat_ids = {f["id"] for f in features}
    missing = meta_ids - feat_ids
    if missing:
        logger.error(
            "territories.geojson MISSING %d condados from metadata: %s",
            len(missing), sorted(missing)[:10],
        )

    out_path = out_dir / "territories.geojson"
    out_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
        encoding="utf-8",
    )
    return out_path


def emit_territories_from_disk(
    project_id: str,
    generated_dir: Path,
    cfg: _ProjCfg,
    original_condados: list[list[Any]] | None = None,
) -> Path:
    """Read-back orchestrator. Parses the REAL map_generator lookup format
    ``{"r,g,b": idx}`` (see lib/map_generator.py SECTION 10, generate_lookup_map).
    DO NOT change to hex parsing — that schema does not exist on disk.

    Emits two artifacts:
      * ``territories.geojson`` (existing contract, via build_territories_geojson)
      * ``condado_colors.json`` sidecar — ``{condado_id: "#rrggbb"}`` for the
        frontend. The Unity-consumed ``lookup_condado_colors.json`` stays
        untouched (D-04 black-box preserved).

    ``original_condados`` — the FULL condados list as passed to map_generator
    (all entries including those with 0 pixels, in original order). When
    supplied, the pixel values written by generate_lookup_map (which are
    ORIGINAL condado indices, 0..n-1 across the full list) are correctly
    remapped to the METADATA position (0..survivors-1) that
    build_territories_geojson expects.  Without this remapping any surviving
    condado whose original index >= number-of-survivors is silently lost
    (Problem B root cause).

    If ``original_condados`` is None the function falls back to the legacy
    identity mapping (orig_idx == meta_ci), which is correct only when no
    condados were dropped — safe for the existing unit-test scenarios where
    every painted color maps to a consecutive metadata entry.
    """
    meta = json.loads((generated_dir / "territory_metadata.json").read_text(encoding='utf-8'))
    condados_meta = meta["condados"]  # list of dicts per export_metadata
    # Rehydrate the tuple/list shape build_territories_geojson expects:
    # [id, name, lon, lat, duchy, baronies]
    condados = [
        [c["id"], c["name"], c["lon"], c["lat"], c.get("duchy", ""), c.get("baronies", [])]
        for c in condados_meta
    ]
    colors_raw = json.loads((generated_dir / "lookup_condado_colors.json").read_text(encoding='utf-8'))

    # Build orig_idx → meta_ci mapping when the full original list is available.
    # generate_lookup_map() writes color_map[rgb] = i where i iterates range(n_total)
    # (ORIGINAL index).  export_metadata() re-indexes survivors as 0..len(survivors)-1
    # (METADATA position).  Without this remap, survivors at orig_idx >= n_survivors
    # are silently lost because build_territories_geojson enumerates condados_meta
    # (0..n_survivors-1) and calls shapes_per_idx.get(ci) — never reaching the
    # higher original indices stored in pc.
    orig_to_meta: dict[int, int] | None = None
    if original_condados is not None:
        # Map each surviving condado's id to its metadata position.
        id_to_meta_ci: dict[str, int] = {c["id"]: ci for ci, c in enumerate(condados_meta)}
        orig_to_meta = {}
        for orig_idx, orig_c in enumerate(original_condados):
            # original_condados entries are [id, name, lon, lat, duchy, baronies]
            orig_id = orig_c[0]
            meta_ci = id_to_meta_ci.get(orig_id)
            if meta_ci is not None:
                orig_to_meta[orig_idx] = meta_ci
        logger.debug(
            "emit_territories_from_disk: orig_to_meta built for %d survivors "
            "out of %d original condados",
            len(orig_to_meta), len(original_condados),
        )

    from PIL import Image
    img = np.array(Image.open(generated_dir / "lookup_condado.png").convert("RGB"))
    H, W, _ = img.shape
    pc = np.full((H, W), -1, dtype=np.int32)

    sidecar: dict[str, str] = {}
    for rgb_key, idx_val in colors_raw.items():
        parts = rgb_key.split(",")
        if len(parts) != 3:
            raise ValueError(
                f"lookup_condado_colors.json malformed key {rgb_key!r}; expected 'r,g,b'"
            )
        r, g, b = (int(p) for p in parts)
        orig_idx = int(idx_val)

        if orig_to_meta is not None:
            # Remap original index to metadata position.
            meta_ci = orig_to_meta.get(orig_idx)
            if meta_ci is None:
                # This condado was dropped by map_generator (0 pixels) — skip.
                logger.debug(
                    "emit_territories_from_disk: orig_idx %d has no metadata entry "
                    "(dropped by map_generator) — skipping color %s",
                    orig_idx, rgb_key,
                )
                continue
            pixel_val = meta_ci
            condado_id = condados[meta_ci][0]
        else:
            # Legacy identity mapping: orig_idx == meta_ci (safe only when no
            # drops occurred upstream).  quick-260426-pcy: this path used to
            # silently skip orig_idx >= len(condados) — the exact failure mode
            # that produced 12 orphans (alcacer/beja/braga/braganca/chaves/
            # evora/lamego/porto/salamanca/santarem/tui/viana) on project
            # 2d402c81 because original_condados was None at generation time.
            # Silent skip turned into hard failure: any caller that omits
            # original_condados AND has out-of-range orig_idx values is hitting
            # the Problem B bug and must pass the full list (production call
            # site at services/generator.py:361 already does this).
            idx = orig_idx
            if idx < 0 or idx >= len(condados):
                raise ValueError(
                    f"lookup_condado_colors.json idx {idx} out of range "
                    f"(len(condados)={len(condados)}). emit_territories_from_disk "
                    f"was called without original_condados, so the legacy "
                    f"identity mapping (orig_idx == meta_ci) is in effect — but "
                    f"map_generator emitted an idx that does not fit. "
                    f"Pass original_condados to remap correctly."
                )
            pixel_val = idx
            condado_id = condados[idx][0]

        mask = (img[:, :, 0] == r) & (img[:, :, 1] == g) & (img[:, :, 2] == b)
        pc[mask] = pixel_val
        # Build sidecar: condado id -> #rrggbb (for frontend fills)
        sidecar[condado_id] = f"#{r:02x}{g:02x}{b:02x}"

    (generated_dir / "condado_colors.json").write_text(
        json.dumps(sidecar, ensure_ascii=False),
        encoding="utf-8",
    )
    return build_territories_geojson(project_id, pc, condados, cfg)


# ---------------------------------------------------------------------------
# Edit-layer helpers: load/save territories as an indexed dict
# ---------------------------------------------------------------------------

async def load_territories(project_id: str) -> dict[str, dict]:
    """Load territories.geojson and return a dict indexed by condado id.

    Each value is a flat dict: {id, name, geometry (GeoJSON), lon, lat,
    neighbors, ...} suitable for O(1) lookup in edit endpoints.

    Returns an empty dict if territories.geojson does not exist (e.g. during
    testing with no pre-generated project data, or for non-UUID project ids
    used in unit tests).

    T-PATH: project_dir() raises ValueError on invalid UUIDs; that ValueError
    propagates to the caller (FastAPI converts it to a 500 unless the caller
    catches it). Edit endpoints catch ValueError at the service-call level —
    this is intentional so tests with non-UUID project_id receive a graceful
    empty dict rather than a 500.
    """
    try:
        from .paths import project_dir
        geojson_path = project_dir(project_id) / "generated" / "territories.geojson"
    except ValueError:
        # Non-UUID project_id (e.g. test fixtures): return empty dict
        return {}

    if not geojson_path.exists():
        return {}

    raw = json.loads(geojson_path.read_text(encoding="utf-8"))
    result: dict[str, dict] = {}
    for feature in raw.get("features", []):
        cid = feature.get("id") or feature.get("properties", {}).get("id")
        if cid is None:
            continue
        props = feature.get("properties") or {}
        result[cid] = {
            "id": cid,
            "name": props.get("name", ""),
            "geometry": feature.get("geometry", {}),
            "lon": props.get("lon", 0.0),
            "lat": props.get("lat", 0.0),
            "neighbors": props.get("neighbors", []),
            "duchy_id": props.get("duchy_id", ""),
            "baronies": props.get("baronies", []),
            "terrain_type": props.get("terrain_type"),  # Optional[str] — None when absent (Phase 5)
        }
    return result


async def save_territories(project_id: str, territories: dict[str, dict]) -> None:
    """Persist the indexed territories dict back to territories.geojson.

    Uses atomic write (.tmp then os.replace) to avoid partial writes.
    Serialises as a FeatureCollection preserving all properties.

    T-PATH: project_dir() raises ValueError on invalid UUIDs.
    """
    import os
    from .paths import project_dir

    out_dir = project_dir(project_id) / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "territories.geojson"
    tmp_path = out_dir / "territories.geojson.tmp"

    features = []
    for cid, t in territories.items():
        properties = {
            "id": cid,
            "name": t.get("name", ""),
            "lon": t.get("lon", 0.0),
            "lat": t.get("lat", 0.0),
            "neighbors": t.get("neighbors", []),
            "duchy_id": t.get("duchy_id", ""),
            "baronies": t.get("baronies", []),
        }
        # Phase 5: persist terrain_type only when present (keeps file compact for un-painted features)
        if t.get("terrain_type"):
            properties["terrain_type"] = t["terrain_type"]
        features.append({
            "type": "Feature",
            "id": cid,
            "geometry": t.get("geometry", {}),
            "properties": properties,
        })

    payload = json.dumps(
        {"type": "FeatureCollection", "features": features},
        ensure_ascii=False,
    )
    tmp_path.write_text(payload, encoding="utf-8")
    # The /preview endpoint now reads files into memory and releases the
    # handle immediately (api/generate.py), so this atomic replace is no
    # longer racing with streaming readers. A short retry loop is kept as
    # belt-and-suspenders in case some other code path (export, renderer)
    # opens the file briefly during a save.
    import time
    for _attempt in range(5):
        try:
            os.replace(tmp_path, out_path)
            return
        except PermissionError:
            time.sleep(0.1)
    # Final failure — re-raise to surface a clear error
    os.replace(tmp_path, out_path)
