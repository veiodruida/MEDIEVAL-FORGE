"""Phase 2.1 GEO-05: HydroSHEDS lv6 basin clip.

Vendored shapefile lives at medieval_forge/data/hydrosheds/hybas_eu_lev06_v1c.shp (CC-BY 4.0).
Reads with geopandas using bbox spatial filter (pushed to GDAL/pyogrio for speed).

Deviation from plan spec (Task 0a delivery):
  Plan specified hybas_lev06_v1c (global). The downloaded file is hybas_eu_lev06_v1c
  (Europe subset). This is documented in SUMMARY deviations. Implication: projects
  with bboxes outside Europe will receive an empty FeatureCollection — Phase 2.2
  clustering will have no watershed constraint for non-European projects. Acceptable
  for current Iberia-focused use case.

T-03-01 mitigation: shapefile path constructed via importlib.resources.files() only —
  no string concatenation with user input, no os.path.join from request data.

T-03-02 accepted: only int/float fields (HYBAS_ID, NEXT_DOWN, SUB_AREA) are consumed.
  No string/name field is read, so latin-1 mojibake (Pitfall 3) is irrelevant.

T-03-03 mitigation: geopandas.read_file with bbox= pushes spatial filter to GDAL/pyogrio
  spatial index — only intersecting features are loaded into memory. asyncio.to_thread
  keeps the async event loop free during the blocking GDAL call.
"""
from __future__ import annotations

import asyncio
import importlib.resources
import json
from typing import Any

import geopandas as gpd

BBox = tuple[float, float, float, float]  # (lon_min, lat_min, lon_max, lat_max)


# T-03-01: shapefile path is constructed only via importlib.resources — never from user input.
def _shapefile_path() -> str:
    return str(
        importlib.resources.files("medieval_forge.data.hydrosheds")
        / "hybas_eu_lev06_v1c.shp"
    )


async def fetch_basins(
    bbox: BBox,
    queue: asyncio.Queue[str | None],
    *,
    stop_event: asyncio.Event | None = None,
) -> dict[str, Any]:
    """Clip HydroSHEDS lv6 basins to bbox and return as GeoJSON FeatureCollection.

    Schema (D-23 contract):
      feature.properties.id: int         — HYBAS_ID (stable HydroSHEDS basin id)
      feature.properties.next_down: int  — downstream HYBAS_ID (0 if outlet)
      feature.properties.sub_area: float — basin area in km²

    SSE queue receives progress messages (Portuguese, matching runner conventions).
    """
    await queue.put("data: lendo HydroSHEDS lv6 (vendored)...\n\n")
    # geopandas read is sync + blocks on GDAL — wrap in to_thread.
    gdf = await asyncio.to_thread(_read_clipped, bbox)
    await queue.put(f"data: {len(gdf)} bacias intersectam o bbox.\n\n")
    if gdf.empty:
        return {"type": "FeatureCollection", "features": []}
    # Rename to D-23 schema:
    gdf = gdf.rename(columns={"HYBAS_ID": "id", "NEXT_DOWN": "next_down", "SUB_AREA": "sub_area"})
    keep = ["id", "next_down", "sub_area", "geometry"]
    # Tolerate missing columns (defensive — ogrinfo confirms the names but be safe):
    keep = [c for c in keep if c in gdf.columns]
    gdf = gdf[keep]
    # Coerce numeric types per contract.
    if "id" in gdf.columns:
        gdf["id"] = gdf["id"].astype("int64")
    if "next_down" in gdf.columns:
        gdf["next_down"] = gdf["next_down"].astype("int64")
    if "sub_area" in gdf.columns:
        gdf["sub_area"] = gdf["sub_area"].astype("float64")
    return json.loads(gdf.to_json())


def _read_clipped(bbox: BBox) -> gpd.GeoDataFrame:
    """Blocking GDAL read — call via asyncio.to_thread from async context.

    geopandas bbox order: (minx, miny, maxx, maxy) == (lon_min, lat_min, lon_max, lat_max).
    Same as our BBox convention — no reorder needed.
    """
    return gpd.read_file(_shapefile_path(), bbox=bbox)
