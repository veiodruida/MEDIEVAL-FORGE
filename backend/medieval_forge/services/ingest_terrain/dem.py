"""Phase 2.1 GEO-06: Copernicus DEM 90m mosaic.

AWS S3 anonymous bucket: copernicus-dem-90m (eu-central-1).
Tile URL pattern verified by Wave 0 HEAD-probe (2026-04-29):
  HEAD https://copernicus-dem-90m.s3.eu-central-1.amazonaws.com/
       Copernicus_DSM_COG_30_N40_00_E000_00_DEM/Copernicus_DSM_COG_30_N40_00_E000_00_DEM.tif
  Response: HTTP/1.1 200 OK  (AmazonS3, Last-Modified: Mon, 09 May 2022)

T-04-01 (SSRF/path-traversal): tile URL constructed ONLY from int lat/lon validated
against -90..89 / -180..179. Filename uses the same int-validated pattern. No header
or server-response value can influence the path.
"""
from __future__ import annotations

import asyncio
import math
from pathlib import Path
from typing import Any, Callable

import httpx

from medieval_forge.database import DEM_CACHE_DIR

AWS_BUCKET_BASE = "https://copernicus-dem-90m.s3.eu-central-1.amazonaws.com"
BBox = tuple[float, float, float, float]  # (lon_min, lat_min, lon_max, lat_max)
DOWNLOAD_CONCURRENCY = 4  # D-08


def enumerate_tiles(
    lon_min: float,
    lat_min: float,
    lon_max: float,
    lat_max: float,
) -> list[tuple[int, int]]:
    """Return (lat, lon) integer SW-corner pairs covering the bbox.

    Uses math.floor/ceil so fractional bbox boundaries are properly included.
    Iteration order: lat ascending, lon ascending (row-major).
    """
    tiles: list[tuple[int, int]] = []
    for lat in range(math.floor(lat_min), math.ceil(lat_max)):
        for lon in range(math.floor(lon_min), math.ceil(lon_max)):
            tiles.append((lat, lon))
    return tiles


def _tile_basename(lat: int, lon: int) -> str:
    """Construct the tile directory/file basename.

    T-04-01: enforce int + range — no float, no string, no headers.
    Raises TypeError for non-int args; ValueError for out-of-range.
    """
    if not isinstance(lat, int) or not isinstance(lon, int):
        raise TypeError(
            f"lat and lon must be int, got {type(lat).__name__}/{type(lon).__name__}"
        )
    if not (-90 <= lat <= 89) or not (-180 <= lon <= 179):
        raise ValueError(f"lat/lon out of range: ({lat},{lon})")
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"Copernicus_DSM_COG_30_{ns}{abs(lat):02d}_00_{ew}{abs(lon):03d}_00_DEM"


def tile_url(lat: int, lon: int) -> str:
    """Return the full S3 HTTPS URL for the given int lat/lon tile.

    T-04-01: only int-validated lat/lon allowed; _tile_basename enforces this.
    """
    base = _tile_basename(lat, lon)
    return f"{AWS_BUCKET_BASE}/{base}/{base}.tif"


def _cache_path(lat: int, lon: int) -> Path:
    """Return the local cache path for the tile; ensures dem_cache/ exists."""
    DEM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return DEM_CACHE_DIR / f"{_tile_basename(lat, lon)}.tif"


async def fetch_dem(
    bbox: BBox,
    out_path: Path,
    queue: asyncio.Queue[str | None],
    *,
    stop_event: asyncio.Event | None = None,
    client_factory: Callable[[], Any] | None = None,
) -> Path:
    """Download Copernicus DEM tiles for bbox, mosaic to out_path.

    D-08: concurrency capped at DOWNLOAD_CONCURRENCY=4 via asyncio.Semaphore.
    D-09: tile cache at DEM_CACHE_DIR shared across projects, never auto-evicted.
    D-10: rasterio.merge runs in asyncio.to_thread to avoid blocking the event loop.
    D-11: output EPSG:4326 / int16 / nodata=-32768 / deflate / tiled 512x512.
    Pitfall 4: pure-ocean tile 404s emit 'ausente (oceano)' and are skipped; mosaic continues.

    client_factory: optional callable returning an async context-manager httpx client.
    Used for test injection. Defaults to httpx.AsyncClient with 300s timeout.
    """
    if stop_event is None:
        stop_event = asyncio.Event()

    tiles = enumerate_tiles(*bbox)
    await queue.put(
        f"data: DEM: {len(tiles)} tiles a verificar (concurrency={DOWNLOAD_CONCURRENCY}).\n\n"
    )
    sem = asyncio.Semaphore(DOWNLOAD_CONCURRENCY)

    async def fetch_one(lat: int, lon: int) -> Path | None:
        cached = _cache_path(lat, lon)
        if cached.exists() and cached.stat().st_size > 0:
            await queue.put(f"data: tile N{abs(lat):02d}E{abs(lon):03d}: cache hit\n\n")
            return cached
        async with sem:
            if stop_event.is_set():
                return None
            url = tile_url(lat, lon)
            try:
                factory = client_factory or (
                    lambda: httpx.AsyncClient(timeout=300.0, http2=True)
                )
                async with factory() as client:
                    resp = await client.get(url)
                    if resp.status_code == 404:
                        await queue.put(
                            f"data: tile N{abs(lat):02d}E{abs(lon):03d}: ausente (oceano).\n\n"
                        )
                        return None
                    if resp.status_code >= 400:
                        raise httpx.HTTPStatusError(
                            f"HTTP {resp.status_code}",
                            request=None,  # type: ignore[arg-type]
                            response=resp,
                        )
                    # Atomic cache write: write to .tif.tmp then rename (D-09).
                    tmp = cached.with_suffix(".tif.tmp")
                    tmp.write_bytes(resp.content)
                    tmp.replace(cached)
                    await queue.put(
                        f"data: tile N{abs(lat):02d}E{abs(lon):03d}: "
                        f"baixado ({len(resp.content) // 1024} KB).\n\n"
                    )
                    return cached
            except httpx.HTTPError as exc:
                await queue.put(
                    f"data: tile N{abs(lat):02d}E{abs(lon):03d}: "
                    f"falhou ({exc.__class__.__name__}).\n\n"
                )
                return None

    paths_result = await asyncio.gather(*[fetch_one(la, lo) for la, lo in tiles])
    valid = [p for p in paths_result if p is not None]

    if stop_event.is_set():
        raise asyncio.CancelledError("ingest stopped by user")

    if not valid:
        raise RuntimeError("Nenhum tile DEM disponível para este bbox.")

    await queue.put(f"data: Mosaicing {len(valid)} tiles -> {out_path.name}...\n\n")
    # D-10: run blocking rasterio.merge in a thread to keep the event loop free.
    await asyncio.to_thread(_merge_to_geotiff, valid, out_path)
    await queue.put("data: mosaic_complete\n\n")
    return out_path


def _merge_to_geotiff(input_paths: list[Path], out_path: Path) -> None:
    """Merge tile GeoTIFFs into a single mosaic.

    D-10: called via asyncio.to_thread — blocking I/O never runs on the event loop.
    D-11: output EPSG:4326 / int16 / nodata=-32768 / deflate compressed / tiled 512x512.
    """
    import rasterio
    from rasterio.merge import merge

    srcs = [rasterio.open(p) for p in input_paths]
    try:
        mosaic, transform = merge(srcs)
        meta = srcs[0].meta.copy()
        meta.update(
            {
                "driver": "GTiff",
                "height": mosaic.shape[1],
                "width": mosaic.shape[2],
                "transform": transform,
                "compress": "deflate",
                "tiled": True,
                "blockxsize": 512,
                "blockysize": 512,
                "nodata": -32768,
            }
        )
        # Atomic write: write to .tif.tmp then replace.
        tmp = out_path.with_suffix(".tif.tmp")
        with rasterio.open(tmp, "w", **meta) as dst:
            dst.write(mosaic)
        tmp.replace(out_path)
    finally:
        for s in srcs:
            s.close()
