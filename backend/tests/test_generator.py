"""Tests for generator.py helper functions — Fix A (Problem A: ghost condados).

A1: _densify_ring / _densify_feature — PT rings with < 40 vertices are densified
    before being written to pt_municipalities.geojson so that map_generator's
    40-vertex filter never silently drops a municipality.

A2: _build_region_config bbox expansion — municipality centroids near the padded
    bbox edge are included in the render window so that decode_topojson_municipalities
    never filters them out.
"""
import json
import math
import uuid
from pathlib import Path

import pytest

from medieval_forge.services.generator import (
    _densify_ring,
    _densify_feature,
    _municipality_centroids,
    _split_municipalities_pt_es,
    _build_region_config,
)


# ---------------------------------------------------------------------------
# A1 — ring densification
# ---------------------------------------------------------------------------

def _make_square_ring(n_vertices: int) -> list:
    """Build a simple square ring with exactly n_vertices (closed)."""
    # Distribute n_vertices-1 open points around a unit square, then close.
    pts = []
    open_n = n_vertices - 1
    per_side = max(1, open_n // 4)
    for i in range(per_side):
        pts.append([float(i) / per_side, 0.0])
    for i in range(per_side):
        pts.append([1.0, float(i) / per_side])
    for i in range(per_side):
        pts.append([1.0 - float(i) / per_side, 1.0])
    for i in range(per_side):
        pts.append([0.0, 1.0 - float(i) / per_side])
    # Trim or pad to exactly open_n points (approximate; test only needs < 40)
    pts = pts[:open_n] if len(pts) >= open_n else pts
    pts.append(list(pts[0]))  # close
    return pts


def _polygon_area(ring: list) -> float:
    """Shoelace formula — signed area of a closed ring."""
    n = len(ring)
    area = 0.0
    for i in range(n - 1):
        area += ring[i][0] * ring[i + 1][1]
        area -= ring[i + 1][0] * ring[i][1]
    return abs(area) / 2.0


def test_densify_ring_already_sufficient():
    """Rings with >= 40 vertices are returned unchanged."""
    ring = _make_square_ring(50)
    result = _densify_ring(ring, min_vertices=40)
    assert result is ring or result == ring
    assert len(result) == len(ring)


def test_densify_ring_short_ring_reaches_minimum():
    """A ring with 8 explicit vertices is densified to >= 40 vertices."""
    # Explicit closed 8-point ring (closed: first == last), 8 total points.
    ring = [
        [0.0, 0.0], [0.5, 0.0], [1.0, 0.0], [1.0, 0.5],
        [1.0, 1.0], [0.5, 1.0], [0.0, 1.0], [0.0, 0.0],
    ]
    assert len(ring) == 8
    result = _densify_ring(ring, min_vertices=40)
    assert len(result) >= 40, (
        f"Expected >= 40 vertices after densification, got {len(result)}"
    )


def test_densify_ring_preserves_closure():
    """Closed ring (first == last) stays closed after densification."""
    ring = _make_square_ring(8)
    assert ring[0] == ring[-1], "Precondition: ring must be closed"
    result = _densify_ring(ring, min_vertices=40)
    assert result[0] == result[-1], "Densified ring must remain closed"


def test_densify_ring_preserves_area():
    """Area of the densified polygon is geometrically equivalent within 1e-4."""
    # Use a known triangle: (0,0), (1,0), (0,1), closed.
    ring = [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 0.0]]
    original_area = _polygon_area(ring)
    result = _densify_ring(ring, min_vertices=40)
    densified_area = _polygon_area(result)
    assert abs(densified_area - original_area) < 1e-4, (
        f"Area changed after densification: {original_area} → {densified_area}"
    )


def test_densify_ring_idempotent():
    """Densifying an already-dense ring twice produces the same result."""
    ring = _make_square_ring(8)
    once = _densify_ring(ring, min_vertices=40)
    twice = _densify_ring(list(once), min_vertices=40)
    assert len(once) == len(twice)


def test_densify_feature_polygon():
    """_densify_feature densifies Polygon outer ring; inner rings untouched."""
    inner_ring = [[0.1, 0.1], [0.2, 0.1], [0.1, 0.2], [0.1, 0.1]]
    outer_ring = _make_square_ring(8)
    feat = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [outer_ring, inner_ring],
        },
        "properties": {},
    }
    result = _densify_feature(feat, min_vertices=40)
    coords = result["geometry"]["coordinates"]
    assert len(coords[0]) >= 40, "Outer ring must be densified"
    assert coords[1] == inner_ring, "Inner ring must be unchanged"


def test_densify_feature_multipolygon():
    """_densify_feature densifies outer rings of all parts of a MultiPolygon."""
    ring_a = _make_square_ring(5)
    ring_b = _make_square_ring(10)
    feat = {
        "type": "Feature",
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [[ring_a], [ring_b]],
        },
        "properties": {},
    }
    result = _densify_feature(feat, min_vertices=40)
    for poly in result["geometry"]["coordinates"]:
        assert len(poly[0]) >= 40, "Every part's outer ring must be densified"


def test_densify_feature_does_not_mutate_original():
    """_densify_feature is non-destructive — original feature is unchanged."""
    ring = _make_square_ring(8)
    original_len = len(ring)
    feat = {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [ring]},
        "properties": {},
    }
    _densify_feature(feat, min_vertices=40)
    assert len(ring) == original_len, "_densify_feature must not mutate the input ring"


# ---------------------------------------------------------------------------
# A1 integration — _split_municipalities_pt_es densifies PT features
# ---------------------------------------------------------------------------

def _write_pt_es_geojson(path: Path, pt_rings: list, es_rings: list) -> None:
    """Write a municipalities GeoJSON with PT features (rings < 40) and ES features."""
    features = []
    # PT: centroid well inside Portugal (lon=-8, lat=40)
    for ring in pt_rings:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {},
        })
    # ES: centroid well inside Spain (lon=-3, lat=40)
    for ring in es_rings:
        # Shift ring to Spain
        shifted = [[c[0] + 5.0, c[1]] for c in ring]
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [shifted]},
            "properties": {},
        })
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))


def test_split_densifies_short_pt_rings(tmp_path):
    """PT features with < 40 vertices in raw_geojson are densified in pt_municipalities.geojson."""
    raw = tmp_path / "municipalities.geojson"
    gen = tmp_path / "generated"
    gen.mkdir()

    # PT ring with only 8 vertices (well below the 40-vertex threshold)
    pt_ring = _make_square_ring(8)
    # shift so centroid is inside PT (around lon=-8, lat=40)
    pt_ring = [[c[0] - 8.5, c[1] + 39.5] for c in pt_ring]
    pt_ring.append(list(pt_ring[0]))  # re-close after shift

    # ES ring with 8 vertices, centroid inside Spain (around lon=-3, lat=40)
    es_ring = _make_square_ring(8)
    es_ring = [[c[0] - 3.5, c[1] + 39.5] for c in es_ring]
    es_ring.append(list(es_ring[0]))

    raw.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [pt_ring]},
         "properties": {}},
        {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [es_ring]},
         "properties": {}},
    ]}))

    pt_path, _es_path = _split_municipalities_pt_es(raw, gen, None)
    pt_fc = json.loads(pt_path.read_text())

    for feat in pt_fc["features"]:
        geom = feat["geometry"]
        if geom["type"] == "Polygon":
            outer = geom["coordinates"][0]
            assert len(outer) >= 40, (
                f"PT feature outer ring has only {len(outer)} vertices after split; "
                "densification must ensure >= 40 so map_generator's filter passes."
            )


# ---------------------------------------------------------------------------
# A2 — bbox expansion covers all municipality centroids
# ---------------------------------------------------------------------------

def test_municipality_centroids_returns_all_centroids(tmp_path):
    """_municipality_centroids extracts one centroid per feature."""
    geojson = tmp_path / "muni.geojson"
    geojson.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Polygon",
         "coordinates": [[[-9.0, 41.0], [-8.0, 41.0], [-8.0, 42.0], [-9.0, 41.0]]]},
         "properties": {}},
        {"type": "Feature", "geometry": {"type": "Polygon",
         "coordinates": [[[-2.0, 40.0], [-1.0, 40.0], [-1.0, 41.0], [-2.0, 40.0]]]},
         "properties": {}},
    ]}))
    lons, lats = _municipality_centroids(geojson)
    assert len(lons) == 2
    assert len(lats) == 2
    # First centroid: mean of [(-9,41),(-8,41),(-8,42),(-9,41)] (4 pts, closed)
    # lon = (-9 + -8 + -8 + -9) / 4 = -34/4 = -8.5
    # lat = (41 + 41 + 42 + 41) / 4 = 165/4 = 41.25
    assert abs(lons[0] - (-8.5)) < 1e-3
    assert abs(lats[0] - 41.25) < 1e-3


def test_build_region_config_expands_bbox_for_municipality_centroids(tmp_path, monkeypatch):
    """A2 fix: municipalities with centroids outside the tight condado-bbox are included.

    Setup: two condados in western Iberia (lon ≈ -8). A municipality centroid
    at lon=-1.5, just inside real Iberia but outside the 5%-padded condado-bbox.
    After the fix, the render bbox must extend to include that centroid.
    """
    import medieval_forge.services.generator as gen_mod

    # Patch map_generator to avoid real RegionConfig validation
    import types
    import dataclasses

    @dataclasses.dataclass
    class FakeRegionConfig:
        output_dir: str = ""
        lon_min: float = -12.0
        lon_max: float = 0.0
        lat_min: float = 35.0
        lat_max: float = 45.0
        map_w: int = 100
        map_h: int = 80
        upscale: int = 1
        lon_scale: float = 0.78
        municipality_pt_geojson: str | None = None
        municipality_es_topojson: str | None = None
        mountain_river_json: str | None = None
        border_polygon: list | None = None
        name: str = "test"

    fake_map_gen = types.ModuleType("map_generator")
    fake_map_gen.RegionConfig = FakeRegionConfig
    monkeypatch.setattr(gen_mod, "map_generator", fake_map_gen)

    # Build project dir structure
    proj = tmp_path / "proj"
    raw_dir = proj / "raw"
    raw_dir.mkdir(parents=True)
    gen_dir = proj / "generated"
    gen_dir.mkdir()

    # Municipality with centroid at lon=-1.5 (east of condado positions)
    # and another at lon=-8.5 (western PT side)
    raw_muni = raw_dir / "municipalities.geojson"
    raw_muni.write_text(json.dumps({"type": "FeatureCollection", "features": [
        # PT municipality (inside PT border polygon, lon ≈ -8.5)
        {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [
            [[-9.0, 41.0], [-8.0, 41.0], [-8.0, 42.0], [-9.0, 42.0], [-9.0, 41.0]]
        ]}, "properties": {}},
        # ES municipality — centroid lon=-1.5, outside tight condado bbox
        {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [
            [[-2.0, 40.0], [-1.0, 40.0], [-1.0, 41.0], [-2.0, 41.0], [-2.0, 40.0]]
        ]}, "properties": {}},
    ]}))

    # Two condados clustered in western Iberia — bbox without A2 would be tight
    config = {
        "territory_data": {
            "kingdoms": {"K1": "K1"},
            "duchies": {"D1": ["K1", "D1"]},
            "condados": [
                ["C1", "West1", -8.5, 41.5, "D1", []],
                ["C2", "West2", -7.5, 40.5, "D1", []],
            ],
        },
    }

    cfg = _build_region_config(gen_dir, config)

    # The ES municipality centroid is at lon = mean([-2,-1,-1,-2,-2]) = -1.6
    # (closed ring, 5 pts). After A2 fix, cfg.lon_max must be > -1.6.
    es_centroid_lon = sum([-2.0, -1.0, -1.0, -2.0, -2.0]) / 5  # = -1.6
    assert cfg.lon_max > es_centroid_lon, (
        f"cfg.lon_max={cfg.lon_max:.3f} does not include ES centroid at "
        f"lon={es_centroid_lon:.3f}; A2 bbox expansion not working."
    )
