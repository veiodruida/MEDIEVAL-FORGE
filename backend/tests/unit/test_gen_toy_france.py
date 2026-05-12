"""Unit tests for gen_toy_france.py script and France 1066 region — Plan 05-06.

Tests:
  - test_deterministic_voronoi: sha256 equality on re-run (T-05-06-02 mitigate)
  - test_feature_count: >=40 and <=50 features (Voronoi drops infinite regions)
  - test_valid_polygons: each feature geometry.type == 'Polygon', closed ring
  - test_load_region_autogen: load_region('france_1066') autogen path
  - test_mountain_river_dict_shape: dict-of-dicts, not lists
"""
import hashlib
import json
import sys
from pathlib import Path

# Resolve repo root so scripts/ is importable
# parents[3]: unit → tests → backend → MEDIEVAL-FORGE (repo root)
_REPO = Path(__file__).resolve().parents[3]
_GEOJSON_PATH = _REPO / "data" / "regions" / "france_1066" / "inputs" / "france_municipalities_toy.geojson"
_MRD_PATH = _REPO / "data" / "regions" / "france_1066" / "inputs" / "mountain_river_data.json"

if str(_REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO / "scripts"))


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_deterministic_voronoi():
    """Re-running main() with rng_seed=42 must produce byte-equal GeoJSON output (T-05-06-02)."""
    import gen_toy_france  # noqa: PLC0415

    before = _sha256_file(_GEOJSON_PATH)
    gen_toy_france.main()
    after = _sha256_file(_GEOJSON_PATH)
    assert before == after, (
        f"GeoJSON changed on re-run: {before!r} != {after!r} — non-determinism detected"
    )


def test_feature_count():
    """Feature count must be >=40 and <=50 (Voronoi may drop infinite-region hull cells)."""
    fc = json.loads(_GEOJSON_PATH.read_text(encoding="utf-8"))
    count = len(fc["features"])
    assert 40 <= count <= 50, f"Expected 40..50 features, got {count}"


def test_valid_polygons():
    """Each feature must be a Polygon with a closed outer ring."""
    fc = json.loads(_GEOJSON_PATH.read_text(encoding="utf-8"))
    for feat in fc["features"]:
        geom = feat["geometry"]
        assert geom["type"] == "Polygon", f"Expected Polygon, got {geom['type']!r}"
        ring = geom["coordinates"][0]
        assert len(ring) >= 4, "Ring must have at least 4 points"
        assert ring[0] == ring[-1], "Ring must be closed (first == last)"


def test_load_region_autogen():
    """load_region('france_1066') must fire autogen: >=40 condados, unique original_idx, 1 kingdom 'unnamed'.

    After the 05-10 autogen fix, load_region routes autogen output through
    _convert_territory_data so cfg.condados is a list of tuples (voronoi-ready
    positional format) and cfg.kingdoms/cfg.duchies are dicts.
    Tuple layout: (id, name, lon, lat, duchy_id, baronies[, original_idx])
    """
    from medieval_forge.services.pipeline.region_loader import (  # noqa: PLC0415
        clear_region_cache,
        load_region,
    )

    clear_region_cache()
    cfg = load_region("france_1066")

    assert len(cfg.condados) >= 40, f"Expected >=40 condados, got {len(cfg.condados)}"
    # After _convert_territory_data, condados are tuples. original_idx is c[6].
    idxs = [c[6] for c in cfg.condados if len(c) > 6]
    assert len(idxs) == len(cfg.condados), (
        f"Expected all {len(cfg.condados)} condados to carry original_idx at c[6], "
        f"but only {len(idxs)} had it"
    )
    assert len(set(idxs)) == len(idxs), "original_idx values must be unique (CLAUDE.md rule 4)"
    # kingdoms is now a dict after _convert_territory_data: {"unnamed": "Unnamed Kingdom"}
    assert isinstance(cfg.kingdoms, dict), f"Expected kingdoms dict, got {type(cfg.kingdoms)}"
    assert "unnamed" in cfg.kingdoms, (
        f"Expected 'unnamed' kingdom key, got keys: {list(cfg.kingdoms.keys())}"
    )


def test_mountain_river_dict_shape():
    """mountain_river_data.json must have 'mountains': {} and 'rivers': {} (dict-of-dicts, not lists)."""
    data = json.loads(_MRD_PATH.read_text(encoding="utf-8"))
    assert "mountains" in data, "mountains key missing"
    assert "rivers" in data, "rivers key missing"
    assert data["mountains"] == {}, f"Expected mountains={{}}, got {data['mountains']!r}"
    assert data["rivers"] == {}, f"Expected rivers={{}}, got {data['rivers']!r}"
    assert isinstance(data["mountains"], dict), "mountains must be a dict (not a list)"
    assert isinstance(data["rivers"], dict), "rivers must be a dict (not a list)"
