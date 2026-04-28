"""Vendored country boundary lookup — Natural Earth Admin 0 (1:50m).

Replaces the previous Overpass admin_level=2 + hardcoded bbox fallback approach.
The NE Admin0 dataset ships with the package as a GeoJSON in `data/`, indexed by
ISO 3166-1 alpha-2 code. Coverage: 234 sovereign countries with valid ISO_A2.

Why not Overpass admin_level=2?
  - Overpass mirrors regularly return 406/504 (observed live). When that happens
    we fall through to a hardcoded fallback that doesn't scale to new countries.
  - NE Admin 0 is a deterministic, offline dataset with ~1km accuracy — more than
    enough to clip municipality polygons (admin_level=6) at country borders.

Lazy-loaded: the 3MB GeoJSON is parsed on first lookup and cached at module level.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from shapely.geometry import MultiPolygon, Polygon, shape

log = logging.getLogger(__name__)

# Path to the bundled NE Admin0 GeoJSON. Resolved relative to this module so the
# lookup keeps working when the package is installed via pip (data/ ships via
# pyproject.toml include-package-data).
_NE_PATH: Path = Path(__file__).resolve().parent.parent / "data" / "ne_50m_admin_0_countries.geojson"

# Module-level cache populated on first call to _ensure_loaded().
_INDEX: dict[str, Polygon | MultiPolygon] | None = None


def _ensure_loaded() -> dict[str, Polygon | MultiPolygon]:
    """Parse NE GeoJSON once and build an ISO_A2 → polygon index."""
    global _INDEX
    if _INDEX is not None:
        return _INDEX

    if not _NE_PATH.exists():
        raise FileNotFoundError(
            f"Natural Earth dataset missing: {_NE_PATH}. "
            "Reinstall the package or download the GeoJSON manually."
        )

    log.info("loading Natural Earth Admin0 boundaries from %s", _NE_PATH.name)
    data = json.loads(_NE_PATH.read_text(encoding="utf-8"))

    index: dict[str, Polygon | MultiPolygon] = {}
    for feat in data.get("features", []):
        props = feat.get("properties", {}) or {}
        # ISO_A2 is the standard ISO 3166-1 alpha-2 code. ISO_A2_EH ("Exceptional
        # Hierarchies") is NE's override for disputed/special-status entities;
        # using both fields catches countries where one is "-99" (unassigned).
        for key in ("ISO_A2", "ISO_A2_EH"):
            iso = props.get(key)
            if not iso or iso == "-99":
                continue
            iso = str(iso).upper()
            if iso in index:
                continue  # already indexed via the other key
            try:
                geom = shape(feat["geometry"])
            except Exception as exc:  # noqa: BLE001 — log + skip malformed
                log.warning("NE: skipping feature %r: bad geometry: %s", iso, exc)
                continue
            if geom.geom_type not in ("Polygon", "MultiPolygon"):
                continue
            index[iso] = geom

    log.info("Natural Earth: indexed %d countries by ISO_A2", len(index))
    _INDEX = index
    return index


def get_country_polygon(iso2: str) -> Polygon | MultiPolygon | None:
    """Return the sovereign-country polygon for `iso2` (ISO 3166-1 alpha-2).

    Returns None if the code is not in the dataset (e.g., sub-national codes
    like "WA" for Wales which is part of GB in NE).
    """
    if not iso2:
        return None
    return _ensure_loaded().get(iso2.upper())


def list_supported_isos() -> list[str]:
    """Return all ISO_A2 codes covered by the bundled NE dataset (sorted)."""
    return sorted(_ensure_loaded().keys())
