"""Unit tests for baronies_builder service (Etapa 2).

Deterministic fixture: 6 unit-square Polygons placed at lon offsets 0,2,4,6,8,10
(lat=40), with osm_ids 101..106. Centroids are well-separated so KMeans
clustering is deterministic given the seeded RNG.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from shapely.geometry import Polygon, mapping

from medieval_forge.services.baronies_builder import build_baronies_from_osm


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

OSM_IDS: list[int] = [101, 102, 103, 104, 105, 106]
LON_OFFSETS: list[float] = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]
LAT_BASE: float = 40.0
SQUARE_SIDE: float = 1.0


def _square(lon0: float, lat0: float, side: float = SQUARE_SIDE) -> Polygon:
    """Axis-aligned square with lower-left corner at (lon0, lat0)."""
    return Polygon([
        (lon0, lat0),
        (lon0 + side, lat0),
        (lon0 + side, lat0 + side),
        (lon0, lat0 + side),
        (lon0, lat0),
    ])


def _build_fixture_geojson(tmp_path: Path) -> Path:
    """Build 6-municipality FeatureCollection at known lon/lat. Returns the path."""
    features = []
    for osm_id, lon0 in zip(OSM_IDS, LON_OFFSETS):
        poly = _square(lon0, LAT_BASE)
        features.append({
            "type": "Feature",
            "properties": {
                "osm_id": osm_id,
                "name": f"Muni{osm_id}",
                "admin_level": "6",
            },
            "geometry": mapping(poly),
        })
    fc = {"type": "FeatureCollection", "features": features}
    path = tmp_path / "municipalities.geojson"
    path.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_baronies_1_to_1_when_granularity_is_all(tmp_path):
    path = _build_fixture_geojson(tmp_path)

    result = build_baronies_from_osm(path, "all")

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 6
    for feat, osm_id in zip(result["features"], OSM_IDS):
        props = feat["properties"]
        assert props["id"] == f"B_{osm_id}"
        assert props["municipality_ids"] == [osm_id]
        # Geometry must be the original município polygon (equal area).
        from shapely.geometry import shape
        assert shape(feat["geometry"]).area == pytest.approx(SQUARE_SIDE * SQUARE_SIDE, abs=1e-9)


def test_baronies_clustered_kdtree_when_target_count_specified(tmp_path):
    path = _build_fixture_geojson(tmp_path)

    result = build_baronies_from_osm(path, 3)  # cluster 6 → 3

    assert len(result["features"]) == 3
    total_members = sum(
        len(f["properties"]["municipality_ids"]) for f in result["features"]
    )
    assert total_members == 6


def test_baronies_preserve_municipality_ids_per_cluster(tmp_path):
    path = _build_fixture_geojson(tmp_path)

    result = build_baronies_from_osm(path, 3)

    all_ids = sorted(
        mid for f in result["features"] for mid in f["properties"]["municipality_ids"]
    )
    assert all_ids == sorted(OSM_IDS)  # no loss, no duplication


def test_baronies_centroid_is_average_of_member_municipalities(tmp_path):
    """Build 2 clusters from 4 municipalities; verify each centroid == mean of members."""
    # 4 squares: lons 0, 2 (cluster A) and 50, 52 (cluster B) — far apart so kmeans is unambiguous.
    features = []
    for osm_id, lon0 in zip([201, 202, 203, 204], [0.0, 2.0, 50.0, 52.0]):
        poly = _square(lon0, LAT_BASE)
        features.append({
            "type": "Feature",
            "properties": {"osm_id": osm_id, "name": f"M{osm_id}", "admin_level": "6"},
            "geometry": mapping(poly),
        })
    fc = {"type": "FeatureCollection", "features": features}
    path = tmp_path / "municipalities.geojson"
    path.write_text(json.dumps(fc), encoding="utf-8")

    result = build_baronies_from_osm(path, 2)
    assert len(result["features"]) == 2

    # Each cluster's centroid should be the mean of its members' representative_points.
    # representative_point for an axis-aligned square ~ centroid (lon0+0.5, LAT_BASE+0.5).
    expected_centroids = {
        frozenset([201, 202]): (1.5, LAT_BASE + 0.5),
        frozenset([203, 204]): (51.5, LAT_BASE + 0.5),
    }
    for feat in result["features"]:
        member_set = frozenset(feat["properties"]["municipality_ids"])
        assert member_set in expected_centroids, f"unexpected cluster: {member_set}"
        exp_lon, exp_lat = expected_centroids[member_set]
        got_lon, got_lat = feat["properties"]["centroid"]
        assert got_lon == pytest.approx(exp_lon, abs=1e-6)
        assert got_lat == pytest.approx(exp_lat, abs=1e-6)


def test_baronies_polygon_is_union_of_member_municipality_polygons(tmp_path):
    """1 barony from 2 adjacent squares sharing an edge → area == sum of inputs."""
    # Two squares sharing the edge at lon=1.0
    s1 = _square(0.0, LAT_BASE)
    s2 = _square(1.0, LAT_BASE)
    features = [
        {
            "type": "Feature",
            "properties": {"osm_id": 301, "name": "A", "admin_level": "6"},
            "geometry": mapping(s1),
        },
        {
            "type": "Feature",
            "properties": {"osm_id": 302, "name": "B", "admin_level": "6"},
            "geometry": mapping(s2),
        },
    ]
    fc = {"type": "FeatureCollection", "features": features}
    path = tmp_path / "municipalities.geojson"
    path.write_text(json.dumps(fc), encoding="utf-8")

    result = build_baronies_from_osm(path, 1)
    assert len(result["features"]) == 1

    from shapely.geometry import shape
    merged = shape(result["features"][0]["geometry"])
    assert merged.area == pytest.approx(2 * SQUARE_SIDE * SQUARE_SIDE, abs=1e-9)
    assert merged.geom_type in ("Polygon", "MultiPolygon")
