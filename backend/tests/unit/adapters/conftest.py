"""Synthetic Overpass FC fixture shared across adapter unit tests (D-12 isolation).

The 6 features cover: 2 Polygons in PT (Lisbon area), 3 in ES (Madrid area),
1 in mid-Atlantic (must be dropped). Geometry is hand-crafted with
representative_points known to fall inside / outside the Natural Earth
country polygons.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def synthetic_iberia_fc() -> dict:
    """Tiny FeatureCollection with 6 features: 2 PT, 3 ES, 1 Atlantic."""
    def _square(lon, lat, size=0.05):
        # Returns a 4-corner square polygon centered at (lon, lat).
        return [
            [lon - size, lat - size],
            [lon + size, lat - size],
            [lon + size, lat + size],
            [lon - size, lat + size],
            [lon - size, lat - size],
        ]

    return {
        "type": "FeatureCollection",
        "features": [
            # 2 PT features (around Lisbon, lon ~-9.13, lat ~38.71)
            {"type": "Feature", "properties": {"name": "PT-1"},
             "geometry": {"type": "Polygon", "coordinates": [_square(-9.13, 38.71)]}},
            {"type": "Feature", "properties": {"name": "PT-2"},
             "geometry": {"type": "Polygon", "coordinates": [_square(-8.41, 41.15)]}},
            # 3 ES features (around Madrid lon=-3.70 lat=40.42, Barcelona 2.17/41.39, Sevilla -5.99/37.39)
            {"type": "Feature", "properties": {"name": "ES-1"},
             "geometry": {"type": "Polygon", "coordinates": [_square(-3.70, 40.42)]}},
            {"type": "Feature", "properties": {"name": "ES-2"},
             "geometry": {"type": "Polygon", "coordinates": [_square(2.17, 41.39)]}},
            {"type": "Feature", "properties": {"name": "ES-3"},
             "geometry": {"type": "Polygon", "coordinates": [_square(-5.99, 37.39)]}},
            # 1 mid-Atlantic feature (must be dropped — outside both PT and ES)
            {"type": "Feature", "properties": {"name": "ATLANTIC"},
             "geometry": {"type": "Polygon", "coordinates": [_square(-25.0, 40.0)]}},
        ],
    }


@pytest.fixture
def synthetic_multipolygon_pt_feature() -> dict:
    """A MultiPolygon feature centered in PT, used to test split_by_iso resilience."""
    def _square(lon, lat, size=0.05):
        return [
            [lon - size, lat - size], [lon + size, lat - size],
            [lon + size, lat + size], [lon - size, lat + size],
            [lon - size, lat - size],
        ]
    return {
        "type": "Feature",
        "properties": {"name": "PT-MP"},
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [
                [_square(-9.13, 38.71)],   # exterior 1
                [_square(-8.41, 41.15)],   # exterior 2
            ],
        },
    }
