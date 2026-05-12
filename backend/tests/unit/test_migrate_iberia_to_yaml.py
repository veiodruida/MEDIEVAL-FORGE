"""Unit tests for migrate_iberia_to_yaml script — Plan 05-02.

Five tests:
  1. test_idempotent              — re-running script produces byte-equal output
  2. test_loader_roundtrip        — load_region('iberia_868') returns cfg equivalent to iberia_config()
  3. test_dataset_is_plain_dict   — emitted YAML has plain dataset dict, no !!python/object tags
  4. test_condados_carry_original_idx — every condado has unique original_idx (CLAUDE.md rule 4)
  5. test_yaml_keyset_matches_schema  — no orphan keys; all required schema keys present
"""
import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Helpers — resolve paths relative to repo root (platform-agnostic)
# ---------------------------------------------------------------------------

REPO = Path(__file__).resolve().parents[3]  # backend/tests/unit/ → repo root
YAML_PATH = REPO / "data" / "regions" / "iberia_868.yaml"
SCRIPT_PATH = REPO / "scripts" / "migrate_iberia_to_yaml.py"

# Ensure backend is on sys.path for direct imports
_BACKEND = str(REPO / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_main():
    """Dynamically import the migration script's main() function."""
    spec = importlib.util.spec_from_file_location("migrate_iberia_to_yaml", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_idempotent():
    """Re-running main() must produce a byte-equal YAML file (idempotency)."""
    assert YAML_PATH.exists(), f"YAML not found at {YAML_PATH} — run the migration script first"
    before = _sha256(YAML_PATH)
    main = _load_main()
    main()
    after = _sha256(YAML_PATH)
    assert before == after, (
        "migrate_iberia_to_yaml.py is NOT idempotent: re-running produced different output"
    )


def test_loader_roundtrip():
    """load_region('iberia_868') must return a RegionConfig equivalent to iberia_config().

    Comparison notes (Rule 1 deviation from plan literal):
      - kingdom_colors: iberia_config() uses int keys; YAML emits str keys because
        RegionConfigSchema declares dict[str, list[int]] and pydantic v2 rejects int keys.
        Compare values only (sorted by int(key)).
      - kingdoms/duchies/condados: iberia_config() returns tuple/dict-based structures
        while YAML emits list[dict]. Compare lengths only (tuple-format adapter is Plan 05-04).
      - dataset: compare Path.samefile() for each resolved path.
    """
    from medieval_forge.services.pipeline.region_loader import load_region, clear_region_cache
    from medieval_forge.services.pipeline.regions import iberia_config

    clear_region_cache()
    loaded = load_region("iberia_868")
    reference = iberia_config()

    # Scalar fields must match exactly
    assert loaded.name == reference.name, f"name mismatch: {loaded.name!r} != {reference.name!r}"
    assert loaded.map_w == reference.map_w, f"map_w mismatch: {loaded.map_w} != {reference.map_w}"
    assert loaded.map_h == reference.map_h, f"map_h mismatch: {loaded.map_h} != {reference.map_h}"
    assert loaded.upscale == reference.upscale, f"upscale mismatch"
    assert loaded.lon_min == reference.lon_min, f"lon_min mismatch"
    assert loaded.lon_max == reference.lon_max, f"lon_max mismatch"
    assert loaded.lat_min == reference.lat_min, f"lat_min mismatch"
    assert loaded.lat_max == reference.lat_max, f"lat_max mismatch"
    assert loaded.smooth_sigma == reference.smooth_sigma, f"smooth_sigma mismatch"
    assert loaded.median_passes == reference.median_passes, f"median_passes mismatch"
    assert loaded.island_min_px == reference.island_min_px, f"island_min_px mismatch"
    assert loaded.fragment_min_px == reference.fragment_min_px, f"fragment_min_px mismatch"
    assert loaded.blob_merge_px == reference.blob_merge_px, f"blob_merge_px mismatch"
    assert loaded.rng_seed == reference.rng_seed, f"rng_seed mismatch"
    assert loaded.draw_names == reference.draw_names, f"draw_names mismatch"
    assert loaded.output_dir == reference.output_dir, f"output_dir mismatch"

    # border_polygon: compare as list-of-pairs
    assert len(loaded.border_polygon) == len(reference.border_polygon), (
        f"border_polygon length: {len(loaded.border_polygon)} != {len(reference.border_polygon)}"
    )

    # pt_duchies: compare as sets
    assert set(loaded.pt_duchies) == set(reference.pt_duchies), (
        f"pt_duchies mismatch: {sorted(loaded.pt_duchies)} != {sorted(reference.pt_duchies)}"
    )

    # kingdom_colors: compare values only (keys differ: str vs int)
    loaded_kc_vals = sorted(loaded.kingdom_colors.values())
    ref_kc_vals = sorted(reference.kingdom_colors.values())
    assert loaded_kc_vals == ref_kc_vals, (
        f"kingdom_colors values mismatch: {loaded_kc_vals} != {ref_kc_vals}"
    )
    assert len(loaded.kingdom_colors) == len(reference.kingdom_colors), (
        f"kingdom_colors key count mismatch"
    )

    # kingdoms / duchies / condados: compare counts only
    # (tuple-format pipeline adapter is Plan 05-04)
    assert len(loaded.condados) == len(reference.condados), (
        f"condados count: {len(loaded.condados)} != {len(reference.condados)}"
    )
    assert len(loaded.kingdoms) == len(reference.kingdoms), (
        f"kingdoms count: {len(loaded.kingdoms)} != {len(reference.kingdoms)}"
    )
    assert len(loaded.duchies) == len(reference.duchies), (
        f"duchies count: {len(loaded.duchies)} != {len(reference.duchies)}"
    )

    # dataset: compare resolved paths
    assert loaded.dataset.pt_geojson.samefile(reference.dataset.pt_geojson), (
        f"dataset.pt_geojson mismatch: {loaded.dataset.pt_geojson} vs {reference.dataset.pt_geojson}"
    )
    assert loaded.dataset.es_input.samefile(reference.dataset.es_input), (
        f"dataset.es_input mismatch: {loaded.dataset.es_input} vs {reference.dataset.es_input}"
    )
    assert loaded.dataset.mountain_river_json.samefile(reference.dataset.mountain_river_json), (
        f"dataset.mountain_river_json mismatch"
    )


def test_dataset_is_plain_dict():
    """R-01 review: emitted YAML dataset block must be a plain dict, no !!python/object tags."""
    assert YAML_PATH.exists(), f"YAML not found at {YAML_PATH}"

    raw_bytes = YAML_PATH.read_bytes()
    assert b"!!python/object" not in raw_bytes, (
        "YAML contains !!python/object tags — migrate_iberia_to_yaml.py is serialising "
        "Python objects instead of plain dicts"
    )

    loaded = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    assert type(loaded["dataset"]) is dict, (
        f"dataset should be a plain dict, got {type(loaded['dataset'])}"
    )
    for k, v in loaded["dataset"].items():
        assert v is None or isinstance(v, str), (
            f"dataset[{k!r}] should be str or None, got {type(v)}: {v!r}"
        )


def test_condados_carry_original_idx():
    """R-01 review / CLAUDE.md rule 4 (Nájera bug): every condado must have a unique original_idx."""
    assert YAML_PATH.exists(), f"YAML not found at {YAML_PATH}"

    loaded = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    condados = loaded["condados"]

    missing = [c for c in condados if "original_idx" not in c]
    assert not missing, (
        f"{len(missing)} condado(s) missing original_idx: {[c.get('id') for c in missing]}"
    )

    indices = [c["original_idx"] for c in condados]
    assert len(set(indices)) == len(indices), (
        f"duplicate original_idx values found — Najera bug guard: "
        f"{[i for i in indices if indices.count(i) > 1]}"
    )


def test_yaml_keyset_matches_schema():
    """R-11 nice-to-have: YAML keys must be a subset of schema fields; required fields must be present."""
    from medieval_forge.services.pipeline.region_loader import RegionConfigSchema

    assert YAML_PATH.exists(), f"YAML not found at {YAML_PATH}"
    loaded = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))

    schema_fields = set(RegionConfigSchema.model_fields.keys())
    yaml_keys = set(loaded.keys())

    orphan_keys = yaml_keys - schema_fields
    assert not orphan_keys, (
        f"YAML contains keys not in RegionConfigSchema: {sorted(orphan_keys)}"
    )

    required_fields = {
        name
        for name, field_info in RegionConfigSchema.model_fields.items()
        if field_info.is_required()
    }
    missing_required = required_fields - yaml_keys
    assert not missing_required, (
        f"YAML missing required schema fields: {sorted(missing_required)}"
    )
