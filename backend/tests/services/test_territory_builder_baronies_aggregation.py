"""Etapa 7 (master plan H.7) test surface for territory_builder aggregation.

These tests exercise the new function ``assemble_territory_data_from_baronies``
which aggregates OSM-derived baronies (from ``baronies_builder``) into condados
according to ``MapResearchResult.barony_assignments`` (Etapa 3 schema).

Each condado's centroid is the arithmetic MEAN of its member-barony centroids
(no LLM-invented coords). This restores the CK3-style "baronies are organic
geometry, condados are political aggregations" architecture and closes the
geometry gap that produced the "erro 0" IndexError described in master plan
section H step 1.

Reference: C:\\Users\\veio_\\.claude\\plans\\hazy-hatching-abelson.md  H.7
"""
from __future__ import annotations

import pytest

from medieval_forge.services.territory_builder import (
    assemble_territory_data_from_baronies,
)


def _feature(barony_id: str, name: str, lon: float, lat: float) -> dict:
    """Build a minimal baronies-builder GeoJSON feature with the fields used by the aggregator."""
    return {
        "type": "Feature",
        "properties": {
            "id": barony_id,
            "name": name,
            "centroid": [lon, lat],
            "municipality_ids": [],
        },
        "geometry": {"type": "Polygon", "coordinates": []},
    }


def test_aggregates_two_baronies_into_one_condado_with_mean_centroid():
    """One condado, two baronies — centroid is arithmetic mean of both barony centroids."""
    map_research_payload = {
        "kingdoms": {"k_iberia": "Iberia"},
        "duchies": {"d_galicia": {"kingdom_id": "k_iberia", "name": "Galicia"}},
        "condados": [
            {
                "id": "C_BRAGA",
                "name": "Braga",
                "kingdom_id": "k_iberia",
                "duchy_id": "d_galicia",
            }
        ],
        "barony_assignments": {"B_001": "C_BRAGA", "B_002": "C_BRAGA"},
    }
    baronies_geojson = {
        "type": "FeatureCollection",
        "features": [
            _feature("B_001", "Braga Norte", -8.40, 41.55),
            _feature("B_002", "Braga Sul", -8.60, 41.45),
        ],
    }

    result = assemble_territory_data_from_baronies(map_research_payload, baronies_geojson)

    assert result["kingdoms"] == {"k_iberia": "Iberia"}
    assert result["duchies"] == {"d_galicia": {"kingdom_id": "k_iberia", "name": "Galicia"}}
    assert len(result["condados"]) == 1
    cid, name, lon, lat, duchy_id, baronies = result["condados"][0]
    assert cid == "C_BRAGA"
    assert name == "Braga"
    assert lon == pytest.approx(-8.50, rel=1e-9)
    assert lat == pytest.approx(41.50, rel=1e-9)
    assert duchy_id == "d_galicia"
    assert baronies == [
        ("Braga Norte", -8.40, 41.55),
        ("Braga Sul", -8.60, 41.45),
    ]


def test_two_condados_each_get_their_own_assigned_baronies():
    """Two condados (C_NORTH / C_SOUTH), 4 baronies — each condado aggregates only its assigned ones."""
    map_research_payload = {
        "kingdoms": {"k_test": "Test Kingdom"},
        "duchies": {"d_test": {"kingdom_id": "k_test", "name": "Test Duchy"}},
        "condados": [
            {"id": "C_NORTH", "name": "North", "kingdom_id": "k_test", "duchy_id": "d_test"},
            {"id": "C_SOUTH", "name": "South", "kingdom_id": "k_test", "duchy_id": "d_test"},
        ],
        "barony_assignments": {
            "B_01": "C_NORTH",
            "B_02": "C_NORTH",
            "B_03": "C_SOUTH",
            "B_04": "C_SOUTH",
        },
    }
    baronies_geojson = {
        "type": "FeatureCollection",
        "features": [
            _feature("B_01", "North-A", 0.0, 10.0),
            _feature("B_02", "North-B", 2.0, 12.0),
            _feature("B_03", "South-A", 10.0, 0.0),
            _feature("B_04", "South-B", 12.0, 2.0),
        ],
    }

    result = assemble_territory_data_from_baronies(map_research_payload, baronies_geojson)

    assert len(result["condados"]) == 2
    north = result["condados"][0]
    south = result["condados"][1]

    # North: mean of (0,10) and (2,12) = (1, 11)
    assert north[0] == "C_NORTH"
    assert north[2] == pytest.approx(1.0, rel=1e-9)
    assert north[3] == pytest.approx(11.0, rel=1e-9)
    assert north[5] == [("North-A", 0.0, 10.0), ("North-B", 2.0, 12.0)]

    # South: mean of (10,0) and (12,2) = (11, 1)
    assert south[0] == "C_SOUTH"
    assert south[2] == pytest.approx(11.0, rel=1e-9)
    assert south[3] == pytest.approx(1.0, rel=1e-9)
    assert south[5] == [("South-A", 10.0, 0.0), ("South-B", 12.0, 2.0)]


def test_unknown_barony_id_in_assignments_raises_value_error():
    """A barony_id in barony_assignments that is missing from the GeoJSON must raise ValueError naming the offending id."""
    map_research_payload = {
        "kingdoms": {"k_iberia": "Iberia"},
        "duchies": {"d_galicia": {"kingdom_id": "k_iberia", "name": "Galicia"}},
        "condados": [
            {
                "id": "C_BRAGA",
                "name": "Braga",
                "kingdom_id": "k_iberia",
                "duchy_id": "d_galicia",
            }
        ],
        "barony_assignments": {"B_999": "C_BRAGA"},
    }
    baronies_geojson = {
        "type": "FeatureCollection",
        "features": [
            _feature("B_001", "Braga Norte", -8.40, 41.55),
        ],
    }

    with pytest.raises(ValueError, match=r"B_999"):
        assemble_territory_data_from_baronies(map_research_payload, baronies_geojson)


def test_condado_with_no_assigned_baronies_raises_value_error():
    """A condado that has no barony assigned to it must raise ValueError naming the empty condado_id.

    Without this check, an empty ``baronies=[]`` would crash ``map_generator.py``
    with the "erro 0" IndexError described in master plan H.1.
    """
    map_research_payload = {
        "kingdoms": {"k_iberia": "Iberia"},
        "duchies": {"d_galicia": {"kingdom_id": "k_iberia", "name": "Galicia"}},
        "condados": [
            {
                "id": "C_BRAGA",
                "name": "Braga",
                "kingdom_id": "k_iberia",
                "duchy_id": "d_galicia",
            },
            {
                "id": "C_EMPTY",
                "name": "Empty",
                "kingdom_id": "k_iberia",
                "duchy_id": "d_galicia",
            },
        ],
        "barony_assignments": {"B_001": "C_BRAGA"},
    }
    baronies_geojson = {
        "type": "FeatureCollection",
        "features": [
            _feature("B_001", "Braga Norte", -8.40, 41.55),
        ],
    }

    with pytest.raises(ValueError, match=r"C_EMPTY"):
        assemble_territory_data_from_baronies(map_research_payload, baronies_geojson)
