"""Orchestration glue for ingestion: fetch -> write GeoJSON -> update status."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from shapely.geometry import shape as _shp_shape
from shapely.ops import unary_union as _shp_unary_union
from sqlalchemy.ext.asyncio import async_sessionmaker

from ..database import AsyncSessionLocal
from ..models import Project
from . import ingest_osm, ingest_wikidata
from .paths import ensure_project_dirs

logger = logging.getLogger(__name__)


async def _set_status(
    project_id: str,
    status: str,
    session_factory: async_sessionmaker,
) -> None:
    async with session_factory() as session:
        proj = await session.get(Project, project_id)
        if proj is not None:
            proj.status = status
            await session.commit()


def _write_geojson_atomic(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)


async def _backfill_bbox(
    project_id: str,
    payload: dict[str, Any],
    session_factory: async_sessionmaker,
    queue: asyncio.Queue[str | None],
) -> None:
    """D-20: persist project.bbox = unary_union(features).bounds at end of ingestion.

    T-01-05 mitigation: only emit exc.__class__.__name__ in SSE, full repr to logger only.
    """
    features = payload.get("features", [])
    if not features:
        await queue.put("data: bbox: 0 features — pulando backfill.\n\n")
        return
    try:
        geoms = []
        for f in features:
            g = f.get("geometry")
            if g:
                geoms.append(_shp_shape(g))
        if not geoms:
            return
        minx, miny, maxx, maxy = _shp_unary_union(geoms).bounds
        async with session_factory() as session:
            proj = await session.get(Project, project_id)
            if proj is not None:
                proj.bbox_lon_min = float(minx)
                proj.bbox_lat_min = float(miny)
                proj.bbox_lon_max = float(maxx)
                proj.bbox_lat_max = float(maxy)
                await session.commit()
        await queue.put(
            f"data: bbox backfilled: lon[{minx:.3f},{maxx:.3f}] lat[{miny:.3f},{maxy:.3f}].\n\n"
        )
    except Exception as exc:
        logger.warning("bbox backfill failed: %s", exc)
        # T-01-05: only class name in SSE, full repr to logger only
        await queue.put(f"data: AVISO: bbox backfill falhou: {exc.__class__.__name__}\n\n")


async def run_ingest(
    project_id: str,
    source: str,
    country: str,
    queue: asyncio.Queue[str | None],
    db_session_factory: async_sessionmaker | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    clip_iso_codes: list[str] | None = None,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Producer task. ALWAYS puts None sentinel before returning.

    bbox: (lat_min, lon_min, lat_max, lon_max) — quando fornecido, OSM usa query
    por bounding box em vez de por país (muito mais rápido).
    clip_iso_codes: lista de ISOs para country clipping após bbox query (ex: ["ES","PT"]).
    """
    factory = db_session_factory or AsyncSessionLocal
    try:
        await queue.put(
            f"data: Iniciando ingestão {source} para projeto {project_id} "
            f"(país={country})...\n\n"
        )
        dirs = ensure_project_dirs(project_id)
        raw_path = dirs["raw"] / "municipalities.geojson"

        if source == "wikidata":
            payload = await ingest_wikidata.fetch_municipalities(country, queue)
        elif source == "osm":
            payload = await ingest_osm.fetch_municipalities(
                country, queue, bbox=bbox, clip_iso_codes=clip_iso_codes,
                stop_event=stop_event,
            )
        else:
            raise ValueError(f"unknown source: {source!r}")

        _write_geojson_atomic(raw_path, payload)
        await queue.put(
            f"data: Wrote {len(payload['features'])} features to {raw_path.name}.\n\n"
        )
        await _backfill_bbox(project_id, payload, factory, queue)
        await _set_status(project_id, "ingested", factory)
        await queue.put("data: DONE\n\n")
    except asyncio.CancelledError:
        logger.info("ingest cancelled by user for project %s", project_id)
        await queue.put("data: Cancelado pelo usuário.\n\n")
        try:
            await _set_status(project_id, "error_ingesting", factory)
        except Exception:  # noqa: BLE001
            logger.exception("failed to update status after cancellation")
    except Exception as exc:  # noqa: BLE001 — runner is top-of-task
        logger.exception("ingest failed")
        await queue.put(f"data: ERROR: {exc}\n\n")
        try:
            await _set_status(project_id, "error_ingesting", factory)
        except Exception:  # noqa: BLE001
            logger.exception("failed to update status to error_ingesting")
    finally:
        await queue.put(None)
