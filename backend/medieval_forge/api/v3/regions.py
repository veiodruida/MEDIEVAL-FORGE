"""GET /api/v3/regions — list available regions discovered under data/regions/*.yaml.

Plan 05-07 (D-06): returns {key, display_name, bounds, has_dataset} per region.
`has_dataset` is true iff all dataset paths declared in the YAML exist on disk.
Alphabetical order by key ensures deterministic responses for the frontend modal.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import APIRouter

router = APIRouter(prefix="/v3/regions", tags=["v3-regions"])

# R-04 (review): permanent path-depth anchor — DO NOT change to parents[3].
# File depth: backend/medieval_forge/api/v3/regions.py
#              4         3            2   1  0
# parents[4] = repo root (parents[3] resolves to backend/ and breaks region
# discovery — same regression Plan 05-04 guards against in projects.py).
_REGIONS_DIR = Path(__file__).resolve().parents[4] / "data" / "regions"


@router.get("")
def list_regions() -> list[dict]:
    """Return a JSON array of available region descriptors, sorted alphabetically by key."""
    out: list[dict] = []
    for yaml_path in sorted(_REGIONS_DIR.glob("*.yaml"), key=lambda p: p.stem):
        try:
            with yaml_path.open("r", encoding="utf-8") as f:
                doc = yaml.safe_load(f) or {}
        except Exception:
            continue  # skip malformed YAML in discovery; loader will surface details on selection

        key = yaml_path.stem
        # R-06 (review): prefer human-readable display_name over machine key
        display_name = doc.get("display_name") or doc.get("name") or key
        bounds = {
            "lon_min": doc.get("lon_min"),
            "lon_max": doc.get("lon_max"),
            "lat_min": doc.get("lat_min"),
            "lat_max": doc.get("lat_max"),
        }

        # has_dataset: true iff ALL required dataset paths exist on disk.
        # Path traversal guard: resolved path must remain under region_root.
        dataset = doc.get("dataset") or {}
        region_root = (_REGIONS_DIR / key).resolve()
        has_dataset = True
        for field in ("pt_geojson", "es_input", "mountain_river_json"):
            rel = dataset.get(field)
            if not rel:
                has_dataset = False
                break
            resolved = (region_root / rel).resolve()
            try:
                resolved.relative_to(region_root)
            except ValueError:
                # T-05-07-01: path traversal attempt — treat as missing
                has_dataset = False
                break
            if not resolved.exists():
                has_dataset = False
                break

        out.append({
            "key": key,
            "display_name": display_name,
            "bounds": bounds,
            "has_dataset": has_dataset,
        })
    return out
