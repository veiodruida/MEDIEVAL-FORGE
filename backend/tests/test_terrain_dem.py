"""Tests for Phase 2.1 GEO-06: Copernicus DEM 90m tile download + mosaic.

HEAD-probe verification (2026-04-29):
  URL: https://copernicus-dem-90m.s3.eu-central-1.amazonaws.com/
       Copernicus_DSM_COG_30_N40_00_E000_00_DEM/Copernicus_DSM_COG_30_N40_00_E000_00_DEM.tif
  Result: HTTP/1.1 200 OK  — URL pattern VERIFIED.
  Server: AmazonS3, Last-Modified: Mon, 09 May 2022 12:59:07 GMT.

RED until Task 1 creates dem.py.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import respx
from httpx import Response

from medieval_forge.services.ingest_terrain.dem import (
    enumerate_tiles,
    fetch_dem,
    tile_url,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SYNTHETIC_TILE = FIXTURES_DIR / "synthetic_dem_tile.tif"


# ---------------------------------------------------------------------------
# Tile enumeration
# ---------------------------------------------------------------------------


def test_enumerate_tiles_returns_sw_integer_corners():
    """enumerate_tiles(0.5, 40.2, 2.7, 41.8) should yield (lat, lon) SW-corner pairs."""
    result = enumerate_tiles(0.5, 40.2, 2.7, 41.8)
    assert result == [
        (40, 0), (40, 1), (40, 2),
        (41, 0), (41, 1), (41, 2),
    ]


def test_enumerate_tiles_handles_negative_longitude():
    """enumerate_tiles(-10.5, 36.0, -7.0, 38.0) includes lon=-11..-8 tiles."""
    result = enumerate_tiles(-10.5, 36.0, -7.0, 38.0)
    assert result == [
        (36, -11), (36, -10), (36, -9), (36, -8),
        (37, -11), (37, -10), (37, -9), (37, -8),
    ]


# ---------------------------------------------------------------------------
# Tile URL construction
# ---------------------------------------------------------------------------


def test_tile_url_format_n40_e000():
    """Verified via HEAD-probe: HTTP 200 on this exact URL."""
    expected = (
        "https://copernicus-dem-90m.s3.eu-central-1.amazonaws.com"
        "/Copernicus_DSM_COG_30_N40_00_E000_00_DEM"
        "/Copernicus_DSM_COG_30_N40_00_E000_00_DEM.tif"
    )
    assert tile_url(40, 0) == expected


def test_tile_url_format_n36_w010():
    expected = (
        "https://copernicus-dem-90m.s3.eu-central-1.amazonaws.com"
        "/Copernicus_DSM_COG_30_N36_00_W010_00_DEM"
        "/Copernicus_DSM_COG_30_N36_00_W010_00_DEM.tif"
    )
    assert tile_url(36, -10) == expected


def test_tile_url_rejects_non_int_lat_lon():
    """T-04-01: tile_url must raise TypeError if lat/lon are not int."""
    with pytest.raises(TypeError):
        tile_url(40.5, 0)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# fetch_dem integration (mocked HTTP)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_dem_skips_404_ocean_tiles(tmp_path, monkeypatch):
    """404 tiles emit 'ausente (oceano)'; mosaic continues with remaining tiles."""
    import medieval_forge.services.paths as paths_mod
    import medieval_forge.services.ingest_terrain.dem as dem_mod

    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")
    # Isolate cache so previously-downloaded real tiles cannot be used.
    monkeypatch.setattr(dem_mod, "DEM_CACHE_DIR", tmp_path / "dem_cache")

    tile_bytes = SYNTHETIC_TILE.read_bytes()
    # bbox covering exactly 2 tiles: (40,0) and (40,1)
    bbox = (0.0, 40.0, 2.0, 41.0)

    url_404 = tile_url(40, 0)
    url_200 = tile_url(40, 1)

    out_path = tmp_path / "dem.tif"
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    with respx.mock(assert_all_called=False) as mock:
        mock.get(url_404).mock(return_value=Response(404))
        mock.get(url_200).mock(return_value=Response(200, content=tile_bytes))

        def _client_factory():
            import httpx
            return httpx.AsyncClient()

        await fetch_dem(bbox, out_path, queue, client_factory=_client_factory)

    assert out_path.exists(), "raw/dem.tif should be written even when one tile is 404"

    messages = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    combined = "\n".join(m for m in messages if m is not None)
    assert "ausente (oceano)" in combined, "404 tile should emit 'ausente (oceano)' message"


@pytest.mark.asyncio
async def test_fetch_dem_concurrency_is_capped_at_four(tmp_path, monkeypatch):
    """No more than 4 tiles should be in-flight at the same time (D-08 / Semaphore(4))."""
    import medieval_forge.services.paths as paths_mod
    import medieval_forge.services.ingest_terrain.dem as dem_mod
    import httpx

    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")
    monkeypatch.setattr(dem_mod, "DEM_CACHE_DIR", tmp_path / "dem_cache")

    tile_bytes = SYNTHETIC_TILE.read_bytes()
    # bbox covering 8 tiles: lon 0..7, lat 40..41
    bbox = (0.0, 40.0, 8.0, 41.0)

    concurrency_counter = 0
    max_concurrency = 0
    counter_lock = asyncio.Lock()

    async def _slow_get(url, **kwargs):
        nonlocal concurrency_counter, max_concurrency
        async with counter_lock:
            concurrency_counter += 1
            if concurrency_counter > max_concurrency:
                max_concurrency = concurrency_counter
        await asyncio.sleep(0.05)  # simulate network latency
        async with counter_lock:
            concurrency_counter -= 1
        return httpx.Response(200, content=tile_bytes)

    class _MockClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def get(self, url, **kwargs):
            return await _slow_get(url)

    out_path = tmp_path / "dem.tif"
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    await fetch_dem(bbox, out_path, queue, client_factory=lambda: _MockClient())

    assert max_concurrency <= 4, (
        f"Expected max concurrency <= 4 (D-08), got {max_concurrency}"
    )


@pytest.mark.asyncio
async def test_fetch_dem_emits_mosaic_complete(tmp_path, monkeypatch):
    """SSE queue should contain 'mosaic_complete' after raw/dem.tif is written."""
    import medieval_forge.services.paths as paths_mod
    import medieval_forge.services.ingest_terrain.dem as dem_mod

    monkeypatch.setattr(paths_mod, "PROJECTS_ROOT", tmp_path / "projects")
    monkeypatch.setattr(dem_mod, "DEM_CACHE_DIR", tmp_path / "dem_cache")

    tile_bytes = SYNTHETIC_TILE.read_bytes()
    # Single tile bbox
    bbox = (0.0, 40.0, 1.0, 41.0)
    url_200 = tile_url(40, 0)

    out_path = tmp_path / "dem.tif"
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    with respx.mock(assert_all_called=False) as mock:
        mock.get(url_200).mock(return_value=Response(200, content=tile_bytes))

        def _client_factory():
            import httpx
            return httpx.AsyncClient()

        await fetch_dem(bbox, out_path, queue, client_factory=_client_factory)

    messages = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    combined = "\n".join(m for m in messages if m is not None)
    assert "mosaic_complete" in combined, (
        "SSE messages should contain 'mosaic_complete' after raw/dem.tif is written"
    )
