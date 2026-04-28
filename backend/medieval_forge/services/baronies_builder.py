"""Etapa 2: Baronies Builder — converts OSM município polygons into baronies.

Two modes:
- target_count == "all": 1 município = 1 barony (id = B_{osm_id})
- target_count == int (e.g. 50, 250, 1000): scipy KMeans on município centroids;
  each município assigned to nearest cluster; output polygon is unary_union of members.

Output GeoJSON FeatureCollection feature shape:
  {
    "type": "Feature",
    "properties": {
      "id": "B_{osm_id}" | "B_C{cluster_idx:04d}",
      "name": str,
      "centroid": [lon, lat],
      "municipality_ids": list[int],
    },
    "geometry": Polygon | MultiPolygon,
  }
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.cluster.vq import kmeans2
from shapely.geometry import mapping, shape
from shapely.ops import unary_union


def _feature_centroid(feat: dict[str, Any]) -> tuple[float, float]:
    """Robust centroid: representative_point handles weird MultiPolygons gracefully."""
    geom = shape(feat["geometry"])
    c = geom.representative_point()
    return (float(c.x), float(c.y))


def build_baronies_from_osm(
    municipalities_geojson_path: Path,
    target_count: int | str,
) -> dict[str, Any]:
    """Return GeoJSON FeatureCollection of baronies built from município polygons.

    Args:
        municipalities_geojson_path: Path to raw/municipalities.geojson
            (output of ingest_osm.fetch_municipalities).
        target_count: "all" or positive int. "all" → 1:1 mode.

    Raises:
        FileNotFoundError: if path does not exist.
        ValueError: if target_count invalid or input has no Polygon/MultiPolygon features.
    """
    if not municipalities_geojson_path.exists():
        raise FileNotFoundError(
            f"municipalities geojson not found: {municipalities_geojson_path}"
        )

    data = json.loads(municipalities_geojson_path.read_text(encoding="utf-8"))
    feats = [
        f for f in data.get("features", [])
        if f.get("geometry", {}).get("type") in ("Polygon", "MultiPolygon")
    ]
    if not feats:
        raise ValueError("no Polygon/MultiPolygon features in input geojson")

    # Validate target_count
    if isinstance(target_count, str):
        if target_count != "all":
            raise ValueError(
                f"target_count str must be 'all', got {target_count!r}"
            )
        return _build_one_to_one(feats)

    if not isinstance(target_count, int) or target_count < 1:
        raise ValueError(
            f"target_count must be 'all' or positive int, got {target_count!r}"
        )

    if target_count >= len(feats):
        # Asking for more (or equal) clusters than municípios → just do 1:1.
        return _build_one_to_one(feats)

    return _build_clustered(feats, target_count)


def _build_one_to_one(feats: list[dict[str, Any]]) -> dict[str, Any]:
    out: list[dict[str, Any]] = []
    for f in feats:
        osm_id = f["properties"].get("osm_id")
        name = f["properties"].get("name", "") or f"Barony {osm_id}"
        lon, lat = _feature_centroid(f)
        out.append({
            "type": "Feature",
            "properties": {
                "id": f"B_{osm_id}",
                "name": name,
                "centroid": [lon, lat],
                "municipality_ids": [osm_id],
            },
            "geometry": f["geometry"],
        })
    return {"type": "FeatureCollection", "features": out}


def _build_clustered(feats: list[dict[str, Any]], k: int) -> dict[str, Any]:
    centroids = np.array([_feature_centroid(f) for f in feats], dtype=float)

    # Deterministic seed for reproducible tests. Set both the global numpy seed
    # (in case the scipy version under test ignores the `seed=` kwarg) and pass
    # seed=42 to kmeans2 directly.
    np.random.seed(42)
    _cluster_centers, labels = kmeans2(centroids, k, minit="++", seed=42)

    # Group features by cluster label
    groups: dict[int, list[dict[str, Any]]] = {}
    for feat, label in zip(feats, labels):
        groups.setdefault(int(label), []).append(feat)

    out: list[dict[str, Any]] = []
    for cluster_idx in sorted(groups.keys()):
        members = groups[cluster_idx]
        muni_ids = [m["properties"].get("osm_id") for m in members]
        member_centroids = np.array([_feature_centroid(m) for m in members])
        c_lon = float(member_centroids[:, 0].mean())
        c_lat = float(member_centroids[:, 1].mean())
        geoms = [shape(m["geometry"]) for m in members]
        merged = unary_union(geoms)
        out.append({
            "type": "Feature",
            "properties": {
                "id": f"B_C{cluster_idx:04d}",
                "name": f"Barony {cluster_idx + 1}",
                "centroid": [c_lon, c_lat],
                "municipality_ids": muni_ids,
            },
            "geometry": mapping(merged),
        })
    return {"type": "FeatureCollection", "features": out}
