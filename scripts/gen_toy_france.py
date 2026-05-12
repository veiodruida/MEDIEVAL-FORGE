"""One-shot: generate ~50 Voronoi-from-grid municipalities for France 1066 toy."""
import json
from pathlib import Path
import numpy as np
from scipy.spatial import Voronoi
from shapely.geometry import Polygon, mapping, box

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "data" / "regions" / "france_1066" / "inputs"
BOUNDS = (-5.0, 42.0, 8.0, 51.0)  # lon_min, lat_min, lon_max, lat_max
N = 50
RNG_SEED = 42  # CLAUDE.md determinism rule


def _voronoi_polygons(points: np.ndarray, bbox: tuple) -> list[Polygon]:
    """Build finite Voronoi polygons clipped to bbox."""
    vor = Voronoi(points)
    clip = box(bbox[0], bbox[1], bbox[2], bbox[3])
    polys: list[Polygon] = []
    for region_idx in vor.point_region:
        verts = vor.regions[region_idx]
        if not verts or -1 in verts:
            # R-13 (review): Voronoi "infinite" regions are skipped here.
            # Expected: ~6-10 of N=50 seeds drop out (cells at the convex hull
            # boundary). The acceptance feature count `>=40 and <=50` below
            # accommodates this (RESEARCH Pitfall 10).
            continue
        poly = Polygon([vor.vertices[i] for i in verts])
        clipped = poly.intersection(clip)
        if clipped.is_empty:
            continue
        if clipped.geom_type == "MultiPolygon":
            clipped = max(clipped.geoms, key=lambda g: g.area)
        polys.append(clipped)
    return polys


def main() -> None:
    rng = np.random.default_rng(RNG_SEED)
    # Jittered grid: sqrt(N)≈7 → 7×8 = 56 points, jitter ±0.5 cell
    nx, ny = 7, 8
    xs = np.linspace(BOUNDS[0], BOUNDS[2], nx)
    ys = np.linspace(BOUNDS[1], BOUNDS[3], ny)
    cell_x = (BOUNDS[2] - BOUNDS[0]) / nx
    cell_y = (BOUNDS[3] - BOUNDS[1]) / ny
    pts = []
    for x in xs:
        for y in ys:
            jx = rng.uniform(-0.5, 0.5) * cell_x
            jy = rng.uniform(-0.5, 0.5) * cell_y
            pts.append([x + jx, y + jy])
    points = np.array(pts[:N])  # cap to N=50

    polys = _voronoi_polygons(points, BOUNDS)
    features = []
    for i, poly in enumerate(polys):
        features.append({
            "type": "Feature",
            "properties": {"id": f"FR_TOY_{i:03d}", "name": f"Toy_{i:03d}"},
            "geometry": mapping(poly),
        })
    fc = {"type": "FeatureCollection", "features": features}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "france_municipalities_toy.geojson").open("w", encoding="utf-8") as f:
        json.dump(fc, f, indent=2, sort_keys=True)
    # RESEARCH-corrected shape: dict-of-dicts, NOT lists
    with (OUT_DIR / "mountain_river_data.json").open("w", encoding="utf-8") as f:
        json.dump({"mountains": {}, "rivers": {}}, f, indent=2, sort_keys=True)
    print(f"wrote {len(features)} features to {OUT_DIR}")


if __name__ == "__main__":
    main()
