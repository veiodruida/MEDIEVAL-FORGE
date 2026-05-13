"""SCHEMA_INVALID coverage (D-08 + D-15) — pydantic v2 schemas in services/export/schemas.py.

Each test uses an explicit numeric/dict fixture (per user preference for
descriptive names + explicit fixtures). Fixtures mirror the canonical golden
territory_metadata.json field set; if any "valid payload" drifts, the parity
test in 06-03 will break.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from medieval_forge.services.export.schemas import (
    LookupBaronyColorsSchema,
    LookupCondadoColorsSchema,
    ManifestSchema,
    MANIFEST_SCHEMA_VERSION,
    MountainRiverDataSchema,
    TerrainTypesSchema,
    TerritoryMetadataSchema,
    ValidationReport,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Lookup colors — RGB-key dict schemas
# ---------------------------------------------------------------------------


def test_lookup_barony_colors_accepts_valid_rgb_keys() -> None:
    payload = {"50,80,30": 0, "127,255,0": 1}
    parsed = LookupBaronyColorsSchema.model_validate(payload)
    assert parsed.root == payload


def test_lookup_barony_colors_rejects_rgb_component_over_255() -> None:
    with pytest.raises(ValidationError):
        LookupBaronyColorsSchema.model_validate({"256,0,0": 0})


def test_lookup_barony_colors_rejects_non_integer_rgb_component() -> None:
    with pytest.raises(ValidationError):
        LookupBaronyColorsSchema.model_validate({"50.5,80,30": 0})


def test_lookup_condado_colors_mirrors_barony_accept_and_reject() -> None:
    valid = {"10,20,30": 5, "200,200,200": 6}
    assert LookupCondadoColorsSchema.model_validate(valid).root == valid
    with pytest.raises(ValidationError):
        LookupCondadoColorsSchema.model_validate({"999,0,0": 0})


# ---------------------------------------------------------------------------
# Terrain types
# ---------------------------------------------------------------------------


def test_terrain_types_accepts_golden_terrain_types_json() -> None:
    payload = {
        "124,179,66": {
            "name": "plains",
            "movement": 1.0,
            "defense": 0.0,
            "attack": 0.0,
        },
        "0,0,0": {
            "name": "ocean",
            "movement": 0.0,
            "defense": 0.0,
            "attack": 0.0,
        },
    }
    parsed = TerrainTypesSchema.model_validate(payload)
    assert parsed.root["124,179,66"].name == "plains"
    assert parsed.root["0,0,0"].movement == 0.0


def test_terrain_types_rejects_negative_movement_value() -> None:
    payload = {
        "124,179,66": {
            "name": "plains",
            "movement": -1.0,
            "defense": 0.0,
            "attack": 0.0,
        },
    }
    with pytest.raises(ValidationError):
        TerrainTypesSchema.model_validate(payload)


# ---------------------------------------------------------------------------
# Territory metadata — canonical Iberia 868 shape
# ---------------------------------------------------------------------------


def _minimal_valid_territory_metadata() -> dict:
    return {
        "region": "iberia",
        "map_size": [3840, 2160],
        "bounds": {
            "lon_min": -13.2,
            "lon_max": 8.2,
            "lat_min": 35.4,
            "lat_max": 44.6,
        },
        "kingdoms": {"asturias": "Reino das Astúrias"},
        "duchies": {"d_asturias": {"kingdom": "asturias", "name": "Ducado das Astúrias"}},
        "condados": [
            {
                "id": "oviedo",
                "name": "Uviéu",
                "lon": -5.84,
                "lat": 43.36,
                "duchy": "d_asturias",
                "kingdom": "asturias",
                "pixel_center": [1200, 800],
                "pixel_count": 4321,
                "baronies": ["Grado"],
                "original_idx": 1,
            }
        ],
        "baronies": [
            {
                "name": "Grado",
                "condado_idx": 0,
                "duchy": "d_asturias",
                "pixel_count": 889,
            }
        ],
    }


def test_territory_metadata_accepts_minimal_canonical_payload() -> None:
    payload = _minimal_valid_territory_metadata()
    parsed = TerritoryMetadataSchema.model_validate(payload)
    assert parsed.region == "iberia"
    assert parsed.map_size == (3840, 2160)
    assert parsed.condados[0].original_idx == 1
    assert parsed.baronies[0].pixel_count == 889


def test_territory_metadata_rejects_unknown_field_on_condado_via_extra_forbid() -> None:
    payload = _minimal_valid_territory_metadata()
    payload["condados"][0]["extra_key"] = "x"
    with pytest.raises(ValidationError):
        TerritoryMetadataSchema.model_validate(payload)


def test_territory_metadata_accepts_condado_without_original_idx() -> None:
    """D-11 enforcement (condados-only) lives in validator.py, NOT the schema layer.

    The canonical golden shape allows `original_idx` to be absent on a condado
    (it is emitted conditionally per export.py:69). The schema must mirror that.
    """
    payload = _minimal_valid_territory_metadata()
    del payload["condados"][0]["original_idx"]
    parsed = TerritoryMetadataSchema.model_validate(payload)
    assert parsed.condados[0].original_idx is None


def test_territory_metadata_rejects_zero_pixel_count_on_condado() -> None:
    payload = _minimal_valid_territory_metadata()
    payload["condados"][0]["pixel_count"] = 0
    with pytest.raises(ValidationError):
        TerritoryMetadataSchema.model_validate(payload)


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def _valid_manifest_payload() -> dict:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "region_key": "iberia_868",
        "project_id": "11111111-2222-3333-4444-555555555555",
        "generated_at_utc": "2026-05-13T12:00:00Z",
        "exported_at_utc": "20260513-120500",
        "spec_version": 1,
        "phase": 6,
        "validation_report": {"passed": True, "errors": [], "warnings": []},
        "files": [
            {
                "name": "lookup_barony.png",
                "source": "generated",
                "size_bytes": 12345,
                # Exactly 64 lowercase hex chars
                "sha256": "a" * 64,
            }
        ],
    }


def test_manifest_accepts_valid_payload_with_schema_version_2() -> None:
    parsed = ManifestSchema.model_validate(_valid_manifest_payload())
    assert parsed.schema_version == 2
    assert parsed.validation_report.passed is True
    assert parsed.files[0].sha256 == "a" * 64


def test_manifest_rejects_short_sha256_on_file_entry() -> None:
    payload = _valid_manifest_payload()
    payload["files"][0]["sha256"] = "deadbeef"
    with pytest.raises(ValidationError):
        ManifestSchema.model_validate(payload)


# ---------------------------------------------------------------------------
# Mountain/river data — permissive
# ---------------------------------------------------------------------------


def test_mountain_river_data_accepts_empty_dict_for_toy_dataset() -> None:
    parsed = MountainRiverDataSchema.model_validate({})
    assert parsed.mountains == {}
    assert parsed.rivers == {}


def test_mountain_river_data_accepts_rich_iberia_payload() -> None:
    payload = {
        "mountains": {"pyrenees": {"polygon": [[0.0, 42.0], [1.0, 43.0]]}},
        "rivers": {"tagus": {"path": [[-9.0, 38.7], [-3.7, 40.4]]}},
    }
    parsed = MountainRiverDataSchema.model_validate(payload)
    assert "pyrenees" in parsed.mountains
    assert "tagus" in parsed.rivers


def test_validation_report_passes_when_no_errors_present() -> None:
    """Sanity check on the report submodel itself — used by ManifestSchema."""
    report = ValidationReport(passed=True)
    assert report.errors == []
    assert report.warnings == []
