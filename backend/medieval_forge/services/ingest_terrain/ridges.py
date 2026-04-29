"""Phase 2.1 GEO-07: derive ridge polygons + centerlines from DEM.

Pipeline (D-14):
  1. Read DEM (rasterio).
  2. Gaussian smooth (denoise crests).
  3. Slope (degrees) via numpy.gradient + arctan(hypot).
  4. Negative laplacian (convex-up = ridge candidate) via scipy.ndimage.laplace.
  5. Threshold mask = (slope > s_min) AND (lap > c_min) AND (z != nodata).
  6. Skeletonize via skimage.morphology.skeletonize (Pitfall 6: bool input).
  7. Polygonize the mask to get MultiPolygon ridge zone (adjacency penalty area).
  8. Extract centerline from skeleton → LineString.
  9. Build feature with deterministic id = sha1(string-format) (Pitfall 7).
 10. Cross-ref OSM peaks (raw/topography.geojson) for peak_count + naming (D-16, D-19).
 11. Cross-ref HydroSHEDS basins (raw/basins.geojson) for basin_ids[] tagging.

Calibration record (Wave 0 Task 0, backend/tests/fixtures/synthetic_dem.tif):
  synthetic DEM z.std ≈ 367; lap_raw range -7.9..58.1; slope range 0..90°.
  slope>30 AND lap_raw>0.002 → 840 mask cells, 2 skeleton components, 2 polygons.
  Polygon areas ≈ 4.2e-2 deg² >> min threshold 4.06e-4 deg² (5e6m²/111000²).
  Unnormalized laplacian used (matches RESEARCH.md §4 thresholds exactly).
"""
from __future__ import annotations

import json
import logging
from hashlib import sha1
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.features import shapes as raster_shapes, rasterize
from scipy import ndimage
from skimage import morphology
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiPolygon,
    Point,
    mapping,
    shape as shp_shape,
)

log = logging.getLogger(__name__)

# Calibrated against backend/tests/fixtures/synthetic_dem.tif (Wave 0 Task 0).
# Unnormalized laplacian (raw scipy.ndimage.laplace output) — NOT divided by std.
# If you change these, re-run the Wave 0 calibration probe and update this comment.
THRESHOLDS: dict[str, dict[str, float]] = {
    "low":  {"slope_min_deg": 25.0, "curvature_min": 0.0010, "min_polygon_area_m2": 1.0e6},
    "med":  {"slope_min_deg": 30.0, "curvature_min": 0.0020, "min_polygon_area_m2": 5.0e6},
    "high": {"slope_min_deg": 35.0, "curvature_min": 0.0030, "min_polygon_area_m2": 1.0e7},
}


def _check_high_quality_available() -> None:
    """D-14: 'high' sensitivity requires `whitebox` extra. Raise if missing."""
    try:
        import whitebox  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "sensitivity='high' requires the [high-quality] extra. "
            "Install with: pip install medieval-forge[high-quality]"
        ) from exc


def _stable_ridge_id(centroid_x: float, centroid_y: float, elev_max: float) -> str:
    """Pitfall 7: string-format hashing — deterministic across Python/numpy versions.

    key = f"{cx:.3f}|{cy:.3f}|{int(round(elev_max))}"
    """
    key = f"{centroid_x:.3f}|{centroid_y:.3f}|{int(round(elev_max))}"
    return sha1(key.encode("ascii")).hexdigest()[:12]



def derive_ridges(
    dem_path: Path | str,
    sensitivity: str = "med",
    topography_path: Path | str | None = None,
    basins_path: Path | str | None = None,
) -> dict[str, Any]:
    """Derive ridge polygons + centerlines from a DEM GeoTIFF.

    Args:
        dem_path: Path to raw/dem.tif (Plan 04 output).
        sensitivity: one of "low", "med", "high" (D-17).
        topography_path: Optional path to raw/topography.geojson for OSM peak cross-ref.
        basins_path: Optional path to raw/basins.geojson for HydroSHEDS basin cross-ref.

    Returns:
        GeoJSON FeatureCollection with ridge features per CONTEXT.md contract.

    Raises:
        ValueError: invalid sensitivity value.
        RuntimeError: sensitivity='high' but whitebox extra not installed (D-14).
    """
    if sensitivity not in THRESHOLDS:
        raise ValueError(
            f"sensitivity must be one of {list(THRESHOLDS)}; got {sensitivity!r}"
        )
    if sensitivity == "high":
        _check_high_quality_available()

    cfg = THRESHOLDS[sensitivity]

    # --- 1. Read DEM ---
    with rasterio.open(dem_path) as src:
        z = src.read(1).astype("float32")
        nodata = float(src.nodata) if src.nodata is not None else -32768.0
        transform = src.transform

    valid = z != nodata

    # --- 2. Gaussian smooth ---
    z_smooth = ndimage.gaussian_filter(
        np.where(valid, z, 0.0).astype("float32"), sigma=1.5
    )

    # --- 3. Slope ---
    dy, dx = np.gradient(z_smooth)
    slope_deg = np.degrees(np.arctan(np.hypot(dx, dy)))

    # --- 4. Negative laplacian (unnormalized — see calibration comment above) ---
    lap = -ndimage.laplace(z_smooth)

    # --- 5. Threshold mask ---
    mask = (slope_deg > cfg["slope_min_deg"]) & (lap > cfg["curvature_min"]) & valid

    # --- 6. Skeletonize (Pitfall 6: must be bool input) ---
    skeleton = morphology.skeletonize(mask.astype(bool))

    # --- 7. Polygonize mask → ridge zones ---
    min_area_deg2 = cfg["min_polygon_area_m2"] / (111_000.0 ** 2)
    polys = []
    for geom_dict, value in raster_shapes(
        mask.astype("uint8"), mask=mask, transform=transform
    ):
        if value != 1:
            continue
        poly = shp_shape(geom_dict)
        if poly.area >= min_area_deg2:
            polys.append(poly)

    # --- Optional OSM peak cross-ref (D-16/D-19) ---
    peaks: list[tuple[Point, str | None]] = []
    if topography_path is not None and Path(topography_path).exists():
        try:
            topo = json.loads(Path(topography_path).read_text(encoding="utf-8"))
            for feat in topo.get("features", []):
                if feat["properties"].get("natural") != "peak":
                    continue
                geom = feat.get("geometry", {})
                if geom.get("type") == "Point":
                    x, y = geom["coordinates"]
                    peaks.append((Point(x, y), feat["properties"].get("name")))
        except Exception as exc:
            log.warning(
                "topography cross-ref failed (continuing without peaks): %s", exc
            )

    # --- Optional HydroSHEDS basin cross-ref ---
    basins: list[tuple[Any, int]] = []
    if basins_path is not None and Path(basins_path).exists():
        try:
            bj = json.loads(Path(basins_path).read_text(encoding="utf-8"))
            for feat in bj.get("features", []):
                g = shp_shape(feat["geometry"])
                bid = int(feat["properties"].get("id") or 0)
                basins.append((g, bid))
        except Exception as exc:
            log.warning(
                "basins cross-ref failed (continuing without basin_ids): %s", exc
            )

    # --- 8. Label raster: one rasterize call replaces per-polygon geometry_mask calls ---
    height, width = z.shape
    label_raster = np.zeros((height, width), dtype=np.int32)
    if polys:
        shapes_with_labels = [(poly.__geo_interface__, i + 1) for i, poly in enumerate(polys)]
        label_raster = rasterize(
            shapes_with_labels,
            out_shape=(height, width),
            transform=transform,
            fill=0,
            dtype=np.int32,
        )

    # --- 9. Build features ---
    features = []
    for i, poly in enumerate(polys):
        cx, cy = poly.centroid.x, poly.centroid.y
        label = i + 1
        pix_mask = label_raster == label  # boolean mask for this polygon

        # Elevation stats via label mask (replaces per-polygon geometry_mask)
        sample = z[pix_mask & (z != nodata)]
        if sample.size == 0:
            elev_min, elev_max, elev_mean = 0.0, 0.0, 0.0
        else:
            elev_min = float(sample.min())
            elev_max = float(sample.max())
            elev_mean = float(sample.mean())

        # OSM peak cross-ref: count contained peaks + pick name
        contained_peaks = [(pt, name) for (pt, name) in peaks if poly.contains(pt)]
        peak_count = len(contained_peaks)
        named = [n for (_, n) in contained_peaks if n]
        ridge_name: str | None = named[0] if named else None

        # Basin cross-ref
        basin_ids = sorted({bid for (g, bid) in basins if poly.intersects(g)})

        # Centerline from skeleton pixels inside polygon via label mask
        ys, xs = np.where(skeleton & pix_mask)
        if len(xs) < 2:
            # Degenerate: return a tiny line at centroid so geometry stays valid.
            centerline = LineString([(cx, cy), (cx + 1e-6, cy + 1e-6)])
        else:
            # Convert pixel (col, row) to world (x, y) via affine transform.
            coords = [transform * (int(c), int(r)) for r, c in zip(ys, xs)]
            centerline = LineString(coords)

        # Deterministic ID (Pitfall 7)
        feat_id = _stable_ridge_id(cx, cy, elev_max)

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": feat_id,
                    "name": ridge_name,
                    "elev_min": float(elev_min),
                    "elev_max": float(elev_max),
                    "elev_mean": float(elev_mean),
                    "peak_count": int(peak_count),
                    "basin_ids": basin_ids,
                },
                "geometry": mapping(
                    GeometryCollection([MultiPolygon([poly]), centerline])
                ),
            }
        )

    return {"type": "FeatureCollection", "features": features}
