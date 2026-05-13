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

    # WR-01 regression guard (Plan 05-13): _autogen_territories deduplicates paths
    # so single-country YAMLs (France points both pt_geojson and es_input at the
    # same file) no longer double-read. Toy dataset has 40 features; bound must
    # stay tight to catch any future double-read regression. The upper bound 55
    # gives 15-feature headroom for future toy enrichment without re-tightening.
    n = len(cfg.condados)
    assert 40 <= n <= 55, (
        f"Expected 40 <= n <= 55 condados (single-country dedupe enforced); got n={n}. "
        f"If n is ~80, _autogen_territories is double-reading dataset.pt_geojson == dataset.es_input."
    )
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


def test_load_region_autogen_deterministic():
    """load_region('france_1066') is deterministic across clear_region_cache() calls.

    WR-01 regression guard (Plan 05-13): two back-to-back loads with cache cleared
    between must produce identical condado ordering, identical (lon, lat) per
    condado, and identical kingdom keys. Even if the bound test passes, a
    re-introduced double-read could produce 80 condados in a different order;
    this test catches that variant.

    After _convert_territory_data, condados are tuples (id, name, lon, lat,
    duchy_id, baronies[, original_idx]).
    """
    from medieval_forge.services.pipeline.region_loader import (  # noqa: PLC0415
        clear_region_cache,
        load_region,
    )

    clear_region_cache()
    cfg_a = load_region("france_1066")
    snapshot_a = {
        "n_condados": len(cfg_a.condados),
        "original_idx": tuple(c[6] for c in cfg_a.condados if len(c) > 6),
        "ids": tuple(c[0] for c in cfg_a.condados),
        "names": tuple(c[1] for c in cfg_a.condados),
        "lons": tuple(round(c[2], 6) for c in cfg_a.condados),
        "lats": tuple(round(c[3], 6) for c in cfg_a.condados),
        "kingdoms": tuple(sorted(cfg_a.kingdoms.keys())) if isinstance(cfg_a.kingdoms, dict) else tuple(),
    }

    clear_region_cache()
    cfg_b = load_region("france_1066")
    snapshot_b = {
        "n_condados": len(cfg_b.condados),
        "original_idx": tuple(c[6] for c in cfg_b.condados if len(c) > 6),
        "ids": tuple(c[0] for c in cfg_b.condados),
        "names": tuple(c[1] for c in cfg_b.condados),
        "lons": tuple(round(c[2], 6) for c in cfg_b.condados),
        "lats": tuple(round(c[3], 6) for c in cfg_b.condados),
        "kingdoms": tuple(sorted(cfg_b.kingdoms.keys())) if isinstance(cfg_b.kingdoms, dict) else tuple(),
    }

    assert snapshot_a == snapshot_b, (
        f"load_region('france_1066') is non-deterministic across clear_region_cache() calls:\n"
        f"  A: {snapshot_a}\n"
        f"  B: {snapshot_b}"
    )
